from dataclasses import dataclass
from typing import Any, Dict, Optional


class BaseEvent:
    """Structured event base class.

    Subclasses must implement type() and to_dict().
    """

    def type(self) -> str:  # pragma: no cover - interface method
        raise NotImplementedError

    def to_dict(self) -> Dict[str, Any]:  # pragma: no cover - interface method
        raise NotImplementedError


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


@dataclass(frozen=True)
class RunLogEvent(BaseEvent):
    message: str
    level: str = "info"

    def type(self) -> str:
        return "ai.run.log"

    def to_dict(self) -> Dict[str, Any]:
        return {"message": self.message, "level": self.level}


@dataclass(frozen=True)
class ExperimentNodeCompletedEvent(BaseEvent):
    stage: str
    node_id: Optional[str]
    summary: Dict[str, Any]

    def type(self) -> str:
        return "ai.experiment.node_completed"

    def to_dict(self) -> Dict[str, Any]:
        return {"stage": self.stage, "node_id": self.node_id, "summary": self.summary}
