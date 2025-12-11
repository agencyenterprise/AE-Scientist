import logging
import multiprocessing
import os
import pickle
import traceback
from pathlib import Path
from typing import Callable, Optional

from ai_scientist.llm import structured_query_with_schema

from .codegen_agent import MinimalAgent
from .events import BaseEvent, RunLogEvent
from .gpu_manager import GPUSpec, get_gpu_specs
from .interpreter import ExecutionResult, Interpreter
from .journal import Node
from .plotting import analyze_plots_with_vlm, generate_plotting_code
from .stages.stage1_baseline import Stage1Baseline
from .stages.stage2_tuning import HyperparamTuningIdea, Stage2Tuning
from .stages.stage4_ablation import AblationIdea, Stage4Ablation
from .types import PromptType
from .utils.config import Config as AppConfig
from .utils.config import apply_log_level
from .utils.metric import MetricValue, WorstMetricValue
from .utils.response import wrap_code
from .vlm_function_specs import METRIC_PARSE_SCHEMA

logger = logging.getLogger("ai-scientist")


def _ensure_worker_log_level(*, cfg: AppConfig) -> None:
    """Best-effort logging configuration for the worker process."""
    try:
        apply_log_level(level_name=cfg.log_level)
    except Exception:
        # Never fail the worker due to logging configuration
        pass


def _prepare_workspace(*, cfg: AppConfig, process_id: str) -> tuple[str, str]:
    """Create and return workspace and working directory paths for this worker."""
    workspace_path = Path(cfg.workspace_dir) / f"process_{process_id}"
    workspace_path.mkdir(parents=True, exist_ok=True)
    working_dir_path = workspace_path / "working"
    working_dir_path.mkdir(parents=True, exist_ok=True)
    return str(workspace_path), str(working_dir_path)


def _should_run_plotting_and_vlm(*, stage_name: str) -> bool:
    """Return True if plotting + VLM analysis should run for this stage."""
    # Skip plotting and VLM for Stage 1 and Stage 2; only run for later stages
    return not (stage_name.startswith("1_") or stage_name.startswith("2_"))


def _configure_gpu_for_worker(*, gpu_id: int | None) -> GPUSpec | None:
    """Configure CUDA visibility and return GPU specs if a GPU is assigned."""
    if gpu_id is None:
        os.environ["CUDA_VISIBLE_DEVICES"] = ""
        return None
    os.environ["CUDA_VISIBLE_DEVICES"] = str(gpu_id)
    return get_gpu_specs(gpu_id)


def _assign_datasets_from_metrics_response(
    *,
    child_node: Node,
    metrics_response: dict[str, object],
) -> None:
    """Populate datasets_successfully_tested from the structured metrics response."""
    raw_metric_names = metrics_response.get("metric_names", [])
    metric_entries: list[object] = (
        list(raw_metric_names) if isinstance(raw_metric_names, list) else []
    )

    dataset_names: list[str] = []
    for metric_entry in metric_entries:
        if not isinstance(metric_entry, dict):
            continue
        data_entries = metric_entry.get("data", [])
        if not isinstance(data_entries, list):
            continue
        for data_entry in data_entries:
            if not isinstance(data_entry, dict):
                continue
            dataset_name = data_entry.get("dataset_name")
            if isinstance(dataset_name, str) and dataset_name:
                dataset_names.append(dataset_name)

    seen: set[str] = set()
    unique_datasets: list[str] = []
    for name in dataset_names:
        if name not in seen:
            seen.add(name)
            unique_datasets.append(name)

    if unique_datasets:
        child_node.datasets_successfully_tested = unique_datasets


def _create_worker_agent(
    *,
    task_desc: str,
    cfg: AppConfig,
    gpu_id: int | None,
    gpu_spec: GPUSpec | None,
    memory_summary: str,
    evaluation_metrics: str,
    stage_name: str,
) -> MinimalAgent:
    return MinimalAgent(
        task_desc=task_desc,
        cfg=cfg,
        gpu_id=gpu_id,
        gpu_spec=gpu_spec,
        memory_summary=memory_summary,
        evaluation_metrics=evaluation_metrics,
        stage_name=stage_name,
    )


def _create_interpreter(*, cfg: AppConfig, workspace: str) -> Interpreter:
    return Interpreter(
        working_dir=workspace,
        timeout=cfg.exec.timeout,
        format_tb_ipython=cfg.exec.format_tb_ipython,
        agent_file_name=cfg.exec.agent_file_name,
    )


def _load_parent_node(*, node_data: dict[str, object] | None) -> Node | None:
    if node_data:
        return Node.from_dict(node_data, journal=None)
    return None


def _create_child_node(
    *,
    worker_agent: MinimalAgent,
    parent_node: Node | None,
    seed_eval: bool,
    new_ablation_idea: AblationIdea | None,
    new_hyperparam_idea: HyperparamTuningIdea | None,
    event_callback: Callable[[BaseEvent], None],
) -> Node:
    if seed_eval:
        assert parent_node is not None, "parent_node must be provided for seed evaluation"
        event_callback(RunLogEvent(message="Running multi-seed evaluation", level="info"))
        child_node = worker_agent.generate_seed_node(parent_node)
        child_node.parent = parent_node
        child_node.plot_code = parent_node.plot_code
        return child_node

    if parent_node is None:
        event_callback(RunLogEvent(message="Generating new implementation code", level="info"))
        child_node = Stage1Baseline.draft(worker_agent)
        event_callback(RunLogEvent(message="Code generation complete", level="info"))
        return child_node

    if parent_node.is_buggy:
        event_callback(
            RunLogEvent(message="Debugging failed node (attempt to fix bugs)", level="info")
        )
        child_node = worker_agent.debug(parent_node)
        child_node.parent = parent_node
        event_callback(RunLogEvent(message="Fix attempt generated", level="info"))
        return child_node

    if new_hyperparam_idea is not None and new_ablation_idea is None:
        logger.info(f"Building hyperparam tuning node {parent_node.id}")
        child_node = Stage2Tuning.build_hyperparam_tuning_node(
            agent=worker_agent,
            parent_node=parent_node,
            hyperparam_idea=new_hyperparam_idea,
        )
        child_node.parent = parent_node
        return child_node

    if new_ablation_idea is not None and new_hyperparam_idea is None:
        logger.info(f"Building ablation node {parent_node.id}")
        child_node = Stage4Ablation.build_ablation_node(
            agent=worker_agent,
            parent_node=parent_node,
            ablation_idea=new_ablation_idea,
        )
        child_node.parent = parent_node
        return child_node

    logger.info(f"Improving node {parent_node.id}")
    child_node = _improve_existing_implementation(
        worker_agent=worker_agent,
        parent_node=parent_node,
    )
    child_node.parent = parent_node
    return child_node


def _improve_existing_implementation(
    *,
    worker_agent: MinimalAgent,
    parent_node: Node,
) -> Node:
    """Improve an existing implementation based on the current experimental stage."""
    prompt: PromptType = {
        "Introduction": (
            "You are an experienced AI researcher. You are provided with a previously developed "
            "implementation. Your task is to improve it based on the current experimental stage."
        ),
        "Research idea": worker_agent.task_desc,
        "Memory": worker_agent.memory_summary if worker_agent.memory_summary else "",
        "Feedback based on generated plots": parent_node.vlm_feedback_summary,
        "Feedback about execution time": parent_node.exec_time_feedback,
        "Instructions": {},
    }
    prompt["Previous solution"] = {
        "Code": wrap_code(code=parent_node.code),
    }

    improve_instructions: dict[str, str | list[str]] = {}
    improve_instructions |= worker_agent.prompt_impl_guideline
    prompt["Instructions"] = improve_instructions

    plan, code = worker_agent.plan_and_code_query(prompt=prompt)
    logger.debug("----- LLM code start (improve) -----")
    logger.debug(code)
    logger.debug("----- LLM code end (improve) -----")
    return Node(
        plan=plan,
        code=code,
        parent=parent_node,
    )


def _execute_experiment(
    *,
    child_node: Node,
    cfg: AppConfig,
    process_interpreter: Interpreter,
    event_callback: Callable[[BaseEvent], None],
) -> ExecutionResult:
    logger.info(f"→ Executing experiment code (timeout: {cfg.exec.timeout}s)...")
    logger.debug("Starting first interpreter: executing experiment code")
    event_callback(RunLogEvent(message="Executing experiment code on GPU...", level="info"))
    exec_result = process_interpreter.run(code=child_node.code, reset_session=True)
    process_interpreter.cleanup_session()
    logger.info(f"✓ Code execution completed in {exec_result.exec_time:.1f}s")
    event_callback(
        RunLogEvent(
            message=f"Code execution completed ({exec_result.exec_time:.1f}s)", level="info"
        )
    )
    return exec_result


def _analyze_results_and_metrics(
    *,
    worker_agent: MinimalAgent,
    child_node: Node,
    parent_node: Node | None,
    cfg: AppConfig,
    working_dir: str,
    process_interpreter: Interpreter,
    seed_eval: bool,
    exec_result: ExecutionResult,
    event_callback: Callable[[BaseEvent], None],
) -> None:
    logger.info("→ Analyzing results and extracting metrics...")
    event_callback(RunLogEvent(message="Analyzing results and extracting metrics", level="info"))
    worker_agent.parse_exec_result(
        node=child_node,
        exec_result=exec_result,
    )
    parse_and_assign_metrics(
        worker_agent=worker_agent,
        child_node=child_node,
        parent_node=parent_node,
        cfg=cfg,
        working_dir=working_dir,
        process_interpreter=process_interpreter,
        seed_eval=seed_eval,
        event_callback=event_callback,
    )
    logger.info(f"✓ Metrics extracted. Buggy: {child_node.is_buggy}")


def _select_plotting_code(
    *,
    worker_agent: MinimalAgent,
    child_node: Node,
    parent_node: Node | None,
    seed_eval: bool,
    best_stage3_plot_code: str | None,
) -> str:
    if seed_eval:
        assert parent_node is not None
        return parent_node.plot_code or ""

    plot_code_from_prev_stage: str | None
    if (
        worker_agent.stage_name
        and worker_agent.stage_name.startswith("4_")
        and best_stage3_plot_code
    ):
        plot_code_from_prev_stage = best_stage3_plot_code
    else:
        plot_code_from_prev_stage = None

    return generate_plotting_code(
        agent=worker_agent,
        node=child_node,
        plot_code_from_prev_stage=plot_code_from_prev_stage,
    )


def _execute_plotting_with_retries(
    *,
    worker_agent: MinimalAgent,
    child_node: Node,
    parent_node: Node | None,
    process_interpreter: Interpreter,
    seed_eval: bool,
    best_stage3_plot_code: str | None,
    event_callback: Callable[[BaseEvent], None],
) -> str:
    logger.info("→ Generating visualization plots...")
    event_callback(RunLogEvent(message="Generating visualization plots", level="info"))
    retry_count = 0
    plotting_code = ""
    while True:
        plotting_code = _select_plotting_code(
            worker_agent=worker_agent,
            child_node=child_node,
            parent_node=parent_node,
            seed_eval=seed_eval,
            best_stage3_plot_code=best_stage3_plot_code,
        )
        event_callback(RunLogEvent(message="Executing plotting code", level="info"))
        plot_exec_result = process_interpreter.run(
            code=plotting_code,
            reset_session=True,
        )
        process_interpreter.cleanup_session()
        child_node.absorb_plot_exec_result(plot_exec_result)
        if child_node.plot_exc_type and retry_count < 3:
            term_lines = child_node.plot_term_out or []
            tail = "".join(term_lines[-50:]) if isinstance(term_lines, list) else str(term_lines)
            event_callback(
                RunLogEvent(
                    message=f"Plotting error ({child_node.plot_exc_type}); retrying {retry_count + 1}/3. Tail of output:\n{tail}",
                    level="warn",
                )
            )
            retry_count += 1
            continue
        break
    return plotting_code


def _move_experiment_artifacts(
    *,
    cfg: AppConfig,
    child_node: Node,
    working_dir: str,
    plotting_code: str,
    event_callback: Callable[[BaseEvent], None],
) -> None:
    plots_dir = Path(working_dir)
    logger.debug(f"Checking plots_dir: {plots_dir}, exists={plots_dir.exists()}")
    if not plots_dir.exists():
        logger.warning(f"plots_dir {plots_dir} does not exist!")
        return

    plot_count = len(list(plots_dir.glob("*.png")))
    logger.debug(f"Found {plot_count} plot files in working directory")
    if plot_count > 0:
        event_callback(RunLogEvent(message=f"✓ Generated {plot_count} plot file(s)", level="info"))
    else:
        event_callback(
            RunLogEvent(
                message="No plot files (*.png) found in working directory after plotting",
                level="warn",
            )
        )
        logger.warning(f"No plot files found in {plots_dir} after plotting code execution")

    base_dir = Path(cfg.workspace_dir).parent
    run_name = Path(cfg.workspace_dir).name
    exp_results_dir = (
        base_dir
        / "logs"
        / run_name
        / "experiment_results"
        / f"experiment_{child_node.id}_proc_{os.getpid()}"
    )
    logger.debug(f"Creating exp_results_dir: {exp_results_dir}")
    child_node.exp_results_dir = str(exp_results_dir)
    exp_results_dir.mkdir(parents=True, exist_ok=True)

    plot_code_path = exp_results_dir / "plotting_code.py"
    with open(plot_code_path, "w") as f:
        f.write(plotting_code)
    exp_code_path = exp_results_dir / "experiment_code.py"
    with open(exp_code_path, "w") as f:
        f.write(child_node.code)
    for exp_data_file in plots_dir.glob("*.npy"):
        exp_data_path = exp_results_dir / exp_data_file.name
        exp_data_file.resolve().rename(exp_data_path)

    plot_files_found = list(plots_dir.glob("*.png"))
    logger.debug(f"Found {len(plot_files_found)} plot files to move for node {child_node.id}")
    logger.debug(
        "Before moving: "
        f"plots={len(child_node.plots) if child_node.plots else 0}, "
        f"plot_paths={len(child_node.plot_paths) if child_node.plot_paths else 0}"
    )
    if len(plot_files_found) == 0:
        logger.warning(
            "No plot files to move! This means plots were generated but not found, "
            "or already moved."
        )
        logger.warning(f"Current plots list: {child_node.plots}")
        logger.warning(f"Current plot_paths list: {child_node.plot_paths}")
    for plot_file in plot_files_found:
        final_path = exp_results_dir / plot_file.name
        try:
            plot_file.resolve().rename(final_path)
            web_path = (
                f"../../logs/{Path(cfg.workspace_dir).name}/experiment_results/"
                f"experiment_{child_node.id}_proc_{os.getpid()}/{plot_file.name}"
            )
            logger.debug(f"Moving plot: {plot_file.name} -> {final_path}, web_path: {web_path}")
            child_node.plots.append(web_path)
            child_node.plot_paths.append(str(final_path.absolute()))
            logger.debug(f"Moved plot: {plot_file.name} -> {final_path}")
        except Exception as move_error:
            logger.error(f"Failed to move plot {plot_file.name}: {move_error}")
            logger.error("This could cause plots/plot_paths mismatch")
    logger.debug(
        "After moving plots: "
        f"plots={len(child_node.plots)}, plot_paths={len(child_node.plot_paths)}"
    )


def _run_vlm_analysis(
    *,
    worker_agent: MinimalAgent,
    child_node: Node,
    event_callback: Callable[[BaseEvent], None],
) -> None:
    try:
        logger.info(f"→ Analyzing {len(child_node.plots)} plots with Vision Language Model...")
        event_callback(
            RunLogEvent(
                message=f"Analyzing {len(child_node.plots)} generated plots with VLM", level="info"
            )
        )
        analyze_plots_with_vlm(agent=worker_agent, node=child_node)
        logger.info(f"✓ VLM analysis complete. Valid plots: {not child_node.is_buggy_plots}")
        event_callback(RunLogEvent(message="✓ Plot analysis complete", level="info"))
    except Exception as e:
        tb = traceback.format_exc()
        event_callback(
            RunLogEvent(message=f"Plot analysis failed with exception: {str(e)}", level="warn")
        )
        event_callback(RunLogEvent(message=f"Plot analysis traceback:\n{tb}", level="warn"))


def _run_plotting_and_vlm(
    *,
    worker_agent: MinimalAgent,
    child_node: Node,
    parent_node: Node | None,
    cfg: AppConfig,
    working_dir: str,
    process_interpreter: Interpreter,
    seed_eval: bool,
    best_stage3_plot_code: str | None,
    event_callback: Callable[[BaseEvent], None],
) -> None:
    logger.debug(
        f"Starting plotting for node {child_node.id}: "
        f"plots={len(child_node.plots) if child_node.plots else 0}, "
        f"plot_paths={len(child_node.plot_paths) if child_node.plot_paths else 0}"
    )
    try:
        plotting_code = _execute_plotting_with_retries(
            worker_agent=worker_agent,
            child_node=child_node,
            parent_node=parent_node,
            process_interpreter=process_interpreter,
            seed_eval=seed_eval,
            best_stage3_plot_code=best_stage3_plot_code,
            event_callback=event_callback,
        )
        _move_experiment_artifacts(
            cfg=cfg,
            child_node=child_node,
            working_dir=working_dir,
            plotting_code=plotting_code,
            event_callback=event_callback,
        )
    except Exception as e:
        tb = traceback.format_exc()
        event_callback(
            RunLogEvent(message=f"Plotting failed with exception: {str(e)}", level="warn")
        )
        event_callback(RunLogEvent(message=f"Plotting traceback:\n{tb}", level="warn"))
    logger.debug(
        "Before VLM check: "
        f"plots={len(child_node.plots) if child_node.plots else 0}, "
        f"plot_paths={len(child_node.plot_paths) if child_node.plot_paths else 0}"
    )
    if not child_node.plots:
        return
    if not child_node.plot_paths:
        logger.warning(
            f"MISMATCH: child_node.plots has {len(child_node.plots)} items but "
            f"plot_paths is empty for node {child_node.id}"
        )
        logger.warning(
            "This suggests plots were populated but plot_paths wasn't. " "This can happen if:"
        )
        logger.warning("   1. Exception occurred during file moving in the plotting step")
        logger.warning("   2. Plots were populated from a previous attempt/retry")
        logger.warning("   3. plot_paths list was cleared/reset somewhere")
        return
    _run_vlm_analysis(
        worker_agent=worker_agent,
        child_node=child_node,
        event_callback=event_callback,
    )


def parse_and_assign_metrics(
    *,
    worker_agent: MinimalAgent,
    child_node: Node,
    parent_node: Node | None,
    cfg: AppConfig,
    working_dir: str,
    process_interpreter: Interpreter,
    seed_eval: bool,
    event_callback: Callable[[BaseEvent], None],
) -> None:
    """Generate/execute metrics parsing code and assign structured metrics to the node."""
    try:
        working_path = Path(working_dir)
        data_files = list(working_path.glob("*.npy"))
        if not data_files:
            event_callback(
                RunLogEvent(
                    message="No .npy files found in working directory. Data may not have been saved properly.",
                    level="warn",
                )
            )

        # Prepare or reuse metrics parsing code
        if seed_eval and parent_node is not None:
            parse_metrics_plan = parent_node.parse_metrics_plan
            parse_metrics_code = parent_node.parse_metrics_code
        else:
            parse_metrics_prompt: PromptType = {
                "Introduction": (
                    "You are an AI researcher analyzing experimental results stored in numpy files. "
                    "Write code to load and analyze the metrics from experiment_data.npy."
                ),
                "Context": [
                    "Original Code: " + child_node.code,
                ],
                "Instructions": [
                    "0. Make sure to get the working directory from os.path.join(os.getcwd(), 'working')",
                    "1. Load the experiment_data.npy file, which is located in the working directory",
                    "2. Extract metrics for each dataset. Refer to the original code to understand the data structure.",
                    "3. Always print the name of the dataset before printing the metrics",
                    "4. Always print the name of the metric before printing the value with precise labels (e.g., 'train accuracy', 'validation loss', 'test F1 score').",
                    "5. Only print the best or final value for each metric for each dataset",
                    "6. DO NOT CREATE ANY PLOTS",
                    "Important code structure requirements:",
                    "  - Do NOT put any execution code inside if __name__ == '" + "__main__" + "':",
                    "  - All code should be at the global scope or in functions that are called from the global scope",
                    "  - The script should execute immediately when run, without requiring any special entry point",
                ],
                "Example data loading code": [
                    (
                        "\nimport numpy as np\nimport os\n"
                        "experiment_data = np.load(os.path.join(os.getcwd(), 'working', 'experiment_data.npy'), allow_pickle=True).item()\n"
                    )
                ],
            }
            logger.debug(
                "Generating metric parsing code to extract metrics from experiment results"
            )
            parse_metrics_plan, parse_metrics_code = worker_agent.plan_and_code_query(
                prompt=parse_metrics_prompt
            )
        child_node.parse_metrics_plan = parse_metrics_plan
        child_node.parse_metrics_code = parse_metrics_code

        # Execute metric parsing code
        logger.debug(
            "Starting second interpreter: executing metric parsing code to load .npy files and extract metrics"
        )
        metrics_exec_result = process_interpreter.run(code=parse_metrics_code, reset_session=True)
        process_interpreter.cleanup_session()
        child_node.parse_term_out = metrics_exec_result.term_out
        child_node.parse_exc_type = metrics_exec_result.exc_type
        child_node.parse_exc_info = metrics_exec_result.exc_info
        child_node.parse_exc_stack = metrics_exec_result.exc_stack

        if metrics_exec_result.exc_type is None:
            # Extract structured metrics from stdout
            metrics_prompt = {
                "Introduction": (
                    "Parse the metrics from the execution output. You only need the final or best value "
                    "of each metric for each dataset."
                ),
                "Execution Output": metrics_exec_result.term_out,
            }
            metrics_model = structured_query_with_schema(
                system_message=metrics_prompt,
                user_message=None,
                model=cfg.agent.feedback.model,
                temperature=cfg.agent.feedback.temperature,
                schema_class=METRIC_PARSE_SCHEMA,
            )
            metrics_response = metrics_model.model_dump(by_alias=True)
            if metrics_model.valid_metrics_received:
                metric_names = metrics_response.get("metric_names", [])
                child_node.metric = MetricValue(value={"metric_names": metric_names})
                _assign_datasets_from_metrics_response(
                    child_node=child_node,
                    metrics_response=metrics_response,
                )
            else:
                child_node.metric = WorstMetricValue()
                child_node.is_buggy = True
        else:
            child_node.metric = WorstMetricValue()
            child_node.is_buggy = True

        # Emit validation outcome
        if child_node.is_buggy:
            bug_summary = (child_node.analysis or "Unknown error")[:150]
            event_callback(
                RunLogEvent(message=f"Implementation has bugs: {bug_summary}", level="warn")
            )
        else:
            event_callback(RunLogEvent(message="Implementation passed validation", level="info"))
    except Exception:
        # On any unexpected error while parsing metrics, mark as worst
        child_node.metric = WorstMetricValue()
        child_node.is_buggy = True


def process_node(
    *,
    node_data: dict[str, object] | None,
    task_desc: str,
    cfg: AppConfig,
    evaluation_metrics: str,
    memory_summary: str,
    stage_name: str,
    seed_eval: bool,
    event_callback: Callable[[BaseEvent], None],
    gpu_id: Optional[int] = None,
    new_ablation_idea: Optional[AblationIdea] = None,
    new_hyperparam_idea: Optional[HyperparamTuningIdea] = None,
    best_stage3_plot_code: Optional[str] = None,
) -> dict[str, object]:
    _ensure_worker_log_level(cfg=cfg)

    process_id = multiprocessing.current_process().name
    workspace, working_dir = _prepare_workspace(cfg=cfg, process_id=process_id)

    gpu_spec = _configure_gpu_for_worker(gpu_id=gpu_id)

    worker_agent = _create_worker_agent(
        task_desc=task_desc,
        cfg=cfg,
        gpu_id=gpu_id,
        gpu_spec=gpu_spec,
        memory_summary=memory_summary,
        evaluation_metrics=evaluation_metrics,
        stage_name=stage_name,
    )

    process_interpreter = _create_interpreter(cfg=cfg, workspace=workspace)

    try:
        parent_node = _load_parent_node(node_data=node_data)

        child_node = _create_child_node(
            worker_agent=worker_agent,
            parent_node=parent_node,
            seed_eval=seed_eval,
            new_ablation_idea=new_ablation_idea,
            new_hyperparam_idea=new_hyperparam_idea,
            event_callback=event_callback,
        )

        exec_result = _execute_experiment(
            child_node=child_node,
            cfg=cfg,
            process_interpreter=process_interpreter,
            event_callback=event_callback,
        )

        _analyze_results_and_metrics(
            worker_agent=worker_agent,
            child_node=child_node,
            parent_node=parent_node,
            cfg=cfg,
            working_dir=working_dir,
            process_interpreter=process_interpreter,
            seed_eval=seed_eval,
            exec_result=exec_result,
            event_callback=event_callback,
        )

        if not child_node.is_buggy:
            if _should_run_plotting_and_vlm(stage_name=worker_agent.stage_name):
                _run_plotting_and_vlm(
                    worker_agent=worker_agent,
                    child_node=child_node,
                    parent_node=parent_node,
                    cfg=cfg,
                    working_dir=working_dir,
                    process_interpreter=process_interpreter,
                    seed_eval=seed_eval,
                    best_stage3_plot_code=best_stage3_plot_code,
                    event_callback=event_callback,
                )
            elif child_node.is_buggy_plots is None:
                # If plotting/VLM is skipped (e.g., Stage 1), treat plots as non-buggy
                child_node.is_buggy_plots = False

        result_data = child_node.to_dict()
        # sanity pickle

        pickle.dumps(result_data)
        return result_data
    except Exception:

        traceback.print_exc()
        raise
    finally:
        if process_interpreter:
            process_interpreter.cleanup_session()
