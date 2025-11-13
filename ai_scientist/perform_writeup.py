import argparse
import json
import os
import os.path as osp
import re
import shutil
import subprocess
import traceback
import unicodedata
import uuid
from pathlib import Path
from typing import Any

import anthropic
import openai

from ai_scientist.ideation.semantic_scholar import search_for_papers
from ai_scientist.latest_run_finder import find_latest_run_dir_name
from ai_scientist.llm import (
    AVAILABLE_LLMS,
    create_client,
    create_vlm_client,
    extract_json_between_markers,
    get_response_from_llm,
)
from ai_scientist.perform_vlm_review import generate_vlm_img_review


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
        print("Warning: failed to adjust \\graphicspath; figures may not render.")
        print(traceback.format_exc())


def remove_accents_and_clean(s: str) -> str:
    # print("Original:", s)
    # Normalize to separate accents
    nfkd_form = unicodedata.normalize("NFKD", s)
    # Remove non-ASCII characters
    ascii_str = nfkd_form.encode("ASCII", "ignore").decode("ascii")
    # Remove anything but letters, digits, underscores, colons, dashes, @, {, }, and now commas
    ascii_str = re.sub(r"[^a-zA-Z0 - 9:_@\{\},-]+", "", ascii_str)
    # Convert to lowercase
    ascii_str = ascii_str.lower()
    # print("Cleaned: ", ascii_str)
    return ascii_str


def compile_latex(cwd: str, pdf_file: str, timeout: int = 30) -> bool:
    print("=" * 80)
    print("GENERATING LATEX")
    print(f"[DEBUG] cwd (latex folder): {cwd}")
    print(f"[DEBUG] target pdf_file: {pdf_file}")
    print(f"[DEBUG] cwd exists: {osp.exists(cwd)}")
    print(f"[DEBUG] cwd is absolute: {osp.isabs(cwd)}")
    print("=" * 80)

    commands = [
        ["pdflatex", "-interaction=nonstopmode", "template.tex"],
        ["bibtex", "template"],
        ["pdflatex", "-interaction=nonstopmode", "template.tex"],
        ["pdflatex", "-interaction=nonstopmode", "template.tex"],
    ]

    for i, command in enumerate(commands):
        print(f"\n[DEBUG] Running command {i + 1}/4: {' '.join(command)}")
        try:
            result = subprocess.run(
                command,
                cwd=cwd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                timeout=timeout,
            )
            print(f"[DEBUG] Command {i + 1} return code: {result.returncode}")
            if result.returncode != 0:
                print(f"[WARNING] Command failed with return code {result.returncode}")
            # Only show full output for errors or final compile
            if result.returncode != 0 or i == len(commands) - 1:
                print(
                    "Standard Output:\n",
                    result.stdout[-2000:] if len(result.stdout) > 2000 else result.stdout,
                )
                print(
                    "Standard Error:\n",
                    result.stderr[-1000:] if len(result.stderr) > 1000 else result.stderr,
                )
        except subprocess.TimeoutExpired:
            print(f"EXCEPTION in compile_latex: LaTeX timed out after {timeout} seconds.")
            print(traceback.format_exc())
        except subprocess.CalledProcessError:
            print(f"EXCEPTION in compile_latex: Error running command {' '.join(command)}")
            print(traceback.format_exc())

    print("\n" + "=" * 80)
    print("FINISHED GENERATING LATEX")

    source_pdf = osp.join(cwd, "template.pdf")
    print(f"[DEBUG] Checking for generated PDF at: {source_pdf}")
    print(f"[DEBUG] PDF exists: {osp.exists(source_pdf)}")

    if osp.exists(source_pdf):
        pdf_size = osp.getsize(source_pdf)
        print(f"[DEBUG] PDF size: {pdf_size} bytes")

    print(f"[DEBUG] Attempting to move to: {pdf_file}")
    print(f"[DEBUG] Target directory exists: {osp.exists(osp.dirname(pdf_file))}")
    print("=" * 80)

    try:
        if not osp.exists(source_pdf):
            print(f"[ERROR] Source PDF not found: {source_pdf}")
            print(f"[ERROR] Files in latex dir: {os.listdir(cwd)}")
            return False

        # Ensure target directory exists
        target_dir = osp.dirname(pdf_file)
        if not osp.exists(target_dir):
            print(f"[WARNING] Target directory doesn't exist, creating: {target_dir}")
            os.makedirs(target_dir, exist_ok=True)

        shutil.move(source_pdf, pdf_file)
        print(f"[SUCCESS] PDF moved to: {pdf_file}")
        print(f"[SUCCESS] Final PDF exists: {osp.exists(pdf_file)}")
        return True
    except FileNotFoundError as e:
        print(f"[ERROR] Failed to rename PDF: {e}")
        print("EXCEPTION in compile_latex while moving PDF:")
        print(traceback.format_exc())
        return False
    except Exception as e:
        print(f"[ERROR] Unexpected error moving PDF: {e}")
        print(traceback.format_exc())
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
    client: openai.OpenAI | anthropic.Anthropic,
    model: str,
    context: tuple,
    current_round: int,
    total_rounds: int,
    idea_text: str,
) -> str | None:
    report, citations = context
    msg_history: list[dict[str, str]] = []
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

Respond in the following format:

THOUGHT:
<THOUGHT>

RESPONSE:
```json
<JSON>
```

In <THOUGHT>, first briefly reason and identify which citations are missing.
If no more citations are needed, add "No more citations needed" to your thoughts.
Do not add "No more citations needed" if you are adding citations this round.

In <JSON>, respond in JSON format with the following fields:
- "Description": The purpose of the desired citation and a brief description of what you are looking for.
- "Query": The search query to find the paper (e.g., attention is all you need).
This JSON will be automatically parsed, so ensure the format is precise."""

    citation_second_prompt_template = """Search has recovered the following articles:

{papers}

Respond in the following format:

THOUGHT:
<THOUGHT>

RESPONSE:
```json
<JSON>
```

In <THOUGHT>, first briefly reason over the search results and identify which citation(s) best fit your paper.
If none are appropriate or would contribute significantly to the write-up, add "Do not add any" to your thoughts.
Do not select papers that are already in the `references.bib` file, or if the same citation exists under a different name.

In <JSON>, respond in JSON format with the following fields:
- "Selected": A list of integer indices for the selected papers, for example [0, 1]. Do not use quotes for the indices, e.g. "['0', '1']" is invalid.
- "Description": Update the previous description of the citation(s) with the additional context. This should be a brief description of the work(s), their relevance, and where in a paper these should be cited.
This JSON will be automatically parsed, so ensure the format is precise."""

    try:
        text, msg_history = get_response_from_llm(
            prompt=citation_first_prompt_template.format(
                current_round=current_round + 1,
                total_rounds=total_rounds,
                Idea=idea_text,
                report=report,
                citations=citations,
            ),
            client=client,
            model=model,
            system_message=citation_system_msg_template.format(total_rounds=total_rounds),
            temperature=1.0,
            msg_history=msg_history,
            print_debug=False,
        )
        if "No more citations needed" in text:
            print("No more citations needed.")
            return None

        json_output = extract_json_between_markers(text)
        if json_output is None:
            print("Failed to extract JSON from LLM output (initial search). Raw response:")
            print(text)
            return None
        query = json_output["Query"]
        papers = search_for_papers(query)
    except Exception:
        print("EXCEPTION in get_citation_addition (initial search):")
        print(traceback.format_exc())
        return None

    if papers is None:
        print("No papers found.")
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
        text, msg_history = get_response_from_llm(
            prompt=citation_second_prompt_template.format(
                papers=papers_str,
                current_round=current_round + 1,
                total_rounds=total_rounds,
            ),
            client=client,
            model=model,
            system_message=citation_system_msg_template.format(total_rounds=total_rounds),
            temperature=1.0,
            msg_history=msg_history,
            print_debug=False,
        )
        if "Do not add any" in text:
            print("Do not add any.")
            return None

        json_output = extract_json_between_markers(text)
        if json_output is None:
            print("Failed to extract JSON from LLM output (selecting papers). Raw response:")
            print(text)
            return None
        desc = json_output["Description"]
        selected_papers = str(json_output["Selected"])

        if selected_papers != "[]":
            selected_indices = []
            for x in selected_papers.strip("[]").split(","):
                x_str = x.strip().strip('"').strip("'")
                if x_str:
                    selected_indices.append(int(x_str))
            assert all([0 <= i < len(papers) for i in selected_indices]), "Invalid paper index"
            bibtexs = [papers[i]["citationStyles"]["bibtex"] for i in selected_indices]

            cleaned_bibtexs = []
            for bibtex in bibtexs:
                newline_index = bibtex.find("\n")
                cite_key_line = bibtex[:newline_index]
                cite_key_line = remove_accents_and_clean(cite_key_line)
                cleaned_bibtexs.append(cite_key_line + bibtex[newline_index:])
            bibtexs = cleaned_bibtexs

            bibtex_string = "\n".join(bibtexs)
        else:
            return None

    except Exception:
        print("EXCEPTION in get_citation_addition (selecting papers):")
        print(traceback.format_exc())
        return None

    references_format = """% {description}
{bibtex}"""

    references_prompt = references_format.format(bibtex=bibtex_string, description=desc)
    return references_prompt


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

Please provide the updated LaTeX code for 'template.tex', wrapped in triple backticks
with "latex" syntax highlighting, like so:

```latex
<UPDATED LATEX CODE>
```
"""


def perform_writeup(
    base_folder: str,
    no_writing: bool = False,
    num_cite_rounds: int = 20,
    small_model: str = "gpt-4o-2024-05-13",
    big_model: str = "o1-2024-12-17",
    n_writeup_reflections: int = 3,
    page_limit: int = 8,
    citations_text: str | None = None,
    run_dir_name: str | None = None,
) -> bool:
    print("\n" + "=" * 80)
    print("STARTING PERFORM_WRITEUP")
    print(f"[DEBUG] base_folder: {base_folder}")
    print(f"[DEBUG] base_folder exists: {osp.exists(base_folder)}")
    print(f"[DEBUG] base_folder is absolute: {osp.isabs(base_folder)}")
    print(f"[DEBUG] Current working directory: {os.getcwd()}")
    print(f"[DEBUG] big_model: {big_model}")
    print(f"[DEBUG] n_writeup_reflections: {n_writeup_reflections}")
    print(f"[DEBUG] citations_text provided: {citations_text is not None}")
    print("=" * 80 + "\n")

    compile_attempt = 0

    # Cleanup will be set after run output directory is resolved
    # if osp.exists(pdf_file):
    #     os.remove(pdf_file)

    try:
        # Load idea text
        idea_text = ""
        research_idea_path = osp.join(base_folder, "research_idea.md")
        if osp.exists(research_idea_path):
            with open(research_idea_path, "r") as f_idea:
                idea_text = f_idea.read()
        else:
            idea_md_path = osp.join(base_folder, "idea.md")
            if osp.exists(idea_md_path):
                with open(idea_md_path, "r") as f_idea:
                    idea_text = f_idea.read()
            else:
                # Warn if neither research_idea.md nor idea.md exists
                print(
                    f"Warning: Missing idea markdown files. "
                    f"Not found: {research_idea_path} and {idea_md_path}. "
                    "Proceeding with empty idea_text."
                )

        # Load summaries
        logs_dir = osp.join(base_folder, "logs")
        latest_run_dir = "0-run"
        if run_dir_name and osp.exists(osp.join(logs_dir, run_dir_name)):
            latest_run_dir = run_dir_name
        elif osp.exists(logs_dir):
            try:
                latest_run_dir = find_latest_run_dir_name(logs_dir=Path(logs_dir))
            except Exception:
                traceback.print_exc()
                latest_run_dir = "0-run"

        # Set run-specific output directories for latex and PDFs
        run_out_dir = osp.join(logs_dir, latest_run_dir)
        os.makedirs(run_out_dir, exist_ok=True)
        base_pdf_file = osp.join(run_out_dir, "paper")
        latex_folder = osp.join(run_out_dir, "latex")
        print(f"[DEBUG] base_pdf_file (without extension): {base_pdf_file}")
        print(f"[DEBUG] latex_folder: {latex_folder}")
        # Cleanup any previous latex folder
        if osp.exists(latex_folder):
            print(f"[DEBUG] Removing existing latex folder: {latex_folder}")
            shutil.rmtree(latex_folder)

        summary_files = [
            (osp.join("logs", latest_run_dir, "baseline_summary.json"), "BASELINE_SUMMARY"),
            (osp.join("logs", latest_run_dir, "research_summary.json"), "RESEARCH_SUMMARY"),
            (osp.join("logs", latest_run_dir, "ablation_summary.json"), "ABLATION_SUMMARY"),
        ]
        loaded_summaries: dict[str, Any] = {}
        for fname, key in summary_files:
            path = osp.join(base_folder, fname)
            if osp.exists(path):
                try:
                    with open(path, "r") as f:
                        data = json.load(f)
                        if key in {"BASELINE_SUMMARY", "RESEARCH_SUMMARY"}:
                            loaded_summaries[key] = data if isinstance(data, dict) else {}
                        elif key == "ABLATION_SUMMARY":
                            loaded_summaries[key] = data if isinstance(data, list) else []
                        else:
                            loaded_summaries[key] = data
                except json.JSONDecodeError:
                    traceback.print_exc()
                    print(f"Warning: {fname} is not valid JSON. Using empty data for {key}.")
                    loaded_summaries[key] = {} if key != "ABLATION_SUMMARY" else []
            else:
                print(f"Warning: Summary file not found for {key}: {path}")
                loaded_summaries[key] = {} if key != "ABLATION_SUMMARY" else []

        # Convert them to one big JSON string for context
        combined_summaries_str = json.dumps(loaded_summaries, indent=2)

        # Prepare a new fresh latex folder
        if not osp.exists(osp.join(latex_folder, "template.tex")):
            shutil.copytree("ai_scientist/blank_icml_latex", latex_folder, dirs_exist_ok=True)

        writeup_file = osp.join(latex_folder, "template.tex")
        with open(writeup_file, "r") as f:
            writeup_text = f.read()

        # Gather plot filenames from figures/ folder (per-run when provided)
        figures_dir = osp.join(base_folder, "figures", latest_run_dir)
        plot_names = []
        if osp.exists(figures_dir):
            for fplot in os.listdir(figures_dir):
                if fplot.lower().endswith(".png"):
                    plot_names.append(fplot)

        # Seed citations from per-run cache if available
        try:
            cache_base = osp.join(logs_dir, latest_run_dir)
            os.makedirs(cache_base, exist_ok=True)
            citations_cache_path = osp.join(cache_base, "cached_citations.bib")
            progress_path = osp.join(cache_base, "citations_progress.json")
            if osp.exists(citations_cache_path):
                with open(citations_cache_path, "r") as f:
                    cached_citations = f.read()
                print(f"[DEBUG] Loaded cached citations from: {citations_cache_path}")
                try:
                    with open(writeup_file, "r") as f:
                        content = f.read()
                    pattern_end = r"\end{filecontents}"
                    content = content.replace(pattern_end, f"\n{cached_citations}{pattern_end}")
                    with open(writeup_file, "w") as f:
                        f.write(content)
                    print("[DEBUG] Seeded LaTeX references with cached citations.")
                except Exception:
                    print("[WARNING] Failed to seed LaTeX with cached citations.")
                    print(traceback.format_exc())
        except Exception:
            print("[WARNING] Exception while initializing citation cache paths.")
            print(traceback.format_exc())

        # Load aggregator script to include in the prompt
        aggregator_path = osp.join(base_folder, "auto_plot_aggregator.py")
        aggregator_code = ""
        if osp.exists(aggregator_path):
            with open(aggregator_path, "r") as fa:
                aggregator_code = fa.read()
        else:
            aggregator_code = "No aggregator script found."

        if no_writing:
            compile_latex(latex_folder, base_pdf_file + ".pdf")
            return osp.exists(base_pdf_file + ".pdf")

        # Run small model for citation additions
        client, client_model = create_client(small_model)
        for round_idx in range(num_cite_rounds):
            with open(writeup_file, "r") as f:
                writeup_text = f.read()
            try:
                references_bib = re.search(
                    r"\\begin{filecontents}{references.bib}(.*?)\\end{filecontents}",
                    writeup_text,
                    re.DOTALL,
                )
                if references_bib is None:
                    raise ValueError("No references.bib found in template.tex")
                citations_text = references_bib.group(1)
                context_for_citation = (combined_summaries_str, citations_text)

                addition = get_citation_addition(
                    client,
                    client_model,
                    context_for_citation,
                    round_idx,
                    num_cite_rounds,
                    idea_text,
                )
                if addition is None:
                    # Mark citation gathering as done in progress cache
                    try:
                        with open(progress_path, "w") as f:
                            json.dump({"done": True, "round_idx": round_idx}, f, indent=2)
                    except Exception:
                        print("[WARNING] Failed to update citations progress cache on completion.")
                        print(traceback.format_exc())
                    break

                if addition is not None:
                    # Simple check to avoid duplicating the same title
                    title_match = re.search(r" title = {(.*?)}", addition)
                    if title_match:
                        new_title = title_match.group(1).lower()
                        existing_titles = re.findall(r" title = {(.*?)}", citations_text)
                        existing_titles = [t.lower() for t in existing_titles]
                        if new_title not in existing_titles:
                            pattern_end = r"\end{filecontents}"
                            revised = writeup_text.replace(
                                pattern_end, f"\n{addition}{pattern_end}"
                            )
                            with open(writeup_file, "w") as fo:
                                fo.write(revised)
                            # Save updated citations to cache
                            try:
                                with open(writeup_file, "r") as f:
                                    current_text = f.read()
                                current_refs = re.search(
                                    r"\\begin{filecontents}{references.bib}(.*?)\\end{filecontents}",
                                    current_text,
                                    re.DOTALL,
                                )
                                if current_refs:
                                    with open(citations_cache_path, "w") as f:
                                        f.write(current_refs.group(1))
                                with open(progress_path, "w") as f:
                                    json.dump(
                                        {"done": False, "round_idx": round_idx + 1},
                                        f,
                                        indent=2,
                                    )
                            except Exception:
                                print("[WARNING] Failed to update citations cache/progress.")
                                print(traceback.format_exc())
            except Exception:
                print("EXCEPTION in perform_writeup (citation round):")
                print(traceback.format_exc())
                # Save progress and current citations in case of error
                try:
                    with open(writeup_file, "r") as f:
                        current_text = f.read()
                    current_refs = re.search(
                        r"\\begin{filecontents}{references.bib}(.*?)\\end{filecontents}",
                        current_text,
                        re.DOTALL,
                    )
                    if current_refs:
                        with open(citations_cache_path, "w") as f:
                            f.write(current_refs.group(1))
                    with open(progress_path, "w") as f:
                        json.dump({"done": False, "round_idx": round_idx}, f, indent=2)
                except Exception:
                    print("[WARNING] Failed to persist citations after exception.")
                    print(traceback.format_exc())
                continue

        # Generate VLM-based descriptions but do not overwrite plot_names
        try:
            vlm_client, vlm_model = create_vlm_client("gpt-4o-2024-05-13")
            desc_map = {}
            for pf in plot_names:
                ppath = osp.join(figures_dir, pf)
                if not osp.exists(ppath):
                    continue
                img_dict = {
                    "images": [ppath],
                    "caption": "No direct caption",
                }
                review_data = generate_vlm_img_review(img_dict, vlm_model, vlm_client)
                if review_data:
                    desc_map[pf] = review_data.get("Img_description", "No description found")
                else:
                    desc_map[pf] = "No description found"

            # Prepare a string listing all figure descriptions in order
            plot_descriptions_list = []
            for fname in plot_names:
                desc_text = desc_map.get(fname, "No description found")
                plot_descriptions_list.append(f"{fname}: {desc_text}")
            plot_descriptions_str = "\n".join(plot_descriptions_list)
        except Exception:
            print("EXCEPTION in VLM figure description generation:")
            print(traceback.format_exc())
            plot_descriptions_str = "No descriptions available."

        # Construct final prompt for big model, placing the figure descriptions alongside the plot list
        big_model_system_message = writeup_system_message_template.format(page_limit=page_limit)
        big_client, big_client_model = create_client(big_model)
        with open(writeup_file, "r") as f:
            writeup_text = f.read()

        combined_prompt = writeup_prompt.format(
            idea_text=idea_text,
            summaries=combined_summaries_str,
            aggregator_code=aggregator_code,
            plot_list=", ".join(plot_names),
            latex_writeup=writeup_text,
            plot_descriptions=plot_descriptions_str,
        )

        print("\n" + "=" * 80)
        print("[DEBUG] Requesting initial LaTeX generation from LLM...")
        print(f"[DEBUG] Model: {big_client_model}")
        print(f"[DEBUG] Prompt length: {len(combined_prompt)} chars")
        print("=" * 80)

        response, msg_history = get_response_from_llm(
            prompt=combined_prompt,
            client=big_client,
            model=big_client_model,
            system_message=big_model_system_message,
            temperature=1.0,
            print_debug=False,
        )

        print("\n" + "=" * 80)
        print(f"[DEBUG] LLM response received. Length: {len(response)} chars")
        print(f"[DEBUG] First 500 chars of response: {response[:500]}")
        print("=" * 80)

        latex_code_match = re.search(r"```latex(.*?)```", response, re.DOTALL)
        if not latex_code_match:
            print("[ERROR] No LaTeX code block found in LLM response!")
            print(f"[ERROR] Full response (first 2000 chars): {response[:2000]}")
            print("[ERROR] Checking for other code block markers...")
            if "```" in response:
                print(
                    f"[ERROR] Found code blocks but not ```latex. First block: {response[response.find('```'):response.find('```') + 200]}"
                )
            else:
                print("[ERROR] No code blocks found at all in response")
            return False

        print(f"[DEBUG] Found LaTeX code block. Length: {len(latex_code_match.group(1))} chars")
        updated_latex_code = latex_code_match.group(1).strip()
        print(f"[DEBUG] Writing LaTeX to: {writeup_file}")
        with open(writeup_file, "w") as f:
            f.write(updated_latex_code)
        print(f"[SUCCESS] Wrote {len(updated_latex_code)} chars to template.tex")
        # Ensure LaTeX \graphicspath points to the run-specific figures directory
        _ensure_graphicspath(
            writeup_file=writeup_file, latex_folder=latex_folder, figures_dir=figures_dir
        )

        # Multiple reflection loops on the final LaTeX
        for i in range(n_writeup_reflections):
            with open(writeup_file, "r") as f:
                current_latex = f.read()

            # Check for unused or invalid figure references
            referenced_figs_temp = re.findall(
                r"\\includegraphics(?:\[[^\]]*\])?{([^}]+)}", current_latex
            )
            used_figs = set(os.path.basename(fig) for fig in referenced_figs_temp)
            all_figs = set(plot_names)
            unused_figs = all_figs - used_figs
            invalid_figs = used_figs - all_figs

            # Compile current version before reflection
            compile_latex(latex_folder, base_pdf_file + f"_{compile_attempt}.pdf")
            compile_attempt += 1
            print(f"Compiled {base_pdf_file}_{compile_attempt}.pdf")

            # Detect where "Impact Statement" appears
            impact_loc = detect_pages_before_impact(latex_folder)
            if impact_loc is not None:
                page_num, line_num = impact_loc
                reflection_page_info = (
                    f"\nCurrently, 'Impact Statement' begins on page {page_num}, approximately on line {line_num}. "
                    f"The page limit is {page_limit}, which is before the Impact Statement. "
                    f"Papers often look more professional if the main text is near or just under {page_limit} pages in length.\n"
                )
            else:
                reflection_page_info = "\nCould not detect 'Impact Statement' page (compilation or detection failed).\n"

            check_output = os.popen(f"chktex {writeup_file} -q -n2 -n24 -n13 -n1").read()

            reflection_prompt = f"""
Now let's reflect and identify any issues (including but not limited to):
1) Are there any LaTeX syntax errors or style violations we can fix? Refer to the chktex output below.
2) Is the writing clear, and scientifically rigorous?
3) Have we included all relevant details from the summaries without hallucinating?
4) The following figures are available in the folder but not used in the LaTeX: {sorted(unused_figs)}
5) The following figure references in the LaTeX do not match any actual file: {sorted(invalid_figs)}
{reflection_page_info}
chktex results:
```
{check_output}
```

Please provide a revised complete LaTeX in triple backticks, or repeat the same if no changes are needed.
Return the entire file in full, with no unfilled placeholders!
This must be an acceptable complete LaTeX writeup.
Do not hallucinate any details!

If you believe you are done, simply say: "I am done".
"""

            reflection_response, msg_history = get_response_from_llm(
                prompt=reflection_prompt,
                client=big_client,
                model=big_client_model,
                system_message=big_model_system_message,
                temperature=1.0,
                msg_history=msg_history,
                print_debug=False,
            )

            if "I am done" in reflection_response:
                print("LLM indicated it is done with reflections. Exiting reflection loop.")
                break

            reflection_code_match = re.search(r"```latex(.*?)```", reflection_response, re.DOTALL)
            if reflection_code_match:
                reflected_latex_code = reflection_code_match.group(1).strip()
                if reflected_latex_code != current_latex:
                    final_text = reflected_latex_code
                    cleanup_map = {
                        "</end": r"\\end",
                        "</begin": r"\\begin",
                        "’": "'",
                    }
                    for bad_str, repl_str in cleanup_map.items():
                        final_text = final_text.replace(bad_str, repl_str)
                    final_text = re.sub(r"(\d+(?:\.\d+)?)%", r"\1\\%", final_text)

                    with open(writeup_file, "w") as fo:
                        fo.write(final_text)

                    # Ensure LaTeX \graphicspath stays correct after edits
                    _ensure_graphicspath(
                        writeup_file=writeup_file,
                        latex_folder=latex_folder,
                        figures_dir=figures_dir,
                    )
                    compile_latex(latex_folder, base_pdf_file + f"_{compile_attempt}.pdf")
                    compile_attempt += 1
                    print(f"Compiled {base_pdf_file}_{compile_attempt}.pdf")
                else:
                    print(f"No changes in reflection step {i + 1}.")
                    break
            else:
                print(f"No valid LaTeX code block found in reflection step {i + 1}.")
                break

        return osp.exists(base_pdf_file + f"_{compile_attempt - 1}.pdf")

    except Exception:
        print("EXCEPTION in perform_writeup:")
        print(traceback.format_exc())
        return False


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Perform writeup for a project")
    parser.add_argument("--folder", type=str, help="Project folder", required=True)
    parser.add_argument("--no-writing", action="store_true", help="Only generate")
    parser.add_argument("--num-cite-rounds", type=int, default=20)
    parser.add_argument(
        "--model",
        type=str,
        default="bedrock/anthropic.claude-3-5-sonnet-20240620-v1:0",
        choices=AVAILABLE_LLMS,
        help="Model to use for citation collection (small model).",
    )
    parser.add_argument(
        "--big-model",
        type=str,
        default="o1-2024-12-17",
        choices=AVAILABLE_LLMS,
        help="Model to use for final writeup (big model).",
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
    args = parser.parse_args()

    try:
        success = perform_writeup(
            base_folder=args.folder,
            no_writing=args.no_writing,
            num_cite_rounds=args.num_cite_rounds,
            small_model=args.model,
            big_model=args.big_model,
            n_writeup_reflections=args.writeup_reflections,
            page_limit=args.page_limit,
        )
        if not success:
            print("Writeup process did not complete successfully.")
    except Exception:
        print("EXCEPTION in main:")
        print(traceback.format_exc())
