import logging

from ai_scientist.llm import structured_query_with_schema

from ..journal import Journal, Node
from ..utils.config import Config as AppConfig
from .base import Stage, StageCompletionEvaluation

logger = logging.getLogger(__name__)


class Stage3Plotting(Stage):
    MAIN_STAGE_SLUG = "creative_research"
    DEFAULT_GOALS = (
        "- Explore novel improvements\n"
        "- Come up with experiments to reveal new insights\n"
        "- Be creative and think outside the box\n"
        "- Test your models on multiple HuggingFace datasets to demonstrate generalization. Use dataset sizes appropriate to the experiment. Usually THREE datasets are enough."
    )
    # Memoization cache for substage-completion queries:
    # key -> (is_complete, message)
    _substage_completion_cache: dict[str, tuple[bool, str]] = {}

    @staticmethod
    def parse_vlm_feedback(*, node: Node) -> str:
        if len(node.plot_analyses) > 0:
            first_analysis = node.plot_analyses[0]
            analysis_text = (
                str(first_analysis.get("analysis", ""))
                if isinstance(first_analysis, dict)
                else str(first_analysis)
            )
            feedback = f"Plot analyses: {analysis_text}\n"
        else:
            feedback = "No plot analyses found\n"
        feedback += f"VLM Feedback Summary: {node.vlm_feedback_summary}\n"
        return feedback

    @staticmethod
    def compute_substage_completion(
        *, goals: str, journal: Journal, cfg: AppConfig
    ) -> tuple[bool, str]:
        best_node = journal.get_best_node()
        if not best_node:
            return False, "No best node found"
        metric_val = best_node.metric.value if best_node.metric is not None else None
        cache_key = f"stage=3_substage|id={best_node.id}|metric={metric_val}|goals={goals}"
        cached = Stage3Plotting._substage_completion_cache.get(cache_key)
        if cached is not None:
            logger.debug(
                f"Stage3 substage-completion cache HIT for best_node={best_node.id[:8]} "
                f"(metric={metric_val}). Goals unchanged. Skipping LLM."
            )
            return cached
        logger.debug(
            f"Stage3 substage-completion cache MISS for best_node={best_node.id[:8]} "
            f"(metric={metric_val}). Goals changed or new best node. Invoking LLM."
        )
        vlm_feedback = Stage3Plotting.parse_vlm_feedback(node=best_node)
        eval_prompt = f"""
        Evaluate if the current sub-stage is complete based on the following evidence:
        1. Figure Analysis:
        {vlm_feedback}

        Requirements for completion:
        - {goals}

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
            result = True, str(evaluation.reasoning or "sub-stage complete")
            Stage3Plotting._substage_completion_cache[cache_key] = result
            logger.debug(
                f"Stage3 substage-completion result cached for best_node={best_node.id[:8]} "
                f"(metric={metric_val})."
            )
            return result
        missing = ", ".join(evaluation.missing_criteria)
        result = False, "Missing criteria: " + missing
        Stage3Plotting._substage_completion_cache[cache_key] = result
        logger.debug(
            f"Stage3 substage-completion result cached (incomplete) for best_node={best_node.id[:8]} "
            f"(metric={metric_val}). Missing: {missing}"
        )
        return result

    @staticmethod
    def compute_stage_completion(
        *, journal: Journal, cfg: AppConfig, max_stage3_iterations: int
    ) -> tuple[bool, str]:
        best_node = journal.get_best_node()
        if not best_node:
            return False, "No best node found"
        if best_node == journal.nodes[0]:
            return False, "No improvement from base node"
        exec_time = best_node.exec_time if best_node.exec_time is not None else 0.0
        exec_time_minutes = exec_time / 60
        if len(journal.nodes) > (max_stage3_iterations / 2):
            if exec_time_minutes < cfg.exec.timeout / 60 / 2:
                exec_time_feedback = (
                    f"Implementation works but runs too quickly ({exec_time_minutes:.2f} minutes). "
                    "Scale up the experiment by increasing epochs, using a larger model, or bigger datasets."
                )
                if journal.nodes:
                    journal.nodes[-1].exec_time_feedback = exec_time_feedback
                return False, exec_time_feedback
        return False, "stage not completed"

    def evaluate_substage_completion(self) -> tuple[bool, str]:
        return Stage3Plotting.compute_substage_completion(
            goals=self._meta.goals,
            journal=self._context.journal,
            cfg=self._context.cfg,
        )

    def evaluate_stage_completion(self) -> tuple[bool, str]:
        return Stage3Plotting.compute_stage_completion(
            journal=self._context.journal,
            cfg=self._context.cfg,
            max_stage3_iterations=self._meta.max_iterations,
        )
