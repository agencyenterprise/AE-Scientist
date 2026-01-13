from dataclasses import dataclass
from dataclasses import fields as dataclass_fields
from pathlib import Path

from ..journal import Node
from ..prompts.render import render_lines
from ..stage_identifiers import StageIdentifier


@dataclass(frozen=True)
class NodeResultContractContext:
    stage_identifier: StageIdentifier
    is_seed_aggregation: bool
    seed_eval: bool
    seed_value: int
    working_png_count: int
    expected_hyperparam_name: str | None
    expected_ablation_name: str | None


def count_working_pngs(*, working_dir: Path) -> int:
    if not working_dir.exists():
        return 0
    return len(list(working_dir.glob("*.png")))


def is_non_empty_string(*, value: object) -> bool:
    return isinstance(value, str) and bool(value.strip())


def is_list_of_strings(*, value: object) -> bool:
    if not isinstance(value, list):
        return False
    return all(isinstance(x, str) for x in value)


def validate_plot_analyses(*, value: object) -> list[str]:
    if not isinstance(value, list):
        return ["plot_analyses must be a list"]
    errors: list[str] = []
    for idx, entry in enumerate(value):
        if not isinstance(entry, dict):
            errors.append(f"plot_analyses[{idx}] must be an object/dict")
            continue
        analysis = entry.get("analysis")
        if not is_non_empty_string(value=analysis):
            errors.append(f"plot_analyses[{idx}].analysis must be a non-empty string")
    return errors


def codex_node_result_contract_prompt_lines_common() -> list[str]:
    return render_lines(template_name="contracts/common.txt.j2", context={})


def _validate_metric(*, value: object) -> list[str]:
    if not isinstance(value, dict):
        return ["metric must be an object/dict"]
    errors: list[str] = []
    name = value.get("name")
    maximize = value.get("maximize")
    description = value.get("description")
    metric_value = value.get("value")

    if not is_non_empty_string(value=name):
        errors.append("metric.name must be a non-empty string")
    if not isinstance(maximize, bool):
        errors.append("metric.maximize must be a boolean")
    if not is_non_empty_string(value=description):
        errors.append("metric.description must be a non-empty string")
    if metric_value is not None and not isinstance(metric_value, (int, float)):
        errors.append("metric.value must be a number (int/float) or null")
    return errors


def _unexpected_node_result_keys(*, node_result: dict[str, object]) -> list[str]:
    allowed = {f.name for f in dataclass_fields(Node)}
    # Serialized form includes relationship IDs rather than `parent`/`children` objects.
    allowed.add("parent_id")
    allowed.add("children")
    # Metric is serialized as a nested object/dict in node_result.json.
    allowed.add("metric")

    extras = sorted({str(k) for k in node_result.keys()} - allowed)
    if not extras:
        return []
    return [f"Unexpected key(s) in node_result.json: {extras}. Remove them."]


def validate_common_node_result_contract(
    *, node_result: dict[str, object], ctx: NodeResultContractContext
) -> list[str]:
    errors: list[str] = []

    errors.extend(_unexpected_node_result_keys(node_result=node_result))

    # Harness-owned fields: Codex must not provide these in node_result.json.
    if "metric" in node_result:
        errors.append("Do NOT include metric in node_result.json")
    if not isinstance(node_result.get("is_buggy_plots"), bool):
        errors.append("is_buggy_plots must be a boolean (true/false)")
    if not isinstance(node_result.get("is_seed_agg_node", False), bool):
        errors.append("is_seed_agg_node must be a boolean")
    is_seed_agg_node = node_result.get("is_seed_agg_node")
    if ctx.is_seed_aggregation:
        if is_seed_agg_node is not True:
            errors.append("seed aggregation run requires is_seed_agg_node=true")
    else:
        if is_seed_agg_node is True:
            errors.append("non-aggregation run requires is_seed_agg_node=false")

    datasets_val = node_result.get("datasets_successfully_tested")
    if datasets_val is None:
        errors.append("datasets_successfully_tested is required (use [] if none)")
    elif not is_list_of_strings(value=datasets_val):
        errors.append("datasets_successfully_tested must be a list of strings")

    if ctx.seed_eval:
        if node_result.get("is_seed_node") is not True:
            errors.append("seed_eval=true requires is_seed_node=true")
        plan_text = node_result.get("plan")
        if isinstance(plan_text, str):
            seed_text = str(ctx.seed_value)
            if ("seed" not in plan_text.lower()) or (seed_text not in plan_text):
                errors.append(
                    f"seed_eval=true requires the plan to mention the seed value (expected {ctx.seed_value})"
                )
        else:
            errors.append("plan must be a string (and must mention the seed when seed_eval=true)")

    return errors
