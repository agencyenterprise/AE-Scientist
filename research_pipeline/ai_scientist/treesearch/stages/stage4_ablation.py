from __future__ import annotations

import logging
from typing import ClassVar, Tuple

from ai_scientist.llm import structured_query_with_schema

from ..journal import Journal
from ..node_result_contract import NodeResultContractContext, is_non_empty_string
from ..stage_identifiers import StageIdentifier
from ..utils.config import Config as AppConfig
from .base import Stage, StageCompletionEvaluation

logger = logging.getLogger(__name__)


class Stage4Ablation(Stage):
    MAIN_STAGE_SLUG: ClassVar[str] = StageIdentifier.STAGE4.slug
    DEFAULT_GOALS: ClassVar[str] = (
        "- Conduct systematic component analysis that reveals the contribution of each part\n"
        "- Use the same datasets you used from the previous stage"
    )
    # Memoization cache for substage-completion queries:
    # key -> (is_complete, message)
    _substage_completion_cache: dict[str, tuple[bool, str]] = {}

    def evaluate_substage_completion(self) -> Tuple[bool, str]:
        return Stage4Ablation.compute_substage_completion(
            goals=self._meta.goals, journal=self._context.journal, cfg=self._context.cfg
        )

    def evaluate_stage_completion(self) -> Tuple[bool, str]:
        return Stage4Ablation.compute_stage_completion()

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
                "Stage4 substage-completion cache HIT for best_node=%s (metric=%s).",
                best_node.id[:8],
                metric_val,
            )
            return cached
        logger.debug(
            "Stage4 substage-completion cache MISS for best_node=%s (metric=%s). Invoking LLM.",
            best_node.id[:8],
            metric_val,
        )
        prompt = f"""
        Evaluate if the ablation sub-stage is complete given the goals:
        - {goals}

        Consider whether the ablation variations produce consistent and interpretable differences.
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
            Stage4Ablation._substage_completion_cache[cache_key] = result
            logger.debug(
                "Stage4 substage-completion result cached for best_node=%s (metric=%s).",
                best_node.id[:8],
                metric_val,
            )
            return result
        missing = ", ".join(evaluation.missing_criteria)
        result = False, "Missing criteria: " + missing
        Stage4Ablation._substage_completion_cache[cache_key] = result
        logger.debug(
            "Stage4 substage-completion result cached (incomplete) for best_node=%s (metric=%s). Missing: %s",
            best_node.id[:8],
            metric_val,
            missing,
        )
        return result

    @staticmethod
    def compute_stage_completion() -> tuple[bool, str]:
        return False, "stage not completed"

    def reset_skip_state(self) -> None:
        super().reset_skip_state()
        journal = self._context.journal
        good_nodes = len(journal.good_nodes)
        logger.info(
            "Stage 4 skip evaluation: total_nodes=%s good_nodes=%s",
            len(journal.nodes),
            good_nodes,
        )
        best_node = journal.get_best_node()
        if best_node and not best_node.is_buggy:
            reason = "Stage 4 has at least one ablation-ready node."
            logger.info("Stage 4 skip allowed: %s", reason)
            self._set_skip_state(can_skip=True, reason=reason)
            return
        if best_node and best_node.is_buggy:
            reason = "Best node is buggy; fix execution before skipping."
        else:
            reason = "Run at least one ablation node before skipping final stage."
        logger.info("Stage 4 skip blocked: %s", reason)
        self._set_skip_state(can_skip=False, reason=reason)


def codex_node_result_contract_prompt_lines() -> list[str]:
    return [
        "- Stage-specific required fields:",
        "  - Stage 4: `ablation_name` must be a non-empty string.",
        "  - Stage 4 (plotting stage):",
        "    - If `is_buggy_plots` is false, you MUST write at least 1 `.png` plot into `./working/`.",
        "    - If `is_buggy_plots` is false, you MUST provide at least 1 `plot_analyses` entry with an `analysis` string.",
        "    - If `is_buggy_plots` is false, you MUST provide a non-empty `vlm_feedback_summary` list.",
    ]


def validate_node_result_contract(
    *, node_result: dict[str, object], ctx: NodeResultContractContext
) -> list[str]:
    errors: list[str] = []
    if not is_non_empty_string(value=node_result.get("ablation_name")):
        errors.append("Stage4 requires ablation_name to be a non-empty string")

    is_buggy_plots = node_result.get("is_buggy_plots")
    if is_buggy_plots is False:
        if ctx.working_png_count <= 0:
            errors.append(
                "Stage4 requires at least one .png in ./working when is_buggy_plots=false"
            )
        plot_analyses_val = node_result.get("plot_analyses")
        if isinstance(plot_analyses_val, list) and len(plot_analyses_val) == 0:
            errors.append("Stage4 requires plot_analyses to be non-empty when is_buggy_plots=false")
        vlm_feedback_summary_val = node_result.get("vlm_feedback_summary")
        if isinstance(vlm_feedback_summary_val, list) and not any(
            is_non_empty_string(value=x) for x in vlm_feedback_summary_val
        ):
            errors.append(
                "Stage4 requires vlm_feedback_summary to be non-empty when is_buggy_plots=false"
            )
    return errors
