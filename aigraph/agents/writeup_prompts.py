from typing import Iterable

from aigraph import utils
from aigraph.utils import Idea


def _task_to_prompt(task: utils.Task) -> str:
    return f"""
    You are an ambitious AI researcher who is looking to publish a paper that
    will contribute significantly to the field.

    You have an idea and you want to conduct creative experiments to gain
    scientific insights.

    Your aim is to run experiments to gather sufficient results for a top
    conference paper.

    Your research idea:

    Name:
    {task.name}

    Title:
    {task.title}

    Abstract:
    {task.abstract}

    Hypothesis:
    {task.short_hypothesis}

    Related Work:
    {task.related_work}

    Experiments:
    {"\n".join(f"- {exp}" for exp in task.experiments)}

    Risk Factors and Limitations:
    {"\n".join(f"- {risk}" for risk in task.risk_factors_and_limitations)}
    """


def build_writeup_system_message(
    task: utils.Task, pages: int = 5, idea: Idea | None = None
) -> str:
    template = utils.DATA_DIR / "template.tex"

    idea_section = ""
    if idea:
        idea_section = f"""
    ## Idea Context

    <IDEA>
    Name: {idea.name}
    Description: {idea.description}
    Plan: {idea.plan}
    Goals:
    {chr(10).join(f"- {goal}" for goal in idea.goals)}
    </IDEA>
"""

    return f"""
    You are an ambitious AI researcher who is looking to publish a paper that
    will contribute significantly to the field. Ensure that the paper is
    scientifically accurate, objective, and truthful. Accurately report the
    experimental results, even if they are negative or inconclusive.
    
    You are planning to submit to a top-tier ML conference, which has
    guidelines:

    - The main paper is limited to {pages} pages, including all figures and
      tables, but excluding references, the impact statement, and optional
      appendices. In general, try to use the available space and include all
      relevant information.
    - The main paper should be double-column format, while the appendices can be
      in single-column format. When in double column format, make sure that
      tables and figures are correctly placed.
    - Do not change the overall style which is mandated by the conference. Keep
      to the current method of including the references.bib file.
    - Do not remove the \\graphicspath directive or no figures will be found.

    Here are some tips for each section of the paper:

    ## Paper

    ### Title

    - Title should be catchy and informative. It should give a good idea of what
      the paper is about.
    - Try to keep it under 2 lines.

    ### Abstract

    - TL;DR of the paper.
    - What are we trying to do and why is it relevant?
    - Make sure the abstract reads smoothly and is well-motivated. This should
      be one continuous paragraph.

    ### Introduction

    - Longer version of the Abstract, i.e., an overview of the entire paper.
    - Provide context to the study and explain its relevance.
    - If results are inconclusive or negative, present them frankly; if they are
      positive, you may highlight how the approach effectively addresses the
      research question or problem.
    - Summarize your contributions, highlighting pertinent findings, insights,
      or proposed methods.

    ### Related Work

    - Academic siblings of our work, i.e., alternative attempts in literature at
      trying to address the same or similar problems.
    - Compare and contrast their approach with yours, noting key differences or
      similarities.
    - Ensure proper citations are provided.

    ### Background

    - Present foundational concepts or prior work needed to understand your
      method.
    - This should include necessary definitions, the problem setting, or
      relevant theoretical constructs.

    ### Method

    - Clearly detail what you propose to do and why. If your study aims to
      address certain hypotheses, describe them and how your method is
      constructed to test them.
    - If results are negative or inconclusive, you may suggest improvements or
      discuss possible causes.

    ### Experimental Setup

    - Explain how you tested your method or hypothesis.
    - Describe necessary details such as data, environment, and baselines, but
      omit hardware details unless explicitly mentioned.

    ### Experiments

    - Present the results truthfully according to the data you have. If outcomes
      are not as expected, discuss it transparently.
    - Include comparisons to baselines if available, and only include analyses
      supported by genuine data.
    - Try to include all relevant plots and tables. Consider combining multiple
      plots into one figure if they are related.

    ### Conclusion

    - Summarize the entire paper, including key strengths or findings.
    - If results are strong, highlight how they might address the research
      problem.
    - If results are negative or inconclusive, highlight potential improvements
      or reasons and propose future directions.

    ### Appendix

    - Place for supplementary material that did not fit in the main paper.

    ## Output

    When returning final code, return ONLY the raw LaTeX code without fenced
    code blocks or triple backticks.
{idea_section}
    ## Research idea

    <RESEARCH_IDEA>
    {_task_to_prompt(task)}
    </RESEARCH_IDEA>

    ## Latex template

    Update the following LaTeX template to reflect the research idea:

    <TEMPLATE>
    {template.read_text()}
    </TEMPLATE>
    """


def build_writeup_prompt(
    code_experiment: str,
    code_parser: str,
    parser_stdout: str | None,
    plots: Iterable[utils.Plot],
    research: str | None = None,
    memory: str = "",
    idea: Idea | None = None,
) -> str:
    idea_section = ""
    if idea:
        idea_section = f"""
    ## Idea Context

    <IDEA>
    Name: {idea.name}
    Description: {idea.description}
    Plan: {idea.plan}
    Goals:
    {chr(10).join(f"- {goal}" for goal in idea.goals)}
    </IDEA>
"""

    return f"""
    ## Introduction

    You are an AI researcher writing a paper for a top-tier ML conference. Your
    task is to write a LaTeX document that summarizes the research you have
    conducted.
{idea_section}
    ## Experiment code

    <EXPERIMENT_CODE>
    {code_experiment}
    </EXPERIMENT_CODE>

    ## Parser code

    <PARSER_CODE>
    {code_parser}
    </PARSER_CODE>

    ## Parser output

    <PARSER_OUTPUT>
    {parser_stdout or "NA"}
    </PARSER_OUTPUT>

    ## Research output

    <RESEARCH_OUTPUT>
    {research or "NA"}
    </RESEARCH_OUTPUT>

    ## Images

    <IMAGES>
    {"\n".join(f"- {p.path.name}: {p.analysis}" for p in plots)}
    </IMAGES>

    ## Memory (Previous Attempts)

    <MEMORY>
    {memory or "NA"}
    </MEMORY>
    """


def build_prompt_compile_output(
    latex: str, stdout: str, stderr: str, idea: Idea | None = None
) -> str:
    idea_section = ""
    if idea:
        idea_section = f"""
    ## Idea Context

    <IDEA>
    Name: {idea.name}
    Description: {idea.description}
    Plan: {idea.plan}
    Goals:
    {chr(10).join(f"- {goal}" for goal in idea.goals)}
    </IDEA>
"""

    return f"""
    Review LaTeX compilation output and identify compilation bugs.
    
    Determine if compilation succeeded or failed.

    Common LaTeX errors:

    - Undefined control sequences
    - Missing $ errors
    - Unmatched braces
    - Missing figures/files
    - Bibliography errors
    - Label/reference issues
    
    Set is_bug=True if compilation failed.
    Provide concise summary of issue.
{idea_section}
    ## LaTeX Code

    <LATEX>
    {latex}
    </LATEX>
    
    ## Stdout
    
    <STDOUT>
    {stdout}
    </STDOUT>
    
    ## Stderr
    
    <STDERR>
    {stderr}
    </STDERR>
    """
