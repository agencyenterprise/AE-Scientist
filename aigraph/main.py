import logging
from pathlib import Path

from langchain.chat_models import BaseChatModel, init_chat_model
from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph
from langgraph.runtime import Runtime
from pydantic import BaseModel

from aigraph import agent_step_1, agent_step_2, agent_step_3, agent_step_4, utils

logger = logging.getLogger(__name__)


class State(BaseModel):
    """Main state that coordinates all agent steps."""

    # Input
    cwd: Path
    task: utils.Task

    step1_state: agent_step_1.State | None = None
    step2_state: agent_step_2.State | None = None
    step3_state: agent_step_3.State | None = None
    step4_state: agent_step_4.State | None = None


class Context(BaseModel):
    model: str = "gpt-4o-mini"
    temperature: float = 0.0

    @property
    def llm(self) -> BaseChatModel:
        return init_chat_model(model=self.model, temperature=self.temperature)


async def node_step1_baseline(state: State, runtime: Runtime[Context]) -> State:
    logger.info("Starting Step 1: Baseline Experiment")

    step1_state = agent_step_1.State(
        cwd=state.cwd,
        task=state.task,
    )

    context = agent_step_1.Context(
        model=runtime.context.model,
        temperature=runtime.context.temperature,
    )

    step1_graph = agent_step_1.build()
    result = await step1_graph.ainvoke(step1_state, context=context)
    state.step1_state = agent_step_1.State.model_validate(result)

    log = "Step 1 completed. Metrics defined: %d"
    logger.info(log, len(state.step1_state.metrics))
    return state


async def node_step2_tuning(state: State, runtime: Runtime[Context]) -> State:
    logger.info("Starting Step 2: Hyperparameter Tuning")
    assert state.step1_state, "Step 1 state is required"
    assert state.step1_state.experiment_code, "Experiment code is required"

    step2_state = agent_step_2.State(
        cwd=state.cwd,
        task=state.task,
        code=state.step1_state.experiment_code,
    )

    context = agent_step_2.Context(
        model=runtime.context.model,
        temperature=runtime.context.temperature,
    )

    step2_graph = agent_step_2.build()
    result = await step2_graph.ainvoke(step2_state, context=context)
    state.step2_state = agent_step_2.State.model_validate(result)

    log = "Step 2 completed. Hyperparams proposed: %d"
    logger.info(log, len(state.step2_state.hyperparams))
    return state


# async def node_step3_plotting(state: State, runtime: Runtime[Context]) -> State:
#     logger.info("Starting Step 3: Plotting")
#     assert state.step1_state, "Step 1 state is required"
#     assert state.step2_state, "Step 2 state is required"
#     assert state.step2_state.tuning_code, "Tuning code is required"

#     step3_state = agent_step_3.State(
#         task=state.task,
#         code=state.step2_state.tuning_code,
#     )

#     context = agent_step_3.Context(
#         model=runtime.context.model,
#         temperature=runtime.context.temperature,
#     )

#     step3_graph = agent_step_3.build()
#     result = await step3_graph.ainvoke(step3_state, context=context)
#     state.step3_state = agent_step_3.State.model_validate(result)

#     logger.info("Step 3 completed. Plots generated.")
#     return state


# async def node_step4_ablation(state: State, runtime: Runtime[Context]) -> State:
#     logger.info("Starting Step 4: Ablation Studies")
#     assert state.step1_state, "Step 1 state is required"
#     assert state.step2_state, "Step 2 state is required"
#     assert state.step2_state.tuning_code, "Tuning code is required"

#     step4_state = agent_step_4.State(
#         task=state.task,
#         code=state.step2_state.tuning_code,
#     )

#     context = agent_step_4.Context(
#         model=runtime.context.model,
#         temperature=runtime.context.temperature,
#     )

#     step4_graph = agent_step_4.build()
#     result = await step4_graph.ainvoke(step4_state, context=context)
#     state.step4_state = agent_step_4.State.model_validate(result)

#     log = "Step 4 completed. Ablations performed: %d"
#     logger.info(log, len(state.step4_state.ablations))
#     return state


def build() -> CompiledStateGraph[State, Context, State, State]:
    """Build the main graph that orchestrates all agent steps."""
    builder = StateGraph(state_schema=State, context_schema=Context)

    # Add nodes for each step
    builder.add_node("step1_baseline", node_step1_baseline)
    builder.add_node("step2_tuning", node_step2_tuning)
    # builder.add_node("step3_plotting", node_step3_plotting)
    # builder.add_node("step4_ablation", node_step4_ablation)

    # Add edges (sequential flow)
    builder.add_edge(START, "step1_baseline")
    builder.add_edge("step1_baseline", "step2_tuning")
    # builder.add_edge("step2_tuning", "step3_plotting")
    # builder.add_edge("step3_plotting", "step4_ablation")
    # builder.add_edge("step4_ablation", END)
    builder.add_edge("step2_tuning", END)

    return builder.compile()  # type: ignore
