"""
End-to-end launcher for the BFTS experiment workflow.

Steps:
- Parse CLI args and load config file
- Load the idea from config's desc_file and merge dataset reference code
- Run experiments via AgentManager (draft/debug/improve/tune/plot/ablate)
- Collect artifacts and aggregate plots
- Optionally generate the paper writeup
- Optionally perform paper review (text and images/captions/reference)
"""

import argparse
import copy
import json
import logging
import os
import os.path as osp
import pickle
import re
import shutil
import sys
import threading
import time
import traceback
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, NamedTuple, Optional, Protocol, cast

from ae_paper_review import ReviewResponseModel, ReviewResult, load_paper
from omegaconf import OmegaConf

from ai_scientist.artifact_manager import ArtifactPublisher, ArtifactSpec
from ai_scientist.latest_run_finder import normalize_run_name
from ai_scientist.perform_citations import gather_citations
from ai_scientist.perform_plotting import aggregate_plots
from ai_scientist.perform_writeup import perform_writeup
from ai_scientist.review_integration import (
    build_auto_review_context,
    perform_imgs_cap_ref_review,
    perform_review,
)
from ai_scientist.review_storage import FigureReviewRecorder, ReviewResponseRecorder
from ai_scientist.sentry_config import set_sentry_run_context
from ai_scientist.telemetry import (
    EventPersistenceManager,
    EventQueueEmitter,
    HardwareStatsReporter,
    WebhookClient,
)
from ai_scientist.treesearch import stage_control
from ai_scientist.treesearch.agent_manager import AgentManager
from ai_scientist.treesearch.codex.codex_task_types import EvaluationMetricSpec
from ai_scientist.treesearch.config import (
    Config,
    ReviewConfig,
    TelemetryConfig,
    WriteupConfig,
    apply_log_level,
    load_task_desc,
    prep_cfg,
    save_run,
)
from ai_scientist.treesearch.events import BaseEvent, GpuShortageEvent
from ai_scientist.treesearch.journal import Journal
from ai_scientist.treesearch.perform_experiments_bfts_with_agentmanager import (
    perform_experiments_bfts,
)
from ai_scientist.treesearch.stage_identifiers import StageIdentifier
from ai_scientist.treesearch.stages.base import StageMeta
from ai_scientist.treesearch.stages.stage1_baseline import Stage1Baseline
from ai_scientist.treesearch.stages.stage2_tuning import Stage2Tuning
from ai_scientist.treesearch.stages.stage3_plotting import Stage3Plotting
from ai_scientist.treesearch.stages.stage4_ablation import Stage4Ablation
from ai_scientist.treesearch.utils.serialize import load_json as load_json_dc
from management_server import (
    initialize_execution_registry,
    shutdown_execution_registry_manager,
    start_termination_server,
    stop_termination_server,
)

logger = logging.getLogger(__name__)


class TelemetryHooks(NamedTuple):
    event_callback: Callable[[BaseEvent], None]
    persistence: Optional[EventPersistenceManager]
    webhook: Optional[WebhookClient]


class ArtifactCallback(Protocol):
    def __call__(self, spec: ArtifactSpec) -> None: ...


@dataclass(frozen=True)
class RunExecutionOutcome:
    run_dir: Path
    success: bool
    message: str


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run AI scientist experiments")
    parser.add_argument(
        "config_file",
        type=str,
        help="Path to the YAML configuration file (e.g., bfts_config.yaml)",
    )
    parser.add_argument(
        "--resume",
        type=str,
        metavar="RUN_NAME_OR_NUMBER",
        help="Resume from a specific run (e.g., 4 or 4-run)",
    )
    args = parser.parse_args()

    # Validate conditional requirements
    cfg_path = Path(args.config_file)
    if not cfg_path.exists():
        parser.error(f"Configuration file not found: {cfg_path}")

    return args


def find_pdf_path_for_review(idea_dir: str, run_dir_name: str | None = None) -> str | None:
    # Look under the run-specific logs directory if provided
    search_dir = idea_dir
    if run_dir_name:
        candidate = osp.join(idea_dir, "logs", run_dir_name)
        if os.path.exists(candidate):
            search_dir = candidate
    pdf_files = [f for f in os.listdir(search_dir) if f.endswith(".pdf")]
    reflection_pdfs = [f for f in pdf_files if "reflection" in f]

    pdf_path = None  # Initialize to avoid UnboundLocalError

    if reflection_pdfs:
        # First check if there's a final version
        final_pdfs = [f for f in reflection_pdfs if "final" in f.lower()]
        if final_pdfs:
            # Use the final version if available
            pdf_path = osp.join(search_dir, final_pdfs[0])
        else:
            # Try to find numbered reflections
            reflection_nums = []
            for f in reflection_pdfs:
                match = re.search(r"reflection[_.]?(\d+)", f)
                if match:
                    reflection_nums.append((int(match.group(1)), f))

            if reflection_nums:
                # Get the file with the highest reflection number
                highest_reflection = max(reflection_nums, key=lambda x: x[0])
                pdf_path = osp.join(search_dir, highest_reflection[1])
            else:
                # Fall back to the first reflection PDF if no numbers found
                pdf_path = osp.join(search_dir, reflection_pdfs[0])
    elif pdf_files:
        # No reflection PDFs, use any PDF
        pdf_path = osp.join(search_dir, pdf_files[0])

    return pdf_path


def resolve_review_settings(*, cfg: Config) -> ReviewConfig | None:
    review_cfg = cfg.review
    if review_cfg is None:
        logger.info("No review section found in config; review step will be skipped.")
    return review_cfg


def resolve_writeup_settings(*, cfg: Config) -> WriteupConfig | None:
    writeup_cfg = cfg.writeup
    if writeup_cfg is None:
        logger.info("No writeup section found in config; default temperature will be used.")
    return writeup_cfg


def load_base_config(config_path: Path) -> Config:
    raw_cfg = OmegaConf.load(str(config_path))
    schema = OmegaConf.structured(Config)
    merged = OmegaConf.merge(schema, raw_cfg)
    cfg_obj = cast(Config, OmegaConf.to_object(merged))
    cfg_obj.desc_file = Path(cfg_obj.desc_file).resolve()
    cfg_obj.log_dir = Path(cfg_obj.log_dir).resolve()
    cfg_obj.workspace_dir = Path(cfg_obj.workspace_dir).resolve()
    return cfg_obj


def select_stage1_dir(run_dir: Path) -> Path:
    stage_dirs = sorted(
        [p for p in run_dir.iterdir() if p.is_dir() and p.name.startswith("stage_1_")]
    )
    if not stage_dirs:
        raise FileNotFoundError(f"No stage_1_* directory found under {run_dir}")
    return stage_dirs[-1]


def select_stage_dir(run_dir: Path, prefix: str) -> Path:
    stage_dirs = sorted([p for p in run_dir.iterdir() if p.is_dir() and p.name.startswith(prefix)])
    if not stage_dirs:
        raise FileNotFoundError(f"No {prefix}* directory found under {run_dir}")
    return stage_dirs[-1]


def load_cfg_from_run(run_dir: Path) -> Config:
    try:
        stage1_dir = select_stage1_dir(run_dir)
        cfg_path = stage1_dir / "config.yaml"
    except FileNotFoundError:
        stage_dirs = sorted(
            [p for p in run_dir.iterdir() if p.is_dir() and p.name.startswith("stage_")]
        )
        if not stage_dirs:
            raise
        cfg_path = stage_dirs[-1] / "config.yaml"
    if not cfg_path.exists():
        raise FileNotFoundError(str(cfg_path))
    raw = OmegaConf.load(str(cfg_path))
    schema = OmegaConf.structured(Config)
    merged = OmegaConf.merge(schema, raw)
    cfg_obj = OmegaConf.to_object(merged)
    assert isinstance(cfg_obj, Config)
    return cfg_obj


def load_stage_journal(stage_dir: Path) -> tuple[str, Journal]:
    stage_name = stage_dir.name.replace("stage_", "", 1)
    journal_path = stage_dir / "journal.json"
    if not journal_path.exists():
        raise FileNotFoundError(str(journal_path))
    journal = load_json_dc(path=journal_path, cls=Journal)
    journal.stage_name = stage_name
    return stage_name, journal


def stage_exists(run_dir: Path, prefix: str) -> bool:
    try:
        select_stage_dir(run_dir, prefix)
        return True
    except FileNotFoundError:
        return False


def all_summaries_exist(run_dir: Path) -> bool:
    paths = [
        run_dir / "draft_summary.json",
        run_dir / "baseline_summary.json",
        run_dir / "research_summary.json",
        run_dir / "ablation_summary.json",
    ]
    return all(p.exists() for p in paths)


def on_event(event: BaseEvent) -> None:
    try:
        logger.debug(event.to_dict())
    except Exception:
        traceback.print_exc()


def setup_event_pipeline(*, telemetry_cfg: TelemetryConfig | None) -> TelemetryHooks:
    started_at = time.monotonic()
    event_callback: Callable[[BaseEvent], None] = EventQueueEmitter(queue=None, fallback=on_event)
    if telemetry_cfg is None:
        return TelemetryHooks(event_callback=event_callback, persistence=None, webhook=None)

    run_identifier = telemetry_cfg.run_id.strip()
    if not run_identifier:
        logger.debug("Telemetry config missing run_id; skipping external sinks.")
        return TelemetryHooks(event_callback=event_callback, persistence=None, webhook=None)

    webhook_client: WebhookClient | None = None
    webhook_url = (telemetry_cfg.webhook_url or "").strip()
    webhook_token = (telemetry_cfg.webhook_token or "").strip()
    if webhook_url and webhook_token:
        webhook_started = time.monotonic()
        webhook_client = WebhookClient(
            base_url=webhook_url,
            token=webhook_token,
            run_id=run_identifier,
        )
        webhook_ms = int((time.monotonic() - webhook_started) * 1000)
    elif webhook_url or webhook_token:
        logger.warning("Telemetry webhook config incomplete; skipping webhook publishing.")

    if webhook_client is None:
        logger.debug("No webhook configured; using in-process logging only.")
        return TelemetryHooks(
            event_callback=event_callback,
            persistence=None,
            webhook=None,
        )

    try:
        persistence_started = time.monotonic()
        event_persistence = EventPersistenceManager(
            run_id=run_identifier,
            webhook_client=webhook_client,
        )
        persistence_init_ms = int((time.monotonic() - persistence_started) * 1000)

        start_started = time.monotonic()
        event_persistence.start()
        start_ms = int((time.monotonic() - start_started) * 1000)

        total_ms = int((time.monotonic() - started_at) * 1000)
        logger.info(
            "Telemetry init timings for run_id=%s: webhook_ms=%s persistence_init_ms=%s start_ms=%s total_ms=%s",
            run_identifier,
            locals().get("webhook_ms", 0),
            persistence_init_ms,
            start_ms,
            total_ms,
        )
        logger.info("Telemetry webhook enabled for run_id=%s", run_identifier)
        return TelemetryHooks(
            event_callback=EventQueueEmitter(queue=event_persistence.queue, fallback=on_event),
            persistence=event_persistence,
            webhook=webhook_client,
        )
    except Exception:
        logger.exception(
            "Failed to initialize telemetry webhook; continuing without external logging."
        )
        return TelemetryHooks(
            event_callback=event_callback, persistence=None, webhook=webhook_client
        )


@dataclass
class _EventCallbackWrapper:
    base_callback: Callable[[BaseEvent], None]
    webhook_client: WebhookClient | None

    def __call__(self, event: BaseEvent) -> None:
        if isinstance(event, GpuShortageEvent):
            _handle_gpu_shortage_event(event=event, webhook_client=self.webhook_client)
        self.base_callback(event)


def _augment_event_callback(
    base_callback: Callable[[BaseEvent], None],
    *,
    webhook_client: WebhookClient | None,
) -> Callable[[BaseEvent], None]:
    return _EventCallbackWrapper(base_callback=base_callback, webhook_client=webhook_client)


def _handle_gpu_shortage_event(
    *,
    event: GpuShortageEvent,
    webhook_client: WebhookClient | None,
) -> None:
    logger.error(
        "GPU shortage detected: required=%s available=%s",
        event.required_gpus,
        event.available_gpus,
    )
    if webhook_client is None:
        logger.warning("Telemetry webhook not configured; cannot notify server about GPU shortage.")
        return
    try:
        shortage_future = webhook_client.publish_gpu_shortage(
            required_gpus=event.required_gpus,
            available_gpus=event.available_gpus,
            message=event.message,
        )
        shortage_future.result(timeout=None)
    except Exception:
        logger.exception("Failed to publish GPU shortage notification.")


def setup_artifact_publisher(
    *, telemetry_cfg: TelemetryConfig, webhook_client: WebhookClient | None
) -> tuple[ArtifactPublisher, ArtifactCallback]:
    webhook_url = os.environ.get("TELEMETRY_WEBHOOK_URL")
    webhook_token = os.environ.get("TELEMETRY_WEBHOOK_TOKEN")

    if not webhook_url or not webhook_token:
        logger.error(
            "Missing TELEMETRY_WEBHOOK_URL or TELEMETRY_WEBHOOK_TOKEN; artifact publishing disabled."
        )
        raise ValueError("Missing TELEMETRY_WEBHOOK_URL or TELEMETRY_WEBHOOK_TOKEN")

    publisher = ArtifactPublisher(
        run_id=telemetry_cfg.run_id,
        webhook_base_url=webhook_url,
        webhook_token=webhook_token,
        webhook_client=webhook_client,
    )

    def _callback(spec: ArtifactSpec) -> None:
        publisher.publish(spec=spec)

    return publisher, _callback


def resume_run(
    base_cfg: Config,
    resume_arg: str,
    event_callback: Callable[[BaseEvent], None],
) -> RunExecutionOutcome:
    try:
        logs_root = base_cfg.log_dir
        raw_exp_name = base_cfg.exp_name
        exp_name = str(raw_exp_name) if raw_exp_name else "run"
        run_name = normalize_run_name(run_arg=resume_arg, exp_name=exp_name)
        run_dir = (logs_root / run_name).resolve()
        if not run_dir.exists():
            raise FileNotFoundError(str(run_dir))

        cfg_obj = load_cfg_from_run(run_dir=run_dir)
        cfg_obj = prep_cfg(cfg=cfg_obj)
        if all_summaries_exist(run_dir=run_dir):
            logger.info(
                "All summary files found; skipping stage execution and proceeding to reports."
            )
            return RunExecutionOutcome(run_dir=run_dir, success=True, message="")

        s1 = stage_exists(run_dir=run_dir, prefix="stage_1_")
        s2 = stage_exists(run_dir=run_dir, prefix="stage_2_")
        s3 = stage_exists(run_dir=run_dir, prefix="stage_3_")
        s4 = stage_exists(run_dir=run_dir, prefix="stage_4_")

        next_stage: int | None = None
        if s1 and not s2:
            next_stage = 2
        elif s2 and not s3:
            next_stage = 3
        elif s3 and not s4:
            next_stage = 4

        if next_stage is None:
            return RunExecutionOutcome(run_dir=run_dir, success=True, message="")

        # Load task description from the run's research_idea.md file
        fake_config = copy.deepcopy(cfg_obj)
        idea_md_path = run_dir / "research_idea.md"
        if not idea_md_path.exists():
            raise FileNotFoundError(f"research_idea.md not found in run directory: {run_dir}")
        fake_config.desc_file = idea_md_path
        task_desc = load_task_desc(cfg=fake_config)

        # Load title from the run's research_title.txt file
        title_path = run_dir / "research_title.txt"
        if not title_path.exists():
            raise FileNotFoundError(f"research_title.txt not found in run directory: {run_dir}")
        title = title_path.read_text(encoding="utf-8").strip()

        evaluation_metric_spec = load_evaluation_metric_spec_from_checkpoint(run_dir=run_dir)
        manager = AgentManager(
            title=title,
            task_desc=task_desc,
            cfg=cfg_obj,
            workspace_dir=Path(cfg_obj.workspace_dir),
            event_callback=event_callback,
            evaluation_metric_spec=evaluation_metric_spec,
        )

        if s1:
            stage1_dir = select_stage_dir(run_dir=run_dir, prefix="stage_1_")
            stage1_name, stage1_journal = load_stage_journal(stage_dir=stage1_dir)
            if cfg_obj.telemetry:
                stage1_journal.run_id = cfg_obj.telemetry.run_id
            identifier = StageIdentifier.STAGE1
            if stage1_name != identifier.prefixed_name:
                logger.warning(
                    "Stage 1 journal name %s did not match expected identifier %s",
                    stage1_name,
                    identifier.prefixed_name,
                )
            stage1_meta = StageMeta(
                identifier=identifier,
                goals=Stage1Baseline.DEFAULT_GOALS,
                max_iterations=manager.get_max_iterations(stage_identifier=identifier),
                num_drafts=0,
            )
            manager.stages.append(stage1_meta)
            manager.register_phase_definition(stage_meta=stage1_meta)
            manager.journals[stage1_meta.name] = stage1_journal

        if s2 or (next_stage and next_stage > 2):
            try:
                stage2_dir = select_stage_dir(run_dir=run_dir, prefix="stage_2_")
                stage2_name, stage2_journal = load_stage_journal(stage_dir=stage2_dir)
                if cfg_obj.telemetry:
                    stage2_journal.run_id = cfg_obj.telemetry.run_id
                identifier = StageIdentifier.STAGE2
                if stage2_name != identifier.prefixed_name:
                    logger.warning(
                        "Stage 2 journal name %s did not match expected identifier %s",
                        stage2_name,
                        identifier.prefixed_name,
                    )
                stage2_meta = StageMeta(
                    identifier=identifier,
                    goals=Stage2Tuning.DEFAULT_GOALS,
                    max_iterations=manager.get_max_iterations(stage_identifier=identifier),
                    num_drafts=0,
                )
                manager.stages.append(stage2_meta)
                manager.register_phase_definition(stage_meta=stage2_meta)
                manager.journals[stage2_meta.name] = stage2_journal
            except FileNotFoundError:
                pass

        if s3 or (next_stage and next_stage > 3):
            try:
                stage3_dir = select_stage_dir(run_dir=run_dir, prefix="stage_3_")
                stage3_name, stage3_journal = load_stage_journal(stage_dir=stage3_dir)
                if cfg_obj.telemetry:
                    stage3_journal.run_id = cfg_obj.telemetry.run_id
                identifier = StageIdentifier.STAGE3
                if stage3_name != identifier.prefixed_name:
                    logger.warning(
                        "Stage 3 journal name %s did not match expected identifier %s",
                        stage3_name,
                        identifier.prefixed_name,
                    )
                stage3_meta = StageMeta(
                    identifier=identifier,
                    goals=Stage3Plotting.DEFAULT_GOALS,
                    max_iterations=manager.get_max_iterations(stage_identifier=identifier),
                    num_drafts=0,
                )
                manager.stages.append(stage3_meta)
                manager.register_phase_definition(stage_meta=stage3_meta)
                manager.journals[stage3_meta.name] = stage3_journal
            except FileNotFoundError:
                pass

        if next_stage == 2:
            next_identifier = StageIdentifier.STAGE2
            next_goals = Stage2Tuning.DEFAULT_GOALS
        elif next_stage == 3:
            next_identifier = StageIdentifier.STAGE3
            next_goals = Stage3Plotting.DEFAULT_GOALS
        else:
            next_identifier = StageIdentifier.STAGE4
            next_goals = Stage4Ablation.DEFAULT_GOALS

        next_meta = StageMeta(
            identifier=next_identifier,
            goals=next_goals,
            max_iterations=manager.get_max_iterations(stage_identifier=next_identifier),
            num_drafts=0,
        )

        manager.stages.append(next_meta)
        manager.register_phase_definition(stage_meta=next_meta)
        manager.current_stage = next_meta
        manager.journals[next_meta.name] = Journal(
            summary_model=cfg_obj.report.model,
            node_selection_model=cfg_obj.agent.feedback.model,
            summary_temperature=cfg_obj.report.temperature,
            node_selection_temperature=cfg_obj.agent.feedback.temperature,
            event_callback=event_callback,
            stage_name=next_meta.name,
            run_id=cfg_obj.telemetry.run_id if cfg_obj.telemetry else None,
        )

        def step_callback(stage: StageMeta, journal: Journal) -> None:
            try:
                save_run(cfg=cfg_obj, journal=journal, stage_name=stage.name)
            except Exception:
                traceback.print_exc()

        manager.run_stage(
            initial_substage=next_meta,
            step_callback=step_callback,
        )
        outcome = manager.get_run_outcome()
        return RunExecutionOutcome(
            run_dir=run_dir, success=outcome.success, message=outcome.message
        )
    except Exception:
        logger.exception("Resume failed; exiting.")
        sys.exit(1)


def load_evaluation_metric_spec_from_checkpoint(*, run_dir: Path) -> EvaluationMetricSpec:
    stage_dirs = sorted(
        [p for p in run_dir.iterdir() if p.is_dir() and p.name.startswith("stage_")],
        key=lambda p: p.name,
        reverse=True,
    )
    for stage_dir in stage_dirs:
        checkpoint_path = stage_dir / "checkpoint.pkl"
        if not checkpoint_path.exists():
            continue
        with open(checkpoint_path, "rb") as f:
            checkpoint = pickle.load(f)
        if not isinstance(checkpoint, dict):
            raise ValueError(f"Invalid checkpoint format at {checkpoint_path}")
        spec = checkpoint.get("evaluation_metric_spec")
        if not isinstance(spec, EvaluationMetricSpec):
            raise ValueError(f"Missing evaluation_metric_spec in {checkpoint_path}")
        return spec
    raise FileNotFoundError(f"No checkpoint.pkl found under {run_dir}")


def determine_run_directory(
    top_log_dir: Path, existing_runs_before: set[str], resume_run_dir: Path | None
) -> Path | None:
    if resume_run_dir is not None:
        return resume_run_dir
    try:
        new_runs = [
            p for p in top_log_dir.iterdir() if p.is_dir() and p.name not in existing_runs_before
        ]
        if new_runs:
            return max(new_runs, key=lambda p: p.stat().st_mtime)
        candidates = [p for p in top_log_dir.iterdir() if p.is_dir()]
        return max(candidates, key=lambda p: p.stat().st_mtime) if candidates else None
    except Exception:
        traceback.print_exc()
        return None


def should_generate_reports(run_dir_path: Path | None) -> bool:
    if run_dir_path is None:
        return False
    try:
        has_stage3_best = any(run_dir_path.glob("stage_3_*/best_solution_*.py"))
        if has_stage3_best:
            return True
        logger.error("No Stage 3 best_solution files found; skipping plot aggregation and writeup.")
    except Exception:
        traceback.print_exc()
        logger.warning(
            "Could not scan for best_solution files; skipping plot aggregation and writeup."
        )
    return False


def has_aggregated_plots(*, reports_base: str, run_dir_path: Path) -> bool:
    figures_dir = Path(reports_base) / "figures" / run_dir_path.name
    if not figures_dir.exists():
        return False
    return any(p.is_file() for p in figures_dir.glob("*.png"))


def has_writeup_pdf(*, reports_base: str, run_dir_path: Path) -> bool:
    run_out_dir = Path(reports_base) / "logs" / run_dir_path.name
    if not run_out_dir.exists():
        return False
    return any(p.is_file() for p in run_out_dir.glob("*.pdf"))


def has_review_outputs(*, reports_base: str, run_dir_path: Path) -> bool:
    run_out_dir = Path(reports_base) / "logs" / run_dir_path.name
    if not run_out_dir.exists():
        return False
    review_text = run_out_dir / "review_text.json"
    review_imgs = run_out_dir / "review_img_cap_ref.json"
    return review_text.exists() and review_imgs.exists()


def run_plot_aggregation(
    writeup_cfg: WriteupConfig,
    reports_base: str,
    run_dir_path: Path | None,
    artifact_callback: ArtifactCallback,
    event_callback: Callable[[BaseEvent], None] | None = None,
    run_id: str | None = None,
) -> bool:
    try:
        aggregate_plots(
            base_folder=reports_base,
            model=writeup_cfg.plot_model,
            temperature=writeup_cfg.temperature,
            run_dir_name=run_dir_path.name if run_dir_path is not None else None,
            event_callback=event_callback,
            run_id=run_id,
        )
        try:
            if run_dir_path is None:
                raise ValueError("run_dir_path is required to archive plots.")
            figures_dir = Path(reports_base) / "figures" / run_dir_path.name
            if not figures_dir.exists():
                raise FileNotFoundError(f"figures directory missing: {figures_dir}")
            plot_paths = sorted(p for p in figures_dir.glob("*.png") if p.is_file())
            if not plot_paths:
                logger.warning("No plot files found to upload in %s", figures_dir)
            for plot_path in plot_paths:
                artifact_callback(
                    ArtifactSpec(
                        artifact_type="plot",
                        path=plot_path,
                        packaging="file",
                        archive_name=None,
                        exclude_dir_names=(),
                    )
                )
        except Exception:
            logger.exception("Failed to record plots archive artifact for %s", run_dir_path)
        return True
    except Exception as e:
        logger.warning(f"Aggregate plots failed: {e}. Skipping writeup.")
        traceback.print_exc()
        return False


def run_writeup_stage(
    writeup_cfg: WriteupConfig,
    reports_base: str,
    run_dir_path: Path,
    artifact_callback: ArtifactCallback,
    codex_timeout_seconds: int,
    event_callback: Callable[[BaseEvent], None] | None = None,
    run_id: str | None = None,
) -> None:

    writeup_retries = writeup_cfg.writeup_retries
    num_cite_rounds = writeup_cfg.num_cite_rounds
    writeup_model = writeup_cfg.model
    citation_model = writeup_cfg.citation_model or writeup_model
    base_path = Path(reports_base)
    logs_dir = base_path / "logs"
    run_dir_name = run_dir_path.name

    citations_text = gather_citations(
        base_path=base_path,
        logs_dir=logs_dir,
        model=citation_model,
        temperature=writeup_cfg.temperature,
        num_cite_rounds=num_cite_rounds,
        run_dir_name=run_dir_name,
    )
    writeup_success = False
    last_error: Exception | None = None
    for attempt in range(writeup_retries):
        logger.info(f"Writeup attempt {attempt + 1} of {writeup_retries}")
        try:
            writeup_success = perform_writeup(
                base_folder=reports_base,
                model=writeup_model,
                temperature=writeup_cfg.temperature,
                run_dir_name=run_dir_name,
                num_cite_rounds=num_cite_rounds,
                max_refinement_rounds=writeup_cfg.max_refinement_rounds,
                page_limit=writeup_cfg.page_limit,
                codex_timeout_seconds=codex_timeout_seconds,
                writeup_attempt=attempt,
                citations_text=citations_text,
                event_callback=event_callback,
                run_id=run_id,
            )
        except Exception as exc:
            last_error = exc
            logger.exception("Writeup attempt %s failed.", attempt + 1)
            continue
        if writeup_success:
            break

    if not writeup_success:
        error_message = "Writeup process did not complete successfully after all retries."
        logger.error(error_message)
        if last_error is not None:
            raise RuntimeError(error_message) from last_error
        raise RuntimeError(error_message)

    run_out_dir = Path(reports_base) / "logs" / run_dir_path.name
    latex_path = run_out_dir / "latex"
    pdf_paths = sorted(run_out_dir.glob("*.pdf"))
    for pdf_path in pdf_paths:
        try:
            artifact_callback(
                ArtifactSpec(
                    artifact_type="paper_pdf",
                    path=pdf_path,
                    packaging="file",
                    archive_name=None,
                    exclude_dir_names=(),
                )
            )
        except Exception:
            logger.exception("Failed to upload PDF artifact: %s", pdf_path)
    if latex_path.exists():
        try:
            artifact_callback(
                ArtifactSpec(
                    artifact_type="latex_archive",
                    path=latex_path,
                    packaging="zip",
                    archive_name=f"{run_dir_path.name}-latex.zip",
                    exclude_dir_names=(),
                )
            )
        except Exception:
            logger.exception("Failed to upload LaTeX archive artifact: %s", latex_path)


def run_review_stage(
    review_cfg: ReviewConfig,
    reports_base: str,
    run_dir_path: Path,
    artifact_callback: ArtifactCallback,
    telemetry_cfg: TelemetryConfig | None,
    event_callback: Callable[[BaseEvent], None] | None = None,
    run_id: str | None = None,
    webhook_client: WebhookClient | None = None,
) -> None:
    pdf_path = find_pdf_path_for_review(
        idea_dir=reports_base,
        run_dir_name=run_dir_path.name if run_dir_path is not None else None,
    )
    if not pdf_path or not os.path.exists(pdf_path):
        logger.warning("No PDF found for review (writeup likely failed). Skipping review.")
        return

    logger.info(f"Paper found at: {pdf_path}")
    paper_content = load_paper(pdf_path)
    review_model = review_cfg.model
    review_context = build_auto_review_context(reports_base, None, paper_content or "")
    review_result = perform_review(
        text=paper_content,
        model=review_model,
        temperature=review_cfg.temperature,
        context=review_context,
        num_reviews_ensemble=3,
        num_reflections=2,
        event_callback=event_callback,
        run_id=run_id,
    )
    if not isinstance(review_result, ReviewResult):
        raise TypeError("perform_review must return ReviewResult")
    review: ReviewResponseModel = review_result.review
    review_img_cap_ref = perform_imgs_cap_ref_review(
        model=review_model,
        pdf_path=pdf_path,
        temperature=review_cfg.temperature,
    )
    serialized_img_reviews = [
        {
            "figure_name": item.figure_name,
            "review": item.review.model_dump(by_alias=True),
        }
        for item in review_img_cap_ref
    ]
    review_out_dir = (
        osp.join(reports_base, "logs", run_dir_path.name)
        if run_dir_path is not None
        else reports_base
    )
    os.makedirs(review_out_dir, exist_ok=True)
    review_json_path = Path(review_out_dir) / "review_text.json"
    review_json_path.write_text(
        json.dumps(review.model_dump(by_alias=True), indent=4),
        encoding="utf-8",
    )
    review_img_path = Path(review_out_dir) / "review_img_cap_ref.json"
    review_img_path.write_text(json.dumps(serialized_img_reviews, indent=4), encoding="utf-8")
    try:
        artifact_callback(
            ArtifactSpec(
                artifact_type="llm_review",
                path=review_json_path,
                packaging="file",
                archive_name=None,
                exclude_dir_names=(),
            )
        )
    except Exception:
        logger.exception("Failed to upload review JSON artifact: %s", review_json_path)

    if telemetry_cfg and webhook_client:
        try:
            recorder = ReviewResponseRecorder.from_webhook_client(
                run_id=telemetry_cfg.run_id,
                webhook_client=webhook_client,
            )
            recorder.insert_review(review=review, source_path=review_json_path)
            figure_recorder = FigureReviewRecorder.from_webhook_client(
                run_id=telemetry_cfg.run_id,
                webhook_client=webhook_client,
            )
            figure_recorder.insert_reviews(
                reviews=review_img_cap_ref,
                source_path=review_img_path,
            )
        except Exception:
            logger.exception("Failed to publish review data via webhook.")
    logger.info("Paper review completed.")


def execute_launcher(args: argparse.Namespace) -> None:
    base_config_path = Path(args.config_file)
    base_cfg = load_base_config(config_path=base_config_path)
    if base_cfg.telemetry and base_cfg.telemetry.run_id:
        set_sentry_run_context(run_id=base_cfg.telemetry.run_id)
    workspace_dir = base_cfg.workspace_dir
    os.environ["WORKSPACE_DIR"] = str(workspace_dir)
    apply_log_level(level_name=str(base_cfg.log_level))
    top_log_dir = base_cfg.log_dir
    top_log_dir.mkdir(parents=True, exist_ok=True)

    existing_runs_before = {p.name for p in top_log_dir.iterdir() if p.is_dir()}
    reports_base = str(top_log_dir.parent.resolve())

    writeup_cfg = resolve_writeup_settings(cfg=base_cfg)
    writeup_enabled = writeup_cfg is not None
    if not writeup_enabled:
        logger.info("No writeup section found in config; writeup and review steps will be skipped.")

    review_cfg = resolve_review_settings(cfg=base_cfg)
    review_enabled = writeup_enabled and review_cfg is not None
    if review_cfg is not None and not writeup_enabled:
        logger.info("Review configuration provided but writeup is disabled; skipping review.")

    stage_control.reset_stage_state()
    initialize_execution_registry()
    try:
        start_termination_server(host="127.0.0.1", port=8090)
    except Exception:
        logger.exception("Failed to start termination server; continuing without it.")

    telemetry_hooks = setup_event_pipeline(telemetry_cfg=base_cfg.telemetry)
    event_persistence = telemetry_hooks.persistence
    webhook_client = telemetry_hooks.webhook
    event_callback = _augment_event_callback(
        telemetry_hooks.event_callback,
        webhook_client=webhook_client,
    )
    stage_control.register_event_callback(event_callback)
    artifact_callback: ArtifactCallback
    if base_cfg.telemetry is not None:
        artifact_publisher, artifact_callback = setup_artifact_publisher(
            telemetry_cfg=base_cfg.telemetry,
            webhook_client=webhook_client,
        )
    else:
        artifact_publisher = None

        def _noop_artifact_callback(spec: ArtifactSpec) -> None:
            del spec
            return

        artifact_callback = _noop_artifact_callback

    heartbeat_thread: threading.Thread | None = None
    heartbeat_stop: threading.Event | None = None
    hw_stats_reporter: HardwareStatsReporter | None = None
    if webhook_client is not None:
        try:
            webhook_client.publish_run_started()
        except Exception:
            logger.exception("Failed to notify run start.")
        heartbeat_stop = threading.Event()

        def heartbeat_loop() -> None:
            while not heartbeat_stop.wait(60):
                try:
                    webhook_client.publish_heartbeat()
                except Exception:
                    logger.exception("Failed to publish telemetry heartbeat.")

        heartbeat_thread = threading.Thread(target=heartbeat_loop, daemon=True)
        heartbeat_thread.start()

        hw_paths_env = os.environ.get("COLLECT_DISK_STATS_PATHS")
        hw_paths = (
            [path.strip() for path in hw_paths_env.split(",") if path.strip()]
            if hw_paths_env
            else []
        )
        if hw_paths:
            hw_interval = int(os.environ.get("HW_STATS_INTERVAL_SECONDS", "600"))
            hw_stats_reporter = HardwareStatsReporter(
                webhook_client=webhook_client,
                paths=hw_paths,
                interval_seconds=hw_interval,
            )
            hw_stats_reporter.start()

    run_success = True
    failure_message = ""
    try:
        resume_outcome: RunExecutionOutcome | None = None
        if args.resume is not None:
            resume_outcome = resume_run(
                base_cfg=base_cfg,
                resume_arg=args.resume,
                event_callback=event_callback,
            )
            run_success = resume_outcome.success
            failure_message = resume_outcome.message
        else:
            outcome = perform_experiments_bfts(
                base_config_path, event_callback, title=base_cfg.title
            )
            run_success = outcome.success
            failure_message = outcome.message

        run_dir_path = determine_run_directory(
            top_log_dir=top_log_dir,
            existing_runs_before=existing_runs_before,
            resume_run_dir=resume_outcome.run_dir if resume_outcome is not None else None,
        )

        # Copy the research idea markdown and title to the run directory
        if run_dir_path is not None:
            try:
                source_idea_path = Path(base_cfg.desc_file)
                dest_idea_path = run_dir_path / "research_idea.md"
                shutil.copy2(source_idea_path, dest_idea_path)
                logger.info(f"Copied research idea from {source_idea_path} to {dest_idea_path}")
            except Exception:
                traceback.print_exc()
                logger.warning(
                    "Failed to copy research_idea.md to run directory; continuing without it."
                )

            try:
                title_path = run_dir_path / "research_title.txt"
                title_path.write_text(base_cfg.title, encoding="utf-8")
                logger.info(f"Wrote research title to {title_path}")
            except Exception:
                traceback.print_exc()
                logger.warning(
                    "Failed to write research_title.txt to run directory; continuing without it."
                )

        run_id = base_cfg.telemetry.run_id if base_cfg.telemetry else None
        if writeup_cfg is not None and run_dir_path is not None:
            agg_ok = True
            if has_aggregated_plots(reports_base=reports_base, run_dir_path=run_dir_path):
                logger.info(
                    "Existing aggregated plots detected for %s; skipping plot aggregation.",
                    run_dir_path.name,
                )
            else:
                agg_ok = run_plot_aggregation(
                    writeup_cfg=writeup_cfg,
                    reports_base=reports_base,
                    run_dir_path=run_dir_path,
                    artifact_callback=artifact_callback,
                    event_callback=event_callback,
                    run_id=run_id,
                )

            if has_writeup_pdf(reports_base=reports_base, run_dir_path=run_dir_path):
                logger.info(
                    "Existing writeup PDF detected for %s; skipping writeup stage.",
                    run_dir_path.name,
                )
            elif agg_ok:
                run_writeup_stage(
                    writeup_cfg=writeup_cfg,
                    reports_base=reports_base,
                    run_dir_path=run_dir_path,
                    artifact_callback=artifact_callback,
                    codex_timeout_seconds=base_cfg.exec.timeout,
                    event_callback=event_callback,
                    run_id=run_id,
                )

            if review_enabled and review_cfg is not None:
                if has_review_outputs(reports_base=reports_base, run_dir_path=run_dir_path):
                    logger.info(
                        "Existing review outputs detected for %s; skipping review stage.",
                        run_dir_path.name,
                    )
                else:
                    run_review_stage(
                        review_cfg=review_cfg,
                        reports_base=reports_base,
                        run_dir_path=run_dir_path,
                        artifact_callback=artifact_callback,
                        telemetry_cfg=base_cfg.telemetry,
                        event_callback=event_callback,
                        run_id=run_id,
                        webhook_client=webhook_client,
                    )

        if artifact_callback is not None and run_dir_path is not None:
            # This call is also performed by the server before terminating the pod.
            # But we want to be sure to upload the log file and workspace archive.
            artifact_callback(
                ArtifactSpec(
                    artifact_type="workspace_archive",
                    path=Path(base_cfg.workspace_dir),
                    packaging="zip",
                    archive_name="workspace.zip",
                    exclude_dir_names=(
                        ".ai_scientist_venv",
                        ".venv",
                        "__pycache__",
                        ".git",
                        "node_modules",
                        ".cache",
                        ".pytest_cache",
                        ".mypy_cache",
                        ".ruff_cache",
                    ),
                )
            )
            artifact_callback(
                ArtifactSpec(
                    artifact_type="run_log",
                    path=Path("/workspace/research_pipeline.log"),
                    packaging="file",
                    archive_name=None,
                    exclude_dir_names=(),
                )
            )

        logger.info("Finished running the experiment.")
    except Exception as exc:
        run_success = False
        failure_message = str(exc)
        raise
    finally:
        try:
            if webhook_client is not None:
                try:
                    message = failure_message.strip() or None
                    run_finished_future = webhook_client.publish_run_finished(
                        success=run_success,
                        message=message,
                    )
                    run_finished_future.result(timeout=None)
                except Exception:
                    logger.exception("Failed to publish run finished notification.")
            if heartbeat_stop is not None:
                heartbeat_stop.set()
            if heartbeat_thread is not None:
                heartbeat_thread.join(timeout=5)
            if event_persistence is not None:
                event_persistence.stop()
            if hw_stats_reporter is not None:
                hw_stats_reporter.stop()
            if artifact_publisher is not None:
                artifact_publisher.close()
            stop_termination_server()
            shutdown_execution_registry_manager()
            stage_control.clear_stage_state()
        except Exception:
            logger.exception("Encountered an error while cleaning up the research pipeline run.")


def main() -> None:
    args = parse_arguments()
    cfg_path = Path(args.config_file)
    try:
        config_text = cfg_path.read_text(encoding="utf-8")
    except Exception as exc:
        logger.error("Failed to read config file %s: %s", cfg_path, exc)
        raise
    logger.info("Launching AE Scientist with config file %s\n%s", cfg_path, config_text)
    execute_launcher(args)


if __name__ == "__main__":
    main()
