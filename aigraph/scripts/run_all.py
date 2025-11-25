import json
import logging
import uuid
from pathlib import Path
from typing import Annotated, Any

import aiosqlite
from langchain_core.runnables import RunnableConfig
from langfuse.langchain import CallbackHandler
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph
from langgraph.runtime import Runtime
from pydantic import AliasChoices, BaseModel, Field
from pydantic_settings import BaseSettings, CliApp, CliImplicitFlag, CliPositionalArg

from aigraph import log, utils
from aigraph.agents import ablation, baseline, plotting, research, tuning, writeup

logger = logging.getLogger(__name__)


class State(BaseModel):
    # inputs
    cwd: Path
    task: utils.Task

    state_research: research.State | None = None
    state_baseline: baseline.State | None = None
    state_tuning: tuning.State | None = None
    state_ablation: ablation.State | None = None
    state_plotting: plotting.State | None = None
    state_writeup: writeup.State | None = None


class Context(BaseModel):
    model: str = "gpt-4o-mini"
    temperature: float = 0.0


async def node_research(state: State, runtime: Runtime[Context]) -> dict[str, Any]:
    research_state = research.State(
        cwd=state.cwd,
        task=state.task,
    )

    graph = research.build(checkpointer=True)
    result = await graph.ainvoke(input=research_state)

    return {"state_research": result}


async def node_baseline(state: State, runtime: Runtime[Context]) -> dict[str, Any]:
    baseline_state = baseline.State(
        cwd=state.cwd,
        task=state.task,
    )
    baseline_context = baseline.Context(
        model=runtime.context.model,
        temperature=runtime.context.temperature,
    )

    graph = baseline.build(checkpointer=True)
    result = await graph.ainvoke(
        input=baseline_state,
        context=baseline_context,
    )

    return {"state_baseline": result}


async def node_tuning(state: State, runtime: Runtime[Context]) -> dict[str, Any]:
    assert state.state_baseline
    assert state.state_baseline.experiment_code

    tuning_state = tuning.State(
        cwd=state.cwd,
        task=state.task,
        code=state.state_baseline.experiment_code,
    )
    tuning_context = tuning.Context(
        model=runtime.context.model,
        temperature=runtime.context.temperature,
    )

    graph = tuning.build(checkpointer=True)
    result = await graph.ainvoke(
        input=tuning_state,
        context=tuning_context,
    )

    return {"state_tuning": result}


async def node_ablation(state: State, runtime: Runtime[Context]) -> dict[str, Any]:
    assert state.state_tuning
    assert state.state_tuning.tuning_code

    ablation_state = ablation.State(
        cwd=state.cwd,
        task=state.task,
        code=state.state_tuning.tuning_code,
    )
    ablation_context = ablation.Context(
        model=runtime.context.model,
        temperature=runtime.context.temperature,
    )

    graph = ablation.build(checkpointer=True)
    result = await graph.ainvoke(
        input=ablation_state,
        context=ablation_context,
    )

    return {"state_ablation": result}


async def node_plotting(state: State, runtime: Runtime[Context]) -> dict[str, Any]:
    assert state.state_ablation
    assert state.state_ablation.ablation_code

    plotting_state = plotting.State(
        cwd=state.cwd,
        task=state.task,
        code=state.state_ablation.ablation_code,
    )
    plotting_context = plotting.Context(
        model=runtime.context.model,
        temperature=runtime.context.temperature,
    )

    graph = plotting.build(checkpointer=True)
    result = await graph.ainvoke(
        input=plotting_state,
        context=plotting_context,
    )

    return {"state_plotting": result}


async def node_writeup(state: State, runtime: Runtime[Context]) -> dict[str, Any]:
    assert state.state_plotting
    assert state.state_ablation
    assert state.state_ablation.ablation_code
    assert state.state_ablation.parser_code

    writeup_state = writeup.State(
        cwd=state.cwd,
        task=state.task,
        experiment_code=state.state_ablation.ablation_code,
        parser_code=state.state_ablation.parser_code,
        plots=list(state.state_plotting.plots),
    )
    writeup_context = writeup.Context(
        model=runtime.context.model,
        temperature=runtime.context.temperature,
    )

    graph = writeup.build(checkpointer=True)
    result = await graph.ainvoke(
        input=writeup_state,
        context=writeup_context,
    )

    return {"state_writeup": result}


def build(
    conn: aiosqlite.Connection,
) -> CompiledStateGraph[State, Context, State, State]:
    builder = StateGraph(state_schema=State, context_schema=Context)

    # Add nodes
    builder.add_node("node_research", node_research)
    builder.add_node("node_baseline", node_baseline)
    builder.add_node("node_tuning", node_tuning)
    builder.add_node("node_ablation", node_ablation)
    builder.add_node("node_plotting", node_plotting)
    builder.add_node("node_writeup", node_writeup)

    # Add edges
    # Research and baseline start in parallel
    builder.add_edge(START, "node_research")
    builder.add_edge(START, "node_baseline")
    # Sequential flow: baseline → tuning → ablation → plotting
    builder.add_edge("node_baseline", "node_tuning")
    builder.add_edge("node_tuning", "node_ablation")
    builder.add_edge("node_ablation", "node_plotting")
    # Writeup waits for both research and plotting to complete
    builder.add_edge(["node_research", "node_plotting"], "node_writeup")
    builder.add_edge("node_writeup", END)

    checkpointer = AsyncSqliteSaver(conn=conn)
    return builder.compile(name="graph_all", checkpointer=checkpointer)  # type: ignore


class Args(BaseSettings):
    cwd: CliPositionalArg[Path]
    task: CliPositionalArg[Path]
    thread_id: Annotated[
        str,
        Field(default_factory=lambda: str(uuid.uuid4())),
    ]
    checkpoint_id: Annotated[
        str | None,
        Field(default=None),
    ]
    checkpoint_db: Annotated[
        Path,
        Field(default=Path("checkpoints.db")),
    ]
    model: Annotated[
        str,
        Field(default="gpt-4o-mini"),
    ]
    temperature: Annotated[
        float,
        Field(default=0.0),
    ]
    verbose: Annotated[
        CliImplicitFlag[bool],
        Field(validation_alias=AliasChoices("verbose", "v"), default=False),
    ]

    async def cli_cmd(self) -> None:
        self.cwd.mkdir(parents=True, exist_ok=True)

        if self.verbose:
            log.init()

        logger.info("thread_id:", self.thread_id)
        if self.checkpoint_id:
            logger.info("checkpoint_id:", self.checkpoint_id)

        configurable = {"thread_id": self.thread_id}
        if self.checkpoint_id:
            configurable["checkpoint_id"] = self.checkpoint_id

        config = RunnableConfig(
            callbacks=[CallbackHandler()],
            configurable=configurable,
        )

        task = utils.Task.model_validate_json(self.task.read_text())
        state = State(cwd=self.cwd, task=task)
        context = Context(model=self.model, temperature=self.temperature)

        async with aiosqlite.connect(self.checkpoint_db) as conn:
            graph = build(conn)
            result = await graph.ainvoke(input=state, context=context, config=config)
            print(json.dumps(result, indent=2, sort_keys=True, default=str))


if __name__ == "__main__":
    CliApp.run(Args)
