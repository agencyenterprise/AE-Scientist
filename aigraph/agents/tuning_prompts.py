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


def build_prompt_tuning_propose(code: str, hyperparams: list[str]) -> str:
    attempted = hyperparams or ["Nothing has been tried yet."]

    return f"""
    You are an AI researcher conducting hyperparameter tuning for baseline
    experiments. Based on the current implementation and previous hyperparameter
    tuning attempts (if any), propose ONE new hyperparameter tuning idea to see
    if it improves the performance.
    
    You should first check if simply training longer (more epochs) improves the
    performance. Then try tuning common hyperparameters such as learning rate,
    batch size, etc. Only propose algorithm-specific and/or model-specific
    hyperparameters after you have tried the above.
    
    ## Code
    
    <CODE>
    ```python
    {code}
    ```
    </CODE>

    ## Previous Hyperparam Tuning Attempts
    
    <PREVIOUS_HYPERPARAM_TUNING_ATTEMPTS>
    {"\n".join(f"- {i}" for i in attempted)}
    </PREVIOUS_HYPERPARAM_TUNING_ATTEMPTS>
    
    ## Requirements
    
    1. Identify ONE specific hyperparameter to tune
    2. Ensure the hyperparameter is different from previous attempts

    ## Response format
    
    - Your response should start with 'HYPERPARAM NAME: <hyperparam name>' on
      the first line to represent the name of the hyperparameter.
    - The second line should start with 'DESCRIPTION: <description>', a brief
      description of what hyperparameter is being tuned and why (3-5 sentences).
    """


def build_prompt_tuning_code(
    task: Task, name: str, description: str, code: str, memory: str
) -> str:
    return f"""
    ## Introduction

    You are an experienced AI researcher. You are provided with a previously
    developed baseline implementation. Your task is to implement hyperparameter
    tuning for the following idea:
    
    Name: {name}
    Description: {description}

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

    ### Hyperparameter tuning guidelines

    - Implement the hyperparameter tuning idea described above.
    - The code should be a single-file python program that is self-contained and
      can be executed as-is.
    - No parts of the code should be skipped, don't terminate the code execution
      before finishing the script.
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

    CRITICAL: Your experiment_data dictionary MUST ALWAYS include these four required keys for each dataset:
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
    2. Track and update metrics as in the original code.
    3. Update metrics at EACH epoch
    4. Save ALL metrics at the end. You must use the filename `data_tuning.json`:
       ```python
       with open(os.path.join(os.getcwd(), 'data_tuning.json'), 'w') as f:
           json.dump(experiment_data, f)
       ```

    YOUR CODE MUST SAVE THE DATA IN THE `data_tuning.json` FILE.

    ## Research idea

    <RESEARCH_IDEA>
    {_task_to_prompt(task)}
    </RESEARCH_IDEA>

    ## Original Code
    
    ```python
    {code}
    ```

    ## Memory

    <MEMORY>
    {memory or "NA"}
    </MEMORY>
    """


def build_prompt_tuning_code_output(
    task: Task, code: str, stdout: str, stderr: str
) -> str:
    return f"""
    ## Introduction
    
    You are an experienced AI researcher. You have written code for your
    research experiment and now need to evaluate the output of the code
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


def build_prompt_tuning_parser_code(code: str, memory: str = "") -> str:
    return f"""
    ## Introduction

    You are an AI researcher analyzing experimental results stored in a JSON
    file. Write code to load and analyze the metrics from a file named
    'data_tuning.json'. It has the following structure:

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

    - Load the `data_tuning.json` file, which is located in the current
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
    with open(os.path.join(os.getcwd(), 'data_tuning.json')) as f:
        experiment_data = json.load(f)
    ```

    ## Context

    Here is the original code that was used to generate the `data_tuning.json`
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


def build_prompt_tuning_parser_output(code: str, stdout: str, stderr: str) -> str:
    return f"""
    ## Introduction

    You are an experienced AI researcher. You have written code to parse and analyze the
    results of your research experiment. Now you need to evaluate the output of the
    parser execution. Analyze the execution output, determine if there were any bugs,
    and provide a summary of the findings.

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
