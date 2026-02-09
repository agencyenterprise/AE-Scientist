import logging
from dataclasses import dataclass
from typing import Any, Optional

from pydantic import BaseModel, Field

from ai_scientist.llm import structured_query_with_schema

from .journal import Journal
from .metrics_extraction import analyze_progress, gather_stage_metrics, identify_issues
from .prompts.render import render_text

logger = logging.getLogger(__name__)


# Stage display names keyed by stage ID
STAGE_DISPLAY_NAMES: dict[str, str] = {
    "1_initial_implementation": "Initial Implementation",
    "2_baseline_tuning": "Baseline Tuning",
    "3_creative_research": "Creative Research",
    "4_ablation_studies": "Ablation Studies",
    "5_paper_generation": "Paper Generation",
}

# Stage display names keyed by stage number (for transition summaries)
STAGE_NAMES_BY_NUMBER: dict[int, str] = {
    1: "Initial Implementation",
    2: "Baseline Tuning",
    3: "Creative Research",
    4: "Ablation Studies",
    5: "Paper Generation",
}


class TransitionSummaryResponse(BaseModel):
    """LLM response schema for stage transition summary."""

    summary: str = Field(
        ...,
        description="A 2-3 sentence summary of what was achieved and what comes next.",
        min_length=20,
        max_length=500,
    )


def generate_transition_summary(
    *,
    idea_title: str,
    completed_stage_number: int,
    completed_stage_goals: str,
    journal: Journal,
    next_stage_number: Optional[int],
    next_stage_goals: Optional[str],
    model: str,
    temperature: float,
) -> str:
    """Generate an LLM-based transition summary for display between stages.

    Args:
        idea_title: Title of the research idea
        completed_stage_number: Number of the stage that just completed (1-4)
        completed_stage_goals: Goals of the completed stage
        journal: Journal with experiment nodes for the completed stage
        next_stage_number: Number of the next stage (or None if final)
        next_stage_goals: Goals of the next stage (or None if final)
        model: LLM model to use
        temperature: Temperature for LLM generation

    Returns:
        A 2-3 sentence transition summary string
    """
    best_node = journal.get_best_node(only_good=True, use_val_metric_only=True)

    # Build context for the prompt
    completed_stage_name = STAGE_NAMES_BY_NUMBER.get(
        completed_stage_number, f"Stage {completed_stage_number}"
    )
    next_stage_name = STAGE_NAMES_BY_NUMBER.get(next_stage_number) if next_stage_number else None

    context = {
        "idea_title": idea_title,
        "completed_stage_number": completed_stage_number,
        "completed_stage_name": completed_stage_name,
        "completed_stage_goals": completed_stage_goals,
        "total_nodes": len(journal.nodes),
        "good_nodes": len(journal.good_nodes),
        "best_metric": str(best_node.metric) if best_node and best_node.metric else None,
        "best_node_analysis": best_node.analysis if best_node else None,
        "next_stage_number": next_stage_number,
        "next_stage_name": next_stage_name,
        "next_stage_goals": next_stage_goals,
    }

    # Render the prompt template
    prompt = render_text(
        template_name="stage_transition/transition_summary.txt.j2",
        context=context,
    )

    logger.debug(
        "llm.transition_summary.request stage=%s model=%s prompt=%s",
        completed_stage_number,
        model,
        prompt,
    )

    try:
        response = structured_query_with_schema(
            system_message=prompt,
            user_message=None,
            model=model,
            temperature=temperature,
            schema_class=TransitionSummaryResponse,
        )
        summary = response.summary
        logger.debug(
            "llm.transition_summary.response stage=%s summary=%s",
            completed_stage_number,
            summary if summary else None,
        )
        return summary
    except Exception as exc:
        logger.warning(
            "Failed to generate transition summary for stage %s: %s",
            completed_stage_number,
            exc,
        )
        # Fallback to a simple deterministic summary
        best_metric_str = str(best_node.metric) if best_node and best_node.metric else "N/A"
        next_stage_label = next_stage_name or "next stage"
        return (
            f"Completed Stage {completed_stage_number} with {len(journal.good_nodes)} "
            f"successful experiments (best metric: {best_metric_str}). "
            f"{'Moving to ' + next_stage_label + '.' if next_stage_number else 'All experimental stages complete.'}"
        )


@dataclass
class PhaseDefinition:
    phase_id: str  # e.g., "1_initial_implementation"
    main_stage_number: int
    goals: str

    @property
    def display_name(self) -> str:
        stage_label = STAGE_DISPLAY_NAMES.get(self.phase_id, self.phase_id)
        return f"Stage {self.main_stage_number}: {stage_label} · "


@dataclass
class PhasePlanProgress:
    completed_phases: int
    current_phase_label: str


@dataclass
class PhaseSummaryFacts:
    phase: PhaseDefinition
    plan_progress: PhasePlanProgress
    decisions: list[dict[str, str]]
    experiments: list[dict[str, Any]]
    metrics: dict[str, Any]
    issues: list[str]


@dataclass
class PhaseSummaryEnvelope:
    facts: PhaseSummaryFacts
    llm_summary: str
    llm_confidence: str
    steering_guidance: list[str]
    llm_goal_alignment: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "phase_id": self.facts.phase.phase_id,
            "phase_label": self.facts.phase.display_name,
            "plan_progress": {
                "completed": self.facts.plan_progress.completed_phases,
                "total": 5,
                "label": self.facts.plan_progress.current_phase_label,
            },
            "decisions": self.facts.decisions,
            "experiments": self.facts.experiments,
            "metrics": self.facts.metrics,
            "issues": self.facts.issues,
            "llm_summary": self.llm_summary,
            "llm_confidence": self.llm_confidence,
            "steering_guidance": self.steering_guidance,
            "llm_goal_alignment": self.llm_goal_alignment,
        }


def build_phase_summary(
    *,
    journal: Journal,
    phase: PhaseDefinition,
    plan_progress: PhasePlanProgress,
) -> PhaseSummaryEnvelope:
    """Deterministic phase summary used in codex-only mode (no LLM)."""
    metrics = gather_stage_metrics(journal=journal)
    issues = identify_issues(journal=journal)
    progress = analyze_progress(journal=journal)
    best_node = journal.get_best_node(only_good=True, use_val_metric_only=True)

    decisions: list[dict[str, str]] = []
    if best_node is not None:
        decisions.append(
            {
                "kind": "best_node",
                "node_id": best_node.id,
                "metric": str(best_node.metric) if best_node.metric is not None else "unknown",
                "analysis": (best_node.analysis or "")[:400],
            }
        )

    experiments: list[dict[str, Any]] = []
    for n in sorted(journal.nodes, key=lambda nn: nn.ctime, reverse=True)[:6]:
        experiments.append(
            {
                "node_id": n.id,
                "is_buggy": bool(n.is_buggy),
                "metric": str(n.metric) if n.metric is not None else None,
                "analysis": (n.analysis or "")[:400] if n.analysis else None,
            }
        )

    best_metric = metrics.get("best_metric")
    best_value_str = str(best_metric.get("value")) if isinstance(best_metric, dict) else "N/A"
    llm_summary = (
        f"{phase.display_name} attempts={metrics.get('total_nodes', len(journal.nodes))}, "
        f"successes={metrics.get('good_nodes', len(journal.good_nodes))}, best={best_value_str}. "
        f"convergence={progress.get('convergence_status', 'unknown')}."
    )
    confidence = (
        "high" if len(journal.good_nodes) >= 2 else ("medium" if journal.good_nodes else "low")
    )
    goal_alignment = (
        "on_track" if journal.good_nodes else ("at_risk" if journal.nodes else "blocked")
    )
    steering_guidance = [
        "Increase iteration budget if no good nodes appear",
        "Prioritize reliable metric extraction",
    ][: (0 if journal.good_nodes else 2)]

    facts = PhaseSummaryFacts(
        phase=phase,
        plan_progress=plan_progress,
        decisions=decisions,
        experiments=experiments,
        metrics=metrics if isinstance(metrics, dict) else {},
        issues=[str(i) for i in issues] if isinstance(issues, list) else [],
    )
    return PhaseSummaryEnvelope(
        facts=facts,
        llm_summary=llm_summary,
        llm_confidence=confidence,
        steering_guidance=steering_guidance,
        llm_goal_alignment=goal_alignment,
    )
