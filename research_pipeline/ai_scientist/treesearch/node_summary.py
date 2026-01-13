import logging
from typing import Any

from pydantic import BaseModel, Field

from ai_scientist.llm import structured_query_with_schema

from .config import TaskDescription
from .journal import Node
from .utils.response import wrap_code

logger = logging.getLogger("ai-scientist")


class ExperimentSummary(BaseModel):
    findings: str = Field(
        ...,
        description="Key experimental findings/outcomes.",
        min_length=1,
    )
    significance: str = Field(
        ...,
        description="Why the findings matter and the insight they provide.",
        min_length=1,
    )
    next_steps: str = Field(
        ...,
        description="Follow-up experiments or improvements.",
        min_length=1,
    )


def generate_node_summary(
    *,
    model: str,
    temperature: float,
    stage_name: str,
    node: Node,
    task_desc: TaskDescription | None = None,
) -> dict[str, Any]:
    summary_prompt: dict[str, Any] = {
        "Introduction": (
            "You are an AI researcher analyzing experimental results. "
            "Please summarize the findings from this experiment iteration."
        ),
        "Stage": stage_name,
        "Hyperparameter": node.hyperparam_name,
        "Parent comparison": {
            "parent_id": node.parent.id if node.parent is not None else None,
            "parent_metric": (
                str(node.parent.metric) if node.parent and node.parent.metric else None
            ),
        },
        "Implementation": wrap_code(node.code),
        "Plan": node.plan,
        "Execution output": wrap_code(node.term_out, lang=""),
        "Analysis": node.analysis,
        "Metric": str(node.metric) if node.metric else "Failed",
        "Plot Analyses": node.plot_analyses,
        "VLM Feedback": node.vlm_feedback_summary,
    }
    if task_desc is not None:
        summary_prompt["Research idea"] = task_desc.model_dump(by_alias=True)
    logger.debug(
        "llm.node_summary.request node=%s model=%s temperature=%s schema=%s payload=%s",
        node.id[:8],
        model,
        temperature,
        ExperimentSummary.__name__,
        summary_prompt,
    )
    response = structured_query_with_schema(
        system_message=summary_prompt,
        user_message=None,
        model=model,
        temperature=temperature,
        schema_class=ExperimentSummary,
    )
    payload = response.model_dump(by_alias=True)
    logger.debug(
        "llm.node_summary.response node=%s model=%s schema=%s payload=%s",
        node.id[:8],
        model,
        ExperimentSummary.__name__,
        payload,
    )
    return payload
