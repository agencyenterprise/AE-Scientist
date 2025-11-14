"""
Run only Stage 3 (creative research/plotting) using Stage 1 and Stage 2 artifacts from an existing run.

Usage:
  uv run python launch_stage3_from_run.py <run_name_or_number>

Examples:
  uv run python launch_stage3_from_run.py 3
  uv run python launch_stage3_from_run.py 3-run
  uv run python launch_stage3_from_run.py run-3
"""

import atexit
import copy
import logging
import sys
from pathlib import Path
from typing import Optional

from omegaconf import OmegaConf

from ai_scientist.treesearch.agent_manager import AgentManager
from ai_scientist.treesearch.events import BaseEvent
from ai_scientist.treesearch.interpreter import ExecutionResult
from ai_scientist.treesearch.journal import Journal
from ai_scientist.treesearch.stages.base import StageMeta
from ai_scientist.treesearch.stages.stage1_baseline import Stage1Baseline
from ai_scientist.treesearch.stages.stage2_tuning import Stage2Tuning
from ai_scientist.treesearch.stages.stage3_plotting import Stage3Plotting
from ai_scientist.treesearch.utils.config import Config, load_task_desc, save_run
from ai_scientist.treesearch.utils.serialize import load_json as load_json_dc

logger = logging.getLogger(__name__)


def _normalize_run_name(run_arg: str) -> str:
    s = run_arg.strip()
    if s.isdigit():
        return f"{s}-run"
    if s.startswith("run-") and s[4:].isdigit():
        return f"{s[4:]}-run"
    return s


def _select_stage_dir(run_dir: Path, stage_prefix: str) -> Path:
    stage_dirs = sorted(
        [p for p in run_dir.iterdir() if p.is_dir() and p.name.startswith(stage_prefix)]
    )
    if not stage_dirs:
        raise FileNotFoundError(f"No {stage_prefix}* directory found under {run_dir}")
    return stage_dirs[-1]


def _load_cfg_from_run(run_dir: Path) -> Config:
    # Prefer a config.yaml from stage 1 dir; fallback to any stage dir
    try:
        stage1_dir = _select_stage_dir(run_dir, "stage_1_")
        cfg_path = stage1_dir / "config.yaml"
    except FileNotFoundError:
        try:
            stage2_dir = _select_stage_dir(run_dir, "stage_2_")
            cfg_path = stage2_dir / "config.yaml"
        except FileNotFoundError:
            stage_dirs = sorted(
                [p for p in run_dir.iterdir() if p.is_dir() and p.name.startswith("stage_")]
            )
            if not stage_dirs:
                raise
            cfg_path = stage_dirs[-1] / "config.yaml"

    if not cfg_path.exists():
        raise FileNotFoundError(str(cfg_path))
    raw = OmegaConf.load(cfg_path)
    schema = OmegaConf.structured(Config)
    merged = OmegaConf.merge(schema, raw)
    cfg_obj = OmegaConf.to_object(merged)
    assert isinstance(cfg_obj, Config)
    return cfg_obj


def _load_stage_journal(stage_dir: Path) -> tuple[str, Journal]:
    # stage directory name is 'stage_<StageMeta.name>'
    stage_name = stage_dir.name.replace("stage_", "", 1)
    journal_path = stage_dir / "journal.json"
    if not journal_path.exists():
        raise FileNotFoundError(str(journal_path))
    journal = load_json_dc(journal_path, Journal)
    return stage_name, journal


def main(run_arg: str) -> None:
    run_name = _normalize_run_name(run_arg)
    logs_root = Path("workspaces") / "logs"
    run_dir = logs_root.resolve() / run_name
    if not run_dir.exists():
        raise FileNotFoundError(str(run_dir))

    cfg = _load_cfg_from_run(run_dir=run_dir)
    fake_config = copy.deepcopy(cfg)
    fake_config.desc_file = Path("idea_example.json")
    task_desc = load_task_desc(cfg=fake_config)

    # Instantiate manager; it will create stage 1 initial config by default
    def on_event(event: BaseEvent) -> None:
        logger.info(event.to_dict())

    manager = AgentManager(
        task_desc=task_desc,
        cfg=cfg,
        workspace_dir=Path(cfg.workspace_dir),
        event_callback=on_event,
    )

    # Load Stage 1 journal
    stage1_dir = _select_stage_dir(run_dir=run_dir, stage_prefix="stage_1_")
    stage1_name, stage1_journal = _load_stage_journal(stage_dir=stage1_dir)

    # Load Stage 2 journal
    try:
        stage2_dir = _select_stage_dir(run_dir=run_dir, stage_prefix="stage_2_")
        stage2_name, stage2_journal = _load_stage_journal(stage_dir=stage2_dir)
    except FileNotFoundError:
        raise FileNotFoundError("Stage 2 results not found. Run Stage 2 first before Stage 3.")

    # Ensure Stage 1 meta exists in manager.stages
    stage1_meta = StageMeta(
        name=stage1_name,
        number=1,
        slug=Stage1Baseline.MAIN_STAGE_SLUG,
        substage_number=1,
        substage_name="preliminary",
        goals=Stage1Baseline.DEFAULT_GOALS,
        max_iterations=manager._get_max_iterations(1),
        num_drafts=0,
    )

    # Ensure Stage 2 meta exists in manager.stages
    stage2_meta = StageMeta(
        name=stage2_name,
        number=2,
        slug=Stage2Tuning.MAIN_STAGE_SLUG,
        substage_number=1,
        substage_name="first_attempt",
        goals=Stage2Tuning.DEFAULT_GOALS,
        max_iterations=manager._get_max_iterations(2),
        num_drafts=0,
    )

    # Replace or append stages
    existing_stage1: Optional[int] = next(
        (i for i, s in enumerate(manager.stages) if s.number == 1), None
    )
    if isinstance(existing_stage1, int):
        manager.stages[existing_stage1] = stage1_meta
    else:
        manager.stages.insert(0, stage1_meta)

    existing_stage2: Optional[int] = next(
        (i for i, s in enumerate(manager.stages) if s.number == 2), None
    )
    if isinstance(existing_stage2, int):
        manager.stages[existing_stage2] = stage2_meta
    else:
        manager.stages.append(stage2_meta)

    manager.journals[stage1_meta.name] = stage1_journal
    manager.journals[stage2_meta.name] = stage2_journal

    # Create empty Stage 3 journal and meta
    stage3_meta = StageMeta(
        name="3_" + Stage3Plotting.MAIN_STAGE_SLUG + "_1_first_attempt",
        number=3,
        slug=Stage3Plotting.MAIN_STAGE_SLUG,
        substage_number=1,
        substage_name="first_attempt",
        goals=Stage3Plotting.DEFAULT_GOALS,
        max_iterations=manager._get_max_iterations(3),
        num_drafts=0,
    )
    manager.stages.append(stage3_meta)
    manager.current_stage = stage3_meta
    manager.journals[stage3_meta.name] = Journal(
        summary_model=cfg.report.model,
        node_selection_model=cfg.agent.feedback.model,
        event_callback=on_event,
    )

    # Per-step save hook
    global_step = 0

    def step_callback(stage: StageMeta, journal: Journal) -> None:
        nonlocal global_step
        global_step += 1
        save_run(cfg=cfg, journal=journal, stage_name=f"stage_{stage.name}")

    def exec_callback(code: str, is_exec: bool) -> ExecutionResult:
        return ExecutionResult(term_out=[], exec_time=0.0, exc_type=None)

    def cleanup() -> None:
        # No workspace deletion
        pass

    atexit.register(cleanup)

    # Run Stage 3 only
    manager.run_stage(
        initial_substage=stage3_meta, exec_callback=exec_callback, step_callback=step_callback
    )


if __name__ == "__main__":
    if len(sys.argv) != 2:
        logger.error("Usage: python launch_stage3_from_run.py <run_name_or_number>")
        sys.exit(1)
    main(sys.argv[1])
