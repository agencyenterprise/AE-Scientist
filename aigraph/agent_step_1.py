import logging
from typing import Literal

from langchain.chat_models import init_chat_model
from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph
from langgraph.runtime import Runtime
from pydantic import BaseModel

from aigraph import prompts, utils

logger = logging.getLogger(__name__)


class State(BaseModel):
    # inputs
    task: utils.Task
    metrics: list[utils.Metric]

    # state
    plan: str | None = None
    code: str | None = None
    memory: str | None = None


class Context(BaseModel):
    model: str = "gpt-4o-mini"
    temperature: float = 0.0


async def node_define_metrics(state: State, runtime: Runtime[Context]) -> State:
    logger.info("Starting node_define_metrics")

    class Schema(BaseModel):
        metrics: list[utils.Metric]

    llm = init_chat_model(model=runtime.context.model, temperature=runtime.context.temperature)
    llms = llm.with_structured_output(Schema)

    prompt = prompts.build_prompt_metrics(state.task)
    response: Schema = await llms.ainvoke(prompt)  # type: ignore
    state.metrics = response.metrics

    logger.info("node_define_metrics completed")
    return state


async def node_plan_and_code(state: State, runtime: Runtime[Context]) -> State:
    logger.info("Starting node_plan_and_code")

    class Schema(BaseModel):
        plan: str
        code: str

    llm = init_chat_model(model=runtime.context.model, temperature=runtime.context.temperature)
    llms = llm.with_structured_output(Schema)

    prompt = prompts.build_prompt_plan_and_code(state.task, state.metrics, state.memory)
    response: Schema = await llms.ainvoke(prompt)  # type: ignore
    state.plan = response.plan
    state.code = response.code

    logger.info("node_plan_and_code completed")
    return state


async def node_code_extraction(state: State, runtime: Runtime[Context]) -> State:
    logger.info("Starting node_code_extraction")
    logger.info("node_code_extraction completed")
    return state


async def node_execute(state: State, runtime: Runtime[Context]) -> State:
    logger.info("Starting node_execute")
    logger.info("node_execute completed")
    return state


async def node_execution_analysis(state: State, runtime: Runtime[Context]) -> State:
    logger.info("Starting node_execution_analysis")
    logger.info("node_execution_analysis completed")
    return state


async def node_metrics_parsing(state: State, runtime: Runtime[Context]) -> State:
    logger.info("Starting node_metrics_parsing")
    logger.info("node_metrics_parsing completed")
    return state


async def node_generate_summary(state: State, runtime: Runtime[Context]) -> State:
    logger.info("Starting node_generate_summary")
    logger.info("node_generate_summary completed")
    return state


async def node_retry_decision(state: State, runtime: Runtime[Context]) -> State:
    logger.info("Starting node_retry_decision")
    logger.info("node_retry_decision completed")
    return state


async def node_substage_completion(state: State, runtime: Runtime[Context]) -> State:
    logger.info("Starting node_substage_completion")
    logger.info("node_substage_completion completed")
    return state


async def node_stage_completion(state: State, runtime: Runtime[Context]) -> State:
    logger.info("Starting node_stage_completion")
    logger.info("node_stage_completion completed")
    return state


def build() -> CompiledStateGraph[State, Context, State, State]:
    builder = StateGraph(state_schema=State, context_schema=Context)

    # Add nodes
    builder.add_node("draft", node_draft)
    builder.add_node("improve", node_improve)
    builder.add_node("run", node_run)
    builder.add_node("check_completion", node_check_completion)
    
    # Add edges
    builder.add_edge(START, "draft")
    builder.add_edge("draft", "run")
    builder.add_edge("run", "check_completion")
    builder.add_edge("improve", "run")

    builder.add_conditional_edges(
        "check_completion",
        should_continue,
        {"improve": "improve", "end": END}
    )

    return builder.compile()  # type: ignore
