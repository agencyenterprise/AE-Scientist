"""
LLM-as-a-judge service for evaluating research ideas immediately after generation.

Four criteria are evaluated in parallel, each via its own structured LLM call:
  1. Relevance   — does the idea connect back to the source conversation?
  2. Feasibility — can it be executed within AE Scientist constraints (RunPod ≤$50, coding agent)?
  3. Novelty     — is the core claim meaningfully differentiated from known prior work?
  4. Impact      — is the research question clear, consequential, and threat-model realistic?

Results are compiled into an IdeaJudgeResult and persisted to idea_judge_reviews.
"""

import asyncio
import logging
import os
from typing import List

import openai
from pydantic import BaseModel, ConfigDict, Field, computed_field

from app.services.base_llm_service import BaseLLMService
from app.services.prompts.render import render_text

JUDGE_DEFAULT_MODEL = "gpt-5.4"
_NOVELTY_SEARCH_MODEL = "gpt-5.4"

logger = logging.getLogger(__name__)


# =============================================================================
# Per-criterion Pydantic output schemas
# =============================================================================


class RelevanceCriterionResult(BaseModel):
    """Structured output for the Relevance criterion."""

    model_config = ConfigDict(extra="forbid")

    score: int = Field(..., ge=1, le=5, description="Relevance score 1-5.")
    rationale: str = Field(..., description="2-4 sentence synthesis of the relevance assessment.")
    connection_points: List[str] = Field(
        ...,
        description="Specific ways the idea connects to the source conversation.",
    )
    drift_concerns: List[str] = Field(
        ...,
        description="Ways the idea departs or over-generalises from the conversation.",
    )
    suggestions: List[str] = Field(
        ...,
        description="Concrete edits to improve relevance.",
    )


class FeasibilityCriterionResult(BaseModel):
    """Structured output for the Feasibility criterion."""

    model_config = ConfigDict(extra="forbid")

    score: int = Field(..., ge=1, le=5, description="Feasibility score 1-5.")
    rationale: str = Field(..., description="2-4 sentence synthesis of the feasibility assessment.")
    compute_viable: bool = Field(
        ...,
        description="True if experiments fit within the ≤$50 combined RunPod + Steering API budget.",
    )
    agent_implementable: bool = Field(
        ...,
        description="True if a coding agent can implement and run the full experiment without human intervention.",
    )
    estimated_cost: str = Field(
        ...,
        description="Itemized cost estimate referencing specific GPU types or Steering API rates (e.g. '~$8 for 10 hrs on A40' or '~$2 for 2M tokens via Steering API').",
    )
    blockers: List[str] = Field(
        ...,
        description="Specific blockers that would prevent execution within constraints.",
    )
    suggestions: List[str] = Field(
        ...,
        description="Concrete modifications to bring the idea within constraints.",
    )


class _NoveltyScoringOutput(BaseModel):
    """Fields the scoring LLM fills after receiving grounded search results.

    Kept separate from NoveltyCriterionResult so that web_search_summary
    is set in code (not by the LLM) without fighting with_structured_output.
    """

    model_config = ConfigDict(extra="forbid")

    score: int = Field(..., ge=1, le=5, description="Novelty score 1-5.")
    rationale: str = Field(..., description="2-4 sentence synthesis of the novelty assessment.")
    core_claims: List[str] = Field(
        ...,
        description="The 3-5 specific novelty claims the idea is making.",
    )
    related_prior_work: List[str] = Field(
        ...,
        description="Prior work found in the search that overlaps (format: 'Title (Year) — overlap description and URL').",
    )
    differentiation: str = Field(
        ...,
        description="What genuinely sets this idea apart from the identified prior work.",
    )
    novelty_risks: List[str] = Field(
        ...,
        description="Specific risks that the core claim has already been addressed (cite paper titles and years).",
    )
    suggestions: List[str] = Field(
        ...,
        description="How to sharpen or strengthen the novelty claim given the identified prior art.",
    )


class NoveltyCriterionResult(_NoveltyScoringOutput):
    """Full novelty result including the raw web-search output."""

    model_config = ConfigDict(extra="forbid")

    web_search_summary: str = Field(
        default="",
        description="Raw output from the live web search step (grounded prior-art citations).",
    )


class ImpactCriterionResult(BaseModel):
    """Structured output for the Impact criterion."""

    model_config = ConfigDict(extra="forbid")

    score: int = Field(..., ge=1, le=5, description="Impact score 1-5.")
    rationale: str = Field(..., description="2-4 sentence synthesis of the impact assessment.")
    research_question: str = Field(
        ...,
        description="The specific research question this idea is answering, stated precisely.",
    )
    what_changes_if_success: str = Field(
        ...,
        description="Concretely what researchers or practitioners would do differently if the experiment succeeds.",
    )
    threat_model_assessment: str = Field(
        ...,
        description="Evaluation of whether safety/alignment assumptions are realistic for frontier deployment.",
    )
    goodhart_risk_assessment: str = Field(
        ...,
        description="Evaluation of Goodhart risk: could the proposed metrics be gamed or diverge from the real objective? Are the evaluation proxies faithful to the underlying property?",
    )
    suggestions: List[str] = Field(
        ...,
        description="How to increase impact (clearer hypothesis, more realistic assumptions, broader model scope, reduce Goodhart risk, etc.).",
    )


class RevisionActionItem(BaseModel):
    """A single concrete action item to address a judge concern."""

    model_config = ConfigDict(extra="forbid")

    action: str = Field(
        ...,
        description="A specific, actionable edit or change to the idea (start with a verb).",
    )
    addresses: str = Field(
        ...,
        description="Which criterion/concern this action resolves (e.g., 'feasibility — budget overrun', 'novelty — overlap with Chen et al. 2024').",
    )
    priority: str = Field(
        ...,
        description="'high' if the idea cannot proceed without this change, 'medium' if it materially improves the idea, 'low' if nice-to-have.",
    )


class RevisionPlan(BaseModel):
    """Synthesized revision plan produced after all four criteria are evaluated."""

    model_config = ConfigDict(extra="forbid")

    action_items: List[RevisionActionItem] = Field(
        ...,
        description="Prioritized list of 3-7 concrete action items to strengthen the idea, ordered by priority (high first).",
    )
    overall_assessment: str = Field(
        ...,
        description="2-3 sentence synthesis: what is the single biggest weakness, and what would make this idea ready for the experiment pipeline?",
    )


# =============================================================================
# Aggregate result
# =============================================================================

_RECOMMENDATION_THRESHOLDS: list[tuple[float, str]] = [
    (4.5, "strong_accept"),
    (3.5, "accept"),
    (2.5, "revise"),
    (0.0, "reject"),
]


def _score_to_recommendation(overall: float) -> str:
    for threshold, label in _RECOMMENDATION_THRESHOLDS:
        if overall >= threshold:
            return label
    return "reject"


class IdeaJudgeResult(BaseModel):
    """Full judge result aggregating all four criteria plus a revision plan."""

    model_config = ConfigDict(extra="forbid")

    relevance: RelevanceCriterionResult
    feasibility: FeasibilityCriterionResult
    novelty: NoveltyCriterionResult
    impact: ImpactCriterionResult
    revision: RevisionPlan

    @computed_field  # type: ignore[prop-decorator]
    @property
    def overall_score(self) -> float:
        """Mean of the four criterion scores (1.0–5.0)."""
        return (
            self.relevance.score
            + self.feasibility.score
            + self.novelty.score
            + self.impact.score
        ) / 4.0

    @computed_field  # type: ignore[prop-decorator]
    @property
    def recommendation(self) -> str:
        """Overall recommendation: strong_accept | accept | revise | reject."""
        return _score_to_recommendation(self.overall_score)

    @computed_field  # type: ignore[prop-decorator]
    @property
    def summary(self) -> str:
        """One-line summary for display."""
        scores = (
            f"Relevance {self.relevance.score}/5 · "
            f"Feasibility {self.feasibility.score}/5 · "
            f"Novelty {self.novelty.score}/5 · "
            f"Impact {self.impact.score}/5"
        )
        rec = self.recommendation.replace("_", " ").title()
        return f"{rec} (overall {self.overall_score:.1f}/5) — {scores}"


# =============================================================================
# Service
# =============================================================================


class IdeaJudgeService:
    """
    Evaluates a research idea across four criteria in parallel LLM calls.

    Usage::

        service = IdeaJudgeService(llm_service=resolve_llm_service(provider))
        result = await service.judge(
            llm_model="gpt-4o",
            idea_title="...",
            idea_markdown="...",
            conversation_text="...",
        )
    """

    def __init__(self, *, llm_service: BaseLLMService) -> None:
        self._llm = llm_service
        self._system_prompt = render_text(template_name="idea_judge/system.txt.j2")

    async def judge(
        self,
        *,
        llm_model: str,
        idea_title: str,
        idea_markdown: str,
        conversation_text: str,
    ) -> IdeaJudgeResult:
        """
        Run all four criteria concurrently, then synthesize a revision plan.

        Raises:
            Exception: If any criterion call fails (callers should catch and handle gracefully).
        """
        relevance_result, feasibility_result, novelty_result, impact_result = (
            await asyncio.gather(
                self._run_relevance(
                    llm_model=llm_model,
                    idea_title=idea_title,
                    idea_markdown=idea_markdown,
                    conversation_text=conversation_text,
                ),
                self._run_feasibility(
                    llm_model=llm_model,
                    idea_title=idea_title,
                    idea_markdown=idea_markdown,
                ),
                self._run_novelty(
                    llm_model=llm_model,
                    idea_title=idea_title,
                    idea_markdown=idea_markdown,
                ),
                self._run_impact(
                    llm_model=llm_model,
                    idea_title=idea_title,
                    idea_markdown=idea_markdown,
                ),
            )
        )

        revision_result = await self._run_revision(
            llm_model=llm_model,
            idea_title=idea_title,
            idea_markdown=idea_markdown,
            relevance=relevance_result,
            feasibility=feasibility_result,
            novelty=novelty_result,
            impact=impact_result,
        )

        return IdeaJudgeResult(
            relevance=relevance_result,
            feasibility=feasibility_result,
            novelty=novelty_result,
            impact=impact_result,
            revision=revision_result,
        )

    # ------------------------------------------------------------------
    # Private per-criterion runners
    # ------------------------------------------------------------------

    async def _run_relevance(
        self,
        *,
        llm_model: str,
        idea_title: str,
        idea_markdown: str,
        conversation_text: str,
    ) -> RelevanceCriterionResult:
        user_prompt = render_text(
            template_name="idea_judge/relevance.txt.j2",
            context={
                "conversation_text": conversation_text,
                "idea_title": idea_title,
                "idea_markdown": idea_markdown,
            },
        )
        result = await self._llm.generate_structured_output(
            llm_model=llm_model,
            system_prompt=self._system_prompt,
            user_prompt=user_prompt,
            schema=RelevanceCriterionResult,
        )
        if not isinstance(result, RelevanceCriterionResult):
            raise TypeError(f"Expected RelevanceCriterionResult, got {type(result)}")
        return result

    async def _run_feasibility(
        self,
        *,
        llm_model: str,
        idea_title: str,
        idea_markdown: str,
    ) -> FeasibilityCriterionResult:
        user_prompt = render_text(
            template_name="idea_judge/feasibility.txt.j2",
            context={
                "idea_title": idea_title,
                "idea_markdown": idea_markdown,
            },
        )
        result = await self._llm.generate_structured_output(
            llm_model=llm_model,
            system_prompt=self._system_prompt,
            user_prompt=user_prompt,
            schema=FeasibilityCriterionResult,
        )
        if not isinstance(result, FeasibilityCriterionResult):
            raise TypeError(f"Expected FeasibilityCriterionResult, got {type(result)}")
        return result

    async def _web_search_prior_art(
        self,
        *,
        idea_title: str,
        idea_markdown: str,
    ) -> str:
        """
        Use the Responses API with web_search to retrieve grounded prior-art citations.

        Returns the raw text response (with inline citations) to feed into the
        scoring step.  Falls back to an empty string if the search fails, so
        the scoring step can still proceed with a parametric assessment.
        """
        instructions = render_text(template_name="idea_judge/novelty_search_system.txt.j2")
        user_prompt = render_text(
            template_name="idea_judge/novelty_search_user.txt.j2",
            context={
                "idea_title": idea_title,
                "idea_markdown": idea_markdown,
            },
        )
        try:
            client = openai.AsyncOpenAI(api_key=os.environ.get("OPENAI_API_KEY"))
            response = await client.responses.create(
                model=_NOVELTY_SEARCH_MODEL,
                instructions=instructions,
                input=user_prompt,
                tools=[{"type": "web_search"}],
            )
            content = response.output_text or ""
            logger.debug("novelty web search complete (%d chars)", len(content))
            return content
        except Exception:
            logger.exception(
                "novelty web search failed (falling back to parametric assessment)"
            )
            return ""

    async def _run_novelty(
        self,
        *,
        llm_model: str,
        idea_title: str,
        idea_markdown: str,
    ) -> NoveltyCriterionResult:
        """Two-step novelty evaluation: live web search → structured scoring."""
        # Step 1: retrieve grounded prior art via gpt-4o-mini-search-preview
        search_results = await self._web_search_prior_art(
            idea_title=idea_title,
            idea_markdown=idea_markdown,
        )

        fallback_note = (
            "\n\n(Note: live web search was unavailable. "
            "Base your assessment on general knowledge of the field.)"
            if not search_results
            else ""
        )

        # Step 2: structured scoring using the grounded search context
        user_prompt = render_text(
            template_name="idea_judge/novelty.txt.j2",
            context={
                "idea_title": idea_title,
                "idea_markdown": idea_markdown,
                "search_results": search_results + fallback_note,
            },
        )
        scoring = await self._llm.generate_structured_output(
            llm_model=llm_model,
            system_prompt=self._system_prompt,
            user_prompt=user_prompt,
            schema=_NoveltyScoringOutput,
        )
        if not isinstance(scoring, _NoveltyScoringOutput):
            raise TypeError(f"Expected _NoveltyScoringOutput, got {type(scoring)}")

        # Attach the raw search output (set in code, not by the LLM)
        return NoveltyCriterionResult(
            **scoring.model_dump(),
            web_search_summary=search_results,
        )

    async def _run_impact(
        self,
        *,
        llm_model: str,
        idea_title: str,
        idea_markdown: str,
    ) -> ImpactCriterionResult:
        user_prompt = render_text(
            template_name="idea_judge/impact.txt.j2",
            context={
                "idea_title": idea_title,
                "idea_markdown": idea_markdown,
            },
        )
        result = await self._llm.generate_structured_output(
            llm_model=llm_model,
            system_prompt=self._system_prompt,
            user_prompt=user_prompt,
            schema=ImpactCriterionResult,
        )
        if not isinstance(result, ImpactCriterionResult):
            raise TypeError(f"Expected ImpactCriterionResult, got {type(result)}")
        return result

    async def _run_revision(
        self,
        *,
        llm_model: str,
        idea_title: str,
        idea_markdown: str,
        relevance: RelevanceCriterionResult,
        feasibility: FeasibilityCriterionResult,
        novelty: NoveltyCriterionResult,
        impact: ImpactCriterionResult,
    ) -> RevisionPlan:
        """Synthesize all criterion results into a prioritized revision plan."""
        user_prompt = render_text(
            template_name="idea_judge/revision.txt.j2",
            context={
                "idea_title": idea_title,
                "idea_markdown": idea_markdown,
                "relevance_score": relevance.score,
                "relevance_rationale": relevance.rationale,
                "relevance_suggestions": "; ".join(relevance.suggestions),
                "feasibility_score": feasibility.score,
                "feasibility_rationale": feasibility.rationale,
                "estimated_cost": feasibility.estimated_cost,
                "feasibility_blockers": "; ".join(feasibility.blockers),
                "feasibility_suggestions": "; ".join(feasibility.suggestions),
                "novelty_score": novelty.score,
                "novelty_rationale": novelty.rationale,
                "novelty_risks": "; ".join(novelty.novelty_risks),
                "novelty_suggestions": "; ".join(novelty.suggestions),
                "impact_score": impact.score,
                "impact_rationale": impact.rationale,
                "goodhart_risk_assessment": impact.goodhart_risk_assessment,
                "impact_suggestions": "; ".join(impact.suggestions),
            },
        )
        result = await self._llm.generate_structured_output(
            llm_model=llm_model,
            system_prompt=self._system_prompt,
            user_prompt=user_prompt,
            schema=RevisionPlan,
        )
        if not isinstance(result, RevisionPlan):
            raise TypeError(f"Expected RevisionPlan, got {type(result)}")
        return result
