from ..prompts.render import render_lines, render_text
from .node_result_contract import NodeResultContractContext, is_non_empty_string


def codex_seed_aggregation_instructions_lines() -> list[str]:
    rendered = render_text(
        template_name="seed_aggregation/seed_aggregation_instructions.md.j2", context={}
    )
    return [line for line in rendered.splitlines() if line.strip()]


def codex_node_result_contract_prompt_lines() -> list[str]:
    return render_lines(template_name="contracts/seed_aggregation.txt.j2", context={})


def validate_node_result_contract(
    *, node_result: dict[str, object], ctx: NodeResultContractContext
) -> list[str]:
    errors: list[str] = []
    if node_result.get("is_seed_node") is not True:
        errors.append("seed aggregation requires is_seed_node=true")
    if node_result.get("is_seed_agg_node") is not True:
        errors.append("seed aggregation requires is_seed_agg_node=true")

    analysis_val = node_result.get("analysis")
    if not is_non_empty_string(value=analysis_val):
        errors.append("seed aggregation requires analysis to be a non-empty string")

    is_buggy_plots = node_result.get("is_buggy_plots")
    if is_buggy_plots is False:
        if ctx.working_png_count <= 0:
            errors.append(
                "seed aggregation requires at least one .png in ./working when is_buggy_plots=false"
            )
    return errors
