import asyncio
import logging
import time
from pathlib import Path
from tempfile import NamedTemporaryFile

from langchain.chat_models import init_chat_model
from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph
from langgraph.runtime import Runtime
from pydantic import BaseModel

logger = logging.getLogger(__name__)


PROMPT_GENERATE_PLOTTING = """
You are an AI researcher tasked with generating plotting code for experimental
results.

## Task

Generate Python code that:

1. Loads experiment data from 'experiment_data.npy' (a numpy file)
2. Creates clear, publication-quality visualizations using matplotlib/seaborn
3. Saves all generated plots to disk with descriptive filenames
4. Uses proper labels, legends, titles, and formatting

## Guidelines

- Create multiple plots to show different aspects of the results
- Include training curves, comparison plots, and any relevant visualizations
- Save plots as PNG files with descriptive names (e.g., 'training_loss.png',
  'accuracy_comparison.png')
- Use clear colors and styling
- Add grid lines where appropriate
- Ensure all text is readable

## Previous plotting code (if available)

{plot_code_from_prev}

## Data path

The experiment data is located at: {experiment_data_path}
"""


PROMPT_EVALUATE_PLOTS = """
Evaluate whether the plotting stage has completed successfully.

## Evidence

- Plots generated: {plots_generated}
- Execution time: {execution_time} seconds
- Return code: {returncode}
- Stdout: {stdout}
- Stderr: {stderr}

## Completion Criteria

1. At least one plot was successfully generated
2. No errors during execution (return code 0)
3. Execution time is reasonable (not too fast or too slow)
4. Generated plots cover key aspects of the experiment

Provide evaluation based on these criteria.
"""


# Pydantic schemas for structured outputs
class GeneratePlotCodeSchema(BaseModel):
    code: str
    dependencies: list[str]


class EvaluatePlotsSchema(BaseModel):
    is_complete: bool
    feedback: str


class State(BaseModel):
    # inputs
    experiment_data_path: str
    plot_code_from_prev: str | None = None

    # working
    plot_code: str | None = None
    plots_generated: list[str] = []

    # outputs
    vlm_feedback: str | None = None
    execution_time: float | None = None
    returncode: int | None = None
    stdout: str | None = None
    stderr: str | None = None

    # control
    is_complete: bool = False


class Context(BaseModel):
    model: str = "gpt-4o-mini"
    temperature: float = 0.0


async def node_generate_plotting(state: State, runtime: Runtime[Context]) -> State:
    """Generate plotting code for experiment results."""
    logger.info("Starting node_generate_plotting")

    llm = init_chat_model(model=runtime.context.model, temperature=runtime.context.temperature)
    llms = llm.with_structured_output(GeneratePlotCodeSchema)

    prompt = PROMPT_GENERATE_PLOTTING.format(
        plot_code_from_prev=state.plot_code_from_prev or "No previous plotting code available.",
        experiment_data_path=state.experiment_data_path
    )

    logger.info("Calling LLM to generate plotting code")
    response: GeneratePlotCodeSchema = await llms.ainvoke(prompt)  # type: ignore

    state.plot_code = response.code

    logger.info(f"Generated {len(response.code)} characters of plotting code")
    return state


async def node_run_plotting(state: State, runtime: Runtime[Context]) -> State:
    """Execute the plotting code and capture generated plots."""
    logger.info("Starting node_run_plotting")

    code = state.plot_code or ""
    assert code, 'plot_code is required'

    start_time = time.time()

    # Get the directory where the experiment data is located
    exp_dir = Path(state.experiment_data_path).parent if state.experiment_data_path else Path.cwd()

    with NamedTemporaryFile(mode="wt", suffix=".py", delete=False) as tmp:
        # deps section
        tmp.write('# /// script\n')
        tmp.write('# dependencies = [\n')
        tmp.write('#   "matplotlib",\n')
        tmp.write('#   "numpy",\n')
        tmp.write('#   "seaborn",\n')
        tmp.write('# ]\n')
        tmp.write('# ///\n')
        tmp.write('\n')

        # actual code
        tmp.write(code)
        tmp.flush()

        logger.info("Running plotting code")
        proc = await asyncio.create_subprocess_exec(
            'uv', 'run', 'python', tmp.name,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=str(exp_dir)
        )

        await proc.wait()

    stdout = await proc.stdout.read() if proc.stdout else b''
    stderr = await proc.stderr.read() if proc.stderr else b''

    state.stdout = stdout.decode()
    state.stderr = stderr.decode()
    state.returncode = proc.returncode
    state.execution_time = time.time() - start_time

    # Try to find generated plot files (simple heuristic: look for .png files)
    if exp_dir.exists():
        plot_files = list(exp_dir.glob("*.png"))
        state.plots_generated = [str(p) for p in plot_files]

    logger.info(f"node_run_plotting completed. Generated {len(state.plots_generated)} plots in {state.execution_time:.2f}s")
    return state


async def node_evaluate_plots(state: State, runtime: Runtime[Context]) -> State:
    """Evaluate if the plotting stage completed successfully."""
    logger.info("Starting node_evaluate_plots")

    llm = init_chat_model(model=runtime.context.model, temperature=runtime.context.temperature)
    llms = llm.with_structured_output(EvaluatePlotsSchema)

    plots_list = ", ".join(state.plots_generated) if state.plots_generated else "None"
    
    prompt = PROMPT_EVALUATE_PLOTS.format(
        plots_generated=plots_list,
        execution_time=state.execution_time or 0.0,
        returncode=state.returncode or "N/A",
        stdout=(state.stdout or "")[:500],
        stderr=(state.stderr or "")[:500]
    )

    logger.info("Calling LLM to evaluate plots")
    response: EvaluatePlotsSchema = await llms.ainvoke(prompt)  # type: ignore

    state.is_complete = response.is_complete
    state.vlm_feedback = response.feedback

    logger.info(f"Plot evaluation complete. is_complete={response.is_complete}")
    return state


def build() -> CompiledStateGraph[State, Context, State, State]:
    """Build the Stage 3 plotting graph."""
    builder = StateGraph(state_schema=State, context_schema=Context)

    # Add nodes
    builder.add_node("node_generate_plotting", node_generate_plotting)
    builder.add_node("node_run_plotting", node_run_plotting)
    builder.add_node("node_evaluate_plots", node_evaluate_plots)

    # Add edges (linear flow)
    builder.add_edge(START, "node_generate_plotting")
    builder.add_edge("node_generate_plotting", "node_run_plotting")
    builder.add_edge("node_run_plotting", "node_evaluate_plots")
    builder.add_edge("node_evaluate_plots", END)

    return builder.compile()  # type: ignore

