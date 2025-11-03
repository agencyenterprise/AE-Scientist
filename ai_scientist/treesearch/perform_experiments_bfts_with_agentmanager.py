import atexit
import json
import logging
import pickle
import shutil
import time
from functools import partial
from pathlib import Path
from typing import Any, Callable, Dict, Optional

from rich.columns import Columns
from rich.console import Group
from rich.live import Live
from rich.padding import Padding
from rich.panel import Panel
from rich.progress import BarColumn, MofNCompleteColumn, Progress, TextColumn, TimeRemainingColumn
from rich.status import Status
from rich.text import Text
from rich.tree import Tree

from . import backend
from .agent_manager import AgentManager, Stage
from .interpreter import ExecutionResult
from .journal import Journal, Node
from .log_summarization import overall_summarize
from .utils.config import load_cfg, load_task_desc, prep_agent_workspace, save_run

logger = logging.getLogger("ai-scientist")


def _safe_emit_event(
    event_callback: Optional[Callable[[str, Dict[str, Any]], None]],
    event_type: str,
    data: Dict[str, Any],
) -> None:
    """Module-level function for event emission that can be pickled for multiprocessing."""
    if event_callback:
        try:
            event_callback(event_type, data)
        except Exception as e:
            logger.warning(f"Event callback failed: {e}")


def journal_to_rich_tree(journal: Journal) -> Tree:
    best_node = journal.get_best_node()

    def append_rec(node: Node, tree: Tree) -> None:
        if node.is_buggy:
            s = "[red]◍ bug"
        else:
            style = "bold " if node is best_node else ""
            metric_val = f"{node.metric.value:.3f}" if node.metric is not None else "N/A"
            if node is best_node:
                s = f"[{style}green]● {metric_val} (best)"
            else:
                s = f"[{style}green]● {metric_val}"

        subtree = tree.add(s)
        for child in node.children:
            append_rec(child, subtree)

    tree = Tree("[bold blue]Solution tree")
    for n in journal.draft_nodes:
        append_rec(n, tree)
    return tree


def perform_experiments_bfts(
    config_path: Path, event_callback: Optional[Callable[[str, Dict[str, Any]], None]] = None
) -> None:
    cfg = load_cfg(config_path)
    logger.info(f'Starting run "{cfg.exp_name}"')

    # Use partial to create a picklable emit_event function
    emit_event = partial(_safe_emit_event, event_callback)

    task_desc = load_task_desc(cfg)
    print(task_desc)
    compiled = backend.compile_prompt_to_md(task_desc)
    task_desc_md = compiled if isinstance(compiled, str) else str(compiled)

    global_step = 0

    with Status("Preparing agent workspace (copying and extracting files) ..."):
        prep_agent_workspace(cfg)

    def cleanup() -> None:
        if global_step == 0:
            shutil.rmtree(cfg.workspace_dir)

    atexit.register(cleanup)

    task_desc_input = task_desc if isinstance(task_desc, str) else json.dumps(task_desc)
    manager = AgentManager(
        task_desc=task_desc_input,
        cfg=cfg,
        workspace_dir=Path(cfg.workspace_dir),
        event_callback=emit_event,
    )

    prog = Progress(
        TextColumn("[progress.description]{task.description}"),
        BarColumn(bar_width=20),
        MofNCompleteColumn(),
        TimeRemainingColumn(),
    )
    status = Status("[green]Running experiments...")
    prog.add_task("Progress:", total=cfg.agent.steps, completed=global_step)

    def create_exec_callback(status_obj: Status) -> Callable[[str, bool], ExecutionResult]:
        def exec_callback(_code: str, _is_exec: bool) -> ExecutionResult:
            status_obj.update("[magenta]Executing code...")
            # This callback is not used by ParallelAgent; return a placeholder result
            status_obj.update("[green]Generating code...")
            return ExecutionResult(term_out=[], exec_time=0.0, exc_type=None)

        return exec_callback

    # Track iteration timing for smart ETA calculation
    iteration_start_times: list[float] = []
    iteration_durations: list[float] = []

    def step_callback(stage: Stage, journal: Journal) -> None:
        print("Step complete")
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
            latest_node_summary = None
            latest_node = None
            if journal.nodes:
                latest_node = journal.nodes[-1]
                if hasattr(latest_node, "_agent"):
                    summary = latest_node._agent._generate_node_summary(latest_node)
                    with open(notes_dir / f"node_{latest_node.id}_summary.json", "w") as f:
                        json.dump(summary, f, indent=2)
                    latest_node_summary = summary

            # Generate and save stage progress summary
            best_node = journal.get_best_node()
            stage_summary = {
                "stage": stage.name,
                "total_nodes": len(journal.nodes),
                "buggy_nodes": len(journal.buggy_nodes),
                "good_nodes": len(journal.good_nodes),
                "best_metric": (str(best_node.metric) if best_node else "None"),
                "current_findings": journal.generate_summary(include_code=False),
            }

            with open(notes_dir / "stage_progress.json", "w") as f:
                json.dump(stage_summary, f, indent=2)

            # Save the run as before
            save_run(cfg, journal, stage_name=f"stage_{stage.name}")

            # ALWAYS emit progress - show actual work being done
            # Use total nodes as iteration count so progress shows even when all buggy
            current_iteration = len(journal.nodes)
            progress = (
                max(0.0, min(current_iteration / stage.max_iterations, 1.0))
                if stage.max_iterations > 0
                else 0.0
            )

            # Calculate smart ETA using moving average of recent iterations
            eta_s = None
            if len(iteration_durations) >= 2:
                # Use last 5 iterations (or fewer if not enough data)
                recent_durations = iteration_durations[-5:]
                avg_duration = sum(recent_durations) / len(recent_durations)
                remaining_iterations = stage.max_iterations - current_iteration
                eta_s = int(remaining_iterations * avg_duration)

            # Get latest node execution time for display
            latest_exec_time_s = None
            if (
                latest_node
                and hasattr(latest_node, "exec_time")
                and latest_node.exec_time is not None
            ):
                latest_exec_time_s = int(latest_node.exec_time)

            # Map internal BFTS stage names to Stage_1 (all BFTS stages are part of experiments phase)
            # Internal names like "1_initial_implementation_1_preliminary" → "Stage_1"
            progress_data = {
                "stage": "Stage_1",  # All BFTS substages are part of Stage_1 in the UI
                "iteration": current_iteration,  # Total nodes attempted
                "max_iterations": stage.max_iterations,
                "progress": progress,  # Based on total attempts, not just good ones
                "total_nodes": len(journal.nodes),
                "buggy_nodes": len(journal.buggy_nodes),
                "good_nodes": len(journal.good_nodes),
                "best_metric": str(best_node.metric) if best_node else None,
            }

            # Add timing information if available
            if eta_s is not None:
                progress_data["eta_s"] = eta_s
            if latest_exec_time_s is not None:
                progress_data["latest_iteration_time_s"] = latest_exec_time_s

            emit_event("ai.run.stage_progress", progress_data)

            # Also emit a log event describing what's happening
            if len(journal.good_nodes) == 0 and len(journal.buggy_nodes) > 0:
                emit_event(
                    "ai.run.log",
                    {
                        "message": f"Debugging failed implementations ({len(journal.buggy_nodes)} buggy nodes, retrying...)",
                        "level": "info",
                    },
                )
            elif len(journal.good_nodes) > 0:
                emit_event(
                    "ai.run.log",
                    {
                        "message": f"Found {len(journal.good_nodes)} working implementation(s), continuing...",
                        "level": "info",
                    },
                )

            # Emit node completion if we have a latest node
            if latest_node is not None and latest_node_summary:
                emit_event(
                    "ai.experiment.node_completed",
                    {
                        "stage": "Stage_1",  # All BFTS substages are part of Stage_1 in the UI
                        "node_id": latest_node.id if hasattr(latest_node, "id") else None,
                        "summary": latest_node_summary,
                    },
                )

        except Exception as e:
            print(f"Error in step callback: {e}")

        print(f"Run saved at {cfg.log_dir / f'stage_{stage.name}'}")
        print(f"Step {len(journal)}/{stage.max_iterations} at stage_{stage.name}")
        print(f"Run saved at {cfg.log_dir / f'stage_{stage.name}'}")

    def generate_live(manager: AgentManager) -> Panel:
        current_stage = manager.current_stage
        key = current_stage.name if current_stage else ""
        current_journal = manager.journals.get(key, None)

        if current_journal:
            tree = journal_to_rich_tree(current_journal)
        else:
            tree = Tree("[bold blue]No results yet")

        file_paths = [
            f"Result visualization:\n[yellow]▶ {str((cfg.log_dir / 'tree_plot.html'))}",
            f"Agent workspace directory:\n[yellow]▶ {str(cfg.workspace_dir)}",
            f"Experiment log directory:\n[yellow]▶ {str(cfg.log_dir)}",
        ]

        stage_info = [
            "[bold]Experiment Progress:",
            f"Current Stage: [cyan]{current_stage.name if current_stage else 'None'}[/cyan]",
            f"Completed Stages: [green]{', '.join(manager.completed_stages)}[/green]",
        ]

        left = Group(
            Panel(Text(task_desc_md.strip()), title="Task description"),
            Panel(Text("\n".join(stage_info)), title="Stage Progress"),
            prog,
            status,
        )
        right = tree
        wide = Group(*file_paths)

        return Panel(
            Group(
                Padding(wide, (1, 1, 1, 1)),
                Columns(
                    [Padding(left, (1, 2, 1, 1)), Padding(right, (1, 1, 1, 2))],
                    equal=True,
                ),
            ),
            title=f'[b]AIDE is working on experiment: [bold green]"{cfg.exp_name}[/b]"',
            subtitle="Press [b]Ctrl+C[/b] to stop the run",
        )

    Live(
        generate_live(manager),
        refresh_per_second=16,
        screen=True,
    )

    manager.run(exec_callback=create_exec_callback(status), step_callback=step_callback)

    manager_pickle_path = cfg.log_dir / "manager.pkl"
    try:
        with open(manager_pickle_path, "wb") as f:
            pickle.dump(manager, f)
        logger.info(f"Saved manager state to: {manager_pickle_path}")
    except Exception as e:
        logger.warning(f"Failed to save full manager state: {e}")
        try:
            with open(manager_pickle_path, "wb") as f:
                pickle.dump(manager.journals.items(), f)
            logger.info(f"Saved manager journals to: {manager_pickle_path}")
        except Exception as e:
            logger.error(f"Failed to save manager journals: {e}")

    if cfg.generate_report:
        print("Generating final report from all stages...")
        (
            draft_summary,
            baseline_summary,
            research_summary,
            ablation_summary,
        ) = overall_summarize(list(manager.journals.items()))
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

        print("Summary reports written to files:")
        print(f"- Draft summary: {draft_summary_path}")
        print(f"- Baseline summary: {baseline_summary_path}")
        print(f"- Research summary: {research_summary_path}")
        print(f"- Ablation summary: {ablation_summary_path}")


if __name__ == "__main__":
    cfg_path = Path("treesearch/utils/config.yaml")
    cfg = load_cfg(cfg_path)
    perform_experiments_bfts(cfg_path)
