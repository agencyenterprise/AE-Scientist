import logging
import traceback
from typing import Any

from pydantic import BaseModel, Field

from ai_scientist.llm import structured_query_with_schema

from .config import TaskDescription
from .journal import Node
from .utils.response import wrap_code

logger = logging.getLogger("ai-scientist")
_node_summary_call_counts: dict[tuple[str, str], int] = {}
_node_summary_seq: int = 0


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
    purpose: str,
    model: str,
    temperature: float,
    stage_name: str,
    node: Node,
    task_desc: TaskDescription | None,
) -> dict[str, Any]:
    global _node_summary_seq  # noqa: PLW0603
    _node_summary_seq += 1
    seq = _node_summary_seq
    node_key = (stage_name, str(node.id))
    prev_count = _node_summary_call_counts.get(node_key, 0)
    call_count = prev_count + 1
    _node_summary_call_counts[node_key] = call_count
    logger.debug(
        "node_summary.invoke seq=%s purpose=%s node=%s stage=%s call_count_for_node_stage=%s",
        seq,
        purpose,
        str(node.id)[:8],
        stage_name,
        call_count,
    )
    if call_count > 1:
        logger.debug(
            "node_summary.duplicate_call seq=%s purpose=%s node=%s stage=%s stack=\n%s",
            seq,
            purpose,
            str(node.id)[:8],
            stage_name,
            "".join(traceback.format_stack(limit=25)),
        )

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
        "llm.node_summary.request seq=%s purpose=%s node=%s stage=%s model=%s temperature=%s schema=%s payload=%s",
        seq,
        purpose,
        node.id[:8],
        stage_name,
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
        "llm.node_summary.response seq=%s purpose=%s node=%s stage=%s model=%s schema=%s payload=%s",
        seq,
        purpose,
        node.id[:8],
        stage_name,
        model,
        ExperimentSummary.__name__,
        payload,
    )
    return payload
