from typing import NamedTuple

from ai_scientist.treesearch.config import TaskDescription
from ai_scientist.treesearch.prompts.render import render_text


class CodexTaskMarkdownRenderContext(NamedTuple):
    execution_id: str
    stage_identifier_name: str
    stage_name: str
    timeout_seconds: int

    task_desc: TaskDescription
    stage_goals: str
    memory_summary: str

    venv_dir: str
    environment_context: dict[str, object]
    num_syn_datasets: int
    evaluation_metric_json: str

    assigned_hyperparam_name: str
    assigned_hyperparam_description: str
    assigned_hyperparam_tried_names: str

    assigned_ablation_name: str
    assigned_ablation_description: str
    assigned_ablation_tried_names: str

    base_code: str
    parent_term_out: str
    parent_exc_type: str
    parent_analysis: str
    parent_vlm_feedback_summary: str
    exec_time_feedback: str
    user_feedback_payload: str
    is_improvement_scenario: bool
    show_plotting_guidelines: bool
    experiment_code_hint: str

    seed_agg_block: str
    contract_block: str

    output_json_name: str
    agent_file_name: str

    def to_jinja_context(self) -> dict[str, object]:
        return {
            "execution_id": self.execution_id,
            "stage_identifier_name": self.stage_identifier_name,
            "stage_name": self.stage_name,
            "timeout_seconds": self.timeout_seconds,
            "task_desc": self.task_desc,
            "stage_goals": self.stage_goals,
            "memory_summary": self.memory_summary,
            "venv_dir": self.venv_dir,
            "environment_context": dict(self.environment_context),
            "num_syn_datasets": self.num_syn_datasets,
            "evaluation_metric_json": self.evaluation_metric_json,
            "assigned_hyperparam_name": self.assigned_hyperparam_name,
            "assigned_hyperparam_description": self.assigned_hyperparam_description,
            "assigned_hyperparam_tried_names": self.assigned_hyperparam_tried_names,
            "assigned_ablation_name": self.assigned_ablation_name,
            "assigned_ablation_description": self.assigned_ablation_description,
            "assigned_ablation_tried_names": self.assigned_ablation_tried_names,
            "base_code": self.base_code,
            "parent_term_out": self.parent_term_out,
            "parent_exc_type": self.parent_exc_type,
            "parent_analysis": self.parent_analysis,
            "parent_vlm_feedback_summary": self.parent_vlm_feedback_summary,
            "exec_time_feedback": self.exec_time_feedback,
            "user_feedback_payload": self.user_feedback_payload,
            "is_improvement_scenario": bool(self.is_improvement_scenario),
            "show_plotting_guidelines": self.show_plotting_guidelines,
            "experiment_code_hint": self.experiment_code_hint,
            "seed_agg_block": self.seed_agg_block,
            "contract_block": self.contract_block,
            "output_json_name": self.output_json_name,
            "agent_file_name": self.agent_file_name,
        }


def render_codex_task_markdown(*, ctx: CodexTaskMarkdownRenderContext) -> str:
    rendered = render_text(
        template_name="codex_task/codex_task.md.j2", context=ctx.to_jinja_context()
    )
    return rendered + "\n"
