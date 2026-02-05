import json
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any, Dict, Literal, Optional, Tuple

from pydantic import BaseModel as PydanticBaseModel

from ai_scientist.api_types import BestNodeSelectionEvent as BestNodeSelectionEventPayload
from ai_scientist.api_types import (
    PaperGenerationProgressEvent as PaperGenerationProgressEventPayload,
)
from ai_scientist.api_types import (
    RunCompletedEventPayload,
)
from ai_scientist.api_types import RunLogEvent as RunLogEventPayload
from ai_scientist.api_types import (
    RunningCodeEventPayload,
)
from ai_scientist.api_types import RunType as ApiRunType
from ai_scientist.api_types import StageProgressEvent as StageProgressEventPayload
from ai_scientist.api_types import (
    StageSkipWindowEventModel,
)
from ai_scientist.api_types import State as StageSkipState
from ai_scientist.api_types import Status6 as RunCompletedStatus
from ai_scientist.api_types import SubstageCompletedEvent as SubstageCompletedEventPayload
from ai_scientist.api_types import SubstageSummaryEvent as SubstageSummaryEventPayload


def _sanitize_summary(data: Dict[str, Any]) -> Dict[str, Any]:
    """Ensure summary dict can be serialized to JSON."""
    try:
        json.dumps(data, default=str)
        return data
    except TypeError:
        sanitized_raw = json.dumps(data, default=str)
        sanitized: Dict[str, Any] = json.loads(sanitized_raw)
        return sanitized


class RunType(str, Enum):
    """Execution stream identifier for code execution telemetry."""

    CODEX_EXECUTION = "codex_execution"
    RUNFILE_EXECUTION = "runfile_execution"


EventKind = Literal[
    "run_stage_progress",
    "run_log",
    "substage_completed",
    "substage_summary",
    "paper_generation_progress",
    "best_node_selection",
    "tree_viz_stored",
    "running_code",
    "run_completed",
    "stage_skip_window",
    "artifact_uploaded",
    "review_completed",
    "codex_event",
    "token_usage",
    "figure_reviews",
]
PersistenceRecord = Tuple[EventKind, PydanticBaseModel]


class CodexEventInnerPayload(PydanticBaseModel):
    """Inner payload for CodexEvent (the dict inside CodexEventPayload.event)."""

    stage: str
    node: int
    event_type: str
    event_content: str


class BaseEvent:
    """Structured event base class.

    Subclasses must implement type() and to_dict().
    """

    def type(self) -> str:  # pragma: no cover - interface method
        raise NotImplementedError

    def to_dict(self) -> Dict[str, Any]:  # pragma: no cover - interface method
        raise NotImplementedError

    def persistence_record(self) -> Optional[PersistenceRecord]:
        """Optional structured payload for telemetry persistence."""
        return None


@dataclass(frozen=True)
class RunStageProgressEvent(BaseEvent):
    stage: str
    iteration: int
    max_iterations: int
    progress: float
    total_nodes: int
    buggy_nodes: int
    good_nodes: int
    best_metric: Optional[str] = None
    is_seed_node: bool = False  # True when this progress is from seed evaluation

    def type(self) -> str:
        return "ai.run.stage_progress"

    def to_dict(self) -> Dict[str, Any]:
        data: Dict[str, Any] = {
            "stage": self.stage,
            "iteration": self.iteration,
            "max_iterations": self.max_iterations,
            "progress": self.progress,
            "total_nodes": self.total_nodes,
            "buggy_nodes": self.buggy_nodes,
            "good_nodes": self.good_nodes,
            "best_metric": self.best_metric,
            "is_seed_node": self.is_seed_node,
        }
        return data

    def persistence_record(self) -> PersistenceRecord:
        event = StageProgressEventPayload(
            stage=self.stage,
            iteration=self.iteration,
            max_iterations=self.max_iterations,
            progress=float(self.progress),
            total_nodes=self.total_nodes,
            buggy_nodes=self.buggy_nodes,
            good_nodes=self.good_nodes,
            best_metric=self.best_metric,
            is_seed_node=self.is_seed_node,
        )
        return ("run_stage_progress", event)


@dataclass(frozen=True)
class RunLogEvent(BaseEvent):
    message: str
    level: str = "info"

    def type(self) -> str:
        return "ai.run.log"

    def to_dict(self) -> Dict[str, Any]:
        return {"message": self.message, "level": self.level}

    def persistence_record(self) -> PersistenceRecord:
        event = RunLogEventPayload(message=self.message, level=self.level)
        return ("run_log", event)


@dataclass(frozen=True)
class CodexEvent(BaseEvent):
    """Event emitted for Codex CLI execution information."""

    stage: str
    node: int
    event_type: str
    event_content: str

    def type(self) -> str:
        return "ai.codex.event"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "stage": self.stage,
            "node": self.node,
            "event_type": self.event_type,
            "event_content": self.event_content,
        }

    def persistence_record(self) -> PersistenceRecord:
        # Return the inner payload model; publish() wraps it in {"event": ...}
        event = CodexEventInnerPayload(
            stage=self.stage,
            node=self.node,
            event_type=self.event_type,
            event_content=self.event_content,
        )
        return ("codex_event", event)


@dataclass(frozen=True)
class SubstageCompletedEvent(BaseEvent):
    """Event emitted when a sub-stage completes."""

    stage: str  # Full stage identifier, e.g. "2_baseline_tuning"
    main_stage_number: int
    reason: str
    summary: Dict[str, Any]

    def type(self) -> str:
        return "ai.run.substage_completed"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "stage": self.stage,
            "main_stage_number": self.main_stage_number,
            "reason": self.reason,
            "summary": self.summary,
        }

    def persistence_record(self) -> PersistenceRecord:
        # Persist a compact payload; detailed information lives in the summary.
        # Sanitize summary to ensure JSON serializability.
        event = SubstageCompletedEventPayload(
            stage=self.stage,
            main_stage_number=self.main_stage_number,
            reason=self.reason,
            summary=_sanitize_summary(self.summary),
        )
        return ("substage_completed", event)


@dataclass(frozen=True)
class SubstageSummaryEvent(BaseEvent):
    """Event emitted with the LLM phase summary for a sub-stage."""

    stage: str
    summary: Dict[str, Any]

    def type(self) -> str:
        return "ai.run.substage_summary"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "stage": self.stage,
            "summary": self.summary,
        }

    def persistence_record(self) -> PersistenceRecord:
        event = SubstageSummaryEventPayload(
            stage=self.stage,
            summary=self.summary,
        )
        return ("substage_summary", event)


@dataclass(frozen=True)
class BestNodeSelectedEvent(BaseEvent):
    """Event emitted when an LLM picks the current best node."""

    run_id: str
    stage: str
    node_id: str
    reasoning: str

    def type(self) -> str:
        return "ai.run.best_node_selected"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "run_id": self.run_id,
            "stage": self.stage,
            "node_id": self.node_id,
            "reasoning": self.reasoning,
        }

    def persistence_record(self) -> PersistenceRecord:
        event = BestNodeSelectionEventPayload(
            stage=self.stage,
            node_id=self.node_id,
            reasoning=self.reasoning,
        )
        return ("best_node_selection", event)


@dataclass(frozen=True)
class GpuShortageEvent(BaseEvent):
    required_gpus: int
    available_gpus: int
    message: str

    def type(self) -> str:
        return "ai.run.gpu_shortage"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "required_gpus": self.required_gpus,
            "available_gpus": self.available_gpus,
            "message": self.message,
        }


@dataclass(frozen=True)
class PaperGenerationProgressEvent(BaseEvent):
    """Event emitted during paper generation (Stage 5) progress."""

    run_id: str
    step: str  # "plot_aggregation" | "citation_gathering" | "paper_writeup" | "paper_review"
    substep: Optional[str] = None
    progress: float = 0.0
    step_progress: float = 0.0
    details: Optional[Dict[str, Any]] = None

    def type(self) -> str:
        return "ai.run.paper_generation_progress"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "run_id": self.run_id,
            "step": self.step,
            "substep": self.substep,
            "progress": self.progress,
            "step_progress": self.step_progress,
            "details": self.details,
        }

    def persistence_record(self) -> PersistenceRecord:
        # Note: run_id is not included - it comes from the URL path on the server
        event = PaperGenerationProgressEventPayload(
            step=self.step,
            substep=self.substep,
            progress=self.progress,
            step_progress=self.step_progress,
            details=self.details,
        )
        return ("paper_generation_progress", event)


@dataclass(frozen=True)
class RunningCodeEvent(BaseEvent):
    execution_id: str
    stage_name: str
    code: str
    started_at: datetime
    run_type: RunType

    def type(self) -> str:
        return "ai.run.running_code"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "execution_id": self.execution_id,
            "stage_name": self.stage_name,
            "run_type": self.run_type.value,
            "code": self.code,
            "started_at": self.started_at.isoformat(),
        }

    def persistence_record(self) -> PersistenceRecord:
        event = RunningCodeEventPayload(
            execution_id=self.execution_id,
            stage_name=self.stage_name,
            run_type=ApiRunType(self.run_type.value),
            code=self.code,
            started_at=self.started_at.isoformat(),
        )
        return ("running_code", event)


@dataclass(frozen=True)
class RunCompletedEvent(BaseEvent):
    execution_id: str
    stage_name: str
    status: Literal["success", "failed"]
    exec_time: float
    completed_at: datetime
    run_type: RunType

    def type(self) -> str:
        return "ai.run.run_completed"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "execution_id": self.execution_id,
            "stage_name": self.stage_name,
            "run_type": self.run_type.value,
            "status": self.status,
            "exec_time": self.exec_time,
            "completed_at": self.completed_at.isoformat(),
        }

    def persistence_record(self) -> PersistenceRecord:
        event = RunCompletedEventPayload(
            execution_id=self.execution_id,
            stage_name=self.stage_name,
            run_type=ApiRunType(self.run_type.value),
            status=RunCompletedStatus(self.status),
            exec_time=self.exec_time,
            completed_at=self.completed_at.isoformat(),
        )
        return ("run_completed", event)


@dataclass(frozen=True)
class StageSkipWindowEvent(BaseEvent):
    stage: str
    state: Literal["opened", "closed"]
    timestamp: datetime
    reason: Optional[str] = None

    def type(self) -> str:
        return "ai.run.stage_skip_window"

    def to_dict(self) -> Dict[str, Any]:
        payload: Dict[str, Any] = {
            "stage": self.stage,
            "state": self.state,
            "timestamp": self.timestamp.isoformat(),
        }
        if self.reason:
            payload["reason"] = self.reason
        return payload

    def persistence_record(self) -> PersistenceRecord:
        event = StageSkipWindowEventModel(
            stage=self.stage,
            state=StageSkipState(self.state),
            timestamp=self.timestamp.isoformat(),
            reason=self.reason,
        )
        return ("stage_skip_window", event)
