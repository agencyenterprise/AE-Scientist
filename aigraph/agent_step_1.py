import asyncio
import logging
from tempfile import NamedTemporaryFile
from typing import NotRequired, TypedDict

from langchain.chat_models import init_chat_model
from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph, RunnableConfig
from langgraph.runtime import Runtime
from pydantic import BaseModel

logger = logging.getLogger(__name__)


PROMPT_SYSTEM = """
## Introduction

You are an AI researcher who is looking to publish a paper that will contribute
significantly to the field. Your first task is to write a python code to
implement a solid baseline based on your research idea provided below, from data
preparation to model training, as well as evaluation and visualization. Focus on
getting a simple but working implementation first, before any sophisticated
improvements. We will explore more advanced variations in later stages.

## Instructions

### Experiment design sketch guideline

- This first experiment design should be relatively simple, without extensive
  hyper-parameter optimization.
- Take the Memory section into consideration when proposing the design.
- The solution sketch should be 6-10 sentences.
- Don't suggest to do EDA.
- Prioritize using real public datasets (e.g., from HuggingFace) when they suit
  the task, and only fall back to synthetic data if no suitable dataset is
  available or synthetic generation is essential to the proposed experiment.

### Goals

- Focus on getting basic working implementation
- Use a dataset appropriate to the experiment
- Aim for basic functional correctness
- If you are given "Code To Use", you can directly use it as a starting point.

## Research idea

{idea}
"""


class State(BaseModel):
    # inputs
    idea: str

    # outputs
    code: str | None = None
    solution: str | None = None
    dependencies: list[str] | None = None
    returncode: int | None = None
    stdout: str | None = None
    stderr: str | None = None


class Context(BaseModel):
    model: str = "gpt-4o-mini"
    temperature: float = 0.0


async def node_plan(state: State, runtime: Runtime[Context]) -> State:
    logger.info("Starting node_plan")

    class Schema(BaseModel):
        code: str
        solution: str
        dependencies: list[str]

    llm = init_chat_model(model=runtime.context.model, temperature=runtime.context.temperature)
    llms = llm.with_structured_output(Schema)
    prompt = PROMPT_SYSTEM.format(idea=state.idea)
    
    logger.info("Calling LLM")
    response: Schema = await llms.ainvoke(prompt)  # type: ignore

    state.code = response.code
    state.solution = response.solution

    logger.info("node_plan completed")
    return state


async def node_run(state: State, runtime: Runtime[Context]) -> State:
    logger.info("Starting node_run")

    code = state.code or ""
    dependencies = state.dependencies or []

    assert code, 'code is required'

    with NamedTemporaryFile(mode="wt") as tmp:
        # deps section. example:
        # ```
        # dependencies = [
        #   "requests<3",
        #   "rich",
        # ]
        # ```
        tmp.write('# /// script\n')
        tmp.write('# dependencies = [\n')
        for dep in dependencies:
            tmp.write(f'#   "{dep}",\n')
        tmp.write('# ]\n')
        tmp.write('# ///\n')
        tmp.write('\n')

        # actual code
        tmp.write(code)
        tmp.flush()

        logger.info("Running code")
        proc = await asyncio.create_subprocess_exec(
            'uv', 'run', 'python', tmp.name,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        await proc.wait()

    stdout = await proc.stdout.read() if proc.stdout else b''
    stderr = await proc.stderr.read() if proc.stderr else b''

    state.stdout = stdout.decode()
    state.stderr = stderr.decode()
    state.returncode = proc.returncode

    logger.info("node_run completed")
    return state


def build() -> CompiledStateGraph[State, Context, State, State]:
    builder = StateGraph(state_schema=State, context_schema=Context)

    # Add nodes
    builder.add_node("node_plan", node_plan)
    builder.add_node("node_run", node_run)
    # Add edges
    builder.add_edge(START, "node_plan")
    builder.add_edge("node_plan", "node_run")
    builder.add_edge("node_run", END)

    return builder.compile()  # type: ignore
