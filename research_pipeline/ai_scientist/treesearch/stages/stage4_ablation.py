import logging
from typing import ClassVar, Tuple

from pydantic import BaseModel, Field

from ai_scientist.llm import structured_query_with_schema

from ..codex.node_result_contract import NodeResultContractContext, is_non_empty_string
from ..config import Config as AppConfig
from ..journal import Journal
from ..prompts.render import render_lines, render_text
from ..stage_identifiers import StageIdentifier
from .base import Stage, StageCompletionEvaluation

logger = logging.getLogger(__name__)


class AblationIdea(BaseModel):
    name: str = Field(
        description=(
            "A short, descriptive name for the proposed ablation study. "
            "It should clearly identify which component/feature is being ablated."
        ),
    )
    description: str = Field(
        description=(
            "A brief description (3-5 sentences) of what component/feature is being ablated and why. "
            "Explain the motivation and what the ablation is expected to reveal about the model."
        ),
    )


def propose_next_ablation_idea(
    *, base_code: str, tried: list[str], model: str, temperature: float
) -> AblationIdea:
    """
    Stage 4 (ablation): propose ONE new ablation idea, avoiding repeats.
    This is harness-owned so we can enforce diversity deterministically.
    """
    prompt: dict[str, object] = {
        "Introduction": (
            "You are an AI researcher conducting ablation studies. "
            "Based on the current implementation and previous ablations (if any), "
            "propose ONE new ablation study that tests a different aspect of the model."
        ),
        "Base code you are working on": base_code,
        "Previous Ablations": {
            "Has been tried": tried if tried else "Nothing has been tried yet.",
        },
        "Instructions": {
            "Requirements": [
                "1. Identify ONE specific component/feature to ablate.",
                "2. Ensure the ablation is different from previous completed or running attempts.",
                "3. The ablation should be a new idea, not a trivial variation of a previous idea.",
                "4. Keep the core model architecture unchanged unless the ablation explicitly targets it.",
            ]
        },
    }

    retry_limit = 5
    for _ in range(retry_limit):
        try:
            result = structured_query_with_schema(
                system_message=prompt,
                user_message=None,
                model=model,
                temperature=temperature,
                schema_class=AblationIdea,
            )
        except Exception:
            continue
        name = result.name.strip()
        description = result.description.strip()
        if name and description:
            return AblationIdea(name=name, description=description)

    return AblationIdea(name="ablate dropout", description="ablate dropout")


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
        prompt = render_text(
            template_name="stage_completion/stage4_substage.txt.j2",
            context={"goals": goals},
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
    return render_lines(template_name="contracts/stage4.txt.j2", context={})


def validate_node_result_contract(
    *, node_result: dict[str, object], ctx: NodeResultContractContext
) -> list[str]:
    errors: list[str] = []
    if not is_non_empty_string(value=node_result.get("ablation_name")):
        errors.append("Stage4 requires ablation_name to be a non-empty string")
    expected = ctx.expected_ablation_name
    if expected is not None:
        actual = node_result.get("ablation_name")
        if actual != expected:
            errors.append(
                f"Stage4 requires ablation_name={expected!r} (got {actual!r}); set it exactly to the assigned idea name"
            )

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
