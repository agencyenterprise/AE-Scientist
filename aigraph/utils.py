import asyncio
from dataclasses import dataclass
import os
from pathlib import Path
from typing import Annotated, NamedTuple
import logging

from pydantic import BaseModel, ConfigDict, Field

ROOT_DIR = Path(__file__).parent
DATA_DIR = ROOT_DIR / "data"

logger = logging.getLogger(__name__)


class Task(BaseModel):
    """
    This class represents a research task/idea

    This is the input passed to the agent on its first step
    """

    model_config = ConfigDict(extra="allow")

    name: Annotated[
        str,
        Field(alias="Name"),
    ]
    title: Annotated[
        str,
        Field(alias="Title"),
    ]
    short_hypothesis: Annotated[
        str,
        Field(alias="Short Hypothesis"),
    ]
    related_work: Annotated[
        str,
        Field(alias="Related Work"),
    ]
    abstract: Annotated[
        str,
        Field(alias="Abstract"),
    ]
    code: Annotated[
        str | None,
        Field(default=None, alias="Code"),
    ]
    experiments: Annotated[
        list[str],
        Field(alias="Experiments", default_factory=list),
    ]
    risk_factors_and_limitations: Annotated[
        list[str],
        Field(alias="Risk Factors and Limitations", default_factory=list),
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
    model_config = ConfigDict(frozen=True)  # so it becomes hashable

    name: str
    maximize: bool
    description: str


class Hyperparam(BaseModel):
    model_config = ConfigDict(frozen=True)  # so it becomes hashable

    name: str
    description: str


class Ablation(BaseModel):
    name: str
    description: str


class Plot(BaseModel):
    model_config = ConfigDict(frozen=True)  # so it becomes hashable

    path: Path
    analysis: str


@dataclass
class RunCodeResult:
    stdout: str
    stderr: str
    returncode: int
    directory: str
    filename: str


class Exec(NamedTuple):
    returncode: int
    stdout: str
    stderr: str


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


async def exec(*args: str, cwd: Path) -> Exec:
    proc = await asyncio.create_subprocess_exec(
        *args,
        cwd=cwd,
        env=os.environ.copy() | {"TQDM_DISABLE": "1"},
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )

    async def _read(stream: asyncio.StreamReader | None, prefix: str) -> str:
        """
        Utility to read and log the stdout/stderr of a subprocess while it is
        executing
        """
        if stream is None:
            return ""

        data = ""
        while line := await stream.readline():
            logger.debug(f"{prefix} (pid={proc.pid}): {line!r}")
            data += line.decode()

        return data

    async with asyncio.TaskGroup() as tg:
        stdout_task = tg.create_task(_read(proc.stdout, "stdout"))
        stderr_task = tg.create_task(_read(proc.stderr, "stderr"))
        await proc.wait()

    stdout = await stdout_task
    stderr = await stderr_task
    returncode = proc.returncode if proc.returncode is not None else -1

    logger.debug(f"returncode: {returncode}")
    logger.debug(f"stdout: {stdout[:32]!r}")
    logger.debug(f"stderr: {stderr[:32]!r}")

    return Exec(returncode=returncode, stdout=stdout, stderr=stderr)


async def exec_code(
    cwd: str | Path, filename: str, code: str, deps: list[str]
) -> RunCodeResult:
    file = Path(cwd) / filename
    file = file.absolute()
    file.touch(exist_ok=True)
    file.write_text(_to_script(code, deps))

    result = await exec("uv", "run", str(file), cwd=Path(cwd))

    return RunCodeResult(
        stdout=result.stdout,
        stderr=result.stderr,
        returncode=result.returncode,
        directory=str(cwd),
        filename=str(file),
    )


async def compile(cwd: Path, file: Path) -> Exec:
    first = await exec("pdflatex", "-interaction=nonstopmode", file.name, cwd=cwd)
    if first.returncode != 0:
        return first

    second = await exec("bibtex", file.stem, cwd=cwd)
    if second.returncode != 0:
        return second

    third = await exec("pdflatex", "-interaction=nonstopmode", file.name, cwd=cwd)
    if third.returncode != 0:
        return third

    fourth = await exec("pdflatex", "-interaction=nonstopmode", file.name, cwd=cwd)
    if fourth.returncode != 0:
        return fourth

    return fourth
