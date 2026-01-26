import argparse
import json
import logging
import os
import os.path as osp
import re
import shutil
import subprocess
import time
import traceback
import uuid
from pathlib import Path
from typing import Any, Callable, Dict, List, NamedTuple, Optional, cast

from pydantic import BaseModel, Field

from ai_scientist.artifact_manager import ArtifactSpec
from ai_scientist.latest_run_finder import find_latest_run_dir_name
from ai_scientist.llm import get_structured_response_from_llm
from ai_scientist.perform_citations import gather_citations
from ai_scientist.perform_vlm_review import (
    detect_duplicate_figures,
    generate_vlm_img_review,
    perform_imgs_cap_ref_review,
    perform_imgs_cap_ref_review_selection,
)
from ai_scientist.prompts.render import render_text
from ai_scientist.treesearch.codex.codex_cli_runner import CodexCliRunner
from ai_scientist.treesearch.events import BaseEvent, PaperGenerationProgressEvent
from ai_scientist.writeup_artifacts import (
    SUMMARY_KEYS_TO_STRIP,
    filter_experiment_summaries,
    load_exp_summaries,
    load_idea_text,
    strip_summary_keys,
)

logger = logging.getLogger(__name__)


class _WriteupSystemMsgContext(NamedTuple):
    page_limit: int


class _WriteupPromptContext(NamedTuple):
    idea_text: str
    summaries: str
    aggregator_code: str
    plot_list: str
    plot_descriptions: str
    latex_writeup: str
    previous_run_context: str


class _WriteupReflectionPromptContext(NamedTuple):
    unused_figs: list[str]
    invalid_figs: list[str]
    reflection_page_info: str
    check_output: str
    review_img_cap_ref: str
    analysis_duplicate_figs: str


class _WriteupImgReflectionPromptContext(NamedTuple):
    used_figs: str
    unused_figs: list[str]
    reflection_page_info: str
    review_img_selection: str


def ensure_graphicspath(writeup_file: str, latex_folder: str, figures_dir: str) -> None:
    """
    Ensure LaTeX graphicspath includes the run-specific figures directory.
    """
    try:
        wf = Path(writeup_file)
        lf = Path(latex_folder)
        fd = Path(figures_dir)
        rel = os.path.relpath(str(fd), str(lf)).replace("\\", "/")
        # Build directive like: \graphicspath{{../figures/<run>/}{../figures/}}
        new_gp = "\\graphicspath{{" + rel + "/}{../figures/}}"
        # Replace entire line containing \graphicspath, else insert after \usepackage{graphicx}
        lines: list[str] = []
        with open(wf, "r") as f:
            lines = f.readlines()
        found = False
        for i, line in enumerate(lines):
            if "\\graphicspath" in line:
                lines[i] = new_gp + "\n"
                found = True
                break
        if not found:
            for i, line in enumerate(lines):
                if "\\usepackage{graphicx}" in line:
                    lines.insert(i + 1, new_gp + "\n")
                    found = True
                    break
        if not found:
            # Fallback: prepend at top
            lines.insert(0, new_gp + "\n")
        with open(wf, "w") as f:
            f.writelines(lines)
    except Exception:
        logger.warning("Warning: failed to adjust \\graphicspath; figures may not render.")
        logger.debug(traceback.format_exc())


def _ensure_all_figures_referenced(writeup_file: str, plot_names: list[str]) -> None:
    """
    Ensure that every available PNG figure is referenced in the LaTeX file.

    If some figures are not used in any \\includegraphics command, append simple
    figure environments near the end of the document so they appear in the PDF.
    """
    if not plot_names:
        return

    try:
        wf = Path(writeup_file)
        text = wf.read_text(encoding="utf-8")
    except Exception:
        logger.warning("Warning: failed to read LaTeX file when ensuring figures.")
        logger.debug(traceback.format_exc())
        return

    # Collect base names (without extension) of all currently used figures
    referenced_paths = re.findall(r"\\includegraphics(?:\[[^]]*])?{([^}]+)}", text)
    used_basenames: set[str] = set()
    for ref_path in referenced_paths:
        ref_stem = Path(ref_path).stem
        used_basenames.add(ref_stem)

    # Determine which available figures are never referenced
    missing_stems: list[str] = []
    for plot_name in plot_names:
        stem = Path(plot_name).stem
        if stem not in used_basenames:
            missing_stems.append(stem)

    if not missing_stems:
        return

    # Build simple figure blocks for missing figures
    figure_blocks: list[str] = []
    for stem in missing_stems:
        figure_blocks.append(
            "\\begin{figure}[t]\n"
            "\\centering\n"
            f"\\includegraphics[width=0.9\\linewidth]{{{stem}}}\n"
            f"\\caption{{Automatically inserted figure for {stem}.}}\n"
            f"\\label{{fig:{stem}}}\n"
            "\\end{figure}\n"
        )
    figures_tex = "\n".join(figure_blocks)

    # Insert before \end{document} if present; otherwise append at the end
    insert_pos = text.rfind("\\end{document}")
    if insert_pos == -1:
        new_text = text + "\n" + figures_tex + "\n"
    else:
        new_text = text[:insert_pos] + figures_tex + "\n" + text[insert_pos:]

    try:
        wf.write_text(new_text, encoding="utf-8")
    except Exception:
        logger.warning("Warning: failed to write LaTeX file after inserting figures.")
        logger.debug(traceback.format_exc())


def compile_latex(cwd: str, pdf_file: str) -> bool:
    LATEX_COMPILE_TIMEOUT = 180
    logger.info("=" * 80)
    logger.info("GENERATING LATEX")
    logger.debug(f"cwd (latex folder): {cwd}")
    logger.debug(f"target pdf_file: {pdf_file}")
    logger.debug(f"cwd exists: {osp.exists(cwd)}")
    logger.debug(f"cwd is absolute: {osp.isabs(cwd)}")
    logger.info("=" * 80)

    commands = [
        ["pdflatex", "-interaction=nonstopmode", "template.tex"],
        ["bibtex", "template"],
        ["pdflatex", "-interaction=nonstopmode", "template.tex"],
        ["pdflatex", "-interaction=nonstopmode", "template.tex"],
    ]

    for i, command in enumerate(commands):
        logger.debug(f"Running command {i + 1}/4: {' '.join(command)}")
        try:
            result = subprocess.run(
                command,
                cwd=cwd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                timeout=LATEX_COMPILE_TIMEOUT,
            )
            logger.debug(f"Command {i + 1} return code: {result.returncode}")
            if result.returncode != 0:
                logger.warning(f"Command failed with return code {result.returncode}")
            # Only show full output for errors or final compile
            if result.returncode != 0 or i == len(commands) - 1:
                logger.debug(
                    f"Standard Output:\n{result.stdout[-2000:] if len(result.stdout) > 2000 else result.stdout}"
                )
                logger.debug(
                    f"Standard Error:\n{result.stderr[-1000:] if len(result.stderr) > 1000 else result.stderr}"
                )
        except subprocess.TimeoutExpired:
            logger.exception(
                f"EXCEPTION in compile_latex: LaTeX timed out after {LATEX_COMPILE_TIMEOUT} seconds."
            )
        except subprocess.CalledProcessError:
            logger.exception(
                f"EXCEPTION in compile_latex: Error running command {' '.join(command)}"
            )

    logger.info("\n" + "=" * 80)
    logger.info("FINISHED GENERATING LATEX")

    source_pdf = osp.join(cwd, "template.pdf")
    logger.debug(f"Checking for generated PDF at: {source_pdf}")
    logger.debug(f"PDF exists: {osp.exists(source_pdf)}")

    if osp.exists(source_pdf):
        pdf_size = osp.getsize(source_pdf)
        logger.debug(f"PDF size: {pdf_size} bytes")

    logger.debug(f"Attempting to move to: {pdf_file}")
    logger.debug(f"Target directory exists: {osp.exists(osp.dirname(pdf_file))}")
    logger.info("=" * 80)

    try:
        if not osp.exists(source_pdf):
            logger.error(f"Source PDF not found: {source_pdf}")
            logger.error(f"Files in latex dir: {os.listdir(cwd)}")
            return False

        # Ensure target directory exists
        target_dir = osp.dirname(pdf_file)
        if not osp.exists(target_dir):
            logger.warning(f"Target directory doesn't exist, creating: {target_dir}")
            os.makedirs(target_dir, exist_ok=True)

        shutil.move(source_pdf, pdf_file)
        logger.info(f"PDF moved to: {pdf_file}")
        logger.info(f"Final PDF exists: {osp.exists(pdf_file)}")
        return True
    except FileNotFoundError as e:
        logger.exception(f"Failed to rename PDF: {e}")
        return False
    except Exception as e:
        logger.exception(f"Unexpected error moving PDF: {e}")
        return False


def detect_pages_before_impact(latex_folder: str, timeout: int = 30) -> tuple[int, int] | None:
    """
    Temporarily copy the latex folder, compile, and detect on which page
    the phrase "Impact Statement" appears.
    Returns a tuple (page_number, line_number) if found, otherwise None.
    """
    temp_dir = osp.join(latex_folder, f"_temp_compile_{uuid.uuid4().hex}")
    try:
        shutil.copytree(latex_folder, temp_dir, dirs_exist_ok=True)

        # Compile in the temp folder
        commands = [
            ["pdflatex", "-interaction=nonstopmode", "template.tex"],
            ["bibtex", "template"],
            ["pdflatex", "-interaction=nonstopmode", "template.tex"],
            ["pdflatex", "-interaction=nonstopmode", "template.tex"],
        ]
        for command in commands:
            try:
                subprocess.run(
                    command,
                    cwd=temp_dir,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    timeout=timeout,
                )
            except (subprocess.TimeoutExpired, subprocess.CalledProcessError):
                return None

        temp_pdf_file = osp.join(temp_dir, "template.pdf")
        if not osp.exists(temp_pdf_file):
            return None

        # Try page-by-page extraction to detect "Impact Statement"
        for i in range(1, 51):
            page_txt = osp.join(temp_dir, f"page_{i}.txt")
            subprocess.run(
                [
                    "pdftotext",
                    "-f",
                    str(i),
                    "-l",
                    str(i),
                    "-q",
                    temp_pdf_file,
                    page_txt,
                ],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
            if not osp.exists(page_txt):
                break
            with open(page_txt, "r", encoding="utf - 8", errors="ignore") as fp:
                page_content = fp.read()
            lines = page_content.split("\n")
            for idx, line in enumerate(lines):
                if "Impact Statement" in line:
                    return (i, idx + 1)
        return None
    except Exception:
        return None
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


# --------------------------------------------------------------------------- #
# Structured response schemas                                                 #
# --------------------------------------------------------------------------- #


class LatexWriteupResponse(BaseModel):
    latex_code: str = Field(
        ...,
        description="Complete LaTeX contents for template.tex, ready to write to disk.",
    )
    should_stop: bool = Field(
        False,
        description=(
            "Set to true when no further edits are required. "
            "When true, latex_code should match the current file."
        ),
    )


LATEX_WRITEUP_SCHEMA = LatexWriteupResponse

# --------------------------------------------------------------------------- #
# Helper utilities shared across the writeup pipeline                         #
# --------------------------------------------------------------------------- #


def update_references_block(writeup_path: Path, citations_text: str) -> None:
    """
    Replace the contents of the references filecontents block with the provided text.
    """
    if not citations_text.strip():
        return
    try:
        content = writeup_path.read_text(encoding="utf-8")
    except Exception:
        logger.warning("Warning: failed to read %s when updating references.", writeup_path)
        logger.debug(traceback.format_exc())
        return

    pattern = r"(\\begin{filecontents}{references\.bib})(.*?)(\\end{filecontents})"

    def _repl(match: re.Match[str]) -> str:
        return f"{match.group(1)}\n{citations_text.strip()}\n{match.group(3)}"

    updated_content, count = re.subn(
        pattern, _repl, content, count=1, flags=re.DOTALL | re.IGNORECASE
    )
    if count == 0:
        logger.warning("Warning: references block not found in %s", writeup_path)
        return
    writeup_path.write_text(updated_content, encoding="utf-8")


def extract_previous_run_context(
    *,
    idea_text: str,
    summaries_str: str,
    model: str,
    workspace_dir: Path,
    artifact_callback: Callable[[ArtifactSpec], None],
    event_callback: Optional[Callable[[BaseEvent], None]] = None,
    run_id: Optional[str] = None,
) -> str | None:
    """
    Use Codex to extract relevant context from previous run data.

    Returns markdown string containing analysis of the previous run, or None if:
    - HAS_PREVIOUS_RUN is not set to "true"
    - Previous run data directory doesn't exist
    - Codex execution fails
    """
    # Check if previous run exists
    has_previous = os.environ.get("HAS_PREVIOUS_RUN", "").strip().lower() == "true"
    if not has_previous:
        logger.info("HAS_PREVIOUS_RUN not set; skipping previous run context extraction.")
        return None

    previous_run_path_str = os.environ.get("PREVIOUS_RUN_DATA_PATH", "/workspace/previous_run_data")
    previous_run_path = Path(previous_run_path_str)
    if not previous_run_path.exists():
        logger.warning(
            "Previous run data directory not found at %s; skipping context extraction.",
            previous_run_path,
        )
        return None

    logger.info("Extracting context from previous research run at %s", previous_run_path)

    # Emit event: starting previous run context extraction
    if event_callback and run_id:
        event_callback(
            PaperGenerationProgressEvent(
                run_id=run_id,
                step="paper_writeup",
                substep="Extracting previous run context...",
                progress=0.25,
                step_progress=0.0,
            )
        )

    try:
        # Build Codex task prompt
        codex_prompt = render_text(
            template_name="writeup/extract_previous_run_context.md.j2",
            context={
                "current_idea_text": idea_text,
                "current_summaries": summaries_str,
                "previous_run_path": str(previous_run_path),
            },
        )

        # Write task file
        task_file = workspace_dir / "extract_previous_context_task.md"
        task_file.write_text(codex_prompt, encoding="utf-8")

        # Run Codex CLI (venv and environment setup handled automatically)
        research_pipeline_root = Path(__file__).resolve().parents[1]
        runner = CodexCliRunner(
            workspace_dir=workspace_dir,
            research_pipeline_root=research_pipeline_root,
            session_log_name="previous_context_extraction.log",
            events_log_name="previous_context_extraction_events.jsonl",
            timeout_seconds=1800,  # 30 minutes
            model=model,
            event_callback=event_callback if event_callback else lambda _: None,
        )

        logger.info("Running Codex to extract previous run context (timeout: 30min)...")
        _term_out, exec_time, exc_type, _exc_info = runner.run_autonomous(
            task_file=task_file,
        )

        logger.info(
            "Codex context extraction completed in %.1fs (exc_type=%s)", exec_time, exc_type
        )

        # Read the output file
        output_file = workspace_dir / "previous_run_context.md"
        if not output_file.exists():
            logger.warning(
                "Codex did not create expected output file at %s; skipping previous context.",
                output_file,
            )
            return None

        context_text = output_file.read_text(encoding="utf-8").strip()
        if not context_text:
            logger.warning("Previous run context file is empty; skipping.")
            return None

        if run_id is None:
            logger.warning(
                "run_id is not set; skipping upload + artifact webhook for %s",
                output_file,
            )
        else:
            try:
                artifact_callback(
                    ArtifactSpec(
                        artifact_type="previous_run_context",
                        path=output_file,
                        packaging="file",
                    )
                )
            except Exception:
                logger.exception(
                    "Failed to upload previous run context artifact + webhook (non-fatal)."
                )

        logger.info("Successfully extracted previous run context (%s chars)", len(context_text))
        return context_text

    except Exception:
        logger.exception("Failed to extract previous run context; proceeding without it.")
        return None


def perform_writeup(
    base_folder: str,
    model: str,
    temperature: float,
    artifact_callback: Callable[[ArtifactSpec], None],
    no_writing: bool = False,
    num_cite_rounds: int = 20,
    n_writeup_reflections: int = 3,
    page_limit: int = 8,
    citations_text: str | None = None,
    run_dir_name: str | None = None,
    event_callback: Optional[Callable[[BaseEvent], None]] = None,
    run_id: Optional[str] = None,
) -> bool:
    logger.info("\n" + "=" * 80)
    logger.info("STARTING PERFORM_WRITEUP")
    logger.debug(f"base_folder: {base_folder}")
    logger.debug(f"Current working directory: {os.getcwd()}")
    logger.debug(f"model: {model}")
    logger.debug(f"n_writeup_reflections: {n_writeup_reflections}")
    logger.debug(f"citations_text provided: {citations_text is not None}")
    logger.info("=" * 80 + "\n")

    # Emit event: paper writeup starting
    if event_callback and run_id:
        event_callback(
            PaperGenerationProgressEvent(
                run_id=run_id,
                step="paper_writeup",
                substep="Starting paper writeup...",
                progress=0.30,
                step_progress=0.0,
            )
        )

    compile_attempt = 0
    final_pdf_path: Path | None = None

    try:
        base_path = Path(base_folder)
        logs_dir = base_path / "logs"
        logs_dir.mkdir(parents=True, exist_ok=True)

        latest_run_dir = "0-run"
        if run_dir_name and (logs_dir / run_dir_name).exists():
            latest_run_dir = run_dir_name
        elif logs_dir.exists():
            try:
                latest_run_dir = find_latest_run_dir_name(logs_dir=logs_dir)
            except Exception:
                logger.debug("Falling back to default run directory.", exc_info=True)
                latest_run_dir = "0-run"

        run_out_dir = logs_dir / latest_run_dir
        run_out_dir.mkdir(parents=True, exist_ok=True)
        base_pdf_stem = run_out_dir / "paper"
        latex_folder = run_out_dir / "latex"
        figures_dir = base_path / "figures" / latest_run_dir
        logger.debug("latex_folder: %s", latex_folder)

        idea_text = load_idea_text(
            base_path=base_path, logs_dir=logs_dir, run_dir_name=latest_run_dir
        )
        summaries = load_exp_summaries(base_path=base_path, run_dir_name=latest_run_dir)
        filtered_summaries_for_writeup = filter_experiment_summaries(
            exp_summaries=summaries, step_name="writeup"
        )
        filtered_summaries_for_writeup = cast(
            Dict[str, Any],
            strip_summary_keys(filtered_summaries_for_writeup, SUMMARY_KEYS_TO_STRIP),
        )
        combined_summaries_str = json.dumps(filtered_summaries_for_writeup, indent=2)

        if latex_folder.exists():
            shutil.rmtree(latex_folder)
        shutil.copytree(
            src="ai_scientist/blank_icml_latex",
            dst=latex_folder,
            dirs_exist_ok=True,
        )

        writeup_file = latex_folder / "template.tex"
        writeup_text = writeup_file.read_text(encoding="utf-8")

        plot_names: List[str] = []
        if figures_dir.exists():
            plot_names = sorted(
                [
                    entry.name
                    for entry in figures_dir.iterdir()
                    if entry.is_file() and entry.suffix.lower() == ".png"
                ]
            )

        aggregator_path = base_path / "auto_plot_aggregator.py"
        aggregator_code = (
            aggregator_path.read_text(encoding="utf-8")
            if aggregator_path.exists()
            else "No aggregator script found."
        )

        if no_writing:
            pdf_target = f"{base_pdf_stem}.pdf"
            compile_latex(cwd=str(latex_folder), pdf_file=pdf_target)
            return Path(pdf_target).exists()

        if citations_text is None:
            citations_text = gather_citations(
                base_path=base_path,
                logs_dir=logs_dir,
                model=model,
                temperature=temperature,
                num_cite_rounds=num_cite_rounds,
                run_dir_name=latest_run_dir,
            )
        if citations_text:
            update_references_block(writeup_path=writeup_file, citations_text=citations_text)

        # Extract context from previous run if available
        previous_run_context: str | None = None
        if os.environ.get("HAS_PREVIOUS_RUN", "").strip().lower() == "true":
            logger.info("Previous run detected; extracting context for paper writing...")
            previous_run_context = extract_previous_run_context(
                idea_text=idea_text,
                summaries_str=combined_summaries_str,
                model=model,
                workspace_dir=Path("/workspace"),
                artifact_callback=artifact_callback,
                event_callback=event_callback,
                run_id=run_id,
            )
            if previous_run_context:
                logger.info("Previous run context successfully extracted for paper writing.")
            else:
                logger.info("Previous run context extraction did not produce usable output.")
        else:
            logger.info("No previous run detected")

        try:
            vlm_started_at = time.monotonic()
            desc_map: Dict[str, str] = {}
            logger.info("Generating VLM figure descriptions for %s plot(s)...", len(plot_names))
            for idx, plot_name in enumerate(plot_names, start=1):
                one_started_at = time.monotonic()
                logger.info(
                    "VLM figure description %s/%s: %s",
                    idx,
                    len(plot_names),
                    plot_name,
                )
                plot_path = figures_dir / plot_name
                if not plot_path.exists():
                    logger.warning("Plot file not found for VLM review: %s", plot_path)
                    continue
                img_dict = {
                    "images": [str(plot_path)],
                    "caption": "No direct caption",
                }
                review_data = generate_vlm_img_review(
                    img=img_dict,
                    model=model,
                    temperature=temperature,
                )
                desc_map[plot_name] = (
                    review_data.get("Img_description", "No description found")
                    if review_data
                    else "No description found"
                )
                logger.info(
                    "VLM figure description complete %s/%s: %s (%.1fs)",
                    idx,
                    len(plot_names),
                    plot_name,
                    time.monotonic() - one_started_at,
                )
            plot_descriptions_list = [
                f"{plot_name}: {desc_map.get(plot_name, 'No description found')}"
                for plot_name in plot_names
            ]
            plot_descriptions_str = "\n".join(plot_descriptions_list)
            logger.info(
                "VLM figure description generation complete (plots=%s, total_time=%.1fs).",
                len(plot_names),
                time.monotonic() - vlm_started_at,
            )
        except Exception:
            logger.exception("EXCEPTION in VLM figure description generation:")
            plot_descriptions_str = "No descriptions available."

        big_model_system_message = render_text(
            template_name="writeup/writeup_system_message.txt.j2",
            context=_WriteupSystemMsgContext(page_limit=page_limit)._asdict(),
        )
        combined_prompt = render_text(
            template_name="writeup/writeup_prompt.txt.j2",
            context=_WriteupPromptContext(
                idea_text=idea_text,
                summaries=combined_summaries_str,
                aggregator_code=aggregator_code,
                plot_list=", ".join(plot_names),
                plot_descriptions=plot_descriptions_str,
                latex_writeup=writeup_text,
                previous_run_context=previous_run_context or "",
            )._asdict(),
        )

        response_data, msg_history = get_structured_response_from_llm(
            prompt=combined_prompt,
            model=model,
            system_message=big_model_system_message,
            temperature=temperature,
            schema_class=LATEX_WRITEUP_SCHEMA,
        )

        updated_latex_code = response_data.get("latex_code", "").strip()
        if not updated_latex_code:
            logger.error("Structured LLM response missing latex_code.")
            return False
        writeup_file.write_text(updated_latex_code, encoding="utf-8")
        ensure_graphicspath(
            writeup_file=str(writeup_file),
            latex_folder=str(latex_folder),
            figures_dir=str(figures_dir),
        )
        _ensure_all_figures_referenced(
            writeup_file=str(writeup_file),
            plot_names=plot_names,
        )

        for reflection_idx in range(n_writeup_reflections):
            # Emit event: paper writeup reflection progress
            if event_callback and run_id:
                step_progress = (reflection_idx + 1) / n_writeup_reflections
                event_callback(
                    PaperGenerationProgressEvent(
                        run_id=run_id,
                        step="paper_writeup",
                        substep=f"Reflection {reflection_idx + 1} of {n_writeup_reflections}",
                        progress=0.30 + 0.50 * step_progress,  # paper_writeup is 30-80%
                        step_progress=step_progress,
                    )
                )

            current_latex = writeup_file.read_text(encoding="utf-8")
            referenced_figs_temp = re.findall(
                r"\\includegraphics(?:\[[^\]]*\])?{([^}]+)}", current_latex
            )
            used_figs = {Path(ref).name for ref in referenced_figs_temp}
            all_figs = set(plot_names)
            unused_figs = sorted(all_figs - used_figs)
            invalid_figs = sorted(used_figs - all_figs)

            reflection_pdf = f"{base_pdf_stem}_{compile_attempt}.pdf"
            compile_latex(cwd=str(latex_folder), pdf_file=reflection_pdf)
            final_pdf_path = Path(reflection_pdf)
            compile_attempt += 1

            impact_loc = detect_pages_before_impact(str(latex_folder))
            if impact_loc is not None:
                page_num, line_num = impact_loc
                reflection_page_info = (
                    f"\n'Impact Statement' currently starts on page {page_num}, approximately line {line_num}. "
                    f"The target length is about {page_limit} pages; keep the narrative concise but informative.\n"
                )
            else:
                reflection_page_info = "\nCould not detect the 'Impact Statement' location (compilation or detection failed).\n"

            check_output = os.popen(f"chktex {writeup_file} -q -n2 -n24 -n13 -n1").read()
            review_img_cap_ref = perform_imgs_cap_ref_review(
                model=model,
                pdf_path=reflection_pdf,
                temperature=temperature,
            )
            analysis_duplicate_figs = detect_duplicate_figures(
                model=model,
                pdf_path=reflection_pdf,
                temperature=temperature,
            )

            reflection_prompt = render_text(
                template_name="writeup/reflection_prompt.txt.j2",
                context=_WriteupReflectionPromptContext(
                    unused_figs=unused_figs,
                    invalid_figs=invalid_figs,
                    reflection_page_info=reflection_page_info,
                    check_output=check_output,
                    review_img_cap_ref=str(review_img_cap_ref),
                    analysis_duplicate_figs=str(analysis_duplicate_figs),
                )._asdict(),
            )

            reflection_data, msg_history = get_structured_response_from_llm(
                prompt=reflection_prompt,
                model=model,
                system_message=big_model_system_message,
                temperature=temperature,
                schema_class=LATEX_WRITEUP_SCHEMA,
                msg_history=msg_history,
            )

            if reflection_data.get("should_stop", False):
                logger.info("LLM indicated reflections are complete.")
                break

            reflected_latex_code = reflection_data.get("latex_code", "").strip()
            if not reflected_latex_code:
                logger.warning(
                    "Structured reflection response missing latex_code (step %s).",
                    reflection_idx + 1,
                )
                break
            if reflected_latex_code != current_latex:
                final_text = reflected_latex_code
                cleanup_map = {"</end": r"\\end", "</begin": r"\\begin", "’": "'"}
                for bad_str, repl_str in cleanup_map.items():
                    final_text = final_text.replace(bad_str, repl_str)
                final_text = re.sub(r"(\d+(?:\.\d+)?)%", r"\1\\%", final_text)
                writeup_file.write_text(final_text, encoding="utf-8")
                ensure_graphicspath(
                    writeup_file=str(writeup_file),
                    latex_folder=str(latex_folder),
                    figures_dir=str(figures_dir),
                )
                _ensure_all_figures_referenced(
                    writeup_file=str(writeup_file),
                    plot_names=plot_names,
                )
                compile_latex(cwd=str(latex_folder), pdf_file=reflection_pdf)
                final_pdf_path = Path(reflection_pdf)
            else:
                logger.debug("No changes detected in reflection step %s.", reflection_idx + 1)
                break

            review_img_selection = perform_imgs_cap_ref_review_selection(
                model=model,
                pdf_path=reflection_pdf,
                reflection_page_info=reflection_page_info,
                temperature=temperature,
            )
            img_reflection_prompt = render_text(
                template_name="writeup/img_reflection_prompt.txt.j2",
                context=_WriteupImgReflectionPromptContext(
                    used_figs=str(sorted(used_figs)),
                    unused_figs=unused_figs,
                    reflection_page_info=reflection_page_info,
                    review_img_selection=str(review_img_selection),
                )._asdict(),
            )
            img_reflection_data, msg_history = get_structured_response_from_llm(
                prompt=img_reflection_prompt,
                model=model,
                system_message=big_model_system_message,
                temperature=temperature,
                schema_class=LATEX_WRITEUP_SCHEMA,
                msg_history=msg_history,
            )
            if img_reflection_data.get("should_stop", False):
                logger.info("Figure reflection complete.")
                break
            reflected_latex_code = img_reflection_data.get("latex_code", "").strip()
            if not reflected_latex_code:
                logger.warning(
                    "Structured figure reflection missing latex_code (step %s).",
                    reflection_idx + 1,
                )
                break
            current_after_text = writeup_file.read_text(encoding="utf-8")
            if reflected_latex_code != current_after_text:
                final_text = reflected_latex_code
                cleanup_map = {"</end": r"\\end", "</begin": r"\\begin", "’": "'"}
                for bad_str, repl_str in cleanup_map.items():
                    final_text = final_text.replace(bad_str, repl_str)
                final_text = re.sub(r"(\d+(?:\.\d+)?)%", r"\1\\%", final_text)
                writeup_file.write_text(final_text, encoding="utf-8")
                ensure_graphicspath(
                    writeup_file=str(writeup_file),
                    latex_folder=str(latex_folder),
                    figures_dir=str(figures_dir),
                )
                _ensure_all_figures_referenced(
                    writeup_file=str(writeup_file),
                    plot_names=plot_names,
                )
                compile_latex(cwd=str(latex_folder), pdf_file=reflection_pdf)
                final_pdf_path = Path(reflection_pdf)
            else:
                logger.debug(
                    "No changes detected in figure reflection step %s.",
                    reflection_idx + 1,
                )
                break

        if final_pdf_path is None:
            fallback_pdf = f"{base_pdf_stem}_{compile_attempt}.pdf"
            compile_latex(cwd=str(latex_folder), pdf_file=fallback_pdf)
            final_pdf_path = Path(fallback_pdf)

        return final_pdf_path.exists()

    except Exception:
        logger.exception("EXCEPTION in perform_writeup:")
        return False


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Perform writeup for a project")
    parser.add_argument("--folder", type=str, help="Project folder", required=True)
    parser.add_argument("--no-writing", action="store_true", help="Only generate")
    parser.add_argument("--num-cite-rounds", type=int, default=20)
    parser.add_argument(
        "--model",
        type=str,
        default="gpt-5",
        help="LLM model to use for writeup.",
    )
    parser.add_argument(
        "--writeup-reflections",
        type=int,
        default=3,
        help="Number of reflection steps for the final LaTeX writeup.",
    )
    parser.add_argument(
        "--page-limit",
        type=int,
        default=8,
        help="Target page limit for the main paper (excluding references, impact statement, etc.)",
    )
    parser.add_argument(
        "--temperature",
        type=float,
        default=1.0,
        help="Sampling temperature for all writeup LLM calls.",
    )
    args = parser.parse_args()

    try:

        def _noop_artifact_callback(_: ArtifactSpec) -> None:
            return

        success = perform_writeup(
            base_folder=args.folder,
            no_writing=args.no_writing,
            num_cite_rounds=args.num_cite_rounds,
            model=args.model,
            n_writeup_reflections=args.writeup_reflections,
            page_limit=args.page_limit,
            temperature=args.temperature,
            artifact_callback=_noop_artifact_callback,
        )
        if not success:
            logger.error("Writeup process did not complete successfully.")
    except Exception:
        logger.exception("EXCEPTION in main:")
