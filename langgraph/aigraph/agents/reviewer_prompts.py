from aigraph import utils
from aigraph.agents import experiment


def _format_experiment(idx: int, exp: experiment.State) -> str:
    """Format a single experiment for the prompt."""
    ablation = exp.state_ablation
    research = exp.state_research

    return f"""
    Experiment id:

    <ID>
    {exp.id}
    </ID>

    ## Idea

    <IDEA>
    Name: {exp.idea.name}
    Description: {exp.idea.description}
    Plan: {exp.idea.plan}
    Goals:
    {"\n".join(f"- {goal}" for goal in exp.idea.goals)}
    </IDEA>

    ## Research

    <RESEARCH>
    {research.research.get("final_report") if research and research.research else "No research available"}
    </RESEARCH>

    <NOTES>
    {"\n".join(f"{i} - {note}" for i, note in enumerate(exp.notes, 1)) if exp.notes else "No notes"}
    </NOTES>

    ## Code

    <CODE>
    {ablation.ablation_code if ablation else "No code available"}
    </CODE>

    ## Code output

    <OUTPUT>
    {ablation.ablation_stdout if ablation else "No output available"}
    </output>

    ## Parsed metrics

    <METRICS>
    {ablation.parser_stdout if ablation else "No metrics available"}
    </METRICS>
    """


def build_prompt_review(
    task: utils.Task,
    experiments: list[experiment.State],
) -> str:
    """Build the prompt for reviewing and triaging experiments."""

    experiments_text = ""
    for i, exp in enumerate(experiments):
        experiments_text += _format_experiment(i, exp)
        experiments_text += "\n\n--------------------------------\n\n"

    return f"""
    You are reviewing multiple research experiments to decide which ones are
    complete, which should be retried with improvements, and which should be
    dropped.

    ## Your Task

    For each experiment, decide:
    - **done**: Experiment succeeded, results are valid and useful
    - **retry**: Experiment has potential but failed or can be improved. Provide a retry package.
    - **drop**: Experiment is fundamentally flawed or redundant with a better one

    ## Guidelines for Decisions

    ### Mark as DONE if:
    - The judge review passed
    - Results are meaningful and support/refute the hypothesis
    - Code executed successfully with valid output

    ### Mark as RETRY if:
    - Partial success but results incomplete
    - Bug or error that seems fixable with new approach
    - Good idea but poor implementation
    - Could benefit from insights learned from other experiments

    ### Mark as DROP if:
    - Fundamentally flawed approach
    - Redundant with another experiment that succeeded
    - Too similar to another retry (avoid duplicate work)
    - Cannot be salvaged

    ## For RETRY decisions, provide:

    1. **new_idea**: Reformulated hypothesis based on learnings
    2. **new_research**: Updated research context (include what was learned)
    3. **new_notes**: Specific guidance for the retry:
    - What worked in other experiments
    - What to avoid (approaches that failed)
    - Specific suggestions for improvement
    4. **avoid_approaches**: List of approaches already tried that failed

    ## Cross-Experiment Analysis

    Look across ALL experiments to:
    - Identify patterns in what works vs what doesn't
    - Share successful techniques with retries
    - Avoid redundant retries (don't retry two similar ideas)
    - Drop experiments that are superseded by better ones

    ## Output Format

    3 lists:

    - done: list of experiments that are complete
    - retry: list of experiments that should be retried
    - drop: list of experiments that should be dropped

    Each item in the lists should be a Reviewed object with the following fields:

    - id: the index of the experiment
    - reasoning: a brief explanation of the decision

    ## Context

    <TASK>
    Title: {task.title}
    Hypothesis: {task.short_hypothesis}
    Abstract: {task.abstract}
    </TASK>

    <EXPERIMENTS>
    {experiments_text}
    </EXPERIMENTS>
    """
