import logging
import operator
import uuid
from pathlib import Path
from typing import Annotated, Any, cast

from langchain.chat_models import BaseChatModel, init_chat_model
from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph
from langgraph.runtime import Runtime
from langgraph.types import Checkpointer
from pydantic import BaseModel

from aigraph import utils
from aigraph.agents import (
    ablation,
    baseline,
    plotting,
    research,
    tuning,
    writeup,
)
from aigraph.agents import experiment_prompts as prompts

logger = logging.getLogger(__name__)


class State(BaseModel):
    """Sub-orchestrator state for a single experiment.

    Attributes:
        id: Unique ID for tracking across retries.
            Used in node_retry to map failed experiments to their original idea.
        cwd: Parent directory for all stage outputs.
             mkdir(parents=True) in setup, passed to all child stages.
        task: Passed to all child stages.
              Injected into each sub-agent's State constructor.
        idea: The specific hypothesis to test.
              Passed to all stages for context-aware code generation.
        state_research: Stores complete state from research stage.
                       Asserted for required fields before passing to next stage.
        state_baseline: Stores complete state from baseline stage.
                        Asserted for required fields before passing to next stage.
        state_tuning: Stores complete state from tuning stage.
                      Asserted for required fields before passing to next stage.
        state_ablation: Stores complete state from ablation stage.
                        Asserted for required fields before passing to next stage.
        state_plotting: Stores complete state from plotting stage.
                        Asserted for required fields before passing to next stage.
        state_writeup: Stores complete state from writeup stage.
                        Asserted for required fields before passing to next stage.
        notes: Accumulated learnings passed between stages.
               Extended via op.add reducer from baseline → tuning → ablation.
        review: Final judge verdict (passed/failed).
                Set by node_judge using LLM evaluation of all outputs.
    """

    # the unique identifier of the experiment
    id: uuid.UUID

    cwd: Path
    task: utils.Task
    idea: utils.Idea

    state_research: research.State | None = None
    state_baseline: baseline.State | None = None
    state_tuning: tuning.State | None = None
    state_ablation: ablation.State | None = None
    state_plotting: plotting.State | None = None
    state_writeup: writeup.State | None = None

    notes: Annotated[list[str], operator.add] = []

    # Judge review
    review: utils.Review | None = None


class Context(BaseModel):
    model: str = "gpt-4o-mini"
    temperature: float = 0.0

    @property
    def llm(self) -> BaseChatModel:
        return init_chat_model(model=self.model, temperature=self.temperature)


async def node_setup(state: State, runtime: Runtime[Context]) -> dict[str, Any]:
    logger.info("Starting node_setup")
    state.cwd.mkdir(parents=True, exist_ok=True)
    logger.info("Finished node_setup")
    return {}


async def node_research(state: State, runtime: Runtime[Context]) -> dict[str, Any]:
    logger.info("Starting node_research")

    research_state = research.State(cwd=state.cwd, task=state.task)
    graph = research.build(checkpointer=True)
    result = await graph.ainvoke(input=research_state)
    result = research.State.model_validate(result)

    logger.info("Finished node_research")
    return {"state_research": result}


async def node_baseline(state: State, runtime: Runtime[Context]) -> dict[str, Any]:
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
    return {"state_baseline": result, "notes": result.notes}


async def node_tuning(state: State, runtime: Runtime[Context]) -> dict[str, Any]:
    logger.info("Starting node_tuning")

    assert state.state_baseline
    assert state.state_baseline.experiment_code

    tuning_state = tuning.State(
        cwd=state.cwd,
        task=state.task,
        code=state.state_baseline.experiment_code,
        idea=state.idea,
        research=state.state_baseline.research,
        notes=state.notes,
    )

    tuning_context = tuning.Context(
        model=runtime.context.model,
        temperature=runtime.context.temperature,
    )

    graph = tuning.build(checkpointer=True)
    result = await graph.ainvoke(input=tuning_state, context=tuning_context)
    result = tuning.State.model_validate(result)

    logger.info("Finished node_tuning")
    return {"state_tuning": result, "notes": result.notes}


async def node_ablation(state: State, runtime: Runtime[Context]) -> dict[str, Any]:
    logger.info("Starting node_ablation")

    assert state.state_tuning
    assert state.state_tuning.tuning_code

    ablation_state = ablation.State(
        cwd=state.cwd,
        task=state.task,
        code=state.state_tuning.tuning_code,
        idea=state.idea,
        research=state.state_tuning.research,
        notes=state.notes,
    )

    ablation_context = ablation.Context(
        model=runtime.context.model,
        temperature=runtime.context.temperature,
    )

    graph = ablation.build(checkpointer=True)
    result = await graph.ainvoke(input=ablation_state, context=ablation_context)
    result = ablation.State.model_validate(result)

    logger.info("Finished node_ablation")
    return {"state_ablation": result, "notes": result.notes}


async def node_plotting(state: State, runtime: Runtime[Context]) -> dict[str, Any]:
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


async def node_writeup(state: State, runtime: Runtime[Context]) -> dict[str, Any]:
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


async def node_judge(state: State, runtime: Runtime[Context]) -> dict[str, Any]:
    logger.info("Starting node_judge")

    ablation = state.state_ablation
    code = ablation.ablation_code if ablation else ""
    code_stdout = ablation.ablation_stdout if ablation else ""
    parser_stdout = ablation.parser_stdout if ablation else ""
    latex = state.state_writeup.latex_content if state.state_writeup else ""

    prompt = prompts.build_prompt_evaluate(
        idea=state.idea,
        code=code or "",
        code_stdout=code_stdout or "",
        parser_stdout=parser_stdout or "",
        latex=latex or "",
        notes=state.notes,
    )

    llm = runtime.context.llm.with_structured_output(utils.Review)
    result = await llm.ainvoke(prompt)
    result = cast(utils.Review, result)

    logger.debug(f"Review: passed={result.passed}")
    logger.debug(f"Review: reasoning={result.reasoning[:32]!r}")

    logger.info("Finished node_judge")
    return {"review": result}


def build(
    checkpointer: Checkpointer | None = None,
) -> CompiledStateGraph[State, Context, State, State]:
    builder = StateGraph(state_schema=State, context_schema=Context)

    # Add nodes
    builder.add_node("node_setup", node_setup)
    builder.add_node("node_research", node_research)
    builder.add_node("node_baseline", node_baseline)
    builder.add_node("node_tuning", node_tuning)
    builder.add_node("node_ablation", node_ablation)
    builder.add_node("node_plotting", node_plotting)
    builder.add_node("node_writeup", node_writeup)
    builder.add_node("node_judge", node_judge)

    # Add edges
    builder.add_edge(START, "node_setup")
    builder.add_edge("node_setup", "node_research")
    builder.add_edge("node_research", "node_baseline")
    builder.add_edge("node_baseline", "node_tuning")
    builder.add_edge("node_tuning", "node_ablation")
    builder.add_edge("node_ablation", "node_plotting")
    builder.add_edge("node_plotting", "node_writeup")
    builder.add_edge("node_writeup", "node_judge")
    builder.add_edge("node_judge", END)

    return builder.compile(name="graph_experiment", checkpointer=checkpointer)  # type: ignore
