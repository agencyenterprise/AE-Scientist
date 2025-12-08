import argparse
import json
import logging
import os
import shutil
import subprocess
import sys
import traceback
from pathlib import Path
from typing import Optional

from langchain_core.messages import BaseMessage
from pydantic import BaseModel, Field

from ai_scientist.latest_run_finder import find_latest_run_dir_name
from ai_scientist.llm import get_structured_response_from_llm
from ai_scientist.perform_icbinb_writeup import (
    filter_experiment_summaries,
    load_exp_summaries,
    load_idea_text,
)

logger = logging.getLogger(__name__)

MAX_FIGURES = 12

AGGREGATOR_SYSTEM_MSG = f"""You are an ambitious AI researcher who is preparing final plots for a scientific paper submission.
You have multiple experiment summaries (baseline, research, ablation), each possibly containing references to different plots or numerical insights.
There is also a top-level 'research_idea.md' file that outlines the overarching research direction.
Your job is to produce ONE Python script that fully aggregates and visualizes the final results for a comprehensive research paper.

Key points:
1) Combine or replicate relevant existing plotting code, referencing how data was originally generated (from code references) to ensure correctness.
2) Create a complete set of final scientific plots, stored in 'figures/' only (since only those are used in the final paper).
3) Make sure to use existing .npy data for analysis; do NOT hallucinate data. If single numeric results are needed, these may be copied from the JSON summaries.
4) Only create plots where the data is best presented as a figure and not as a table. E.g. don't use bar plots if the data is hard to visually compare.
5) If there are plots based on synthetic data, include them in the appendix.

Implement best practices:
- Do not produce extraneous or irrelevant plots.
- Maintain clarity, minimal but sufficient code.
- Demonstrate thoroughness for a final research paper submission.
- Do NOT reference non-existent files or images.
- Use the .npy files to get data for the plots and key numbers from the JSON summaries.
- Demarcate each individual plot, and put them in separate try-catch blocks so that the failure of one plot does not affect the others.
- Make sure to only create plots that are unique and needed for the final paper and appendix. A good number could be around {MAX_FIGURES} plots in total.
- Aim to aggregate multiple figures into one plot if suitable, i.e. if they are all related to the same topic. You can place up to 3 plots in one row.
- Provide well-labeled plots (axes, legends, titles) that highlight main findings. Use informative names everywhere, including in the legend for referencing them in the final paper. Make sure the legend is always visible.
- Make the plots look professional (if applicable, no top and right spines, dpi of 300, adequate ylim, etc.).
- Do not use labels with underscores, e.g. "loss_vs_epoch" should be "loss vs epoch".
- For image examples, select a few categories/classes to showcase the diversity of results instead of showing a single category/class. Some can be included in the main paper, while the rest can go in the appendix.

Return your response using the structured schema, filling the `script` field with the final Python aggregator code.
"""


def build_aggregator_prompt(combined_summaries_str: str, idea_text: str) -> str:
    return f"""
We have three JSON summaries of scientific experiments: baseline, research, ablation.
They may contain lists of figure descriptions, code to generate the figures, and paths to the .npy files containing the numerical results.
Our goal is to produce final, publishable figures.

--- RESEARCH IDEA ---
```
{idea_text}
```

IMPORTANT:
- The aggregator script must load existing .npy experiment data from the "exp_results_npy_files" fields (ONLY using full and exact file paths in the summary JSONs) for thorough plotting.
- It should call os.makedirs("figures", exist_ok=True) before saving any plots.
- Aim for a balance of empirical results, ablations, and diverse, informative visuals in 'figures/' that comprehensively showcase the finalized research outcomes.
- If you need .npy paths from the summary, only copy those paths directly (rather than copying and parsing the entire summary).

Your generated Python script must:
1) Load or refer to relevant data and .npy files from these summaries. Use the full and exact file paths in the summary JSONs.
2) Synthesize or directly create final, scientifically meaningful plots for a final research paper (comprehensive and complete), referencing the original code if needed to see how the data was generated.
3) Carefully combine or replicate relevant existing plotting code to produce these final aggregated plots in 'figures/' only, since only those are used in the final paper.
4) Do not hallucinate data. Data must either be loaded from .npy files or copied from the JSON summaries.
5) The aggregator script must be fully self-contained, and place the final plots in 'figures/'.
6) This aggregator script should produce a comprehensive and final set of scientific plots for the final paper, reflecting all major findings from the experiment data.
7) Make sure that every plot is unique and not duplicated from the original plots. Delete any duplicate plots if necessary.
8) Each figure can have up to 3 subplots using fig, ax = plt.subplots(1, 3).
9) Use a font size larger than the default for plot labels and titles to ensure they are readable in the final PDF paper.


Below are the summaries in JSON:

{combined_summaries_str}

Provide your answer using the structured response schema (field: script). Do not include commentary outside the schema.
"""


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

    idea_text = load_idea_text(base_folder)
    exp_summaries = load_exp_summaries(base_folder, run_dir_name=run_dir_name)
    filtered_summaries_for_plot_agg = filter_experiment_summaries(
        exp_summaries, step_name="plot_aggregation"
    )
    # Make exp_results_npy_files and plot_paths absolute under the chosen run dir
    try:
        chosen_run = run_dir_name
        if not chosen_run:
            chosen_run = find_latest_run_dir_name(logs_dir=Path(base_folder) / "logs")
        run_dir = Path(base_folder) / "logs" / str(chosen_run)

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
