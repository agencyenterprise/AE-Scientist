import logging
from dataclasses import dataclass
from typing import Any

from .journal import Journal
from .metrics_extraction import analyze_progress, gather_stage_metrics, identify_issues

logger = logging.getLogger(__name__)


@dataclass
class PhaseDefinition:
    phase_id: str
    main_stage_number: int
    stage_slug: str
    goals: str

    @property
    def display_name(self) -> str:
        slug_label = self.stage_slug.replace("_", " ").title()
        return f"Stage {self.main_stage_number}: {slug_label} · "


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
