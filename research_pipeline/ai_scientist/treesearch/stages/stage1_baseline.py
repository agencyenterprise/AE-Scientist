import logging
from typing import ClassVar, Tuple

from ai_scientist.llm import structured_query_with_schema

from ..codex.node_result_contract import NodeResultContractContext
from ..config import Config as AppConfig
from ..journal import Journal
from ..prompts.render import render_text
from ..stage_identifiers import StageIdentifier
from .base import Stage, StageCompletionEvaluation

logger = logging.getLogger(__name__)


class Stage1Baseline(Stage):
    MAIN_STAGE_SLUG: ClassVar[str] = StageIdentifier.STAGE1.slug
    DEFAULT_GOALS: ClassVar[str] = (
        "- Focus on getting basic working implementation\n"
        "- Use a dataset appropriate to the experiment\n"
        "- Aim for basic functional correctness\n"
        '- If you are given "Code To Use", you can directly use it as a starting point.'
    )
    # Memoization cache for substage-completion queries:
    # key -> (is_complete, message)
    _substage_completion_cache: dict[str, tuple[bool, str]] = {}

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
                "Stage1 substage-completion cache HIT for best_node=%s (metric=%s). Goals unchanged.",
                best_node.id[:8],
                metric_val,
            )
            return cached
        logger.debug(
            "Stage1 substage-completion cache MISS for best_node=%s (metric=%s). Invoking LLM.",
            best_node.id[:8],
            metric_val,
        )
        prompt = render_text(
            template_name="stage_completion/stage1_substage.txt.j2",
            context={
                "best_metric_value": (
                    best_node.metric.value if best_node.metric is not None else "N/A"
                ),
                "is_buggy": best_node.is_buggy,
                "goals": goals,
            },
        )
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
                "Stage1 substage-completion result cached for best_node=%s (metric=%s).",
                best_node.id[:8],
                metric_val,
            )
            return result
        missing = ", ".join(evaluation.missing_criteria)
        result = False, "Missing criteria: " + missing
        Stage1Baseline._substage_completion_cache[cache_key] = result
        logger.debug(
            "Stage1 substage-completion result cached (incomplete) for best_node=%s (metric=%s). Missing: %s",
            best_node.id[:8],
            metric_val,
            missing,
        )
        return result

    def evaluate_substage_completion(self) -> Tuple[bool, str]:
        return Stage1Baseline.compute_substage_completion(
            goals=self._meta.goals, journal=self._context.journal, cfg=self._context.cfg
        )

    def evaluate_stage_completion(self) -> Tuple[bool, str]:
        return Stage1Baseline.compute_stage_completion(journal=self._context.journal)

    def reset_skip_state(self) -> None:
        super().reset_skip_state()
        journal = self._context.journal
        total_nodes = len(journal.nodes)
        good_nodes = len(journal.good_nodes)
        logger.info(
            "Stage 1 skip evaluation: total_nodes=%s good_nodes=%s",
            total_nodes,
            good_nodes,
        )
        if journal.good_nodes:
            reason = "Stage 1 has at least one working implementation."
            logger.info("Stage 1 skip allowed: %s", reason)
            self._set_skip_state(can_skip=True, reason=reason)
            return
        reason = "Produce a working baseline implementation before skipping."
        logger.info("Stage 1 skip blocked: %s", reason)
        self._set_skip_state(can_skip=False, reason=reason)


def codex_node_result_contract_prompt_lines() -> list[str]:
    # Stage 1 doesn't require additional node_result fields beyond the common contract.
    return []


def validate_node_result_contract(
    *, node_result: dict[str, object], ctx: NodeResultContractContext
) -> list[str]:
    # Stage 1 does not impose additional constraints beyond the common contract.
    del node_result, ctx
    return []
