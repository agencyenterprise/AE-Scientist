from pathlib import Path
from typing import Any

import humanize
from jinja2 import Environment, FileSystemLoader, StrictUndefined

_PROMPTS_DIR = Path(__file__).resolve().parent


def _naturaldelta_filter(seconds: object) -> str:
    if not isinstance(seconds, (int, float)):
        raise TypeError("naturaldelta expects seconds as int|float")
    return str(humanize.naturaldelta(seconds))


def _naturalsize_filter(num_bytes: object) -> str:
    if not isinstance(num_bytes, (int, float)):
        raise TypeError("naturalsize expects bytes as int|float")
    return str(humanize.naturalsize(num_bytes, binary=True))


def _env() -> Environment:
    # StrictUndefined ensures missing variables fail fast.
    env = Environment(
        loader=FileSystemLoader(str(_PROMPTS_DIR)),
        undefined=StrictUndefined,
        autoescape=False,
        trim_blocks=True,
        lstrip_blocks=True,
    )
    env.filters["naturaldelta"] = _naturaldelta_filter
    env.filters["naturalsize"] = _naturalsize_filter
    return env


def render_text(*, template_name: str, context: dict[str, Any]) -> str:
    template = _env().get_template(template_name)
    rendered = template.render(**context)
    return str(rendered).strip()


def render_lines(*, template_name: str, context: dict[str, Any]) -> list[str]:
    rendered = render_text(template_name=template_name, context=context)
    lines = [line.rstrip("\n") for line in rendered.splitlines()]
    return [line for line in lines if line.strip()]
