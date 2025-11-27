from aigraph import utils


def build_prompt_evaluate(
    idea: utils.Idea,
    code: str,
    code_stdout: str,
    parser_stdout: str,
    latex: str | None,
    notes: list[str],
) -> str:
    return f"""
    ## Introduction

    You are a senior AI researcher evaluating experiment quality.
    Determine if this experiment is publishable or needs refinement.

    ## Idea

    <IDEA>
    Name: {idea.name}
    Description: {idea.description}
    Plan: {idea.plan}
    Goals:
    {"\n".join(f"- {goal}" for goal in idea.goals)}
    </IDEA>

    ## Experiment Code

    <CODE>
    {code}
    </CODE>

    ## Execution Output

    <STDOUT>
    {code_stdout}
    </STDOUT>

    ## Metrics

    <METRICS>
    {parser_stdout}
    </METRICS>

    ## Writeup

    <LATEX>
    {latex}
    </LATEX>

    ## Accumulated Notes

    <NOTES>
    {"\n".join(f"{i} - {note}" for i, note in enumerate(notes, 1)) or "No notes."}
    </NOTES>

    ## Evaluation Criteria

    1. Code executes without critical errors
    2. Results are meaningful (not NaN, not trivial)
    3. Experiment addresses the research goals
    4. Sufficient data for a paper

    ## Instructions

    Respond with:
    - passed: true if experiment is acceptable, false otherwise
    - reasoning: Brief explanation of decision (2-3 sentences)
    - summary: Summary of experiment quality and findings
    """
