
import json
from aigraph.utils import ROOT_DIR, Task


def _task_to_prompt(task: Task) -> str:
    prompt = f"""
    You are an ambitious AI researcher who is looking to publish a paper that
    will contribute significantly to the field.

    You have an idea and you want to conduct creative experiments to gain
    scientific insights.

    Your aim is to run experiments to gather sufficient results for a top
    conference paper.

    Your research idea:

    Title:
    {task.title}

    Abstract:
    {task.abstract}

    Hypothesis:
    {task.short_hypothesis}

    """

    if task.code:
        code = f'```python\n{task.code}\n```'
        return prompt + f"Code To Use:\n{code}\n"

    example = ROOT_DIR / "example.py"
    if not example.exists():
        return prompt

    code = example.read_text()
    code = f'```python\n{code}\n```'
    return prompt + f"Code To Use:\n{code}\n"


def build_prompt_plotting_code(task: Task, code: str, memory: str = "") -> str:
    return f"""
    ## Introduction

    You are an AI researcher. You have run an experiment and generated results
    in `experiment_data.json`. Your task is to write a Python script to
    visualize these results using matplotlib or seaborn.

    ## Instructions

    - Write a Python script to load `experiment_data.json` and generate plots.
    - The `experiment_data.json` file has the following structure:

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
    - Save all plots as .png or .pdf files in the current working directory.
    - Do NOT use `plt.show()`.
    - Handle potential missing keys gracefully.

    ### Response format

    Your response should use structured json outputs in the following format:

    - plan: A brief outline/sketch of your proposed solution in natural language
      (7-10 sentences)
    - code: A python script in plain python. DO NOT USE FENCES. EG:
      \\`\\`\\`python ... \\`\\`\\`
    - dependencies: A list of dependencies required for the code to run. EG:
      ["matplotlib", "seaborn", "numpy", "pandas"]. Do not include standard
      library dependencies.

    ### Coding Guidelines

    - Import necessary libraries (matplotlib.pyplot, json, os, etc.).
    - Load data: `with open('experiment_data.json', 'r') as f: data =
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
    ```python
    {code}
    ```
    </CODE>

    ## Memory (Previous Attempts)

    <MEMORY>
    {memory or "NA"}
    </MEMORY>
    """


def build_prompt_plotting_output(task: Task, code: str, stdout: str, stderr: str) -> str:
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

    ## Research idea

    <RESEARCH_IDEA>
    {_task_to_prompt(task)}
    </RESEARCH_IDEA>

    ## Implementation

    <IMPLEMENTATION>
    ```python
    {code}
    ```
    </IMPLEMENTATION>

    ## Stdout

    <STDOUT>
    ```
    {stdout}
    ```
    </STDOUT>

    ## Stderr

    <STDERR>
    ```
    {stderr}
    ```
    </STDERR>
    """


def build_prompt_analyze_plots(task: Task) -> str:
    return f"""
    ## Introduction

    You are an AI researcher. You have generated plots from your experiment
    results. Your task is to analyze these plots to interpret the scientific
    findings.

    ## Research idea

    <RESEARCH_IDEA>
    {_task_to_prompt(task)}
    </RESEARCH_IDEA>

    ## Instructions

    - Analyze the provided plot images.
    - Describe the trends you observe (e.g., convergence, overfitting,
      performance comparison).
    - Relate the findings back to the hypothesis.
    - Conclude if the hypothesis is supported or rejected.
    """
