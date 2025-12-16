import json
import logging
from dataclasses import dataclass
from typing import Any, Literal

from pydantic import BaseModel, Field

from ai_scientist.llm import structured_query_with_schema

from .journal import Journal
from .metrics_extraction import analyze_progress, gather_stage_metrics, identify_issues

logger = logging.getLogger(__name__)

PHASE_DECISION_LIMIT = 6
PHASE_EXPERIMENT_LIMIT = 6


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


class PhaseSummaryLLMResponse(BaseModel):
    summary: str = Field(
        ...,
        description=(
            "2‑4 sentences that synthesize the phase outcome for the user. "
            "Highlight decisive experiments and plan progress."
        ),
    )
    steering_guidance: list[str] = Field(
        ...,
        description=(
            "0‑3 actionable suggestions (short imperatives) the user could take next. "
            "Only include guidance that materially affects the next steps."
        ),
    )
    confidence: Literal["high", "medium", "low"] = Field(
        ...,
        description=(
            "Confidence in the summary based on available evidence: "
            "'high' when multiple successful signals align, "
            "'medium' when evidence is mixed, "
            "and 'low' when results are sparse or conflicting."
        ),
    )
    goal_alignment: Literal["on_track", "at_risk", "blocked"] = Field(
        ...,
        description=(
            "'on_track' when current evidence meets phase goals, "
            "'at_risk' when more work is needed but progress exists, "
            "'blocked' when objectives cannot be met without external changes."
        ),
    )


def _collect_phase_decisions(*, journal: Journal) -> list[dict[str, str]]:
    logger.debug("Collecting phase decisions for stage %s", journal.stage_name)
    decisions: list[dict[str, str]] = []
    seen_signatures: set[str] = set()
    best_node = journal.get_best_node()
    if best_node is not None:
        entry = {
            "kind": "best_node",
            "node_id": best_node.id,
            "metric": str(best_node.metric) if best_node.metric is not None else "unknown",
            "analysis": best_node.analysis or "",
            "hyperparameter": best_node.hyperparam_name or "",
            "ablation": best_node.ablation_name or "",
        }
        signature = f"best_node:{best_node.id}"
        decisions.append(entry)
        seen_signatures.add(signature)

    for node in journal.nodes:
        if node.hyperparam_name:
            signature = f"hyper:{node.id}:{node.hyperparam_name}"
            if signature not in seen_signatures:
                decisions.append(
                    {
                        "kind": "hyperparameter_choice",
                        "node_id": node.id,
                        "hyperparameter": node.hyperparam_name,
                        "metric": str(node.metric) if node.metric is not None else "unknown",
                        "analysis": node.analysis or "",
                    }
                )
                seen_signatures.add(signature)
        if node.ablation_name:
            signature = f"ablation:{node.id}:{node.ablation_name}"
            if signature not in seen_signatures:
                decisions.append(
                    {
                        "kind": "ablation_focus",
                        "node_id": node.id,
                        "ablation": node.ablation_name,
                        "metric": str(node.metric) if node.metric is not None else "unknown",
                        "analysis": node.analysis or "",
                    }
                )
                seen_signatures.add(signature)

    if len(decisions) > PHASE_DECISION_LIMIT:
        decisions = decisions[-PHASE_DECISION_LIMIT:]
    logger.debug(
        "Collected %s decision entries for stage %s: %s",
        len(decisions),
        journal.stage_name,
        decisions,
    )
    return decisions


def _collect_experiment_outcomes(*, journal: Journal, limit: int) -> list[dict[str, Any]]:
    logger.debug(
        "Collecting experiment outcomes for stage %s (limit=%s)",
        journal.stage_name,
        limit,
    )
    recent_nodes = journal.nodes[-limit:]
    experiments: list[dict[str, Any]] = []
    for node in recent_nodes:
        status = "success" if node.is_buggy is False and node.is_buggy_plots is False else "failed"
        experiments.append(
            {
                "node_id": node.id,
                "status": status,
                "metric": node.metric.value if node.metric is not None else None,
                "metric_detail": str(node.metric) if node.metric is not None else None,
                "analysis": node.analysis or "",
                "hyperparameter": node.hyperparam_name or "",
                "ablation": node.ablation_name or "",
                "datasets": list(node.datasets_successfully_tested),
            }
        )
    logger.debug(
        "Collected %s experiment summaries for stage %s: %s",
        len(experiments),
        journal.stage_name,
        experiments,
    )
    return experiments


def _build_phase_summary_facts(
    *,
    journal: Journal,
    phase: PhaseDefinition,
    plan_progress: PhasePlanProgress,
) -> PhaseSummaryFacts:
    logger.info(
        "Building phase summary facts for stage %s (phase=%s)",
        journal.stage_name,
        phase.phase_id,
    )
    metrics_snapshot = gather_stage_metrics(journal=journal)
    progress_snapshot = analyze_progress(journal=journal)
    metrics_snapshot["progress_snapshot"] = progress_snapshot
    issues = identify_issues(journal=journal)
    decisions = _collect_phase_decisions(journal=journal)
    experiments = _collect_experiment_outcomes(
        journal=journal,
        limit=PHASE_EXPERIMENT_LIMIT,
    )
    facts = PhaseSummaryFacts(
        phase=phase,
        plan_progress=plan_progress,
        decisions=decisions,
        experiments=experiments,
        metrics=metrics_snapshot,
        issues=issues,
    )
    logger.debug(
        "Phase summary facts ready for %s: decisions=%s experiments=%s issues=%s",
        phase.phase_id,
        len(decisions),
        len(experiments),
        len(issues),
    )
    return facts


def build_phase_summary(
    *,
    journal: Journal,
    phase: PhaseDefinition,
    plan_progress: PhasePlanProgress,
) -> PhaseSummaryEnvelope:
    logger.info(
        "Generating phase summary for %s (%s/5 complete)",
        phase.phase_id,
        plan_progress.completed_phases,
    )
    facts = _build_phase_summary_facts(
        journal=journal,
        phase=phase,
        plan_progress=plan_progress,
    )
    fact_payload = {
        "phase": {
            "id": phase.phase_id,
            "label": phase.display_name,
            "goals": phase.goals,
        },
        "plan_progress": {
            "completed": plan_progress.completed_phases,
            "total": 5,
            "label": plan_progress.current_phase_label,
        },
        "decisions": facts.decisions,
        "experiments": facts.experiments,
        "metrics": facts.metrics,
        "issues": facts.issues,
    }
    user_payload = json.dumps(fact_payload, indent=2)
    logger.debug(
        "Phase summary LLM payload for %s: %s",
        phase.phase_id,
        user_payload,
    )
    system_prompt = (
        "You are an autonomous research lead summarizing a completed phase for a human user. "
        "Synthesize the provided data into a concise narrative that includes: "
        "(1) key decisions and why they mattered, "
        "(2) experiment outcomes and what they imply, "
        "(3) where the run stands relative to the plan, and "
        "(4) whether progress is on_track, at_risk, or blocked. "
        "Offer concrete steering suggestions if progress is uncertain."
        "Don't mention any node.id"
    )
    logger.debug("System prompt: %s", system_prompt)
    llm_response = structured_query_with_schema(
        system_message=system_prompt,
        user_message=user_payload,
        model=journal.summary_model,
        temperature=journal.summary_temperature,
        schema_class=PhaseSummaryLLMResponse,
    )
    logger.info(
        "Phase summary LLM response for %s: confidence=%s goal_alignment=%s",
        phase.phase_id,
        llm_response.confidence,
        llm_response.goal_alignment,
    )
    return PhaseSummaryEnvelope(
        facts=facts,
        llm_summary=llm_response.summary,
        llm_confidence=llm_response.confidence,
        steering_guidance=llm_response.steering_guidance,
        llm_goal_alignment=llm_response.goal_alignment,
    )
