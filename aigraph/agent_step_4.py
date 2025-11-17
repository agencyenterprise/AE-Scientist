import asyncio
import logging
from tempfile import NamedTemporaryFile
from typing import Literal

from langchain.chat_models import init_chat_model
from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph
from langgraph.runtime import Runtime
from pydantic import BaseModel

logger = logging.getLogger(__name__)


PROMPT_PROPOSE_ABLATION = """
You are an AI researcher conducting ablation studies. Based on the current
implementation and previous ablations (if any), propose ONE new ablation study
that tests a different aspect of the model.

## Base code you are working on

{base_code}

## Previous Ablations

{completed_ablations}

## Requirements

1. Identify ONE specific component/feature to ablate
2. Ensure the ablation is different from previous completed or running attempts
3. The ablation should be a new idea, not a variation of previous ideas
4. If you have only used a single synthetic dataset throughout the experiment,
   one of your ablations should be to use multiple synthetic datasets (at least
   3 different datasets)
"""


PROMPT_IMPLEMENT_ABLATION = """
You are an experienced AI researcher. You are provided with a previously
developed baseline implementation. Your task is to implement the ablation study
for the following idea:

**{ablation_name}**

{ablation_description}

## Base code you are working on

{base_code}

## Implementation Guidelines

- The code should be a single-file python program that is self-contained and can
  be executed as-is.
- No parts of the code should be skipped, don't terminate the code execution
  before finishing the script.
- Data saving requirements: * Save all plottable data (metrics, losses,
  predictions, etc.) as numpy arrays using np.save() * Use the following naming
  convention for saved files:
    ```python # At the start of your code experiment_data = {{
        'ablation_type_1': {{
            'dataset_name_1': {{
                'metrics': {{'train': [], 'val': []}}, 'losses': {{'train': [],
                'val': []}}, 'predictions': [], 'ground_truth': [],
            }},
        }},
    }}
    ```
  * Make sure to use a filename 'experiment_data.npy' to save the data. Do not
    use any other filename.
"""


PROMPT_EVALUATE = """
Evaluate if the ablation sub-stage is complete given the goals.

## Evidence

- Return code: {returncode}
- Stdout: {stdout}
- Stderr: {stderr}

## Requirements for Completion

- Conduct systematic component analysis that reveals the contribution of each
  part
- Use the same datasets you used from the previous stage
- Ablation variations should produce consistent and interpretable differences
"""


# Pydantic schemas for structured outputs
class ProposeAblationSchema(BaseModel):
    name: str
    description: str


class ImplementAblationSchema(BaseModel):
    code: str
    dependencies: list[str]


class EvaluateSchema(BaseModel):
    is_complete: bool
    reasoning: str
    missing_criteria: list[str]


class State(BaseModel):
    # inputs
    idea: str
    base_code: str

    # working
    completed_ablations: list[str] = []
    current_ablation_name: str | None = None
    current_ablation_description: str | None = None

    # outputs
    code: str | None = None
    dependencies: list[str] | None = None
    returncode: int | None = None
    stdout: str | None = None
    stderr: str | None = None

    # control
    is_complete: bool = False
    iteration_count: int = 0


class Context(BaseModel):
    model: str = "gpt-4o-mini"
    temperature: float = 0.0
    max_iterations: int = 5


async def node_propose_ablation(state: State, runtime: Runtime[Context]) -> State:
    """Propose the next ablation study."""
    logger.info("Starting node_propose_ablation")

    llm = init_chat_model(model=runtime.context.model, temperature=runtime.context.temperature)
    llms = llm.with_structured_output(ProposeAblationSchema)

    completed_list = state.completed_ablations if state.completed_ablations else ["Nothing has been tried yet."]
    prompt = PROMPT_PROPOSE_ABLATION.format(
        base_code=state.base_code,
        completed_ablations="\n".join(f"- {abl}" for abl in completed_list)
    )

    logger.info("Calling LLM to propose ablation")
    response: ProposeAblationSchema = await llms.ainvoke(prompt)  # type: ignore

    state.current_ablation_name = response.name
    state.current_ablation_description = response.description

    logger.info(f"Proposed ablation: {response.name}")
    return state


async def node_implement_ablation(state: State, runtime: Runtime[Context]) -> State:
    """Generate ablation code based on the proposed ablation study."""
    logger.info("Starting node_implement_ablation")

    llm = init_chat_model(model=runtime.context.model, temperature=runtime.context.temperature)
    llms = llm.with_structured_output(ImplementAblationSchema)

    prompt = PROMPT_IMPLEMENT_ABLATION.format(
        ablation_name=state.current_ablation_name or "unknown",
        ablation_description=state.current_ablation_description or "",
        base_code=state.base_code
    )

    logger.info("Calling LLM to implement ablation")
    response: ImplementAblationSchema = await llms.ainvoke(prompt)  # type: ignore

    state.code = response.code
    state.dependencies = response.dependencies

    logger.info(f"Generated {len(response.code)} characters of ablation code")
    return state


async def node_run(state: State, runtime: Runtime[Context]) -> State:
    """Execute the generated ablation code."""
    logger.info("Starting node_run")

    code = state.code or ""
    dependencies = state.dependencies or []

    assert code, 'code is required'

    with NamedTemporaryFile(mode="wt", suffix=".py", delete=False) as tmp:
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

    logger.info(f"node_run completed with returncode: {proc.returncode}")
    return state


async def node_evaluate(state: State, runtime: Runtime[Context]) -> State:
    """Evaluate if the ablation stage is complete."""
    logger.info("Starting node_evaluate")

    llm = init_chat_model(model=runtime.context.model, temperature=runtime.context.temperature)
    llms = llm.with_structured_output(EvaluateSchema)

    prompt = PROMPT_EVALUATE.format(
        returncode=state.returncode or "N/A",
        stdout=(state.stdout or "")[:500],  # Limit to first 500 chars
        stderr=(state.stderr or "")[:500]   # Limit to first 500 chars
    )

    logger.info("Calling LLM to evaluate completion")
    response: EvaluateSchema = await llms.ainvoke(prompt)  # type: ignore

    state.is_complete = response.is_complete
    state.iteration_count += 1

    # If successful (returncode 0 and has ablation name), add to completed list
    if state.returncode == 0 and state.current_ablation_name:
        if state.current_ablation_name not in state.completed_ablations:
            state.completed_ablations.append(state.current_ablation_name)

    logger.info(f"Evaluation complete. is_complete={response.is_complete}, iteration={state.iteration_count}")
    return state


def should_continue(state: State, context: Context) -> Literal["node_propose_ablation", "__end__"]:
    """Determine if we should continue iterating or end."""
    if state.is_complete:
        logger.info("Stage complete - ending")
        return END
    if state.iteration_count >= context.max_iterations:
        logger.info(f"Max iterations ({context.max_iterations}) reached - ending")
        return END
    logger.info("Continuing to next iteration")
    return "node_propose_ablation"


def build() -> CompiledStateGraph[State, Context, State, State]:
    """Build the Stage 4 ablation studies graph."""
    builder = StateGraph(state_schema=State, context_schema=Context)

    # Add nodes
    builder.add_node("node_propose_ablation", node_propose_ablation)
    builder.add_node("node_implement_ablation", node_implement_ablation)
    builder.add_node("node_run", node_run)
    builder.add_node("node_evaluate", node_evaluate)

    # Add edges
    builder.add_edge(START, "node_propose_ablation")
    builder.add_edge("node_propose_ablation", "node_implement_ablation")
    builder.add_edge("node_implement_ablation", "node_run")
    builder.add_edge("node_run", "node_evaluate")
    
    # Add conditional edge from evaluate back to propose or to end
    builder.add_conditional_edges("node_evaluate", should_continue)

    return builder.compile()  # type: ignore

