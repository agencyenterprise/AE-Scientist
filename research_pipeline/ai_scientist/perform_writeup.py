import argparse
import json
import logging
import os
import os.path as osp
import re
import shutil
import subprocess
import traceback
import uuid
from pathlib import Path
from typing import Any, Callable, Dict, List, NamedTuple, Optional, cast

from ai_scientist.perform_citations import gather_citations
from ai_scientist.prompts.render import render_text
from ai_scientist.review_integration import (
    detect_duplicate_figures,
    generate_vlm_img_review,
    perform_imgs_cap_ref_review,
    perform_imgs_cap_ref_review_selection,
)
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


# --------------------------------------------------------------------------- #
# Helper utilities                                                            #
# --------------------------------------------------------------------------- #


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


# --------------------------------------------------------------------------- #
# Codex-based writeup implementation                                          #
# --------------------------------------------------------------------------- #


class _CodexPaperTaskContext(NamedTuple):
    idea_text: str
    summaries: str
    aggregator_code: str
    plot_list: str
    plot_descriptions: str
    figures_dir: str
    latex_folder: str
    page_limit: int
    previous_run_path: str


class _CodexRefinementTaskContext(NamedTuple):
    latex_folder: str
    current_pdf_path: str
    page_info: str
    used_figures: str
    unused_figures: str
    invalid_figures: str
    chktex_output: str
    vlm_caption_review: str
    vlm_duplicate_analysis: str
    vlm_selection_review: str


class VLMReviewResult(NamedTuple):
    """Results from VLM review of the paper."""

    page_info: str
    used_figures: set[str]
    unused_figures: list[str]
    invalid_figures: list[str]
    chktex_output: str
    caption_review: str
    duplicate_analysis: str
    selection_review: str
    is_acceptable: bool


def _run_vlm_review(
    *,
    pdf_path: str,
    latex_folder: Path,
    plot_names: list[str],
    model: str,
    temperature: float,
    page_limit: int,
) -> VLMReviewResult:
    """
    Run VLM review on the compiled PDF and gather all feedback.

    Returns a VLMReviewResult with all review information.
    """
    writeup_file = latex_folder / "template.tex"

    # Read current LaTeX to find referenced figures
    current_latex = writeup_file.read_text(encoding="utf-8")
    referenced_figs_temp = re.findall(r"\\includegraphics(?:\[[^\]]*\])?{([^}]+)}", current_latex)
    used_figs = {Path(ref).name for ref in referenced_figs_temp}
    all_figs = set(plot_names)
    unused_figs = sorted(all_figs - used_figs)
    invalid_figs = sorted(used_figs - all_figs)

    # Detect page count
    impact_loc = detect_pages_before_impact(str(latex_folder))
    if impact_loc is not None:
        page_num, line_num = impact_loc
        page_info = (
            f"'Impact Statement' currently starts on page {page_num}, approximately line {line_num}. "
            f"The target length is about {page_limit} pages; keep the narrative concise but informative."
        )
    else:
        page_info = (
            "Could not detect the 'Impact Statement' location (compilation or detection failed)."
        )

    # Run chktex
    chktex_output = os.popen(f"chktex {writeup_file} -q -n2 -n24 -n13 -n1").read()

    # VLM reviews
    caption_review = perform_imgs_cap_ref_review(
        model=model,
        pdf_path=pdf_path,
        temperature=temperature,
    )
    duplicate_analysis = detect_duplicate_figures(
        model=model,
        pdf_path=pdf_path,
        temperature=temperature,
    )
    selection_review = perform_imgs_cap_ref_review_selection(
        model=model,
        pdf_path=pdf_path,
        reflection_page_info=page_info,
        temperature=temperature,
    )

    # Determine if paper is acceptable (heuristic: no major issues)
    is_acceptable = (
        len(invalid_figs) == 0
        and len(chktex_output.strip()) < 100  # Few/no chktex warnings
        and "duplicate" not in str(duplicate_analysis).lower()
    )

    return VLMReviewResult(
        page_info=page_info,
        used_figures=used_figs,
        unused_figures=unused_figs,
        invalid_figures=invalid_figs,
        chktex_output=chktex_output,
        caption_review=str(caption_review),
        duplicate_analysis=str(duplicate_analysis),
        selection_review=str(selection_review),
        is_acceptable=is_acceptable,
    )


def perform_writeup(
    *,
    base_folder: str,
    model: str,
    temperature: float,
    run_dir_name: str,
    num_cite_rounds: int,
    max_refinement_rounds: int,
    page_limit: int,
    codex_timeout_seconds: int,
    writeup_attempt: int,
    citations_text: str | None = None,
    event_callback: Optional[Callable[[BaseEvent], None]] = None,
    run_id: Optional[str] = None,
) -> bool:
    """
    Perform paper writeup using Codex for LaTeX generation.

    This function uses Codex to write and compile the paper iteratively,
    with VLM review providing feedback between Codex runs.

    Args:
        base_folder: Base folder containing experiment data
        model: Model to use for Codex and VLM review
        temperature: Sampling temperature for LLM calls
        run_dir_name: Name of the run directory (e.g., "0-run") - determined by earlier pipeline stages
        num_cite_rounds: Number of citation gathering rounds
        max_refinement_rounds: Maximum number of VLM review + Codex refinement cycles
        page_limit: Target page limit for the paper
        codex_timeout_seconds: Timeout for each Codex run
        writeup_attempt: Attempt number for unique log filenames (0-indexed)
        citations_text: Pre-gathered citations (optional)
        event_callback: Callback for emitting progress events
        run_id: Run ID for event tracking

    Returns:
        True if paper was successfully generated, False otherwise
    """
    logger.info("\n" + "=" * 80)
    logger.info("STARTING PERFORM_WRITEUP")
    logger.debug(f"base_folder: {base_folder}")
    logger.debug(f"run_dir_name: {run_dir_name}")
    logger.debug(f"model: {model}")
    logger.debug(f"max_refinement_rounds: {max_refinement_rounds}")
    logger.info("=" * 80 + "\n")

    def emit_event(substep: str, progress: float, step_progress: float) -> None:
        if event_callback and run_id:
            event_callback(
                PaperGenerationProgressEvent(
                    run_id=run_id,
                    step="paper_writeup",
                    substep=substep,
                    progress=progress,
                    step_progress=step_progress,
                )
            )

    emit_event("Starting Codex-based paper writeup...", 0.30, 0.0)

    try:
        base_path = Path(base_folder)
        logs_dir = base_path / "logs"
        logs_dir.mkdir(parents=True, exist_ok=True)

        run_out_dir = logs_dir / run_dir_name
        run_out_dir.mkdir(parents=True, exist_ok=True)
        base_pdf_stem = run_out_dir / "paper"
        latex_folder = run_out_dir / "latex"
        figures_dir = base_path / "figures" / run_dir_name

        # Load experiment data
        idea_text = load_idea_text(
            base_path=base_path, logs_dir=logs_dir, run_dir_name=run_dir_name
        )
        summaries = load_exp_summaries(base_path=base_path, run_dir_name=run_dir_name)
        filtered_summaries = filter_experiment_summaries(
            exp_summaries=summaries, step_name="writeup"
        )
        filtered_summaries = cast(
            Dict[str, Any],
            strip_summary_keys(filtered_summaries, SUMMARY_KEYS_TO_STRIP),
        )
        combined_summaries_str = json.dumps(filtered_summaries, indent=2)

        # Setup LaTeX folder from template
        if latex_folder.exists():
            shutil.rmtree(latex_folder)
        shutil.copytree(
            src="ai_scientist/blank_icml_latex",
            dst=latex_folder,
            dirs_exist_ok=True,
        )

        writeup_file = latex_folder / "template.tex"

        # Collect available plots
        plot_names: List[str] = []
        if figures_dir.exists():
            plot_names = sorted(
                [
                    entry.name
                    for entry in figures_dir.iterdir()
                    if entry.is_file() and entry.suffix.lower() == ".png"
                ]
            )

        # Load aggregator code
        aggregator_path = base_path / "auto_plot_aggregator.py"
        aggregator_code = (
            aggregator_path.read_text(encoding="utf-8")
            if aggregator_path.exists()
            else "No aggregator script found."
        )

        # Gather citations
        emit_event("Gathering citations...", 0.32, 0.05)
        if citations_text is None:
            citations_text = gather_citations(
                base_path=base_path,
                logs_dir=logs_dir,
                model=model,
                temperature=temperature,
                num_cite_rounds=num_cite_rounds,
                run_dir_name=run_dir_name,
            )
        if citations_text:
            update_references_block(writeup_path=writeup_file, citations_text=citations_text)

        # Check for previous run data
        previous_run_path: str = ""
        if os.environ.get("HAS_PREVIOUS_RUN", "").strip().lower() == "true":
            previous_run_path_str = os.environ.get(
                "PREVIOUS_RUN_DATA_PATH", "/workspace/previous_run_data"
            )
            if Path(previous_run_path_str).exists():
                previous_run_path = previous_run_path_str
                logger.info("Previous run data available at: %s", previous_run_path)
            else:
                logger.warning(
                    "HAS_PREVIOUS_RUN is set but path %s does not exist", previous_run_path_str
                )

        # Generate VLM figure descriptions
        emit_event("Generating figure descriptions...", 0.38, 0.15)
        plot_descriptions_str = ""
        try:
            desc_map: Dict[str, str] = {}
            logger.info("Generating VLM figure descriptions for %s plot(s)...", len(plot_names))
            for idx, plot_name in enumerate(plot_names, start=1):
                plot_path = figures_dir / plot_name
                if not plot_path.exists():
                    continue
                img_dict = {"images": [str(plot_path)], "caption": "No direct caption"}
                review_data = generate_vlm_img_review(
                    img=img_dict, model=model, temperature=temperature
                )
                desc_map[plot_name] = (
                    review_data.get("Img_description", "No description found")
                    if review_data
                    else "No description found"
                )
            plot_descriptions_list = [
                f"{plot_name}: {desc_map.get(plot_name, 'No description found')}"
                for plot_name in plot_names
            ]
            plot_descriptions_str = "\n".join(plot_descriptions_list)
        except Exception:
            logger.exception("Failed to generate VLM figure descriptions")
            plot_descriptions_str = "No descriptions available."

        # Setup graphicspath
        ensure_graphicspath(
            writeup_file=str(writeup_file),
            latex_folder=str(latex_folder),
            figures_dir=str(figures_dir),
        )

        # ------------------------------------------------------------------- #
        # Phase 1: Initial Codex paper writing                                #
        # ------------------------------------------------------------------- #
        emit_event("Running Codex to write initial paper...", 0.40, 0.20)

        codex_task_content = render_text(
            template_name="writeup/codex_paper_task.md.j2",
            context=_CodexPaperTaskContext(
                idea_text=idea_text,
                summaries=combined_summaries_str,
                aggregator_code=aggregator_code,
                plot_list=", ".join(plot_names),
                plot_descriptions=plot_descriptions_str,
                figures_dir=str(figures_dir),
                latex_folder=str(latex_folder),
                page_limit=page_limit,
                previous_run_path=previous_run_path,
            )._asdict(),
        )

        task_file = run_out_dir / "codex_paper_task.md"
        task_file.write_text(codex_task_content, encoding="utf-8")

        research_pipeline_root = Path(__file__).resolve().parents[1]
        runner = CodexCliRunner(
            workspace_dir=base_path,
            research_pipeline_root=research_pipeline_root,
            session_log_name=f"codex_paper_writeup_attempt_{writeup_attempt}.log",
            events_log_name=f"codex_paper_writeup_attempt_{writeup_attempt}_events.jsonl",
            timeout_seconds=codex_timeout_seconds,
            model=model,
            event_callback=event_callback if event_callback else lambda _: None,
        )

        logger.info("Running Codex for initial paper writing...")
        term_out, exec_time, exc_type, exc_info = runner.run_autonomous(task_file=task_file)
        logger.info(
            "Codex initial paper writing completed in %.1fs (exc_type=%s)",
            exec_time,
            exc_type,
        )

        # Save initial PDF
        version = 0
        initial_pdf = f"{base_pdf_stem}_{version}.pdf"
        source_pdf = latex_folder / "template.pdf"

        if not source_pdf.exists():
            # Try compiling if Codex didn't
            logger.warning("Codex did not produce PDF, attempting manual compilation...")
            compile_latex(cwd=str(latex_folder), pdf_file=initial_pdf)
        else:
            shutil.copy(source_pdf, initial_pdf)
            logger.info("Saved initial paper as %s", initial_pdf)

        if not Path(initial_pdf).exists():
            logger.error("Failed to produce initial PDF")
            return False

        # ------------------------------------------------------------------- #
        # Phase 2: VLM review + Codex refinement loop                         #
        # ------------------------------------------------------------------- #
        current_pdf = initial_pdf

        for refinement_idx in range(max_refinement_rounds):
            version = refinement_idx + 1
            step_progress = 0.30 + (0.60 * version / (max_refinement_rounds + 1))

            emit_event(
                f"Running VLM review (round {version}/{max_refinement_rounds})...",
                0.40 + step_progress * 0.5,
                step_progress,
            )

            # Run VLM review
            logger.info("Running VLM review round %d...", version)
            review = _run_vlm_review(
                pdf_path=current_pdf,
                latex_folder=latex_folder,
                plot_names=plot_names,
                model=model,
                temperature=temperature,
                page_limit=page_limit,
            )

            if review.is_acceptable:
                logger.info("VLM review indicates paper is acceptable. Stopping refinement.")
                break

            # Run Codex refinement
            emit_event(
                f"Running Codex refinement (round {version}/{max_refinement_rounds})...",
                0.40 + step_progress * 0.5 + 0.05,
                step_progress + 0.05,
            )

            refinement_task_content = render_text(
                template_name="writeup/codex_paper_refinement_task.md.j2",
                context=_CodexRefinementTaskContext(
                    latex_folder=str(latex_folder),
                    current_pdf_path=current_pdf,
                    page_info=review.page_info,
                    used_figures=str(sorted(review.used_figures)),
                    unused_figures=str(review.unused_figures),
                    invalid_figures=str(review.invalid_figures),
                    chktex_output=review.chktex_output,
                    vlm_caption_review=review.caption_review,
                    vlm_duplicate_analysis=review.duplicate_analysis,
                    vlm_selection_review=review.selection_review,
                )._asdict(),
            )

            refinement_task_file = run_out_dir / f"codex_refinement_task_{version}.md"
            refinement_task_file.write_text(refinement_task_content, encoding="utf-8")

            refinement_runner = CodexCliRunner(
                workspace_dir=base_path,
                research_pipeline_root=research_pipeline_root,
                session_log_name=f"codex_paper_refinement_attempt_{writeup_attempt}_v{version}.log",
                events_log_name=f"codex_paper_refinement_attempt_{writeup_attempt}_v{version}_events.jsonl",
                timeout_seconds=codex_timeout_seconds,
                model=model,
                event_callback=event_callback if event_callback else lambda _: None,
            )

            logger.info("Running Codex refinement round %d...", version)
            term_out, exec_time, exc_type, exc_info = refinement_runner.run_autonomous(
                task_file=refinement_task_file
            )
            logger.info(
                "Codex refinement round %d completed in %.1fs (exc_type=%s)",
                version,
                exec_time,
                exc_type,
            )

            # Save refined PDF
            refined_pdf = f"{base_pdf_stem}_{version}.pdf"
            if source_pdf.exists():
                shutil.copy(source_pdf, refined_pdf)
                logger.info("Saved refined paper as %s", refined_pdf)
                current_pdf = refined_pdf
            else:
                # Try manual compilation
                compile_latex(cwd=str(latex_folder), pdf_file=refined_pdf)
                if Path(refined_pdf).exists():
                    current_pdf = refined_pdf

        emit_event("Paper writeup complete.", 0.80, 1.0)
        logger.info("Final paper: %s", current_pdf)
        return Path(current_pdf).exists()

    except Exception:
        logger.exception("EXCEPTION in perform_writeup:")
        return False


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Perform writeup for a project using Codex")
    parser.add_argument("--folder", type=str, help="Project folder", required=True)
    parser.add_argument(
        "--run-dir-name", type=str, help="Run directory name (e.g., 0-run)", required=True
    )
    parser.add_argument("--num-cite-rounds", type=int, default=20)
    parser.add_argument(
        "--model",
        type=str,
        default="claude-sonnet-4-20250514",
        help="Model to use for Codex and VLM review.",
    )
    parser.add_argument(
        "--max-refinement-rounds",
        type=int,
        default=3,
        help="Maximum number of VLM review + Codex refinement cycles.",
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
        help="Sampling temperature for all LLM calls.",
    )
    parser.add_argument(
        "--codex-timeout",
        type=int,
        default=3600,
        help="Timeout in seconds for each Codex run.",
    )
    parser.add_argument(
        "--writeup-attempt",
        type=int,
        default=0,
        help="Attempt number for unique log filenames.",
    )
    args = parser.parse_args()

    try:
        success = perform_writeup(
            base_folder=args.folder,
            model=args.model,
            temperature=args.temperature,
            run_dir_name=args.run_dir_name,
            num_cite_rounds=args.num_cite_rounds,
            max_refinement_rounds=args.max_refinement_rounds,
            page_limit=args.page_limit,
            codex_timeout_seconds=args.codex_timeout,
            writeup_attempt=args.writeup_attempt,
        )
        if not success:
            logger.error("Writeup process did not complete successfully.")
    except Exception:
        logger.exception("EXCEPTION in main:")
