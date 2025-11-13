from typing import List, Protocol, Tuple

from ai_scientist.llm.query import FunctionSpec, query

from ..journal import Journal, Node
from ..response_parsing import parse_keyword_prefix_response
from ..types import PromptType
from ..utils.config import Config as AppConfig
from ..utils.response import wrap_code
from .base import Stage


class HyperparamTuningIdea:
    def __init__(self, name: str, description: str):
        self.name = name
        self.description = description


class SupportsStage2Agent(Protocol):
    def plan_and_code_query(self, *, prompt: PromptType, retries: int = 3) -> Tuple[str, str]:
        pass

    @property
    def _prompt_hyperparam_tuning_resp_fmt(self) -> dict[str, str]:
        pass


class Stage2Tuning(Stage):
    MAIN_STAGE_SLUG = "baseline_tuning"
    DEFAULT_GOALS = (
        "- Change hyperparameters such as learning rate, number of epochs, batch size, etc. to improve the performance\n"
        "- DO NOT change the model architecture from the previous stage\n"
        "- Introduce additional datasets from HuggingFace to test the model. Use dataset sizes appropriate to the experiment. Use streaming=True for very large datasets."
    )

    @staticmethod
    def build_hyperparam_tuning_node(
        *, agent: SupportsStage2Agent, parent_node: Node, hyperparam_idea: HyperparamTuningIdea
    ) -> Node:
        prompt: PromptType = {
            "Introduction": (
                "You are an experienced AI researcher. You are provided with a previously developed "
                "baseline implementation. Your task is to implement hyperparameter tuning for the following idea: "
                + hyperparam_idea.name
                + ". "
                + hyperparam_idea.description
            ),
            "Base code you are working on": wrap_code(parent_node.code),
            "Instructions": {},
        }
        hp_instructions: dict[str, str | list[str]] = {}
        hp_instructions |= {
            "Implementation guideline": [
                "The code should be a single-file python program that is self-contained and can be executed as-is.",
                "No parts of the code should be skipped, don't terminate the code execution before finishing the script.",
                "Data saving requirements:",
                "- Save all plottable data (metrics, losses, predictions, etc.) as numpy arrays using np.save()",
                "- Use the following naming convention for saved files:",
                "  ```python",
                "  # At the start of your code",
                "  experiment_data = {",
                "      'hyperparam_tuning_type_1': {",
                "          'dataset_name_1': {",
                "              'metrics': {'train': [], 'val': []},",
                "              'losses': {'train': [], 'val': []},",
                "              'predictions': [],",
                "              'ground_truth': [],",
                "          },",
                "      },",
                "  }",
                "Make sure to use a filename 'experiment_data.npy' to save the data. Do not use any other filename.",
            ]
        }
        hp_instructions |= agent._prompt_hyperparam_tuning_resp_fmt
        prompt["Instructions"] = hp_instructions
        plan, code = agent.plan_and_code_query(prompt=prompt)
        return Node(
            plan="Hyperparam tuning name: " + hyperparam_idea.name + ".\n" + plan,
            code=code,
            parent=parent_node,
            hyperparam_name=hyperparam_idea.name,
        )

    @staticmethod
    def propose_next_hyperparam_idea(
        *, base_stage1_code: str, tried: List[str], model: str, temperature: float
    ) -> HyperparamTuningIdea:
        hyperparam_tuning_prompt: dict[str, object] = {
            "Introduction": (
                "You are an AI researcher conducting hyperparameter tuning for baseline experiments. "
                "Based on the current implementation and previous hyperparameter tuning attempts (if any), "
                "propose ONE new hyperparameter tuning idea to see if it improves the performance."
                "You should first check if simply training longer (more epochs) improves the performance."
                "Then try tuning common hyperparameters such as learning rate, batch size, etc."
                "Only propose algorithm-specific and/or model-specific hyperparameters after you have tried the above."
            ),
            "Base code you are working on": wrap_code(base_stage1_code),
            "Previous Hyperparam Tuning Attempts": {
                "Has been tried": tried if tried else "Nothing has been tried yet.",
            },
            "Instructions": {
                "Requirements": [
                    "1. Identify ONE specific hyperparameter to tune",
                    "2. Ensure the hyperparameter is different from previous attempts",
                ]
            },
            "Response format": (
                "Your response should start with 'HYPERPARAM NAME: <hyperparam name>' on the first line to represent the name of the hyperparameter."
                "The second line should start with 'DESCRIPTION: <description>', a brief description of what hyperparameter is being tuned and why (3-5 sentences). "
            ),
        }

        retry_count = 0
        retry_limit = 5
        while retry_count < retry_limit:
            response = query(
                system_message=hyperparam_tuning_prompt,
                user_message=None,
                model=model,
                temperature=temperature,
            )
            hyperparam_name, hyperparam_description = parse_keyword_prefix_response(
                str(response), "HYPERPARAM NAME:", "DESCRIPTION:"
            )
            if hyperparam_name and hyperparam_description:
                return HyperparamTuningIdea(
                    name=hyperparam_name, description=hyperparam_description
                )
            retry_count += 1

        return HyperparamTuningIdea(
            name="increase learning rate", description="increase learning rate"
        )

    @staticmethod
    def update_hyperparam_state(
        *, stage_name: str | None, result_node: Node, state_set: set[str]
    ) -> None:
        if not stage_name or not stage_name.startswith("2_"):
            return
        hyperparam_name = result_node.hyperparam_name
        if hyperparam_name is None:
            return
        if not result_node.is_buggy:
            state_set.add(hyperparam_name)

    @staticmethod
    def compute_substage_completion(
        *, goals: str, journal: Journal, cfg: AppConfig
    ) -> tuple[bool, str]:
        best_node = journal.get_best_node()
        if not best_node:
            return False, "No best node found"
        eval_prompt = f"""
        Evaluate if Stage 2 (baseline tuning) sub-stage is complete.

        Evidence:
        - Datasets tested: {best_node.datasets_successfully_tested}
        - Best metric: {best_node.metric.value if best_node.metric is not None else 'N/A'}

        Requirements for completion:
        - {goals}
        """
        spec = FunctionSpec(
            name="evaluate_stage_completion",
            description="Evaluate if a stage/sub-stage is complete",
            json_schema={
                "type": "object",
                "properties": {
                    "is_complete": {"type": "boolean"},
                    "reasoning": {"type": "string"},
                    "missing_criteria": {"type": "array", "items": {"type": "string"}},
                },
                "required": ["is_complete", "reasoning", "missing_criteria"],
            },
        )
        evaluation = query(
            system_message=eval_prompt,
            user_message=None,
            func_spec=spec,
            model=cfg.agent.feedback.model,
            temperature=cfg.agent.feedback.temp,
        )
        if isinstance(evaluation, dict) and evaluation.get("is_complete"):
            return True, str(evaluation.get("reasoning", "sub-stage complete"))
        if isinstance(evaluation, dict):
            missing = ", ".join(evaluation.get("missing_criteria", []))
            return False, "Missing criteria: " + missing
        return False, "Sub-stage not complete"

    @staticmethod
    def compute_stage_completion(*, journal: Journal, cfg: AppConfig) -> tuple[bool, str]:
        best_node = journal.get_best_node()
        if not best_node:
            return False, "No best node found"
        if best_node == journal.nodes[0]:
            return False, "No improvement from base node"
        eval_prompt = f"""
        Evaluate if Stage 2 (baseline tuning) is complete based on the following evidence:

        1. Datasets Tested: {best_node.datasets_successfully_tested}

        Requirements for completion:
        1. Training curves should show stable convergence
        2. Results should be tested on at least two datasets
        3. No major instabilities or issues in the plots

        Provide a detailed evaluation of completion status.
        """
        spec = FunctionSpec(
            name="evaluate_stage_completion",
            description="Evaluate if a stage/sub-stage is complete",
            json_schema={
                "type": "object",
                "properties": {
                    "is_complete": {"type": "boolean"},
                    "reasoning": {"type": "string"},
                    "missing_criteria": {"type": "array", "items": {"type": "string"}},
                },
                "required": ["is_complete", "reasoning", "missing_criteria"],
            },
        )
        evaluation = query(
            system_message=eval_prompt,
            user_message=None,
            func_spec=spec,
            model=cfg.agent.feedback.model,
            temperature=cfg.agent.feedback.temp,
        )
        if isinstance(evaluation, dict) and evaluation.get("is_complete"):
            return True, str(evaluation.get("reasoning", "stage complete"))
        if isinstance(evaluation, dict):
            missing = ", ".join(evaluation.get("missing_criteria", []))
            return False, "Missing criteria: " + missing
        return False, "stage not completed"

    def curate_task_desc(self) -> str:
        return self._context.task_desc

    def evaluate_substage_completion(self) -> tuple[bool, str]:
        return Stage2Tuning.compute_substage_completion(
            goals=self._meta.goals, journal=self._context.journal, cfg=self._context.cfg
        )

    def evaluate_stage_completion(self) -> tuple[bool, str]:
        return Stage2Tuning.compute_stage_completion(
            journal=self._context.journal, cfg=self._context.cfg
        )

    def update_state(self, *, result_node: Node) -> None:
        state_set: set[str] = set()
        Stage2Tuning.update_hyperparam_state(
            stage_name=self._context.stage_name, result_node=result_node, state_set=state_set
        )

    def generate_substage_goal(self) -> tuple[str, str]:
        return self._meta.goals, "first_attempt"
