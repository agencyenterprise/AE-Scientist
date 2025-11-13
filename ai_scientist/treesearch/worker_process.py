import logging
import multiprocessing
import os
import pickle
import traceback
from pathlib import Path
from typing import Callable, Optional, cast

from ai_scientist.llm.query import query

from .codegen_agent import MinimalAgent
from .interpreter import Interpreter
from .journal import Node
from .plotting import analyze_plots_with_vlm, generate_plotting_code
from .stages.stage1_baseline import Stage1Baseline
from .stages.stage2_tuning import Stage2Tuning
from .stages.stage4_ablation import Stage4Ablation
from .types import PromptType
from .utils.config import Config as AppConfig
from .utils.metric import MetricValue, WorstMetricValue
from .vlm_function_specs import metric_parse_spec

logger = logging.getLogger("ai-scientist")


def parse_and_assign_metrics(
    *,
    worker_agent: MinimalAgent,
    child_node: Node,
    parent_node: Node | None,
    cfg: AppConfig,
    working_dir: str,
    process_interpreter: Interpreter,
    seed_eval: bool,
    emit: Callable[[str, dict[str, object]], None],
) -> None:
    """Generate/execute metrics parsing code and assign structured metrics to the node."""
    try:
        working_path = Path(working_dir)
        data_files = list(working_path.glob("*.npy"))
        if not data_files:
            emit(
                "ai.run.log",
                {
                    "message": "No .npy files found in working directory. Data may not have been saved properly.",
                    "level": "warn",
                },
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
                "Response format": cast(
                    dict[str, str | list[str]], worker_agent._prompt_metricparse_resp_fmt()
                ),
            }
            parse_metrics_plan, parse_metrics_code = worker_agent.plan_and_code_query(
                prompt=parse_metrics_prompt
            )
        child_node.parse_metrics_plan = parse_metrics_plan
        child_node.parse_metrics_code = parse_metrics_code

        # Execute metric parsing code
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
            metrics_response = query(
                system_message=metrics_prompt,
                user_message=None,
                func_spec=metric_parse_spec,
                model=cfg.agent.feedback.model,
                temperature=cfg.agent.feedback.temp,
            )
            if isinstance(metrics_response, dict) and metrics_response.get(
                "valid_metrics_received"
            ):
                child_node.metric = MetricValue(
                    value={"metric_names": metrics_response.get("metric_names", [])}
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
            emit(
                "ai.run.log",
                {"message": f"Implementation has bugs: {bug_summary}", "level": "warn"},
            )
        else:
            emit(
                "ai.run.log",
                {"message": "Implementation passed validation", "level": "info"},
            )
    except Exception:
        # On any unexpected error while parsing metrics, mark as worst
        child_node.metric = WorstMetricValue()
        child_node.is_buggy = True


def process_node(
    *,
    node_data: dict[str, object] | None,
    task_desc: str,
    cfg: AppConfig,
    gpu_id: Optional[int] = None,
    memory_summary: Optional[str] = None,
    evaluation_metrics: str | list[str] | None = None,
    stage_name: Optional[str] = None,
    new_ablation_idea: Optional[object] = None,
    new_hyperparam_idea: Optional[object] = None,
    best_stage3_plot_code: Optional[str] = None,
    best_stage2_plot_code: Optional[str] = None,
    best_stage1_plot_code: Optional[str] = None,
    seed_eval: bool = False,
    event_callback: Optional[Callable[[str, dict[str, object]], None]] = None,
) -> dict[str, object]:
    def emit(event_type: str, data: dict[str, object]) -> None:
        if event_callback:
            try:
                data["stage"] = stage_name
                event_callback(event_type, data)
            except Exception:
                pass

    process_id = multiprocessing.current_process().name
    workspace = os.path.join(cfg.workspace_dir, f"process_{process_id}")
    os.makedirs(workspace, exist_ok=True)
    working_dir = os.path.join(workspace, "working")
    os.makedirs(working_dir, exist_ok=True)

    if gpu_id is not None:
        os.environ["CUDA_VISIBLE_DEVICES"] = str(gpu_id)
    else:
        os.environ["CUDA_VISIBLE_DEVICES"] = ""

    worker_agent = MinimalAgent(
        task_desc=task_desc,
        cfg=cfg,
        memory_summary=memory_summary,
        evaluation_metrics=evaluation_metrics,
        stage_name=stage_name,
    )

    process_interpreter = Interpreter(
        working_dir=workspace,
        timeout=cfg.exec.timeout,
        format_tb_ipython=cfg.exec.format_tb_ipython,
        agent_file_name=cfg.exec.agent_file_name,
    )

    try:
        if node_data:
            parent_node = Node.from_dict(node_data, journal=None)
        else:
            parent_node = None

        if seed_eval:
            assert parent_node is not None, "parent_node must be provided for seed evaluation"
            emit("ai.run.log", {"message": "Running multi-seed evaluation", "level": "info"})
            child_node = worker_agent._generate_seed_node(parent_node)
            child_node.parent = parent_node
            child_node.plot_code = parent_node.plot_code
        else:
            if parent_node is None:
                emit(
                    "ai.run.log", {"message": "Generating new implementation code", "level": "info"}
                )
                child_node = Stage1Baseline.draft(worker_agent)
                emit("ai.run.log", {"message": "Code generation complete", "level": "info"})
            elif parent_node.is_buggy:
                emit(
                    "ai.run.log",
                    {"message": "Debugging failed node (attempt to fix bugs)", "level": "info"},
                )
                child_node = worker_agent._debug(parent_node)
                child_node.parent = parent_node
                emit("ai.run.log", {"message": "Fix attempt generated", "level": "info"})
            else:
                if new_hyperparam_idea is not None and new_ablation_idea is None:
                    logger.info(f"Building hyperparam tuning node {parent_node.id}")
                    child_node = Stage2Tuning.build_hyperparam_tuning_node(agent=worker_agent, parent_node=parent_node, hyperparam_idea=new_hyperparam_idea)  # type: ignore[arg-type]
                    child_node.parent = parent_node
                elif new_ablation_idea is not None and new_hyperparam_idea is None:
                    logger.info(f"Building ablation node {parent_node.id}")
                    child_node = Stage4Ablation.build_ablation_node(agent=worker_agent, parent_node=parent_node, ablation_idea=new_ablation_idea)  # type: ignore[arg-type]
                    child_node.parent = parent_node
                else:
                    logger.info(f"Improving node {parent_node.id}")
                    child_node = Stage1Baseline.improve(agent=worker_agent, parent_node=parent_node)
                    child_node.parent = parent_node

        print(
            f"[bold blue]→ Executing experiment code (timeout: {cfg.exec.timeout}s)...[/bold blue]"
        )
        emit("ai.run.log", {"message": "Executing experiment code on GPU...", "level": "info"})
        exec_result = process_interpreter.run(child_node.code, True)
        process_interpreter.cleanup_session()
        print(
            f"[bold green]✓ Code execution completed in {exec_result.exec_time:.1f}s[/bold green]"
        )
        emit(
            "ai.run.log",
            {
                "message": f"Code execution completed ({exec_result.exec_time:.1f}s)",
                "level": "info",
            },
        )

        print("[bold blue]→ Analyzing results and extracting metrics...[/bold blue]")
        emit("ai.run.log", {"message": "Analyzing results and extracting metrics", "level": "info"})
        worker_agent.parse_exec_result(
            node=child_node, exec_result=exec_result, workspace=working_dir
        )
        parse_and_assign_metrics(
            worker_agent=worker_agent,
            child_node=child_node,
            parent_node=parent_node,
            cfg=cfg,
            working_dir=working_dir,
            process_interpreter=process_interpreter,
            seed_eval=seed_eval,
            emit=emit,
        )
        print(f"[bold green]✓ Metrics extracted. Buggy: {child_node.is_buggy}[/bold green]")

        if not child_node.is_buggy:
            print(
                f"[DEBUG] Starting plotting for node {child_node.id}: plots={len(child_node.plots) if child_node.plots else 0}, plot_paths={len(child_node.plot_paths) if child_node.plot_paths else 0}"
            )
            try:
                print("[bold blue]→ Generating visualization plots...[/bold blue]")
                emit("ai.run.log", {"message": "Generating visualization plots", "level": "info"})
                retry_count = 0
                while True:
                    if seed_eval:
                        assert parent_node is not None
                        plotting_code = parent_node.plot_code or ""
                    else:
                        if (
                            worker_agent.stage_name
                            and worker_agent.stage_name.startswith("3_")
                            and best_stage2_plot_code
                        ):
                            plot_code_from_prev_stage = best_stage2_plot_code
                        elif (
                            worker_agent.stage_name
                            and worker_agent.stage_name.startswith("4_")
                            and best_stage3_plot_code
                        ):
                            plot_code_from_prev_stage = best_stage3_plot_code
                        else:
                            plot_code_from_prev_stage = None

                        plotting_code = generate_plotting_code(
                            agent=worker_agent,
                            node=child_node,
                            working_dir=working_dir,
                            plot_code_from_prev_stage=plot_code_from_prev_stage,
                        )
                    emit("ai.run.log", {"message": "Executing plotting code", "level": "info"})
                    plot_exec_result = process_interpreter.run(plotting_code, True)
                    process_interpreter.cleanup_session()
                    child_node.absorb_plot_exec_result(plot_exec_result)
                    if child_node.plot_exc_type and retry_count < 3:
                        # Emit details to help diagnose plotting failures
                        term_lines = child_node.plot_term_out or []
                        tail = (
                            "".join(term_lines[-50:])
                            if isinstance(term_lines, list)
                            else str(term_lines)
                        )
                        emit(
                            "ai.run.log",
                            {
                                "message": f"Plotting error ({child_node.plot_exc_type}); retrying {retry_count + 1}/3. Tail of output:\\n{tail}",
                                "level": "warn",
                            },
                        )
                        retry_count += 1
                        continue
                    else:
                        break

                plots_dir = Path(working_dir)
                print(f"[DEBUG] Checking plots_dir: {plots_dir}, exists={plots_dir.exists()}")
                if plots_dir.exists():
                    plot_count = len(list(plots_dir.glob("*.png")))
                    print(f"[DEBUG] Found {plot_count} plot files in working directory")
                    if plot_count > 0:
                        emit(
                            "ai.run.log",
                            {"message": f"✓ Generated {plot_count} plot file(s)", "level": "info"},
                        )
                    else:
                        emit(
                            "ai.run.log",
                            {
                                "message": "No plot files (*.png) found in working directory after plotting",
                                "level": "warn",
                            },
                        )
                        print(
                            f"[WARN] No plot files found in {plots_dir} after plotting code execution"
                        )

                    base_dir = Path(cfg.workspace_dir).parent
                    run_name = Path(cfg.workspace_dir).name
                    exp_results_dir = (
                        base_dir
                        / "logs"
                        / run_name
                        / "experiment_results"
                        / f"experiment_{child_node.id}_proc_{os.getpid()}"
                    )
                    print(f"[DEBUG] Creating exp_results_dir: {exp_results_dir}")
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
                    print(
                        f"[DEBUG] Found {len(plot_files_found)} plot files to move for node {child_node.id}"
                    )
                    print(
                        f"[DEBUG] Before moving: plots={len(child_node.plots) if child_node.plots else 0}, plot_paths={len(child_node.plot_paths) if child_node.plot_paths else 0}"
                    )
                    if len(plot_files_found) == 0:
                        print(
                            "[WARN] No plot files to move! This means plots were generated but not found, or already moved."
                        )
                        print(f"[WARN] Current plots list: {child_node.plots}")
                        print(f"[WARN] Current plot_paths list: {child_node.plot_paths}")
                    for plot_file in plot_files_found:
                        final_path = exp_results_dir / plot_file.name
                        try:
                            plot_file.resolve().rename(final_path)
                            web_path = f"../../logs/{Path(cfg.workspace_dir).name}/experiment_results/experiment_{child_node.id}_proc_{os.getpid()}/{plot_file.name}"
                            print(
                                f"[DEBUG] Moving plot: {plot_file.name} -> {final_path}, web_path: {web_path}"
                            )
                            child_node.plots.append(web_path)
                            child_node.plot_paths.append(str(final_path.absolute()))
                            print(f"[DEBUG] Moved plot: {plot_file.name} -> {final_path}")
                        except Exception as move_error:
                            print(f"[ERROR] Failed to move plot {plot_file.name}: {move_error}")
                            print("[ERROR] This could cause plots/plot_paths mismatch")
                    print(
                        f"[DEBUG] After moving plots: plots={len(child_node.plots)}, plot_paths={len(child_node.plot_paths)}"
                    )
                else:
                    print(f"[WARN] plots_dir {plots_dir} does not exist!")
            except Exception as e:
                tb = traceback.format_exc()
                emit(
                    "ai.run.log",
                    {"message": f"Plotting failed with exception: {str(e)}", "level": "warn"},
                )
                emit(
                    "ai.run.log",
                    {"message": f"Plotting traceback:\\n{tb}", "level": "warn"},
                )

            print(
                f"[DEBUG] Before VLM check: plots={len(child_node.plots) if child_node.plots else 0}, plot_paths={len(child_node.plot_paths) if child_node.plot_paths else 0}"
            )
            if child_node.plots:
                if not child_node.plot_paths:
                    print(
                        f"[WARN] MISMATCH: child_node.plots has {len(child_node.plots)} items but plot_paths is empty for node {child_node.id}"
                    )
                    print(
                        "[WARN] This suggests plots were populated but plot_paths wasn't. This can happen if:"
                    )
                    print("[WARN]   1. Exception occurred during file moving (lines 366-371)")
                    print("[WARN]   2. Plots were populated from a previous attempt/retry")
                    print("[WARN]   3. plot_paths list was cleared/reset somewhere")
                try:
                    print(
                        f"[bold blue]→ Analyzing {len(child_node.plots)} plots with Vision Language Model...[/bold blue]"
                    )
                    emit(
                        "ai.run.log",
                        {
                            "message": f"Analyzing {len(child_node.plots)} generated plots with VLM",
                            "level": "info",
                        },
                    )
                    analyze_plots_with_vlm(agent=worker_agent, node=child_node)
                    print(
                        f"[bold green]✓ VLM analysis complete. Valid plots: {not child_node.is_buggy_plots}[/bold green]"
                    )
                    emit("ai.run.log", {"message": "✓ Plot analysis complete", "level": "info"})
                except Exception as e:
                    tb = traceback.format_exc()
                    emit(
                        "ai.run.log",
                        {
                            "message": f"Plot analysis failed with exception: {str(e)}",
                            "level": "warn",
                        },
                    )
                    emit(
                        "ai.run.log",
                        {"message": f"Plot analysis traceback:\\n{tb}", "level": "warn"},
                    )

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
