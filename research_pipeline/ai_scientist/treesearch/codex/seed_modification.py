"""
Seed modification task utilities for multi-seed reproducibility runs.

This module provides the prompt generation for seed modification tasks,
where Codex is asked to modify the random seed in experiment code and re-run it.
"""

from pathlib import Path
from typing import NamedTuple

from ..prompts.render import render_text


class SeedModificationTaskContext(NamedTuple):
    """Context for rendering the seed modification task template."""

    seed_value: int
    agent_file_name: str
    venv_dir: str
    base_code: str


def render_seed_modification_task_markdown(*, ctx: SeedModificationTaskContext) -> str:
    """
    Render the seed modification task markdown.

    Uses a focused template that only asks Codex to find and replace seed values.
    """
    context = {
        "seed_value": ctx.seed_value,
        "agent_file_name": ctx.agent_file_name,
        "venv_dir": ctx.venv_dir,
        "base_code": ctx.base_code,
    }
    rendered = render_text(
        template_name="seed_modification/seed_modification_instructions.md.j2",
        context=context,
    )
    return rendered + "\n"


def write_seed_modification_task_file(
    *,
    workspace_dir: Path,
    ctx: SeedModificationTaskContext,
) -> Path:
    """
    Write the seed modification task markdown to a file.

    Returns the path to the written task file.
    """
    task_path = workspace_dir / "codex_task.md"
    task_markdown = render_seed_modification_task_markdown(ctx=ctx)
    task_path.write_text(task_markdown, encoding="utf-8")
    return task_path
