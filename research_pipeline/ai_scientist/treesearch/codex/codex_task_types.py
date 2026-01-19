from typing import Any, NamedTuple

from ..config import TaskDescription


class EvaluationMetricSpec(NamedTuple):
    name: str
    maximize: bool
    description: str

    def to_json_dict(self) -> dict[str, object]:
        return {
            "name": self.name,
            "maximize": self.maximize,
            "description": self.description,
        }

    @staticmethod
    def from_json_dict(*, obj: object) -> "EvaluationMetricSpec":
        if not isinstance(obj, dict):
            raise TypeError("evaluation_metric_spec must be an object/dict")
        name = obj.get("name")
        maximize = obj.get("maximize")
        description = obj.get("description")
        if not isinstance(name, str) or not name.strip():
            raise ValueError("evaluation_metric_spec.name must be a non-empty string")
        if not isinstance(maximize, bool):
            raise ValueError("evaluation_metric_spec.maximize must be a boolean")
        if not isinstance(description, str) or not description.strip():
            raise ValueError("evaluation_metric_spec.description must be a non-empty string")
        return EvaluationMetricSpec(name=name, maximize=maximize, description=description)


class StageIdea(NamedTuple):
    name: str
    description: str
    tried_names: list[str]

    def to_json_dict(self) -> dict[str, object]:
        return {
            "name": self.name,
            "description": self.description,
            "tried_names": list(self.tried_names),
        }


class SeedNodeSummary(NamedTuple):
    id: str
    exp_results_dir: str | None
    metric: dict[str, Any] | None
    plots: list[str]
    plot_paths: list[str]
    is_buggy: bool
    is_buggy_plots: bool

    def to_json_dict(self) -> dict[str, object]:
        return {
            "id": self.id,
            "exp_results_dir": self.exp_results_dir,
            "metric": self.metric,
            "plots": list(self.plots),
            "plot_paths": list(self.plot_paths),
            "is_buggy": self.is_buggy,
            "is_buggy_plots": self.is_buggy_plots,
        }


class SeedAggregationPayload(NamedTuple):
    parent_node_id: str
    stage_name: str
    seed_nodes: list[SeedNodeSummary]

    def to_json_dict(self) -> dict[str, object]:
        return {
            "parent_node_id": self.parent_node_id,
            "stage_name": self.stage_name,
            "seed_nodes": [n.to_json_dict() for n in self.seed_nodes],
        }


class ParentNodeSummary(NamedTuple):
    id: str
    step: int | None
    parent_id: str | None
    plan: str
    overall_plan: str
    analysis: str | None
    metric: dict[str, Any] | None
    is_buggy: bool | None
    is_buggy_plots: bool | None
    exc_type: str | None
    exec_time: float | None
    exec_time_feedback: str
    exp_results_dir: str | None
    plot_analyses: list[dict[str, Any]]
    vlm_feedback_summary: str
    datasets_successfully_tested: list[str]
    hyperparam_name: str | None
    ablation_name: str | None
    is_seed_node: bool
    is_seed_agg_node: bool

    def to_json_dict(self) -> dict[str, object]:
        return {
            "id": self.id,
            "step": self.step,
            "parent_id": self.parent_id,
            "plan": self.plan,
            "overall_plan": self.overall_plan,
            "analysis": self.analysis,
            "metric": self.metric,
            "is_buggy": self.is_buggy,
            "is_buggy_plots": self.is_buggy_plots,
            "exc_type": self.exc_type,
            "exec_time": self.exec_time,
            "exec_time_feedback": self.exec_time_feedback,
            "exp_results_dir": self.exp_results_dir,
            "plot_analyses": list(self.plot_analyses),
            "vlm_feedback_summary": self.vlm_feedback_summary,
            "datasets_successfully_tested": list(self.datasets_successfully_tested),
            "hyperparam_name": self.hyperparam_name,
            "ablation_name": self.ablation_name,
            "is_seed_node": self.is_seed_node,
            "is_seed_agg_node": self.is_seed_agg_node,
        }


class CodexTaskContext(NamedTuple):
    execution_id: str
    stage_identifier: str
    seed_aggregation: SeedAggregationPayload | None
    stage2_hyperparam_idea: StageIdea | None
    stage4_ablation_idea: StageIdea | None
    gpu_id: int | None
    agent_file_name: str
    timeout_seconds: int
    parent_node: ParentNodeSummary | None
    user_feedback_payload: str
    task_desc: TaskDescription
    stage_goals: str
    evaluation_metric_spec: EvaluationMetricSpec
    memory_summary: str
