from aigraph.utils import DATA_DIR, Task

RESEARCH_METHODOLOGY_GUIDELINES = """
## Research Methodology Guidelines

Follow these principles for rigorous, reproducible research:

### Hypotheses & Design
- State precise primary/secondary hypotheses with clear success criteria
- Pre-register design: lock protocols, metrics, endpoints, exclusion rules
- Distinguish confirmatory vs exploratory analyses upfront

### Baselines & Controls
- Validate instruments/protocols; confirm measurement reliability first
- Include negative/positive controls; match groups to remove confounds
- Establish calibrated baselines before any intervention

### Metrics & Power
- Use bounded, interpretable metrics with clear units
- Report absolutes and differences; avoid unstable ratios
- Justify sample sizes; estimate variability and detectable effects

### Statistical Rigor
- Report effect sizes with confidence/credible intervals
- Use robust estimators; adjust for multiple testing
- Bootstrap/permutation when distributional assumptions are weak

### Validation & Robustness
- Replicate across runs/seeds/datasets; quantify between-run variance
- Perform sensitivity and ablation analyses on key parameters
- Avoid ceiling/floor artifacts; use difficulty sweeps

### Reproducibility
- Share data/code/configs/logs; fix random seeds
- Version datasets/models/analyses with immutable IDs
- Document exact environments/versions/dependencies

### Reporting Standards
- Visualize distributions (ECDFs/histograms), not just means
- Document negative and null results with plausible causes
- Methods sufficient for independent re-run
- Test out-of-sample for generalization; state scope and limits
"""


def _task_to_prompt(task: Task) -> str:
    prompt = f"""
    You are an ambitious AI researcher who is looking to publish a paper that
    will contribute significantly to the field.

    You have an idea and you want to conduct creative experiments to gain
    scientific insights.

    Your aim is to run experiments to gather sufficient results for a top
    conference paper.

    {RESEARCH_METHODOLOGY_GUIDELINES}

    ## Your Research Idea

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

    if task.code:
        code = f"<CODE>\n{task.code}\n</CODE>"
        return prompt + f"Code To Use:\n{code}\n"

    example = DATA_DIR / "code.py.txt"
    if not example.exists():
        return prompt

    code = example.read_text()
    code = f"<CODE>\n{code}\n</CODE>"
    return prompt + f"Code To Use:\n{code}\n"
