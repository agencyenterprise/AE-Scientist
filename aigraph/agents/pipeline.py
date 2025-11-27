import json
import logging
import operator as op
import uuid
from pathlib import Path
from typing import Annotated, Any

from langchain.chat_models import BaseChatModel, init_chat_model
from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph
from langgraph.runtime import Runtime
from langgraph.types import Checkpointer, Send
from pydantic import BaseModel

from aigraph import utils
from aigraph.agents import experiment, ideas, reviewer

logger = logging.getLogger(__name__)


class Context(BaseModel):
    model: str = "gpt-4o-mini"
    temperature: float = 0.0
    max_iterations: int = 3

    @property
    def llm(self) -> BaseChatModel:
        return init_chat_model(model=self.model, temperature=self.temperature)


class State(BaseModel):
    """Main orchestrator state for the research pipeline.

    Attributes:
        cwd: Root directory for all experiment outputs.
             Combined with iteration + UUID to create unique experiment folders.
        task: Research task passed to all sub-agents.
              Injected into ideas.State and experiment.State via Send.
        iteration: Tracks retry loop count for failed experiments.
                   Compared against max_iterations in node_retry to stop retrying.
        experiments: Collects results from parallel experiment runs.
                     Aggregated via op.add reducer, passed to reviewer for evaluation.
        reviews: Stores reviewer decisions (done/drop/retry) per iteration.
                 Last review's retry list determines which experiments to re-run.
    """

    # inputs
    cwd: Path
    task: utils.Task

    # state
    iteration: int = 0
    experiments: Annotated[list[experiment.State], op.add] = []
    reviews: Annotated[list[reviewer.ReviewOutput], op.add] = []


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
        id = uuid.uuid4()
        sends.append(
            Send(
                "node_experiment",
                experiment.State(
                    id=id,
                    idea=idea,
                    task=state.task,
                    cwd=state.cwd / f"experiment_{state.iteration:03d}_{id}",
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
    state.cwd.mkdir(parents=True, exist_ok=True)

    file = state.cwd / "idea.json"
    file.write_text(state.idea.model_dump_json(indent=2))

    graph = experiment.build(checkpointer=True)
    experiment_context = experiment.Context(
        model=runtime.context.model,
        temperature=runtime.context.temperature,
    )
    result = await graph.ainvoke(input=state, context=experiment_context)
    result = experiment.State.model_validate(result)

    file = state.cwd / "state.json"
    file.write_text(result.model_dump_json(indent=2))

    if result.state_research:
        file = state.cwd / "research.json"
        file.write_text(json.dumps(result.state_research.research, indent=2))

    logger.info("Finished node_experiment")
    return {"experiments": [result]}


async def node_review(state: State, runtime: Runtime[Context]) -> dict[str, Any]:
    logger.info("Starting node_review")

    review_state = reviewer.State(
        task=state.task,
        experiments=state.experiments,
    )
    review_context = reviewer.Context(
        model=runtime.context.model,
        temperature=runtime.context.temperature,
    )

    graph = reviewer.build(checkpointer=True)
    result = await graph.ainvoke(input=review_state, context=review_context)
    result = reviewer.State.model_validate(result)
    assert result.review is not None

    for e in result.review.done:
        logger.info("Experiment %s is done", e.id)
    for e in result.review.drop:
        logger.debug(f"Experiment {e.id} is dropped")
    for e in result.review.retry:
        logger.info("Experiment %s is retry", e.id)

    return {"reviews": [result.review], "iteration": state.iteration + 1}


async def node_retry(state: State, runtime: Runtime[Context]) -> list[Send]:
    logger.info("Starting node_retry")
    assert state.reviews is not None
    assert len(state.reviews) > 0

    if state.iteration > runtime.context.max_iterations:
        logger.info("Max iterations reached")
        return [Send(END, {})]

    last = state.reviews[-1]
    iteration = state.iteration

    map = {exp.id: exp for exp in state.experiments}

    sends: list[Send] = []
    for e in last.retry:
        sends.append(
            Send(
                "node_experiment",
                experiment.State(
                    id=e.id,
                    idea=map[e.id].idea,
                    task=state.task,
                    cwd=state.cwd / f"experiment_{iteration:03d}_{e.id}",
                ),
            )
        )

    return sends


def build(
    checkpointer: Checkpointer | None = None,
) -> CompiledStateGraph[State, Context, State, State]:
    builder = StateGraph(state_schema=State, context_schema=Context)

    # Add nodes
    builder.add_node("node_ideas", node_ideas)
    builder.add_node("node_experiment", node_experiment)
    builder.add_node("node_review", node_review)

    # Add edges
    builder.add_conditional_edges(START, node_ideas, ["node_experiment"])
    builder.add_edge("node_experiment", "node_review")
    builder.add_conditional_edges("node_review", node_retry, ["node_experiment", END])

    return builder.compile(name="graph_all", checkpointer=checkpointer)  # type: ignore
