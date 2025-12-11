import logging
from typing import List, Protocol, Tuple

from pydantic import BaseModel, Field

from ai_scientist.llm import structured_query_with_schema

from ..journal import Journal, Node
from ..types import PromptType
from ..utils.config import Config as AppConfig
from ..utils.response import wrap_code
from .base import Stage, StageCompletionEvaluation

logger = logging.getLogger(__name__)


class HyperparamTuningIdea(BaseModel):
    name: str = Field(
        description=(
            "A short, descriptive name for the proposed hyperparameter tuning idea. "
            "It should clearly identify which hyperparameter is being tuned."
        ),
    )
    description: str = Field(
        description=(
            "A brief description (3-5 sentences) of which hyperparameter is being tuned, how it will be changed, "
            "and why this change is expected to improve performance."
        ),
    )


class SupportsStage2Agent(Protocol):
    def plan_and_code_query(self, *, prompt: PromptType, retries: int = 3) -> Tuple[str, str]:
        pass


class Stage2Tuning(Stage):
    MAIN_STAGE_SLUG = "baseline_tuning"
    DEFAULT_GOALS = (
        "- Change hyperparameters such as learning rate, number of epochs, batch size, etc. to improve the performance\n"
        "- DO NOT change the model architecture from the previous stage\n"
        "- Introduce additional datasets from HuggingFace to test the model. Use dataset sizes appropriate to the experiment. Use streaming=True for very large datasets."
    )
    # Memoization caches for completion queries
    # key -> (is_complete, message)
    _substage_completion_cache: dict[str, tuple[bool, str]] = {}
    _stage_completion_cache: dict[str, tuple[bool, str]] = {}

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
        prompt["Instructions"] = hp_instructions
        plan, code = agent.plan_and_code_query(prompt=prompt)
        logger.debug("----- LLM code start (stage2 tuning) -----")
        logger.debug(code)
        logger.debug("----- LLM code end (stage2 tuning) -----")
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
                    "1. Identify ONE specific hyperparameter to tune.",
                    "2. Ensure the hyperparameter is different from previous attempts.",
                ]
            },
        }

        retry_count = 0
        retry_limit = 5
        while retry_count < retry_limit:
            try:
                result = structured_query_with_schema(
                    system_message=hyperparam_tuning_prompt,
                    model=model,
                    temperature=temperature,
                    schema_class=HyperparamTuningIdea,
                )
            except Exception:
                retry_count += 1
                continue

            name = result.name.strip()
            description = result.description.strip()
            if name and description:
                return HyperparamTuningIdea(name=name, description=description)

            retry_count += 1

        return HyperparamTuningIdea(
            name="increase learning rate", description="increase learning rate"
        )

    @staticmethod
    def update_hyperparam_state(*, stage_name: str, result_node: Node, state_set: set[str]) -> None:
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
        metric_val = best_node.metric.value if best_node.metric is not None else None
        cache_key = f"stage=2_substage|id={best_node.id}|metric={metric_val}|goals={goals}"
        cached = Stage2Tuning._substage_completion_cache.get(cache_key)
        if cached is not None:
            logger.debug(
                f"Stage2 substage-completion cache HIT for best_node={best_node.id[:8]} "
                f"(metric={metric_val}). Goals unchanged. Skipping LLM."
            )
            return cached
        logger.debug(
            f"Stage2 substage-completion cache MISS for best_node={best_node.id[:8]} "
            f"(metric={metric_val}). Goals changed or new best node. Invoking LLM."
        )
        eval_prompt = f"""
        Evaluate if Stage 2 (baseline tuning) sub-stage is complete.

        Evidence:
        - Datasets tested: {best_node.datasets_successfully_tested}
        - Best metric: {best_node.metric.value if best_node.metric is not None else 'N/A'}

        Requirements for completion:
        - {goals}
        """
        evaluation = structured_query_with_schema(
            system_message=eval_prompt,
            user_message=None,
            model=cfg.agent.feedback.model,
            temperature=cfg.agent.feedback.temperature,
            schema_class=StageCompletionEvaluation,
        )
        if evaluation.is_complete:
            result = True, str(evaluation.reasoning or "sub-stage complete")
            Stage2Tuning._substage_completion_cache[cache_key] = result
            logger.debug(
                f"Stage2 substage-completion result cached for best_node={best_node.id[:8]} "
                f"(metric={metric_val})."
            )
            return result
        missing = ", ".join(evaluation.missing_criteria)
        result = False, "Missing criteria: " + missing
        Stage2Tuning._substage_completion_cache[cache_key] = result
        logger.debug(
            f"Stage2 substage-completion result cached (incomplete) for best_node={best_node.id[:8]} "
            f"(metric={metric_val}). Missing: {missing}"
        )
        return result

    @staticmethod
    def compute_stage_completion(*, journal: Journal, cfg: AppConfig) -> tuple[bool, str]:
        best_node = journal.get_best_node()
        if not best_node:
            return False, "No best node found"
        if best_node == journal.nodes[0]:
            return False, "No improvement from base node"
        metric_val = best_node.metric.value if best_node.metric is not None else None
        # Static requirement goals for Stage 2 completion encoded as a short signature
        goals_sig = "stable_convergence;two_datasets;no_training_instabilities"
        cache_key = f"stage=2_stage|id={best_node.id}|metric={metric_val}|goals={goals_sig}"
        cached = Stage2Tuning._stage_completion_cache.get(cache_key)
        if cached is not None:
            logger.debug(
                f"Stage2 stage-completion cache HIT for best_node={best_node.id[:8]} "
                f"(metric={metric_val}). Requirements unchanged. Skipping LLM."
            )
            return cached
        logger.debug(
            f"Stage2 stage-completion cache MISS for best_node={best_node.id[:8]} "
            f"(metric={metric_val}). Requirements changed or new best node. Invoking LLM."
        )
        eval_prompt = f"""
        Evaluate if Stage 2 (baseline tuning) is complete based on the following evidence:

        1. Datasets Tested: {best_node.datasets_successfully_tested}

        Requirements for completion:
        1. Training dynamics (metrics/loss curves) should show stable convergence
        2. Results should be tested on at least two datasets
        3. There should be no clear signs of training instabilities or divergence in the reported metrics

        Provide a detailed evaluation of completion status.
        """
        evaluation = structured_query_with_schema(
            system_message=eval_prompt,
            user_message=None,
            model=cfg.agent.feedback.model,
            temperature=cfg.agent.feedback.temperature,
            schema_class=StageCompletionEvaluation,
        )
        if evaluation.is_complete:
            result = True, str(evaluation.reasoning or "stage complete")
            Stage2Tuning._stage_completion_cache[cache_key] = result
            logger.debug(
                f"Stage2 stage-completion result cached for best_node={best_node.id[:8]} "
                f"(metric={metric_val})."
            )
            return result
        missing = ", ".join(evaluation.missing_criteria)
        result = False, "Missing criteria: " + missing
        Stage2Tuning._stage_completion_cache[cache_key] = result
        logger.debug(
            f"Stage2 stage-completion result cached (incomplete) for best_node={best_node.id[:8]} "
            f"(metric={metric_val}). Missing: {missing}"
        )
        return result

    def evaluate_substage_completion(self) -> tuple[bool, str]:
        return Stage2Tuning.compute_substage_completion(
            goals=self._meta.goals, journal=self._context.journal, cfg=self._context.cfg
        )

    def evaluate_stage_completion(self) -> tuple[bool, str]:
        return Stage2Tuning.compute_stage_completion(
            journal=self._context.journal, cfg=self._context.cfg
        )
