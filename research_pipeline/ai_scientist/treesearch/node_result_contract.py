from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .stage_identifiers import StageIdentifier


@dataclass(frozen=True)
class NodeResultContractContext:
    stage_identifier: StageIdentifier
    is_seed_aggregation: bool
    seed_eval: bool
    seed_value: int
    working_png_count: int


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
    return [
        "## Node result contract (STRICT; enforced by the harness)",
        "- You MUST include the following keys in `node_result.json` with the exact types:",
        "  - `is_buggy_plots`: boolean (true/false; never null)",
        "  - `plot_analyses`: list of objects (can be empty)",
        "  - `vlm_feedback_summary`: list of strings (can be empty)",
        "  - `vlm_feedback`: object/dict (can be empty `{}`)",
        "  - `datasets_successfully_tested`: list of strings (can be empty)",
        "  - `is_seed_agg_node`: boolean (false for normal runs; true only for seed aggregation runs)",
        "- If `seed_eval` is true, you MUST include `is_seed_node=true`.",
    ]


def validate_common_node_result_contract(
    *, node_result: dict[str, object], ctx: NodeResultContractContext
) -> list[str]:
    errors: list[str] = []

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

    plot_analyses_val = node_result.get("plot_analyses")
    if plot_analyses_val is None:
        errors.append("plot_analyses is required (use [] if none)")
    else:
        errors.extend(validate_plot_analyses(value=plot_analyses_val))

    vlm_feedback_summary_val = node_result.get("vlm_feedback_summary")
    if vlm_feedback_summary_val is None:
        errors.append("vlm_feedback_summary is required (use [] if none)")
    elif not is_list_of_strings(value=vlm_feedback_summary_val):
        errors.append("vlm_feedback_summary must be a list of strings")

    vlm_feedback_val = node_result.get("vlm_feedback")
    if vlm_feedback_val is None:
        errors.append("vlm_feedback is required (use {} if none)")
    elif not isinstance(vlm_feedback_val, dict):
        errors.append("vlm_feedback must be an object/dict")

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
