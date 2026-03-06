"""
Idea refinement service that takes a judge evaluation and produces an improved idea.

Given an IdeaJudgeResult, the refiner:
  1. Synthesizes all criterion feedback and the revision plan into a single prompt
  2. Asks the LLM to produce a concrete, improved version of the idea
  3. Returns the refined idea (title + markdown) along with a changelog

The refined idea stays within AE Scientist execution constraints (≤$50 RunPod/Steering
API budget, fully automatable, standard Python/ML ecosystem) and preserves the core
research hypothesis.
"""

import logging
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field

from app.services.base_llm_service import BaseLLMService
from app.services.idea_judge_service import IdeaJudgeResult
from app.services.prompts.render import render_text

REFINER_DEFAULT_MODEL = "gpt-5.4"

logger = logging.getLogger(__name__)


# =============================================================================
# Pydantic output schemas
# =============================================================================


class RefinementChange(BaseModel):
    """A single change made during refinement."""

    model_config = ConfigDict(extra="forbid")

    change: str = Field(
        ...,
        description="What was changed in the idea (be specific).",
    )
    criterion_addressed: str = Field(
        ...,
        description="Which judge criterion or action item this addresses (e.g., 'feasibility — budget overrun', 'novelty — overlap with Chen 2024').",
    )
    expected_score_impact: str = Field(
        ...,
        description="Expected effect on the criterion score (e.g., '+1 feasibility', 'maintains relevance').",
    )


class RefinedIdeaOutput(BaseModel):
    """Structured LLM output for the refinement call."""

    model_config = ConfigDict(extra="forbid")

    refined_title: str = Field(
        ...,
        description="Concise, descriptive title for the refined research idea.",
    )
    refined_markdown: str = Field(
        ...,
        description="The full refined idea in markdown format following the standard sections: Project Summary, Idea Description, Proposed Experiments, Expected Outcome, Key Considerations.",
    )
    changes_made: List[RefinementChange] = Field(
        ...,
        description="List of 3-10 specific changes made and which judge concerns they address.",
    )
    refinement_summary: str = Field(
        ...,
        description="2-3 sentence summary of the refinement strategy: what was the main weakness, and how does the revision address it?",
    )


class IdeaRefinerResult(BaseModel):
    """Full result from the refiner, pairing the refined idea with its provenance."""

    model_config = ConfigDict(extra="forbid")

    original_title: str
    original_overall_score: float
    original_recommendation: str
    refined_title: str
    refined_markdown: str
    changes_made: List[RefinementChange]
    refinement_summary: str


# =============================================================================
# Service
# =============================================================================


class IdeaRefinerService:
    """
    Produces an improved research idea based on judge feedback.

    Usage::

        refiner = IdeaRefinerService(llm_service=resolve_llm_service(provider))
        result = await refiner.refine(
            llm_model="gpt-4o",
            idea_title="...",
            idea_markdown="...",
            judge_result=judge_result,
            conversation_text="...",   # optional, for relevance grounding
        )
    """

    def __init__(self, *, llm_service: BaseLLMService) -> None:
        self._llm = llm_service
        self._system_prompt = render_text(template_name="idea_refiner/system.txt.j2")

    async def refine(
        self,
        *,
        llm_model: str,
        idea_title: str,
        idea_markdown: str,
        judge_result: IdeaJudgeResult,
        conversation_text: Optional[str] = None,
    ) -> IdeaRefinerResult:
        """
        Generate a refined version of the idea that addresses judge concerns.

        Args:
            llm_model: Model identifier for the refinement call.
            idea_title: Title of the original idea.
            idea_markdown: Full markdown of the original idea.
            judge_result: The complete IdeaJudgeResult from the judge service.
            conversation_text: Optional source conversation for relevance grounding.

        Returns:
            IdeaRefinerResult with the refined idea, changelog, and provenance.

        Raises:
            Exception: If the LLM call fails.
        """
        user_prompt = self._build_refinement_prompt(
            idea_title=idea_title,
            idea_markdown=idea_markdown,
            judge_result=judge_result,
            conversation_text=conversation_text,
        )

        refined = await self._llm.generate_structured_output(
            llm_model=llm_model,
            system_prompt=self._system_prompt,
            user_prompt=user_prompt,
            schema=RefinedIdeaOutput,
            max_completion_tokens=4000,
        )
        if not isinstance(refined, RefinedIdeaOutput):
            raise TypeError(f"Expected RefinedIdeaOutput, got {type(refined)}")

        return IdeaRefinerResult(
            original_title=idea_title,
            original_overall_score=judge_result.overall_score,
            original_recommendation=judge_result.recommendation,
            refined_title=refined.refined_title,
            refined_markdown=refined.refined_markdown,
            changes_made=refined.changes_made,
            refinement_summary=refined.refinement_summary,
        )

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _build_refinement_prompt(
        *,
        idea_title: str,
        idea_markdown: str,
        judge_result: IdeaJudgeResult,
        conversation_text: Optional[str],
    ) -> str:
        rel = judge_result.relevance
        feas = judge_result.feasibility
        nov = judge_result.novelty
        imp = judge_result.impact
        rev = judge_result.revision

        return render_text(
            template_name="idea_refiner/refine.txt.j2",
            context={
                "idea_title": idea_title,
                "idea_markdown": idea_markdown,
                "conversation_text": conversation_text or "",
                "overall_score": f"{judge_result.overall_score:.1f}",
                "recommendation": judge_result.recommendation.replace("_", " ").title(),
                # Relevance
                "relevance_score": rel.score,
                "relevance_rationale": rel.rationale,
                "relevance_connection_points": "; ".join(rel.connection_points),
                "relevance_drift_concerns": "; ".join(rel.drift_concerns),
                "relevance_suggestions": "; ".join(rel.suggestions),
                # Feasibility
                "feasibility_score": feas.score,
                "feasibility_rationale": feas.rationale,
                "estimated_cost": feas.estimated_cost,
                "compute_viable": feas.compute_viable,
                "agent_implementable": feas.agent_implementable,
                "feasibility_blockers": "; ".join(feas.blockers),
                "feasibility_suggestions": "; ".join(feas.suggestions),
                # Novelty
                "novelty_score": nov.score,
                "novelty_rationale": nov.rationale,
                "novelty_differentiation": nov.differentiation,
                "novelty_risks": "; ".join(nov.novelty_risks),
                "novelty_suggestions": "; ".join(nov.suggestions),
                # Impact
                "impact_score": imp.score,
                "impact_rationale": imp.rationale,
                "research_question": imp.research_question,
                "what_changes_if_success": imp.what_changes_if_success,
                "goodhart_risk_assessment": imp.goodhart_risk_assessment,
                "impact_suggestions": "; ".join(imp.suggestions),
                # Revision plan
                "revision_overall_assessment": rev.overall_assessment,
                "revision_action_items": [
                    {
                        "priority": item.priority,
                        "action": item.action,
                        "addresses": item.addresses,
                    }
                    for item in rev.action_items
                ],
            },
        )
