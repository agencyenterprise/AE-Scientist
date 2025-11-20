
import json
from aigraph.utils import ROOT_DIR, Task, Metric


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


def build_prompt_baseline_metrics(task: Task) -> str:
    return f"""
    ## Introduction
    
    You are an AI researcher setting up experiments. Please propose meaningful
    evaluation metrics that will help analyze the performance and
    characteristics of solutions for this research task.

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


def build_prompt_baseline_code(task: Task, metrics: list[Metric], memory: str) -> str:
    prompt = f"""
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
      ["torch", "torchvision", "numpy", "pandas", "scikit-learn"]. Do not 
      include standard library dependencies. Only third party dependencies.

    ### Baseline experiment guidelines

    - This first experiment design should be relatively simple, without
      extensive hyper-parameter optimization.
    - Take the Memory section into consideration when proposing the design.
    - Don't suggest to do EDA.
    - Prioritize using real public datasets (e.g., from HuggingFace) when they
      suit the task, and only fall back to synthetic data if no suitable dataset
      is available or synthetic generation is essential to the proposed
      experiment.

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
    - Store any extra files and outputs in the current working directory.
    - DO NOT CREATE ANY PLOTS! USING PLOTS IS NOT ALLOWED.

    Data saving requirements:

    - Save all data (metrics, losses, predictions, etc.) as numpy arrays using 
      `np.save()`.
    - Use the following naming convention for saved files:
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

       # During training/evaluation:
       experiment_data['dataset_name_1']['metrics']['train'].append(train_metric)
       ```
    - Include timestamps or epochs with the saved metrics
      
    ### CRITICAL EVALUATION REQUIREMENTS 
      
    Your code MUST include ALL of these:

    1. Track and print to stdout the validation loss at each epoch or at suitable 
       intervals:
       ```python
       print(f'Epoch {{epoch}}: validation_loss = {{val_loss:.4f}}')
       ```
    2. Track and update ALL metrics passed below
    3. Update metrics at EACH epoch
    4. Save ALL metrics at the end
       ```python
       np.save(os.path.join(os.getcwd(), 'experiment_data.npy'), experiment_data)
       ```

    YOUR CODE MUST SAVE THE DATA IN THE `experiment_data.npy` FILE.

    ## Research idea

    <RESEARCH IDEA>
    {_task_to_prompt(task)}
    </RESEARCH IDEA>

    ## Evaluation metrics

    <EVALUATION METRICS>
    ```json 
    {json.dumps([i.model_dump(mode='json') for i in metrics], indent=2)}
    ```
    </EVALUATION METRICS>

    ## Memory

    <MEMORY>
    {memory or 'NA'}
    </MEMORY>
    """
    return prompt


def build_prompt_baseline_code_output(task: Task, code: str, stdout: str, stderr: str) -> str:
    return f"""
    ## Introduction
    
    You are an experienced AI researcher. You have written code for your
    research experiment and now need to evaluate the output of the code
    execution. Analyze the execution output, determine if there were any bugs,
    and provide a summary of the findings.

    ## Research idea

    <RESEARCH IDEA>
    {_task_to_prompt(task)}
    </RESEARCH IDEA>

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


def build_prompt_baseline_parser_code(code: str) -> str:
    return f"""
    ## Introduction
    
    You are an AI researcher analyzing experimental results stored in numpy
    files. Write code to load and analyze the metrics from
    `experiment_data.npy`. The data in the `experiment_data.npy` file is nested
    has been saved with the following structure:

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

    # During training/evaluation:
    experiment_data['dataset_name_1']['metrics']['train'].append(train_metric)

    # saved        
    np.save(os.path.join(os.getcwd(), 'experiment_data.npy'), experiment_data)
    ```

    ### Response format

    Your response should use structured json outputs in the following format:

    - plan: A brief outline/sketch of your proposed solution in natural language
      (7-10 sentences)
    - code: A python script in plain python. DO NOT USE FENCES. EG:
      \\`\\`\\`python ... \\`\\`\\`
    - dependencies: A list of dependencies required for the code to run. EG:
      ["torch", "torchvision", "numpy", "pandas", "scikit-learn"]
    
    ## Instructions
    
    - Load the `experiment_data.npy` file, which is located in the current
      working directory
    - Extract metrics for each dataset. Refer to the original code to understand
      the data structure.
    - Always print the name of the dataset before printing the metrics
    - Always print the name of the metric before printing the value with precise
      labels (e.g., 'train accuracy', 'validation loss', 'test F1 score').
    - Only print the best or final value for each metric for each dataset
    - DO NOT CREATE ANY PLOTS
    
    ### CODING GUIDELINES

    - Do NOT put any execution code inside 'if __name__ == "__main__":' block
    - All code should be at the global scope or in functions that are called
      from the global scope
    - The script should execute immediately when run, without requiring any
      special entry point or args. Should be executable py running `python
      script.py`.
    - Store any extra files and outputs in the current working directory.

    ## Example data loading code
    
    ```python
    import os
    import numpy as np
    experiment_data = np.load(os.path.join(os.getcwd(), 'experiment_data.npy'), allow_pickle=True).item()
    ```

    ## Context

    Here is the original code that was used to generate the `experiment_data.npy` file:
    
    <ORIGINAL_CODE>
    ```python
    {code}
    ```
    </ORIGINAL_CODE>
    """


def build_prompt_baseline_parser_output(stdout: str) -> str:
    return f"""
    ## Introduction

    Parse the metrics from the execution output. You only need the final or best
    value of each metric for each dataset.

    ## Execution Output

    ```
    {stdout}
    ```
    """

