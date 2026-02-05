import json
import logging
import multiprocessing
import os
import pickle
import shutil
import traceback
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Callable, Literal, TypedDict

from pydantic import BaseModel, Field

from ai_scientist.llm import structured_query_with_schema

from . import execution_registry
from .codex.codex_cli_runner import CodexCliRunner, build_codex_env, ensure_codex_venv
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
from .codex.seed_aggregation import (
    codex_seed_aggregation_instructions_lines,
)
from .config import Config as AppConfig
from .config import apply_log_level
from .events import BaseEvent, RunCompletedEvent, RunLogEvent, RunningCodeEvent, RunType
from .executor import run_python_script
from .gpu_manager import GPUSpec, get_gpu_specs
from .journal import Node
from .metrics_parsing import generate_and_assign_metrics, persist_metrics_pass_artifacts
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

logger = logging.getLogger("ai-scientist")
RESEARCH_PIPELINE_ROOT = Path(__file__).resolve().parents[2]


class TrainingReview(BaseModel):
    is_bug: bool = Field(
        ...,
        description="True if the output log shows a failure or bug; False when execution succeeded.",
    )
    summary: str = Field(
        ...,
        description=(
            "Summary of what happened. If is_bug=True, summarize the failure and propose a fix direction. "
            "If is_bug=False, summarize the findings."
        ),
        min_length=1,
    )


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
        except Exception:  # pylint: disable=broad-exception-caught
            exp_results_dir = str(Path(parent_node.exp_results_dir).resolve())

    plot_analyses: list[dict[str, Any]] = []
    for analysis in parent_node.plot_analyses:
        plot_path = analysis.get("plot_path")
        if isinstance(plot_path, str) and plot_path.strip():
            try:
                rel_plot_path = str(Path(plot_path).resolve().relative_to(Path.cwd()))
            except Exception:  # pylint: disable=broad-exception-caught
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


def _review_execution_with_llm(
    *,
    cfg: AppConfig,
    title: str,
    task_desc: str,
    stage_goals: str,
    stage_identifier: StageIdentifier,
    code: str,
    plan: str,
    term_out: str,
    exc_type: str | None,
    exec_time: float,
) -> TrainingReview | None:
    prompt = {
        "Introduction": (
            "Analyze the execution output, determine if there were any bugs, and provide a summary of the findings. "
            "If there is a bug, summarize the failure and propose a concrete fix direction."
            "I am giving you the execution output of what the agent did, the agent iterates on the code trying to fix"
            "the problems it might find. If the agent found and fixed a bug you should not say that there is a bug."
            "A bug is a problem that the agent wasn't able to fix or if the agent didn't manage to make it work."
        ),
        "Research idea title": title,
        "Research idea description": task_desc,
        "Stage": stage_identifier.name,
        "Stage goals": stage_goals,
        "Experiment plan": plan,
        "Experiment code": wrap_code(code, lang="python"),
        "Execution output": wrap_code(term_out, lang=""),
        "Exception type": str(exc_type or ""),
        "Execution time (seconds)": exec_time,
    }
    logger.debug(
        "llm.review.request model=%s temperature=%s schema=%s payload=%s",
        cfg.agent.feedback.model,
        cfg.agent.feedback.temperature,
        TrainingReview.__name__,
        prompt,
    )
    try:
        response = structured_query_with_schema(
            system_message=prompt,
            user_message=None,
            model=cfg.agent.feedback.model,
            temperature=cfg.agent.feedback.temperature,
            schema_class=TrainingReview,
        )
    except Exception:  # noqa: BLE001  # pylint: disable=broad-exception-caught
        logger.exception("Failed to summarize execution output via LLM.")
        return None
    try:
        logger.debug(
            "llm.review.response model=%s schema=%s payload=%s",
            cfg.agent.feedback.model,
            TrainingReview.__name__,
            response.model_dump(by_alias=True),
        )
    except Exception:  # noqa: BLE001  # pylint: disable=broad-exception-caught
        logger.debug(
            "llm.review.response model=%s schema=%s payload=<unprintable>",
            cfg.agent.feedback.model,
            TrainingReview.__name__,
        )
    return response


def _build_seed_eval_script_text(*, seed_value: int, parent_code: str) -> str:
    """
    Build a standalone Python script that enforces deterministic seeding, then runs `parent_code`.

    This is used for `seed_eval` runs, which intentionally bypass Codex and re-execute an existing
    experiment implementation under different RNG seeds.
    """
    return "\n".join(
        [
            "",
            "",
            "import random",
            "from pathlib import Path",
            "",
            "import numpy as np",
            "",
            "try:",
            "    import torch",
            "except Exception:  # noqa: BLE001",
            "    torch = None",
            "",
            f"seed_value = {seed_value}",
            "random.seed(seed_value)",
            "np.random.seed(seed_value)",
            "if torch is not None:",
            "    torch.manual_seed(seed_value)",
            "    torch.cuda.manual_seed_all(seed_value)",
            "",
            "# Ensure working/ exists (the experiment code is expected to use it).",
            "working_dir = Path.cwd() / 'working'",
            "working_dir.mkdir(parents=True, exist_ok=True)",
            "",
            parent_code,
            "",
        ]
    )


def _process_seed_eval_reuse(
    *,
    cfg: AppConfig,
    title: str,
    task_desc: str,
    stage_goals: str,
    stage_identifier: StageIdentifier,
    evaluation_metric_spec: EvaluationMetricSpec,
    workspace_dir: Path,
    working_dir: Path,
    venv_dir: Path,
    execution_id: str,
    seed_eval: bool,
    seed_value: int,
    parent_node: Node,
    event_callback: Callable[[BaseEvent], None],
    node_index: int,
) -> dict[str, object]:
    """
    Execute the parent node's experiment code under a different seed (no Codex involved).

    Purpose:
    - After a main stage completes, the system re-runs the best implementation across multiple
      RNG seeds to check that the metric is not a one-off due to randomness.

    Key point:
    - The seed-eval run **does not** ask Codex to generate/modify code. It writes a small wrapper
      (`seed_eval_run.py`) that sets seeds and then executes the parent's experiment code verbatim.
    """
    # Seed-eval reuse: execute the parent's experiment code with a different seed.
    parent_code = str(parent_node.code or "")
    agent_file = workspace_dir / str(cfg.exec.agent_file_name)
    agent_file.write_text(parent_code, encoding="utf-8")

    seed_eval_script = workspace_dir / "seed_eval_run.py"
    seed_eval_script.write_text(
        _build_seed_eval_script_text(seed_value=seed_value, parent_code=parent_code),
        encoding="utf-8",
    )

    # Build Codex environment for script execution
    codex_env = build_codex_env(venv_dir=venv_dir)

    python_executable = venv_dir / "bin" / "python"
    exec_result = run_python_script(
        purpose="seed_eval",
        python_executable=python_executable,
        script_path=seed_eval_script,
        cwd=workspace_dir,
        env=codex_env,
        timeout_seconds=int(cfg.exec.timeout),
    )
    term_out = exec_result.term_out
    exec_time = exec_result.exec_time_s
    exc_type = exec_result.exc_type
    exc_info = exec_result.exc_info

    child_node = Node(
        id=execution_id,
        plan=f"Seed evaluation run. Seed: {seed_value}",
        code=parent_code,
        is_seed_node=True,
        is_seed_agg_node=False,
        is_buggy_plots=False,
        plot_code=parent_node.plot_code,
        plot_plan=parent_node.plot_plan,
        parse_metrics_plan=str(parent_node.parse_metrics_plan or ""),
        parse_metrics_code=str(parent_node.parse_metrics_code or ""),
    )
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
    child_node.exec_time = exec_time
    child_node.exc_type = exc_type
    child_node.exc_info = exc_info or {}

    llm_review = _review_execution_with_llm(
        cfg=cfg,
        title=title,
        task_desc=task_desc,
        stage_goals=stage_goals,
        stage_identifier=stage_identifier,
        code=child_node.code,
        plan=child_node.plan,
        term_out="".join(term_out),
        exc_type=exc_type,
        exec_time=float(exec_time),
    )
    if llm_review is None:
        child_node.analysis = "LLM execution review failed; see execution output."
        child_node.is_buggy = True
    else:
        child_node.analysis = str(llm_review.summary or "").strip()
        child_node.is_buggy = bool(llm_review.is_bug) or (exc_type is not None)

    metrics_workspace_dir = generate_and_assign_metrics(
        cfg=cfg,
        research_pipeline_root=RESEARCH_PIPELINE_ROOT,
        codex_timeout_seconds=int(cfg.exec.timeout),
        venv_dir=venv_dir,
        workspace_dir=workspace_dir,
        working_dir=working_dir,
        node=child_node,
        node_index=node_index,
        parent_node=parent_node,
        stage_identifier=stage_identifier,
        evaluation_metric_spec=evaluation_metric_spec,
        seed_eval=seed_eval,
        event_callback=event_callback,
    )

    _move_experiment_artifacts(
        cfg=cfg,
        child_node=child_node,
        working_dir=working_dir,
        event_callback=event_callback,
    )
    if metrics_workspace_dir is not None:
        persist_metrics_pass_artifacts(node=child_node, metrics_workspace_dir=metrics_workspace_dir)

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


def _attach_parent(*, child_node: Node, parent_node: Node) -> None:
    # We intentionally attach relationships here so that `Node.to_dict()` emits `parent_id`,
    # which `Node.from_dict(..., journal=...)` uses to reconstruct the tree in the main process.
    child_node.parent = parent_node


class NodeTask(TypedDict):
    node_data: dict[str, object] | None
    title: str
    task_desc: str
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
    node_index: int


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


def _cleanup_venv(*, venv_dir: Path) -> None:
    """Remove the per-execution venv to free disk space."""
    if not venv_dir.exists():
        return
    try:
        shutil.rmtree(venv_dir)
        logger.debug("Cleaned up venv at %s", venv_dir)
    except OSError:
        logger.warning("Failed to cleanup venv at %s", venv_dir, exc_info=True)


def _prepare_workspace(
    *,
    cfg: AppConfig,
    stage_name: str,
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

    # Copy default example_code.py to workspace
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
        raw_term_out = parent_node._term_out  # pylint: disable=protected-access
        if isinstance(raw_term_out, list):
            parent_term_out = trim_long_string("".join([str(x) for x in raw_term_out]))
        parent_vlm_feedback_summary = str(parent_node.vlm_feedback_summary or "").strip()

    is_seed_aggregation = task_context.seed_aggregation is not None
    is_improvement_scenario = (
        (parent_node is not None) and (parent_node.is_buggy is False) and (not is_seed_aggregation)
    )
    if is_seed_aggregation:
        # Override stage contract for seed-aggregation runs: keep common contract + add explicit
        # aggregation requirements (including is_seed_agg_node=true).
        contract_lines = (
            codex_node_result_contract_prompt_lines_common() + codex_seed_agg_contract_lines()
        )
        seed_agg_instructions = "\n".join(
            codex_seed_aggregation_instructions_lines(
                seed_aggregation=task_context.seed_aggregation
            )
        ).strip()
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
        task_title=task_context.task_title,
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
        is_improvement_scenario=is_improvement_scenario,
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


def _copy_workspace_artifacts(
    *,
    workspace_dir: Path,
    exp_results_dir: Path,
) -> None:
    venv_dir = workspace_dir / ".ai_scientist_venv"
    for src in workspace_dir.iterdir():
        if src == venv_dir:
            continue
        dst = exp_results_dir / src.name
        try:
            if src.is_dir():
                shutil.copytree(src, dst, dirs_exist_ok=True)
            else:
                shutil.copy2(src, dst)
        except OSError:
            logger.debug(
                "artifacts.copy_failed src=%s dst=%s",
                src,
                dst,
                exc_info=True,
            )


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

    _copy_workspace_artifacts(workspace_dir=workspace_dir, exp_results_dir=exp_results_dir)
    logger.debug(
        "artifacts.done node=%s exp_results_dir=%s plots=%s npy_files=%s",
        child_node.id[:8],
        exp_results_dir,
        len(child_node.plots),
        len(npy_files),
    )


def _absorb_exec_result(
    *,
    child_node: Node,
    term_out: list[str],
    exec_time: float,
    exc_type: str | None,
    exc_info: dict[str, object] | None,
) -> None:
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


def _return_buggy_node_dict(
    *,
    cfg: AppConfig,
    execution_id: str,
    plan: str,
    code: str,
    analysis: str,
    exc_type: str,
    exec_time: float,
    term_out: list[str],
    exc_info: dict[str, object] | None,
    parent_node: Node | None,
    working_dir: Path,
    event_callback: Callable[[BaseEvent], None],
) -> dict[str, object]:
    child_node = Node(
        id=execution_id,
        plan=plan,
        code=code,
        is_buggy=True,
        is_buggy_plots=True,
        analysis=analysis,
        exc_type=exc_type,
        exec_time=exec_time,
    )
    termination_payload = execution_registry.get_termination_payload(execution_id) or ""
    if termination_payload.strip():
        child_node.is_user_feedback = True
        child_node.user_feedback_payload = termination_payload
        child_node.user_feedback_pending = True
    child_node.metric = WorstMetricValue()
    if parent_node is not None:
        _attach_parent(child_node=child_node, parent_node=parent_node)
    _absorb_exec_result(
        child_node=child_node,
        term_out=term_out,
        exec_time=exec_time,
        exc_type=exc_type,
        exc_info=exc_info,
    )
    _move_experiment_artifacts(
        cfg=cfg,
        child_node=child_node,
        working_dir=working_dir,
        event_callback=event_callback,
    )
    result_data = child_node.to_dict()
    pickle.dumps(result_data)
    return result_data


def _read_text_or_empty(*, path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        logger.debug("Failed reading text file at %s", path, exc_info=True)
        return ""


def _prepare_codex_task_file(
    *,
    workspace_dir: Path,
    execution_id: str,
    stage_identifier: StageIdentifier,
    stage_name: str,
    cfg: AppConfig,
    venv_dir: Path,
    title: str,
    task_desc: str,
    stage_goals: str,
    evaluation_metric_spec: EvaluationMetricSpec,
    memory_summary: str,
    parent_node: Node | None,
    seed_aggregation: SeedAggregationPayload | None,
    stage2_hyperparam_idea: StageIdea | None,
    stage4_ablation_idea: StageIdea | None,
    gpu_id: int | None,
    gpu_spec: GPUSpec | None,
    user_feedback_payload: str,
) -> tuple[Path, Path, dict[str, object]]:
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
        seed_aggregation=seed_aggregation,
        stage2_hyperparam_idea=stage2_hyperparam_idea,
        stage4_ablation_idea=stage4_ablation_idea,
        gpu_id=gpu_id,
        agent_file_name=cfg.exec.agent_file_name,
        timeout_seconds=cfg.exec.timeout,
        parent_node=parent_node_summary,
        user_feedback_payload=user_feedback_payload,
        task_title=title,
        task_desc=task_desc,
        stage_goals=stage_goals,
        evaluation_metric_spec=evaluation_metric_spec,
        memory_summary=memory_summary,
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
    return output_json_file, task_file, env_ctx


def _run_codex_cli(
    *,
    workspace_dir: Path,
    execution_id: str,
    stage_name: str,
    cfg: AppConfig,
    venv_dir: Path,
    task_file: Path,
    event_callback: Callable[[BaseEvent], None],
    node: int,
    is_seed_node: bool = False,
    is_seed_agg_node: bool = False,
) -> tuple[list[str], float, str | None, dict[str, object] | None]:
    runner = CodexCliRunner(
        workspace_dir=workspace_dir,
        research_pipeline_root=RESEARCH_PIPELINE_ROOT,
        session_log_name="codex_session.log",
        events_log_name="codex_events.jsonl",
        timeout_seconds=cfg.exec.timeout,
        model=cfg.agent.code.model,
        event_callback=event_callback,
        venv_dir=venv_dir,
    )

    codex_task_content = _read_text_or_empty(path=task_file)
    started_at = datetime.now(timezone.utc)
    event_callback(RunLogEvent(message="Executing via Codex CLI...", level="info"))

    # Warn if code is empty - this should never happen
    if not codex_task_content or not codex_task_content.strip():
        logger.warning(
            "Emitting RunningCodeEvent with empty/missing code (execution_id=%s, stage=%s, run_type=CODEX_EXECUTION, task_file=%s)",
            execution_id,
            stage_name,
            task_file,
        )

    event_callback(
        RunningCodeEvent(
            execution_id=execution_id,
            stage_name=stage_name,
            code=codex_task_content,
            started_at=started_at,
            run_type=RunType.CODEX_EXECUTION,
            is_seed_node=is_seed_node,
            is_seed_agg_node=is_seed_agg_node,
        )
    )

    runfile_started_at: datetime | None = None
    runfile_item_id: str | None = None

    def _codex_json_event_callback(*, line: str, obj: dict[str, object]) -> None:
        """
        Handle raw Codex JSONL events during `codex exec --json` execution.

        Goals:
        - **Live code streaming**: while the Codex-controlled command that runs our agent file
          (commonly `runfile.py`) is still running, emit `RunningCodeEvent` updates where
          `code` is the current contents of the agent file on disk. This keeps the UI in sync
          with what will actually be executed, instead of only showing the task markdown.
        - **Runfile lifecycle**: when the runfile command reaches `status="completed"`, emit a
          `RunCompletedEvent` for `run_type="runfile_execution"`.
        - The `codex_execution` lifecycle is always completed after `runner.run(...)` returns.

        Notes:
        - We only react to Codex events shaped like:
          `{"type":"item.started|item.completed", "item": {"type":"command_execution", ...}}`
        - We filter to the command that references the agent file name or `runfile.py`
          (using both the parsed command string and the raw JSON line as a fallback).
        - This is best-effort: if the file is missing/empty we simply skip emitting updates.
        """
        nonlocal runfile_item_id, runfile_started_at

        # We only care about the command execution item because that's what produces the
        # agent file on disk and has a clear completed/in-progress lifecycle.
        item = obj.get("item")
        if not isinstance(item, dict):
            return
        if item.get("type") != "command_execution":
            return

        command = item.get("command")
        if not isinstance(command, str):
            return

        agent_file_name = str(cfg.exec.agent_file_name)
        if (
            agent_file_name not in command
            and "runfile.py" not in command
            and agent_file_name not in line
            and "runfile.py" not in line
        ):
            return

        item_id = item.get("id")
        if not isinstance(item_id, str):
            item_id = None

        status = item.get("status")
        if status == "in_progress":
            # Start a new runfile window for each command_execution item.
            if runfile_item_id != item_id:
                runfile_item_id = item_id
                runfile_started_at = datetime.now(timezone.utc)

        if status == "completed":
            completed_at = datetime.now(timezone.utc)
            exec_time_base = started_at if runfile_started_at is None else runfile_started_at
            exec_time = (completed_at - exec_time_base).total_seconds()
            status_value: Literal["success", "failed"] = "success"
            exit_code = item.get("exit_code")
            if isinstance(exit_code, int) and exit_code != 0:
                status_value = "failed"
            event_callback(
                RunCompletedEvent(
                    execution_id=execution_id,
                    stage_name=stage_name,
                    status=status_value,
                    exec_time=exec_time,
                    completed_at=completed_at,
                    run_type=RunType.RUNFILE_EXECUTION,
                    is_seed_node=is_seed_node,
                    is_seed_agg_node=is_seed_agg_node,
                )
            )
            runfile_item_id = None
            runfile_started_at = None
            return

        runfile_path = workspace_dir / agent_file_name
        if not runfile_path.exists():
            return
        runfile_content = _read_text_or_empty(path=runfile_path)
        if not runfile_content.strip():
            return
        # Stream the current on-disk code while Codex is still running the command.
        if runfile_started_at is None:
            runfile_started_at = datetime.now(timezone.utc)
        event_callback(
            RunningCodeEvent(
                execution_id=execution_id,
                stage_name=stage_name,
                code=runfile_content,
                started_at=runfile_started_at,
                run_type=RunType.RUNFILE_EXECUTION,
                is_seed_node=is_seed_node,
                is_seed_agg_node=is_seed_agg_node,
            )
        )

    def _pid_tracker(*, pid: int) -> None:
        execution_registry.update_pid(execution_id=execution_id, pid=pid)

    def _termination_checker() -> bool:
        return execution_registry.is_terminated(execution_id=execution_id)

    term_out, exec_time, exc_type, exc_info = runner.run(
        task_file=task_file,
        stage=stage_name,
        node=node,
        pid_callback=lambda pid: _pid_tracker(pid=pid),
        termination_checker=_termination_checker,
        json_event_callback=lambda line, obj: _codex_json_event_callback(line=line, obj=obj),
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
            run_type=RunType.CODEX_EXECUTION,
            is_seed_node=is_seed_node,
            is_seed_agg_node=is_seed_agg_node,
        )
    )
    if exc_type is None:
        execution_registry.mark_completed(execution_id=execution_id)
    else:
        execution_registry.clear_pid(execution_id=execution_id)

    return term_out, exec_time, exc_type, exc_info


def process_node(
    *,
    node_data: dict[str, object] | None,
    title: str,
    task_desc: str,
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
    node_index: int,
) -> dict[str, object]:
    """
    Worker entrypoint for producing a single `Node`.

    `seed_eval` semantics:
    - When `seed_eval=True` (and a parent node is provided), the worker **does not use Codex**.
      Instead it re-executes the parent node's experiment code under `seed_value` to measure
      robustness across RNG seeds.
    - When `seed_eval=False`, the worker uses Codex to draft/debug/improve code as usual.
    """
    _ensure_worker_log_level(cfg=cfg)
    process_id = multiprocessing.current_process().name
    stage_name = stage_identifier.prefixed_name
    workspace_dir, working_dir = _prepare_workspace(
        cfg=cfg,
        stage_name=stage_name,
    )
    gpu_spec = _configure_gpu_for_worker(gpu_id=gpu_id)
    venv_dir = ensure_codex_venv(
        workspace_dir=workspace_dir,
        research_pipeline_root=RESEARCH_PIPELINE_ROOT,
    )

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

    if seed_eval and seed_aggregation is None and parent_node is not None:
        result_data = _process_seed_eval_reuse(
            cfg=cfg,
            title=title,
            task_desc=task_desc,
            stage_goals=stage_goals,
            stage_identifier=stage_identifier,
            evaluation_metric_spec=evaluation_metric_spec,
            workspace_dir=workspace_dir,
            working_dir=working_dir,
            venv_dir=venv_dir,
            execution_id=execution_id,
            seed_eval=seed_eval,
            seed_value=seed_value,
            parent_node=parent_node,
            event_callback=event_callback,
            node_index=node_index,
        )
        _cleanup_venv(venv_dir=venv_dir)
        return result_data

    output_json_file, task_file, _env_ctx = _prepare_codex_task_file(
        workspace_dir=workspace_dir,
        execution_id=execution_id,
        stage_identifier=stage_identifier,
        stage_name=stage_name,
        cfg=cfg,
        venv_dir=venv_dir,
        title=title,
        task_desc=task_desc,
        stage_goals=stage_goals,
        evaluation_metric_spec=evaluation_metric_spec,
        memory_summary=memory_summary,
        parent_node=parent_node,
        seed_aggregation=seed_aggregation,
        stage2_hyperparam_idea=stage2_hyperparam_idea,
        stage4_ablation_idea=stage4_ablation_idea,
        gpu_id=gpu_id,
        gpu_spec=gpu_spec,
        user_feedback_payload=user_feedback_payload,
    )

    term_out, exec_time, exc_type, exc_info = _run_codex_cli(
        workspace_dir=workspace_dir,
        execution_id=execution_id,
        stage_name=stage_name,
        cfg=cfg,
        venv_dir=venv_dir,
        task_file=task_file,
        event_callback=event_callback,
        node=node_index,
        is_seed_node=seed_eval and seed_aggregation is None,
        is_seed_agg_node=seed_aggregation is not None,
    )

    node_result = _load_node_result(output_json_file=output_json_file)
    if node_result is None:
        termination_payload = execution_registry.get_termination_payload(execution_id) or ""
        exc_type_value = str(exc_type or "ExecutionTerminatedError")

        def _return_terminated_result(*, analysis: str) -> dict[str, object]:
            return _return_buggy_node_dict(
                cfg=cfg,
                execution_id=execution_id,
                plan="",
                code="",
                analysis=analysis,
                exc_type=exc_type_value,
                exec_time=exec_time,
                term_out=term_out,
                exc_info=exc_info,
                parent_node=parent_node,
                working_dir=working_dir,
                event_callback=event_callback,
            )

        if termination_payload.strip():
            logger.debug(
                "codex.output.terminated execution_id=%s node_index=%s",
                execution_id[:8],
                node_index,
            )
            return _return_terminated_result(
                analysis=(
                    f"User terminated execution and provided the feedback {termination_payload.strip()}"
                )
            )
        if execution_registry.is_terminated(execution_id):
            logger.debug(
                "codex.output.terminated execution_id=%s node_index=%s",
                execution_id[:8],
                node_index,
            )
            return _return_terminated_result(analysis="User terminated execution.")
        logger.debug(
            "codex.output.missing_node_result execution_id=%s expected_path=%s",
            execution_id[:8],
            output_json_file,
        )
        return _return_buggy_node_dict(
            cfg=cfg,
            execution_id=execution_id,
            plan="",
            code="",
            analysis="Codex did not produce a valid node_result.json.",
            exc_type=str(exc_type or "CodexError"),
            exec_time=exec_time,
            term_out=term_out,
            exc_info=exc_info,
            parent_node=parent_node,
            working_dir=working_dir,
            event_callback=event_callback,
        )

    if seed_aggregation is not None:
        node_result["is_seed_agg_node"] = True
        # Determine plot health from artifacts: if no plots were written, mark plots buggy.
        node_result["is_buggy_plots"] = count_working_pngs(working_dir=working_dir) <= 0

    # Always treat the agent file as the source of truth for the executed code.
    # If Codex fails to write this file (or writes it empty), treat it as a contract failure.
    agent_file_name = str(cfg.exec.agent_file_name)
    agent_file_path = workspace_dir / agent_file_name
    if not agent_file_path.exists():
        logger.debug(
            "codex.output.missing_agent_code execution_id=%s expected_path=%s",
            execution_id[:8],
            agent_file_path,
        )
        return _return_buggy_node_dict(
            cfg=cfg,
            execution_id=execution_id,
            plan=str(node_result.get("plan") or ""),
            code="",
            analysis=f"Codex did not write the required agent code file: {agent_file_name}",
            exc_type=str(exc_type or "CodexContractError"),
            exec_time=exec_time,
            term_out=term_out,
            exc_info=exc_info,
            parent_node=parent_node,
            working_dir=working_dir,
            event_callback=event_callback,
        )

    code_text = _read_text_or_empty(path=agent_file_path)
    if not code_text:
        logger.debug(
            "codex.output.agent_code_read_failed execution_id=%s path=%s",
            execution_id[:8],
            agent_file_path,
            exc_info=True,
        )
    if not code_text.strip():
        return _return_buggy_node_dict(
            cfg=cfg,
            execution_id=execution_id,
            plan=str(node_result.get("plan") or ""),
            code="",
            analysis=f"Codex wrote an empty agent code file: {agent_file_name}",
            exc_type=str(exc_type or "CodexContractError"),
            exec_time=exec_time,
            term_out=term_out,
            exc_info=exc_info,
            parent_node=parent_node,
            working_dir=working_dir,
            event_callback=event_callback,
        )

    node_result["code"] = code_text

    node_result["id"] = execution_id
    node_result["parent_id"] = None if parent_node is None else parent_node.id
    logger.debug(
        "codex.output.node_result_loaded execution_id=%s keys=%s plan_preview=%s",
        execution_id[:8],
        sorted(list(node_result.keys())),
        str(node_result.get("plan") or ""),
    )

    contract_ctx = NodeResultContractContext(
        stage_identifier=stage_identifier,
        is_seed_aggregation=seed_aggregation is not None,
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
        return _return_buggy_node_dict(
            cfg=cfg,
            execution_id=execution_id,
            plan=str(node_result.get("plan") or ""),
            code=str(node_result.get("code") or ""),
            analysis="Codex node_result contract violation(s):\n- " + "\n- ".join(contract_errors),
            exc_type=str(exc_type or "CodexContractError"),
            exec_time=exec_time,
            term_out=term_out,
            exc_info=exc_info,
            parent_node=parent_node,
            working_dir=working_dir,
            event_callback=event_callback,
        )

    parse_failed = False
    try:
        child_node = Node.from_dict(dict(node_result), journal=None)
    except Exception as exc:  # noqa: BLE001  # pylint: disable=broad-exception-caught
        # Never crash the worker on schema drift: mark the node buggy and return a valid Node dict.
        parse_failed = True
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

    if parent_node is not None and child_node.parent is None:
        _attach_parent(child_node=child_node, parent_node=parent_node)

    effective_exc_type = child_node.exc_type if parse_failed else exc_type
    _absorb_exec_result(
        child_node=child_node,
        term_out=term_out,
        exec_time=exec_time,
        exc_type=effective_exc_type,
        exc_info=exc_info,
    )

    if not parse_failed:
        # Avoid extra LLM calls when Codex already provided analysis/bugginess.
        has_analysis = bool(str(child_node.analysis or "").strip())
        has_bug_flag = child_node.is_buggy is not None
        if not (has_analysis and has_bug_flag):
            llm_review = _review_execution_with_llm(
                cfg=cfg,
                title=title,
                task_desc=task_desc,
                stage_goals=stage_goals,
                stage_identifier=stage_identifier,
                code=str(child_node.code or ""),
                plan=str(child_node.plan or ""),
                term_out="".join(term_out),
                exc_type=exc_type,
                exec_time=float(exec_time),
            )
            if llm_review is None:
                child_node.analysis = "LLM execution review failed; see execution output."
                child_node.is_buggy = True
            else:
                child_node.analysis = str(llm_review.summary or "").strip()
                child_node.is_buggy = bool(llm_review.is_bug) or (exc_type is not None)

    metrics_workspace_dir = generate_and_assign_metrics(
        cfg=cfg,
        research_pipeline_root=RESEARCH_PIPELINE_ROOT,
        codex_timeout_seconds=int(cfg.exec.timeout),
        venv_dir=venv_dir,
        workspace_dir=workspace_dir,
        working_dir=working_dir,
        node=child_node,
        node_index=node_index,
        parent_node=parent_node,
        stage_identifier=stage_identifier,
        evaluation_metric_spec=evaluation_metric_spec,
        seed_eval=seed_eval,
        event_callback=event_callback,
    )

    if child_node.metric is None:
        child_node.metric = WorstMetricValue()
        child_node.is_buggy = True
    if child_node.is_buggy is None:
        child_node.is_buggy = True

    _move_experiment_artifacts(
        cfg=cfg,
        child_node=child_node,
        working_dir=working_dir,
        event_callback=event_callback,
    )
    if metrics_workspace_dir is not None:
        persist_metrics_pass_artifacts(node=child_node, metrics_workspace_dir=metrics_workspace_dir)
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

    result_data = child_node.to_dict()
    pickle.dumps(result_data)
    _cleanup_venv(venv_dir=venv_dir)
    return result_data
