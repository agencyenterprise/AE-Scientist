"""
Minimal code-generation agent used within the tree search pipeline.

Responsibilities:
- Build structured prompts and call the LLM to produce plan + code for a node
- Parse execution results to derive analysis and buggy/non-buggy status
- Produce concise summaries of experiment iterations

Scope:
- Focused on node-level generation and interpretation; orchestration happens elsewhere
- All model calls go through ai_scientist.llm.query
"""

import logging
import random
from typing import cast

import humanize

from ai_scientist.llm.query import query

from .interpreter import ExecutionResult
from .journal import Node
from .types import PromptType
from .utils.config import Config
from .utils.response import extract_code, extract_text_up_to_code, wrap_code
from .vlm_function_specs import review_func_spec, summary_func_spec

logger = logging.getLogger("ai-scientist")


class MinimalAgent:
    """A minimal agent class that only contains what's needed for processing nodes"""

    def __init__(
        self,
        task_desc: str,
        cfg: Config,
        memory_summary: str | None = None,
        evaluation_metrics: str | list[str] | None = None,
        stage: int | None = None,
        stage_name: str | None = None,
    ) -> None:
        self.task_desc = task_desc
        self.memory_summary = memory_summary
        self.cfg = cfg
        self.evaluation_metrics = evaluation_metrics
        self.stage_name = stage_name
        self.data_preview = None

    @property
    def _prompt_environment(self) -> dict[str, str]:
        # Describe available packages and (optionally) GPU context for the LLM
        pkgs = [
            "numpy",
            "pandas",
            "scikit-learn",
            "statsmodels",
            "xgboost",
            "lightGBM",
            "torch",
            "torchvision",
            "torch-geometric",
            "bayesian-optimization",
            "timm",
            "albumentations",
        ]
        random.shuffle(pkgs)
        pkg_str = ", ".join([f"`{p}`" for p in pkgs])

        # Add GPU info if available in config
        gpu_info = ""
        compute_cfg = self.cfg.compute
        if compute_cfg is not None:
            gpu_type = compute_cfg.gpu.type
            vram_gb = compute_cfg.gpu.vram_gb
            gpu_info = (
                f"\n\n**Available Hardware**: You have access to ONE {gpu_type} GPU with {vram_gb}GB VRAM. This is a powerful enterprise GPU that can handle:\n"
                "  - Large models (up to ~7B parameters for inference, ~3B for training)\n"
                "  - Large batch sizes (don't be conservative - use batch sizes of 32-128+)\n"
                "  - Extensive training (15-20+ epochs is fine)\n"
                "  - Multiple datasets with thousands of samples\n"
                "Don't limit yourself to tiny models like distilgpt2 (82M) - consider using gpt2-medium (355M), gpt2-large (774M), or even larger models if appropriate for your task, but prefer gpt-2-like models to not take so long to run."
            )

        env_prompt = {
            "Installed Packages": f"Your solution can use any relevant machine learning packages such as: {pkg_str}. Feel free to use any other packages too (all packages are already installed!). For neural networks we suggest using PyTorch rather than TensorFlow.{gpu_info}"
        }
        return env_prompt

    @property
    def _prompt_impl_guideline(self) -> dict[str, list[str]]:
        # High-level implementation requirements the generated code must follow
        impl_guideline = [
            "CRITICAL GPU REQUIREMENTS - Your code MUST include ALL of these:",
            "  - At the start of your code, add these lines to handle GPU/CPU:",
            "    ```python",
            "    device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')",
            "    print(f'Using device: {device}')",
            "    ```",
            "  - ALWAYS move models to device using the `.to(device)` method",
            "  - ALWAYS move input tensors to device using the `.to(device)` method",
            "  - ALWAYS move model related tensors to device using the `.to(device)` method",
            "  - For optimizers, create them AFTER moving model to device",
            "  - When using DataLoader, move batch tensors to device in training loop: `batch = {k: v.to(device) for k, v in batch.items() if isinstance(v, torch.Tensor)}`",
            "CRITICAL MODEL INPUT GUIDELINES:",
            "  - Always pay extra attention to the input to the model being properly normalized",
            "  - This is extremely important because the input to the model's forward pass directly affects the output, and the loss function is computed based on the output",
        ]
        if hasattr(self.cfg.experiment, "num_syn_datasets"):
            num_syn_datasets = self.cfg.experiment.num_syn_datasets
            if num_syn_datasets > 1:
                impl_guideline.extend(
                    [
                        f"You MUST evaluate your solution on at least {num_syn_datasets} different datasets to ensure robustness:",
                        "  - Use dataset sizes appropriate to the experiment at hand",
                        "  - Use standard benchmark datasets when available",
                        f"  - If using synthetic data, generate at least {num_syn_datasets} variants with different characteristics",
                        "  - For very large datasets (>10GB), use streaming=True to avoid memory issues",
                        "  - Report metrics separately for each dataset",
                        "  - Compute and report the average metric across all datasets",
                    ]
                )
        impl_guideline.extend(
            [
                "For generative modeling tasks, you must:",
                "  - Generate a set of samples from your model",
                "  - Compare these samples with ground truth data using appropriate visualizations",
                "  - When saving plots, always use the 'working_dir' variable that will be defined at the start of the script",
                "  - Make sure to give each figure a unique and appropriate name based on the dataset it represents, rather than reusing the same filename.",
                "Important code structure requirements:",
                "  - Do NOT put any execution code inside 'if __name__ == \"__main__\":' block",
                "  - All code should be at the global scope or in functions that are called from the global scope",
                "  - The script should execute immediately when run, without requiring any special entry point",
                "The code should start with:",
                "  import os",
                "  working_dir = os.path.join(os.getcwd(), 'working')",
                "  os.makedirs(working_dir, exist_ok=True)",
                "The code should be a single-file python program that is self-contained and can be executed as-is.",
                "No parts of the code should be skipped, don't terminate the code execution before finishing the script.",
                "Your response should only contain a single code block.",
                f"Be aware of the running time of the code, it should complete within {humanize.naturaldelta(self.cfg.exec.timeout)}.",
                'You can also use the "./working" directory to store any temporary files that your code needs to create.',
                "Data saving requirements:",
                "- Save all plottable data (metrics, losses, predictions, etc.) as numpy arrays using np.save()",
                "- Use the following naming convention for saved files:",
                "  ```python",
                "  # At the start of your code",
                "  experiment_data = {",
                "      'dataset_name_1': {",
                "          'metrics': {'train': [], 'val': []},",
                "          'losses': {'train': [], 'val': []},",
                "          'predictions': [],",
                "          'ground_truth': [],",
                "          # Add other relevant data",
                "      },",
                "      # Add additional datasets as needed:",
                "      'dataset_name_2': {",
                "          'metrics': {'train': [], 'val': []},",
                "          'losses': {'train': [], 'val': []},",
                "          'predictions': [],",
                "          'ground_truth': [],",
                "          # Add other relevant data",
                "      },",
                "  }",
                "  # During training/evaluation:",
                "  experiment_data['dataset_name_1']['metrics']['train'].append(train_metric)",
                "  ```",
                "- Include timestamps or epochs with the saved metrics",
                "- For large datasets, consider saving in chunks or using np.savez_compressed()",
                "CRITICAL EVALUATION REQUIREMENTS - Your code MUST include ALL of these:",
                "  1. Track and print validation loss at each epoch or at suitable intervals:",
                "     ```python",
                "     print(f'Epoch {epoch}: validation_loss = {val_loss:.4f}')",
                "     ```",
                "  2. Track and update ALL these additional metrics: "
                + str(self.evaluation_metrics),
                "  3. Update metrics at EACH epoch:",
                "  4. Save ALL metrics at the end:",
                "     ```python",
                "     np.save(os.path.join(working_dir, 'experiment_data.npy'), experiment_data)",
                "     ```",
            ]
        )

        if self.cfg.agent.k_fold_validation > 1:
            impl_guideline.append(
                f"The evaluation should be based on {self.cfg.agent.k_fold_validation}-fold cross-validation but only if that's an appropriate evaluation for the task at hand."
            )

        return {"Implementation guideline": impl_guideline}

    @property
    def _prompt_resp_fmt(self) -> dict[str, str]:
        # Response structure: short plan followed by a single python code block
        return {
            "Response format": (
                "Your response should be a brief outline/sketch of your proposed solution in natural language (7-10 sentences), "
                "followed by a single markdown code block (using the format ```python ... ```) which implements this solution and prints out the evaluation metric(s) if applicable. "
                "There should be no additional headings or text in your response. Just natural language text followed by a newline and then the markdown code block. "
                "Make sure to write concise code."
            )
        }

    def _prompt_metricparse_resp_fmt(self) -> dict[str, str]:
        # Response structure tailored for metric-parsing code generation
        return {
            "Response format": (
                "Your response should be a brief outline/sketch of your proposed solution in natural language (3-5 sentences), "
                "followed by a single markdown code block (using the format ```python ... ```) which implements the full code for the metric parsing. "
                "There should be no additional headings or text in your response. Just natural language text followed by a newline and then the markdown code block. "
                "Your generated code should be complete and executable. "
            )
        }

    @property
    def _prompt_debug_resp_fmt(self) -> dict[str, str]:
        # Response structure tailored for debugging/fix iterations
        return {
            "Response format": (
                "Your response should be a brief outline/sketch of your proposed solution in natural language (3-5 sentences), "
                "followed by a single markdown code block (using the format ```python ... ```) which implements the full code including the bugfix/solution. "
                "There should be no additional headings or text in your response. Just natural language text followed by a newline and then the markdown code block. "
                "Your generated code should be complete and executable. Do not omit any part of the code, even if it was part of a previous implementation."
                "Make sure to write concise code."
            )
        }

    @property
    def _prompt_hyperparam_tuning_resp_fmt(self) -> dict[str, str]:
        # Response structure tailored for hyperparameter tuning code
        return {
            "Response format": (
                "Your response should be a brief outline/sketch of your proposed solution in natural language (3-5 sentences), "
                "followed by a single markdown code block (using the format ```python ... ```) which implements the full code including hyperparameter tuning. "
                "There should be no additional headings or text in your response. Do not omit any part of the code, "
                "Your generated code should be complete and executable."
                "Make sure to write concise code."
            )
        }

    @property
    def _prompt_ablation_resp_fmt(self) -> dict[str, str]:
        # Response structure tailored for ablation study code
        return {
            "Response format": (
                "Your response should be a brief outline/sketch of your proposed solution in natural language (3-5 sentences), "
                "followed by a single markdown code block (using the format ```python ... ```) which implements the full code including the ablation study. "
                "There should be no additional headings or text in your response. Do not omit any part of the code, "
                "Your generated code should be complete and executable."
                "Make sure to write concise code."
            )
        }

    def _debug(self, parent_node: Node) -> Node:
        # Build a debugging prompt combining previous code, outputs, and feedback
        prompt: PromptType = {
            "Introduction": (
                "You are an experienced AI researcher. Your previous code for research experiment had a bug, so based on the information below, you should revise it in order to fix this bug. "
                "Your response should be an implementation outline in natural language,"
                " followed by a single markdown code block which implements the bugfix/solution."
            ),
            "Research idea": self.task_desc,
            "Previous (buggy) implementation": wrap_code(parent_node.code),
            "Execution output": wrap_code(parent_node.term_out, lang=""),
            "Feedback based on generated plots": parent_node.vlm_feedback_summary,
            "Feedback about execution time": parent_node.exec_time_feedback,
            "Instructions": {},
        }
        debug_instructions: dict[str, str | list[str]] = {}
        debug_instructions |= self._prompt_debug_resp_fmt
        debug_instructions |= {
            "Bugfix improvement sketch guideline": [
                "You should write a brief natural language description (3-5 sentences) of how the issue in the previous implementation can be fixed.",
                "Don't suggest to do EDA.",
            ],
        }
        debug_instructions |= self._prompt_impl_guideline
        prompt["Instructions"] = debug_instructions

        if self.cfg.agent.data_preview:
            prompt["Data Overview"] = self.data_preview

        plan, code = self.plan_and_code_query(prompt)
        return Node(plan=plan, code=code, parent=parent_node)

    def _generate_seed_node(self, parent_node: Node) -> Node:
        return Node(
            plan="Seed node",
            code=parent_node.code,
            parent=parent_node,
            is_seed_node=True,
        )

    # Wrapper removed: callers should use Stage2Tuning.build_hyperparam_tuning_node directly

    # Wrapper removed: callers should use Stage4Ablation.build_ablation_node directly

    def plan_and_code_query(self, prompt: PromptType, retries: int = 3) -> tuple[str, str]:
        """Generate a natural language plan + code in the same LLM call and split them apart."""
        last_completion: str = ""
        for _ in range(retries):
            # 1) Call LLM once to get combined plan + code
            completion_any = query(
                system_message=prompt,
                user_message=None,
                model=self.cfg.agent.code.model,
                temperature=self.cfg.agent.code.temp,
            )

            completion_text = cast(str, completion_any)
            last_completion = completion_text

            # 2) Try to extract python code block and the leading natural language plan
            code = extract_code(completion_text)
            nl_text = extract_text_up_to_code(completion_text)

            if code and nl_text:
                # merge all code blocks into a single string
                return nl_text, code

            print("Plan + code extraction failed, retrying...")
            # 3) Provide parsing feedback for the next attempt
            prompt["Parsing Feedback"] = (
                "The code extraction failed. Make sure to use the format ```python ... ``` for the code blocks."
            )
        print("Final plan + code extraction attempt failed, giving up...")
        return "", last_completion

    def parse_exec_result(self, node: Node, exec_result: ExecutionResult, workspace: str) -> None:
        logger.info(f"Agent is parsing execution results for node {node.id}")
        # Store raw execution output into the node first
        node.absorb_exec_result(exec_result)
        # Build a structured review prompt for a function-call style response
        prompt = {
            "Introduction": (
                "You are an experienced AI researcher. "
                "You have written code for your research experiment and now need to evaluate the output of the code execution. "
                "Analyze the execution output, determine if there were any bugs, and provide a summary of the findings. "
            ),
            "Research idea": self.task_desc,
            "Implementation": wrap_code(node.code),
            "Execution output": wrap_code(node.term_out, lang=""),
        }
        # Query the feedback model using the review function spec
        response = cast(
            dict,
            query(
                system_message=prompt,
                user_message=None,
                func_spec=review_func_spec,
                model=self.cfg.agent.feedback.model,
                temperature=self.cfg.agent.feedback.temp,
            ),
        )
        # Update node-level analysis and bug status based on model output
        node.analysis = response["summary"]
        node.is_buggy = response["is_bug"] or node.exc_type is not None
        print(
            "[red]Checking if response contains metric name and description[/red]",
            flush=True,
        )
        print(response)

    # Wrapper removed: callers should use Stage3Plotting.generate_plotting_code directly

    def _generate_node_summary(self, node: Node) -> dict:
        """Generate a summary of the node's experimental findings"""
        # Build a compact summary prompt capturing key artifacts from the iteration
        summary_prompt = {
            "Introduction": (
                "You are an AI researcher analyzing experimental results. "
                "Please summarize the findings from this experiment iteration."
            ),
            "Research idea": self.task_desc,
            "Implementation": wrap_code(node.code),
            "Plan": node.plan,
            "Execution output": wrap_code(node.term_out, lang=""),
            "Analysis": node.analysis,
            "Metric": str(node.metric) if node.metric else "Failed",
            "Plot Analyses": (node.plot_analyses if hasattr(node, "plot_analyses") else []),
            "VLM Feedback": (
                node.vlm_feedback_summary if hasattr(node, "vlm_feedback_summary") else ""
            ),
        }
        # Query the feedback model for a structured summary
        return cast(
            dict,
            query(
                system_message=summary_prompt,
                user_message=None,
                func_spec=summary_func_spec,
                model=self.cfg.agent.feedback.model,
                temperature=self.cfg.agent.feedback.temp,
            ),
        )
