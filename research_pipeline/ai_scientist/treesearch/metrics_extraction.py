"""
Utilities to aggregate metrics and progress signals from a stage journal.

Responsibilities:
- Collect per-node summaries, VLM feedback, and best-metric information
- Identify systemic issues/patterns and summarize recent changes
"""

from typing import Dict, List

from .journal import Journal, Node


def gather_stage_metrics(*, journal: Journal) -> Dict[str, object]:
    """Gather detailed metrics and analysis from the stage's nodes."""
    node_summaries: list[object] = []
    vlm_feedback_list: list[object] = []

    for node in journal.nodes:
        if node._agent is not None:
            try:
                node_summary = node._agent._generate_node_summary(node)
                node_summaries.append(node_summary)
            except Exception:
                continue

    for node in journal.good_nodes:
        if node._vlm_feedback is not None:
            vlm_feedback_list.append(node._vlm_feedback)

    best_metric_obj: Dict[str, object] | None = None
    best_node = journal.get_best_node()
    if best_node and best_node.metric is not None:
        best_metric_obj = {
            "value": best_node.metric.value,
            "name": (
                best_node.metric.name if best_node.metric.name is not None else "validation_metric"
            ),
            "maximize": bool(best_node.metric.maximize),
            "analysis": best_node.analysis,
        }

    return {
        "total_nodes": len(journal.nodes),
        "good_nodes": len(journal.good_nodes),
        "buggy_nodes": len(journal.buggy_nodes),
        "best_metric": best_metric_obj,
        "node_summaries": node_summaries,
        "vlm_feedback": vlm_feedback_list,
    }


def identify_issues(*, journal: Journal) -> List[str]:
    """Identify systemic issues and challenges from the current stage's results."""
    issues: List[str] = []

    # Look for patterns in leaf nodes (endpoints of improvement attempts)
    leaf_nodes: List[Node] = [n for n in journal.nodes if n.is_leaf]
    buggy_leaves: List[Node] = [n for n in leaf_nodes if n.is_buggy]

    if buggy_leaves:
        # Group similar issues
        error_patterns: Dict[str, List[str]] = {}
        for node in buggy_leaves:
            key = node.analysis if node.analysis is not None else "Unknown error"
            error_patterns.setdefault(key, []).append(node.id)

        for error_msg, node_ids in error_patterns.items():
            if len(node_ids) >= 2:
                issues.append(f"Persistent issue in nodes {node_ids}: {error_msg}")

    # Include VLM-identified systemic issues
    vlm_issues: set[str] = set()
    for node in journal.good_nodes:
        vlm_feedback = node._vlm_feedback
        if isinstance(vlm_feedback, dict):
            systemic = vlm_feedback.get("systemic_issues", [])
            if isinstance(systemic, list):
                vlm_issues.update([str(x) for x in systemic])
            analyses = vlm_feedback.get("plot_analyses", [])
            if isinstance(analyses, list):
                for analysis in analyses:
                    if (
                        isinstance(analysis, dict)
                        and "limitation" in str(analysis.get("type", "")).lower()
                    ):
                        detail = analysis.get("analysis", "")
                        vlm_issues.add(f"VLM (Node {node.id}): {detail}")

    issues.extend(list(vlm_issues))
    return issues


def analyze_progress(*, journal: Journal) -> Dict[str, object]:
    """Analyze progress and convergence in the current stage."""
    progress: Dict[str, object] = {
        "iterations_completed": len(journal.nodes),
        "improvements_found": 0,
        "convergence_status": "not_converged",
        "improvement_trend": [],
        "recent_changes": [],
    }

    # Analyze recent changes
    recent_nodes = journal.nodes[-3:] if len(journal.nodes) >= 3 else journal.nodes
    for node in recent_nodes:
        if not node.is_buggy:
            change = {
                "node_id": node.id,
                "metric": (node.metric.value if node.metric is not None else None),
                "parent_id": node.parent.id if node.parent else None,
                "analysis": node.analysis,
            }
            recent_list = progress.get("recent_changes")
            if isinstance(recent_list, list):
                recent_list.append(change)
            else:
                progress["recent_changes"] = [change]

    return progress
