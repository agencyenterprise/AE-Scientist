from __future__ import annotations

from .node_result_contract import NodeResultContractContext, is_non_empty_string


def codex_seed_aggregation_instructions_lines() -> list[str]:
    return [
        "## Seed aggregation task (multi-seed roll-up)",
        "- `codex_input.json` includes a `seed_aggregation` object describing seed runs.",
        "- Your job is to aggregate results across seeds and produce a rolled-up report + plots.",
        "- Load each seed run's `experiment_data.npy` from the provided `exp_results_dir` paths when available.",
        "- Compute mean ± std/sem across seeds where applicable and produce summary plots (error bars, aggregated curves).",
        "- Write plots as `.png` files into `./working/`.",
        "- Set `is_seed_node=true` and `is_seed_agg_node=true` in `node_result.json`.",
        "- Set `is_buggy=false` and `is_buggy_plots=false` if aggregation succeeded and plots were produced.",
        "- Populate `metric` with an aggregate value (e.g., mean across seeds) matching `evaluation_metric_spec`.",
    ]


def codex_node_result_contract_prompt_lines() -> list[str]:
    return [
        "- Seed aggregation required fields:",
        "  - `is_seed_node` must be true",
        "  - `is_seed_agg_node` must be true",
        "  - `analysis` must summarize variability/stability across seeds (mention mean and spread)",
        "  - If `is_buggy_plots` is false, you MUST write at least 1 `.png` plot into `./working/`.",
        "  - If `is_buggy_plots` is false, you MUST provide at least 1 `plot_analyses` entry with an `analysis` string.",
        "  - If `is_buggy_plots` is false, you MUST provide a non-empty `vlm_feedback_summary` list.",
    ]


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
        plot_analyses_val = node_result.get("plot_analyses")
        if isinstance(plot_analyses_val, list) and len(plot_analyses_val) == 0:
            errors.append(
                "seed aggregation requires plot_analyses to be non-empty when is_buggy_plots=false"
            )
        vlm_feedback_summary_val = node_result.get("vlm_feedback_summary")
        if isinstance(vlm_feedback_summary_val, list) and not any(
            is_non_empty_string(value=x) for x in vlm_feedback_summary_val
        ):
            errors.append(
                "seed aggregation requires vlm_feedback_summary to be non-empty when is_buggy_plots=false"
            )
    return errors
