import json
import logging
from pathlib import Path
from typing import Any, Callable

from ai_scientist.llm import structured_query_with_schema
from ai_scientist.llm.vlm import get_structured_response_from_vlm

from .config import Config as AppConfig
from .events import BaseEvent, RunLogEvent
from .journal import Node
from .stage_identifiers import StageIdentifier
from .vlm_function_specs import PLOT_SELECTION_SCHEMA, VLM_FEEDBACK_SCHEMA

logger = logging.getLogger("ai-scientist")


def generate_vlm_feedback(
    *,
    cfg: AppConfig,
    node: Node,
    stage_identifier: StageIdentifier,
    event_callback: Callable[[BaseEvent], None],
) -> None:
    """
    Harness-owned VLM feedback generation for a node with plots.

    - Select up to 10 plots (LLM-assisted when more are available)
    - Run VLM on selected plots (structured output)
    - Populate:
      - node.is_buggy_plots
      - node.plot_analyses
      - node.vlm_feedback_summary (string)
      - node.vlm_feedback (raw dict)
    - Persist a sidecar artifact: <exp_results_dir>/node_result_harness.json
    """
    if not str(cfg.agent.vlm_feedback.model or "").strip():
        return

    # Mirror the old behavior: if plots exist but plot_paths is empty, warn and do not block the run.
    if not node.plot_paths:
        if node.plots:
            warning_msg = (
                "=" * 100
                + "\n"
                + "plot_paths is EMPTY but plots list has items; skipping VLM analysis.\n"
                + f"Node ID: {node.id}\n"
                + f"plots count: {len(node.plots)}\n"
                + f"plot_paths count: {len(node.plot_paths)}\n"
                + "Setting is_buggy_plots = False (plots unverified)\n"
                + "=" * 100
            )
            logger.warning("%s", warning_msg)
            node.is_buggy_plots = False
        return

    all_plot_paths = [Path(p) for p in node.plot_paths if str(p).strip()]
    all_plot_paths = [p for p in all_plot_paths if p.exists()]
    if not all_plot_paths:
        return

    if len(all_plot_paths) <= 10:
        selected_plot_paths = all_plot_paths
    else:
        prompt_select_plots = {
            "Introduction": (
                "You are an experienced AI researcher analyzing experimental results. "
                "You have been provided with plots from a machine learning experiment. "
                "Please select 10 most relevant plots to analyze. "
                "For similar plots (e.g. generated samples at each epoch), select at most 5 plots at a suitable interval."
            ),
            "Plot paths": [str(p) for p in all_plot_paths],
        }
        try:
            response_select_plots = structured_query_with_schema(
                system_message=prompt_select_plots,
                user_message=None,
                model=cfg.agent.feedback.model,
                temperature=cfg.agent.feedback.temperature,
                schema_class=PLOT_SELECTION_SCHEMA,
            )
            candidates = [Path(p) for p in response_select_plots.selected_plots if str(p).strip()]
            valid: list[Path] = []
            for p in candidates:
                if p.exists() and p.suffix.lower() in (".png", ".jpg", ".jpeg"):
                    valid.append(p)
            selected_plot_paths = valid if valid else all_plot_paths[:10]
        except Exception:  # noqa: BLE001
            selected_plot_paths = all_plot_paths[:10]

    try:
        logger.debug(
            "Selected %s plot(s) for VLM analysis: %s",
            len(selected_plot_paths),
            [str(p) for p in selected_plot_paths],
        )
        logger.debug(
            "VLM feedback model=%s temperature=%s",
            cfg.agent.vlm_feedback.model,
            cfg.agent.vlm_feedback.temperature,
        )
    except Exception:  # noqa: BLE001
        logger.debug("Failed to log selected plots for VLM analysis (non-fatal).")

    try:
        msg = (
            "You are an experienced AI researcher analyzing experimental results. "
            "You have been provided with plots from a machine learning experiment. "
            f"This experiment is based on the following stage: {stage_identifier.name}. "
            "Please analyze these plots and provide detailed insights about the results. "
            "If you don't receive any plots, say 'No plots received'. "
            "Never make up plot analysis. "
            "Please return the analyses in strict order of the uploaded images."
        )
        feedback, _ = get_structured_response_from_vlm(
            msg=msg,
            image_paths=[str(p) for p in selected_plot_paths],
            model=cfg.agent.vlm_feedback.model,
            system_message="",
            temperature=float(cfg.agent.vlm_feedback.temperature),
            schema_class=VLM_FEEDBACK_SCHEMA,
            max_images=25,
        )
    except Exception:  # noqa: BLE001
        logger.exception("Failed to generate VLM feedback for node=%s", node.id[:8])
        return

    try:
        response = feedback.model_dump(by_alias=True)
        try:
            logger.debug("VLM plot analysis raw response: %s", response)
        except Exception:  # noqa: BLE001
            logger.debug("VLM plot analysis raw response: <unprintable>")

        valid_plots_received = bool(response.get("valid_plots_received"))
        node.is_buggy_plots = not valid_plots_received

        plot_analyses_val = response.get("plot_analyses")
        if isinstance(plot_analyses_val, list):
            sanitized: list[dict[str, Any]] = []
            for idx, analysis in enumerate(plot_analyses_val):
                item: dict[str, Any]
                if isinstance(analysis, dict):
                    item = dict(analysis)
                else:
                    item = {"analysis": str(analysis)}
                if "plot_path" not in item and idx < len(selected_plot_paths):
                    item["plot_path"] = str(selected_plot_paths[idx])
                sanitized.append(item)
            node.plot_analyses = sanitized

        vlm_summary_val = response.get("vlm_feedback_summary")
        if isinstance(vlm_summary_val, str):
            node.vlm_feedback_summary = vlm_summary_val.strip()
        elif isinstance(vlm_summary_val, list):
            node.vlm_feedback_summary = "\n".join(
                [str(x) for x in vlm_summary_val if str(x).strip()]
            ).strip()
        else:
            node.vlm_feedback_summary = ""

        node.vlm_feedback = response

        # Persist harness-generated fields alongside artifacts for traceability.
        if node.exp_results_dir:
            out_path = Path(node.exp_results_dir) / "node_result_harness.json"
            out_obj: dict[str, object] = {
                "plots": list(node.plots),
                "plot_paths": list(node.plot_paths),
                "plot_analyses": list(node.plot_analyses),
                "vlm_feedback_summary": node.vlm_feedback_summary,
                "vlm_feedback": node.vlm_feedback,
                "datasets_successfully_tested": list(node.datasets_successfully_tested),
            }
            out_path.write_text(json.dumps(out_obj, indent=2), encoding="utf-8")

        event_callback(
            RunLogEvent(
                message=f"✓ Generated VLM feedback for {len(node.plot_analyses)} plot(s)",
                level="info",
            )
        )
    except Exception:  # noqa: BLE001
        logger.exception("Failed applying VLM feedback to node=%s", node.id[:8])
