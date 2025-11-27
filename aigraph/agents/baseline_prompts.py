import json
from typing import TYPE_CHECKING, Iterable

from aigraph.agents.research_prompts import _task_to_prompt
from aigraph.utils import Idea, Metric, Task

if TYPE_CHECKING:
    from aigraph.agents.baseline import State


def build_prompt_baseline_metrics(task: Task, idea: Idea, research: str) -> str:
    return f"""
    ## Introduction

    You are an AI researcher setting up experiments. Please propose meaningful
    evaluation metrics that will help analyze the performance and
    characteristics of solutions for this research task.

    ## Idea Context

    <IDEA>
    Name: {idea.name}
    Description: {idea.description}
    Plan: {idea.plan}
    Goals:
    {"\n".join(f"- {goal}" for goal in idea.goals)}
    </IDEA>

    ## Research Background

    <RESEARCH>
    {research}
    </RESEARCH>

    ## Research idea

    {_task_to_prompt(task)}

    ## Goals

    - Focus on getting basic working implementation
    - Use a dataset appropriate to the experiment
    - Aim for basic functional correctness
    - If you are given "Code To Use", you can directly use it as a starting
      point.

    ## Instructions

    Propose a single evaluation metric that would be useful for analyzing the
    performance of solutions for this research task.

    Note: Validation loss will be tracked separately so you don't need to
    include it in your response.

    Format your response as a list containing:

      - name: The name of the metric
      - maximize: Whether higher values are better (true/false)
      - description: A brief explanation of what the metric measures. Your list
        should contain only one metric.
    """


def build_prompt_baseline_code(
    task: Task,
    metrics: Iterable[Metric],
    memory: str,
    idea: Idea,
    research: str,
    notes: list[str] | None = None,
) -> str:
    return f"""
    ## Introduction

    You are an AI researcher who is looking to publish a paper that will
    contribute significantly to the field. Your first task is to write a python
    script that implements a solid baseline based on the research idea provided
    below. From data preparation to model training. Focus on getting a simple
    but working implementation first, before any sophisticated improvements. We
    will explore more advanced variations in later stages.

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

    ### Baseline experiment guidelines

    - This first experiment design should be relatively simple, without
      extensive hyper-parameter optimization.
    - Take the Memory section into consideration when proposing the design.
    - Don't suggest to do EDA.
    - Prioritize using real public datasets (e.g., from HuggingFace) when they
      suit the task, and only fall back to synthetic data if no suitable dataset
      is available or synthetic generation is essential to the proposed
      experiment.
    - You MUST evaluate your solution on at least 3 different datasets to ensure
      robustness. Use standard benchmark datasets when available (e.g., MNIST,
      CIFAR-10, ImageNet, GLUE, SQuAD, etc.). Each dataset should be evaluated
      separately and results should be tracked per dataset in the experiment_data
      structure.

    ## Implementation guidelines

    ### CRITICAL GPU REQUIREMENTS

    Your code MUST include ALL of these:

    - At the start of your code, add these lines to handle GPU/CPU:
      ```python
      device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
      print(f'Using device: {{device}}')
      ```
    - ALWAYS move models to device using the `.to(device)` method
    - ALWAYS move input tensors to device using the `.to(device)` method
    - ALWAYS move model related tensors to device using the `.to(device)` method
    - For optimizers, create them AFTER moving model to device
    - When using DataLoader, move batch tensors to device in training loop:
      ```python
      batch = {{k: v.to(device) for k, v in batch.items() if isinstance(v, torch.Tensor)}}
      ```

    ### CRITICAL MODEL INPUT GUIDELINES

    - Always pay extra attention to the input to the model being properly
      normalized
    - This is extremely important because the input to the model's forward pass
      directly affects the output, and the loss function is computed based on
      the output

    For generative modeling tasks, you must:

    - Generate a set of samples from your model
    - Compare these samples with ground truth data using appropriate
      visualizations

    ### CODING GUIDELINES

    - Do NOT put any execution code inside 'if __name__ == "__main__":' block
    - All code should be at the global scope or in functions that are called
      from the global scope
    - The script should execute immediately when run, without requiring any
      special entry point or args. Should be executable py running `python
      script.py`.
    - Store any extra files and outputs in the current directory.
    - DO NOT CREATE ANY PLOTS! USING PLOTS IS NOT ALLOWED.

    Data saving requirements:

    Save all data (metrics, losses, predictions, etc.) as JSON following
    the following structure:

    ```python
    # At the start of your code
    experiment_data = {{
        'dataset_name_1': {{
            'metrics': {{'train': [], 'val': []}},
            'losses': {{'train': [], 'val': []}},
            'predictions': [],
            'ground_truth': [],
            # Add other relevant data
        }},
        # Add additional datasets as needed:
        'dataset_name_2': {{
            'metrics': {{'train': [], 'val': []}},
            'losses': {{'train': [], 'val': []}},
            'predictions': [],
            'ground_truth': [],
            # Add other relevant data
        }},
    }}
    ```

    CRITICAL: Your experiment_data dictionary MUST ALWAYS include these four
    required keys for each dataset:
    
    - 'metrics': Dictionary with 'train' and 'val' lists
    - 'losses': Dictionary with 'train' and 'val' lists  
    - 'predictions': List of model predictions
    - 'ground_truth': List of ground truth values

    These keys are MANDATORY and must be present even if some remain empty lists.

    YOU MUST APPEND THE DATA TO THE STRUCTURE ABOVE FOR EACH EPOCH. Like so 
    (update the code to your specific logic):

    ```python
    for epoch in range(num_epochs):
        # logic
        train_metric = ...
        val_metric = ...
        train_loss = ...
        val_loss = ...
        
        # REQUIRED: Always append to these four mandatory keys
        experiment_data['dataset_name_1']['metrics']['train'].append(train_metric)
        experiment_data['dataset_name_1']['metrics']['val'].append(val_metric)
        experiment_data['dataset_name_1']['losses']['train'].append(train_loss)
        experiment_data['dataset_name_1']['losses']['val'].append(val_loss)
        
        # Update predictions and ground_truth as appropriate for your experiment
        if predictions_available:
            experiment_data['dataset_name_1']['predictions'].extend(batch_predictions)
        if ground_truth_available:
            experiment_data['dataset_name_1']['ground_truth'].extend(batch_ground_truth)
    ```

    ### CRITICAL EVALUATION REQUIREMENTS

    Your code MUST include ALL of these:

    1. Track and print to stdout the validation loss at each epoch or at suitable
       intervals:
       ```python
       print(f'Epoch {{epoch}}: validation_loss = {{val_loss:.4f}}')
       ```
    2. Track and update ALL metrics passed below
    3. Update metrics at EACH epoch
    4. Save ALL metrics at the end. You must use the filename `data_baseline.json`:
       ```python
       with open(os.path.join(os.getcwd(), 'data_baseline.json'), 'w') as f:
           json.dump(experiment_data, f)
       ```

    YOUR CODE MUST SAVE THE DATA IN THE `data_baseline.json` FILE.

    ## Idea Context

    <IDEA>
    Name: {idea.name}
    Description: {idea.description}
    Plan: {idea.plan}
    Goals:
    {"\n".join(f"- {goal}" for goal in idea.goals)}
    </IDEA>

    ## Research Background

    <RESEARCH>
    {research}
    </RESEARCH>

    <NOTES>
    {"\n".join(f"{i} - {note}" for i, note in enumerate(notes or [], 1)) or "No notes."}
    </NOTES>

    ## Research idea

    <RESEARCH IDEA>
    {_task_to_prompt(task)}
    </RESEARCH IDEA>

    ## Evaluation metrics

    <EVALUATION METRICS>
    {json.dumps([i.model_dump(mode="json") for i in metrics], indent=2)}
    </EVALUATION METRICS>

    ## Memory

    <MEMORY>
    {memory or "NA"}
    </MEMORY>
    """


def build_prompt_baseline_code_output(
    task: Task,
    code: str,
    stdout: str,
    stderr: str,
    idea: Idea,
    notes: list[str] | None = None,
) -> str:
    return f"""
    ## Introduction

    You are an experienced AI researcher. You have written code for your
    research experiment and now need to evaluate the output of the code
    execution. Analyze the execution output, determine if there were any bugs,
    and provide a summary of the findings.

    ## Idea Context

    <IDEA>
    Name: {idea.name}
    Description: {idea.description}
    Plan: {idea.plan}
    Goals:
    {"\n".join(f"- {goal}" for goal in idea.goals)}
    </IDEA>

    ## Research idea

    <RESEARCH IDEA>
    {_task_to_prompt(task)}
    </RESEARCH IDEA>

    <NOTES>
    {"\n".join(f"{i} - {note}" for i, note in enumerate(notes or [], 1)) or "No notes."}
    </NOTES>

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


def build_prompt_create_notes(state: "State") -> str:
    return f"""
    ## Introduction

    You are summarizing the results of a baseline experiment execution. Create a concise note
    describing what was accomplished, key findings, and any important observations.

    ## Experiment Code

    <CODE>
    ```python
    {state.experiment_code or "N/A"}
    ```
    </CODE>

    ## Execution Summary

    <SUMMARY>
    {state.experiment_summary or "N/A"}
    </SUMMARY>

    ## Metrics

    <METRICS>
    {"\n".join(f"- {m.name}: {m.description}" for m in state.metrics)}
    </METRICS>

    ## Execution Output

    <STDOUT>
    {state.experiment_stdout or "N/A"}
    </STDOUT>

    <STDERR>
    {state.experiment_stderr or "N/A"}
    </STDERR>

    ## Instructions

    Write a brief note (2-3 sentences) summarizing:
    - What experiment was run
    - Key results or findings
    - Any notable observations or issues
    """


def build_prompt_baseline_parser_code(code: str, memory: str = "") -> str:
    return f"""
    ## Introduction

    You are an AI researcher analyzing experimental results stored in a JSON
    file. Write code to load and analyze the metrics from a file named
    'data_baseline.json'. It has the following structure:

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
        }},
    }}
    ```

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

    ## Instructions

    - Load the `data_baseline.json` file, which is located in the current
      directory
    - Extract metrics for each dataset. Refer to the original code to understand
      the data structure.
    - Always print the name of the dataset before printing the metrics
    - Always print the name of the metric before printing the value with precise
      labels (e.g., 'train accuracy', 'validation loss', 'test F1 score').
    - Only print the best or final value for each metric for each dataset
    - DO NOT CREATE ANY PLOTS. PLOTS ARE NOT ALLOWED.

    ### CODING GUIDELINES

    - Do NOT put any execution code inside 'if __name__ == "__main__":' block
    - All code should be at the global scope or in functions that are called
      from the global scope
    - The script should execute immediately when run, without requiring any
      special entry point or args. Should be executable py running `python
      script.py`.
    - Store any extra files and outputs in the current directory.

    ## Example data loading code

    ```python
    import os
    import json
    with open(os.path.join(os.getcwd(), 'data_baseline.json')) as f:
        experiment_data = json.load(f)
    ```

    ## Context

    Here is the original code that was used to generate the `data_baseline.json`
    file:

    <ORIGINAL_CODE>
    ```python
    {code}
    ```
    </ORIGINAL_CODE>

    ## Memory

    <MEMORY>
    {memory or "NA"}
    </MEMORY>
    """


def build_prompt_baseline_parser_output(
    code: str, stdout: str, stderr: str, idea: Idea
) -> str:
    return f"""
    ## Introduction

    You are an experienced AI researcher. You have written code to parse and
    analyze the results of your research experiment. Now you need to evaluate
    the output of the parser execution. Analyze the execution output, determine
    if there were any bugs, and provide a summary of the findings.

    ## Idea Context

    <IDEA>
    Name: {idea.name}
    Description: {idea.description}
    Plan: {idea.plan}
    Goals:
    {"\n".join(f"- {goal}" for goal in idea.goals)}
    </IDEA>

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
