import asyncio
from dataclasses import dataclass
from pathlib import Path
from tempfile import NamedTemporaryFile
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
        str | list[str] | list[dict[str, str]], 
        Field(alias="Experiments")
    ]
    risk_factors_and_limitations: Annotated[
        str | list[str], 
        Field(alias="Risk Factors and Limitations")
    ]


class Metric(BaseModel):
    name: str
    maximize: bool
    description: str

@dataclass
class RunCodeResult:
    stdout: str
    stderr: str
    returncode: int


async def exec_code(code: str, dependencies: list[str]) -> RunCodeResult:
    with NamedTemporaryFile(mode="wt", suffix=".py") as tmp:
        # dependencies section
        # https://docs.astral.sh/uv/guides/scripts/#running-a-script-with-dependencies
        tmp.write("# /// script\n")
        tmp.write("# dependencies = [\n")
        for dep in dependencies:
            tmp.write(f'#   "{dep}",\n')
        tmp.write("# ]\n")
        tmp.write("# ///\n")
        tmp.write("\n")

        # actual code
        tmp.write(code)
        tmp.flush()

        proc = await asyncio.create_subprocess_exec(
            "uv",
            "run",
            "python",
            tmp.name,
            cwd=Path(tmp.file.name).parent,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        await proc.wait()

    stdout = await proc.stdout.read() if proc.stdout else b""
    stderr = await proc.stderr.read() if proc.stderr else b""
    returncode = proc.returncode if proc.returncode is not None else 1

    return RunCodeResult(
        stdout=stdout.decode(),
        stderr=stderr.decode(),
        returncode=returncode,
    )
