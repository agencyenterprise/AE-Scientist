from pydantic import BaseModel, Field

from ai_scientist.llm import get_structured_response_from_llm

from .codex.codex_task_types import EvaluationMetricSpec
from .prompts.render import render_text


class EvaluationMetricSpecResponse(BaseModel):
    name: str = Field(
        ...,
        min_length=1,
        description="The metric name, e.g. 'accuracy' or 'RMSE'.",
    )
    maximize: bool = Field(
        ...,
        description="True if larger is better; False if smaller is better.",
    )
    description: str = Field(
        ...,
        min_length=1,
        description="Short description of how the metric is computed.",
    )


def define_evaluation_metric_spec_via_llm(
    *,
    title: str,
    task_desc: str,
    model: str,
    temperature: float,
) -> EvaluationMetricSpec:
    prompt = render_text(
        template_name="agent_manager/evaluation_metric_spec_prompt.txt.j2",
        context={"title": title, "task_desc": task_desc},
    )

    parsed, _ = get_structured_response_from_llm(
        prompt=prompt,
        model=model,
        system_message=None,
        temperature=temperature,
        schema_class=EvaluationMetricSpecResponse,
    )
    response = EvaluationMetricSpecResponse.model_validate(parsed)
    return EvaluationMetricSpec.from_json_dict(obj=response.model_dump())
