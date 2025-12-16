"""
Pydantic models describing Server-Sent Event payloads.

These schemas mirror the streaming event objects emitted by the API so they can
be referenced in OpenAPI and consumed by the frontend via generated types.
"""

from typing import Annotated, List, Literal, Optional, Union

from pydantic import BaseModel, Field, RootModel

from app.models.conversations import ConversationResponse
from app.models.ideas import Idea
from app.models.research_pipeline import (
    ResearchRunArtifactMetadata,
    ResearchRunBestNodeSelection,
    ResearchRunEvent,
    ResearchRunInfo,
    ResearchRunLogEntry,
    ResearchRunPaperGenerationProgress,
    ResearchRunStageProgress,
    ResearchRunSubstageEvent,
    ResearchRunSubstageSummary,
    TreeVizItem,
)
from app.services.chat_models import ChatStatus

# ----------------------------------------------------------------------------
# Chat streaming SSE events
# ----------------------------------------------------------------------------


class ChatStreamDoneData(BaseModel):
    """Final payload emitted when chat streaming completes."""

    idea_updated: bool
    assistant_response: str


class ChatStreamStatusEvent(BaseModel):
    type: Literal["status"]
    data: ChatStatus


class ChatStreamContentEvent(BaseModel):
    type: Literal["content"]
    data: str


class ChatStreamIdeaUpdatedEvent(BaseModel):
    type: Literal["idea_updated"]
    data: str


class ChatStreamErrorEvent(BaseModel):
    type: Literal["error"]
    data: str


class ChatStreamDoneEvent(BaseModel):
    type: Literal["done"]
    data: ChatStreamDoneData


ChatStreamEventUnion = Annotated[
    Union[
        ChatStreamStatusEvent,
        ChatStreamContentEvent,
        ChatStreamIdeaUpdatedEvent,
        ChatStreamErrorEvent,
        ChatStreamDoneEvent,
    ],
    Field(discriminator="type"),
]


class ChatStreamEvent(RootModel[ChatStreamEventUnion]):
    """Root model exposed in OpenAPI for chat SSE events."""


# ----------------------------------------------------------------------------
# Conversation import SSE events
# ----------------------------------------------------------------------------
class ConversationImportSectionUpdateEvent(BaseModel):
    type: Literal["section_update"]
    field: str
    data: str


class ConversationImportStateEvent(BaseModel):
    type: Literal["state"]
    data: Literal["importing", "creating_manual_seed", "summarizing", "generating"]


class ConversationImportProgressPayload(BaseModel):
    phase: str
    current: int
    total: int


class ConversationImportProgressEvent(BaseModel):
    type: Literal["progress"]
    data: ConversationImportProgressPayload


class ConversationImportConflictItem(BaseModel):
    id: int
    title: str
    updated_at: str
    url: str


class ConversationImportConflictData(BaseModel):
    conversations: List[ConversationImportConflictItem]


class ConversationImportConflictEvent(BaseModel):
    type: Literal["conflict"]
    data: ConversationImportConflictData


class ConversationImportModelLimitData(BaseModel):
    message: str
    suggestion: Optional[str] = None


class ConversationImportModelLimitEvent(BaseModel):
    type: Literal["model_limit_conflict"]
    data: ConversationImportModelLimitData


class ConversationImportErrorEvent(BaseModel):
    type: Literal["error"]
    data: str
    code: Optional[str] = None


class ConversationImportDoneData(BaseModel):
    conversation: Optional[ConversationResponse] = None
    idea: Optional[Idea] = None
    error: Optional[str] = None


class ConversationImportDoneEvent(BaseModel):
    type: Literal["done"]
    data: ConversationImportDoneData


class ConversationImportContentEvent(BaseModel):
    type: Literal["content"]
    data: str


ConversationImportEventUnion = Annotated[
    Union[
        ConversationImportSectionUpdateEvent,
        ConversationImportStateEvent,
        ConversationImportProgressEvent,
        ConversationImportConflictEvent,
        ConversationImportModelLimitEvent,
        ConversationImportErrorEvent,
        ConversationImportDoneEvent,
        ConversationImportContentEvent,
    ],
    Field(discriminator="type"),
]


class ConversationImportStreamEvent(RootModel[ConversationImportEventUnion]):
    """Root model for conversation import SSE stream events."""


# ----------------------------------------------------------------------------
# Research pipeline SSE events
# ----------------------------------------------------------------------------


class ResearchRunInitialEventData(BaseModel):
    run: ResearchRunInfo
    stage_progress: List[ResearchRunStageProgress]
    logs: List[ResearchRunLogEntry]
    substage_events: List[ResearchRunSubstageEvent]
    substage_summaries: List[ResearchRunSubstageSummary]
    artifacts: List[ResearchRunArtifactMetadata]
    tree_viz: List[TreeVizItem]
    events: List[ResearchRunEvent]
    paper_generation_progress: List[ResearchRunPaperGenerationProgress]
    best_node_selections: List[ResearchRunBestNodeSelection]


class ResearchRunInitialEvent(BaseModel):
    type: Literal["initial"]
    data: ResearchRunInitialEventData


class ResearchRunCompleteData(BaseModel):
    status: Literal["pending", "running", "completed", "failed", "cancelled"]
    success: Optional[bool] = None
    message: Optional[str] = None


class ResearchRunCompleteEvent(BaseModel):
    type: Literal["complete"]
    data: ResearchRunCompleteData


class ResearchRunStageProgressEvent(BaseModel):
    type: Literal["stage_progress"]
    data: ResearchRunStageProgress


class ResearchRunRunEvent(BaseModel):
    type: Literal["run_event"]
    data: ResearchRunEvent


class ResearchRunLogEvent(BaseModel):
    type: Literal["log"]
    data: ResearchRunLogEntry


class ResearchRunBestNodeEvent(BaseModel):
    type: Literal["best_node_selection"]
    data: ResearchRunBestNodeSelection

class ResearchRunSubstageCompletedEvent(BaseModel):
    type: Literal["substage_completed"]
    data: ResearchRunSubstageEvent


class ResearchRunPaperGenerationEvent(BaseModel):
    type: Literal["paper_generation_progress"]
    data: ResearchRunPaperGenerationProgress


class ResearchRunSubstageEventStream(BaseModel):
    type: Literal["substage_event"]
    data: ResearchRunSubstageEvent


class ResearchRunSubstageSummaryEvent(BaseModel):
    type: Literal["substage_summary"]
    data: ResearchRunSubstageSummary


class ResearchRunHeartbeatEvent(BaseModel):
    type: Literal["heartbeat"]
    data: Optional[dict] = None


class ResearchRunErrorEvent(BaseModel):
    type: Literal["error"]
    data: str


ResearchRunEventUnion = Annotated[
    Union[
        ResearchRunInitialEvent,
        ResearchRunCompleteEvent,
        ResearchRunStageProgressEvent,
        ResearchRunRunEvent,
        ResearchRunLogEvent,
        ResearchRunBestNodeEvent,
        ResearchRunSubstageCompletedEvent,
        ResearchRunPaperGenerationEvent,
        ResearchRunSubstageEventStream,
        ResearchRunSubstageSummaryEvent,
        ResearchRunHeartbeatEvent,
        ResearchRunErrorEvent,
    ],
    Field(discriminator="type"),
]


class ResearchRunStreamEvent(RootModel[ResearchRunEventUnion]):
    """Root model for research pipeline SSE events."""


# ----------------------------------------------------------------------------
# Billing wallet SSE events
# ----------------------------------------------------------------------------


class WalletCreditsData(BaseModel):
    balance: int


class WalletCreditsEvent(BaseModel):
    type: Literal["credits"]
    data: WalletCreditsData


class WalletHeartbeatEvent(BaseModel):
    type: Literal["heartbeat"]
    data: Optional[dict] = None


WalletStreamEventUnion = Annotated[
    Union[WalletCreditsEvent, WalletHeartbeatEvent],
    Field(discriminator="type"),
]


class WalletStreamEvent(RootModel[WalletStreamEventUnion]):
    """Root model for wallet SSE updates."""
