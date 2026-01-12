import logging
import os
from dataclasses import dataclass
from typing import Any, List

from .journal import Journal, Node

logger = logging.getLogger(__name__)


@dataclass
class StageSummaryResponse:
    Experiment_description: str
    Significance: str
    Description: str
    List_of_included_plots: List[dict[str, Any]]
    Key_numerical_results: List[dict[str, Any]]

    def model_dump(self, *, by_alias: bool) -> dict[str, Any]:
        _ = by_alias
        return {
            "Experiment_description": self.Experiment_description,
            "Significance": self.Significance,
            "Description": self.Description,
            "List_of_included_plots": self.List_of_included_plots,
            "Key_numerical_results": self.Key_numerical_results,
        }


def summarize_stage(*, journal: Journal) -> StageSummaryResponse:
    """Deterministic stage summary (no LLM)."""
    best = journal.get_best_node(only_good=True, use_val_metric_only=True)
    best_metric = str(best.metric) if best is not None and best.metric is not None else "N/A"
    exp_desc = (
        f"Stage {journal.stage_name} ran {len(journal.nodes)} experiments "
        f"({len(journal.good_nodes)} successful, {len(journal.buggy_nodes)} buggy)."
    )
    significance = f"Best metric observed: {best_metric}."
    description = (
        "Summaries are computed deterministically from recorded node metrics and analyses."
    )

    included_plots: List[dict[str, Any]] = []
    if best is not None and best.plots:
        for p in best.plots[:6]:
            included_plots.append({"path": p, "description": "plot", "analysis": ""})

    key_results: List[dict[str, Any]] = []
    if best is not None and best.metric is not None:
        key_results.append({"result": best_metric, "description": "best_metric", "analysis": ""})

    return StageSummaryResponse(
        Experiment_description=exp_desc,
        Significance=significance,
        Description=description,
        List_of_included_plots=included_plots,
        Key_numerical_results=key_results,
    )


def _annotate_history_deterministic(*, journal: Journal) -> None:
    """
    Deterministic replacement for LLM-based overall_plan synthesis.

    Keeps any existing overall_plan (e.g., produced by Codex). Otherwise constructs a
    simple parent→child concatenation so downstream consumers (e.g., writeup filters)
    have non-empty content.
    """
    # Ensure parents have overall_plan first.
    for node in sorted(journal.nodes, key=lambda n: n.ctime):
        if node.overall_plan:
            continue
        if node.parent is None:
            node.overall_plan = node.plan or ""
            continue
        parent_plan = node.parent.overall_plan or node.parent.plan or ""
        node_plan = node.plan or ""
        combined = (parent_plan.strip() + "\n\n" + node_plan.strip()).strip()
        # Avoid runaway growth
        node.overall_plan = combined[:8000]


def _get_node_log(*, node: Node) -> dict[str, Any]:
    node_dict = node.to_dict()
    keys_to_include = [
        "overall_plan",
        "analysis",
        "metric",
        "code",
        "plot_code",
        "plot_plan",
        "plot_analyses",
        "plot_paths",
        "vlm_feedback_summary",
        "exp_results_dir",
        "ablation_name",
        "hyperparam_name",
    ]
    ret: dict[str, Any] = {
        key: node_dict[key]
        for key in keys_to_include
        if key in node_dict and node_dict[key] is not None
    }
    exp_results_dir_obj = ret.get("exp_results_dir")
    if isinstance(exp_results_dir_obj, str) and exp_results_dir_obj:
        original_dir_path = exp_results_dir_obj
        idx = original_dir_path.find("experiment_results")
        short_dir_path = original_dir_path[idx:] if idx != -1 else original_dir_path
        ret["exp_results_dir"] = short_dir_path
        abs_dir = os.path.join(os.getcwd(), original_dir_path)
        if os.path.isdir(abs_dir):
            npy_files = [f for f in os.listdir(abs_dir) if f.endswith(".npy")]
            ret["exp_results_npy_files"] = [os.path.join(short_dir_path, f) for f in npy_files]
        else:
            ret["exp_results_npy_files"] = []
    return ret


def _summarize_best_node_block(*, journal: Journal) -> dict[str, Any]:
    best_node = journal.get_best_node(only_good=True, use_val_metric_only=True)
    if best_node is None:
        return {"best node": {}}
    # Include seed child nodes when present
    seed_nodes = [
        child for child in best_node.children if child.is_seed_node and not child.is_seed_agg_node
    ]
    return {
        "best node": _get_node_log(node=best_node),
        "best node with different seeds": [_get_node_log(node=n) for n in seed_nodes],
    }


def _summarize_ablations(*, journal: Journal) -> list[dict[str, Any]]:
    ablation_roots = [
        n for n in journal.nodes if n.ablation_name is not None and not n.is_seed_node
    ]
    summaries: list[dict[str, Any]] = []
    for root in ablation_roots:
        if root.is_buggy:
            continue
        node_log = _get_node_log(node=root)
        if "ablation_name" not in node_log and root.ablation_name is not None:
            node_log["ablation_name"] = root.ablation_name
        summaries.append(node_log)
    return summaries


def overall_summarize(
    journals: list[tuple[str, Journal]],
    *,
    model: str,
    temperature: float,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], list[dict[str, Any]]]:
    """
    Deterministic replacement for the LLM summarizer.

    Returns: (draft_summary, baseline_summary, research_summary, ablation_summary)
    """
    _ = model
    _ = temperature
    draft: dict[str, Any] = {}
    baseline: dict[str, Any] = {}
    research: dict[str, Any] = {}
    ablation: list[dict[str, Any]] = []

    for stage_name, journal in journals:
        _annotate_history_deterministic(journal=journal)
        if "draft" in stage_name:
            draft = summarize_stage(journal=journal).model_dump(by_alias=True)
            continue
        if "stage_4" in stage_name:
            ablation = _summarize_ablations(journal=journal)
            continue
        if "stage_1" in stage_name:
            baseline = _summarize_best_node_block(journal=journal)
            continue
        # Stage 2/3 and anything else are treated as "research" for reporting.
        research = _summarize_best_node_block(journal=journal)

    return draft, baseline, research, ablation
