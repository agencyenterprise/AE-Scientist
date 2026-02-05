import argparse
import json
import logging
import os
import shutil
import subprocess
import sys
import traceback
from pathlib import Path
from typing import Callable, NamedTuple, Optional

from langchain_core.messages import BaseMessage
from pydantic import BaseModel, Field

from ai_scientist.latest_run_finder import find_latest_run_dir_name
from ai_scientist.llm import get_structured_response_from_llm
from ai_scientist.prompts.render import render_text
from ai_scientist.treesearch.events import (
    BaseEvent,
    PaperGenerationProgressEvent,
    PaperGenerationStep,
)
from ai_scientist.writeup_artifacts import (
    filter_experiment_summaries,
    load_exp_summaries,
    load_idea_text,
)

logger = logging.getLogger(__name__)

MAX_FIGURES = 12


class _AggregatorSystemMsgContext(NamedTuple):
    max_figures: int


AGGREGATOR_SYSTEM_MSG = render_text(
    template_name="plotting/aggregator_system_msg.txt.j2",
    context=_AggregatorSystemMsgContext(max_figures=MAX_FIGURES)._asdict(),
)


class _AggregatorPromptContext(NamedTuple):
    idea_text: str
    combined_summaries_str: str


def build_aggregator_prompt(combined_summaries_str: str, idea_text: str) -> str:
    ctx = _AggregatorPromptContext(
        idea_text=idea_text, combined_summaries_str=combined_summaries_str
    )
    return render_text(
        template_name="plotting/aggregator_prompt.txt.j2",
        context=ctx._asdict(),
    )


class AggregatorScriptResponse(BaseModel):
    script: str = Field(..., description="Complete Python script for plot aggregation.")
    should_stop: bool = Field(
        default=False,
        description="Set to true when no further updates to the script are needed.",
    )


def run_aggregator_script(
    aggregator_code: str, aggregator_script_path: str, base_folder: str, script_name: str
) -> str:
    if not aggregator_code.strip():
        logger.info("No aggregator code was provided. Skipping aggregator script run.")
        return ""
    with open(aggregator_script_path, "w") as f:
        f.write(aggregator_code)

    logger.info(f"Aggregator script written to '{aggregator_script_path}'. Attempting to run it...")

    aggregator_out = ""
    try:
        result = subprocess.run(
            [sys.executable, script_name],
            cwd=base_folder,
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        aggregator_out = result.stdout + "\n" + result.stderr
        logger.info("Aggregator script ran successfully.")
    except subprocess.CalledProcessError as e:
        aggregator_out = (e.stdout or "") + "\n" + (e.stderr or "")
        logger.warning(f"Error: aggregator script returned a non-zero exit code: {e}")
    except Exception as e:
        aggregator_out = str(e)
        logger.exception(f"Error while running aggregator script: {e}")

    return aggregator_out


def aggregate_plots(
    base_folder: str,
    model: str,
    temperature: float,
    n_reflections: int = 5,
    run_dir_name: Optional[str] = None,
    event_callback: Optional[Callable[[BaseEvent], None]] = None,
    run_id: Optional[str] = None,
) -> None:
    filename = "auto_plot_aggregator.py"
    aggregator_script_path = os.path.join(base_folder, filename)
    figures_dir = os.path.join(base_folder, "figures")

    # Clean up previous files
    if os.path.exists(aggregator_script_path):
        os.remove(aggregator_script_path)
    if os.path.exists(figures_dir):
        shutil.rmtree(figures_dir)
        logger.debug("Cleaned up previous figures directory")

    base_path = Path(base_folder)
    logs_dir = base_path / "logs"
    active_run_name = run_dir_name
    if not active_run_name:
        try:
            active_run_name = find_latest_run_dir_name(logs_dir=logs_dir)
        except Exception:
            traceback.print_exc()
            active_run_name = "0-run"
    idea_text = load_idea_text(
        base_path=base_path,
        logs_dir=logs_dir,
        run_dir_name=run_dir_name,
    )
    exp_summaries = load_exp_summaries(
        base_path=base_path,
        run_dir_name=active_run_name,
    )
    filtered_summaries_for_plot_agg = filter_experiment_summaries(
        exp_summaries, step_name="plot_aggregation"
    )
    # Make exp_results_npy_files and plot_paths absolute under the chosen run dir
    try:
        chosen_run = active_run_name
        run_dir = logs_dir / str(chosen_run)

        def absolutize_paths(obj: object) -> object:
            if isinstance(obj, dict):
                new_d: dict[str, object] = {}
                for k, v in obj.items():
                    if k in {"exp_results_npy_files", "plot_paths"} and isinstance(v, list):
                        abs_list: list[str] = []
                        for p in v:
                            if isinstance(p, str) and not os.path.isabs(p):
                                abs_list.append(str(run_dir / p))
                            else:
                                abs_list.append(p)
                        new_d[k] = abs_list
                    else:
                        new_d[k] = absolutize_paths(v)
                return new_d
            if isinstance(obj, list):
                return [absolutize_paths(x) for x in obj]
            return obj

        filtered_summaries_for_plot_agg = absolutize_paths(filtered_summaries_for_plot_agg)  # type: ignore[assignment]

        # Collect and validate required .npy files
        def collect_npy_files(obj: object, out: list[str]) -> None:
            if isinstance(obj, dict):
                for k, v in obj.items():
                    if k == "exp_results_npy_files" and isinstance(v, list):
                        for p in v:
                            if isinstance(p, str) and p.lower().endswith(".npy"):
                                out.append(p)
                    else:
                        collect_npy_files(v, out)
            elif isinstance(obj, list):
                for x in obj:
                    collect_npy_files(x, out)

        npy_files: list[str] = []
        collect_npy_files(filtered_summaries_for_plot_agg, npy_files)
        if len(npy_files) == 0:
            raise ValueError(
                f"No exp_results_npy_files found in summaries for run '{chosen_run}'. "
                f"Cannot generate data-driven figures."
            )
        missing = [p for p in npy_files if not os.path.exists(p)]
        if missing:
            # Show at most a few missing paths to keep error readable
            preview = "\n".join(missing[:10])
            more = f"\n... and {len(missing) - 10} more" if len(missing) > 10 else ""
            raise FileNotFoundError(
                f"Missing experiment .npy files for run '{chosen_run}'. "
                f"Ensure summaries reference existing files under {run_dir}.\nMissing files:\n{preview}{more}"
            )
    except Exception:
        traceback.print_exc()
    # Convert them to one big JSON string for context
    combined_summaries_str = json.dumps(filtered_summaries_for_plot_agg, indent=2)

    # Build aggregator prompt
    aggregator_prompt = build_aggregator_prompt(combined_summaries_str, idea_text)

    msg_history: list[BaseMessage] = []
    try:
        response_dict, msg_history = get_structured_response_from_llm(
            prompt=aggregator_prompt,
            model=model,
            system_message=AGGREGATOR_SYSTEM_MSG,
            temperature=temperature,
            msg_history=msg_history,
            schema_class=AggregatorScriptResponse,
        )
    except Exception:
        traceback.print_exc()
        logger.exception("Failed to get aggregator script from LLM.")
        return

    try:
        aggregator_response = AggregatorScriptResponse.model_validate(response_dict)
    except Exception:
        logger.error("Structured aggregator response validation failed: %s", response_dict)
        return

    aggregator_code = aggregator_response.script.strip()
    if not aggregator_code.strip():
        logger.warning("No Python code block was found in LLM response. Full response:")
        logger.debug(response_dict)
        return

    # Emit event: plot_aggregation starting
    if event_callback and run_id:
        event_callback(
            PaperGenerationProgressEvent(
                run_id=run_id,
                step=PaperGenerationStep.plot_aggregation,
                substep="Starting plot aggregation...",
                progress=0.0,
                step_progress=0.0,
            )
        )

    # First run of aggregator script
    aggregator_out = run_aggregator_script(
        aggregator_code, aggregator_script_path, base_folder, filename
    )

    # Multiple reflection loops
    for i in range(n_reflections):
        # Check number of figures
        figure_count = 0
        if os.path.exists(figures_dir):
            figure_count = len(
                [f for f in os.listdir(figures_dir) if os.path.isfile(os.path.join(figures_dir, f))]
            )
        logger.info(f"[{i + 1} / {n_reflections}]: Number of figures: {figure_count}")

        # Emit event: plot aggregation reflection progress
        if event_callback and run_id:
            step_progress = (i + 1) / n_reflections
            event_callback(
                PaperGenerationProgressEvent(
                    run_id=run_id,
                    step=PaperGenerationStep.plot_aggregation,
                    substep=f"Reflection {i + 1} of {n_reflections} (figures: {figure_count})",
                    progress=0.15 * step_progress,  # plot_aggregation is 0-15% of overall
                    step_progress=step_progress,
                    details={"figure_count": figure_count} if figure_count > 0 else None,
                )
            )
        # Reflection prompt with reminder for common checks and early exit
        reflection_prompt = f"""We have run your aggregator script and it produced {figure_count} figure(s). The script's output is:
```
{aggregator_out}
```

Please criticize the current script for any flaws including but not limited to:
- Are these enough plots for a final paper submission? Don't create more than {MAX_FIGURES} plots.
- Have you made sure to both use key numbers and generate more detailed plots from .npy files?
- Does the figure title and legend have informative and descriptive names? These plots are the final versions, ensure there are no comments or other notes.
- Can you aggregate multiple plots into one figure if suitable?
- Do the labels have underscores? If so, replace them with spaces.
- Make sure that every plot is unique and not duplicated from the original plots.

Respond using the structured schema: set `should_stop` to true if no further changes are required; otherwise update the `script` field with the revised Python code."""

        logger.debug(f"Reflection prompt: {reflection_prompt}")
        try:
            reflection_dict, msg_history = get_structured_response_from_llm(
                prompt=reflection_prompt,
                model=model,
                system_message=AGGREGATOR_SYSTEM_MSG,
                temperature=temperature,
                msg_history=msg_history,
                schema_class=AggregatorScriptResponse,
            )

        except Exception:
            traceback.print_exc()
            logger.exception("Failed to get reflection from LLM.")
            return

        try:
            reflection_data = AggregatorScriptResponse.model_validate(reflection_dict)
        except Exception:
            logger.error("Structured reflection response validation failed: %s", reflection_dict)
            break

        # Early-exit check
        if figure_count > 0 and reflection_data.should_stop:
            logger.info("LLM indicated it is done with reflections. Exiting reflection loop.")
            break

        aggregator_new_code = reflection_data.script.strip()

        # If new code is provided and differs, run again
        if aggregator_new_code.strip() and aggregator_new_code.strip() != aggregator_code.strip():
            aggregator_code = aggregator_new_code
            aggregator_out = run_aggregator_script(
                aggregator_code, aggregator_script_path, base_folder, filename
            )
        else:
            logger.debug(
                f"No new aggregator script was provided or it was identical. Reflection step {i + 1} complete."
            )

    # Move generated figures into a per-run subfolder to avoid mixing runs
    try:
        chosen_run_final = run_dir_name or find_latest_run_dir_name(
            logs_dir=Path(base_folder) / "logs"
        )
        dest_dir = os.path.join(figures_dir, str(chosen_run_final))
        os.makedirs(dest_dir, exist_ok=True)
        if os.path.exists(figures_dir):
            for fname in os.listdir(figures_dir):
                src = os.path.join(figures_dir, fname)
                if os.path.isfile(src):
                    shutil.move(src, os.path.join(dest_dir, fname))
    except Exception:
        traceback.print_exc()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate and execute a final plot aggregation script with LLM assistance."
    )
    parser.add_argument(
        "--folder",
        required=True,
        help="Path to the experiment folder with summary JSON files.",
    )
    parser.add_argument(
        "--model",
        default="gpt-5",
        help="LLM model to use (default: gpt-5).",
    )
    parser.add_argument(
        "--reflections",
        type=int,
        default=5,
        help="Number of reflection steps to attempt (default: 5).",
    )
    parser.add_argument(
        "--temperature",
        type=float,
        required=True,
        help="Sampling temperature for the plot aggregation LLM.",
    )
    args = parser.parse_args()
    aggregate_plots(
        base_folder=args.folder,
        model=args.model,
        temperature=args.temperature,
        n_reflections=args.reflections,
    )


if __name__ == "__main__":
    main()
