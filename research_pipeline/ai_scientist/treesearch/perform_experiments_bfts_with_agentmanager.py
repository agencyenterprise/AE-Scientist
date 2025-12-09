"""
Run the BFTS experiments using AgentManager with a simple terminal UI.

High-level steps:
- Load run configuration and problem description
- Prepare a clean agent workspace for the experiment
- Construct an AgentManager to orchestrate stages/substages
- Render a lightweight live UI (task description, tree view, progress)
- Iterate experiment steps and persist progress snapshots
- Emit progress/log events for external listeners
- Optionally generate final summary reports at the end
"""

import atexit
import json
import logging
import shutil
import time
from pathlib import Path
from typing import Callable

from .agent_manager import AgentManager
from .events import BaseEvent, RunLogEvent, RunStageProgressEvent
from .journal import Journal
from .log_summarization import overall_summarize
from .stages.base import StageMeta
from .utils.config import load_cfg, load_task_desc, prep_agent_workspace, save_run

logger = logging.getLogger("ai-scientist")


def perform_experiments_bfts(
    config_path: Path, event_callback: Callable[[BaseEvent], None]
) -> None:
    # Load configuration for this run
    cfg = load_cfg(config_path)
    logger.info(f'Starting run "{cfg.exp_name}"')

    # Use partial to create a picklable emit_event function

    # Load the task description (idea) for the experiment
    task_desc = load_task_desc(cfg)

    global_step = 0

    # Prepare a clean agent workspace for the run
    logger.info("Preparing agent workspace (copying and extracting files) ...")
    prep_agent_workspace(cfg)

    def cleanup() -> None:
        if global_step == 0:
            # Remove workspace if the run produced no steps
            shutil.rmtree(cfg.workspace_dir)

    atexit.register(cleanup)

    # Initialize the AgentManager (orchestrates stages and substages)
    manager = AgentManager(
        task_desc=task_desc,
        cfg=cfg,
        workspace_dir=Path(cfg.workspace_dir),
        event_callback=event_callback,
    )

    # Track iteration timing for smart ETA calculation
    iteration_start_times: list[float] = []
    iteration_durations: list[float] = []
    # Track per-stage iteration state to avoid duplicate progress events and
    # to ensure iteration counts start from 1 for each main stage.
    last_reported_iteration_by_stage: dict[str, int] = {}
    baseline_nodes_by_stage: dict[str, int] = {}

    def step_callback(stage: StageMeta, journal: Journal) -> None:
        # Persist progress snapshot and emit progress events after each step
        logger.debug("Step complete")
        try:
            # Track iteration timing
            current_time = time.time()
            if len(iteration_start_times) > 0:
                duration = current_time - iteration_start_times[-1]
                iteration_durations.append(duration)
            iteration_start_times.append(current_time)

            # Generate and save notes for this step
            notes_dir = cfg.log_dir / f"stage_{stage.name}" / "notes"
            notes_dir.mkdir(parents=True, exist_ok=True)

            # Save latest node summary
            latest_node = None
            if journal.nodes:
                latest_node = journal.nodes[-1]
                if hasattr(latest_node, "_agent"):
                    summary = latest_node._agent._generate_node_summary(latest_node)
                    with open(notes_dir / f"node_{latest_node.id}_summary.json", "w") as f:
                        json.dump(summary, f, indent=2)

            # Generate and save stage progress summary
            best_node = journal.get_best_node()
            # Compute good_nodes once to avoid repeated property calls (which also log)
            good_nodes_list = journal.good_nodes
            good_nodes_count = len(good_nodes_list)
            stage_summary = {
                "stage": stage.name,
                "total_nodes": len(journal.nodes),
                "buggy_nodes": len(journal.buggy_nodes),
                "good_nodes": good_nodes_count,
                "best_metric": (str(best_node.metric) if best_node else "None"),
                "current_findings": journal.generate_summary(include_code=False),
            }

            with open(notes_dir / "stage_progress.json", "w") as f:
                json.dump(stage_summary, f, indent=2)

            # Save the run as before
            save_run(cfg, journal, stage_name=f"stage_{stage.name}")

            # ALWAYS emit progress - show actual work being done.
            # Derive an effective iteration count for this stage that:
            # - Ignores seed nodes (multi-seed eval and aggregation nodes)
            # - For stages > 1, treats the single carried-over best node from the
            #   previous stage as baseline (not counted as a new iteration).
            non_seed_nodes = [n for n in journal.nodes if not n.is_seed_node]
            if stage.name not in baseline_nodes_by_stage:
                baseline_nodes_by_stage[stage.name] = 0 if stage.number == 1 else 1
            baseline = baseline_nodes_by_stage[stage.name]
            effective_iteration = max(len(non_seed_nodes) - baseline, 0)

            if stage.max_iterations > 0:
                iteration_display = min(effective_iteration, stage.max_iterations)
                progress = max(0.0, min(effective_iteration / stage.max_iterations, 1.0))
            else:
                iteration_display = effective_iteration
                progress = 0.0

            # Calculate smart ETA using moving average of recent iterations
            eta_s = None
            if len(iteration_durations) >= 2:
                # Use last 5 iterations (or fewer if not enough data)
                recent_durations = iteration_durations[-5:]
                avg_duration = sum(recent_durations) / len(recent_durations)
                remaining_iterations = max(stage.max_iterations - effective_iteration, 0)
                eta_s = int(remaining_iterations * avg_duration)

            # Get latest node execution time for display
            latest_exec_time_s = None
            if (
                latest_node
                and hasattr(latest_node, "exec_time")
                and latest_node.exec_time is not None
            ):
                latest_exec_time_s = int(latest_node.exec_time)

            # Emit progress with the actual stage name to reflect current substage accurately.
            # To avoid duplicate events (for example, during multi-seed evaluation where
            # additional nodes do not advance the effective iteration), only emit when
            # the iteration for this stage actually increases.
            # Also emit when stage completes (reaches max_iterations) to ensure final progress=1.0 is recorded.
            previous_iteration = last_reported_iteration_by_stage.get(stage.name)
            stage_complete = stage.max_iterations > 0 and len(journal.nodes) >= stage.max_iterations
            # Emit if iteration increased, or if stage completed and we haven't emitted the final event yet
            iteration_increased = (
                previous_iteration is None or iteration_display > previous_iteration
            )
            needs_final_event = (
                stage_complete
                and previous_iteration is not None
                and previous_iteration < stage.max_iterations
            )
            should_emit = iteration_display > 0 and (iteration_increased or needs_final_event)
            if should_emit:
                last_reported_iteration_by_stage[stage.name] = iteration_display
                # When stage completes, ensure progress is exactly 1.0 and iteration equals max_iterations
                if stage_complete and stage.max_iterations > 0:
                    final_progress = 1.0
                    final_iteration = stage.max_iterations
                else:
                    final_progress = progress
                    final_iteration = iteration_display
                event_callback(
                    RunStageProgressEvent(
                        stage=stage.name,
                        iteration=final_iteration,
                        max_iterations=stage.max_iterations,
                        progress=final_progress,
                        total_nodes=len(journal.nodes),
                        buggy_nodes=len(journal.buggy_nodes),
                        good_nodes=good_nodes_count,
                        best_metric=str(best_node.metric) if best_node else None,
                        eta_s=eta_s,
                        latest_iteration_time_s=latest_exec_time_s,
                    )
                )

            # Also emit a log event describing what's happening
            if good_nodes_count == 0 and len(journal.buggy_nodes) > 0:
                event_callback(
                    RunLogEvent(
                        message=f"Debugging failed implementations ({len(journal.buggy_nodes)} buggy nodes, retrying...)",
                        level="info",
                    )
                )
            elif good_nodes_count > 0:
                event_callback(
                    RunLogEvent(
                        message=f"Found {good_nodes_count} working implementation(s), continuing...",
                        level="info",
                    )
                )

        except Exception as e:
            logger.exception(f"Error in step callback: {e}")

        logger.info(f"Run saved at {cfg.log_dir / f'stage_{stage.name}'}")
        logger.debug(
            f"Step {min(len(journal), stage.max_iterations)}/{stage.max_iterations} at stage_{stage.name}"
        )

    manager.run(step_callback=step_callback)

    if cfg.generate_report:
        logger.info("Generating final report from all stages...")
        (
            draft_summary,
            baseline_summary,
            research_summary,
            ablation_summary,
        ) = overall_summarize(
            list(manager.journals.items()),
            model=cfg.report.model,
            temperature=cfg.report.temp,
        )
        draft_summary_path = cfg.log_dir / "draft_summary.json"
        baseline_summary_path = cfg.log_dir / "baseline_summary.json"
        research_summary_path = cfg.log_dir / "research_summary.json"
        ablation_summary_path = cfg.log_dir / "ablation_summary.json"

        with open(draft_summary_path, "w") as draft_file:
            json.dump(draft_summary, draft_file, indent=2)

        with open(baseline_summary_path, "w") as baseline_file:
            json.dump(baseline_summary, baseline_file, indent=2)

        with open(research_summary_path, "w") as research_file:
            json.dump(research_summary, research_file, indent=2)

        with open(ablation_summary_path, "w") as ablation_file:
            json.dump(ablation_summary, ablation_file, indent=2)

        logger.info("Summary reports written to files:")
        logger.info(f"- Draft summary: {draft_summary_path}")
        logger.info(f"- Baseline summary: {baseline_summary_path}")
        logger.info(f"- Research summary: {research_summary_path}")
        logger.info(f"- Ablation summary: {ablation_summary_path}")


if __name__ == "__main__":
    cfg_path = Path("treesearch/utils/config.yaml")
    cfg = load_cfg(cfg_path)
    perform_experiments_bfts(cfg_path, event_callback=lambda event: logger.info(event.to_dict()))
