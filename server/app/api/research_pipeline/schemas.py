"""Pydantic schemas for research pipeline event webhooks and file uploads."""

from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field

from app.models.research_pipeline import RunType

# ============================================================================
# Event Webhook Payloads
# ============================================================================


class StageProgressEvent(BaseModel):
    stage: str
    iteration: int
    max_iterations: int
    progress: float
    total_nodes: int
    buggy_nodes: int
    good_nodes: int
    best_metric: Optional[str] = None
    eta_s: Optional[int] = None
    latest_iteration_time_s: Optional[int] = None


class StageProgressPayload(BaseModel):
    event: StageProgressEvent


class SubstageCompletedEvent(BaseModel):
    stage: str
    main_stage_number: int
    reason: str
    summary: Dict[str, Any]


class SubstageCompletedPayload(BaseModel):
    event: SubstageCompletedEvent


class SubstageSummaryEvent(BaseModel):
    stage: str
    summary: Dict[str, Any]


class SubstageSummaryPayload(BaseModel):
    event: SubstageSummaryEvent


class RunStartedPayload(BaseModel):
    pass


class RunFinishedPayload(BaseModel):
    success: bool
    message: Optional[str] = None


class InitializationProgressPayload(BaseModel):
    message: str


class DiskUsagePartition(BaseModel):
    partition: str
    total_bytes: int
    used_bytes: int


class HardwareStatsPartition(BaseModel):
    partition: str
    used_bytes: int


class HeartbeatPayload(BaseModel):
    pass


class HardwareStatsPayload(BaseModel):
    partitions: List[HardwareStatsPartition] = Field(default_factory=list)


class GPUShortagePayload(BaseModel):
    required_gpus: int
    available_gpus: int
    message: Optional[str] = None


class PaperGenerationProgressEvent(BaseModel):
    step: str
    substep: Optional[str] = None
    progress: float
    step_progress: float
    details: Optional[Dict[str, Any]] = None


class PaperGenerationProgressPayload(BaseModel):
    event: PaperGenerationProgressEvent


class ArtifactUploadedEvent(BaseModel):
    artifact_type: str
    filename: str
    file_size: int
    file_type: str
    created_at: str


class ArtifactUploadedPayload(BaseModel):
    event: ArtifactUploadedEvent


class ReviewCompletedEvent(BaseModel):
    summary: str
    strengths: List[str]
    weaknesses: List[str]
    originality: int
    quality: int
    clarity: int
    significance: int
    questions: List[str]
    limitations: List[str]
    ethical_concerns: bool
    soundness: int
    presentation: int
    contribution: int
    overall: int
    confidence: int
    decision: str
    source_path: Optional[str]
    created_at: str


class ReviewCompletedPayload(BaseModel):
    event: ReviewCompletedEvent


class BestNodeSelectionEvent(BaseModel):
    stage: str
    node_id: str
    reasoning: str


class BestNodeSelectionPayload(BaseModel):
    event: BestNodeSelectionEvent


class StageSkipWindowEventModel(BaseModel):
    stage: str
    state: Literal["opened", "closed"]
    timestamp: str
    reason: Optional[str] = None


class StageSkipWindowPayload(BaseModel):
    event: StageSkipWindowEventModel


class TreeVizStoredEvent(BaseModel):
    stage_id: str
    version: int
    viz: Dict[str, Any]


class TreeVizStoredPayload(BaseModel):
    event: TreeVizStoredEvent


class RunLogEvent(BaseModel):
    message: str
    level: str = "info"


class RunLogPayload(BaseModel):
    event: RunLogEvent


class CodexEventPayload(BaseModel):
    event: dict[str, Any]


class RunningCodeEventPayload(BaseModel):
    execution_id: str
    stage_name: str
    code: str
    started_at: str
    run_type: RunType


class RunningCodePayload(BaseModel):
    event: RunningCodeEventPayload


class RunCompletedEventPayload(BaseModel):
    execution_id: str
    stage_name: str
    status: Literal["success", "failed"]
    exec_time: float
    completed_at: str
    run_type: RunType


class RunCompletedPayload(BaseModel):
    event: RunCompletedEventPayload


class TokenUsageEvent(BaseModel):
    provider: str
    model: str
    input_tokens: int
    cached_input_tokens: int
    output_tokens: int


class TokenUsagePayload(BaseModel):
    event: TokenUsageEvent


class FigureReviewEvent(BaseModel):
    figure_name: str
    img_description: str
    img_review: str
    caption_review: str
    figrefs_review: str
    source_path: Optional[str] = None


class FigureReviewsEvent(BaseModel):
    """Event containing multiple figure reviews."""

    reviews: List[FigureReviewEvent]


class FigureReviewsPayload(BaseModel):
    event: FigureReviewsEvent


# ============================================================================
# File Upload Schemas
# ============================================================================


class PresignedUploadUrlRequest(BaseModel):
    artifact_type: str
    filename: str
    content_type: str
    file_size: int
    metadata: Optional[Dict[str, str]] = None


class PresignedUploadUrlResponse(BaseModel):
    upload_url: str
    s3_key: str
    expires_in: int


class MultipartUploadInitRequest(BaseModel):
    """Request to initiate a multipart upload."""

    artifact_type: str
    filename: str
    content_type: str
    file_size: int
    part_size: int = Field(description="Size of each part in bytes")
    num_parts: int = Field(description="Total number of parts")
    metadata: Optional[Dict[str, str]] = None


class MultipartUploadPartUrl(BaseModel):
    """Presigned URL for uploading a single part."""

    part_number: int
    upload_url: str


class MultipartUploadInitResponse(BaseModel):
    """Response with multipart upload initiation details."""

    upload_id: str
    s3_key: str
    part_urls: List[MultipartUploadPartUrl]
    expires_in: int


class MultipartUploadPart(BaseModel):
    """Completed part information for multipart upload completion."""

    part_number: int = Field(alias="PartNumber")
    etag: str = Field(alias="ETag")

    class Config:
        populate_by_name = True


class MultipartUploadCompleteRequest(BaseModel):
    """Request to complete a multipart upload."""

    upload_id: str
    s3_key: str
    parts: List[MultipartUploadPart]
    artifact_type: str
    filename: str
    file_size: int
    content_type: str


class MultipartUploadCompleteResponse(BaseModel):
    """Response after completing a multipart upload."""

    s3_key: str
    success: bool


class MultipartUploadAbortRequest(BaseModel):
    """Request to abort a multipart upload."""

    upload_id: str
    s3_key: str


class ParentRunFileInfo(BaseModel):
    s3_key: str
    filename: str
    size: int
    download_url: str


class ParentRunFilesRequest(BaseModel):
    parent_run_id: str


class ParentRunFilesResponse(BaseModel):
    files: List[ParentRunFileInfo]
    expires_in: int


class DatasetFileInfo(BaseModel):
    s3_key: str
    relative_path: str
    size: int
    download_url: str


class ListDatasetsRequest(BaseModel):
    datasets_folder: str


class ListDatasetsResponse(BaseModel):
    files: List[DatasetFileInfo]
    expires_in: int


class DatasetUploadUrlRequest(BaseModel):
    datasets_folder: str
    relative_path: str
    content_type: str
    file_size: int


class DatasetUploadUrlResponse(BaseModel):
    upload_url: str
    s3_key: str
    expires_in: int
