"""
Run only Stage 1 (initial implementation) of the BFTS workflow.

Steps:
- Load run configuration and research idea (task description)
- Prepare the agent workspace for the experiment
- Initialize AgentManager and event logging
- Run a single main stage (Stage 1) using AgentManager.run_stage
- Persist results and checkpoint
"""

import atexit
import logging
import shutil
from pathlib import Path

from ai_scientist.treesearch.agent_manager import AgentManager
from ai_scientist.treesearch.events import BaseEvent
from ai_scientist.treesearch.interpreter import ExecutionResult
from ai_scientist.treesearch.journal import Journal
from ai_scientist.treesearch.stages.base import StageMeta
from ai_scientist.treesearch.utils.config import (
    load_cfg,
    load_task_desc,
    prep_agent_workspace,
    save_run,
)

logger = logging.getLogger("ai-scientist")


def main(config_path: Path) -> None:
    cfg = load_cfg(path=config_path)
    logger.info(f'Starting Stage 1 run for "{cfg.exp_name}"')

    task_desc = load_task_desc(cfg=cfg)

    # Prepare workspace
    prep_agent_workspace(cfg=cfg)

    global_step = 0

    def cleanup() -> None:
        if global_step == 0:
            shutil.rmtree(cfg.workspace_dir)

    atexit.register(cleanup)

    def on_event(event: BaseEvent) -> None:
        logger.info(event.to_dict())

    manager = AgentManager(
        task_desc=task_desc,
        cfg=cfg,
        workspace_dir=Path(cfg.workspace_dir),
        event_callback=on_event,
    )

    def exec_callback(_code: str, _is_exec: bool) -> ExecutionResult:
        return ExecutionResult(term_out=[], exec_time=0.0, exc_type=None)

    def step_callback(stage: StageMeta, journal: Journal) -> None:
        nonlocal global_step
        global_step += 1
        save_run(cfg=cfg, journal=journal, stage_name=f"stage_{stage.name}")

    # Run only the current main stage (Stage 1 at initialization)
    if manager.current_stage is not None:
        manager.run_stage(
            initial_substage=manager.current_stage,
            exec_callback=exec_callback,
            step_callback=step_callback,
        )


if __name__ == "__main__":
    cfg_path = Path("bfts_config.yaml")
    main(config_path=cfg_path)

