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


class Stage2Tuning(Stage):
    MAIN_STAGE_SLUG: ClassVar[str] = StageIdentifier.STAGE2.slug
    DEFAULT_GOALS: ClassVar[str] = (
        "- Change hyperparameters such as learning rate, number of epochs, batch size, etc. to improve the performance\n"
        "- DO NOT change the model architecture from the previous stage\n"
        "- Introduce additional datasets to test robustness.\n"
        "- Research appropriate dataset sources (HuggingFace, Github, academic repositories, etc.) or use datasets specified in the research idea.\n"
    )
    # Memoization caches for completion queries
    # key -> (is_complete, message)
    _substage_completion_cache: dict[str, tuple[bool, str]] = {}
    _stage_completion_cache: dict[str, tuple[bool, str]] = {}

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
                "Stage2 substage-completion cache HIT for best_node=%s (metric=%s).",
                best_node.id[:8],
                metric_val,
            )
            return cached
        logger.debug(
            "Stage2 substage-completion cache MISS for best_node=%s (metric=%s). Invoking LLM.",
            best_node.id[:8],
            metric_val,
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
                "Stage2 substage-completion result cached for best_node=%s (metric=%s).",
                best_node.id[:8],
                metric_val,
            )
            return result
        missing = ", ".join(evaluation.missing_criteria)
        result = False, "Missing criteria: " + missing
        Stage2Tuning._substage_completion_cache[cache_key] = result
        logger.debug(
            "Stage2 substage-completion result cached (incomplete) for best_node=%s (metric=%s). Missing: %s",
            best_node.id[:8],
            metric_val,
            missing,
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
        goals_sig = "stable_convergence;two_datasets;no_training_instabilities"
        cache_key = f"stage=2_stage|id={best_node.id}|metric={metric_val}|goals={goals_sig}"
        cached = Stage2Tuning._stage_completion_cache.get(cache_key)
        if cached is not None:
            logger.debug(
                "Stage2 stage-completion cache HIT for best_node=%s (metric=%s).",
                best_node.id[:8],
                metric_val,
            )
            return cached
        logger.debug(
            "Stage2 stage-completion cache MISS for best_node=%s (metric=%s). Invoking LLM.",
            best_node.id[:8],
            metric_val,
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
                "Stage2 stage-completion result cached for best_node=%s (metric=%s).",
                best_node.id[:8],
                metric_val,
            )
            return result
        missing = ", ".join(evaluation.missing_criteria)
        result = False, "Missing criteria: " + missing
        Stage2Tuning._stage_completion_cache[cache_key] = result
        logger.debug(
            "Stage2 stage-completion result cached (incomplete) for best_node=%s (metric=%s). Missing: %s",
            best_node.id[:8],
            metric_val,
            missing,
        )
        return result

    def evaluate_substage_completion(self) -> Tuple[bool, str]:
        return Stage2Tuning.compute_substage_completion(
            goals=self._meta.goals, journal=self._context.journal, cfg=self._context.cfg
        )

    def evaluate_stage_completion(self) -> Tuple[bool, str]:
        return Stage2Tuning.compute_stage_completion(
            journal=self._context.journal, cfg=self._context.cfg
        )

    def reset_skip_state(self) -> None:
        super().reset_skip_state()
        journal = self._context.journal
        best_node = journal.get_best_node()
        total_nodes = len(journal.nodes)
        best_node_id = best_node.id[:8] if best_node else "None"
        logger.info(
            "Stage 2 skip evaluation: total_nodes=%s best_node=%s good_nodes=%s",
            total_nodes,
            best_node_id,
            len(journal.good_nodes),
        )
        if not best_node:
            reason = "Stage 2 skipping requires a best node."
            logger.info("Stage 2 skip blocked: %s", reason)
            self._set_skip_state(can_skip=False, reason=reason)
            return
        reason = "Stage 2 has a working node."
        logger.info("Stage 2 skip allowed: %s (best_node=%s)", reason, best_node_id)
        self._set_skip_state(can_skip=True, reason=reason)


def codex_node_result_contract_prompt_lines() -> list[str]:
    return [
        "- Stage-specific required fields:",
        "  - Stage 2: `hyperparam_name` must be a non-empty string.",
    ]


def validate_node_result_contract(
    *, node_result: dict[str, object], ctx: NodeResultContractContext
) -> list[str]:
    errors: list[str] = []
    del ctx
    if not is_non_empty_string(value=node_result.get("hyperparam_name")):
        errors.append("Stage2 requires hyperparam_name to be a non-empty string")
    return errors
