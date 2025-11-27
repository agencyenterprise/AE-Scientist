import logging
import operator as op
from pathlib import Path
from typing import Annotated, Any

import aiosqlite
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph
from langgraph.runtime import Runtime
from langgraph.types import Checkpointer, Send
from pydantic import BaseModel

from aigraph import utils
from aigraph.agents import (
    ablation,
    baseline,
    ideas,
    plotting,
    research,
    tuning,
    writeup,
)

logger = logging.getLogger(__name__)


class Experiment(BaseModel):
    cwd: Path
    task: utils.Task
    idea: utils.Idea

    state_research: research.State | None = None
    state_baseline: baseline.State | None = None
    state_tuning: tuning.State | None = None
    state_ablation: ablation.State | None = None
    state_plotting: plotting.State | None = None
    state_writeup: writeup.State | None = None


class State(BaseModel):
    # inputs
    cwd: Path
    task: utils.Task

    # state
    experiments: Annotated[list[Experiment], op.add] = []


class Context(BaseModel):
    model: str = "gpt-4o-mini"
    temperature: float = 0.0


async def node_ideas(state: State, runtime: Runtime[Context]) -> list[Send]:
    logger.info("Starting node_ideas")

    ideas_state = ideas.State(
        cwd=state.cwd,
        task=state.task,
    )

    ideas_context = ideas.Context(
        num_ideas=3,
        model=runtime.context.model,
        temperature=runtime.context.temperature,
    )

    graph = ideas.build(checkpointer=True)
    result = await graph.ainvoke(input=ideas_state, context=ideas_context)
    result = ideas.State.model_validate(result)

    for i, idea in enumerate(result.ideas, start=1):
        logger.debug(f"Idea name {i:03d}: {idea.name}")
        logger.debug(f"Idea description {i:03d}: {idea.description[:32]!r}")

    sends: list[Send] = []
    for i, idea in enumerate(result.ideas, start=1):
        sends.append(
            Send(
                "node_research",
                Experiment(
                    idea=idea,
                    task=state.task,
                    cwd=state.cwd / f"idea_{i:03d}",
                ),
            )
        )

    logger.info("Finished node_ideas")
    return sends


async def node_research(state: Experiment, runtime: Runtime[Context]) -> dict[str, Any]:
    logger.info("Starting node_research")

    research_state = research.State(cwd=state.cwd, task=state.task)
    graph = research.build(checkpointer=True)
    result = await graph.ainvoke(input=research_state)
    result = research.State.model_validate(result)

    logger.info("Finished node_research")
    return {"state_research": result}


async def node_baseline(state: Experiment, runtime: Runtime[Context]) -> dict[str, Any]:
    logger.info("Starting node_baseline")

    assert state.state_research
    assert state.state_research.research

    baseline_state = baseline.State(
        cwd=state.cwd,
        task=state.task,
        idea=state.idea,
        research=state.state_research.research["final_report"],
    )

    baseline_context = baseline.Context(
        model=runtime.context.model,
        temperature=runtime.context.temperature,
    )

    graph = baseline.build(checkpointer=True)
    result = await graph.ainvoke(input=baseline_state, context=baseline_context)
    result = baseline.State.model_validate(result)

    logger.info("Finished node_baseline")
    return {"state_baseline": result}


async def node_tuning(state: Experiment, runtime: Runtime[Context]) -> dict[str, Any]:
    logger.info("Starting node_tuning")

    assert state.state_baseline
    assert state.state_baseline.experiment_code

    tuning_state = tuning.State(
        cwd=state.cwd,
        task=state.task,
        code=state.state_baseline.experiment_code,
        idea=state.idea,
        research=state.state_baseline.research,
    )

    tuning_context = tuning.Context(
        model=runtime.context.model,
        temperature=runtime.context.temperature,
    )

    graph = tuning.build(checkpointer=True)
    result = await graph.ainvoke(input=tuning_state, context=tuning_context)
    result = tuning.State.model_validate(result)

    logger.info("Finished node_tuning")
    return {"state_tuning": result}


async def node_ablation(state: Experiment, runtime: Runtime[Context]) -> dict[str, Any]:
    logger.info("Starting node_ablation")

    assert state.state_tuning
    assert state.state_tuning.tuning_code

    ablation_state = ablation.State(
        cwd=state.cwd,
        task=state.task,
        code=state.state_tuning.tuning_code,
        idea=state.idea,
        research=state.state_tuning.research,
    )

    ablation_context = ablation.Context(
        model=runtime.context.model,
        temperature=runtime.context.temperature,
    )

    graph = ablation.build(checkpointer=True)
    result = await graph.ainvoke(input=ablation_state, context=ablation_context)
    result = ablation.State.model_validate(result)

    logger.info("Finished node_ablation")
    return {"state_ablation": result}


async def node_plotting(state: Experiment, runtime: Runtime[Context]) -> dict[str, Any]:
    logger.info("Starting node_plotting")

    assert state.state_ablation
    assert state.state_ablation.ablation_code

    plotting_state = plotting.State(
        cwd=state.cwd,
        task=state.task,
        code=state.state_ablation.ablation_code,
        idea=state.idea,
        research=state.state_ablation.research,
    )

    plotting_context = plotting.Context(
        model=runtime.context.model,
        temperature=runtime.context.temperature,
    )

    graph = plotting.build(checkpointer=True)
    result = await graph.ainvoke(input=plotting_state, context=plotting_context)
    result = plotting.State.model_validate(result)

    logger.info("Finished node_plotting")
    return {"state_plotting": result}


async def node_writeup(state: Experiment, runtime: Runtime[Context]) -> dict[str, Any]:
    logger.info("Starting node_writeup")

    assert state.state_plotting
    assert state.state_ablation
    assert state.state_ablation.ablation_code
    assert state.state_ablation.parser_code
    assert state.state_ablation.parser_stdout
    assert state.state_research
    assert state.state_research.research

    writeup_state = writeup.State(
        cwd=state.cwd,
        task=state.task,
        idea=state.idea,
        experiment_code=state.state_ablation.ablation_code,
        parser_code=state.state_ablation.parser_code,
        parser_stdout=state.state_ablation.parser_stdout,
        plots=list(state.state_plotting.plots),
        research=state.state_research.research["final_report"],
    )

    writeup_context = writeup.Context(
        model=runtime.context.model,
        temperature=runtime.context.temperature,
    )

    graph = writeup.build(checkpointer=True)
    result = await graph.ainvoke(input=writeup_state, context=writeup_context)
    result = writeup.State.model_validate(result)

    logger.info("Finished node_writeup")
    return {"state_writeup": result}


def build(
    conn: aiosqlite.Connection,
    checkpointer: Checkpointer | None = None,
) -> CompiledStateGraph[State, Context, State, State]:
    builder = StateGraph(state_schema=State, context_schema=Context)

    # Add nodes
    builder.add_node("node_ideas", node_ideas)
    builder.add_node("node_research", node_research)
    builder.add_node("node_baseline", node_baseline)
    builder.add_node("node_tuning", node_tuning)
    builder.add_node("node_ablation", node_ablation)
    builder.add_node("node_plotting", node_plotting)
    builder.add_node("node_writeup", node_writeup)

    # Add edges
    builder.add_conditional_edges(START, node_ideas, ["node_research"])
    builder.add_edge("node_research", "node_baseline")
    builder.add_edge("node_baseline", "node_tuning")
    builder.add_edge("node_tuning", "node_ablation")
    builder.add_edge("node_ablation", "node_plotting")
    builder.add_edge("node_writeup", END)

    if checkpointer is None:
        checkpointer = AsyncSqliteSaver(conn=conn)

    return builder.compile(name="graph_all", checkpointer=checkpointer)  # type: ignore
