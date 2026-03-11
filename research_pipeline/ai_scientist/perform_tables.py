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

MAX_TABLES = 6


class _TableSystemMsgContext(NamedTuple):
    max_tables: int


TABLE_AGGREGATOR_SYSTEM_MSG = render_text(
    template_name="tables/table_aggregator_system_msg.txt.j2",
    context=_TableSystemMsgContext(max_tables=MAX_TABLES)._asdict(),
)


class _TablePromptContext(NamedTuple):
    idea_text: str
    combined_summaries_str: str


def build_table_aggregator_prompt(combined_summaries_str: str, idea_text: str) -> str:
    ctx = _TablePromptContext(
        idea_text=idea_text, combined_summaries_str=combined_summaries_str
    )
    return render_text(
        template_name="tables/table_aggregator_prompt.txt.j2",
        context=ctx._asdict(),
    )


class TableAggregatorScriptResponse(BaseModel):
    script: str = Field(..., description="Complete Python script for table generation.")
    should_stop: bool = Field(
        default=False,
        description="Set to true when no further updates to the script are needed.",
    )


def run_table_script(
    table_code: str, table_script_path: str, base_folder: str, script_name: str
) -> str:
    if not table_code.strip():
        logger.info("No table generation code was provided. Skipping.")
        return ""
    with open(table_script_path, "w", encoding="utf-8") as f:
        f.write(table_code)

    logger.info("Table script written to '%s'. Running...", table_script_path)

    table_out = ""
    try:
        result = subprocess.run(
            [sys.executable, script_name],
            cwd=base_folder,
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        table_out = result.stdout + "\n" + result.stderr
        logger.info("Table generation script ran successfully.")
    except subprocess.CalledProcessError as e:
        table_out = (e.stdout or "") + "\n" + (e.stderr or "")
        logger.warning("Error: table script returned a non-zero exit code: %s", e)
    except Exception as e:  # noqa: BLE001
        table_out = str(e)
        logger.exception("Error while running table script: %s", e)

    return table_out


def aggregate_tables(
    base_folder: str,
    model: str,
    temperature: float,
    n_reflections: int = 3,
    run_dir_name: Optional[str] = None,
    event_callback: Optional[Callable[[BaseEvent], None]] = None,
    run_id: Optional[str] = None,
) -> None:
    """Generate results tables from experiment data, parallel to aggregate_plots."""
    filename = "auto_table_aggregator.py"
    table_script_path = os.path.join(base_folder, filename)
    tables_dir = os.path.join(base_folder, "tables")

    if os.path.exists(table_script_path):
        os.remove(table_script_path)
    if os.path.exists(tables_dir):
        shutil.rmtree(tables_dir)
        logger.debug("Cleaned up previous tables directory")

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
    # Reuse the plot_aggregation filter since it includes npy paths + analyses
    filtered_summaries = filter_experiment_summaries(
        exp_summaries, step_name="plot_aggregation"
    )

    # Make npy paths absolute
    try:
        run_dir = logs_dir / str(active_run_name)

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

        filtered_summaries = absolutize_paths(filtered_summaries)  # type: ignore[assignment]

        # Validate npy files exist
        npy_files: list[str] = []

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

        collect_npy_files(filtered_summaries, npy_files)
        if len(npy_files) == 0:
            raise ValueError(
                f"No exp_results_npy_files found in summaries for run '{active_run_name}'. "
                f"Cannot generate data-driven tables."
            )
        missing = [p for p in npy_files if not os.path.exists(p)]
        if missing:
            preview = "\n".join(missing[:10])
            more = f"\n... and {len(missing) - 10} more" if len(missing) > 10 else ""
            raise FileNotFoundError(
                f"Missing experiment .npy files for run '{active_run_name}'. "
                f"Missing files:\n{preview}{more}"
            )
    except Exception:
        traceback.print_exc()

    combined_summaries_str = json.dumps(filtered_summaries, indent=2)
    table_prompt = build_table_aggregator_prompt(combined_summaries_str, idea_text)

    msg_history: list[BaseMessage] = []
    try:
        response_dict, msg_history = get_structured_response_from_llm(
            prompt=table_prompt,
            model=model,
            system_message=TABLE_AGGREGATOR_SYSTEM_MSG,
            temperature=temperature,
            msg_history=msg_history,
            schema_class=TableAggregatorScriptResponse,
        )
    except Exception:
        traceback.print_exc()
        logger.exception("Failed to get table generation script from LLM.")
        return

    try:
        table_response = TableAggregatorScriptResponse.model_validate(response_dict)
    except Exception:
        logger.error("Structured table response validation failed: %s", response_dict)
        return

    table_code = table_response.script.strip()
    if not table_code:
        logger.warning("No Python code was found in LLM response for table generation.")
        return

    if event_callback and run_id:
        event_callback(
            PaperGenerationProgressEvent(
                run_id=run_id,
                step=PaperGenerationStep.plot_aggregation,
                substep="Starting table generation...",
                progress=0.0,
                step_progress=0.0,
            )
        )

    table_out = run_table_script(table_code, table_script_path, base_folder, filename)

    # Reflection loop
    for i in range(n_reflections):
        table_count = 0
        if os.path.exists(tables_dir):
            table_count = len(
                [f for f in os.listdir(tables_dir) if f.endswith(".tex")]
            )
        logger.info("[%d / %d]: Number of tables: %d", i + 1, n_reflections, table_count)

        manifest_path = os.path.join(tables_dir, "manifest.json")
        manifest_info = ""
        if os.path.exists(manifest_path):
            try:
                manifest_info = Path(manifest_path).read_text(encoding="utf-8")
            except Exception:
                pass

        reflection_prompt = f"""We have run your table generation script and it produced {table_count} table(s). The script's output is:
```
{table_out}
```

Current manifest.json:
```json
{manifest_info}
```

Please criticize the current script for any flaws including but not limited to:
- Are there enough tables for a final paper? Typical papers have 2-4 result tables. Max {MAX_TABLES}.
- Do the tables include the most important quantitative comparisons?
- Are numbers formatted with appropriate precision?
- Are best results highlighted with \\textbf{{}}?
- Is there a table showing ablation results (if ablation data exists)?
- If prediction data exists, is there a qualitative examples table?
- Are column headers and row labels clear and descriptive?

Respond using the structured schema: set `should_stop` to true if no further changes are required; otherwise update the `script` field with the revised Python code."""

        try:
            reflection_dict, msg_history = get_structured_response_from_llm(
                prompt=reflection_prompt,
                model=model,
                system_message=TABLE_AGGREGATOR_SYSTEM_MSG,
                temperature=temperature,
                msg_history=msg_history,
                schema_class=TableAggregatorScriptResponse,
            )
        except Exception:
            traceback.print_exc()
            logger.exception("Failed to get table reflection from LLM.")
            return

        try:
            reflection_data = TableAggregatorScriptResponse.model_validate(reflection_dict)
        except Exception:
            logger.error("Structured table reflection validation failed: %s", reflection_dict)
            break

        if table_count > 0 and reflection_data.should_stop:
            logger.info("LLM indicated table generation is complete. Exiting reflection loop.")
            break

        new_code = reflection_data.script.strip()
        if new_code and new_code != table_code:
            table_code = new_code
            table_out = run_table_script(table_code, table_script_path, base_folder, filename)
        else:
            logger.debug("No new table code provided. Reflection step %d complete.", i + 1)

    # Move tables into per-run subfolder
    try:
        chosen_run_final = run_dir_name or find_latest_run_dir_name(
            logs_dir=Path(base_folder) / "logs"
        )
        dest_dir = os.path.join(tables_dir, str(chosen_run_final))
        os.makedirs(dest_dir, exist_ok=True)
        if os.path.exists(tables_dir):
            for fname in os.listdir(tables_dir):
                src = os.path.join(tables_dir, fname)
                if os.path.isfile(src):
                    shutil.move(src, os.path.join(dest_dir, fname))
    except Exception:
        traceback.print_exc()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate results tables from experiment data with LLM assistance."
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
        default=3,
        help="Number of reflection steps (default: 3).",
    )
    parser.add_argument(
        "--temperature",
        type=float,
        required=True,
        help="Sampling temperature.",
    )
    args = parser.parse_args()
    aggregate_tables(
        base_folder=args.folder,
        model=args.model,
        temperature=args.temperature,
        n_reflections=args.reflections,
    )


if __name__ == "__main__":
    main()
