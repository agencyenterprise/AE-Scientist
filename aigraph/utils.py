import asyncio
from dataclasses import dataclass
from pathlib import Path
from tempfile import NamedTemporaryFile, TemporaryDirectory
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field

ROOT_DIR = Path(__file__).parent


class Task(BaseModel):
    model_config = ConfigDict(extra="allow")

    name: Annotated[str, Field(alias="Name")]
    title: Annotated[str, Field(alias="Title")]
    short_hypothesis: Annotated[str, Field(alias="Short Hypothesis")]
    related_work: Annotated[str, Field(alias="Related Work")]
    abstract: Annotated[str, Field(alias="Abstract")]
    code: Annotated[str | None, Field(default=None, alias="Code")]
    experiments: Annotated[
        str | list[str] | list[dict[str, str]], Field(alias="Experiments")
    ]
    risk_factors_and_limitations: Annotated[
        str | list[str], Field(alias="Risk Factors and Limitations")
    ]


class MetricData(BaseModel):
    dataset_name: str
    final_value: float
    best_value: float


class MetricValue(BaseModel):
    metric_name: str
    lower_is_better: bool
    description: str
    data: list[MetricData]


class Metric(BaseModel):
    name: str
    maximize: bool
    description: str


class Hyperparam(BaseModel):
    name: str
    description: str


class Ablation(BaseModel):
    name: str
    description: str


@dataclass
class RunCodeResult:
    stdout: str
    stderr: str
    returncode: int
    directory: str
    filename: str


def _to_script(code: str, deps: list[str] = []) -> str:
    # dependencies section
    # https://docs.astral.sh/uv/guides/scripts/#running-a-script-with-dependencies
    script = "# /// script\n"
    script += "# dependencies = [\n"
    for dep in deps:
        script += f'#   "{dep}",\n'
    script += "# ]\n"
    script += "# ///\n"
    script += "\n"

    # actual code
    script += code
    return script


async def exec_code(
    code: str,
    deps: list[str] = [],
) -> RunCodeResult:
    dir = TemporaryDirectory(delete=False)
    file = NamedTemporaryFile(mode="wt", suffix=".py", dir=dir.name, delete=False)

    script = _to_script(code, deps)
    file.write(script)
    file.flush()

    proc = await asyncio.create_subprocess_exec(
        "uv",
        "run",
        file.name,
        cwd=dir.name,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )

    await proc.wait()

    stdout = await proc.stdout.read() if proc.stdout else b""
    stderr = await proc.stderr.read() if proc.stderr else b""

    # ternary because 0 is a valid return code and falsy... so, using:
    # `returncode = proc.returncode or -1` would be incorrectly mapped to -1
    returncode = proc.returncode if proc.returncode is not None else -1

    return RunCodeResult(
        stdout=stdout.decode(),
        stderr=stderr.decode(),
        returncode=returncode,
        directory=dir.name,
        filename=file.name,
    )


async def exec_code_at(
    cwd: str,
    code: str,
    deps: list[str] = [],
) -> RunCodeResult:
    file = NamedTemporaryFile(mode="wt", suffix=".py", dir=cwd, delete=False)
    
    script = _to_script(code, deps)
    file.write(script)
    file.flush()

    proc = await asyncio.create_subprocess_exec(
        "uv",
        "run",
        file.name,
        cwd=cwd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )

    await proc.wait()

    stdout = await proc.stdout.read() if proc.stdout else b""
    stderr = await proc.stderr.read() if proc.stderr else b""

    # ternary because 0 is a valid return code and falsy... so, using:
    # `returncode = proc.returncode or -1` would be incorrectly mapped to -1
    returncode = proc.returncode if proc.returncode is not None else -1

    return RunCodeResult(
        stdout=stdout.decode(),
        stderr=stderr.decode(),
        returncode=returncode,
        directory=cwd,
        filename=file.name,
    )
