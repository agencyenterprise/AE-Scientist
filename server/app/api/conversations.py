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
from app.services import (
    AnthropicService,
    GrokService,
    OpenAIService,
    SummarizerService,
    get_database,
)
from app.services.base_llm_service import LLMIdeaGeneration
from app.services.billing_guard import enforce_minimum_credits
from app.services.database import DatabaseManager
from app.services.database.conversations import Conversation as DBConversation
from app.services.database.conversations import DashboardConversation as DBDashboardConversation
from app.services.database.conversations import FullConversation as DBFullConversation
from app.services.database.conversations import ImportedChatMessage as DBImportedChatMessage
from app.services.database.conversations import UrlConversationBrief as DBUrlConversationBrief
from app.services.database.research_pipeline_runs import ResearchPipelineRun
from app.services.database.users import UserData
from app.services.langchain_llm_service import LangChainLLMService
from app.services.parser_router import ParserRouterService
from app.services.scraper.errors import ChatNotFound

router = APIRouter(prefix="/conversations")

# Initialize services
parser_service = ParserRouterService()
openai_service = OpenAIService()
anthropic_service = AnthropicService()
grok_service = GrokService()

logger = logging.getLogger(__name__)

IDEA_SECTION_CONFIG: List[tuple[str, str, bool]] = [
    ("title", "Title", False),
    ("short_hypothesis", "Short Hypothesis", False),
    ("related_work", "Related Work", False),
    ("abstract", "Abstract", False),
    ("experiments", "Experiments", True),
    ("expected_outcome", "Expected Outcome", False),
    ("risk_factors_and_limitations", "Risk Factors and Limitations", True),
]
IDEA_SECTION_META: Dict[str, tuple[str, bool]] = {
    field: (label, expects_list) for field, label, expects_list in IDEA_SECTION_CONFIG
}


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
    idea_abstract: Optional[str] = None
    last_user_message_content: Optional[str] = None
    last_assistant_message_content: Optional[str] = None
    manual_title: Optional[str] = None
    manual_hypothesis: Optional[str] = None


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


def _format_section_value(*, value: object, expects_list: bool) -> str:
    if expects_list:
        entries: List[str] = []
        if isinstance(value, list):
            entries = [entry.strip() for entry in value if isinstance(entry, str) and entry.strip()]
        elif isinstance(value, str):
            entries = [entry.strip() for entry in value.split("\n") if entry.strip()]
        if not entries:
            return "No entries provided."
        return "\n".join(f"- {entry}" for entry in entries)

    if isinstance(value, str):
        text_value = value.strip()
    elif value is None:
        text_value = ""
    else:
        text_value = str(value).strip()
    return text_value if text_value else "Not provided."


def _format_section_from_value(field: str, value: object) -> Optional[tuple[str, str]]:
    meta = IDEA_SECTION_META.get(field)
    if not meta:
        return None
    label, expects_list = meta
    formatted_value = _format_section_value(value=value, expects_list=expects_list)
    return field, f"{label}:\n{formatted_value}\n"


def _iter_formatted_sections(idea: LLMIdeaGeneration) -> List[tuple[str, str]]:
    sections: List[tuple[str, str]] = []
    for field, _, _ in IDEA_SECTION_CONFIG:
        formatted = _format_section_from_value(field, getattr(idea, field))
        if formatted:
            sections.append(formatted)
    return sections


async def _stream_structured_idea(
    *,
    db: DatabaseManager,
    llm_service: LangChainLLMService,
    idea_stream: AsyncGenerator[str, None],
    conversation_id: int,
    user_id: int,
) -> AsyncGenerator[str, None]:
    """Persist structured idea output and stream formatted sections."""
    final_payload: Optional[str] = None
    streamed_sections: Dict[str, str] = {}

    async for content_chunk in idea_stream:
        try:
            event = json.loads(content_chunk)
        except json.JSONDecodeError:
            logger.warning("Received non-JSON chunk from idea stream: %s", content_chunk)
            continue

        event_type = event.get("event")
        if event_type == "section_delta":
            field = event.get("field")
            if not isinstance(field, str):
                continue
            formatted = _format_section_from_value(field, event.get("value"))
            if not formatted:
                continue
            field_key, section_text = formatted
            streamed_sections[field_key] = section_text
            yield json.dumps(
                {"type": "section_update", "field": field_key, "data": section_text}
            ) + "\n"
        elif event_type == "final_idea_payload":
            payload = event.get("data")
            if isinstance(payload, str):
                final_payload = payload
        else:
            logger.debug("Ignoring unknown idea stream event: %s", event_type)

    if not final_payload:
        raise ValueError("LLM did not provide a final structured idea payload.")

    llm_idea = llm_service._parse_idea_response(content=final_payload)
    existing_idea = db.get_idea_by_conversation_id(conversation_id)
    if existing_idea is None:
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

    for field_key, section_text in _iter_formatted_sections(idea=llm_idea):
        if streamed_sections.get(field_key) == section_text:
            continue
        yield json.dumps(
            {"type": "section_update", "field": field_key, "data": section_text}
        ) + "\n"


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
        _user_id=user_id,
    )
    async for chunk in _stream_structured_idea(
        db=db,
        llm_service=service,
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
        llm_model=llm_model,
        user_prompt=user_prompt,
    )
    async for chunk in _stream_structured_idea(
        db=db,
        llm_service=service,
        idea_stream=idea_stream,
        conversation_id=conversation_id,
        user_id=user_id,
    ):
        yield chunk


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
    db.update_conversation_messages(existing_conversation_id, db_messages)
    logger.info(
        f"Deleting imported conversation summary for conversation {existing_conversation_id}"
    )
    db.delete_imported_conversation_summary(existing_conversation_id)

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


def _create_conversation(
    db: DatabaseManager,
    parse_result: ParseSuccessResult,
    user_id: int,
) -> DBFullConversation:
    """Persist the imported conversation."""
    conversation_id = db.create_conversation(
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
    conversation = db.get_conversation_by_id(conversation_id)
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


def _create_failure_idea(
    db: DatabaseManager, conversation_id: int, user_id: int, error_message: str
) -> None:
    """Create a failure idea entry so the UI can show the error state."""
    db.create_idea(
        conversation_id=conversation_id,
        title="Failed to Generate Idea",
        short_hypothesis="Generation failed",
        related_work="",
        abstract=f"Idea generation failed: {error_message}\n\nPlease try regenerating the idea manually.",
        experiments=[],
        expected_outcome="",
        risk_factors_and_limitations=[],
        created_by_user_id=user_id,
    )


async def _stream_failure_response(
    db: DatabaseManager,
    conversation: DBFullConversation,
    user_id: int,
    error_message: str,
) -> AsyncGenerator[str, None]:
    """Stream the failure response after persisting the failure idea."""
    _create_failure_idea(
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
        matching = db.list_conversations_by_url(url)
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

        conversation = _create_conversation(
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
        conversation_id = db.create_manual_conversation(
            manual_title=manual_title,
            manual_hypothesis=manual_hypothesis,
            imported_by_user_id=user.id,
        )
        conversation = db.get_conversation_by_id(conversation_id)
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

    user = get_current_user(request)
    logger.debug("User authenticated for import: %s", user.email)
    enforce_minimum_credits(
        user_id=user.id,
        required=settings.MIN_USER_CREDITS_FOR_CONVERSATION,
        action="input_pipeline",
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


@router.post("/import/manual")
async def import_manual_seed(
    manual_data: ManualIdeaSeedRequest, request: Request
) -> StreamingResponse:
    """
    Generate an idea directly from a manually provided title and hypothesis.
    """
    user = get_current_user(request)
    logger.debug("User authenticated for manual import: %s", user.email)
    enforce_minimum_credits(
        user_id=user.id,
        required=settings.MIN_USER_CREDITS_FOR_CONVERSATION,
        action="input_pipeline",
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


@router.get("")
async def list_conversations(
    request: Request, response: Response, limit: int = 100, offset: int = 0
) -> Union[ConversationListResponse, ErrorResponse]:
    """
    Get a paginated list of conversations for the current user.
    """
    user = get_current_user(request)

    if limit <= 0 or limit > 1000:
        response.status_code = 400
        return ErrorResponse(error="Invalid limit", detail="Limit must be between 1 and 1000")

    if offset < 0:
        response.status_code = 400
        return ErrorResponse(error="Invalid offset", detail="Offset must be non-negative")

    db = get_database()
    conversations: List[DBDashboardConversation] = db.list_conversations(
        limit=limit, offset=offset, user_id=user.id
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
                idea_abstract=conv.idea_abstract,
                last_user_message_content=conv.last_user_message_content,
                last_assistant_message_content=conv.last_assistant_message_content,
                manual_title=conv.manual_title,
                manual_hypothesis=conv.manual_hypothesis,
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

    run_summaries = [
        _run_to_summary(run) for run in db.list_research_runs_for_conversation(conversation_id)
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
