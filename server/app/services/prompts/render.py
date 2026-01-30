"""
Jinja2 template rendering utilities for prompt templates.

This module provides utilities for rendering Jinja2 templates stored in the templates/
subdirectory. It follows the same pattern as the research pipeline's prompt rendering.
"""

from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader, StrictUndefined

_PROMPTS_DIR = Path(__file__).resolve().parent


def _env() -> Environment:
    """Create a Jinja2 environment configured for prompt rendering."""
    return Environment(
        loader=FileSystemLoader(str(_PROMPTS_DIR / "templates")),
        undefined=StrictUndefined,
        autoescape=False,
        trim_blocks=True,
        lstrip_blocks=True,
    )


def render_text(*, template_name: str, context: dict[str, Any] | None = None) -> str:
    """
    Render a Jinja2 template with the given context.

    Args:
        template_name: Name of the template file (e.g., "idea_generation.txt.j2")
        context: Dictionary of variables to pass to the template

    Returns:
        The rendered template as a string, with leading/trailing whitespace stripped.

    Raises:
        jinja2.UndefinedError: If a required template variable is missing from context
        jinja2.TemplateNotFound: If the template file doesn't exist
    """
    if context is None:
        context = {}
    template = _env().get_template(template_name)
    rendered = template.render(**context)
    return str(rendered).strip()
