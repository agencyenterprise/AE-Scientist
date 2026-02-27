"""Jinja2 template rendering using importlib.resources for baseline prompt templates."""

import importlib.resources
from typing import Any, Callable

from jinja2 import BaseLoader, Environment, StrictUndefined, TemplateNotFound


class PackageResourceLoader(BaseLoader):
    """Jinja2 loader that loads templates from package resources."""

    def __init__(self, package: str) -> None:
        self.package = package

    def get_source(
        self, environment: Environment, template: str
    ) -> tuple[str, str, Callable[[], bool]]:
        del environment  # Required by Jinja2 interface but unused
        try:
            files = importlib.resources.files(self.package)
            content = (files / template).read_text()
            return content, template, lambda: True
        except (FileNotFoundError, TypeError) as e:
            raise TemplateNotFound(template) from e


def _env() -> Environment:
    """Create Jinja2 environment with package resource loader for baseline prompts."""
    return Environment(
        loader=PackageResourceLoader("ae_paper_review.baseline.prompts"),
        undefined=StrictUndefined,
        autoescape=False,
        trim_blocks=True,
        lstrip_blocks=True,
    )


def render_text(*, template_name: str, context: dict[str, Any]) -> str:
    """Render a baseline template with the given context.

    Args:
        template_name: Name of the template file (e.g., "llm_review/neurips_form.md.j2")
        context: Dictionary of variables to pass to the template

    Returns:
        Rendered template as a string
    """
    template = _env().get_template(template_name)
    rendered = template.render(**context)
    return str(rendered).strip()
