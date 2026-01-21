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
    LlmReviewResponse,
    ResearchRunArtifactMetadata,
    ResearchRunBestNodeSelection,
    ResearchRunCodeExecution,
    ResearchRunEvent,
    ResearchRunInfo,
    ResearchRunLogEntry,
    ResearchRunPaperGenerationProgress,
    ResearchRunStageProgress,
    ResearchRunStageSkipWindow,
    ResearchRunSubstageEvent,
    ResearchRunSubstageSummary,
    RunType,
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


class ResearchRunHwCostEstimateData(BaseModel):
    hw_estimated_cost_cents: int = Field(
        ...,
        description="Estimated hardware cost in cents since the run started running.",
    )
    hw_cost_per_hour_cents: int = Field(
        ...,
        description="RunPod hourly cost in cents recorded at launch.",
    )
    hw_started_running_at: Optional[str] = Field(
        None,
        description="ISO timestamp when the run transitioned from pending to running.",
    )


class ResearchRunHwCostEstimateEvent(BaseModel):
    type: Literal["hw_cost_estimate"]
    data: ResearchRunHwCostEstimateData


class ResearchRunHwCostActualData(BaseModel):
    hw_actual_cost_cents: int = Field(
        ...,
        description="Actual hardware cost in cents as billed by RunPod.",
    )
    hw_actual_cost_updated_at: str = Field(
        ...,
        description="ISO timestamp when the billing summary was recorded.",
    )
    billing_summary: dict = Field(
        default_factory=dict,
        description="Raw billing summary metadata returned by RunPod.",
    )


class ResearchRunHwCostActualEvent(BaseModel):
    type: Literal["hw_cost_actual"]
    data: ResearchRunHwCostActualData


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
    stage_skip_windows: List[ResearchRunStageSkipWindow] = Field(
        default_factory=list,
        description="Recorded windows when stages became skippable.",
    )
    hw_cost_estimate: ResearchRunHwCostEstimateData | None = Field(
        None,
        description="Hardware cost estimate available when the initial snapshot was emitted.",
    )
    hw_cost_actual: ResearchRunHwCostActualData | None = Field(
        None,
        description="Hardware cost billed so far, if available.",
    )
    code_executions: dict[RunType, ResearchRunCodeExecution] = Field(
        default_factory=dict,
        description="Latest code execution snapshot per run_type for the run.",
    )


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


class ResearchRunInitializationStatusData(BaseModel):
    initialization_status: str = Field(
        ...,
        description="Latest initialization status message for the run.",
    )
    updated_at: str = Field(..., description="ISO timestamp for the status update.")


class ResearchRunInitializationStatusEvent(BaseModel):
    type: Literal["initialization_status"]
    data: ResearchRunInitializationStatusData


class ResearchRunTerminationStatusData(BaseModel):
    status: Literal["none", "requested", "in_progress", "terminated", "failed"]
    last_error: Optional[str] = None


class ResearchRunTerminationStatusEvent(BaseModel):
    type: Literal["termination_status"]
    data: ResearchRunTerminationStatusData


class ResearchRunLogEvent(BaseModel):
    type: Literal["log"]
    data: ResearchRunLogEntry


class ResearchRunBestNodeEvent(BaseModel):
    type: Literal["best_node_selection"]
    data: ResearchRunBestNodeSelection


class ResearchRunCodeExecutionStartedData(BaseModel):
    execution_id: str
    stage_name: str
    run_type: RunType
    code: str
    started_at: str


class ResearchRunCodeExecutionStartedEvent(BaseModel):
    type: Literal["code_execution_started"]
    data: ResearchRunCodeExecutionStartedData


class ResearchRunCodeExecutionCompletedData(BaseModel):
    execution_id: str
    stage_name: str
    run_type: RunType
    status: Literal["success", "failed"]
    exec_time: float
    completed_at: str


class ResearchRunCodeExecutionCompletedEvent(BaseModel):
    type: Literal["code_execution_completed"]
    data: ResearchRunCodeExecutionCompletedData


class ResearchRunStageSkipWindowUpdate(BaseModel):
    stage: str
    state: Literal["opened", "closed"]
    timestamp: str
    reason: Optional[str] = None


class ResearchRunStageSkipWindowEvent(BaseModel):
    type: Literal["stage_skip_window"]
    data: ResearchRunStageSkipWindowUpdate


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


class ResearchRunArtifactEvent(BaseModel):
    type: Literal["artifact"]
    data: ResearchRunArtifactMetadata


class ResearchRunReviewCompletedEvent(BaseModel):
    type: Literal["review_completed"]
    data: "LlmReviewResponse"


ResearchRunEventUnion = Annotated[
    Union[
        ResearchRunInitialEvent,
        ResearchRunCompleteEvent,
        ResearchRunStageProgressEvent,
        ResearchRunRunEvent,
        ResearchRunInitializationStatusEvent,
        ResearchRunTerminationStatusEvent,
        ResearchRunLogEvent,
        ResearchRunArtifactEvent,
        ResearchRunReviewCompletedEvent,
        ResearchRunBestNodeEvent,
        ResearchRunSubstageCompletedEvent,
        ResearchRunPaperGenerationEvent,
        ResearchRunSubstageEventStream,
        ResearchRunSubstageSummaryEvent,
        ResearchRunCodeExecutionStartedEvent,
        ResearchRunCodeExecutionCompletedEvent,
        ResearchRunStageSkipWindowEvent,
        ResearchRunHeartbeatEvent,
        ResearchRunHwCostEstimateEvent,
        ResearchRunHwCostActualEvent,
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
