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

import json
import logging
from pathlib import Path
from typing import Callable

from .agent_manager import AgentManager, RunOutcome
from .config import load_cfg, load_task_desc, prep_agent_workspace, save_run
from .evaluation_metric import define_evaluation_metric_spec_via_llm
from .events import BaseEvent, RunLogEvent, RunStageProgressEvent
from .journal import Journal
from .log_summarization import overall_summarize
from .node_summary import generate_node_summary
from .stages.base import StageMeta

logger = logging.getLogger("ai-scientist")


def perform_experiments_bfts(
    config_path: Path, event_callback: Callable[[BaseEvent], None], title: str
) -> RunOutcome:
    # Load configuration for this run
    cfg = load_cfg(config_path)
    logger.info(f'Starting run "{cfg.exp_name}"')

    # Use partial to create a picklable emit_event function

    # Load the task description (idea) for the experiment
    task_desc = load_task_desc(cfg)

    # Prepare a clean agent workspace for the run
    logger.info("Preparing agent workspace (copying and extracting files) ...")
    prep_agent_workspace(cfg=cfg, config_path=config_path)

    # Define the global evaluation metric spec once for this run.
    try:
        event_callback(
            RunLogEvent(message="Defining global evaluation metric spec via LLM...", level="info")
        )
    except (OSError, RuntimeError, ValueError, TypeError):
        logger.exception("Failed to emit run log event for metric definition.")
    stage_cfg = cfg.agent.feedback
    evaluation_metric_spec = define_evaluation_metric_spec_via_llm(
        title=title,
        task_desc=task_desc,
        model=stage_cfg.model,
        temperature=stage_cfg.temperature,
    )

    # Initialize the AgentManager (orchestrates stages and substages)
    manager = AgentManager(
        title=title,
        task_desc=task_desc,
        cfg=cfg,
        workspace_dir=Path(cfg.workspace_dir),
        event_callback=event_callback,
        evaluation_metric_spec=evaluation_metric_spec,
    )

    # Track per-stage iteration state to avoid duplicate progress events and
    # to ensure iteration counts start from 1 for each main stage.
    last_reported_iteration_by_stage: dict[str, int] = {}
    stage_best_node_summary_written: set[str] = set()

    def iteration_started_callback(stage: StageMeta, journal: Journal) -> None:
        attempt_iteration = manager.get_attempt_iteration(stage.name)
        if attempt_iteration == 0:
            return
        if stage.max_iterations > 0:
            iteration_display = min(attempt_iteration, stage.max_iterations)
        else:
            iteration_display = attempt_iteration

        best_node = journal.get_best_node()
        good_nodes_list = journal.good_nodes
        good_nodes_count = len(good_nodes_list)

        stage_completed = manager.has_stage_completed(stage.name)
        previous_iteration = last_reported_iteration_by_stage.get(stage.name)
        stage_complete = stage.max_iterations > 0 and attempt_iteration > stage.max_iterations
        iteration_increased = previous_iteration is None or iteration_display > previous_iteration
        needs_final_event = (
            stage_complete
            and previous_iteration is not None
            and previous_iteration < stage.max_iterations
        )
        should_emit = iteration_display > 0 and (iteration_increased or needs_final_event)
        if should_emit and not stage_completed:
            last_reported_iteration_by_stage[stage.name] = iteration_display
            final_iteration = iteration_display
            # Report progress based on completed iterations, not started iterations
            # When iteration N starts, N-1 iterations have completed
            completed_iterations = max(iteration_display - 1, 0)
            final_progress = (
                completed_iterations / stage.max_iterations if stage.max_iterations > 0 else 0.0
            )
            if stage_complete:
                final_progress = 1.0

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
                    is_seed_node=False,
                    is_seed_agg_node=False,
                )
            )

    def step_callback(stage: StageMeta, journal: Journal) -> None:
        # Persist progress snapshot and emit progress events after each step
        logger.debug("Step complete")
        try:
            # Generate and save notes for this step
            notes_dir = cfg.log_dir / f"stage_{stage.name}" / "notes"
            notes_dir.mkdir(parents=True, exist_ok=True)

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

            # Generate a single LLM summary at the end of the stage (not per node).
            if (
                manager.has_stage_completed(stage.name)
                and stage.name not in stage_best_node_summary_written
            ):
                best_node_for_summary = journal.get_best_node(
                    only_good=True, use_val_metric_only=True
                )
                node_for_summary = (
                    best_node_for_summary if best_node_for_summary is not None else None
                )
                if node_for_summary is None and journal.nodes:
                    node_for_summary = journal.nodes[-1]
                if node_for_summary is not None:
                    try:
                        logger.debug(
                            "node_summary.callsite purpose=%s node=%s stage=%s",
                            "step_callback.stage_completed_best_node_summary",
                            node_for_summary.id[:8],
                            stage.name,
                        )
                        summary = generate_node_summary(
                            purpose="step_callback.stage_completed_best_node_summary",
                            model=journal.summary_model,
                            temperature=journal.summary_temperature,
                            stage_name=stage.name,
                            node=node_for_summary,
                            task_desc=task_desc,
                        )
                    except Exception:  # noqa: BLE001  # pylint: disable=broad-exception-caught
                        summary = None
                    if summary is not None:
                        payload = {
                            "stage": stage.name,
                            "node_id": node_for_summary.id,
                            "summary": summary,
                        }
                        with open(
                            notes_dir / "best_node_summary.json",
                            mode="w",
                            encoding="utf-8",
                        ) as f:
                            json.dump(payload, f, indent=2)
                        stage_best_node_summary_written.add(stage.name)

            # Save the run as before
            save_run(cfg, journal, stage_name=f"stage_{stage.name}")

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

        nodes_saved = len(journal)
        logger.info(f"Run saved at {cfg.log_dir / f'stage_{stage.name}'}")
        logger.debug(
            msg=(
                f"Saved run snapshot at stage_{stage.name} "
                f"(nodes={nodes_saved}, max_iterations={stage.max_iterations})"
            )
        )

    manager.run(
        step_callback=step_callback,
        iteration_started_callback=iteration_started_callback,
    )
    outcome = manager.get_run_outcome()

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
            temperature=cfg.report.temperature,
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
    return outcome


if __name__ == "__main__":
    cfg_path = Path("treesearch/utils/config.yaml")
    cfg = load_cfg(cfg_path)
    perform_experiments_bfts(
        cfg_path,
        event_callback=lambda event: logger.info(event.to_dict()),
        title="Test Research Idea",
    )
