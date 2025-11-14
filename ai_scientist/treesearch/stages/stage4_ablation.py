import logging
from typing import List, Protocol, Tuple

from ai_scientist.llm.query import FunctionSpec, query

from ..journal import Journal, Node
from ..response_parsing import parse_keyword_prefix_response
from ..types import PromptType
from ..utils.config import Config as AppConfig
from ..utils.response import wrap_code
from .base import Stage

logger = logging.getLogger(__name__)


class AblationIdea:
    def __init__(self, name: str, description: str):
        self.name = name
        self.description = description


class SupportsStage4Agent(Protocol):
    def plan_and_code_query(self, *, prompt: PromptType, retries: int = 3) -> Tuple[str, str]:
        pass

    @property
    def _prompt_ablation_resp_fmt(self) -> dict[str, str]:
        pass


class Stage4Ablation(Stage):
    MAIN_STAGE_SLUG = "ablation_studies"
    DEFAULT_GOALS = (
        "- Conduct systematic component analysis that reveals the contribution of each part\n"
        "- Use the same datasets you used from the previous stage"
    )
    # Memoization cache for substage-completion queries:
    # key -> (is_complete, message)
    _substage_completion_cache: dict[str, tuple[bool, str]] = {}

    @staticmethod
    def build_ablation_node(
        *, agent: SupportsStage4Agent, parent_node: Node, ablation_idea: AblationIdea
    ) -> Node:
        prompt: PromptType = {
            "Introduction": (
                "You are an experienced AI researcher. You are provided with a previously developed "
                "baseline implementation. Your task is to implement the ablation study for the following idea: "
                + ablation_idea.name
                + ". "
                + ablation_idea.description
            ),
            "Base code you are working on": wrap_code(parent_node.code),
            "Instructions": {},
        }
        abl_instructions: dict[str, str | list[str]] = {}
        abl_instructions |= {
            "Implementation guideline": [
                "The code should be a single-file python program that is self-contained and can be executed as-is.",
                "No parts of the code should be skipped, don't terminate the code execution before finishing the script.",
                "Data saving requirements:",
                "- Save all plottable data (metrics, losses, predictions, etc.) as numpy arrays using np.save()",
                "- Use the following naming convention for saved files:",
                "  ```python",
                "  # At the start of your code",
                "  experiment_data = {",
                "      'ablation_type_1': {",
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
        abl_instructions |= agent._prompt_ablation_resp_fmt
        prompt["Instructions"] = abl_instructions
        plan, code = agent.plan_and_code_query(prompt=prompt)
        logger.debug("----- LLM code start (stage4 ablation) -----")
        logger.debug(code)
        logger.debug("----- LLM code end (stage4 ablation) -----")
        return Node(
            plan="Ablation name: " + ablation_idea.name + ".\n" + plan,
            code=code,
            parent=parent_node,
            ablation_name=ablation_idea.name,
        )

    @staticmethod
    def propose_next_ablation_idea(
        *, base_stage3_code: str, completed: List[str], model: str, temperature: float
    ) -> AblationIdea:
        ablation_prompt: dict[str, object] = {
            "Introduction": (
                "You are an AI researcher conducting ablation studies. "
                "Based on the current implementation and previous ablations (if any), "
                "propose ONE new ablation study that tests a different aspect of the model."
            ),
            "Base code you are working on": wrap_code(base_stage3_code),
            "Previous Ablations": {
                "Has been tried": (completed if completed else "Nothing has been tried yet."),
            },
            "Instructions": {
                "Requirements": [
                    "1. Identify ONE specific component/feature to ablate",
                    "2. Ensure the ablation is different from previous completed or running attempts",
                    "3. The ablation should be a new idea, not a variation of previous ideas",
                    "4. If you have only used a single synthetic dataset throughout the experiment, one of your ablations should be to use multiple synthetic datasets (at least 3 different datasets)",
                ]
            },
            "Response format": (
                "Your response should start with 'ABLATION NAME: <ablation name>' on the first line to represent the name of the ablation."
                "The second line should start with 'ABLATION DESCRIPTION: <description>', a brief description of what component is being ablated and why (3-5 sentences), "
            ),
        }

        retry_count = 0
        retry_limit = 5
        while retry_count < retry_limit:
            response = query(
                system_message=ablation_prompt,
                user_message=None,
                model=model,
                temperature=temperature,
            )
            ablation_name, ablation_description = parse_keyword_prefix_response(
                str(response), "ABLATION NAME:", "ABLATION DESCRIPTION:"
            )
            if ablation_name and ablation_description:
                return AblationIdea(name=ablation_name, description=ablation_description)
            retry_count += 1
        return AblationIdea(name="add one more layer", description="add one more layer")

    @staticmethod
    def update_ablation_state(
        *, stage_name: str | None, result_node: Node, state_set: set[str]
    ) -> None:
        if not stage_name or not stage_name.startswith("4_"):
            return
        ablation_name = result_node.ablation_name
        if ablation_name is None:
            return
        if not result_node.is_buggy:
            state_set.add(ablation_name)

    @staticmethod
    def compute_substage_completion(
        *, goals: str, journal: Journal, cfg: AppConfig
    ) -> tuple[bool, str]:
        best_node = journal.get_best_node()
        if not best_node:
            return False, "No best node found"
        metric_val = best_node.metric.value if best_node.metric is not None else None
        cache_key = f"stage=4_substage|id={best_node.id}|metric={metric_val}|goals={goals}"
        cached = Stage4Ablation._substage_completion_cache.get(cache_key)
        if cached is not None:
            logger.debug(
                f"Stage4 substage-completion cache HIT for best_node={best_node.id[:8]} "
                f"(metric={metric_val}). Goals unchanged. Skipping LLM."
            )
            return cached
        logger.debug(
            f"Stage4 substage-completion cache MISS for best_node={best_node.id[:8]} "
            f"(metric={metric_val}). Goals changed or new best node. Invoking LLM."
        )
        prompt = f"""
        Evaluate if the ablation sub-stage is complete given the goals:
        - {goals}

        Consider whether the ablation variations produce consistent and interpretable differences.
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
            system_message=prompt,
            user_message=None,
            func_spec=spec,
            model=cfg.agent.feedback.model,
            temperature=cfg.agent.feedback.temp,
        )
        if isinstance(evaluation, dict) and evaluation.get("is_complete"):
            result = True, str(evaluation.get("reasoning", "sub-stage complete"))
            Stage4Ablation._substage_completion_cache[cache_key] = result
            logger.debug(
                f"Stage4 substage-completion result cached for best_node={best_node.id[:8]} "
                f"(metric={metric_val})."
            )
            return result
        if isinstance(evaluation, dict):
            missing = ", ".join(evaluation.get("missing_criteria", []))
            result = False, "Missing criteria: " + missing
            Stage4Ablation._substage_completion_cache[cache_key] = result
            logger.debug(
                f"Stage4 substage-completion result cached (incomplete) for best_node={best_node.id[:8]} "
                f"(metric={metric_val}). Missing: {missing}"
            )
            return result
        result = False, "Sub-stage not complete"
        Stage4Ablation._substage_completion_cache[cache_key] = result
        logger.debug(
            f"Stage4 substage-completion result cached (non-dict fallback) for best_node={best_node.id[:8]} "
            f"(metric={metric_val})."
        )
        return result

    @staticmethod
    def compute_stage_completion(*, journal: Journal) -> tuple[bool, str]:
        return False, "stage not completed"

    def curate_task_desc(self) -> str:
        return self._context.task_desc

    def evaluate_substage_completion(self) -> tuple[bool, str]:
        return Stage4Ablation.compute_substage_completion(
            goals=self._meta.goals, journal=self._context.journal, cfg=self._context.cfg
        )

    def evaluate_stage_completion(self) -> tuple[bool, str]:
        return Stage4Ablation.compute_stage_completion(journal=self._context.journal)

    def update_state(self, *, result_node: Node) -> None:
        state_set: set[str] = set()
        Stage4Ablation.update_ablation_state(
            stage_name=self._context.stage_name, result_node=result_node, state_set=state_set
        )

    def generate_substage_goal(self) -> tuple[str, str]:
        return self._meta.goals, "first_attempt"
