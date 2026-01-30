"""
MCP Server endpoint for Claude Code integration.

This endpoint handles MCP JSON-RPC requests and exposes the run_pipeline tool.
Authentication is via the user's MCP API key in the Authorization header.
"""

import json
import logging
from datetime import datetime
from typing import Any, Optional, cast

from fastapi import APIRouter, Header, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from app.api.research_pipeline_runs import (
    IdeaPayloadSource,
    PodLaunchError,
    create_and_launch_research_run,
    extract_user_first_name,
)
from app.config import settings
from app.services import get_database
from app.services.database.conversations import Conversation, ImportedChatMessage
from app.services.database.users import UserData
from app.services.research_pipeline.runpod import get_supported_gpu_types

router = APIRouter(tags=["mcp"])

logger = logging.getLogger(__name__)


# MCP Protocol Models
class JsonRpcRequest(BaseModel):
    jsonrpc: str = "2.0"
    id: Optional[int | str] = None
    method: str
    params: Optional[dict] = None


# Tool Definition
TOOLS = [
    {
        "name": "run_pipeline",
        "description": "Start a research pipeline run with a research idea. The idea should include a hypothesis and detailed content describing the research proposal.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "idea": {
                    "type": "string",
                    "description": "A concise, descriptive title for the research idea",
                },
                "content": {
                    "type": "string",
                    "description": """The research idea content in markdown format with the following sections:
## Short Hypothesis
[2-3 sentences describing the core hypothesis]

## Related Work
[Brief overview of relevant prior research]

## Abstract
[Comprehensive description of the research idea]

## Experiments
[Bulleted list of proposed experiments]

## Expected Outcome
[Description of anticipated results]

## Risk Factors and Limitations
[Bulleted list of potential risks and limitations]""",
                },
            },
            "required": ["idea", "content"],
        },
    }
]


async def get_user_from_mcp_token(authorization: Optional[str]) -> UserData:
    """Extract and validate user from Authorization header using MCP API key."""
    if not authorization:
        raise HTTPException(status_code=401, detail="Missing Authorization header")

    if not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=401, detail="Invalid Authorization format. Expected: Bearer <token>"
        )

    token = authorization[7:]  # Remove "Bearer " prefix

    if not token.startswith("mcp_"):
        raise HTTPException(status_code=401, detail="Invalid MCP API key format")

    db = get_database()
    user = await db.get_user_by_mcp_api_key(token)

    if not user:
        raise HTTPException(status_code=401, detail="Invalid or expired MCP API key")

    return user


def handle_initialize(_params: dict | None) -> dict:
    """Handle MCP initialize request."""
    return {
        "protocolVersion": "2024-11-05",
        "capabilities": {"tools": {}},
        "serverInfo": {"name": "research-pipeline-mcp", "version": "1.0.0"},
    }


def handle_tools_list(_params: dict | None) -> dict:
    """Handle tools/list request."""
    return {"tools": TOOLS}


async def handle_tools_call(params: dict | None, user: UserData) -> dict:
    """Handle tools/call request to run the research pipeline."""
    if not params:
        return {"content": [{"type": "text", "text": "Missing params"}], "isError": True}

    tool_name = params.get("name")
    arguments = params.get("arguments", {})

    if tool_name != "run_pipeline":
        return {
            "content": [{"type": "text", "text": f"Unknown tool: {tool_name}"}],
            "isError": True,
        }

    idea_title = arguments.get("idea", "")
    idea_content = arguments.get("content", "")

    if not idea_title or not idea_content:
        return {
            "content": [{"type": "text", "text": "Both 'idea' and 'content' are required"}],
            "isError": True,
        }

    # Check user has sufficient credits
    db = get_database()
    required_credits = settings.MIN_USER_CREDITS_FOR_RESEARCH_PIPELINE
    if required_credits > 0:
        balance = await db.get_user_wallet_balance(user.id)
        if balance < required_credits:
            return {
                "content": [
                    {
                        "type": "text",
                        "text": f"Insufficient credits. Required: {required_credits}, Available: {balance}. Please add credits at {settings.FRONTEND_URL}/billing",
                    }
                ],
                "isError": True,
            }

    try:
        # Create a conversation for this MCP-initiated run
        now = datetime.now()
        conversation = Conversation(
            url=f"mcp://{now.isoformat()}",
            title=idea_title,
            import_date=now.strftime("%Y-%m-%d"),
            imported_chat=[
                ImportedChatMessage(
                    role="user",
                    content=f"Research idea submitted via MCP:\n\n{idea_content}",
                )
            ],
        )
        conversation_id = await db.create_conversation(conversation, imported_by_user_id=user.id)

        # Create idea with initial version
        await db.create_idea(
            conversation_id=conversation_id,
            title=idea_title,
            idea_markdown=idea_content,
            created_by_user_id=user.id,
        )

        # Get the idea data for launching the run
        idea_data = await db.get_idea_by_conversation_id(conversation_id)
        if not idea_data:
            return {
                "content": [
                    {"type": "text", "text": "Failed to retrieve idea data after creation"}
                ],
                "isError": True,
            }

        # Get available GPU types
        gpu_types = get_supported_gpu_types()
        if not gpu_types:
            return {
                "content": [
                    {"type": "text", "text": "No GPU types available for research pipeline"}
                ],
                "isError": True,
            }

        # Launch the research pipeline
        requester_first_name = extract_user_first_name(full_name=user.name)

        run_id, pod_info = await create_and_launch_research_run(
            idea_data=cast(IdeaPayloadSource, idea_data),
            requested_by_first_name=requester_first_name,
            gpu_types=gpu_types,  # Pass all GPU types for fallback
            conversation_id=conversation_id,
            parent_run_id=None,
        )

        # Build the frontend URL for this run
        frontend_url = (
            f"{settings.FRONTEND_URL.rstrip('/')}/research/{conversation_id}/runs/{run_id}"
        )

        logger.info(
            "MCP pipeline launched: run_id=%s user=%s title=%s",
            run_id,
            user.email,
            idea_title,
        )

        return {
            "content": [
                {
                    "type": "text",
                    "text": json.dumps(
                        {
                            "status": "launched",
                            "run_id": run_id,
                            "pod_id": pod_info.pod_id,
                            "pod_name": pod_info.pod_name,
                            "gpu_type": pod_info.gpu_type,
                            "conversation_id": conversation_id,
                            "url": frontend_url,
                            "message": f"Research pipeline launched successfully. View at: {frontend_url}",
                        },
                        indent=2,
                    ),
                }
            ],
            "isError": False,
        }

    except PodLaunchError as exc:
        logger.exception("MCP pipeline launch failed: %s", exc)
        return {
            "content": [{"type": "text", "text": f"Failed to launch pipeline: {exc.message}"}],
            "isError": True,
        }
    except Exception as exc:
        logger.exception("Unexpected error in MCP tools/call: %s", exc)
        return {
            "content": [{"type": "text", "text": f"Internal error: {str(exc)}"}],
            "isError": True,
        }


@router.post("/mcp")
async def mcp_endpoint(
    request: Request, authorization: Optional[str] = Header(None)
) -> JSONResponse:
    """Main MCP JSON-RPC endpoint."""
    # Authenticate user via MCP API key
    user = await get_user_from_mcp_token(authorization)

    # Parse JSON-RPC request
    try:
        body = await request.json()
    except Exception:
        return JSONResponse(
            content={
                "jsonrpc": "2.0",
                "id": None,
                "error": {"code": -32700, "message": "Parse error"},
            },
            status_code=400,
        )

    rpc_request = JsonRpcRequest(**body)
    method = rpc_request.method
    params = rpc_request.params
    request_id = rpc_request.id

    logger.debug("[MCP] User: %s | Method: %s", user.email, method)

    # Route to appropriate handler
    result = None
    error = None

    if method == "initialize":
        result = handle_initialize(params)
    elif method == "notifications/initialized":
        result = {}
    elif method == "tools/list":
        result = handle_tools_list(params)
    elif method == "tools/call":
        result = await handle_tools_call(params, user)
    else:
        error = {"code": -32601, "message": f"Method not found: {method}"}

    # Build response
    response: dict[str, Any] = {"jsonrpc": "2.0", "id": request_id}
    if error:
        response["error"] = error
    else:
        response["result"] = result

    return JSONResponse(content=response)
