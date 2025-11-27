from aigraph.utils import Idea, Task


def _task_to_prompt(task: Task) -> str:
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


def build_prompt_plotting_code(
    task: Task,
    code: str,
    memory: str = "",
    idea: Idea | None = None,
    research: str | None = None,
) -> str:
    idea_section = ""
    research_section = ""

    if idea:
        idea_section = f"""
    ## Idea Context

    <IDEA>
    Name: {idea.name}
    Description: {idea.description}
    Plan: {idea.plan}
    Goals:
    {"\n".join(f"- {goal}" for goal in idea.goals)}
    </IDEA>
"""

    if research:
        research_section = f"""
    ## Research Background

    <RESEARCH>
    {research}
    </RESEARCH>
"""

    return f"""
    ## Introduction

    You are an AI researcher. You have run an experiment and generated results
    in `data_ablation.json`. Your task is to write a Python script to
    visualize these results using matplotlib or seaborn.
{idea_section}{research_section}
    ## Instructions

    - Write a Python script to load `data_ablation.json` and generate plots.
    - The `data_ablation.json` file has the following structure:

    ```json
    {{
        "dataset_name_1": {{
            "metrics": {{ "train": [], "val": [] }},
            "losses": {{ "train": [], "val": [] }},
            "predictions": [],
            "ground_truth": [],
        }},
        "dataset_name_2": {{
            "metrics": {{ "train": [], "val": [] }},
            "losses": {{ "train": [], "val": [] }},
            "predictions": [],
            "ground_truth": [],
        }}
    }}
    ```

    - Create standard visualizations (learning curves, sample comparisons,
      etc.).
    - Save all plots as .png or .pdf files in the current directory.
    - Do NOT use `plt.show()`.
    - Handle potential missing keys gracefully.

    ### Response format

    Your response should use structured json outputs in the following format:

    - plan: A brief outline/sketch of your proposed solution in natural language
      (7-10 sentences)
    - code: A python script in plain python. DO NOT USE FENCES. EG:
      \\`\\`\\`python ... \\`\\`\\`
    - dependencies: A list of dependencies required for the code to run. EG:
      ["matplotlib", "seaborn", "numpy", "pandas"]. NEVER include Python
      standard library dependencies (e.g., json, os, sys, pathlib). ALWAYS only
      include third-party packages.

    ### Coding Guidelines

    - Import necessary libraries (matplotlib.pyplot, json, os, etc.).
    - Load data: `with open('data_ablation.json', 'r') as f: data =
      json.load(f)`
    - Iterate through datasets/metrics in the JSON to create relevant plots.
    - Save figures with descriptive names, e.g., `loss_curves.png`,
      `predictions_vs_truth.png`.
    - Always close figures: `plt.close()`.
    - Use try/except blocks for robustness if unsure about data shape.

    ## Research idea

    <RESEARCH_IDEA>
    {_task_to_prompt(task)}
    </RESEARCH_IDEA>

    ## Experiment Code

    This is the code that generated the data:
    
    <CODE>
    {code}
    </CODE>

    ## Memory (Previous Attempts)

    <MEMORY>
    {memory or "NA"}
    </MEMORY>
    """


def build_prompt_plotting_output(
    task: Task, code: str, stdout: str, stderr: str, idea: Idea | None = None
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
    {"\n".join(f"- {goal}" for goal in idea.goals)}
    </IDEA>
"""

    return f"""
    ## Introduction

    You are an AI researcher. You have executed a plotting script to visualize
    experiment results. Analyze the execution output to determine if the
    plotting was successful or if there were bugs.

    ## Instructions

    - Check if the code executed without crashing (return code 0 is not enough,
      look for python tracebacks).
    - Check if the expected plot files seem to have been generated (based on
      logs if any).
    - If there are errors, summarize them.
    - If successful, confirm that plots were generated.
{idea_section}
    ## Research idea

    <RESEARCH_IDEA>
    {_task_to_prompt(task)}
    </RESEARCH_IDEA>

    ## Implementation

    <IMPLEMENTATION>
    {code}
    </IMPLEMENTATION>

    ## Stdout

    <STDOUT>
    {stdout}
    </STDOUT>

    ## Stderr

    <STDERR>
    {stderr}
    </STDERR>
    """


def build_prompt_analyze_plots(task: Task, idea: Idea) -> str:
    return f"""
    ## Introduction

    You are an AI researcher. You have generated plots from your experiment
    results. Your task is to analyze these plots to interpret the scientific
    findings.
    ## Research idea

    <RESEARCH_IDEA>
    {_task_to_prompt(task)}
    </RESEARCH_IDEA>

    <IDEA>
    Name: {idea.name}
    Description: {idea.description}
    Plan: {idea.plan}
    Goals:
    {"\n".join(f"- {goal}" for goal in idea.goals)}
    </IDEA>

    ## Instructions

    - Analyze the provided plot images.
    - Describe the trends you observe (e.g., convergence, overfitting,
      performance comparison).
    - Relate the findings back to the hypothesis.
    - Conclude if the hypothesis is supported or rejected.
    """
