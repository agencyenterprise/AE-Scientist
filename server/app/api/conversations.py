"""
Conversation API endpoints.

This module contains FastAPI routes for conversation management and summaries.
"""

import asyncio
import json
import logging
import re
from dataclasses import dataclass
from enum import Enum
from typing import AsyncGenerator, Dict, List, Optional, Union

from fastapi import APIRouter, Request, Response
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from app.config import settings
from app.middleware.auth import get_current_user
from app.models import (
    ConversationImportStreamEvent,
    ConversationResponse,
    ConversationUpdate,
    Idea,
    IdeaVersion,
    ImportChatGPTConversation,
    ImportChatPrompt,
    ImportChatUpdateExisting,
    ImportedChatMessage,
    ImportedConversationSummaryUpdate,
    ManualIdeaSeedRequest,
    ParseErrorResult,
    ParseSuccessResult,
    ResearchRunSummary,
)
from app.models.conversations import ModelCost, ResearchCost
from app.services import (
    AnthropicService,
    GrokService,
    OpenAIService,
    SummarizerService,
    get_database,
)
from app.services.billing_guard import charge_user_credits, enforce_minimum_credits
from app.services.cost_calculator import calculate_llm_token_usage_cost
from app.services.database import DatabaseManager
from app.services.database.conversations import CONVERSATION_STATUSES
from app.services.database.conversations import Conversation as DBConversation
from app.services.database.conversations import DashboardConversation as DBDashboardConversation
from app.services.database.conversations import FullConversation as DBFullConversation
from app.services.database.conversations import ImportedChatMessage as DBImportedChatMessage
from app.services.database.conversations import UrlConversationBrief as DBUrlConversationBrief
from app.services.database.ideas import IdeaCreationFromRunParams
from app.services.database.research_pipeline_runs import PIPELINE_RUN_STATUSES, ResearchPipelineRun
from app.services.database.users import UserData
from app.services.langchain_llm_service import LangChainLLMService
from app.services.parser_router import ParserRouterService
from app.services.prompts import format_review_feedback_message
from app.services.scraper.errors import ChatNotFound

router = APIRouter(prefix="/conversations")

# Initialize services
parser_service = ParserRouterService()
openai_service = OpenAIService()
anthropic_service = AnthropicService()
grok_service = GrokService()

logger = logging.getLogger(__name__)


def _resolve_llm_service(llm_provider: str) -> LangChainLLMService:
    """Return the configured LangChain service for the requested provider."""
    if llm_provider == "openai":
        return openai_service
    if llm_provider == "grok":
        return grok_service
    if llm_provider == "anthropic":
        return anthropic_service
    raise ValueError(f"Unsupported LLM provider: {llm_provider}")


class ImportConversationStreamError(Exception):
    """Raised to signal streamed import errors that should be sent to the client."""

    def __init__(self, payload: dict) -> None:
        super().__init__("Import conversation streaming error")
        self.payload = payload


class ImportAction(Enum):
    """Available import strategies after duplicate detection."""

    CREATE_NEW = "create_new"
    UPDATE_EXISTING = "update_existing"
    CONFLICT = "conflict"
    INVALID_TARGET = "invalid_target"


@dataclass
class ImportDecision:
    """Result of import strategy detection."""

    action: ImportAction
    target_conversation_id: Optional[int]


@dataclass
class PreparedImportContext:
    """Holds derived context used while creating a conversation."""

    imported_conversation_text: str


# Import URL validation regexes
CHATGPT_URL_PATTERN = re.compile(
    r"^https://chatgpt\.com/share/[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}$"
)
BRANCHPROMPT_URL_PATTERN = re.compile(r"^https://v2\.branchprompt\.com/conversation/[a-f0-9]{24}$")
CLAUDE_URL_PATTERN = re.compile(
    r"^https://claude\.ai/share/[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}$",
)
GROK_URL_PATTERN = re.compile(r"^https://grok\.com/share/")


def validate_import_chat_url(url: str) -> bool:
    """Validate if the URL is a valid importable conversation URL (ChatGPT, BranchPrompt, Claude, Grok)."""
    return bool(
        CHATGPT_URL_PATTERN.match(url)
        or BRANCHPROMPT_URL_PATTERN.match(url)
        or CLAUDE_URL_PATTERN.match(url)
        or GROK_URL_PATTERN.match(url)
    )


# API Response Models
class ErrorResponse(BaseModel):
    """Standard error response schema."""

    error: str = Field(..., description="Error message")
    detail: Optional[str] = Field(None, description="Additional error details")


class ConversationListItem(BaseModel):
    """Response model for dashboard list view."""

    id: int
    url: str
    title: str
    import_date: str
    created_at: str
    updated_at: str
    user_id: int
    user_name: str
    user_email: str
    idea_title: Optional[str] = None
    idea_content: Optional[str] = None
    last_user_message_content: Optional[str] = None
    last_assistant_message_content: Optional[str] = None
    manual_title: Optional[str] = None
    manual_hypothesis: Optional[str] = None
    status: str = "draft"  # Conversation status: 'draft' or 'with_research'


class ConversationListResponse(BaseModel):
    """Response for listing conversations."""

    conversations: List[ConversationListItem] = Field(..., description="List of conversations")


class ConversationUpdateResponse(BaseModel):
    """Response for conversation updates."""

    conversation: ConversationResponse = Field(..., description="Updated conversation")


class ConversationCostResponse(BaseModel):
    total_cost: float
    cost_by_model: list[ModelCost]
    cost_by_research: list[ResearchCost]


class MessageResponse(BaseModel):
    """Simple message response."""

    message: str = Field(..., description="Response message")


class IdMessageResponse(BaseModel):
    """Response with ID and message."""

    id: int = Field(..., description="Resource ID")
    message: str = Field(..., description="Response message")


class SummaryResponse(BaseModel):
    """Response for summary operations."""

    summary: str = Field(..., description="Generated or updated summary")


class SeedFromRunResponse(BaseModel):
    """Response when seeding a new idea from a run."""

    conversation_id: int = Field(..., description="ID of the new conversation")
    idea_id: int = Field(..., description="ID of the new idea")
    message: str = Field(..., description="Success message")


def convert_db_to_api_response(
    db_conversation: DBFullConversation,
    research_runs: Optional[List[ResearchRunSummary]] = None,
) -> ConversationResponse:
    """Convert NamedTuple DBFullConversation to Pydantic ConversationResponse for API responses."""
    return ConversationResponse(
        id=db_conversation.id,
        url=db_conversation.url,
        title=db_conversation.title,
        import_date=db_conversation.import_date,
        created_at=db_conversation.created_at.isoformat(),
        updated_at=db_conversation.updated_at.isoformat(),
        has_images=db_conversation.has_images,
        has_pdfs=db_conversation.has_pdfs,
        user_id=db_conversation.user_id,
        user_name=db_conversation.user_name,
        user_email=db_conversation.user_email,
        status=db_conversation.status,
        imported_chat=(
            [
                ImportedChatMessage(
                    role=msg.role,
                    content=msg.content,
                )
                for msg in db_conversation.imported_chat
            ]
            if db_conversation.imported_chat
            else None
        ),
        manual_title=db_conversation.manual_title,
        manual_hypothesis=db_conversation.manual_hypothesis,
        research_runs=research_runs or [],
        parent_run_id=db_conversation.parent_run_id,
    )


def _run_to_summary(run: ResearchPipelineRun) -> ResearchRunSummary:
    return ResearchRunSummary(
        run_id=run.run_id,
        status=run.status,
        idea_id=run.idea_id,
        idea_version_id=run.idea_version_id,
        pod_id=run.pod_id,
        pod_name=run.pod_name,
        gpu_type=run.gpu_type,
        cost=run.cost,
        public_ip=run.public_ip,
        ssh_port=run.ssh_port,
        pod_host_id=run.pod_host_id,
        error_message=run.error_message,
        last_heartbeat_at=run.last_heartbeat_at.isoformat() if run.last_heartbeat_at else None,
        heartbeat_failures=run.heartbeat_failures,
        created_at=run.created_at.isoformat(),
        updated_at=run.updated_at.isoformat(),
    )


def _imported_chat_messages_to_text(imported_chat_messages: List[ImportedChatMessage]) -> str:
    """
    Format conversation messages into readable text.

    Args:
        imported_chat_messages: List of conversation messages

    Returns:
        Formatted conversation text
    """
    formatted_messages = []

    for message in imported_chat_messages:
        role = "User" if message.role == "user" else "Assistant"
        formatted_messages.append(f"{role}: {message.content}")

    return "\n\n".join(formatted_messages)


async def _stream_structured_idea(
    *,
    db: DatabaseManager,
    idea_stream: AsyncGenerator[str, None],
    conversation_id: int,
    user_id: int,
) -> AsyncGenerator[str, None]:
    """Persist structured idea output and stream content."""
    title: Optional[str] = None
    idea_markdown: Optional[str] = None

    async for content_chunk in idea_stream:
        try:
            event = json.loads(content_chunk)
        except json.JSONDecodeError:
            logger.warning("Received non-JSON chunk from idea stream: %s", content_chunk)
            continue

        event_type = event.get("event")
        if event_type == "markdown_delta":
            # Stream markdown content chunks for UI feedback
            markdown_chunk = event.get("data")
            if markdown_chunk:
                yield json.dumps({"type": "markdown_delta", "data": markdown_chunk}) + "\n"
        elif event_type == "structured_idea_data":
            # Structured output with separate title and content
            data = event.get("data")
            if isinstance(data, dict):
                title = data.get("title", "")
                idea_markdown = data.get("content", "")
        else:
            logger.debug("Ignoring unknown idea stream event: %s", event_type)

    # Validate we received structured data
    if not title or not idea_markdown:
        raise ValueError(
            "LLM did not provide valid structured idea data (title and content required)."
        )

    existing_idea = await db.get_idea_by_conversation_id(conversation_id)
    if existing_idea is None:
        await db.create_idea(
            conversation_id=conversation_id,
            title=title,
            idea_markdown=idea_markdown,
            created_by_user_id=user_id,
        )
    else:
        await db.update_idea_version(
            idea_id=existing_idea.idea_id,
            version_id=existing_idea.version_id,
            title=title,
            idea_markdown=idea_markdown,
            is_manual_edit=False,
        )

    # Don't send "done" event here - it's sent by _generate_response_for_conversation
    # which is called after this function in the import flow


async def _generate_idea(
    db: DatabaseManager,
    llm_provider: str,
    llm_model: str,
    conversation_id: int,
    imported_conversation: str,
    user_id: int,
) -> AsyncGenerator[str, None]:
    """Generate idea, streaming the response."""
    yield json.dumps({"type": "state", "data": "generating"}) + "\n"
    service = _resolve_llm_service(llm_provider=llm_provider)
    idea_stream = service.generate_idea(
        llm_model=llm_model,
        conversation_text=imported_conversation,
        user_id=user_id,
        conversation_id=conversation_id,
    )
    async for chunk in _stream_structured_idea(
        db=db,
        idea_stream=idea_stream,
        conversation_id=conversation_id,
        user_id=user_id,
    ):
        yield chunk


async def _generate_manual_seed_idea(
    db: DatabaseManager,
    llm_provider: str,
    llm_model: str,
    conversation_id: int,
    manual_title: str,
    manual_hypothesis: str,
    user_id: int,
) -> AsyncGenerator[str, None]:
    """Generate an idea from manual seed data."""
    yield json.dumps({"type": "state", "data": "generating"}) + "\n"
    service = _resolve_llm_service(llm_provider=llm_provider)
    user_prompt = service.generate_manual_seed_idea_prompt(
        idea_title=manual_title, idea_hypothesis=manual_hypothesis
    )
    summarizer_service = SummarizerService.for_model(llm_provider, llm_model)
    asyncio.create_task(
        summarizer_service.init_chat_summary(
            conversation_id,
            [ImportedChatMessage(role="user", content=user_prompt)],
        )
    )
    idea_stream = service.generate_manual_seed_idea(
        llm_model=llm_model, user_prompt=user_prompt, conversation_id=conversation_id
    )
    async for chunk in _stream_structured_idea(
        db=db,
        idea_stream=idea_stream,
        conversation_id=conversation_id,
        user_id=user_id,
    ):
        yield chunk


async def _generate_response_for_conversation(
    db: DatabaseManager, conversation_id: int
) -> AsyncGenerator[str, None]:
    """Generate response for conversation."""
    conversation = await db.get_conversation_by_id(conversation_id)
    assert conversation is not None
    idea_data = await db.get_idea_by_conversation_id(conversation_id)
    assert idea_data is not None
    active_version = IdeaVersion(
        version_id=idea_data.version_id,
        title=idea_data.title,
        idea_markdown=idea_data.idea_markdown,
        is_manual_edit=idea_data.is_manual_edit,
        version_number=idea_data.version_number,
        created_at=idea_data.version_created_at.isoformat(),
    )
    idea = Idea(
        idea_id=idea_data.idea_id,
        conversation_id=idea_data.conversation_id,
        active_version=active_version,
        created_at=idea_data.created_at.isoformat(),
        updated_at=idea_data.updated_at.isoformat(),
    )
    response_content = {
        "conversation": convert_db_to_api_response(conversation).model_dump(),
        "idea": idea.model_dump(),
    }
    yield json.dumps({"type": "done", "data": response_content}) + "\n"


async def _handle_existing_conversation(
    db: DatabaseManager,
    existing_conversation_id: int,
    messages: List[ImportedChatMessage],
    llm_provider: str,
    llm_model: str,
) -> None:
    """Handle existing conversation, update conversation with new content, delete imported chat summary, and generate a new summarization in the background"""
    # Update existing conversation with new content
    db_messages = [
        DBImportedChatMessage(
            role=msg.role,
            content=msg.content,
        )
        for msg in messages
    ]
    await db.update_conversation_messages(existing_conversation_id, db_messages)
    logger.debug(
        f"Deleting imported conversation summary for conversation {existing_conversation_id}"
    )
    await db.delete_imported_conversation_summary(existing_conversation_id)

    # Will generate a new summarization in the background
    summarizer_service = SummarizerService.for_model(llm_provider, llm_model)
    await asyncio.create_task(
        summarizer_service.init_chat_summary(existing_conversation_id, messages)
    )


def _validate_import_url_or_raise(url: str) -> None:
    """Ensure the provided URL matches an allowed pattern."""
    if validate_import_chat_url(url=url):
        return
    raise ImportConversationStreamError(
        payload={
            "type": "error",
            "data": "Invalid share URL format. Expected ChatGPT https://chatgpt.com/share/{uuid} or BranchPrompt https://v2.branchprompt.com/conversation/{24-hex} or Claude https://claude.ai/share/{uuid} or Grok https://grok.com/share/…",
        }
    )


def _determine_import_decision(
    import_data: ImportChatGPTConversation, matching: List[DBUrlConversationBrief]
) -> ImportDecision:
    """Select how to proceed depending on the request payload and duplicates."""
    if isinstance(import_data, ImportChatPrompt):
        if matching:
            return ImportDecision(action=ImportAction.CONFLICT, target_conversation_id=None)
        return ImportDecision(action=ImportAction.CREATE_NEW, target_conversation_id=None)
    if isinstance(import_data, ImportChatUpdateExisting):
        target_id = import_data.target_conversation_id
        if any(m.id == target_id for m in matching):
            return ImportDecision(
                action=ImportAction.UPDATE_EXISTING, target_conversation_id=target_id
            )
        return ImportDecision(action=ImportAction.INVALID_TARGET, target_conversation_id=target_id)
    return ImportDecision(action=ImportAction.CREATE_NEW, target_conversation_id=None)


def _build_conflict_payload(matching: List[DBUrlConversationBrief]) -> dict:
    """Serialize conflicts so the frontend can prompt the user."""
    return {
        "type": "conflict",
        "data": {
            "conversations": [
                {
                    "id": conversation.id,
                    "title": conversation.title,
                    "updated_at": conversation.updated_at.isoformat(),
                    "url": conversation.url,
                }
                for conversation in matching
            ]
        },
    }


async def _parse_conversation_or_raise(url: str) -> ParseSuccessResult:
    """Parse an external conversation and translate failures into streamed errors."""
    try:
        parse_result = await parser_service.parse_conversation(url)
    except ChatNotFound:
        raise ImportConversationStreamError(
            payload={
                "type": "error",
                "code": "CHAT_NOT_FOUND",
                "data": "This conversation no longer exists or has been deleted",
            }
        )

    if not parse_result.success:
        assert isinstance(parse_result, ParseErrorResult)
        raise ImportConversationStreamError(payload={"type": "error", "data": parse_result.error})

    assert isinstance(parse_result, ParseSuccessResult)
    return parse_result


async def _prepare_import_context(parse_result: ParseSuccessResult) -> PreparedImportContext:
    """Prepare text context for a newly imported conversation."""
    imported_conversation_text = _imported_chat_messages_to_text(parse_result.data.content)
    return PreparedImportContext(imported_conversation_text=imported_conversation_text)


async def _create_conversation(
    db: DatabaseManager,
    parse_result: ParseSuccessResult,
    user_id: int,
) -> DBFullConversation:
    """Persist the imported conversation."""
    conversation_id = await db.create_conversation(
        conversation=DBConversation(
            url=parse_result.data.url,
            title=parse_result.data.title,
            import_date=parse_result.data.import_date,
            imported_chat=[
                DBImportedChatMessage(
                    role=message.role,
                    content=message.content,
                )
                for message in parse_result.data.content
            ],
        ),
        imported_by_user_id=user_id,
    )
    conversation = await db.get_conversation_by_id(conversation_id)
    assert conversation is not None
    return conversation


async def _stream_existing_conversation_update(
    db: DatabaseManager,
    target_id: int,
    messages: List[ImportedChatMessage],
    llm_provider: str,
    llm_model: str,
) -> AsyncGenerator[str, None]:
    """Handle the update flow for an already imported conversation."""
    await _handle_existing_conversation(
        db=db,
        existing_conversation_id=target_id,
        messages=messages,
        llm_provider=llm_provider,
        llm_model=llm_model,
    )
    async for chunk in _generate_response_for_conversation(
        db=db,
        conversation_id=target_id,
    ):
        yield chunk


async def _stream_generation_flow(
    db: DatabaseManager,
    conversation: DBFullConversation,
    llm_provider: str,
    llm_model: str,
    imported_conversation_text: str,
    messages: List[ImportedChatMessage],
    user_id: int,
) -> AsyncGenerator[str, None]:
    """
    Stream responses when the conversation fits in the model context or not.

    It uses the summarizer service to generate a summary of the conversation IF needed.
    If the conversation fits in the model context, we will use the imported conversation text.
    If the conversation does not fit in the model context, we will use the generated summary.
    """

    yield json.dumps({"type": "state", "data": "generating"}) + "\n"
    summarizer_service = SummarizerService.for_model(llm_provider, llm_model)
    _, latest_summary = await summarizer_service.init_chat_summary(
        conversation.id,
        messages,
    )

    imported_conversation = latest_summary or imported_conversation_text
    async for chunk in _generate_idea(
        db=db,
        llm_provider=llm_provider,
        llm_model=llm_model,
        conversation_id=conversation.id,
        imported_conversation=imported_conversation,
        user_id=user_id,
    ):
        yield chunk
    async for chunk in _generate_response_for_conversation(
        db=db,
        conversation_id=conversation.id,
    ):
        yield chunk


async def _stream_manual_seed_flow(
    db: DatabaseManager,
    conversation: DBFullConversation,
    llm_provider: str,
    llm_model: str,
    manual_title: str,
    manual_hypothesis: str,
    user_id: int,
) -> AsyncGenerator[str, None]:
    """Stream responses for manual idea seed flow."""
    async for chunk in _generate_manual_seed_idea(
        db=db,
        llm_provider=llm_provider,
        llm_model=llm_model,
        conversation_id=conversation.id,
        manual_title=manual_title,
        manual_hypothesis=manual_hypothesis,
        user_id=user_id,
    ):
        yield chunk
    async for chunk in _generate_response_for_conversation(
        db=db,
        conversation_id=conversation.id,
    ):
        yield chunk


async def _create_failure_idea(
    db: DatabaseManager, conversation_id: int, user_id: int, error_message: str
) -> None:
    """Create a failure idea entry so the UI can show the error state."""
    failure_title = "Failed to Generate Idea"
    failure_markdown = f"""## Short Hypothesis
Generation failed

## Related Work
(none)

## Abstract
Idea generation failed: {error_message}

Please try regenerating the idea manually.

## Experiments
(none)

## Expected Outcome
(none)

## Risk Factors and Limitations
(none)
"""
    await db.create_idea(
        conversation_id=conversation_id,
        title=failure_title,
        idea_markdown=failure_markdown,
        created_by_user_id=user_id,
    )


async def _stream_failure_response(
    db: DatabaseManager,
    conversation: DBFullConversation,
    user_id: int,
    error_message: str,
) -> AsyncGenerator[str, None]:
    """Stream the failure response after persisting the failure idea."""
    await _create_failure_idea(
        db=db,
        conversation_id=conversation.id,
        user_id=user_id,
        error_message=error_message,
    )
    async for chunk in _generate_response_for_conversation(
        db=db,
        conversation_id=conversation.id,
    ):
        yield chunk


async def _stream_import_pipeline(
    import_data: ImportChatGPTConversation,
    user: UserData,
    url: str,
    llm_model: str,
    llm_provider: str,
) -> AsyncGenerator[str, None]:
    """Main workflow for importing conversations, factored for readability."""
    db = get_database()
    conversation: Optional[DBFullConversation] = None

    try:
        _validate_import_url_or_raise(url=url)
        matching = await db.list_conversations_by_url(url)
        decision = _determine_import_decision(import_data=import_data, matching=matching)
        if decision.action == ImportAction.CONFLICT:
            raise ImportConversationStreamError(payload=_build_conflict_payload(matching=matching))
        if decision.action == ImportAction.INVALID_TARGET:
            raise ImportConversationStreamError(
                payload={
                    "type": "error",
                    "data": "Target conversation does not match the provided URL",
                }
            )

        yield json.dumps({"type": "state", "data": "importing"}) + "\n"
        parse_result = await _parse_conversation_or_raise(url=url)

        if decision.action == ImportAction.UPDATE_EXISTING:
            assert decision.target_conversation_id is not None
            async for chunk in _stream_existing_conversation_update(
                db=db,
                target_id=decision.target_conversation_id,
                messages=parse_result.data.content,
                llm_provider=llm_provider,
                llm_model=llm_model,
            ):
                yield chunk
            return

        prepared_context = await _prepare_import_context(parse_result=parse_result)

        conversation = await _create_conversation(
            db=db,
            parse_result=parse_result,
            user_id=user.id,
        )

        async for chunk in _stream_generation_flow(
            db=db,
            conversation=conversation,
            llm_provider=llm_provider,
            llm_model=llm_model,
            imported_conversation_text=prepared_context.imported_conversation_text,
            messages=parse_result.data.content,
            user_id=user.id,
        ):
            yield chunk
        return
    except ImportConversationStreamError as stream_error:
        yield json.dumps(stream_error.payload) + "\n"
        return
    except Exception as exc:
        logger.exception("Failed to generate idea: %s", exc)
        if conversation is None:
            logger.error("Conversation not found after import: %s", exc)
            return
        async for chunk in _stream_failure_response(
            db=db,
            conversation=conversation,
            user_id=user.id,
            error_message=str(exc),
        ):
            yield chunk
        return


async def _stream_manual_seed_pipeline(
    manual_data: ManualIdeaSeedRequest,
    user: UserData,
) -> AsyncGenerator[str, None]:
    """Workflow for generating ideas directly from manual seed data."""
    db = get_database()
    conversation: Optional[DBFullConversation] = None

    manual_title = manual_data.idea_title.strip()
    manual_hypothesis = manual_data.idea_hypothesis.strip()
    try:
        yield json.dumps({"type": "state", "data": "creating_manual_seed"}) + "\n"
        conversation_id = await db.create_manual_conversation(
            manual_title=manual_title,
            manual_hypothesis=manual_hypothesis,
            imported_by_user_id=user.id,
        )
        conversation = await db.get_conversation_by_id(conversation_id)
        assert conversation is not None

        async for chunk in _stream_manual_seed_flow(
            db=db,
            conversation=conversation,
            llm_provider=manual_data.llm_provider,
            llm_model=manual_data.llm_model,
            manual_title=manual_title,
            manual_hypothesis=manual_hypothesis,
            user_id=user.id,
        ):
            yield chunk
        return
    except Exception as exc:
        logger.exception("Failed manual idea seed flow: %s", exc)
        if conversation is None:
            logger.error("Manual conversation not created: %s", exc)
            return
        async for chunk in _stream_failure_response(
            db=db,
            conversation=conversation,
            user_id=user.id,
            error_message=str(exc),
        ):
            yield chunk
        return


@router.post(
    "/import",
    response_model=ConversationImportStreamEvent,
    responses={
        200: {
            "description": "Server-sent events emitted while importing a conversation",
            "content": {
                "text/event-stream": {
                    "schema": {"$ref": "#/components/schemas/ConversationImportStreamEvent"}
                }
            },
        }
    },
)
async def import_conversation(
    import_data: ImportChatGPTConversation, request: Request
) -> StreamingResponse:
    """
    Import a conversation from a share URL and automatically generate an idea with streaming.
    """
    url = import_data.url.strip()
    llm_model = import_data.llm_model
    llm_provider = import_data.llm_provider

    user = get_current_user(request)
    logger.debug("User authenticated for import: %s", user.email)
    await enforce_minimum_credits(
        user_id=user.id,
        required=settings.MIN_USER_CREDITS_FOR_CONVERSATION,
        action="input_pipeline",
    )
    await charge_user_credits(
        user_id=user.id,
        cost=settings.CHAT_MESSAGE_CREDIT_COST,
        action="conversation_import",
        description="Conversation import request",
        metadata={
            "url": url,
            "llm_provider": llm_provider,
            "llm_model": llm_model,
        },
    )

    async def generate_import_stream() -> AsyncGenerator[str, None]:
        async for chunk in _stream_import_pipeline(
            import_data=import_data,
            user=user,
            url=url,
            llm_model=llm_model,
            llm_provider=llm_provider,
        ):
            yield chunk

    return StreamingResponse(
        generate_import_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "Content-Type": "text/event-stream",
        },
    )


@router.post(
    "/import/manual",
    response_model=ConversationImportStreamEvent,
    responses={
        200: {
            "description": "Server-sent events emitted while generating an idea from manual seed data",
            "content": {
                "text/event-stream": {
                    "schema": {"$ref": "#/components/schemas/ConversationImportStreamEvent"}
                }
            },
        }
    },
)
async def import_manual_seed(
    manual_data: ManualIdeaSeedRequest, request: Request
) -> StreamingResponse:
    """
    Generate an idea directly from a manually provided title and hypothesis.
    """
    user = get_current_user(request)
    logger.debug("User authenticated for manual import: %s", user.email)
    await enforce_minimum_credits(
        user_id=user.id,
        required=settings.MIN_USER_CREDITS_FOR_CONVERSATION,
        action="input_pipeline",
    )
    await charge_user_credits(
        user_id=user.id,
        cost=settings.CHAT_MESSAGE_CREDIT_COST,
        action="manual_import",
        description="Manual idea seed request",
        metadata={
            "idea_title": manual_data.idea_title.strip(),
            "llm_provider": manual_data.llm_provider,
            "llm_model": manual_data.llm_model,
        },
    )

    async def generate_manual_stream() -> AsyncGenerator[str, None]:
        async for chunk in _stream_manual_seed_pipeline(manual_data=manual_data, user=user):
            yield chunk

    return StreamingResponse(
        generate_manual_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "Content-Type": "text/event-stream",
        },
    )


@router.post(
    "/{conversation_id}/idea/research-run/{run_id}/seed-new-idea",
    response_model=SeedFromRunResponse,
)
async def seed_idea_from_run(
    conversation_id: int,
    run_id: str,
    request: Request,
    response: Response,
) -> Union[SeedFromRunResponse, ErrorResponse]:
    """
    Seed a new idea from a completed research run.

    Creates a new conversation and idea by copying the idea version data
    from the specified run. The new conversation is linked to the parent run via
    parent_run_id.

    Args:
        conversation_id: ID of the conversation containing the source idea
        run_id: ID of the research run to seed from
        request: FastAPI request object
        response: FastAPI response object

    Returns:
        SeedFromRunResponse with new conversation_id and idea_id

    Raises:
        404: If conversation, run, or idea not found
        403: If user doesn't own the conversation
        400: If run is not completed
    """
    user = get_current_user(request)
    db = get_database()

    # Validate conversation exists and user owns it
    conversation = await db.get_conversation_by_id(conversation_id)
    if not conversation:
        response.status_code = 404
        return ErrorResponse(
            error="Conversation not found",
            detail=f"No conversation found with ID {conversation_id}",
        )

    if conversation.user_id != user.id:
        response.status_code = 403
        return ErrorResponse(
            error="Forbidden",
            detail="You don't have permission to seed from this conversation",
        )

    # Validate run exists and belongs to this conversation
    run = await db.get_run_for_conversation(
        run_id=run_id,
        conversation_id=conversation_id,
    )
    if not run:
        response.status_code = 404
        return ErrorResponse(
            error="Run not found",
            detail=f"No run found with ID {run_id} for conversation {conversation_id}",
        )

    # Validate run is completed
    if run.status != "completed":
        response.status_code = 400
        return ErrorResponse(
            error="Invalid run status",
            detail=f"Can only seed from completed runs. Run status is '{run.status}'",
        )

    # Get the idea version used in this run
    source_version_id = run.idea_version_id

    try:
        # Create new conversation
        new_conversation_id = await db.create_seeded_conversation(
            parent_run_id=run_id,
            imported_by_user_id=user.id,
        )

        # Create new idea from run's version
        new_idea_id = await db.create_idea_from_run(
            params=IdeaCreationFromRunParams(
                conversation_id=new_conversation_id,
                source_version_id=source_version_id,
                created_by_user_id=user.id,
            ),
        )

        # Fetch LLM review for this run and create initial improvement message
        review_data = await db.get_review_by_run_id(run_id=run_id)
        if review_data:
            # Format the review feedback into a user message
            improvement_message = format_review_feedback_message(review_data=review_data)

            # Create initial chat message asking LLM to help improve the idea
            await db.create_chat_message(
                idea_id=new_idea_id,
                role="user",
                content=improvement_message,
                sent_by_user_id=user.id,
            )

            logger.debug(
                f"Created initial improvement message for seeded idea {new_idea_id} "
                f"based on review from run {run_id}. Frontend will auto-trigger SSE streaming."
            )

        logger.debug(
            f"User {user.id} seeded new idea {new_idea_id} from run {run_id} "
            f"(conversation {new_conversation_id})"
        )

        return SeedFromRunResponse(
            conversation_id=new_conversation_id,
            idea_id=new_idea_id,
            message=f"Successfully seeded new idea from run {run_id}",
        )

    except ValueError as exc:
        logger.exception(f"Failed to seed idea from run {run_id}: {exc}")
        response.status_code = 400
        return ErrorResponse(
            error="Seed failed",
            detail=str(exc),
        )
    except Exception as exc:
        logger.exception(f"Unexpected error seeding from run {run_id}: {exc}")
        response.status_code = 500
        return ErrorResponse(
            error="Internal server error",
            detail="Failed to seed new idea. Please try again.",
        )


@router.get("")
async def list_conversations(
    request: Request,
    response: Response,
    limit: int = 100,
    offset: int = 0,
    conversation_status: str | None = None,
    run_status: str | None = None,
) -> Union[ConversationListResponse, ErrorResponse]:
    """
    Get a paginated list of conversations for the current user.

    Query Parameters:
    - conversation_status: Filter by "draft" or "with_research" (optional)
    - run_status: Filter by "pending", "running", "completed", or "failed" (optional)
    """
    user = get_current_user(request)

    if limit <= 0 or limit > 1000:
        response.status_code = 400
        return ErrorResponse(error="Invalid limit", detail="Limit must be between 1 and 1000")

    if offset < 0:
        response.status_code = 400
        return ErrorResponse(error="Invalid offset", detail="Offset must be non-negative")

    # Validate conversation_status
    if conversation_status is not None and conversation_status not in CONVERSATION_STATUSES:
        response.status_code = 400
        return ErrorResponse(
            error="Invalid conversation_status",
            detail=f"Must be one of: {', '.join(CONVERSATION_STATUSES)}",
        )

    # Validate run_status
    if run_status is not None and run_status not in PIPELINE_RUN_STATUSES:
        response.status_code = 400
        return ErrorResponse(
            error="Invalid run_status", detail=f"Must be one of: {', '.join(PIPELINE_RUN_STATUSES)}"
        )

    db = get_database()
    conversations: List[DBDashboardConversation] = await db.list_conversations(
        limit=limit,
        offset=offset,
        user_id=user.id,
        conversation_status=conversation_status,
        run_status=run_status,
    )

    return ConversationListResponse(
        conversations=[
            ConversationListItem(
                id=conv.id,
                url=conv.url,
                title=conv.title,
                import_date=conv.import_date,
                created_at=conv.created_at.isoformat(),
                updated_at=conv.updated_at.isoformat(),
                user_id=conv.user_id,
                user_name=conv.user_name,
                user_email=conv.user_email,
                idea_title=conv.idea_title,
                idea_content=conv.idea_markdown,  # Pass full markdown, frontend handles preview
                last_user_message_content=conv.last_user_message_content,
                last_assistant_message_content=conv.last_assistant_message_content,
                manual_title=conv.manual_title,
                manual_hypothesis=conv.manual_hypothesis,
                status=conv.status,
            )
            for conv in conversations
        ]
    )


@router.get("/{conversation_id}")
async def get_conversation(
    conversation_id: int, response: Response
) -> Union[ConversationResponse, ErrorResponse]:
    """
    Get a specific conversation by ID with complete details.
    """
    if conversation_id <= 0:
        response.status_code = 400
        return ErrorResponse(
            error="Invalid conversation ID", detail="Conversation ID must be positive"
        )

    db = get_database()
    try:
        conversation = await db.get_conversation_by_id(conversation_id)
    except Exception as e:
        logger.exception(f"Error getting conversation: {e}")
        response.status_code = 500
        return ErrorResponse(error="Database error", detail=str(e))

    if not conversation:
        response.status_code = 404
        return ErrorResponse(
            error="Conversation not found",
            detail=f"No conversation found with ID {conversation_id}",
        )

    run_summaries = [
        _run_to_summary(run)
        for run in await db.list_research_runs_for_conversation(conversation_id)
    ]
    return convert_db_to_api_response(conversation, research_runs=run_summaries)


@router.delete("/{conversation_id}")
async def delete_conversation(
    conversation_id: int, response: Response
) -> Union[MessageResponse, ErrorResponse]:
    """
    Delete a specific conversation by ID.
    """
    if conversation_id <= 0:
        response.status_code = 400
        return ErrorResponse(
            error="Invalid conversation ID", detail="Conversation ID must be positive"
        )

    db = get_database()

    # Check if conversation exists first
    existing_conversation = await db.get_conversation_by_id(conversation_id)
    if not existing_conversation:
        response.status_code = 404
        return ErrorResponse(error="Conversation not found", detail="Conversation not found")

    # Delete the conversation
    deleted = await db.delete_conversation(conversation_id)
    if not deleted:
        response.status_code = 500
        return ErrorResponse(error="Delete failed", detail="Failed to delete conversation")

    return MessageResponse(message="Conversation deleted successfully")


@router.patch("/{conversation_id}")
async def update_conversation(
    conversation_id: int, conversation_data: ConversationUpdate, response: Response
) -> Union[ConversationUpdateResponse, ErrorResponse]:
    """
    Update a conversation's title.
    """
    if conversation_id <= 0:
        response.status_code = 400
        return ErrorResponse(
            error="Invalid conversation ID", detail="Conversation ID must be positive"
        )

    db = get_database()

    # Check if conversation exists first
    existing_conversation = await db.get_conversation_by_id(conversation_id)
    if not existing_conversation:
        response.status_code = 404
        return ErrorResponse(error="Conversation not found", detail="Conversation not found")

    # Update the conversation title
    updated = await db.update_conversation_title(conversation_id, conversation_data.title)
    if not updated:
        response.status_code = 500
        return ErrorResponse(error="Update failed", detail="Failed to update conversation")

    # Return the updated conversation
    updated_conversation = await db.get_conversation_by_id(conversation_id)
    if not updated_conversation:
        response.status_code = 500
        return ErrorResponse(
            error="Retrieval failed", detail="Failed to retrieve updated conversation"
        )

    return ConversationUpdateResponse(conversation=convert_db_to_api_response(updated_conversation))


@router.get("/{conversation_id}/costs")
async def get_conversation_costs(
    conversation_id: int, response: Response
) -> Union[ConversationCostResponse, ErrorResponse]:
    """
    Get the cost breakdown for a specific conversation.
    """
    if conversation_id <= 0:
        response.status_code = 400
        return ErrorResponse(
            error="Invalid conversation ID", detail="Conversation ID must be positive"
        )

    db = get_database()
    try:
        researches_token_usage = (
            await db.get_llm_token_usages_by_conversation_aggregated_by_run_and_model(
                conversation_id
            )
        )
        conversation_token_usage = (
            await db.get_llm_token_usages_by_conversation_aggregated_by_model(conversation_id)
        )

        researches_token_usage_cost = calculate_llm_token_usage_cost(researches_token_usage)
        conversation_token_usage_cost = calculate_llm_token_usage_cost(conversation_token_usage)

        total_cost = sum(
            [
                cost.input_cost + cost.output_cost
                for cost in researches_token_usage_cost + conversation_token_usage_cost
            ]
        )

        conversation_cost_by_model: Dict[str, ModelCost] = {}
        for cost in conversation_token_usage_cost:
            if cost.model not in conversation_cost_by_model:
                conversation_cost_by_model[cost.model] = ModelCost(
                    model=cost.model, cost=cost.input_cost + cost.output_cost
                )
            else:
                conversation_cost_by_model[cost.model].cost += cost.input_cost + cost.output_cost

        researches_cost_by_run_id: Dict[str, ResearchCost] = {}
        for cost in researches_token_usage_cost:
            if not cost.run_id:
                continue
            if cost.run_id not in researches_cost_by_run_id:
                researches_cost_by_run_id[cost.run_id] = ResearchCost(
                    run_id=cost.run_id, cost=cost.input_cost + cost.output_cost
                )
            else:
                researches_cost_by_run_id[cost.run_id].cost += cost.input_cost + cost.output_cost

        return ConversationCostResponse(
            total_cost=total_cost,
            cost_by_model=list(conversation_cost_by_model.values()),
            cost_by_research=list(researches_cost_by_run_id.values()),
        )
    except Exception as e:
        logger.exception(f"Error getting conversation costs: {e}")
        response.status_code = 500
        return ErrorResponse(error="Database error", detail=str(e))


@router.get("/{conversation_id}/imported_chat_summary")
async def get_conversation_summary(
    conversation_id: int, response: Response
) -> Union[SummaryResponse, ErrorResponse]:
    """
    Get the current summary for a conversation.

    Prefers the imported conversation summary, falls back to chat summary, then to
    concatenated imported chat messages if neither exists.
    """
    if conversation_id <= 0:
        response.status_code = 400
        return ErrorResponse(
            error="Invalid conversation ID", detail="Conversation ID must be positive"
        )

    db = get_database()
    try:
        imported = await db.get_imported_conversation_summary_by_conversation_id(conversation_id)
        if imported and imported.summary:
            return SummaryResponse(summary=imported.summary)
        response.status_code = 404
        return ErrorResponse(error="Imported chat summary not found", detail="")
    except Exception as e:
        logger.exception(f"Failed to get conversation summary for {conversation_id}: {e}")
        response.status_code = 500
        return ErrorResponse(error="Database error", detail=str(e))


@router.patch("/{conversation_id}/summary")
async def update_conversation_summary(
    conversation_id: int, summary_data: ImportedConversationSummaryUpdate, response: Response
) -> Union[SummaryResponse, ErrorResponse]:
    """
    Update a conversation's summary.
    """
    if conversation_id <= 0:
        response.status_code = 400
        return ErrorResponse(
            error="Invalid conversation ID", detail="Conversation ID must be positive"
        )

    db = get_database()

    # Check if conversation exists first
    existing_conversation = await db.get_conversation_by_id(conversation_id)
    if not existing_conversation:
        response.status_code = 404
        return ErrorResponse(error="Conversation not found", detail="Conversation not found")

    # Update the conversation summary
    updated = await db.update_imported_conversation_summary(conversation_id, summary_data.summary)
    if not updated:
        response.status_code = 500
        return ErrorResponse(error="Update failed", detail="Failed to update summary")

    return SummaryResponse(
        summary=summary_data.summary,
    )
