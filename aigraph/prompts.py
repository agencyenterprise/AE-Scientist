
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


def build_prompt_define_metrics(task: Task) -> str:
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


def build_prompt_code_experiment(task: Task, metrics: list[Metric], memory: str) -> str:
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

    {_task_to_prompt(task)}

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

    - Do NOT put any execution code inside 'if __name__ == "__main__":' block
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


def build_prompt_parse_experiment_output(task: Task, code: str, stdout: str, stderr: str) -> str:
    return f"""
    ## Introduction
    
    You are an experienced AI researcher. You have written code for your
    research experiment and now need to evaluate the output of the code
    execution. Analyze the execution output, determine if there were any bugs,
    and provide a summary of the findings.

    ## Research idea

    {_task_to_prompt(task)}

    ## Implementation

    ```python
    {code}
    ```

    ## Stdout

    ```
    {stdout}
    ```

    ## Stderr

    ```
    {stderr}
    ```
    """


def build_prompt_code_metrics_parser(code: str) -> str:
    return f"""
    ## Introduction
    
    You are an AI researcher analyzing experimental results stored in numpy
    files. Write code to load and analyze the metrics from
    `experiment_data.npy`.
    
    ## Context
    
    Original Code:
    
    ```python
    {code}
    ```
    
    ## Instructions
    
    0. Make sure to get the working directory from `os.path.join(os.getcwd(),
       'working')`
    1. Load the `experiment_data.npy` file, which is located in the working
       directory
    2. Extract metrics for each dataset. Refer to the original code to
       understand the data structure.
    3. Always print the name of the dataset before printing the metrics
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
    import numpy as np
    import os
    experiment_data = np.load(os.path.join(os.getcwd(), 'working', 'experiment_data.npy'), allow_pickle=True).item()
    ```
    
    ## Response format
    
    Your response should be a brief outline/sketch of your proposed solution in
    natural language (3-5 sentences), followed by a single markdown code block
    (using the format ```python ... ```) which implements the full code for the
    metric parsing. There should be no additional headings or text in your
    response. Just natural language text followed by a newline and then the
    markdown code block. Your generated code should be complete and executable.
    """


def build_prompt_parse_metrics(stdout: str) -> str:
    return f"""
    ## Introduction

    Parse the metrics from the execution output. You only need the final or best
    value of each metric for each dataset.

    ## Execution Output

    ```
    {stdout}
    ```
    """


def build_prompt_propose_hyperparam(code: str, hyperparams: list[str]) -> str:
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
    
    ```python
    {code}
    ```
    
    ## Previous Hyperparam Tuning Attempts
    
    {"\n".join(f"- {i}" for i in attempted)}
    
    ## Requirements
    
    1. Identify ONE specific hyperparameter to tune
    2. Ensure the hyperparameter is different from previous attempts

    ## Response format
    
    - Your response should start with 'HYPERPARAM NAME: <hyperparam name>' on
      the first line to represent the name of the hyperparameter.
    - The second line should start with 'DESCRIPTION: <description>', a brief
      description of what hyperparameter is being tuned and why (3-5 sentences).
    """


def build_prompt_code_tuning(name: str, description: str, code: str) -> str:
    return f"""
    ## Introduction

    You are an experienced AI researcher. You are provided with a previously
    developed baseline implementation. Your task is to implement hyperparameter
    tuning for the following idea:
    
    Name: {name}
    Description: {description}
    
    ## Code
    
    ```python
    {code}
    ```
    
    ## Implementation Guidelines
    
    - The code should be a single-file python program that is self-contained and
      can be executed as-is.
    - No parts of the code should be skipped, don't terminate the code execution
      before finishing the script.
    
    Data saving requirements:

    - Save all plottable data (metrics, losses, predictions, etc.) as numpy
      arrays using  `np.save()`
    - Use the following naming convention for saved files:
      ```python
      # At the start of your code
      experiment_data = {{
          'hyperparam_tuning_type_1': {{
              'dataset_name_1': {{
                  'metrics': {{'train': [], 'val': []}},
                  'losses': {{'train': [], 'val': []}},
                  'predictions': [],
                  'ground_truth': [],
              }},
          }},
      }}
      ```
    - Make sure to use a filename 'experiment_data.npy' to save the data. Do not
      use any other filename.

    # Response format

    - Your response should be a brief outline/sketch of your proposed solution
      in natural language (3-5 sentences), followed by a single markdown code
      block (using the format ```python ...```) which implements the full code
      including hyperparameter tuning. 
    - There should be no additional headings or text in your response. 
    - Do not omit any part of the code
    - Your generated code should be complete and executable. 
    - Make sure to write concise code.
    """


def build_prompt_code_tuning_metrics_parser(code: str) -> str:
    return f"""
    ## Introduction
    
    You are an AI researcher analyzing experimental results stored in numpy
    files. Write code to load and analyze the metrics from
    `experiment_data.npy` generated by a hyperparameter tuning experiment.
    
    ## Context
    
    Original Tuning Code:
    
    ```python
    {code}
    ```
    
    ## Instructions
    
    0. Make sure to get the working directory from `os.path.join(os.getcwd(),
       'working')`
    1. Load the `experiment_data.npy` file, which is located in the working
       directory
    2. Extract metrics for each hyperparameter tuning run and dataset. Refer to the 
       original code to understand the data structure (it is nested with 
       hyperparameter tuning types).
    3. Always print the name of the hyperparameter setting/type and dataset before printing the metrics
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
    import numpy as np
    import os
    experiment_data = np.load(os.path.join(os.getcwd(), 'working', 'experiment_data.npy'), allow_pickle=True).item()
    ```
    
    ## Response format
    
    Your response should be a brief outline/sketch of your proposed solution in
    natural language (3-5 sentences), followed by a single markdown code block
    (using the format ```python ... ```) which implements the full code for the
    metric parsing. There should be no additional headings or text in your
    response. Just natural language text followed by a newline and then the
    markdown code block. Your generated code should be complete and executable.
    """


def build_prompt_evaluate_tuning_substage(datasets: str, best_metric: str, returncode: str, stderr: str) -> str:
    return f"""
    Evaluate if Stage 2 (baseline tuning) sub-stage is complete.
    
    ## Evidence
    
    - Datasets tested: {datasets}
    - Best metric: {best_metric}
    - Return code: {returncode}
    - Stderr: {stderr}
    
    ## Requirements for completion
    
    - Change hyperparameters such as learning rate, number of epochs, batch
      size, etc. to improve the performance
    - DO NOT change the model architecture from the previous stage
    - Introduce additional datasets from HuggingFace to test the model. Use
      dataset sizes appropriate to the experiment. Use streaming=True for very
      large datasets.
    """


def build_prompt_evaluate_tuning_stage(datasets: str) -> str:
    return f"""
    Evaluate if Stage 2 (baseline tuning) is complete based on the following
    evidence:
    
    ## Evidence
    
    - Datasets tested: {datasets}
    
    ## Requirements for completion
    
    1. Training curves should show stable convergence
    2. Results should be tested on at least two datasets
    3. No major instabilities or issues in the plots
    
    Provide a detailed evaluation of completion status.
    """


def build_prompt_generate_plotting_code(code: str, data: str) -> str:
    return f"""
    ## AVAILABLE DATA: 
    
    Experiment Data: {data}

    ## REQUIREMENTS: 

    The code should start with:

    ```python
    import matplotlib.pyplot as plt
    import numpy as np
    import os
    working_dir = os.path.join(os.getcwd(), 'working')
    ```

    - Create standard visualizations of experiment results
    - Save all plots to working_dir
    - Include training/validation curves if available
    - ONLY plot data that exists in experiment_data.npy - DO NOT make up or
      simulate any values
    - Use basic matplotlib without custom styles
    - Each plot should be in a separate try-except block
    - Always close figures after saving
    - Always include a title for each plot, and be sure to use clear
      subtitles—such as 'Left: Ground Truth, Right: Generated Samples'—while
      also specifying the type of dataset being used.
    - Make sure to use descriptive names for figures when saving e.g. always
      include the dataset name and the type of plot in the name
    - When there are many similar figures to plot (e.g. generated samples at
      each epoch), make sure to plot only at a suitable interval of epochs so
      that you only plot at most 5 figures.
    
    Use the following experiment code to infer the data to plot: 
    
    ```python
    {code}
    ```

    Example to extract data from experiment_data: 
    
    ```python
    experiment_data['dataset_name_1']['metrics']['train']
    ```
    
    Example data loading and plot saving code: 

    ```python
        try:
            experiment_data = np.load(os.path.join(working_dir, 'experiment_data.npy'), allow_pickle=True).item()
        except Exception as e:
        print(f'Error loading experiment data: {{e}}')

        try:
            # First plot
            plt.figure()
            # ... plotting code ...
            plt.savefig('working_dir/[plot_name_1].png')
            plt.close()
        except Exception as e:
        print(f"Error creating plot1: {{e}}")
            plt.close()  # Always close figure even if error occurs

        try:
            # Second plot
            plt.figure()
            # ... plotting code ...
            plt.savefig('working_dir/[plot_name_2].png')
            plt.close()
        except Exception as e:
        print(f"Error creating plot2: {{e}}")
            plt.close()
    ```
    """


def build_prompt_propose_ablation(code: str, ablations: list[str]) -> str:
    attempted = ablations or ["Nothing has been tried yet."]

    return f"""
    You are an AI researcher conducting ablation studies. Based on the current
    implementation and previous ablations (if any), propose ONE new ablation
    study that tests a different aspect of the model.

    ## Base code you are working on

    ```python
    {code}
    ```

    ## Previous Ablations

    {"\n".join(f"- {i}" for i in attempted)}

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


def build_prompt_code_ablation(name: str, description: str, code: str) -> str:
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
    
    Implementation guideline:

    - The code should be a single-file python program that is self-contained and
      can be executed as-is.
    - No parts of the code should be skipped, don't terminate the code execution
      before finishing the script.
    
    Data saving requirements:

    - Save all plottable data (metrics, losses, predictions, etc.) as numpy
      arrays using `np.save()`
    - Use the following naming convention for saved files:
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
    - Make sure to use a filename 'experiment_data.npy' to save the data. Do not
      use any other filename.
    """


def build_prompt_code_ablation_metrics_parser(code: str) -> str:
    return f"""
    ## Introduction
    
    You are an AI researcher analyzing experimental results stored in numpy
    files. Write code to load and analyze the metrics from
    `experiment_data.npy` generated by an ablation study experiment.
    
    ## Context
    
    Original Ablation Code:
    
    ```python
    {code}
    ```
    
    ## Instructions
    
    0. Make sure to get the working directory from `os.path.join(os.getcwd(),
       'working')`
    1. Load the `experiment_data.npy` file, which is located in the working
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
    import numpy as np
    import os
    experiment_data = np.load(os.path.join(os.getcwd(), 'working', 'experiment_data.npy'), allow_pickle=True).item()
    ```
    
    ## Response format
    
    Your response should be a brief outline/sketch of your proposed solution in
    natural language (3-5 sentences), followed by a single markdown code block
    (using the format ```python ... ```) which implements the full code for the
    metric parsing. There should be no additional headings or text in your
    response. Just natural language text followed by a newline and then the
    markdown code block. Your generated code should be complete and executable.
    """


def build_prompt_evaluate_ablation_substage() -> str:
    return """
    Evaluate if the ablation sub-stage is complete.

    - Conduct systematic component analysis that reveals the contribution of
      each part
    - Use the same datasets you used from the previous stage

    Consider whether the ablation variations produce consistent and
    interpretable differences.
    """
