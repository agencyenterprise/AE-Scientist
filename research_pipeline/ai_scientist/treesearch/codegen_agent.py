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
import re

import humanize
from pydantic import BaseModel, Field

from ai_scientist.llm import structured_query_with_schema

from .gpu_manager import GPUSpec
from .interpreter import ExecutionResult
from .journal import Node
from .types import PromptType
from .utils.config import Config
from .utils.response import wrap_code
from .vlm_function_specs import REVIEW_RESPONSE_SCHEMA, SUMMARY_RESPONSE_SCHEMA

logger = logging.getLogger("ai-scientist")


class PlanAndCodeSchema(BaseModel):
    plan: str = Field(
        description=(
            "A brief outline or sketch of the proposed solution in natural language. "
            "Use a small number of clear sentences (typically between 3 and 10) to describe the high-level approach "
            "for the current task (e.g., baseline implementation, metric parsing, debugging, or hyperparameter tuning)."
        ),
    )
    code: str = Field(
        description=(
            "The full Python implementation of the solution for the current task as plain executable code. "
            "Do not include markdown code fences or extra commentary; provide only code that can be run directly "
            "in the described environment (e.g., it should compute metrics, parse metrics, or implement the bugfix/tuning as required)."
        ),
    )


class MinimalAgent:
    """A minimal agent class that only contains what's needed for processing nodes"""

    def __init__(
        self,
        task_desc: str,
        cfg: Config,
        stage_name: str,
        gpu_id: int | None = None,
        gpu_spec: GPUSpec | None = None,
        memory_summary: str | None = None,
        evaluation_metrics: str | list[str] | None = None,
    ) -> None:
        self.task_desc = task_desc
        self.memory_summary = memory_summary
        self.cfg = cfg
        self.gpu_id = gpu_id
        self.gpu_spec = gpu_spec
        self.evaluation_metrics = evaluation_metrics
        self.stage_name = stage_name

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
        if self.gpu_spec is not None and self.gpu_id is not None:
            gpu_info = (
                f"\n\n**Available Hardware**: You have access to ONE {self.gpu_spec['name']} GPU with {self.gpu_spec['memory_total_mib']}MB VRAM. This is a powerful enterprise GPU that can handle:\n"
                "  - Large models (up to ~{self.gpu_spec['memory_total_mib']} parameters for inference, ~{self.gpu_spec['memory_total_mib']} for training)\n"
                "  - Large batch sizes (don't be conservative - use batch sizes of 32-128+)\n"
                "  - Extensive training (15-20+ epochs is fine)\n"
                "  - Multiple datasets with thousands of samples"
            )

            gpu_info += f"\n\n**GPU Selection**: Use GPU index {self.gpu_id}. Set the device to `cuda:{self.gpu_id}` and enforce using this GPU (do not fall back)."

        env_prompt = {
            "Installed Packages": f"Your solution can use any relevant machine learning packages such as: {pkg_str}. Feel free to use any other packages too (all packages are already installed!). For neural networks we suggest using PyTorch rather than TensorFlow.{gpu_info}"
        }
        # Debug: show GPU context fed to the LLM
        logger.debug(
            "LLM environment GPU context: gpu_id=%s, gpu_spec=%s",
            self.gpu_id,
            self.gpu_spec,
        )
        return env_prompt

    @property
    def prompt_impl_guideline(self) -> dict[str, list[str]]:
        # High-level implementation requirements the generated code must follow
        impl_guideline = [
            "CRITICAL GPU REQUIREMENTS - Your code MUST include ALL of these:",
            "  - At the start of your code, add these lines to handle GPU/CPU:",
        ]
        if self.gpu_id is not None:
            impl_guideline.extend(
                [
                    "    ```python",
                    f"    torch.cuda.set_device({self.gpu_id})",
                    f"    device = torch.device('cuda:{self.gpu_id}')",
                    "    print(f'Using device: {device}')",
                    "    ```",
                ]
            )
        else:
            impl_guideline.extend(
                [
                    "    ```python",
                    "    device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')",
                    "    print(f'Using device: {device}')",
                    "    ```",
                ]
            )
        impl_guideline.extend(
            [
                "  - ALWAYS move models to device using the `.to(device)` method",
                "  - ALWAYS move input tensors to device using the `.to(device)` method",
                "  - ALWAYS move model related tensors to device using the `.to(device)` method",
                "  - For optimizers, create them AFTER moving model to device",
                "  - When using DataLoader, move batch tensors to device in training loop: `batch = {k: v.to(device) for k, v in batch.items() if isinstance(v, torch.Tensor)}`",
                "CRITICAL MODEL INPUT GUIDELINES:",
                "  - Always pay extra attention to the input to the model being properly normalized",
                "  - This is extremely important because the input to the model's forward pass directly affects the output, and the loss function is computed based on the output",
            ]
        )
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

        # Response format is fully specified by the PlanAndCodeSchema Pydantic model

    # schemas used elsewhere; no additional response-format helpers are needed here.

    def debug(self, parent_node: Node) -> Node:
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
        debug_instructions |= {
            "Bugfix improvement sketch guideline": [
                "You should write a brief natural language description (3-5 sentences) of how the issue in the previous implementation can be fixed.",
                "Don't suggest to do EDA.",
            ],
        }
        debug_instructions |= self.prompt_impl_guideline
        prompt["Instructions"] = debug_instructions
        plan, code = self.plan_and_code_query(prompt)
        return Node(plan=plan, code=code, parent=parent_node)

    def generate_seed_node(self, parent_node: Node) -> Node:
        return Node(
            plan="Seed node",
            code=parent_node.code,
            parent=parent_node,
            is_seed_node=True,
        )

    def plan_and_code_query(self, prompt: PromptType, retries: int = 3) -> tuple[str, str]:
        """Generate a natural language plan + code in the same LLM call and split them apart."""
        last_completion: str = ""
        for _ in range(retries):
            logger.debug(
                "Calling code-generation LLM with gpu_id=%s, gpu_spec=%s",
                self.gpu_id,
                self.gpu_spec,
            )
            try:
                response = structured_query_with_schema(
                    system_message=prompt,
                    model=self.cfg.agent.code.model,
                    temperature=self.cfg.agent.code.temperature,
                    schema_class=PlanAndCodeSchema,
                )
            except Exception as exc:
                logger.warning("Structured plan + code query failed, retrying...")
                logger.warning("Details: %s", exc)
                continue

            nl_text = response.plan.strip()
            code = response.code.strip()
            last_completion = f"{nl_text}\n\n{code}"

            if code and nl_text:
                if self.gpu_id is not None:
                    is_valid, validation_msg = self._validate_code_uses_gpu_id(code)
                    if not is_valid:
                        logger.warning("GPU id enforcement validation failed")
                        logger.warning("GPU validation details: %s", validation_msg)
                        prompt["Validation Feedback"] = validation_msg
                        continue
                return nl_text, code

            logger.warning("Structured plan + code extraction failed, retrying...")
            prompt["Parsing Feedback"] = (
                "The structured response was missing either 'plan' or 'code'. "
                "Ensure both fields are present and non-empty."
            )
        logger.error("Final plan + code extraction attempt failed, giving up...")
        return "", last_completion

    def _validate_code_uses_gpu_id(self, code: str) -> tuple[bool, str]:
        """Ensure the generated code explicitly targets the configured GPU index.

        Requirements:
        - Must set the CUDA device index via torch.cuda.set_device({gpu_id}) when CUDA is available
        - Must create a torch.device(...) that refers to 'cuda:{gpu_id}' when CUDA is available
        - It is allowed to fall back to CPU when CUDA is not available
        """
        assert self.gpu_id is not None
        gpu_id_str = str(self.gpu_id)
        # Accept alias imports and varying whitespace:
        # - torch.cuda.set_device(<id>) OR cuda.set_device(<id>) OR set_device(<id>)
        pattern_set_device = (
            rf"\b(?:(?:torch\.)?cuda\.)?set_device\(\s*{re.escape(gpu_id_str)}\s*\)"
        )
        # - torch.device('cuda:<id>') OR device('cuda:<id>') with either quote
        pattern_device_ctor = (
            rf"\b(?:(?:torch\.)?)device\([^)]*['\"]cuda:{re.escape(gpu_id_str)}['\"][^)]*\)"
        )
        has_set_device = re.search(pattern_set_device, code) is not None
        has_device_ctor = re.search(pattern_device_ctor, code) is not None
        if has_set_device and has_device_ctor:
            return True, ""
        missing_parts: list[str] = []
        if not has_set_device:
            missing_parts.append(f"Add: torch.cuda.set_device({gpu_id_str})")
        if not has_device_ctor:
            missing_parts.append(f"Add: device = torch.device('cuda:{gpu_id_str}')")
        feedback = (
            "You must enforce using the specified GPU index when CUDA is available. "
            + " ".join(missing_parts)
            + " CPU fallback via torch.cuda.is_available() checks is allowed."
        )
        return False, feedback

    def parse_exec_result(self, node: Node, exec_result: ExecutionResult) -> None:
        logger.info("Agent is parsing execution results for node %s", node.id)
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
        response_model = structured_query_with_schema(
            system_message=prompt,
            user_message=None,
            model=self.cfg.agent.feedback.model,
            temperature=self.cfg.agent.feedback.temperature,
            schema_class=REVIEW_RESPONSE_SCHEMA,
        )
        response = response_model.model_dump(by_alias=True)
        # Update node-level analysis and bug status based on model output
        node.analysis = response["summary"]
        node.is_buggy = response["is_bug"] or node.exc_type is not None
        logger.debug("Checking if response contains metric name and description")
        logger.debug("Bug check response: %s", response)

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
            "Plot Analyses": node.plot_analyses,
            "VLM Feedback": node.vlm_feedback_summary,
        }
        # Query the feedback model for a structured summary
        return structured_query_with_schema(
            system_message=summary_prompt,
            user_message=None,
            model=self.cfg.agent.feedback.model,
            temperature=self.cfg.agent.feedback.temperature,
            schema_class=SUMMARY_RESPONSE_SCHEMA,
        ).model_dump(by_alias=True)
