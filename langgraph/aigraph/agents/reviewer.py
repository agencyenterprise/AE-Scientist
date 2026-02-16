import logging
import uuid
from typing import Any, cast

from langchain.chat_models import BaseChatModel, init_chat_model
from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph
from langgraph.runtime import Runtime
from langgraph.types import Checkpointer
from pydantic import BaseModel

from aigraph import utils
from aigraph.agents import experiment
from aigraph.agents import reviewer_prompts as prompts

logger = logging.getLogger(__name__)


class Reviewed(BaseModel):
    id: uuid.UUID
    reasoning: str


class ReviewOutput(BaseModel):
    """Full output of the review process."""

    done: list[Reviewed]
    drop: list[Reviewed]
    retry: list[Reviewed]


class State(BaseModel):
    """State for reviewing and evaluating experiments.

    Attributes:
        task: Evaluation criteria for experiments.
              Included in review prompt for task-relevant judgment.
        experiments: All experiment states to judge.
                      Serialized and fed to build_prompt_review() for LLM evaluation.
        review: Output: done (accept), drop (discard), retry (rerun).
                Each list contains {id, reasoning}, used by pipeline to route.
    """

    task: utils.Task
    experiments: list[experiment.State]

    review: ReviewOutput | None = None


class Context(BaseModel):
    model: str = "gpt-4o-mini"
    temperature: float = 0.0

    @property
    def llm(self) -> BaseChatModel:
        return init_chat_model(model=self.model, temperature=self.temperature)


async def node_review(state: State, runtime: Runtime[Context]) -> dict[str, Any]:
    logger.info("Starting node_review")

    prompt = prompts.build_prompt_review(
        task=state.task,
        experiments=state.experiments,
    )

    llm = runtime.context.llm.with_structured_output(ReviewOutput)
    result = await llm.ainvoke(prompt)
    result = cast(ReviewOutput, result)

    logger.debug(f"Done {len(result.done)} experiments")
    logger.debug(f"Retry {len(result.retry)} experiments")
    logger.debug(f"Drop {len(result.drop)} experiments")

    logger.info("Finished node_review")
    return {"review": result}


def build(
    checkpointer: Checkpointer | None = None,
) -> CompiledStateGraph[State, Context, State, State]:
    builder = StateGraph(state_schema=State, context_schema=Context)

    # Nodes
    builder.add_node("node_review", node_review)

    # Edges
    builder.add_edge(START, "node_review")
    builder.add_edge("node_review", END)

    return builder.compile(name="graph_reviewer", checkpointer=checkpointer)  # type: ignore
