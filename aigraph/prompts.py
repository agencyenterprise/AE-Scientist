

import json
from aigraph.utils import ROOT_DIR, Task, Metric


def build_task_prompt(task: Task) -> str:
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



def build_prompt_metrics(task: Task) -> str:
    return f"""
    ## Introduction
    
    You are an AI researcher setting up experiments. Please propose meaningful
    evaluation metrics that will help analyze the performance and
    characteristics of solutions for this research task.

    ## Research idea

    {build_task_prompt(task)}
    
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


def build_prompt_plan_and_code(task: Task, metrics: list[Metric], memory: str) -> str:
    prompt = f"""
    ## Introduction

    You are an AI researcher who is looking to publish a paper that will
    contribute significantly to the field.Your first task is to write a python
    code to implement a solid baseline based on your research idea provided
    below, from data preparation to model training, as well as evaluation and
    visualization. Focus on getting a simple but working implementation first,
    before any sophisticated improvements. We will explore more advanced
    variations in later stages.

    ## Research idea

    {build_task_prompt(task)}

    ## Memory

    {memory}

    ## Evaluation metrics

    ```json 
    {json.dumps([i.model_dump(mode='json') for i in metrics], indent=2)}
    ```

    ## Instructions

    ### Response format

    Your response should be a brief outline/sketch of your proposed solution in
    natural language (7-10 sentences), followed by a single markdown code block
    (using the format ```python ... ```) which implements this solution and
    prints out the evaluation metric(s) if applicable. There should be no
    additional headings or text in your response. Just natural language text
    followed by a newline and then the markdown code block. Make sure to write
    concise code.

    ### Experiment design sketch guideline

    - This first experiment design should be relatively simple, without
      extensive hyper-parameter optimization.
    - Take the Memory section into consideration when proposing the design.
    - The solution sketch should be 6-10 sentences.
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
    
    ### CRITICAL MODEL INPUT GUIDELINES:

    - Always pay extra attention to the input to the model being properly
      normalized
    - This is extremely important because the input to the model's forward pass
      directly affects the output, and the loss function is computed based on
      the output

    For generative modeling tasks, you must:

    - Generate a set of samples from your model
    - Compare these samples with ground truth data using appropriate
      visualizations
    - When saving plots, always use the 'working_dir' variable that will be
      defined at the start of the script
    - Make sure to give each figure a unique and appropriate name based on the
      dataset it represents, rather than reusing the same filename.

    Important code structure requirements:

    - Do NOT put any execution code inside 'if __name__ == \"__main__\":' block
    - All code should be at the global scope or in functions that are called
      from the global scope
    - The script should execute immediately when run, without requiring any
      special entry point

    The code should start with:

    ```python
    import os
    working_dir = os.path.join(os.getcwd(), 'working')
    os.makedirs(working_dir, exist_ok=True)
    ```

    The code should be a single-file python program that is self-contained and
    can be executed as-is. No parts of the code should be skipped, don't
    terminate the code execution before finishing the script. Your response
    should only contain a single code block. Be aware of the running time of the
    code, it should complete within 2 hours. You can also use the "./working"
    directory to store any temporary files that your code needs to create.

    Data saving requirements:

    - Save all plottable data (metrics, losses, predictions, etc.) as numpy 
       arrays using np.save()
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
    - For large datasets, consider saving in chunks or using `np.savez_compressed()`
      
    ### CRITICAL EVALUATION REQUIREMENTS 
      
    Your code MUST include ALL of these:

    1. Track and print validation loss at each epoch or at suitable intervals:
       ```python
       print(f'Epoch {{epoch}}: validation_loss = {{val_loss:.4f}}')
       ```
    2. Track and update ALL these additional metrics: 
       ```json
       {json.dumps([i.model_dump(mode='json') for i in metrics], indent=2)}
       ```
    3. Update metrics at EACH epoch
    4. Save ALL metrics at the end
       ```python
       np.save(os.path.join(working_dir, 'experiment_data.npy'), experiment_data)
       ```
    """
    return prompt

def build_prompt_draft(*, task: Task, memory: str) -> str:
    return f"""
    ## Introduction
    
    You are an AI researcher who is looking to publish a paper that will
    contribute significantly to the field. Your first task is to write python
    code to implement a solid baseline based on your research idea provided
    below, from data preparation to model training, as well as evaluation and
    visualization. Focus on getting a simple but working implementation first,
    before any sophisticated improvements. We will explore more advanced
    variations in later stages.
    
    ## Research idea
    
    {build_task_prompt(task)}
    
    ## Memory
    
    {memory}
    
    ## Instructions
    
    ### Experiment design sketch guideline
    
    - This first experiment design should be relatively simple, without
      extensive hyper-parameter optimization.
    - Take the Memory section into consideration when proposing the design.
    - The solution sketch should be 6-10 sentences.
    - Don't suggest to do EDA.
    - Prioritize using real public datasets (e.g., from HuggingFace) when they
      suit the task, and only fall back to synthetic data if no suitable dataset
      is available or synthetic generation is essential to the proposed
      experiment.
    
    ### Goals
    
    - Focus on getting basic working implementation
    - Use a dataset appropriate to the experiment
    - Aim for basic functional correctness
    - If you are given "Code To Use", you can directly use it as a starting
      point.
    """


def build_prompt_improve(
    *,
    task: Task,
    memory: str,
    previous_code: str,
    feedback: str,
) -> str:
    code_block = f"```python\n{previous_code}\n```" if previous_code else "None"
    return f"""
    ## Introduction
    
    You are an experienced AI researcher. You are provided with a previously
    developed implementation. Your task is to improve it based on the current
    experimental stage.
    
    ## Research idea
    
    {build_task_prompt(task)}
    
    ## Memory
    
    {memory}
    
    ## Previous solution
    
    ### Code
    
    {code_block}
    
    ## Feedback
    
    {feedback}
    
    ## Instructions
    
    Focus on addressing the feedback and improving the implementation while
    maintaining the core functionality.
    """


def build_prompt_check_completion(
    *,
    metric: float | str | None,
    has_code: bool,
    returncode: int | None,
    stderr: str | None,
    goals: str,
) -> str:
    metric_str = str(metric) if metric is not None else "N/A"
    err = (stderr or "None")[:1000]
    return f"""
    Evaluate if the current stage is complete.
    
    ## Evidence
    
    - Best metric: {metric_str}
    - Has working code: {has_code}
    - Return code: {returncode}
    - Error output: {err}
    
    ## Requirements for completion
    
    - {goals}
    
    Determine if these requirements are met.
    """
