import logging
from typing import ClassVar, Tuple

from ai_scientist.llm import structured_query_with_schema

from ..codex.node_result_contract import NodeResultContractContext
from ..config import Config as AppConfig
from ..journal import Journal, Node
from ..prompts.render import render_lines, render_text
from ..stage_identifiers import StageIdentifier
from .base import Stage, StageCompletionEvaluation

logger = logging.getLogger(__name__)


class Stage3Plotting(Stage):
    MAIN_STAGE_SLUG: ClassVar[str] = StageIdentifier.STAGE3.slug
    DEFAULT_GOALS: ClassVar[str] = (
        "- Explore novel improvements\n"
        "- Come up with experiments to reveal new insights\n"
        "- Be creative and think outside the box\n"
        "- Test your models on multiple datasets from appropriate sources to demonstrate generalization.\n"
        "- Use dataset sizes appropriate to the experiment. Usually THREE datasets are enough."
    )
    # Memoization cache for substage-completion queries:
    # key -> (is_complete, message)
    _substage_completion_cache: dict[str, tuple[bool, str]] = {}

    def evaluate_substage_completion(self) -> Tuple[bool, str]:
        return Stage3Plotting.compute_substage_completion(
            goals=self._meta.goals,
            journal=self._context.journal,
            cfg=self._context.cfg,
        )

    def evaluate_stage_completion(self) -> Tuple[bool, str]:
        return Stage3Plotting.compute_stage_completion(
            journal=self._context.journal,
            cfg=self._context.cfg,
            max_stage3_iterations=self._meta.max_iterations,
        )

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
                "Stage3 substage-completion cache HIT for best_node=%s (metric=%s).",
                best_node.id[:8],
                metric_val,
            )
            return cached
        logger.debug(
            "Stage3 substage-completion cache MISS for best_node=%s (metric=%s). Invoking LLM.",
            best_node.id[:8],
            metric_val,
        )
        vlm_feedback = Stage3Plotting.parse_vlm_feedback(node=best_node)
        eval_prompt = render_text(
            template_name="stage_completion/stage3_substage.txt.j2",
            context={"vlm_feedback": vlm_feedback, "goals": goals},
        )
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
                "Stage3 substage-completion result cached for best_node=%s (metric=%s).",
                best_node.id[:8],
                metric_val,
            )
            return result
        missing = ", ".join(evaluation.missing_criteria)
        result = False, "Missing criteria: " + missing
        Stage3Plotting._substage_completion_cache[cache_key] = result
        logger.debug(
            "Stage3 substage-completion result cached (incomplete) for best_node=%s (metric=%s). Missing: %s",
            best_node.id[:8],
            metric_val,
            missing,
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

    def reset_skip_state(self) -> None:
        super().reset_skip_state()
        journal = self._context.journal
        best_node = journal.get_best_node()
        total_nodes = len(journal.nodes)
        best_node_id = best_node.id[:8] if best_node else "None"
        logger.info(
            "Stage 3 skip evaluation: total_nodes=%s best_node=%s good_nodes=%s",
            total_nodes,
            best_node_id,
            len(journal.good_nodes),
        )
        if not best_node:
            reason = "Stage 3 skipping requires a best node."
            logger.info("Stage 3 skip blocked: %s", reason)
            self._set_skip_state(can_skip=False, reason=reason)
            return
        if best_node.is_buggy or best_node.is_buggy_plots:
            reason = "Best node must pass execution and plot validation."
            logger.info(
                "Stage 3 skip blocked: %s (is_buggy=%s is_buggy_plots=%s)",
                reason,
                best_node.is_buggy,
                best_node.is_buggy_plots,
            )
            self._set_skip_state(can_skip=False, reason=reason)
            return
        if not best_node.plots or not best_node.plot_paths:
            reason = "Generate at least one plot artifact before skipping Stage 3."
            logger.info(
                "Stage 3 skip blocked: %s (plots=%s plot_paths=%s)",
                reason,
                len(best_node.plots or []),
                len(best_node.plot_paths or []),
            )
            self._set_skip_state(can_skip=False, reason=reason)
            return
        reason = "Stage 3 has plot artifacts ready for downstream stages."
        logger.info("Stage 3 skip allowed: %s (best_node=%s)", reason, best_node_id)
        self._set_skip_state(can_skip=True, reason=reason)


def codex_node_result_contract_prompt_lines() -> list[str]:
    return render_lines(template_name="contracts/stage3.txt.j2", context={})


def validate_node_result_contract(
    *, node_result: dict[str, object], ctx: NodeResultContractContext
) -> list[str]:
    errors: list[str] = []
    is_buggy_plots = node_result.get("is_buggy_plots")
    if is_buggy_plots is False:
        if ctx.working_png_count <= 0:
            errors.append(
                "Stage3 requires at least one .png in ./working when is_buggy_plots=false"
            )
    return errors
