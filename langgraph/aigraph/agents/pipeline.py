import json
import logging
import operator as op
import uuid
from pathlib import Path
from typing import Annotated, Any

from aigraph import utils
from aigraph.agents import experiment, ideas, reviewer
from langchain.chat_models import BaseChatModel, init_chat_model
from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph
from langgraph.runtime import Runtime
from langgraph.types import Checkpointer, Send
from pydantic import BaseModel

logger = logging.getLogger(__name__)


class Context(BaseModel):
    model: str = "gpt-4o-mini"
    temperature: float = 0.0
    max_iterations: int = 3

    # Stage: ideas
    stage_ideas_model: str = "gpt-4.1"
    stage_ideas_temperature: float = 0.7
    stage_ideas_num_ideas: int = 5

    # Stage: baseline
    stage_baseline_model: str = "gpt-4.1"
    stage_baseline_temperature: float = 0.0
    stage_baseline_max_retries: int = 5

    # Stage: tuning
    stage_tuning_model: str = "gpt-4.1"
    stage_tuning_temperature: float = 0.0
    stage_tuning_max_retries: int = 5

    # Stage: ablation
    stage_ablation_model: str = "gpt-4.1"
    stage_ablation_temperature: float = 0.0
    stage_ablation_max_retries: int = 5

    # Stage: plotting
    stage_plotting_model: str = "gpt-4.1"
    stage_plotting_temperature: float = 0.0
    stage_plotting_max_retries: int = 5

    # Stage: writeup
    stage_writeup_model: str = "gpt-4.1"
    stage_writeup_temperature: float = 0.0
    stage_writeup_max_retries: int = 5

    # Stage: reviewer
    stage_reviewer_model: str = "gpt-4.1"
    stage_reviewer_temperature: float = 0.0

    # Stage: research (open_deep_research)
    stage_research_model: str = "gpt-4.1"
    stage_research_final_report_model: str = "gpt-4.1"

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
        num_ideas=runtime.context.stage_ideas_num_ideas,
        model=runtime.context.stage_ideas_model or runtime.context.model,
        temperature=runtime.context.stage_ideas_temperature,
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
        # baseline
        stage_baseline_model=runtime.context.stage_baseline_model,
        stage_baseline_temperature=runtime.context.stage_baseline_temperature,
        stage_baseline_max_retries=runtime.context.stage_baseline_max_retries,
        # tuning
        stage_tuning_model=runtime.context.stage_tuning_model,
        stage_tuning_temperature=runtime.context.stage_tuning_temperature,
        stage_tuning_max_retries=runtime.context.stage_tuning_max_retries,
        # ablation
        stage_ablation_model=runtime.context.stage_ablation_model,
        stage_ablation_temperature=runtime.context.stage_ablation_temperature,
        stage_ablation_max_retries=runtime.context.stage_ablation_max_retries,
        # plotting
        stage_plotting_model=runtime.context.stage_plotting_model,
        stage_plotting_temperature=runtime.context.stage_plotting_temperature,
        stage_plotting_max_retries=runtime.context.stage_plotting_max_retries,
        # writeup
        stage_writeup_model=runtime.context.stage_writeup_model,
        stage_writeup_temperature=runtime.context.stage_writeup_temperature,
        stage_writeup_max_retries=runtime.context.stage_writeup_max_retries,
        # research
        stage_research_model=runtime.context.stage_research_model,
        stage_research_final_report_model=runtime.context.stage_research_final_report_model,
    )
    result = await graph.ainvoke(input=state, context=experiment_context)
    result = experiment.State.model_validate(result)

    file = state.cwd / "state.json"
    file.write_text(result.model_dump_json(indent=2))

    if result.state_research and result.state_research.research:
        file = state.cwd / "research.json"
        report = result.state_research.research.get("final_report")
        file.write_text(json.dumps(report, indent=2))

    logger.info("Finished node_experiment")
    return {"experiments": [result]}


async def node_review(state: State, runtime: Runtime[Context]) -> dict[str, Any]:
    logger.info("Starting node_review")

    review_state = reviewer.State(
        task=state.task,
        experiments=state.experiments,
    )
    review_context = reviewer.Context(
        model=runtime.context.stage_reviewer_model or runtime.context.model,
        temperature=runtime.context.stage_reviewer_temperature,
    )

    graph = reviewer.build(checkpointer=True)
    result = await graph.ainvoke(input=review_state, context=review_context)
    result = reviewer.State.model_validate(result)
    assert result.review is not None

    filename = state.cwd / f"review_{state.iteration:03d}.json"
    filename.write_text(result.model_dump_json(indent=2))

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
