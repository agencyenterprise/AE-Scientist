from aigraph.agents.research_prompts import _task_to_prompt
from aigraph.utils import Task


def build_prompt_generate_ideas(task: Task, num_ideas: int) -> str:
    return f"""
    ## Introduction

    You are an AI researcher tasked with generating creative and impactful
    research ideas that meet high standards of scientific rigor.

    ## Task Description

    {_task_to_prompt(task)}

    ## Instructions

    Generate {num_ideas} research ideas based on the task description above.

    ### Quality Criteria

    Each idea must be:

    - **Novel**: Distinct from prior work; clear contribution beyond baselines
    - **Testable**: Precise hypotheses with measurable success criteria
    - **Rigorous**: Proper controls, statistical power, reproducibility plan
    - **Bounded**: Realistic scope; defined failure modes and limitations
    - **Publishable**: Sufficient for a top-tier venue

    ### Required Components

    For each idea, provide:

    - **Name**: Short, descriptive identifier
    - **Title**: Full research paper title
    - **Abstract**: 2-3 paragraphs covering motivation, method, expected contribution
    - **Short Hypothesis**: Precise, falsifiable statement with success metric
    - **Related Work**: Key prior work and how this differs
    - **Experiments** (3-5 items):
      - Include baseline comparisons and ablation studies
      - Specify metrics with units and interpretability
      - Plan for multiple runs/seeds to quantify variance
      - Include at least one robustness/sensitivity check
    - **Risk Factors and Limitations** (2-4 items):
      - Potential failure modes and mitigation strategies
      - Ceiling/floor effects and how to detect them
      - Generalization limits and out-of-distribution concerns
    - **Code**: Optional starting code (can be null)

    ### Anti-Patterns to Avoid

    - Vague hypotheses without clear success/failure criteria
    - Missing baselines or controls
    - Single-run results without variance estimates
    - Cherry-picked metrics or selective reporting
    - Ceiling/floor effects that hide true signal

    Format your response as a list of research ideas, each following the Task
    schema structure.
    """
