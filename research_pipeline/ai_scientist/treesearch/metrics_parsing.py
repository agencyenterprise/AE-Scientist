import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, List

from pydantic import BaseModel, Field

from ai_scientist.llm import structured_query_with_schema

from .codex.codex_cli_runner import CodexCliRunner
from .codex.codex_task_types import EvaluationMetricSpec
from .config import Config as AppConfig
from .events import BaseEvent, RunLogEvent
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


@dataclass(frozen=True)
class MetricsPassArtifacts:
    metrics_workspace_dir: Path
    metrics_task_file: Path


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
    codex_env: dict[str, str],
    codex_argv: list[str],
    codex_timeout_seconds: int,
    venv_dir: Path,
    workspace_dir: Path,
    working_dir: Path,
    node: Node,
    parent_node: Node | None,
    stage_identifier: StageIdentifier,
    evaluation_metric_spec: EvaluationMetricSpec,
    seed_eval: bool,
    event_callback: Callable[[BaseEvent], None],
) -> MetricsPassArtifacts | None:
    """
    Two-step metrics pipeline:
    1) Codex generates parse_metrics.py (optionally reusing parent parse code for seed_eval)
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

    metrics_workspace_dir = workspace_dir / "metrics_pass"
    metrics_working_dir = metrics_workspace_dir / "working"
    metrics_working_dir.mkdir(parents=True, exist_ok=True)

    try:
        (metrics_working_dir / experiment_data.name).write_bytes(experiment_data.read_bytes())
    except OSError:
        logger.exception("Failed copying experiment_data.npy to metrics workspace")
        node.metric = WorstMetricValue()
        node.is_buggy = True
        return None

    agent_file_name = str(cfg.exec.agent_file_name)
    src_agent_file = workspace_dir / agent_file_name
    dst_agent_file = metrics_workspace_dir / agent_file_name
    if src_agent_file.exists():
        try:
            dst_agent_file.write_bytes(src_agent_file.read_bytes())
        except OSError:
            logger.debug("Failed copying %s into metrics workspace", agent_file_name, exc_info=True)

    parse_metrics_path = metrics_workspace_dir / "parse_metrics.py"
    if seed_eval and parent_node is not None and str(parent_node.parse_metrics_code or "").strip():
        parse_metrics_path.write_text(str(parent_node.parse_metrics_code), encoding="utf-8")
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
        success_file = metrics_workspace_dir / "metrics_task_result.json"

        metrics_runner = CodexCliRunner(
            workspace_dir=metrics_workspace_dir,
            timeout_seconds=codex_timeout_seconds,
            argv=codex_argv,
            env=codex_env,
        )

        event_callback(
            RunLogEvent(
                message="Generating metrics parsing code via Codex...",
                level="info",
            )
        )
        term_out, _, exc_type, exc_info = metrics_runner.run(
            task_file=metrics_task_file,
            pid_callback=None,
            termination_checker=None,
            success_file=success_file,
            stream_callback=lambda msg: event_callback(RunLogEvent(message=msg, level="info")),
        )
        node.parse_metrics_plan = task_text
        node.parse_term_out = term_out
        node.parse_exc_type = exc_type
        node.parse_exc_info = exc_info or {}
        node.parse_exc_stack = []

        if not parse_metrics_path.exists():
            node.metric = WorstMetricValue()
            node.is_buggy = True
            return MetricsPassArtifacts(
                metrics_workspace_dir=metrics_workspace_dir, metrics_task_file=metrics_task_file
            )

        node.parse_metrics_code = parse_metrics_path.read_text(encoding="utf-8", errors="replace")

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
        return MetricsPassArtifacts(
            metrics_workspace_dir=metrics_workspace_dir,
            metrics_task_file=(metrics_workspace_dir / "codex_metrics_task.md"),
        )

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
        return MetricsPassArtifacts(
            metrics_workspace_dir=metrics_workspace_dir,
            metrics_task_file=(metrics_workspace_dir / "codex_metrics_task.md"),
        )

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

    return MetricsPassArtifacts(
        metrics_workspace_dir=metrics_workspace_dir,
        metrics_task_file=(metrics_workspace_dir / "codex_metrics_task.md"),
    )


def persist_metrics_pass_artifacts(
    *,
    node: Node,
    artifacts: MetricsPassArtifacts,
) -> None:
    if not node.exp_results_dir:
        return
    exp_dir = Path(node.exp_results_dir)
    exp_dir.mkdir(parents=True, exist_ok=True)

    for rel_path in (
        "codex_metrics_task.md",
        "metrics_task_result.json",
        "parse_metrics.py",
        "codex_session.log",
        "codex_events.jsonl",
    ):
        src = artifacts.metrics_workspace_dir / rel_path
        if not src.exists():
            continue
        dst = exp_dir / f"metrics_pass__{rel_path}"
        try:
            dst.write_bytes(src.read_bytes())
        except OSError:
            logger.debug("Failed copying metrics artifact %s", rel_path, exc_info=True)
