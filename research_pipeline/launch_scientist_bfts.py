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
import re
import shutil
import sys
import threading
import traceback
from pathlib import Path
from typing import Callable, NamedTuple, Optional, cast

from omegaconf import OmegaConf

from ai_scientist.latest_run_finder import normalize_run_name
from ai_scientist.llm import token_tracker
from ai_scientist.perform_icbinb_writeup import gather_citations
from ai_scientist.perform_icbinb_writeup import perform_writeup as perform_icbinb_writeup
from ai_scientist.perform_llm_review import load_paper, perform_review
from ai_scientist.perform_plotting import aggregate_plots
from ai_scientist.perform_vlm_review import perform_imgs_cap_ref_review
from ai_scientist.perform_writeup import perform_writeup
from ai_scientist.review_context import build_auto_review_context
from ai_scientist.telemetry import EventPersistenceManager, EventQueueEmitter, WebhookClient
from ai_scientist.treesearch.agent_manager import AgentManager
from ai_scientist.treesearch.bfts_utils import idea_to_markdown
from ai_scientist.treesearch.events import BaseEvent
from ai_scientist.treesearch.interpreter import ExecutionResult
from ai_scientist.treesearch.journal import Journal
from ai_scientist.treesearch.perform_experiments_bfts_with_agentmanager import (
    perform_experiments_bfts,
)
from ai_scientist.treesearch.stages.base import StageMeta
from ai_scientist.treesearch.stages.stage1_baseline import Stage1Baseline
from ai_scientist.treesearch.stages.stage2_tuning import Stage2Tuning
from ai_scientist.treesearch.stages.stage3_plotting import Stage3Plotting
from ai_scientist.treesearch.stages.stage4_ablation import Stage4Ablation
from ai_scientist.treesearch.utils.config import (
    Config,
    ReviewConfig,
    TelemetryConfig,
    WriteupConfig,
    apply_log_level,
    load_task_desc,
    prep_cfg,
    save_run,
)
from ai_scientist.treesearch.utils.serialize import load_json as load_json_dc

logger = logging.getLogger(__name__)


class TelemetryHooks(NamedTuple):
    event_callback: Callable[[BaseEvent], None]
    persistence: Optional[EventPersistenceManager]
    webhook: Optional[WebhookClient]


def save_token_tracker(idea_dir: str) -> None:
    try:
        with open(osp.join(idea_dir, "token_tracker.json"), "w") as f:
            json.dump(token_tracker.get_summary(), f)
    except Exception:
        traceback.print_exc()
    try:
        with open(osp.join(idea_dir, "token_tracker_interactions.json"), "w") as f:
            json.dump(token_tracker.get_interactions(), f)
    except Exception:
        traceback.print_exc()


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
    event_callback: Callable[[BaseEvent], None] = EventQueueEmitter(queue=None, fallback=on_event)
    if telemetry_cfg is None:
        return TelemetryHooks(event_callback=event_callback, persistence=None, webhook=None)

    run_identifier = telemetry_cfg.run_id.strip()
    if not run_identifier:
        logger.debug("Telemetry config missing run_id; skipping external sinks.")
        return TelemetryHooks(event_callback=event_callback, persistence=None, webhook=None)

    db_url = telemetry_cfg.database_url.strip()
    webhook_client: WebhookClient | None = None
    webhook_url = (telemetry_cfg.webhook_url or "").strip()
    webhook_token = (telemetry_cfg.webhook_token or "").strip()
    if webhook_url and webhook_token:
        webhook_client = WebhookClient(
            base_url=webhook_url,
            token=webhook_token,
            run_id=run_identifier,
        )
    elif webhook_url or webhook_token:
        logger.warning("Telemetry webhook config incomplete; skipping webhook publishing.")

    if not db_url and webhook_client is None:
        logger.debug("No telemetry sinks configured; using in-process logging only.")
        return TelemetryHooks(
            event_callback=event_callback,
            persistence=None,
            webhook=webhook_client,
        )

    try:
        event_persistence = EventPersistenceManager(
            database_url=db_url or None,
            run_id=run_identifier,
            webhook_client=webhook_client,
        )
        event_persistence.start()
        logger.info("Telemetry sinks enabled for run_id=%s", run_identifier)
        return TelemetryHooks(
            event_callback=EventQueueEmitter(queue=event_persistence.queue, fallback=on_event),
            persistence=event_persistence,
            webhook=webhook_client,
        )
    except Exception:
        logger.exception(
            "Failed to initialize telemetry sinks; continuing without external logging."
        )
        return TelemetryHooks(
            event_callback=event_callback, persistence=None, webhook=webhook_client
        )


def resume_run(
    base_cfg: Config,
    idea_json_path: str,
    resume_arg: str,
    event_callback: Callable[[BaseEvent], None],
) -> Path:
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
            return run_dir

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
            return run_dir

        fake_config = copy.deepcopy(cfg_obj)
        fake_config.desc_file = Path(idea_json_path)
        task_desc = load_task_desc(cfg=fake_config)

        manager = AgentManager(
            task_desc=task_desc,
            cfg=cfg_obj,
            workspace_dir=Path(cfg_obj.workspace_dir),
            event_callback=event_callback,
        )

        if s1:
            stage1_dir = select_stage_dir(run_dir=run_dir, prefix="stage_1_")
            stage1_name, stage1_journal = load_stage_journal(stage_dir=stage1_dir)
            stage1_meta = StageMeta(
                name=stage1_name,
                number=1,
                slug=Stage1Baseline.MAIN_STAGE_SLUG,
                substage_number=1,
                substage_name="preliminary",
                goals=Stage1Baseline.DEFAULT_GOALS,
                max_iterations=manager.get_max_iterations(1),
                num_drafts=0,
            )
            manager.stages.append(stage1_meta)
            manager.journals[stage1_meta.name] = stage1_journal

        if s2 or (next_stage and next_stage > 2):
            try:
                stage2_dir = select_stage_dir(run_dir=run_dir, prefix="stage_2_")
                stage2_name, stage2_journal = load_stage_journal(stage_dir=stage2_dir)
                stage2_meta = StageMeta(
                    name=stage2_name,
                    number=2,
                    slug=Stage2Tuning.MAIN_STAGE_SLUG,
                    substage_number=1,
                    substage_name="first_attempt",
                    goals=Stage2Tuning.DEFAULT_GOALS,
                    max_iterations=manager.get_max_iterations(2),
                    num_drafts=0,
                )
                manager.stages.append(stage2_meta)
                manager.journals[stage2_meta.name] = stage2_journal
            except FileNotFoundError:
                pass

        if s3 or (next_stage and next_stage > 3):
            try:
                stage3_dir = select_stage_dir(run_dir=run_dir, prefix="stage_3_")
                stage3_name, stage3_journal = load_stage_journal(stage_dir=stage3_dir)
                stage3_meta = StageMeta(
                    name=stage3_name,
                    number=3,
                    slug=Stage3Plotting.MAIN_STAGE_SLUG,
                    substage_number=1,
                    substage_name="first_attempt",
                    goals=Stage3Plotting.DEFAULT_GOALS,
                    max_iterations=manager.get_max_iterations(3),
                    num_drafts=0,
                )
                manager.stages.append(stage3_meta)
                manager.journals[stage3_meta.name] = stage3_journal
            except FileNotFoundError:
                pass

        if next_stage == 2:
            next_meta = StageMeta(
                name="2_" + Stage2Tuning.MAIN_STAGE_SLUG + "_1_first_attempt",
                number=2,
                slug=Stage2Tuning.MAIN_STAGE_SLUG,
                substage_number=1,
                substage_name="first_attempt",
                goals=Stage2Tuning.DEFAULT_GOALS,
                max_iterations=manager.get_max_iterations(2),
                num_drafts=0,
            )
        elif next_stage == 3:
            next_meta = StageMeta(
                name="3_" + Stage3Plotting.MAIN_STAGE_SLUG + "_1_first_attempt",
                number=3,
                slug=Stage3Plotting.MAIN_STAGE_SLUG,
                substage_number=1,
                substage_name="first_attempt",
                goals=Stage3Plotting.DEFAULT_GOALS,
                max_iterations=manager.get_max_iterations(3),
                num_drafts=0,
            )
        else:
            next_meta = StageMeta(
                name="4_" + Stage4Ablation.MAIN_STAGE_SLUG + "_1_first_attempt",
                number=4,
                slug=Stage4Ablation.MAIN_STAGE_SLUG,
                substage_number=1,
                substage_name="first_attempt",
                goals=Stage4Ablation.DEFAULT_GOALS,
                max_iterations=manager.get_max_iterations(4),
                num_drafts=0,
            )

        manager.stages.append(next_meta)
        manager.current_stage = next_meta
        manager.journals[next_meta.name] = Journal(
            summary_model=cfg_obj.report.model,
            node_selection_model=cfg_obj.agent.feedback.model,
            summary_temperature=cfg_obj.report.temp,
            node_selection_temperature=cfg_obj.agent.feedback.temp,
            event_callback=event_callback,
        )

        def step_callback(stage: StageMeta, journal: Journal) -> None:
            try:
                save_run(cfg=cfg_obj, journal=journal, stage_name=f"stage_{stage.name}")
            except Exception:
                traceback.print_exc()

        def exec_callback(_code: str, _is_exec: bool) -> ExecutionResult:
            return ExecutionResult(term_out=[], exec_time=0.0, exc_type=None)

        manager.run_stage(
            initial_substage=next_meta,
            exec_callback=exec_callback,
            step_callback=step_callback,
        )
        return run_dir
    except Exception:
        logger.exception("Resume failed; exiting.")
        sys.exit(1)


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


def write_research_idea_to_run(run_dir_path: Path | None, idea: dict[str, object]) -> None:
    try:
        if run_dir_path is not None:
            md_output_path = run_dir_path / "research_idea.md"
            idea_to_markdown(data=idea, output_path=str(md_output_path), load_code="")
            logger.info(f"Wrote research idea markdown to {md_output_path}")
        else:
            logger.warning(
                "Warning: run_dir_path is None; cannot write research_idea.md to a run-specific folder."
            )
    except Exception:
        traceback.print_exc()
        logger.warning(
            "Failed to write research_idea.md into the run directory; continuing without it."
        )


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


def run_plot_aggregation(
    writeup_cfg: WriteupConfig | None,
    reports_base: str,
    run_dir_path: Path | None,
    should_run_reports: bool,
) -> bool:
    if writeup_cfg is None or not should_run_reports:
        return False
    try:
        aggregate_plots(
            base_folder=reports_base,
            model=writeup_cfg.plot_model,
            temperature=writeup_cfg.temperature,
            run_dir_name=run_dir_path.name if run_dir_path is not None else None,
        )
        return True
    except Exception as e:
        logger.warning(f"Aggregate plots failed: {e}. Skipping writeup.")
        traceback.print_exc()
        return False


def cleanup_aggregated_results(reports_base: str) -> None:
    shutil.rmtree(osp.join(reports_base, "experiment_results"), ignore_errors=True)


def run_writeup_stage(
    writeup_cfg: WriteupConfig | None,
    reports_base: str,
    run_dir_path: Path | None,
    should_run_reports: bool,
    agg_ok: bool,
) -> bool:
    if writeup_cfg is None or not should_run_reports or not agg_ok:
        return False

    writeup_type = writeup_cfg.writeup_type.lower()
    writeup_retries = writeup_cfg.writeup_retries
    num_cite_rounds = writeup_cfg.num_cite_rounds
    writeup_model = writeup_cfg.model
    citation_model = writeup_cfg.citation_model or writeup_model

    citations_text = gather_citations(
        base_folder=reports_base,
        num_cite_rounds=num_cite_rounds,
        model=citation_model,
        run_dir_name=run_dir_path.name if run_dir_path is not None else None,
        temperature=writeup_cfg.temperature,
    )
    writeup_success = False
    try:
        for attempt in range(writeup_retries):
            logger.info(f"Writeup attempt {attempt + 1} of {writeup_retries}")
            if writeup_type == "normal":
                writeup_success = perform_writeup(
                    base_folder=reports_base,
                    model=writeup_model,
                    page_limit=8,
                    citations_text=citations_text,
                    run_dir_name=run_dir_path.name if run_dir_path is not None else None,
                    temperature=writeup_cfg.temperature,
                )
            else:
                writeup_success = perform_icbinb_writeup(
                    base_folder=reports_base,
                    model=writeup_model,
                    page_limit=4,
                    citations_text=citations_text,
                    run_dir_name=run_dir_path.name if run_dir_path is not None else None,
                    temperature=writeup_cfg.temperature,
                )
            if writeup_success:
                break
    except Exception as e:
        logger.exception(f"Writeup failed: {e}")
        traceback.print_exc()

    if not writeup_success:
        logger.error("Writeup process did not complete successfully after all retries.")
    return writeup_success


def run_review_stage(
    review_cfg: ReviewConfig | None,
    reports_base: str,
    run_dir_path: Path | None,
    writeup_success: bool,
    should_run_reports: bool,
    agg_ok: bool,
) -> None:
    if (
        review_cfg is None
        or run_dir_path is None
        or not should_run_reports
        or not agg_ok
        or not writeup_success
    ):
        return

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
    review_text = perform_review(
        text=paper_content,
        model=review_model,
        temperature=review_cfg.temperature,
        context=review_context,
        num_reviews_ensemble=3,
        num_reflections=2,
    )
    review_img_cap_ref = perform_imgs_cap_ref_review(
        model=review_model,
        pdf_path=pdf_path,
        temperature=review_cfg.temperature,
    )
    review_out_dir = (
        osp.join(reports_base, "logs", run_dir_path.name)
        if run_dir_path is not None
        else reports_base
    )
    os.makedirs(review_out_dir, exist_ok=True)
    with open(osp.join(review_out_dir, "review_text.txt"), "w") as f:
        f.write(json.dumps(review_text, indent=4))
    with open(osp.join(review_out_dir, "review_img_cap_ref.json"), "w") as f:
        json.dump(review_img_cap_ref, f, indent=4)
    logger.info("Paper review completed.")


def execute_launcher(args: argparse.Namespace) -> None:
    base_config_path = Path(args.config_file)
    base_cfg = load_base_config(config_path=base_config_path)
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

    telemetry_hooks = setup_event_pipeline(telemetry_cfg=base_cfg.telemetry)
    event_callback = telemetry_hooks.event_callback
    event_persistence = telemetry_hooks.persistence
    webhook_client = telemetry_hooks.webhook
    heartbeat_thread: threading.Thread | None = None
    heartbeat_stop: threading.Event | None = None
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

    run_success = False
    failure_message: str | None = None
    try:
        idea_json_path = str(base_cfg.desc_file)
        with open(idea_json_path, "r") as f:
            idea = json.load(f)
            logger.info(f"Loaded idea from {idea_json_path}")

        resume_run_dir: Path | None = None
        if args.resume is not None:
            resume_run_dir = resume_run(
                base_cfg=base_cfg,
                idea_json_path=idea_json_path,
                resume_arg=args.resume,
                event_callback=event_callback,
            )
        else:
            perform_experiments_bfts(base_config_path, event_callback)

        run_dir_path = determine_run_directory(
            top_log_dir=top_log_dir,
            existing_runs_before=existing_runs_before,
            resume_run_dir=resume_run_dir,
        )
        write_research_idea_to_run(run_dir_path=run_dir_path, idea=idea)

        should_run_reports = should_generate_reports(run_dir_path=run_dir_path)
        agg_ok = run_plot_aggregation(
            writeup_cfg=writeup_cfg,
            reports_base=reports_base,
            run_dir_path=run_dir_path,
            should_run_reports=should_run_reports,
        )

        cleanup_aggregated_results(reports_base=reports_base)

        save_token_tracker(
            idea_dir=run_dir_path.as_posix() if run_dir_path is not None else reports_base
        )

        writeup_success = run_writeup_stage(
            writeup_cfg=writeup_cfg,
            reports_base=reports_base,
            run_dir_path=run_dir_path,
            should_run_reports=should_run_reports,
            agg_ok=agg_ok,
        )

        run_review_stage(
            review_cfg=review_cfg if review_enabled else None,
            reports_base=reports_base,
            run_dir_path=run_dir_path,
            writeup_success=writeup_success,
            should_run_reports=should_run_reports,
            agg_ok=agg_ok,
        )

        logger.info("Finished running the experiment.")
        run_success = True
    except Exception as exc:
        failure_message = str(exc)
        raise
    finally:
        if webhook_client is not None:
            try:
                webhook_client.publish_run_finished(success=run_success, message=failure_message)
            except Exception:
                logger.exception("Failed to notify run completion.")
        if heartbeat_stop is not None:
            heartbeat_stop.set()
        if heartbeat_thread is not None:
            heartbeat_thread.join(timeout=5)
        if event_persistence is not None:
            event_persistence.stop()


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
