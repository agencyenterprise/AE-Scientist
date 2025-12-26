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
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, NamedTuple, Optional, Protocol, cast

from omegaconf import OmegaConf

from ai_scientist.artifact_manager import ArtifactPublisher, ArtifactSpec
from ai_scientist.latest_run_finder import normalize_run_name
from ai_scientist.perform_icbinb_writeup import gather_citations
from ai_scientist.perform_icbinb_writeup import perform_writeup as perform_icbinb_writeup
from ai_scientist.perform_llm_review import ReviewResponseModel, load_paper, perform_review
from ai_scientist.perform_plotting import aggregate_plots
from ai_scientist.perform_vlm_review import perform_imgs_cap_ref_review
from ai_scientist.perform_writeup import perform_writeup
from ai_scientist.review_context import build_auto_review_context
from ai_scientist.review_storage import FigureReviewRecorder, ReviewResponseRecorder
from ai_scientist.telemetry import EventPersistenceManager, EventQueueEmitter, WebhookClient
from ai_scientist.treesearch.agent_manager import AgentManager
from ai_scientist.treesearch.bfts_utils import idea_to_markdown
from ai_scientist.treesearch.events import BaseEvent, GpuShortageEvent
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
from termination_server import (
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



def load_base_config(config_path: Path) -> Config:
    raw_cfg = OmegaConf.load(str(config_path))
    schema = OmegaConf.structured(Config)
    merged = OmegaConf.merge(schema, raw_cfg)
    cfg_obj = cast(Config, OmegaConf.to_object(merged))
    cfg_obj.desc_file = Path(cfg_obj.desc_file).resolve()
    cfg_obj.log_dir = Path(cfg_obj.log_dir).resolve()
    cfg_obj.workspace_dir = Path(cfg_obj.workspace_dir).resolve()
    return cfg_obj

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


def execute_launcher(args: argparse.Namespace) -> None:
    base_config_path = Path(args.config_file)
    base_cfg = load_base_config(config_path=base_config_path)
    workspace_dir = base_cfg.workspace_dir
    os.environ["WORKSPACE_DIR"] = str(workspace_dir)
    apply_log_level(level_name=str(base_cfg.log_level))
    top_log_dir = base_cfg.log_dir
    top_log_dir.mkdir(parents=True, exist_ok=True)

    telemetry_hooks = setup_event_pipeline(telemetry_cfg=base_cfg.telemetry)
    webhook_client = telemetry_hooks.webhook
    if webhook_client is not None:
        webhook_client.publish_run_finished(success=True, message=None)

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
