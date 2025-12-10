import argparse
import json
import logging
import os
import os.path as osp
import re
import shutil
import subprocess
import traceback
import unicodedata
import uuid
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from langchain_core.messages import BaseMessage
from pydantic import BaseModel, Field

from ai_scientist.citations_specs import CITATION_SEARCH_SCHEMA, CITATION_SELECTION_SCHEMA
from ai_scientist.ideation.semantic_scholar import search_for_papers
from ai_scientist.latest_run_finder import find_latest_run_dir_name
from ai_scientist.llm import get_structured_response_from_llm
from ai_scientist.perform_vlm_review import (
    detect_duplicate_figures,
    generate_vlm_img_review,
    perform_imgs_cap_ref_review,
    perform_imgs_cap_ref_review_selection,
)
from ai_scientist.treesearch.events import BaseEvent, PaperGenerationProgressEvent

logger = logging.getLogger(__name__)


def _ensure_graphicspath(writeup_file: str, latex_folder: str, figures_dir: str) -> None:
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


def remove_accents_and_clean(s: str) -> str:
    # Normalize to separate accents
    nfkd_form = unicodedata.normalize("NFKD", s)
    # Remove non-ASCII characters
    ascii_str = nfkd_form.encode("ASCII", "ignore").decode("ascii")
    # Remove anything but letters, digits, underscores, colons, dashes, @, {, }, and now commas
    ascii_str = re.sub(r"[^a-zA-Z0 - 9:_@\{\},-]+", "", ascii_str)
    # Convert to lowercase
    ascii_str = ascii_str.lower()
    return ascii_str


def compile_latex(cwd: str, pdf_file: str, timeout: int = 30) -> bool:
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
                timeout=timeout,
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
                f"EXCEPTION in compile_latex: LaTeX timed out after {timeout} seconds."
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


def get_citation_addition(
    model: str,
    context: tuple,
    current_round: int,
    total_rounds: int,
    idea_text: str,
    temperature: float,
) -> str | None:
    report, citations = context
    msg_history: list[BaseMessage] = []
    citation_system_msg_template = """You are an ambitious AI researcher who is looking to publish a paper to a top-tier ML conference that will contribute significantly to the field.
You have already completed the experiments and now you are looking to collect citations to related papers.
This phase focuses on collecting references and annotating them to be integrated later.
Collected citations will be added to a references.bib file.

Reasons to reference papers include:
1. Summarizing Research: Cite sources when summarizing the existing literature.
2. Using Specific Concepts or Data: Provide citations when discussing specific theories, models, or data.
3. Comparing Findings: Cite relevant studies when comparing or contrasting different findings.
4. Highlighting Research Gaps: Cite previous research when pointing out gaps your survey addresses.
5. Using Established Methods: Cite the creators of methodologies you employ in your survey.
6. Supporting Arguments: Cite sources that back up your conclusions and arguments.
7. Suggesting Future Research: Reference studies related to proposed future research directions.

Ensure sufficient cites will be collected for all of these categories, and no categories are missed.
You will be given access to the Semantic Scholar API; only add citations that you have found using the API.
Aim to discuss a broad range of relevant papers, not just the most popular ones.
Make sure not to copy verbatim from prior literature to avoid plagiarism.
You will have {total_rounds} rounds to add to the references but do not need to use them all.

DO NOT ADD A CITATION THAT ALREADY EXISTS!"""

    citation_first_prompt_template = """Round {current_round}/{total_rounds}:

You planned and executed the following idea:
```markdown
{Idea}
```

You produced the following report:
```markdown
{report}
```

Your current list of citations is:
```
{citations}
```

Identify the most important citation that you still need to add, and the query to find the paper.

Return a JSON object matching the CitationSearchResponse schema:
- "needs_more_citations": whether another citation is still required.
- "description": purpose of the desired citation (what you are looking for).
- "query": Semantic Scholar search query to find the paper.
If "needs_more_citations" is false, leave the other fields blank."""

    citation_second_prompt_template = """Search has recovered the following articles:

{papers}

Return a JSON object matching the CitationSelectionResponse schema:
- "should_add": whether any of the retrieved papers should be added.
- "selected_indices": array of integer indices referencing the papers above.
- "description": brief summary of the selected work(s), their relevance, and where to cite them.
If "should_add" is false, leave "selected_indices" empty."""

    try:
        structured_response, msg_history = get_structured_response_from_llm(
            prompt=citation_first_prompt_template.format(
                current_round=current_round + 1,
                total_rounds=total_rounds,
                Idea=idea_text,
                report=report,
                citations=citations,
            ),
            model=model,
            system_message=citation_system_msg_template.format(total_rounds=total_rounds),
            temperature=temperature,
            schema_class=CITATION_SEARCH_SCHEMA,
            msg_history=msg_history,
        )
        if not structured_response.get("needs_more_citations", True):
            logger.info("No more citations needed.")
            return None
        query = structured_response.get("query", "")
        if not isinstance(query, str) or not query.strip():
            logger.warning("Citation search response missing query.")
            return None
        papers = search_for_papers(query)
    except Exception:
        logger.exception("EXCEPTION in get_citation_addition (initial search):")
        return None

    if papers is None:
        logger.warning("No papers found.")
        return None

    paper_strings = []
    for i, paper in enumerate(papers):
        paper_strings.append(
            "{i}: {title}. {authors}. {venue}, {year}.\nAbstract: {abstract}".format(
                i=i,
                title=paper["title"],
                authors=paper["authors"],
                venue=paper["venue"],
                year=paper["year"],
                abstract=paper["abstract"],
            )
        )
    papers_str = "\n\n".join(paper_strings)

    try:
        selection_response, msg_history = get_structured_response_from_llm(
            prompt=citation_second_prompt_template.format(
                papers=papers_str,
                current_round=current_round + 1,
                total_rounds=total_rounds,
            ),
            model=model,
            system_message=citation_system_msg_template.format(total_rounds=total_rounds),
            temperature=temperature,
            schema_class=CITATION_SELECTION_SCHEMA,
            msg_history=msg_history,
        )
        if not selection_response.get("should_add", False):
            logger.info("Do not add any.")
            return None
        selected_indices = selection_response.get("selected_indices", [])
        if not isinstance(selected_indices, list) or not selected_indices:
            logger.warning("Citation selection returned no indices.")
            return None
        if not all(isinstance(idx, int) and 0 <= idx < len(papers) for idx in selected_indices):
            logger.warning("Received invalid citation indices: %s", selected_indices)
            return None
        bibtexs = [papers[i]["citationStyles"]["bibtex"] for i in selected_indices]

        cleaned_bibtexs = []
        for bibtex in bibtexs:
            newline_index = bibtex.find("\n")
            cite_key_line = bibtex[:newline_index]
            cite_key_line = remove_accents_and_clean(cite_key_line)
            cleaned_bibtexs.append(cite_key_line + bibtex[newline_index:])
        bibtexs = cleaned_bibtexs

        bibtex_string = "\n".join(bibtexs)
        desc = selection_response.get("description", "")
    except Exception:
        logger.exception("EXCEPTION in get_citation_addition (selecting papers):")
        return None

    references_format = """% {description}
{bibtex}"""

    references_prompt = references_format.format(bibtex=bibtex_string, description=desc)
    return references_prompt


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


def load_idea_text(base_path: Path, logs_dir: Path, run_dir_name: str | None) -> str:
    """
    Load the idea markdown content by checking project-level and run-level files.
    """
    candidates: List[Path] = [
        base_path / "research_idea.md",
        base_path / "idea.md",
    ]
    if run_dir_name:
        candidates.append(logs_dir / run_dir_name / "research_idea.md")

    for candidate in candidates:
        if candidate.exists():
            try:
                return candidate.read_text(encoding="utf-8")
            except Exception:
                logger.warning("Warning: failed to read idea text from %s", candidate)
                logger.debug(traceback.format_exc())
    logger.warning("Warning: Missing idea markdown files under %s and %s", base_path, logs_dir)
    return ""


def load_exp_summaries(base_path: Path, run_dir_name: str) -> Dict[str, Any]:
    """
    Load experiment summary artifacts (baseline, research, ablations) from the run directory.
    """
    logs_dir = base_path / "logs"
    summary_map: Dict[str, Path] = {
        "BASELINE_SUMMARY": logs_dir / run_dir_name / "baseline_summary.json",
        "RESEARCH_SUMMARY": logs_dir / run_dir_name / "research_summary.json",
        "ABLATION_SUMMARY": logs_dir / run_dir_name / "ablation_summary.json",
    }
    loaded: Dict[str, Any] = {}
    for key, path in summary_map.items():
        if path.exists():
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                if key == "ABLATION_SUMMARY":
                    loaded[key] = data if isinstance(data, list) else []
                else:
                    loaded[key] = data if isinstance(data, dict) else {}
            except json.JSONDecodeError:
                logger.warning("Warning: %s is not valid JSON. Using empty data.", path)
                logger.debug(traceback.format_exc())
                loaded[key] = [] if key == "ABLATION_SUMMARY" else {}
        else:
            logger.warning("Summary file not found for %s: %s", key, path)
            loaded[key] = [] if key == "ABLATION_SUMMARY" else {}
    return loaded


def filter_experiment_summaries(exp_summaries: Dict[str, Any], step_name: str) -> Dict[str, Any]:
    """
    Reduce experiment summaries to the fields needed by a specific pipeline step.
    """
    if step_name == "citation_gathering":
        node_keys_to_keep = {
            "overall_plan",
            "analysis",
            "metric",
            "vlm_feedback_summary",
        }
    elif step_name == "writeup":
        node_keys_to_keep = {
            "overall_plan",
            "analysis",
            "metric",
            "code",
            "plot_analyses",
            "vlm_feedback_summary",
        }
    elif step_name == "plot_aggregation":
        node_keys_to_keep = {
            "overall_plan",
            "analysis",
            "plot_plan",
            "plot_code",
            "plot_analyses",
            "vlm_feedback_summary",
            "exp_results_npy_files",
        }
    else:
        raise ValueError(f"Invalid step name: {step_name}")

    filtered: Dict[str, Any] = {}
    for stage_name, stage_content in exp_summaries.items():
        if stage_name in {"BASELINE_SUMMARY", "RESEARCH_SUMMARY"}:
            filtered[stage_name] = {}
            best_node = stage_content.get("best node", {})
            filtered_best: Dict[str, Any] = {}
            for node_key, node_value in best_node.items():
                if node_key in node_keys_to_keep:
                    filtered_best[node_key] = node_value
            filtered[stage_name]["best node"] = filtered_best
        elif stage_name == "ABLATION_SUMMARY":
            if step_name == "plot_aggregation":
                filtered[stage_name] = {}
                for ablation_summary in stage_content:
                    ablation_name = ablation_summary.get("ablation_name")
                    if not ablation_name:
                        continue
                    filtered[stage_name][ablation_name] = {}
                    for node_key, node_value in ablation_summary.items():
                        if node_key in node_keys_to_keep:
                            filtered[stage_name][ablation_name][node_key] = node_value
            else:
                filtered[stage_name] = stage_content
    return filtered


def gather_citations(
    base_path: Path,
    logs_dir: Path,
    model: str,
    temperature: float,
    num_cite_rounds: int,
    run_dir_name: str,
) -> str | None:
    """
    Resume-aware citation gathering that persists progress per run directory.
    """
    cache_base = logs_dir / run_dir_name if run_dir_name else base_path
    cache_base.mkdir(parents=True, exist_ok=True)
    citations_cache_path = cache_base / "cached_citations.bib"
    progress_path = cache_base / "citations_progress.json"

    citations_text = ""
    current_round = 0
    if citations_cache_path.exists() and progress_path.exists():
        try:
            citations_text = citations_cache_path.read_text(encoding="utf-8")
            progress_data = json.loads(progress_path.read_text(encoding="utf-8"))
            current_round = int(progress_data.get("completed_rounds", 0))
            logger.info("Resuming citation gathering from round %s", current_round)
        except Exception:
            logger.warning("Warning: failed to load cached citations; starting fresh.")
            logger.debug(traceback.format_exc())
            citations_text = ""
            current_round = 0

    idea_text = load_idea_text(base_path=base_path, logs_dir=logs_dir, run_dir_name=run_dir_name)
    summaries = load_exp_summaries(base_path=base_path, run_dir_name=run_dir_name)
    filtered_summaries = filter_experiment_summaries(
        exp_summaries=summaries, step_name="citation_gathering"
    )
    filtered_summaries_str = json.dumps(filtered_summaries, indent=2)

    for round_idx in range(current_round, num_cite_rounds):
        try:
            context_for_citation = (filtered_summaries_str, citations_text)
            addition = get_citation_addition(
                model=model,
                context=context_for_citation,
                current_round=round_idx,
                total_rounds=num_cite_rounds,
                idea_text=idea_text,
                temperature=temperature,
            )
            if addition is None:
                citations_cache_path.write_text(citations_text, encoding="utf-8")
                progress_path.write_text(
                    json.dumps(
                        {"completed_rounds": round_idx, "status": "completed"},
                        indent=2,
                    ),
                    encoding="utf-8",
                )
                break

            title_match = re.search(r" title = {(.*?)}", addition, flags=re.IGNORECASE)
            if title_match:
                new_title = title_match.group(1).lower()
                existing_titles = [
                    t.lower()
                    for t in re.findall(r" title = {(.*?)}", citations_text, flags=re.IGNORECASE)
                ]
                if new_title in existing_titles:
                    logger.info("Skipping duplicate citation: %s", new_title)
                    continue

            citations_text = f"{citations_text}\n{addition}".strip()
            citations_cache_path.write_text(citations_text, encoding="utf-8")
            progress_path.write_text(
                json.dumps(
                    {"completed_rounds": round_idx + 1, "status": "in_progress"},
                    indent=2,
                ),
                encoding="utf-8",
            )
        except Exception:
            logger.exception("EXCEPTION in gather_citations during round %s:", round_idx)
            citations_cache_path.write_text(citations_text, encoding="utf-8")
            progress_path.write_text(
                json.dumps({"completed_rounds": round_idx, "status": "error"}, indent=2),
                encoding="utf-8",
            )
            continue

    return citations_text if citations_text else None


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


# Using a template string to allow injection of the {page_limit} argument
writeup_system_message_template = """You are an ambitious AI researcher who is looking to publish a paper that will contribute significantly to the field.
Ensure that the paper is scientifically accurate, objective, and truthful. Accurately report the experimental results, even if they are negative or inconclusive.
You are planning to submit to a top-tier ML conference, which has guidelines:
- The main paper is limited to {page_limit} pages, including all figures and tables, but excluding references, the impact statement, and optional appendices. In general, try to use the available space and include all relevant information.
- The main paper should be double-column format, while the appendices can be in single-column format. When in double column format, make sure that tables and figures are correctly placed.
- Do not change the overall style which is mandated by the conference. Keep to the current method of including the references.bib file.
- Do not remove the \\graphicspath directive or no figures will be found.

Here are some tips for each section of the paper:

- **Title**:
  - Title should be catchy and informative. It should give a good idea of what the paper is about.
  - Try to keep it under 2 lines.

- **Abstract**:
  - TL;DR of the paper.
  - What are we trying to do and why is it relevant?
  - Make sure the abstract reads smoothly and is well-motivated. This should be one continuous paragraph.

- **Introduction**:
  - Longer version of the Abstract, i.e., an overview of the entire paper.
  - Provide context to the study and explain its relevance.
  - If results are inconclusive or negative, present them frankly; if they are positive, you may highlight how the approach effectively addresses the research question or problem.
  - Summarize your contributions, highlighting pertinent findings, insights, or proposed methods.

- **Related Work**:
  - Academic siblings of our work, i.e., alternative attempts in literature at trying to address the same or similar problems.
  - Compare and contrast their approach with yours, noting key differences or similarities.
  - Ensure proper citations are provided.

- **Background**:
  - Present foundational concepts or prior work needed to understand your method.
  - This should include necessary definitions, the problem setting, or relevant theoretical constructs.

- **Method**:
  - Clearly detail what you propose to do and why. If your study aims to address certain hypotheses, describe them and how your method is constructed to test them.
  - If results are negative or inconclusive, you may suggest improvements or discuss possible causes.

- **Experimental Setup**:
  - Explain how you tested your method or hypothesis.
  - Describe necessary details such as data, environment, and baselines, but omit hardware details unless explicitly mentioned.

- **Experiments**:
  - Present the results truthfully according to the data you have. If outcomes are not as expected, discuss it transparently.
  - Include comparisons to baselines if available, and only include analyses supported by genuine data.
  - Try to include all relevant plots and tables. Consider combining multiple plots into one figure if they are related.

- **Conclusion**:
  - Summarize the entire paper, including key strengths or findings.
  - If results are strong, highlight how they might address the research problem.
  - If results are negative or inconclusive, highlight potential improvements or reasons and propose future directions.

- **Appendix**:
  - Place for supplementary material that did not fit in the main paper.

Ensure you are always writing good compilable LaTeX code. Common mistakes that should be fixed include:
- LaTeX syntax errors (unenclosed math, unmatched braces, etc.).
- Duplicate figure labels or references.
- Unescaped special characters: & % $ # _ {{ }} ~ ^ \\
- Proper table/figure closure.
- Do not hallucinate new citations or any results not in the logs.

When returning final code, place it in fenced triple backticks with 'latex' syntax highlighting.
"""

writeup_prompt = """Your goal is to write up the following idea:

```markdown
{idea_text}
```

We have the following experiment summaries (JSON):
```json
{summaries}
```

We also have a script used to produce the final plots (use this to see how the plots are generated and what names are used in the legend):
```python
{aggregator_code}
```
Please also consider which plots should naturally be grouped together as subfigures.

Available plots for the writeup (use these filenames):
```
{plot_list}
```

We also have VLM-based figure descriptions:
```
{plot_descriptions}
```

Your current progress on the LaTeX write-up is:
```latex
{latex_writeup}
```

Produce the final version of the LaTeX manuscript now, ensuring the paper is coherent, concise, and reports results accurately.
Return the entire file in full, with no unfilled placeholders!
This must be an acceptable complete LaTeX writeup.
Use the structured response schema (fields: latex_code, should_stop). Set should_stop=true only if no edits are required.
"""


def perform_writeup(
    base_folder: str,
    model: str,
    temperature: float,
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

        try:
            desc_map: Dict[str, str] = {}
            for plot_name in plot_names:
                plot_path = figures_dir / plot_name
                if not plot_path.exists():
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
            plot_descriptions_list = [
                f"{plot_name}: {desc_map.get(plot_name, 'No description found')}"
                for plot_name in plot_names
            ]
            plot_descriptions_str = "\n".join(plot_descriptions_list)
        except Exception:
            logger.exception("EXCEPTION in VLM figure description generation:")
            plot_descriptions_str = "No descriptions available."

        big_model_system_message = writeup_system_message_template.format(page_limit=page_limit)
        combined_prompt = writeup_prompt.format(
            idea_text=idea_text,
            summaries=combined_summaries_str,
            aggregator_code=aggregator_code,
            plot_list=", ".join(plot_names),
            latex_writeup=writeup_text,
            plot_descriptions=plot_descriptions_str,
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
        _ensure_graphicspath(
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

            reflection_prompt = f"""
Now let's reflect and identify issues (including but not limited to):
1) LaTeX syntax errors or style violations? Use chktex output below.
2) Is the writing clear and scientifically rigorous?
3) Have we included all relevant details from the summaries without hallucinating?
4) Figures available but not used: {unused_figs}
5) Figure references with no backing files: {invalid_figs}
{reflection_page_info}
chktex results:
```
{check_output}
```
VLM caption/reference review:
```
{review_img_cap_ref}
```
Duplicate figure analysis:
```
{analysis_duplicate_figs}
```

Respond using the structured schema (latex_code, should_stop). Set should_stop=true only if no revisions are necessary.
"""

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
                _ensure_graphicspath(
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
            img_reflection_prompt = f"""Review the figures with these goals:
1. Move low-impact figures to the appendix.
2. Remove redundant or uninformative visuals.
3. Combine sparse plots into richer groups.
4. Update accompanying text to reflect figure changes.

Currently used figures: {sorted(used_figs)}
Unused figures: {unused_figs}
{reflection_page_info}

VLM figure selection feedback:
```
{review_img_selection}
```

Use the structured response schema (latex_code, should_stop). Set should_stop=true if no changes are required.
"""
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
                _ensure_graphicspath(
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
        success = perform_writeup(
            base_folder=args.folder,
            no_writing=args.no_writing,
            num_cite_rounds=args.num_cite_rounds,
            model=args.model,
            n_writeup_reflections=args.writeup_reflections,
            page_limit=args.page_limit,
            temperature=args.temperature,
        )
        if not success:
            logger.error("Writeup process did not complete successfully.")
    except Exception:
        logger.exception("EXCEPTION in main:")
