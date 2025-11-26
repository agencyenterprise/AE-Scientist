"""
Conversation API endpoints.

This module contains FastAPI routes for conversation management and summaries.
"""

import asyncio
import json
import logging
import re
from typing import AsyncGenerator, List, Optional, Union

from fastapi import APIRouter, Request, Response
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from app.config import settings
from app.middleware.auth import get_current_user
from app.models import (
    ConversationResponse,
    ConversationUpdate,
    Idea,
    IdeaVersion,
    ImportChatCreateNew,
    ImportChatGPTConversation,
    ImportChatPrompt,
    ImportChatUpdateExisting,
    ImportedChatMessage,
    ImportedConversationSummaryUpdate,
    ParseErrorResult,
    ParseSuccessResult,
)
from app.services import (
    AnthropicService,
    GrokService,
    Mem0Service,
    OpenAIService,
    SummarizerService,
    get_database,
)
from app.services.database import DatabaseManager
from app.services.database.conversations import Conversation as DBConversation
from app.services.database.conversations import DashboardConversation as DBDashboardConversation
from app.services.database.conversations import FullConversation as DBFullConversation
from app.services.database.conversations import ImportedChatMessage as DBImportedChatMessage
from app.services.parser_router import ParserRouterService
from app.services.prompts import get_idea_generation_prompt
from app.services.scraper.errors import ChatNotFound

router = APIRouter(prefix="/conversations")

# Initialize services
parser_service = ParserRouterService()
summarizer_service = SummarizerService()
openai_service = OpenAIService(summarizer_service)
anthropic_service = AnthropicService(summarizer_service)
grok_service = GrokService(summarizer_service)
mem0_service = Mem0Service()

logger = logging.getLogger(__name__)


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
    idea_abstract: Optional[str] = None
    last_user_message_content: Optional[str] = None
    last_assistant_message_content: Optional[str] = None


class ConversationListResponse(BaseModel):
    """Response for listing conversations."""

    conversations: List[ConversationListItem] = Field(..., description="List of conversations")


class ConversationUpdateResponse(BaseModel):
    """Response for conversation updates."""

    conversation: ConversationResponse = Field(..., description="Updated conversation")


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


def convert_db_to_api_response(db_conversation: DBFullConversation) -> ConversationResponse:
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


async def _generate_imported_chat_keywords(
    llm_provider: str, llm_model: str, imported_conversation_text: str
) -> str:
    """Generate imported chat keywords."""
    if llm_provider == "openai":
        return await openai_service.generate_imported_chat_keywords(
            llm_model, imported_conversation_text
        )
    elif llm_provider == "grok":
        return await grok_service.generate_imported_chat_keywords(
            llm_model, imported_conversation_text
        )
    elif llm_provider == "anthropic":
        return await anthropic_service.generate_imported_chat_keywords(
            llm_model, imported_conversation_text
        )
    else:
        raise ValueError(f"Unsupported LLM provider: {llm_provider}")


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
    collected_content = ""
    if llm_provider == "openai":
        async for content_chunk in openai_service.generate_idea(
            llm_model, imported_conversation, user_id, conversation_id
        ):
            collected_content += content_chunk
            yield json.dumps({"type": "content", "data": content_chunk}) + "\n"
        llm_idea = openai_service._parse_idea_response(collected_content)
    elif llm_provider == "grok":
        async for content_chunk in grok_service.generate_idea(
            llm_model, imported_conversation, user_id, conversation_id
        ):
            collected_content += content_chunk
            yield json.dumps({"type": "content", "data": content_chunk}) + "\n"
        llm_idea = grok_service._parse_idea_response(collected_content)
    elif llm_provider == "anthropic":
        async for content_chunk in anthropic_service.generate_idea(
            llm_model, imported_conversation, user_id, conversation_id
        ):
            collected_content += content_chunk
            yield json.dumps({"type": "content", "data": content_chunk}) + "\n"
        llm_idea = anthropic_service._parse_idea_response(collected_content)
    else:
        raise ValueError(f"Unsupported LLM provider: {llm_provider}")

    existing_idea = db.get_idea_by_conversation_id(conversation_id)
    if existing_idea is None:
        # Save idea to database
        db.create_idea(
            conversation_id=conversation_id,
            title=llm_idea.title,
            short_hypothesis=llm_idea.short_hypothesis,
            related_work=llm_idea.related_work,
            abstract=llm_idea.abstract,
            experiments=llm_idea.experiments,
            expected_outcome=llm_idea.expected_outcome,
            risk_factors_and_limitations=llm_idea.risk_factors_and_limitations,
            created_by_user_id=user_id,
        )
    else:
        db.update_idea_version(
            idea_id=existing_idea.idea_id,
            version_id=existing_idea.version_id,
            title=llm_idea.title,
            short_hypothesis=llm_idea.short_hypothesis,
            related_work=llm_idea.related_work,
            abstract=llm_idea.abstract,
            experiments=llm_idea.experiments,
            expected_outcome=llm_idea.expected_outcome,
            risk_factors_and_limitations=llm_idea.risk_factors_and_limitations,
            is_manual_edit=False,
        )


async def _generate_idea_consuming_yields(
    db: DatabaseManager,
    llm_provider: str,
    llm_model: str,
    conversation_id: int,
    imported_conversation: str,
    user_id: int,
) -> None:
    """Generate idea, consuming yields."""
    async for _ in _generate_idea(
        db, llm_provider, llm_model, conversation_id, imported_conversation, user_id
    ):
        pass
    return None


def _must_summarize(
    db: DatabaseManager,
    llm_provider: str,
    llm_model: str,
    messages: List[ImportedChatMessage],
    memories_block: str,
) -> bool:
    """Determine if summarization is required for a given conversation, accounting for memories context size."""

    def _estimate_tokens_from_messages() -> int:
        """Rough token estimate using character count/4 heuristic."""
        total_chars = 0
        for msg in messages:
            total_chars += len(msg.content)
        # 1 token ~ 4 chars heuristic
        return max(total_chars // 4, 0)

    def _get_context_window_tokens() -> int:
        """Get context window tokens for a given provider/model."""
        if llm_provider == "openai":
            return openai_service.get_context_window_tokens(llm_model)
        if llm_provider == "grok":
            return grok_service.get_context_window_tokens(llm_model)
        if llm_provider == "anthropic":
            return anthropic_service.get_context_window_tokens(llm_model)
        raise ValueError(f"Unsupported LLM provider: {llm_provider}")

    ctx_tokens = _get_context_window_tokens()
    system_prompt = get_idea_generation_prompt(db, memories_block)
    system_prompt_tokens = max(len(system_prompt) // 4, 0)
    message_tokens = _estimate_tokens_from_messages()
    overhead_tokens = 256
    planned_completion_tokens = settings.IDEA_MAX_COMPLETION_TOKENS
    total_planned = (
        message_tokens + system_prompt_tokens + overhead_tokens + planned_completion_tokens
    )
    must_summarize = total_planned > ctx_tokens
    return must_summarize


async def _generate_response_for_conversation(
    db: DatabaseManager, conversation_id: int
) -> AsyncGenerator[str, None]:
    """Generate response for conversation."""
    conversation = db.get_conversation_by_id(conversation_id)
    assert conversation is not None
    idea_data = db.get_idea_by_conversation_id(conversation_id)
    assert idea_data is not None
    active_version = IdeaVersion(
        version_id=idea_data.version_id,
        title=idea_data.title,
        short_hypothesis=idea_data.short_hypothesis,
        related_work=idea_data.related_work,
        abstract=idea_data.abstract,
        experiments=idea_data.experiments,
        expected_outcome=idea_data.expected_outcome,
        risk_factors_and_limitations=idea_data.risk_factors_and_limitations,
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
    db: DatabaseManager, existing_conversation_id: int, messages: List[ImportedChatMessage]
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
    db.update_conversation_messages(existing_conversation_id, db_messages)
    logger.info(
        f"Deleting imported conversation summary for conversation {existing_conversation_id}"
    )
    await summarizer_service.drop_imported_chat_summary_job(existing_conversation_id)
    db.delete_imported_conversation_summary(existing_conversation_id)

    # Will generate a new summarization in the background
    await asyncio.create_task(
        summarizer_service.create_imported_chat_summary(existing_conversation_id, messages)
    )


@router.post("/import")
async def import_conversation(
    import_data: ImportChatGPTConversation, request: Request
) -> StreamingResponse:
    """
    Import a conversation from a share URL and automatically generate an idea with streaming.
    """
    url = import_data.url.strip()
    llm_model = import_data.llm_model
    llm_provider = import_data.llm_provider
    accept_summarization = import_data.accept_summarization

    # Get authenticated user BEFORE the generator starts
    user = get_current_user(request)
    logger.debug(f"User authenticated for import: {user.email}")

    # Create async streaming response
    async def generate_import_stream() -> AsyncGenerator[str, None]:
        conversation = None
        try:
            # Validate URL format
            if not validate_import_chat_url(url):
                yield json.dumps(
                    {
                        "type": "error",
                        "data": "Invalid share URL format. Expected ChatGPT https://chatgpt.com/share/{uuid} or BranchPrompt https://v2.branchprompt.com/conversation/{24-hex} or Claude https://claude.ai/share/{uuid} or Grok https://grok.com/share/…",
                    }
                ) + "\n"
                return

            # Check if conversation already exists
            db = get_database()
            matching = db.list_conversations_by_url(url)
            # Handle duplicate resolution strategies
            if isinstance(import_data, (ImportChatPrompt,)):
                if matching:
                    yield json.dumps(
                        {
                            "type": "conflict",
                            "data": {
                                "conversations": [
                                    {
                                        "id": m.id,
                                        "title": m.title,
                                        "updated_at": m.updated_at.isoformat(),
                                        "url": m.url,
                                    }
                                    for m in matching
                                ]
                            },
                        }
                    ) + "\n"
                    return
                # No conflicts, proceed to create new
            elif isinstance(import_data, (ImportChatUpdateExisting,)):
                # Validate target id belongs to same url
                target_id = import_data.target_conversation_id
                if not any(m.id == target_id for m in matching):
                    yield json.dumps(
                        {
                            "type": "error",
                            "data": "Target conversation does not match the provided URL",
                        }
                    ) + "\n"
                    return
            elif isinstance(import_data, (ImportChatCreateNew,)):
                # Always proceed to create new, regardless of conflicts
                pass

            # Parse the conversation
            yield json.dumps({"type": "state", "data": "importing"}) + "\n"
            try:
                parse_result = await parser_service.parse_conversation(url)
            except ChatNotFound:
                # Handle 404 errors with specific error code
                yield json.dumps(
                    {
                        "type": "error",
                        "code": "CHAT_NOT_FOUND",
                        "data": "This conversation no longer exists or has been deleted",
                    }
                ) + "\n"
                return

            if not parse_result.success:
                # Type narrowing: if success is False, it's ParseErrorResult
                assert isinstance(parse_result, ParseErrorResult)
                yield json.dumps({"type": "error", "data": parse_result.error}) + "\n"
                return

            # Type narrowing: if success is True, it's ParseSuccessResult
            assert isinstance(parse_result, ParseSuccessResult)

            # Handle update_existing flow
            if isinstance(import_data, (ImportChatUpdateExisting,)):
                target_id = import_data.target_conversation_id
                await _handle_existing_conversation(db, target_id, parse_result.data.content)
                async for chunk in _generate_response_for_conversation(db, target_id):
                    yield chunk
                return

            imported_conversation_text = _imported_chat_messages_to_text(parse_result.data.content)

            yield json.dumps({"type": "state", "data": "extracting_chat_keywords"}) + "\n"
            # Build context from Mem0 memories to include it in system prompt
            imported_chat_keywords = await _generate_imported_chat_keywords(
                llm_provider=llm_provider,
                llm_model=llm_model,
                imported_conversation_text=imported_conversation_text,
            )
            if not imported_chat_keywords:
                logger.warning("No imported chat keywords generated, skipping memories generation")
                raw_memory_results: list[dict] = []
                formatted_memories_context: str = ""
            else:
                yield json.dumps({"type": "state", "data": "retrieving_memories"}) + "\n"
                raw_memory_results, formatted_memories_context = (
                    await mem0_service.generate_project_creation_memories(
                        imported_chat_keywords=imported_chat_keywords
                    )
                )
            must_summarize = _must_summarize(
                db=db,
                llm_provider=llm_provider,
                llm_model=llm_model,
                messages=parse_result.data.content,
                memories_block=formatted_memories_context,
            )
            if must_summarize:
                # The content is too long for the selected model context, so we need to summarize
                if not accept_summarization:
                    # Inform frontend to prompt user for acceptance to summarize
                    yield json.dumps(
                        {
                            "type": "model_limit_conflict",
                            "data": {
                                "message": "Imported chat is too long for the selected model context. Summarization is required and can take several minutes.",
                                "suggestion": "Consider choosing a model with a larger context window, or proceed to summarize.",
                            },
                        }
                    ) + "\n"
                    return

            # Create new conversation in the database
            conversation_id = db.create_conversation(
                conversation=DBConversation(
                    url=parse_result.data.url,
                    title=parse_result.data.title,
                    import_date=parse_result.data.import_date,
                    imported_chat=[
                        DBImportedChatMessage(
                            role=msg.role,
                            content=msg.content,
                        )
                        for msg in parse_result.data.content
                    ],
                ),
                imported_by_user_id=user.id,
            )
            conversation = db.get_conversation_by_id(conversation_id)
            assert conversation is not None

            db.store_memories_block(
                conversation_id=conversation_id,
                source="imported_chat",
                memories_block=raw_memory_results,
            )

            if must_summarize and accept_summarization:
                # The frontend has accepted to summarize, so we can proceed
                # Inform frontend and create placeholder idea, then background summarize+generate
                yield json.dumps({"type": "state", "data": "summarizing"}) + "\n"

                db.create_idea(
                    conversation_id=conversation.id,
                    title="Generating...",
                    short_hypothesis="Generating idea...",
                    related_work="",
                    abstract="Generating idea...",
                    experiments=[],
                    expected_outcome="",
                    risk_factors_and_limitations=[],
                    created_by_user_id=user.id,
                )

                async def callback_function(summary_text: str) -> None:
                    logger.info(
                        f"Summarization callback function called for conversation {conversation.id}"
                    )
                    try:
                        await _generate_idea_consuming_yields(
                            db, llm_provider, llm_model, conversation.id, summary_text, user.id
                        )
                    except Exception as e:
                        logger.exception(f"Failed to generate idea: {e}")
                        db.create_idea(
                            conversation_id=conversation.id,
                            title="Failed to Generate Idea",
                            short_hypothesis="Generation failed",
                            related_work="",
                            abstract=f"Idea generation failed: {str(e)}\n\nPlease try regenerating the idea manually.",
                            experiments=[],
                            expected_outcome="",
                            risk_factors_and_limitations=[],
                            created_by_user_id=user.id,
                        )

                asyncio.create_task(
                    summarizer_service.create_imported_chat_summary(
                        conversation.id,
                        parse_result.data.content,
                        callback_function=callback_function,
                    )
                )

                # here we will return the placeholder idea
                async for chunk in _generate_response_for_conversation(db, conversation.id):
                    yield chunk
                return

            # Happy path, the conversation is not too long for the selected model context
            # Generating an idea
            async for chunk in _generate_idea(
                db, llm_provider, llm_model, conversation.id, imported_conversation_text, user.id
            ):
                yield chunk
            # Will generate a new summarization in the background
            asyncio.create_task(
                summarizer_service.create_imported_chat_summary(
                    conversation.id,
                    parse_result.data.content,
                    callback_function=None,
                )
            )
            # finished generating an idea

            async for chunk in _generate_response_for_conversation(db, conversation.id):
                yield chunk
            return

        except Exception as e:
            logger.exception(f"Failed to generate idea: {e}")
            # Create placeholder idea
            if not conversation:
                logger.error(f"Conversation not found after import: {e}")
                return

            db.create_idea(
                conversation_id=conversation.id,
                title="Failed to Generate Idea",
                short_hypothesis="Generation failed",
                related_work="",
                abstract=f"Idea generation failed: {str(e)}\n\nPlease try regenerating the idea manually.",
                experiments=[],
                expected_outcome="",
                risk_factors_and_limitations=[],
                created_by_user_id=user.id,
            )

            async for chunk in _generate_response_for_conversation(db, conversation.id):
                yield chunk
            return

    return StreamingResponse(
        generate_import_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "Content-Type": "text/event-stream",
        },
    )


@router.get("")
async def list_conversations(
    response: Response, limit: int = 100, offset: int = 0
) -> Union[ConversationListResponse, ErrorResponse]:
    """
    Get a paginated list of all imported conversations.
    """
    if limit <= 0 or limit > 1000:
        response.status_code = 400
        return ErrorResponse(error="Invalid limit", detail="Limit must be between 1 and 1000")

    if offset < 0:
        response.status_code = 400
        return ErrorResponse(error="Invalid offset", detail="Offset must be non-negative")

    db = get_database()
    conversations: List[DBDashboardConversation] = db.list_conversations(limit=limit, offset=offset)
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
                idea_abstract=conv.idea_abstract,
                last_user_message_content=conv.last_user_message_content,
                last_assistant_message_content=conv.last_assistant_message_content,
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
        conversation = db.get_conversation_by_id(conversation_id)
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

    return convert_db_to_api_response(conversation)


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
    existing_conversation = db.get_conversation_by_id(conversation_id)
    if not existing_conversation:
        response.status_code = 404
        return ErrorResponse(error="Conversation not found", detail="Conversation not found")

    # Delete the conversation
    deleted = db.delete_conversation(conversation_id)
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
    existing_conversation = db.get_conversation_by_id(conversation_id)
    if not existing_conversation:
        response.status_code = 404
        return ErrorResponse(error="Conversation not found", detail="Conversation not found")

    # Update the conversation title
    updated = db.update_conversation_title(conversation_id, conversation_data.title)
    if not updated:
        response.status_code = 500
        return ErrorResponse(error="Update failed", detail="Failed to update conversation")

    # Return the updated conversation
    updated_conversation = db.get_conversation_by_id(conversation_id)
    if not updated_conversation:
        response.status_code = 500
        return ErrorResponse(
            error="Retrieval failed", detail="Failed to retrieve updated conversation"
        )

    return ConversationUpdateResponse(conversation=convert_db_to_api_response(updated_conversation))


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
        imported = db.get_imported_conversation_summary_by_conversation_id(conversation_id)
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
    existing_conversation = db.get_conversation_by_id(conversation_id)
    if not existing_conversation:
        response.status_code = 404
        return ErrorResponse(error="Conversation not found", detail="Conversation not found")

    # Update the conversation summary
    updated = db.update_imported_conversation_summary(conversation_id, summary_data.summary)
    if not updated:
        response.status_code = 500
        return ErrorResponse(error="Update failed", detail="Failed to update summary")

    return SummaryResponse(
        summary=summary_data.summary,
    )
