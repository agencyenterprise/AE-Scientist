from dataclasses import dataclass
from typing import Any, Dict, Literal, Optional, Tuple

EventKind = Literal[
    "run_stage_progress",
    "run_log",
    "substage_completed",
    "substage_summary",
    "paper_generation_progress",
    "best_node_selection",
    "tree_viz_stored",
]
PersistenceRecord = Tuple[EventKind, Dict[str, Any]]


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
    eta_s: Optional[int] = None
    latest_iteration_time_s: Optional[int] = None

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
        }
        if self.eta_s is not None:
            data["eta_s"] = self.eta_s
        if self.latest_iteration_time_s is not None:
            data["latest_iteration_time_s"] = self.latest_iteration_time_s
        return data

    def persistence_record(self) -> PersistenceRecord:
        return (
            "run_stage_progress",
            {
                "stage": self.stage,
                "iteration": self.iteration,
                "max_iterations": self.max_iterations,
                "progress": float(self.progress),
                "total_nodes": self.total_nodes,
                "buggy_nodes": self.buggy_nodes,
                "good_nodes": self.good_nodes,
                "best_metric": self.best_metric,
                "eta_s": self.eta_s,
                "latest_iteration_time_s": self.latest_iteration_time_s,
            },
        )


@dataclass(frozen=True)
class RunLogEvent(BaseEvent):
    message: str
    level: str = "info"

    def type(self) -> str:
        return "ai.run.log"

    def to_dict(self) -> Dict[str, Any]:
        return {"message": self.message, "level": self.level}

    def persistence_record(self) -> PersistenceRecord:
        return ("run_log", {"message": self.message, "level": self.level})


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
        return (
            "substage_completed",
            {
                "stage": self.stage,
                "main_stage_number": self.main_stage_number,
                "reason": self.reason,
                "summary": self.summary,
            },
        )


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
        return (
            "substage_summary",
            {
                "stage": self.stage,
                "summary": self.summary,
            },
        )


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
        return (
            "best_node_selection",
            {
                "stage": self.stage,
                "node_id": self.node_id,
                "reasoning": self.reasoning,
            },
        )


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
        return (
            "paper_generation_progress",
            {
                "run_id": self.run_id,
                "step": self.step,
                "substep": self.substep,
                "progress": self.progress,
                "step_progress": self.step_progress,
                "details": self.details,
            },
        )
