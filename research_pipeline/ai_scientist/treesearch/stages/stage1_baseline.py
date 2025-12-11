import logging

from ai_scientist.llm import structured_query_with_schema

from ..codegen_agent import MinimalAgent
from ..journal import Journal, Node
from ..types import PromptType
from ..utils.config import Config as AppConfig
from .base import Stage, StageCompletionEvaluation

logger = logging.getLogger(__name__)


class Stage1Baseline(Stage):
    MAIN_STAGE_SLUG = "initial_implementation"
    DEFAULT_GOALS = (
        "- Focus on getting basic working implementation\n"
        "- Use a dataset appropriate to the experiment\n"
        "- Aim for basic functional correctness\n"
        '- If you are given "Code To Use", you can directly use it as a starting point.'
    )
    # Memoization cache for substage-completion queries:
    # key -> (is_complete, message)
    _substage_completion_cache: dict[str, tuple[bool, str]] = {}

    @staticmethod
    def draft(agent: "MinimalAgent") -> Node:
        """Stage 1: Generate initial baseline implementation."""
        prompt: PromptType = {
            "Introduction": (
                "You are an AI researcher who is looking to publish a paper that will contribute significantly to the field."
                "Your first task is to write a python code to implement a solid baseline based on your research idea provided below, "
                "from data preparation to model training, as well as evaluation and visualization. "
                "Focus on getting a simple but working implementation first, before any sophisticated improvements. "
                "We will explore more advanced variations in later stages."
            ),
            "Research idea": agent.task_desc,
            "Memory": agent.memory_summary if agent.memory_summary else "",
            "Instructions": {},
        }

        instructions: dict[str, str | list[str]] = {}
        instructions |= {
            "Experiment design sketch guideline": [
                "This first experiment design should be relatively simple, without extensive hyper-parameter optimization.",
                "Take the Memory section into consideration when proposing the design. ",
                "The solution sketch should be 6-10 sentences. ",
                "Don't suggest to do EDA.",
                "Prioritize using real public datasets (e.g., from HuggingFace) when they suit the task, and only fall back to synthetic data if no suitable dataset is available or synthetic generation is essential to the proposed experiment.",
                "",
            ],
            "Evaluation Metric(s)": agent.evaluation_metrics or "",
        }
        instructions |= agent.prompt_impl_guideline
        instructions |= agent._prompt_environment
        prompt["Instructions"] = instructions

        logger.debug("MinimalAgent: Getting plan and code")
        plan, code = agent.plan_and_code_query(prompt=prompt)
        logger.debug("MinimalAgent: Draft complete")
        logger.debug("----- LLM code start -----")
        logger.debug(code)
        logger.debug("----- LLM code end -----")
        logger.info(f"✓ Generated {len(code)} characters of code")
        return Node(plan=plan, code=code)

    @staticmethod
    def compute_stage_completion(*, journal: Journal) -> tuple[bool, str]:
        if len(journal.good_nodes) > 0:
            return True, "Found working implementation"
        return False, "Working implementation not found yet"

    @staticmethod
    def compute_substage_completion(
        *, goals: str, journal: Journal, cfg: AppConfig
    ) -> tuple[bool, str]:
        best_node = journal.get_best_node()
        if not best_node:
            return False, "No best node found"
        metric_val = best_node.metric.value if best_node.metric is not None else None
        cache_key = f"stage=1_substage|id={best_node.id}|metric={metric_val}|goals={goals}"
        cached = Stage1Baseline._substage_completion_cache.get(cache_key)
        if cached is not None:
            logger.debug(
                f"Stage1 substage-completion cache HIT for best_node={best_node.id[:8]} "
                f"(metric={metric_val}). Goals unchanged. Skipping LLM."
            )
            return cached
        logger.debug(
            f"Stage1 substage-completion cache MISS for best_node={best_node.id[:8]} "
            f"(metric={metric_val}). Goals changed or new best node. Invoking LLM."
        )
        prompt = f"""
        Evaluate if the current sub-stage is complete.

        Evidence:
        - Best metric: {best_node.metric.value if best_node.metric is not None else 'N/A'}
        - Is buggy: {best_node.is_buggy}

        Requirements for completion:
        - {goals}
        """
        evaluation = structured_query_with_schema(
            system_message=prompt,
            user_message=None,
            model=cfg.agent.feedback.model,
            temperature=cfg.agent.feedback.temperature,
            schema_class=StageCompletionEvaluation,
        )
        if evaluation.is_complete:
            result = True, str(evaluation.reasoning or "sub-stage complete")
            Stage1Baseline._substage_completion_cache[cache_key] = result
            logger.debug(
                f"Stage1 substage-completion result cached for best_node={best_node.id[:8]} "
                f"(metric={metric_val})."
            )
            return result
        missing = ", ".join(evaluation.missing_criteria)
        result = False, "Missing criteria: " + missing
        Stage1Baseline._substage_completion_cache[cache_key] = result
        logger.debug(
            f"Stage1 substage-completion result cached (incomplete) for best_node={best_node.id[:8]} "
            f"(metric={metric_val}). Missing: {missing}"
        )
        return result

    def evaluate_substage_completion(self) -> tuple[bool, str]:
        return Stage1Baseline.compute_substage_completion(
            goals=self._meta.goals, journal=self._context.journal, cfg=self._context.cfg
        )

    def evaluate_stage_completion(self) -> tuple[bool, str]:
        return Stage1Baseline.compute_stage_completion(journal=self._context.journal)
