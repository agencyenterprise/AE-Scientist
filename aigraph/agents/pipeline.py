import logging
import operator as op
from pathlib import Path
from typing import Annotated, Any

from langchain.chat_models import BaseChatModel, init_chat_model
from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph
from langgraph.runtime import Runtime
from langgraph.types import Checkpointer, Send
from pydantic import BaseModel

from aigraph import utils
from aigraph.agents import experiment, ideas

logger = logging.getLogger(__name__)


class Context(BaseModel):
    model: str = "gpt-4o-mini"
    temperature: float = 0.0

    @property
    def llm(self) -> BaseChatModel:
        return init_chat_model(model=self.model, temperature=self.temperature)


class State(BaseModel):
    # inputs
    cwd: Path
    task: utils.Task

    # state
    experiments: Annotated[list[experiment.State], op.add] = []


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
                "node_experiment",
                experiment.State(
                    idea=idea,
                    task=state.task,
                    cwd=state.cwd / f"idea_{i:03d}",
                ),
            )
        )

    logger.info("Finished node_ideas")
    return sends


async def node_experiment(
    state: experiment.State,
    runtime: Runtime[Context],
) -> dict[str, Any]:
    """Runs experiment graph."""
    logger.info("Starting node_experiment")

    graph = experiment.build(checkpointer=True)
    experiment_context = experiment.Context(
        model=runtime.context.model,
        temperature=runtime.context.temperature,
    )
    result = await graph.ainvoke(input=state, context=experiment_context)
    result = experiment.State.model_validate(result)

    logger.info("Finished node_experiment")
    return {"experiments": [result]}


def build(
    checkpointer: Checkpointer | None = None,
) -> CompiledStateGraph[State, Context, State, State]:
    builder = StateGraph(state_schema=State, context_schema=Context)

    # Add nodes
    builder.add_node("node_ideas", node_ideas)
    builder.add_node("node_experiment", node_experiment)

    # Add edges
    builder.add_conditional_edges(START, node_ideas, ["node_experiment"])
    builder.add_edge("node_experiment", END)

    return builder.compile(name="graph_all", checkpointer=checkpointer)  # type: ignore
