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


PROMPT_PROPOSE_HYPERPARAM = """
You are an AI researcher conducting hyperparameter tuning for baseline
experiments. Based on the current implementation and previous hyperparameter
tuning attempts (if any), propose ONE new hyperparameter tuning idea to see if
it improves the performance.

You should first check if simply training longer (more epochs) improves the
performance. Then try tuning common hyperparameters such as learning rate, batch
size, etc. Only propose algorithm-specific and/or model-specific hyperparameters
after you have tried the above.

## Base code you are working on

{base_code}

## Previous Hyperparam Tuning Attempts

{tried_hyperparams}

## Requirements

1. Identify ONE specific hyperparameter to tune
2. Ensure the hyperparameter is different from previous attempts
"""


PROMPT_IMPLEMENT_TUNING = """
You are an experienced AI researcher. You are provided with a previously
developed baseline implementation. Your task is to implement hyperparameter
tuning for the following idea:

**{hyperparam_name}**

{hyperparam_description}

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
    ```python 
    # At the start of your code 
    experiment_data = {{
        'hyperparam_tuning_type_1': {{
            'dataset_name_1': {{
                'metrics': {{ 'train': [], 'val': [] }}, 
                'losses': {{ 'train': [], 'val': [] }}, 
                'predictions': [], 
                'ground_truth': [],
            }},
        }},
    }}
    ```
  * Make sure to use a filename 'experiment_data.npy' to save the data. Do not
    use any other filename.
"""


PROMPT_EVALUATE = """
Evaluate if Stage 2 (baseline tuning) sub-stage is complete.

## Evidence

- Datasets tested: {datasets_tested}
- Best metric: {best_metric}
- Return code: {returncode}
- Stdout: {stdout}
- Stderr: {stderr}

## Requirements for completion

- Change hyperparameters such as learning rate, number of epochs, batch size,
  etc. to improve the performance
- DO NOT change the model architecture from the previous stage
- Introduce additional datasets from HuggingFace to test the model. Use dataset
  sizes appropriate to the experiment. Use streaming=True for very large
  datasets.
- Training curves should show stable convergence
- Results should be tested on at least two datasets
- No major instabilities or issues in the plots
"""


# Pydantic schemas for structured outputs
class ProposeHyperparamSchema(BaseModel):
    name: str
    description: str


class ImplementTuningSchema(BaseModel):
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
    tried_hyperparams: list[str] = []
    current_hyperparam_name: str | None = None
    current_hyperparam_description: str | None = None

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


async def node_propose_hyperparam(state: State, runtime: Runtime[Context]) -> State:
    """Propose the next hyperparameter to tune."""
    logger.info("Starting node_propose_hyperparam")

    llm = init_chat_model(model=runtime.context.model, temperature=runtime.context.temperature)
    llms = llm.with_structured_output(ProposeHyperparamSchema)

    tried_list = state.tried_hyperparams or ["Nothing has been tried yet."]
    prompt = PROMPT_PROPOSE_HYPERPARAM.format(
        base_code=state.base_code,
        tried_hyperparams="\n".join(f"- {hp}" for hp in tried_list)
    )

    logger.info("Calling LLM to propose hyperparameter")
    response: ProposeHyperparamSchema = await llms.ainvoke(prompt)  # type: ignore

    state.current_hyperparam_name = response.name
    state.current_hyperparam_description = response.description

    logger.info(f"Proposed hyperparameter: {response.name}")
    return state


async def node_implement_tuning(state: State, runtime: Runtime[Context]) -> State:
    """Generate tuning code based on the proposed hyperparameter."""
    logger.info("Starting node_implement_tuning")

    llm = init_chat_model(model=runtime.context.model, temperature=runtime.context.temperature)
    llms = llm.with_structured_output(ImplementTuningSchema)

    prompt = PROMPT_IMPLEMENT_TUNING.format(
        hyperparam_name=state.current_hyperparam_name or "unknown",
        hyperparam_description=state.current_hyperparam_description or "",
        base_code=state.base_code
    )

    logger.info("Calling LLM to implement tuning")
    response: ImplementTuningSchema = await llms.ainvoke(prompt)  # type: ignore

    state.code = response.code
    state.dependencies = response.dependencies

    logger.info(f"Generated {len(response.code)} characters of tuning code")
    return state


async def node_run(state: State, runtime: Runtime[Context]) -> State:
    """Execute the generated tuning code."""
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
    """Evaluate if the stage is complete."""
    logger.info("Starting node_evaluate")

    llm = init_chat_model(model=runtime.context.model, temperature=runtime.context.temperature)
    llms = llm.with_structured_output(EvaluateSchema)

    # Extract dataset information from stdout/stderr if available
    datasets_tested = "Unknown"
    best_metric = "Unknown"
    
    prompt = PROMPT_EVALUATE.format(
        datasets_tested=datasets_tested,
        best_metric=best_metric,
        returncode=state.returncode or "N/A",
        stdout=(state.stdout or "")[:500],  # Limit to first 500 chars
        stderr=(state.stderr or "")[:500]   # Limit to first 500 chars
    )

    logger.info("Calling LLM to evaluate completion")
    response: EvaluateSchema = await llms.ainvoke(prompt)  # type: ignore

    state.is_complete = response.is_complete
    state.iteration_count += 1

    # If successful (returncode 0 and has hyperparam name), add to tried list
    if state.returncode == 0 and state.current_hyperparam_name:
        if state.current_hyperparam_name not in state.tried_hyperparams:
            state.tried_hyperparams.append(state.current_hyperparam_name)

    logger.info(f"Evaluation complete. is_complete={response.is_complete}, iteration={state.iteration_count}")
    return state


def should_continue(state: State, context: Context) -> Literal["node_propose_hyperparam", "__end__"]:
    """Determine if we should continue iterating or end."""
    if state.is_complete:
        logger.info("Stage complete - ending")
        return END
    if state.iteration_count >= context.max_iterations:
        logger.info(f"Max iterations ({context.max_iterations}) reached - ending")
        return END
    logger.info("Continuing to next iteration")
    return "node_propose_hyperparam"


def build() -> CompiledStateGraph[State, Context, State, State]:
    """Build the Stage 2 hyperparameter tuning graph."""
    builder = StateGraph(state_schema=State, context_schema=Context)

    # Add nodes
    builder.add_node("node_propose_hyperparam", node_propose_hyperparam)
    builder.add_node("node_implement_tuning", node_implement_tuning)
    builder.add_node("node_run", node_run)
    builder.add_node("node_evaluate", node_evaluate)

    # Add edges
    builder.add_edge(START, "node_propose_hyperparam")
    builder.add_edge("node_propose_hyperparam", "node_implement_tuning")
    builder.add_edge("node_implement_tuning", "node_run")
    builder.add_edge("node_run", "node_evaluate")
    
    # Add conditional edge from evaluate back to propose or to end
    builder.add_conditional_edges("node_evaluate", should_continue)

    return builder.compile()  # type: ignore

