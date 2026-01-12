import json
import logging
import multiprocessing
import os
import pickle
import traceback
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Callable, Literal, TypedDict

from ai_scientist.llm import structured_query_with_schema

from . import execution_registry
from .codex.codex_cli_runner import CodexCliRunner
from .codex.codex_env import build_codex_env, ensure_codex_venv
from .codex.codex_task_types import (
    CodexTaskContext,
    EvaluationMetricSpec,
    ParentNodeSummary,
    SeedAggregationPayload,
    StageIdea,
)
from .codex.node_result_contract import (
    NodeResultContractContext,
    codex_node_result_contract_prompt_lines_common,
    count_working_pngs,
)
from .codex.seed_aggregation import (
    codex_node_result_contract_prompt_lines as codex_seed_agg_contract_lines,
)
from .codex.seed_aggregation import codex_seed_aggregation_instructions_lines
from .config import Config as AppConfig
from .config import TaskDescription, apply_log_level
from .events import BaseEvent, RunCompletedEvent, RunLogEvent, RunningCodeEvent
from .gpu_manager import GPUSpec, get_gpu_specs
from .journal import Node
from .prompts.codex_task.codex_task_template import (
    CodexTaskMarkdownRenderContext,
    render_codex_task_markdown,
)
from .prompts.environment_context import build_environment_context
from .stage_identifiers import StageIdentifier
from .stages.node_result_contracts import (
    codex_node_result_contract_prompt_lines_for_stage,
    validate_node_result_contract_for_stage,
)
from .utils.metric import WorstMetricValue
from .utils.response import trim_long_string, wrap_code
from .vlm_feedback import generate_vlm_feedback
from .vlm_function_specs import REVIEW_RESPONSE_SCHEMA, TrainingReview

logger = logging.getLogger("ai-scientist")
RESEARCH_PIPELINE_ROOT = Path(__file__).resolve().parents[2]


def _parent_node_summary_for_task_context(*, parent_node: Node) -> ParentNodeSummary:
    """
    A minimal parent-node payload for the JSON context embedded in codex_task.md.

    We intentionally exclude large fields (notably `code`) to keep the prompt size bounded; the
    parent code is embedded separately as a python code block in the markdown context.
    """
    parent_id = parent_node.parent.id if parent_node.parent is not None else None

    metric = (
        None
        if parent_node.metric is None
        else {
            "value": parent_node.metric.value,
            "maximize": parent_node.metric.maximize,
            "name": parent_node.metric.name,
            "description": parent_node.metric.description,
        }
    )

    exp_results_dir: str | None
    if parent_node.exp_results_dir is None:
        exp_results_dir = None
    else:
        try:
            exp_results_dir = str(
                Path(parent_node.exp_results_dir).resolve().relative_to(Path.cwd())
            )
        except Exception:
            exp_results_dir = str(Path(parent_node.exp_results_dir).resolve())

    plot_analyses: list[dict[str, Any]] = []
    for analysis in parent_node.plot_analyses:
        plot_path = analysis.get("plot_path")
        if isinstance(plot_path, str) and plot_path.strip():
            try:
                rel_plot_path = str(Path(plot_path).resolve().relative_to(Path.cwd()))
            except Exception:
                rel_plot_path = str(Path(plot_path).resolve())
            plot_analyses.append({**analysis, "plot_path": rel_plot_path})
        else:
            plot_analyses.append(dict(analysis))

    return ParentNodeSummary(
        id=parent_node.id,
        step=parent_node.step,
        parent_id=parent_id,
        plan=parent_node.plan,
        overall_plan=parent_node.overall_plan,
        analysis=parent_node.analysis,
        metric=metric,
        is_buggy=parent_node.is_buggy,
        is_buggy_plots=parent_node.is_buggy_plots,
        exc_type=parent_node.exc_type,
        exec_time=parent_node.exec_time,
        exec_time_feedback=parent_node.exec_time_feedback,
        exp_results_dir=exp_results_dir,
        plot_analyses=plot_analyses,
        vlm_feedback_summary=str(parent_node.vlm_feedback_summary or "").strip(),
        datasets_successfully_tested=list(parent_node.datasets_successfully_tested),
        hyperparam_name=parent_node.hyperparam_name,
        ablation_name=parent_node.ablation_name,
        is_seed_node=parent_node.is_seed_node,
        is_seed_agg_node=parent_node.is_seed_agg_node,
    )


def _summarize_execution_with_llm(
    *,
    cfg: AppConfig,
    task_desc: TaskDescription,
    stage_goals: str,
    stage_identifier: StageIdentifier,
    term_out: str,
    exc_type: str | None,
    exec_time: float,
) -> TrainingReview | None:
    prompt = {
        "Introduction": (
            "Analyze the execution output, determine if there were any bugs, and provide a summary of the findings. "
            "If there is a bug, summarize the failure and propose a concrete fix direction."
        ),
        "Research idea": task_desc.model_dump(by_alias=True),
        "Stage": stage_identifier.name,
        "Stage goals": stage_goals,
        "Execution output": wrap_code(term_out, lang=""),
        "Exception type": str(exc_type or ""),
        "Execution time (seconds)": exec_time,
    }
    try:
        response = structured_query_with_schema(
            system_message=prompt,
            user_message=None,
            model=cfg.agent.feedback.model,
            temperature=cfg.agent.feedback.temperature,
            schema_class=REVIEW_RESPONSE_SCHEMA,
        )
    except Exception:  # noqa: BLE001
        logger.exception("Failed to summarize execution output via LLM.")
        return None
    return response


def _attach_parent(*, child_node: Node, parent_node: Node) -> None:
    # We intentionally attach relationships here so that `Node.to_dict()` emits `parent_id`,
    # which `Node.from_dict(..., journal=...)` uses to reconstruct the tree in the main process.
    child_node.parent = parent_node


class NodeTask(TypedDict):
    node_data: dict[str, object] | None
    task_desc: TaskDescription
    stage_goals: str
    evaluation_metric_spec: EvaluationMetricSpec
    cfg: AppConfig
    memory_summary: str
    stage_identifier: StageIdentifier
    seed_eval: bool
    seed_value: int
    seed_aggregation: SeedAggregationPayload | None
    stage2_hyperparam_idea: StageIdea | None
    stage4_ablation_idea: StageIdea | None
    event_callback: Callable[[BaseEvent], None]
    gpu_id: int | None
    execution_id: str
    user_feedback_payload: str


class ExecutionTerminatedError(RuntimeError):
    """Raised when the execution was intentionally terminated via user action."""

    def __init__(self, execution_id: str, *, exec_time: float | None) -> None:
        super().__init__(f"Execution {execution_id} terminated intentionally")
        self.execution_id = execution_id
        self.exec_time = exec_time


class ExecutionCrashedError(RuntimeError):
    """Raised when the Codex process died unexpectedly."""

    def __init__(self, execution_id: str, *, exec_time: float | None) -> None:
        super().__init__(f"Execution {execution_id} crashed unexpectedly")
        self.execution_id = execution_id
        self.exec_time = exec_time


def _ensure_worker_log_level(*, cfg: AppConfig) -> None:
    try:
        apply_log_level(level_name=cfg.log_level)
    except (ValueError, TypeError):
        pass


def _prepare_workspace(
    *,
    cfg: AppConfig,
    stage_name: str,
    task_desc: TaskDescription,
) -> tuple[Path, Path]:
    ts = datetime.now(tz=timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    run_workspace_dir = Path(cfg.workspace_dir)
    exec_root_dir = run_workspace_dir / "executions"
    exec_root_dir.mkdir(parents=True, exist_ok=True)

    base_name = f"{stage_name}_{ts}_{os.getpid()}"
    workspace_path = exec_root_dir / base_name
    for suffix in range(1000):
        candidate = workspace_path if suffix == 0 else exec_root_dir / f"{base_name}_{suffix}"
        try:
            candidate.mkdir(parents=True, exist_ok=False)
        except FileExistsError:
            continue
        workspace_path = candidate
        break
    else:
        raise RuntimeError(f"Failed to create unique execution workspace dir under {exec_root_dir}")

    working_dir_path = workspace_path / "working"
    working_dir_path.mkdir(parents=True, exist_ok=True)

    example_code = task_desc.code
    if example_code is None or not str(example_code).strip():
        example_code_path = Path(__file__).resolve().parents[1] / "example_code.py"
        example_code = example_code_path.read_text(encoding="utf-8")
    try:
        (workspace_path / "example_code.py").write_text(str(example_code), encoding="utf-8")
    except OSError:
        logger.debug(
            "Failed writing example_code.py into worker workspace (dst=%s)",
            workspace_path / "example_code.py",
            exc_info=True,
        )

    return workspace_path, working_dir_path


def _configure_gpu_for_worker(*, gpu_id: int | None) -> GPUSpec | None:
    if gpu_id is None:
        os.environ["CUDA_VISIBLE_DEVICES"] = ""
        return None
    os.environ["CUDA_VISIBLE_DEVICES"] = str(gpu_id)
    return get_gpu_specs(gpu_id)


def _load_parent_node(*, node_data: dict[str, object] | None) -> Node | None:
    if node_data is None:
        return None
    return Node.from_dict(node_data, journal=None)


def _abort_if_skip_requested(*, execution_id: str) -> None:
    skip_pending, reason = execution_registry.is_skip_pending(execution_id)
    if skip_pending:
        logger.info(
            "Skip pending for execution_id=%s (reason=%s); aborting before Codex run.",
            execution_id,
            reason,
        )
        raise ExecutionTerminatedError(execution_id=execution_id, exec_time=0.0)


def _write_codex_task_file(
    *,
    workspace_dir: Path,
    execution_id: str,
    stage_identifier: StageIdentifier,
    stage_name: str,
    timeout_seconds: int,
    agent_file_name: str,
    output_json_file: Path,
    venv_dir: Path,
    cfg: AppConfig,
    task_context: CodexTaskContext,
    environment_context: dict[str, object],
    parent_node: Node | None,
) -> Path:
    task_path = workspace_dir / "codex_task.md"
    env_ctx_dict = environment_context
    memory_summary = str(task_context.memory_summary or "").strip()
    base_code = ""
    exec_time_feedback = ""
    parent_term_out = ""
    parent_analysis = ""
    parent_exc_type = ""
    parent_vlm_feedback_summary = ""
    user_feedback_payload = str(task_context.user_feedback_payload or "").strip()
    if parent_node is not None:
        base_code = str(parent_node.code or "")
        exec_time_feedback = str(parent_node.exec_time_feedback or "")
        parent_analysis = str(parent_node.analysis or "").strip()
        parent_exc_type = str(parent_node.exc_type or "").strip()
        raw_term_out = parent_node._term_out
        if isinstance(raw_term_out, list):
            parent_term_out = trim_long_string("".join([str(x) for x in raw_term_out]))
        parent_vlm_feedback_summary = str(parent_node.vlm_feedback_summary or "").strip()

    is_seed_aggregation = task_context.seed_aggregation is not None
    if is_seed_aggregation:
        # Override stage contract for seed-aggregation runs: keep common contract + add explicit
        # aggregation requirements (including is_seed_agg_node=true).
        contract_lines = (
            codex_node_result_contract_prompt_lines_common() + codex_seed_agg_contract_lines()
        )
        seed_agg_instructions = "\n".join(codex_seed_aggregation_instructions_lines()).strip()
        seed_agg_block = seed_agg_instructions + "\n\n"
    else:
        contract_lines = codex_node_result_contract_prompt_lines_for_stage(
            stage_identifier=stage_identifier
        )
        seed_agg_block = ""
    contract_block = "\n".join(contract_lines).strip() + "\n\n"
    assigned_hyperparam_name = ""
    assigned_hyperparam_description = ""
    assigned_hyperparam_tried_names = ""
    if stage_identifier is StageIdentifier.STAGE2:
        if task_context.stage2_hyperparam_idea is not None:
            assigned_hyperparam_name = str(task_context.stage2_hyperparam_idea.name or "").strip()
            assigned_hyperparam_description = str(
                task_context.stage2_hyperparam_idea.description or ""
            ).strip()
            tried_names = [
                str(x) for x in task_context.stage2_hyperparam_idea.tried_names if str(x).strip()
            ]
            assigned_hyperparam_tried_names = ", ".join(tried_names[:50])

    assigned_ablation_name = ""
    assigned_ablation_description = ""
    assigned_ablation_tried_names = ""
    if stage_identifier is StageIdentifier.STAGE4:
        if task_context.stage4_ablation_idea is not None:
            assigned_ablation_name = str(task_context.stage4_ablation_idea.name or "").strip()
            assigned_ablation_description = str(
                task_context.stage4_ablation_idea.description or ""
            ).strip()
            tried_names = [
                str(x) for x in task_context.stage4_ablation_idea.tried_names if str(x).strip()
            ]
            assigned_ablation_tried_names = ", ".join(tried_names[:50])

    show_plotting_guidelines = stage_identifier in (StageIdentifier.STAGE3, StageIdentifier.STAGE4)
    experiment_code_hint = (
        "Use the final experiment code you wrote in the agent file to infer what data exists in experiment_data.npy."
        if not base_code
        else base_code
    )

    ctx = CodexTaskMarkdownRenderContext(
        execution_id=execution_id,
        stage_identifier_name=stage_identifier.name,
        stage_name=stage_name,
        timeout_seconds=timeout_seconds,
        task_desc=task_context.task_desc,
        stage_goals=task_context.stage_goals,
        memory_summary=memory_summary,
        venv_dir=str(venv_dir),
        environment_context=env_ctx_dict,
        num_syn_datasets=int(cfg.experiment.num_syn_datasets),
        evaluation_metric_json=json.dumps(
            task_context.evaluation_metric_spec.to_json_dict(), indent=2
        ),
        assigned_hyperparam_name=assigned_hyperparam_name,
        assigned_hyperparam_description=assigned_hyperparam_description,
        assigned_hyperparam_tried_names=assigned_hyperparam_tried_names,
        assigned_ablation_name=assigned_ablation_name,
        assigned_ablation_description=assigned_ablation_description,
        assigned_ablation_tried_names=assigned_ablation_tried_names,
        base_code=base_code.rstrip(),
        parent_term_out=parent_term_out.strip(),
        parent_exc_type=parent_exc_type.strip(),
        parent_analysis=parent_analysis.strip(),
        parent_vlm_feedback_summary=parent_vlm_feedback_summary.strip(),
        exec_time_feedback=exec_time_feedback.strip(),
        user_feedback_payload=user_feedback_payload.strip(),
        show_plotting_guidelines=show_plotting_guidelines,
        experiment_code_hint=experiment_code_hint,
        seed_agg_block=seed_agg_block,
        contract_block=contract_block,
        output_json_name=output_json_file.name,
        agent_file_name=agent_file_name,
    )
    task_markdown = render_codex_task_markdown(ctx=ctx)
    task_path.write_text(task_markdown, encoding="utf-8")
    return task_path


def _load_node_result(*, output_json_file: Path) -> dict[str, object] | None:
    if not output_json_file.exists():
        return None
    try:
        parsed = json.loads(output_json_file.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        logger.debug("Failed reading node_result.json at %s", output_json_file, exc_info=True)
        return None
    if not isinstance(parsed, dict):
        return None
    return parsed


def _move_experiment_artifacts(
    *,
    cfg: AppConfig,
    child_node: Node,
    working_dir: Path,
    event_callback: Callable[[BaseEvent], None],
) -> None:
    if not working_dir.exists():
        return
    base_dir = Path(cfg.workspace_dir).parent
    run_name = Path(cfg.workspace_dir).name
    exp_results_dir = (
        base_dir
        / "logs"
        / run_name
        / "experiment_results"
        / f"experiment_{child_node.id}_proc_{os.getpid()}"
    )
    child_node.exp_results_dir = str(exp_results_dir)
    exp_results_dir.mkdir(parents=True, exist_ok=True)
    logger.debug(
        "artifacts.begin node=%s working_dir=%s exp_results_dir=%s",
        child_node.id[:8],
        working_dir,
        exp_results_dir,
    )

    workspace_dir = working_dir.parent
    for fname in (
        "codex_task.md",
        "codex_session.log",
        "codex_events.jsonl",
        "node_result.json",
    ):
        src = workspace_dir / fname
        if not src.exists():
            continue
        dst = exp_results_dir / fname
        try:
            dst.write_bytes(src.read_bytes())
        except OSError:
            logger.debug("artifacts.copy_failed src=%s dst=%s", src, dst, exc_info=True)
        else:
            logger.debug("artifacts.copied src=%s dst=%s bytes=%s", src, dst, dst.stat().st_size)

    summary_path = working_dir / "summary.json"
    if summary_path.exists():
        try:
            summary_text = summary_path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            logger.debug(
                "artifacts.summary_json read_failed path=%s",
                summary_path,
                exc_info=True,
            )
        else:
            logger.debug(
                "artifacts.summary_json captured path=%s chars=%s preview=\n%s",
                summary_path,
                len(summary_text),
                trim_long_string(string=summary_text, threshold=2000, k=700),
            )

    code_src = (working_dir.parent / cfg.exec.agent_file_name).resolve()
    if code_src.exists():
        code_text = code_src.read_text(encoding="utf-8")
        (exp_results_dir / "experiment_code.py").write_text(code_text, encoding="utf-8")
        logger.debug(
            "artifacts.experiment_code captured path=%s chars=%s preview=\n%s",
            exp_results_dir / "experiment_code.py",
            len(code_text),
            trim_long_string(string=code_text, threshold=2400, k=800),
        )

    npy_files = list(working_dir.glob("*.npy"))
    if npy_files:
        logger.debug(
            "artifacts.npy_files count=%s names=%s",
            len(npy_files),
            [p.name for p in npy_files],
        )
    for exp_data_file in npy_files:
        exp_data_path = exp_results_dir / exp_data_file.name
        exp_data_file.resolve().rename(exp_data_path)

    plot_files_found = list(working_dir.glob("*.png"))
    if plot_files_found:
        event_callback(
            RunLogEvent(message=f"✓ Generated {len(plot_files_found)} plot file(s)", level="info")
        )
        logger.debug(
            "artifacts.png_files count=%s names=%s",
            len(plot_files_found),
            [p.name for p in plot_files_found],
        )
    for plot_file in plot_files_found:
        final_path = exp_results_dir / plot_file.name
        plot_file.resolve().rename(final_path)
        web_path = (
            f"../../logs/{Path(cfg.workspace_dir).name}/experiment_results/"
            f"experiment_{child_node.id}_proc_{os.getpid()}/{plot_file.name}"
        )
        child_node.plots.append(web_path)
        child_node.plot_paths.append(str(final_path.absolute()))
    logger.debug(
        "artifacts.done node=%s exp_results_dir=%s plots=%s npy_files=%s",
        child_node.id[:8],
        exp_results_dir,
        len(child_node.plots),
        len(npy_files),
    )


def process_node(
    *,
    node_data: dict[str, object] | None,
    task_desc: TaskDescription,
    stage_goals: str,
    evaluation_metric_spec: EvaluationMetricSpec,
    cfg: AppConfig,
    memory_summary: str,
    stage_identifier: StageIdentifier,
    seed_eval: bool,
    seed_value: int,
    seed_aggregation: SeedAggregationPayload | None,
    stage2_hyperparam_idea: StageIdea | None,
    stage4_ablation_idea: StageIdea | None,
    event_callback: Callable[[BaseEvent], None],
    gpu_id: int | None,
    execution_id: str,
    user_feedback_payload: str,
) -> dict[str, object]:
    _ensure_worker_log_level(cfg=cfg)
    process_id = multiprocessing.current_process().name
    stage_name = stage_identifier.prefixed_name
    workspace_dir, working_dir = _prepare_workspace(
        cfg=cfg,
        stage_name=stage_name,
        task_desc=task_desc,
    )
    gpu_spec = _configure_gpu_for_worker(gpu_id=gpu_id)
    venv_dir = ensure_codex_venv(
        workspace_dir=workspace_dir,
        research_pipeline_root=RESEARCH_PIPELINE_ROOT,
    )
    codex_env = build_codex_env(venv_dir=venv_dir)

    parent_node = _load_parent_node(node_data=node_data)
    logger.debug(
        "worker.begin execution_id=%s process_id=%s stage=%s seed_eval=%s seed_value=%s gpu_id=%s parent=%s workspace_dir=%s working_dir=%s",
        execution_id[:8],
        process_id,
        stage_name,
        seed_eval,
        seed_value,
        gpu_id,
        None if parent_node is None else parent_node.id[:8],
        workspace_dir,
        working_dir,
    )
    if seed_aggregation is not None:
        logger.debug(
            "worker.seed_aggregation enabled execution_id=%s seed_nodes=%s",
            execution_id[:8],
            len(seed_aggregation.seed_nodes),
        )
    if user_feedback_payload.strip():
        logger.debug(
            "worker.user_feedback provided execution_id=%s payload_preview=%s",
            execution_id[:8],
            user_feedback_payload[:200].replace("\n", " "),
        )

    _abort_if_skip_requested(execution_id=execution_id)

    output_json_file = workspace_dir / "node_result.json"
    env_ctx = build_environment_context(gpu_id=gpu_id, gpu_spec=gpu_spec)
    parent_node_summary = (
        _parent_node_summary_for_task_context(parent_node=parent_node)
        if parent_node is not None
        else None
    )
    task_context = CodexTaskContext(
        execution_id=execution_id,
        stage_identifier=stage_identifier.name,
        seed_eval=seed_eval,
        seed_value=seed_value,
        seed_aggregation=seed_aggregation,
        stage2_hyperparam_idea=stage2_hyperparam_idea,
        stage4_ablation_idea=stage4_ablation_idea,
        gpu_id=gpu_id,
        agent_file_name=cfg.exec.agent_file_name,
        timeout_seconds=cfg.exec.timeout,
        parent_node=parent_node_summary,
        user_feedback_payload=user_feedback_payload,
        task_desc=task_desc,
        stage_goals=stage_goals,
        evaluation_metric_spec=evaluation_metric_spec,
        memory_summary=memory_summary,
    )
    logger.debug(
        "codex.task_context_built execution_id=%s stage=%s metric_name=%s seed_eval=%s seed_value=%s",
        execution_id[:8],
        stage_name,
        str(evaluation_metric_spec.name or ""),
        seed_eval,
        seed_value,
    )
    task_file = _write_codex_task_file(
        workspace_dir=workspace_dir,
        execution_id=execution_id,
        stage_identifier=stage_identifier,
        stage_name=stage_name,
        timeout_seconds=cfg.exec.timeout,
        agent_file_name=cfg.exec.agent_file_name,
        output_json_file=output_json_file,
        venv_dir=venv_dir,
        cfg=cfg,
        task_context=task_context,
        environment_context=env_ctx,
        parent_node=parent_node,
    )
    logger.debug(
        "codex.task.written execution_id=%s path=%s chars=%s",
        execution_id[:8],
        task_file,
        len(task_file.read_text(encoding="utf-8", errors="replace")),
    )
    try:
        codex_task_text = task_file.read_text(encoding="utf-8", errors="replace")
    except OSError:
        logger.debug(
            "codex.task.read_failed execution_id=%s path=%s",
            execution_id[:8],
            task_file,
            exc_info=True,
        )
    else:
        logger.debug(
            "codex.task.contents execution_id=%s path=%s chars=%s\n%s",
            execution_id[:8],
            task_file,
            len(codex_task_text),
            codex_task_text,
        )

    runner = CodexCliRunner(
        workspace_dir=workspace_dir,
        timeout_seconds=cfg.exec.timeout,
        argv=[
            "codex",
            "exec",
            "--yolo",
            "--skip-git-repo-check",
            "--json",
        ],
        env=codex_env,
    )

    started_at = datetime.now(timezone.utc)
    event_callback(RunLogEvent(message="Executing via Codex CLI...", level="info"))
    event_callback(
        RunningCodeEvent(
            execution_id=execution_id,
            stage_name=stage_name,
            code="(Codex-managed)",
            started_at=started_at,
        )
    )

    def _pid_tracker(pid: int) -> None:
        execution_registry.update_pid(execution_id=execution_id, pid=pid)

    def _termination_checker() -> bool:
        return execution_registry.is_terminated(execution_id=execution_id)

    term_out, exec_time, exc_type, exc_info = runner.run(
        task_file=task_file,
        pid_callback=_pid_tracker,
        termination_checker=_termination_checker,
        success_file=output_json_file,
        stream_callback=lambda msg: event_callback(RunLogEvent(message=msg, level="info")),
    )
    logger.debug(
        "codex.run.completed execution_id=%s status=%s exec_time_s=%s exc_type=%s exc_info=%s workspace_dir=%s session_log=%s events_jsonl=%s",
        execution_id[:8],
        "success" if exc_type is None else "failed",
        exec_time,
        exc_type,
        exc_info,
        workspace_dir,
        workspace_dir / "codex_session.log",
        workspace_dir / "codex_events.jsonl",
    )

    completed_at = datetime.now(timezone.utc)
    status: Literal["success", "failed"] = "success" if exc_type is None else "failed"
    event_callback(
        RunCompletedEvent(
            execution_id=execution_id,
            stage_name=stage_name,
            status=status,
            exec_time=exec_time,
            completed_at=completed_at,
        )
    )
    if exc_type is None:
        execution_registry.mark_completed(execution_id=execution_id)
    else:
        execution_registry.clear_pid(execution_id=execution_id)

    node_result = _load_node_result(output_json_file=output_json_file)
    if node_result is None:
        logger.debug(
            "codex.output.missing_node_result execution_id=%s expected_path=%s",
            execution_id[:8],
            output_json_file,
        )
        child_node = Node(
            id=execution_id,
            plan="",
            code="",
            is_buggy=True,
            analysis="Codex did not produce a valid node_result.json.",
            exc_type=exc_type or "CodexError",
            exec_time=exec_time,
        )
        child_node.absorb_exec_result(
            SimpleNamespace(
                term_out=term_out,
                exec_time=exec_time,
                exc_type=exc_type,
                exc_info=exc_info,
                exc_stack=None,
            )
        )
        child_node.exc_info = exc_info or {}
        child_node.metric = WorstMetricValue()
        if parent_node is not None:
            _attach_parent(child_node=child_node, parent_node=parent_node)
        _move_experiment_artifacts(
            cfg=cfg,
            child_node=child_node,
            working_dir=working_dir,
            event_callback=event_callback,
        )
        result_data = child_node.to_dict()
        pickle.dumps(result_data)
        return result_data

    node_result["id"] = execution_id
    node_result["parent_id"] = None if parent_node is None else parent_node.id
    logger.debug(
        "codex.output.node_result_loaded execution_id=%s keys=%s plan_preview=%s",
        execution_id[:8],
        sorted(list(node_result.keys()))[:40],
        str(node_result.get("plan") or "")[:200].replace("\n", " "),
    )

    contract_ctx = NodeResultContractContext(
        stage_identifier=stage_identifier,
        is_seed_aggregation=seed_aggregation is not None,
        seed_eval=seed_eval,
        seed_value=seed_value,
        working_png_count=count_working_pngs(working_dir=working_dir),
        expected_hyperparam_name=(
            stage2_hyperparam_idea.name
            if stage_identifier is StageIdentifier.STAGE2 and stage2_hyperparam_idea is not None
            else None
        ),
        expected_ablation_name=(
            stage4_ablation_idea.name
            if stage_identifier is StageIdentifier.STAGE4 and stage4_ablation_idea is not None
            else None
        ),
    )
    contract_errors = validate_node_result_contract_for_stage(
        node_result=node_result,
        ctx=contract_ctx,
    )
    if contract_errors:
        logger.debug(
            "codex.output.contract_failed execution_id=%s errors_count=%s errors=%s",
            execution_id[:8],
            len(contract_errors),
            contract_errors,
        )
        child_node = Node(
            id=execution_id,
            plan=str(node_result.get("plan") or ""),
            code=str(node_result.get("code") or ""),
            is_buggy=True,
            is_buggy_plots=True,
            analysis=(
                "Codex node_result contract violation(s):\n- " + "\n- ".join(contract_errors)
            ),
            exc_type=exc_type or "CodexContractError",
            exec_time=exec_time,
        )
        child_node.metric = WorstMetricValue()
        if parent_node is not None:
            _attach_parent(child_node=child_node, parent_node=parent_node)
        child_node.absorb_exec_result(
            SimpleNamespace(
                term_out=term_out,
                exec_time=exec_time,
                exc_type=exc_type,
                exc_info=exc_info,
                exc_stack=None,
            )
        )
        child_node.exc_info = exc_info or {}
        _move_experiment_artifacts(
            cfg=cfg,
            child_node=child_node,
            working_dir=working_dir,
            event_callback=event_callback,
        )
        result_data = child_node.to_dict()
        pickle.dumps(result_data)
        return result_data

    try:
        child_node = Node.from_dict(dict(node_result), journal=None)
    except Exception as exc:  # noqa: BLE001
        # Never crash the worker on schema drift: mark the node buggy and return a valid Node dict.
        tb = traceback.format_exc()
        child_node = Node(
            id=execution_id,
            plan=str(node_result.get("plan") or ""),
            code=str(node_result.get("code") or ""),
            is_buggy=True,
            is_buggy_plots=True,
            analysis=(
                "Failed to parse node_result.json into Node.\n"
                f"Exception: {exc}\n\n"
                f"Traceback:\n{tb}"
            ),
            exc_type=exc_type or "NodeParseError",
            exec_time=exec_time,
        )
        child_node.metric = WorstMetricValue()
        if parent_node is not None:
            _attach_parent(child_node=child_node, parent_node=parent_node)
    logger.debug(
        "worker.node_parsed execution_id=%s is_buggy=%s is_buggy_plots=%s metric=%s plan_preview=%s analysis_preview=%s plot_analyses=%s vlm_feedback_summary=%s datasets_successfully_tested=%s",
        execution_id[:8],
        child_node.is_buggy,
        child_node.is_buggy_plots,
        None if child_node.metric is None else str(child_node.metric),
        (child_node.plan or "")[:160].replace("\n", " "),
        (str(child_node.analysis or ""))[:160].replace("\n", " "),
        len(child_node.plot_analyses),
        len(str(child_node.vlm_feedback_summary or "")),
        len(child_node.datasets_successfully_tested),
    )
    child_node.absorb_exec_result(
        SimpleNamespace(
            term_out=term_out,
            exec_time=exec_time,
            exc_type=exc_type,
            exc_info=exc_info,
            exc_stack=None,
        )
    )
    child_node.exec_time = exec_time
    child_node.exc_type = exc_type
    child_node.exc_info = exc_info or {}
    if parent_node is not None and child_node.parent is None:
        _attach_parent(child_node=child_node, parent_node=parent_node)
    if child_node.metric is None:
        child_node.metric = WorstMetricValue()
        child_node.is_buggy = True if child_node.is_buggy is None else child_node.is_buggy
    if child_node.analysis is None or not str(child_node.analysis).strip():
        llm_review = _summarize_execution_with_llm(
            cfg=cfg,
            task_desc=task_desc,
            stage_goals=stage_goals,
            stage_identifier=stage_identifier,
            term_out="".join(term_out),
            exc_type=exc_type,
            exec_time=float(exec_time),
        )
        if llm_review is not None:
            summary = str(llm_review.summary or "").strip()
            if summary:
                child_node.analysis = summary
            if llm_review.is_bug:
                child_node.is_buggy = True

    _move_experiment_artifacts(
        cfg=cfg,
        child_node=child_node,
        working_dir=working_dir,
        event_callback=event_callback,
    )
    # only run VLM for later stages, and only for non-buggy nodes.
    if child_node.is_buggy is False and stage_identifier in (
        StageIdentifier.STAGE3,
        StageIdentifier.STAGE4,
    ):
        generate_vlm_feedback(
            cfg=cfg,
            node=child_node,
            stage_identifier=stage_identifier,
            event_callback=event_callback,
        )

    result_data = child_node.to_dict()
    pickle.dumps(result_data)
    return result_data
