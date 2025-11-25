from aigraph.utils import DATA_DIR, Task


def _task_to_prompt(task: Task) -> str:
    prompt = f"""
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

    if task.code:
        code = f"```python\n{task.code}\n```"
        return prompt + f"Code To Use:\n{code}\n"

    example = DATA_DIR / "code.py.txt"
    if not example.exists():
        return prompt

    code = example.read_text()
    code = f"```python\n{code}\n```"
    return prompt + f"Code To Use:\n{code}\n"


def build_prompt_propose_ablation(code: str, ablations: list[str]) -> str:
    attempted = ablations or ["Nothing has been tried yet."]

    return f"""
    You are an AI researcher conducting ablation studies. Based on the current
    implementation and previous ablations (if any), propose ONE new ablation
    study that tests a different aspect of the model.

    ## Base code you are working on

    <CODE>
    ```python
    {code}
    ```
    </CODE>

    ## Previous Ablations

    <PREVIOUS_ABLATIONS>
    {"\n".join(f"- {i}" for i in attempted)}
    </PREVIOUS_ABLATIONS>

    ## Requirements

    1. Identify ONE specific component/feature to ablate
    2. Ensure the ablation is different from previous completed or running
       attempts
    3. The ablation should be a new idea, not a variation of previous ideas
    4. If you have only used a single synthetic dataset throughout the
       experiment, one of your ablations should be to use multiple synthetic
       datasets (at least 3 different datasets)

    ## Response format

    Your response should start with 'ABLATION NAME: <ablation name>' on the
    first line to represent the name of the ablation. The second line should
    start with 'ABLATION DESCRIPTION: <description>', a brief description of
    what component is being ablated and why (3-5 sentences).
    """


def build_prompt_code_ablation(
    name: str, description: str, code: str, memory: str
) -> str:
    return f"""
    You are an experienced AI researcher. You are provided with a previously
    developed baseline implementation. Your task is to implement the ablation
    study for the following idea:
    
    Name: {name}
    Description: {description}

    ## Base code you are working on
    
    ```python
    {code}
    ```
    
    ## Instructions
    
    ### Response format

    Your response should use structured json outputs in the following format:

    - plan: A brief outline/sketch of your proposed solution in natural language
      (7-10 sentences)
    - code: A python script in plain python. DO NOT USE FENCES. EG:
      \\`\\`\\`python ... \\`\\`\\`
    - dependencies: A list of dependencies required for the code to run. EG:
      ["torch", "torchvision", "numpy", "pandas", "scikit-learn"]. NEVER
      include Python standard library dependencies (e.g., json, os, sys, pathlib).
      ALWAYS only include third-party packages.

    ### Ablation study guidelines

    - Implement the ablation study idea described above.
    - The code should be a single-file python program that is self-contained and
      can be executed as-is.
    - No parts of the code should be skipped, don't terminate the code execution
      before finishing the script.
    - You MUST evaluate your solution on at least 3 different datasets to ensure
      robustness. Use standard benchmark datasets when available (e.g., MNIST,
      CIFAR-10, ImageNet, GLUE, SQuAD, etc.). Each dataset should be evaluated
      separately and results should be tracked per dataset in the experiment_data
      structure.

    ### Implementation guidelines

    - The code should be a single-file python program that is self-contained and
      can be executed as-is.
    - No parts of the code should be skipped, don't terminate the code execution
      before finishing the script.
    
    Data saving requirements:

    - Save all data (metrics, losses, predictions, etc.) as JSON following
      the following structure:
      ```python
      # At the start of your code
      experiment_data = {{
          'ablation_type_1': {{
              'dataset_name_1': {{
                  'metrics': {{'train': [], 'val': []}},
                  'losses': {{'train': [], 'val': []}},
                  'predictions': [],
                  'ground_truth': [],
              }},
          }},
      }}
      ```
    - Make sure to use a filename 'data_ablation.json' to save the data. Do not
      use any other filename.

    ## Memory

    <MEMORY>
    {memory or "NA"}
    </MEMORY>
    """


def build_prompt_ablation_output(
    task: Task, code: str, stdout: str, stderr: str
) -> str:
    return f"""
    ## Introduction
    
    You are an experienced AI researcher. You have written code for your
    ablation experiment and now need to evaluate the output of the code
    execution. Analyze the execution output, determine if there were any bugs,
    and provide a summary of the findings.

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


def build_prompt_ablation_parser_code(code: str, memory: str = "") -> str:
    return f"""
    ## Introduction
    
    You are an AI researcher analyzing experimental results stored in a JSON
    file. Write code to load and analyze the metrics from
    `data_ablation.json` generated by an ablation study experiment.
    
    ## Context
    
    Original Ablation Code:
    
    ```python
    {code}
    ```
    
    ## Instructions
    
    1. Load the `data_ablation.json` file, which is located in the current
       directory
    2. Extract metrics for the ablation run and dataset. Refer to the original
       code to understand the data structure.
    3. Always print the name of the ablation type and dataset before printing
       the metrics
    4. Always print the name of the metric before printing the value with
       precise labels (e.g., 'train accuracy', 'validation loss', 'test F1
       score').
    5. Only print the best or final value for each metric for each dataset
    6. DO NOT CREATE ANY PLOTS
    
    Important code structure requirements:

    - Do NOT put any execution code inside `if __name__ == "__main__":`
    - All code should be at the global scope or in functions that are called
      from the global scope
    - The script should execute immediately when run, without requiring any
      special entry point
    
    ## Example data loading code
    
    ```python
    import json
    import os
    with open(os.path.join(os.getcwd(), 'data_ablation.json')) as f:
        experiment_data = json.load(f)
    ```
    
    ## Response format
    
    Your response should use structured json outputs in the following format:

    - plan: A brief outline/sketch of your proposed solution in natural language
      (7-10 sentences)
    - code: A python script in plain python. DO NOT USE FENCES. EG:
      \\`\\`\\`python ... \\`\\`\\`
    - dependencies: A list of dependencies required for the code to run. EG:
      ["torch", "torchvision", "numpy", "pandas", "scikit-learn"]. NEVER
      include Python standard library dependencies (e.g., json, os, sys, pathlib).
      ALWAYS only include third-party packages.

    ## Memory

    <MEMORY>
    {memory or "NA"}
    </MEMORY>
    """


def build_prompt_ablation_parser_output(code: str, stdout: str, stderr: str) -> str:
    return f"""
    ## Introduction

    You are an experienced AI researcher. You have written code to parse and
    analyze the results of your ablation experiment. Now you need to evaluate
    the output of the parser execution. Analyze the execution output, determine
    if there were any bugs, and provide a summary of the findings.

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
