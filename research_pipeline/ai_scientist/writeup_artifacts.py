import json
import logging
import traceback
from pathlib import Path
from typing import Any, Dict, FrozenSet, List

logger = logging.getLogger(__name__)

JsonValue = str | int | float | bool | None | Dict[str, "JsonValue"] | List["JsonValue"]
SUMMARY_KEYS_TO_STRIP: FrozenSet[str] = frozenset({"plot_code", "code"})


def strip_summary_keys(data: JsonValue, keys_to_strip: FrozenSet[str]) -> JsonValue:
    if isinstance(data, dict):
        return {
            k: strip_summary_keys(v, keys_to_strip)
            for k, v in data.items()
            if k not in keys_to_strip
        }
    if isinstance(data, list):
        return [strip_summary_keys(item, keys_to_strip) for item in data]
    return data


def load_idea_text(base_path: Path, logs_dir: Path, run_dir_name: str | None) -> str:
    """
    Load the idea markdown content by checking project-level and run-level files.
    """
    candidates: List[Path] = [
        base_path / "research_idea.md",
        base_path / "idea.md",
    ]
    if run_dir_name:
        candidates.append(logs_dir / run_dir_name / "research_idea.md")

    for candidate in candidates:
        if candidate.exists():
            try:
                return candidate.read_text(encoding="utf-8")
            except Exception:
                logger.warning("Warning: failed to read idea text from %s", candidate)
                logger.debug(traceback.format_exc())
    logger.warning("Warning: Missing idea markdown files under %s and %s", base_path, logs_dir)
    return ""


def load_exp_summaries(base_path: Path, run_dir_name: str) -> Dict[str, Any]:
    """
    Load experiment summary artifacts (baseline, research, ablations) from the run directory.
    """
    logs_dir = base_path / "logs"
    summary_map: Dict[str, Path] = {
        "BASELINE_SUMMARY": logs_dir / run_dir_name / "baseline_summary.json",
        "RESEARCH_SUMMARY": logs_dir / run_dir_name / "research_summary.json",
        "ABLATION_SUMMARY": logs_dir / run_dir_name / "ablation_summary.json",
    }
    loaded: Dict[str, Any] = {}
    for key, path in summary_map.items():
        if path.exists():
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                if key == "ABLATION_SUMMARY":
                    loaded[key] = data if isinstance(data, list) else []
                else:
                    loaded[key] = data if isinstance(data, dict) else {}
            except json.JSONDecodeError:
                logger.warning("Warning: %s is not valid JSON. Using empty data.", path)
                logger.debug(traceback.format_exc())
                loaded[key] = [] if key == "ABLATION_SUMMARY" else {}
        else:
            logger.warning("Summary file not found for %s: %s", key, path)
            loaded[key] = [] if key == "ABLATION_SUMMARY" else {}
    return loaded


def filter_experiment_summaries(exp_summaries: Dict[str, Any], step_name: str) -> Dict[str, Any]:
    """
    Filter experiment summaries to include only keys relevant for a given step.
    """
    if step_name == "citation_gathering":
        node_keys_to_keep = {
            "overall_plan",
            "analysis",
            "metric",
            "code",
        }
    elif step_name == "writeup":
        node_keys_to_keep = {
            "overall_plan",
            "analysis",
            "metric",
            "code",
            "plot_analyses",
            "vlm_feedback_summary",
        }
    elif step_name == "plot_aggregation":
        node_keys_to_keep = {
            "overall_plan",
            "analysis",
            "plot_plan",
            "plot_code",
            "plot_analyses",
            "vlm_feedback_summary",
            "exp_results_npy_files",
        }
    else:
        raise ValueError(f"Invalid step name: {step_name}")

    filtered: Dict[str, Any] = {}
    for stage_name, stage_content in exp_summaries.items():
        if stage_name in {"BASELINE_SUMMARY", "RESEARCH_SUMMARY"}:
            filtered[stage_name] = {}
            best_node = stage_content.get("best node", {})
            filtered_best: Dict[str, Any] = {}
            for node_key, node_value in best_node.items():
                if node_key in node_keys_to_keep:
                    filtered_best[node_key] = node_value
            filtered[stage_name]["best node"] = filtered_best
        elif stage_name == "ABLATION_SUMMARY":
            if step_name == "plot_aggregation":
                filtered[stage_name] = {}
                for ablation_summary in stage_content:
                    ablation_name = ablation_summary.get("ablation_name")
                    if not ablation_name:
                        continue
                    filtered[stage_name][ablation_name] = {}
                    for node_key, node_value in ablation_summary.items():
                        if node_key in node_keys_to_keep:
                            filtered[stage_name][ablation_name][node_key] = node_value
            else:
                filtered[stage_name] = stage_content
    return filtered
