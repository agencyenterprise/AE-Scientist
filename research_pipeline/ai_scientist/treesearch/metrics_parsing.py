import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, List

from pydantic import BaseModel, Field

from ai_scientist.llm import structured_query_with_schema

from .codex.codex_cli_runner import CodexCliRunner, build_codex_env
from .codex.codex_task_types import EvaluationMetricSpec
from .config import Config as AppConfig
from .events import BaseEvent, RunCompletedEvent, RunLogEvent, RunningCodeEvent, RunType
from .executor import run_python_script
from .journal import Node
from .prompts.render import render_text
from .stage_identifiers import StageIdentifier
from .utils.metric import MetricValue, WorstMetricValue

logger = logging.getLogger("ai-scientist")


class MetricDataPoint(BaseModel):
    dataset_name: str = Field(
        ...,
        description="Name of the dataset without 'train', 'val', or 'test' suffixes.",
        min_length=1,
    )
    final_value: float
    best_value: float


class MetricInfo(BaseModel):
    metric_name: str = Field(
        ...,
        description=(
            "Specific metric name (e.g., 'validation accuracy', 'BLEU-4'); "
            "avoid vague labels like 'train' or 'test'."
        ),
        min_length=1,
    )
    lower_is_better: bool = Field(
        ...,
        description="Whether lower values are better for this metric.",
    )
    description: str = Field(
        ...,
        description="Short explanation of what the metric captures.",
        min_length=1,
    )
    data: List[MetricDataPoint] = Field(
        ...,
        description="Per-dataset measurements for this metric.",
    )


class MetricParseResponse(BaseModel):
    valid_metrics_received: bool = Field(
        ...,
        description=(
            "True if any metrics were parsed from the execution output; "
            "False when output lacked metrics."
        ),
    )
    metric_names: List[MetricInfo] = Field(
        ...,
        description=(
            "Collection of metrics parsed from the logs. "
            "Leave empty when valid_metrics_received=False."
        ),
    )


METRIC_PARSE_SCHEMA = MetricParseResponse


def _build_metrics_task_markdown(
    *,
    stage_identifier: StageIdentifier,
    evaluation_metric_spec: EvaluationMetricSpec,
    agent_file_name: str,
) -> str:
    return render_text(
        template_name="metrics_parsing/metrics_parsing_task.md.j2",
        context={
            "stage_identifier_name": stage_identifier.name,
            "agent_file_name": agent_file_name,
            "evaluation_metric_json": json.dumps(evaluation_metric_spec.to_json_dict(), indent=2),
        },
    )


def _datasets_from_metric_response(*, response: dict[str, object]) -> list[str]:
    metric_names = response.get("metric_names")
    if not isinstance(metric_names, list):
        return []
    datasets: set[str] = set()
    for metric in metric_names:
        if not isinstance(metric, dict):
            continue
        data = metric.get("data")
        if not isinstance(data, list):
            continue
        for entry in data:
            if not isinstance(entry, dict):
                continue
            dataset = entry.get("dataset_name")
            if isinstance(dataset, str) and dataset.strip():
                datasets.add(dataset.strip())
    return sorted(datasets)


def generate_and_assign_metrics(
    *,
    cfg: AppConfig,
    research_pipeline_root: Path,
    codex_timeout_seconds: int,
    venv_dir: Path,
    workspace_dir: Path,
    working_dir: Path,
    node: Node,
    node_index: int,
    parent_node: Node | None,
    stage_identifier: StageIdentifier,
    evaluation_metric_spec: EvaluationMetricSpec,
    seed_eval: bool,
    event_callback: Callable[[BaseEvent], None],
) -> Path | None:
    """
    Two-step metrics pipeline:
    1) For normal runs: Codex generates parse_metrics.py.
       For seed-eval runs: reuse the parent node's parse_metrics.py (do NOT call Codex).
    2) Harness runs parse_metrics.py and uses an LLM schema to extract/validate metrics
    """
    if node.is_buggy is True:
        node.metric = WorstMetricValue()
        return None

    experiment_data = working_dir / "experiment_data.npy"
    if not experiment_data.exists():
        event_callback(
            RunLogEvent(
                message="No working/experiment_data.npy found; cannot compute metrics.",
                level="warn",
            )
        )
        node.metric = WorstMetricValue()
        node.is_buggy = True
        return None

    if not str(cfg.agent.feedback.model or "").strip():
        node.metric = WorstMetricValue()
        node.is_buggy = True
        return None

    metrics_workspace_dir = workspace_dir

    agent_file_name = str(cfg.exec.agent_file_name)
    src_agent_file = workspace_dir / agent_file_name
    if not src_agent_file.exists():
        logger.debug("Agent file missing during metrics pass: %s", src_agent_file, exc_info=False)

    parse_metrics_path = metrics_workspace_dir / "parse_metrics.py"
    if seed_eval:
        parent_code = "" if parent_node is None else str(parent_node.parse_metrics_code or "")
        if parent_node is None or not parent_code.strip():
            event_callback(
                RunLogEvent(
                    message=(
                        "Seed evaluation requires reusing the parent's parse_metrics.py, but it was missing. "
                        "Cannot compute metrics for seed-eval run."
                    ),
                    level="warn",
                )
            )
            node.metric = WorstMetricValue()
            node.is_buggy = True
            return None
        parse_metrics_path.write_text(parent_code, encoding="utf-8")
        node.parse_metrics_plan = str(parent_node.parse_metrics_plan or "")
        node.parse_metrics_code = str(parent_node.parse_metrics_code or "")
    else:
        task_text = _build_metrics_task_markdown(
            stage_identifier=stage_identifier,
            evaluation_metric_spec=evaluation_metric_spec,
            agent_file_name=agent_file_name,
        )
        metrics_task_file = metrics_workspace_dir / "codex_metrics_task.md"
        metrics_task_file.write_text(task_text, encoding="utf-8")

        metrics_runner = CodexCliRunner(
            workspace_dir=metrics_workspace_dir,
            research_pipeline_root=research_pipeline_root,
            session_log_name="codex_session__metrics.log",
            events_log_name="codex_events__metrics.jsonl",
            timeout_seconds=codex_timeout_seconds,
            model=cfg.agent.code.model,
            event_callback=event_callback,
            venv_dir=venv_dir,
        )

        event_callback(
            RunLogEvent(
                message="Generating metrics parsing code via Codex...",
                level="info",
            )
        )
        started_at = datetime.now(timezone.utc)

        # Warn if code is empty - this should never happen
        if not task_text or not task_text.strip():
            logger.warning(
                "Emitting RunningCodeEvent with empty/missing code (execution_id=%s_metrics, stage=%s, run_type=CODEX_EXECUTION, context=metrics_parsing)",
                node.id,
                stage_identifier.prefixed_name,
            )

        event_callback(
            RunningCodeEvent(
                execution_id=f"{node.id}_metrics",
                stage_name=stage_identifier.prefixed_name,
                code=task_text,
                started_at=started_at,
                run_type=RunType.CODEX_EXECUTION,
                is_seed_node=False,
                is_seed_agg_node=False,
                node_index=node_index,
            )
        )
        term_out, exec_time, exc_type, exc_info = metrics_runner.run(
            task_file=metrics_task_file,
            stage=stage_identifier.prefixed_name,
            node=node_index,
            pid_callback=None,
            termination_checker=None,
            json_event_callback=None,
        )
        completed_at = datetime.now(timezone.utc)
        event_callback(
            RunCompletedEvent(
                execution_id=f"{node.id}_metrics",
                stage_name=stage_identifier.prefixed_name,
                status="success" if exc_type is None else "failed",
                exec_time=float(exec_time),
                completed_at=completed_at,
                run_type=RunType.CODEX_EXECUTION,
                is_seed_node=False,
                is_seed_agg_node=False,
                node_index=node_index,
            )
        )
        node.parse_metrics_plan = task_text
        node.parse_term_out = term_out
        node.parse_exc_type = exc_type
        node.parse_exc_info = exc_info or {}
        node.parse_exc_stack = []

        if not parse_metrics_path.exists():
            node.metric = WorstMetricValue()
            node.is_buggy = True
            return metrics_workspace_dir

        node.parse_metrics_code = parse_metrics_path.read_text(encoding="utf-8", errors="replace")

    # Build Codex environment for script execution
    codex_env = build_codex_env(venv_dir=venv_dir)

    python_executable = venv_dir / "bin" / "python"
    parse_result = run_python_script(
        purpose="metrics_parse",
        python_executable=python_executable,
        script_path=parse_metrics_path,
        cwd=metrics_workspace_dir,
        env=codex_env,
        timeout_seconds=int(cfg.exec.timeout),
    )
    parse_term_out = parse_result.term_out
    parse_exc_type = parse_result.exc_type
    parse_exc_info = parse_result.exc_info
    node.parse_term_out = parse_term_out
    node.parse_exc_type = parse_exc_type
    node.parse_exc_info = parse_exc_info
    node.parse_exc_stack = []

    if parse_exc_type is not None:
        node.metric = WorstMetricValue()
        node.is_buggy = True
        return metrics_workspace_dir

    metrics_prompt = {
        "Introduction": (
            "Parse the metrics from the execution output. You only need the final or best value "
            "of each metric for each dataset."
        ),
        "Execution Output": parse_term_out,
    }
    logger.debug(
        "llm.metrics_parse.request node=%s model=%s temperature=%s schema=%s payload=%s",
        node.id[:8],
        cfg.agent.feedback.model,
        cfg.agent.feedback.temperature,
        METRIC_PARSE_SCHEMA.__name__,
        metrics_prompt,
    )
    try:
        metrics_model = structured_query_with_schema(
            system_message=metrics_prompt,
            user_message=None,
            model=cfg.agent.feedback.model,
            temperature=cfg.agent.feedback.temperature,
            schema_class=METRIC_PARSE_SCHEMA,
        )
    except Exception:  # noqa: BLE001  # pylint: disable=broad-exception-caught
        logger.exception("Failed to parse metrics via LLM for node=%s", node.id[:8])
        node.metric = WorstMetricValue()
        node.is_buggy = True
        return metrics_workspace_dir

    metrics_response = metrics_model.model_dump(by_alias=True)
    logger.debug(
        "llm.metrics_parse.response node=%s model=%s schema=%s payload=%s",
        node.id[:8],
        cfg.agent.feedback.model,
        METRIC_PARSE_SCHEMA.__name__,
        metrics_response,
    )
    if metrics_model.valid_metrics_received:
        metric_names = metrics_response.get("metric_names", [])
        node.metric = MetricValue(value={"metric_names": metric_names})
        node.datasets_successfully_tested = _datasets_from_metric_response(
            response=metrics_response
        )
        if node.is_buggy is None:
            node.is_buggy = False
    else:
        node.metric = WorstMetricValue()
        node.is_buggy = True

    return metrics_workspace_dir


def persist_metrics_pass_artifacts(
    *,
    node: Node,
    metrics_workspace_dir: Path,
) -> None:
    if not node.exp_results_dir:
        return
    exp_dir = Path(node.exp_results_dir)
    exp_dir.mkdir(parents=True, exist_ok=True)

    for rel_path in (
        "codex_metrics_task.md",
        "metrics_task_result.json",
        "parse_metrics.py",
        "codex_session__metrics.log",
        "codex_events__metrics.jsonl",
    ):
        src = metrics_workspace_dir / rel_path
        if not src.exists():
            continue
        dst = exp_dir / f"metrics_pass__{rel_path}"
        try:
            dst.write_bytes(src.read_bytes())
        except OSError:
            logger.debug("Failed copying metrics artifact %s", rel_path, exc_info=True)
