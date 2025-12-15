import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, Field

from ai_scientist.llm import structured_query_with_schema

from .journal import Journal
from .metrics_extraction import analyze_progress, gather_stage_metrics, identify_issues

logger = logging.getLogger(__name__)

_DEFAULT_ARTIFACT_HINTS: tuple[str, ...] = (
    "experiment_logs",
    "metrics_report",
    "generated_code_snapshot",
)
_ARTIFACT_HINTS_BY_SLUG: dict[str, tuple[str, ...]] = {
    "initial_implementation": (
        "baseline_notebook",
        "execution_logs",
        "dataset_selection_notes",
    ),
    "baseline_tuning": (
        "hyperparameter_grid",
        "comparison_table",
        "training_curves",
    ),
    "creative_research": (
        "plots",
        "vlm_feedback",
        "dashboard_assets",
    ),
    "ablation_studies": (
        "ablation_results",
        "analysis_notebook",
        "comparison_plots",
    ),
}
PHASE_DECISION_LIMIT = 6
PHASE_EXPERIMENT_LIMIT = 6
PHASE_ARTIFACT_LIMIT = 10


def expected_artifacts_for_slug(stage_slug: str) -> list[str]:
    hints = _ARTIFACT_HINTS_BY_SLUG.get(stage_slug, _DEFAULT_ARTIFACT_HINTS)
    return list(hints)


@dataclass
class PhaseDefinition:
    phase_id: str
    main_stage_number: int
    substage_number: int
    stage_slug: str
    substage_name: str
    goals: str
    expected_artifacts: list[str]

    @property
    def display_name(self) -> str:
        slug_label = self.stage_slug.replace("_", " ").title()
        return (
            f"Stage {self.main_stage_number}: {slug_label} · "
            f"Substage {self.substage_number} ({self.substage_name})"
        )


@dataclass
class PhasePlanProgress:
    completed_phases: int
    total_phases: int
    current_phase_label: str


@dataclass
class PhaseSummaryFacts:
    phase: PhaseDefinition
    plan_progress: PhasePlanProgress
    decisions: list[dict[str, str]]
    experiments: list[dict[str, Any]]
    artifacts: list[dict[str, str]]
    metrics: dict[str, Any]
    issues: list[str]
    goal_assessment: dict[str, str]


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
                "total": self.facts.plan_progress.total_phases,
                "label": self.facts.plan_progress.current_phase_label,
            },
            "goal_assessment": self.facts.goal_assessment,
            "decisions": self.facts.decisions,
            "experiments": self.facts.experiments,
            "artifacts": self.facts.artifacts,
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
            "Highlight decisive experiments, artifact references, and plan progress."
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


def _collect_phase_decisions(*, journal: "Journal") -> list[dict[str, str]]:
    logger.debug("Collecting phase decisions for stage %s", journal.stage_name)
    decisions: list[dict[str, str]] = []
    seen_signatures: set[str] = set()
    best_node = journal.get_best_node()
    if best_node is not None:
        entry = {
            "kind": "best_node",
            "node_id": best_node.id,
            "node_label": best_node.id[:8],
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
                        "node_label": node.id[:8],
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
                        "node_label": node.id[:8],
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


def _collect_experiment_outcomes(*, journal: "Journal", limit: int) -> list[dict[str, Any]]:
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
                "node_label": node.id[:8],
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


def _collect_artifacts(*, journal: "Journal", limit: int) -> list[dict[str, str]]:
    logger.debug(
        "Collecting artifacts for stage %s (limit=%s)",
        journal.stage_name,
        limit,
    )
    artifacts: list[dict[str, str]] = []
    seen_paths: set[str] = set()
    for node in reversed(journal.nodes):
        if node.exp_results_dir:
            path_str = str(Path(node.exp_results_dir))
            if path_str not in seen_paths:
                artifacts.append(
                    {
                        "kind": "results_dir",
                        "path": path_str,
                        "node_id": node.id[:8],
                    }
                )
                seen_paths.add(path_str)
        for plot_path in node.plot_paths:
            normalized = str(Path(plot_path))
            if normalized not in seen_paths:
                artifacts.append(
                    {
                        "kind": "plot_path",
                        "path": normalized,
                        "node_id": node.id[:8],
                    }
                )
                seen_paths.add(normalized)
        for plot in node.plots:
            normalized = str(plot)
            if normalized not in seen_paths:
                artifacts.append(
                    {
                        "kind": "plot_asset",
                        "path": normalized,
                        "node_id": node.id[:8],
                    }
                )
                seen_paths.add(normalized)
        if len(artifacts) >= limit:
            break
    trimmed = artifacts[-limit:]
    logger.debug(
        "Collected %s artifact references for stage %s: %s",
        len(trimmed),
        journal.stage_name,
        trimmed,
    )
    return list(reversed(trimmed))


def _assess_goal_status(*, journal: "Journal") -> dict[str, str]:
    total_nodes = len(journal.nodes)
    good_count = len(journal.good_nodes)
    best_node = journal.get_best_node()
    if (
        best_node is not None
        and best_node.metric is not None
        and best_node.is_buggy is False
        and best_node.is_buggy_plots is False
    ):
        metric_val = best_node.metric.value
        reason = (
            f"Best node {best_node.id[:8]} reached metric {metric_val} "
            f"with {good_count} stable implementation(s)."
        )
        assessment = {"status": "on_track", "reason": reason}
        logger.info("Goal assessment for stage %s: %s", journal.stage_name, assessment)
        return assessment
    if good_count > 0:
        reason = f"{good_count} working implementation(s) exist but metrics remain inconclusive."
        assessment = {"status": "at_risk", "reason": reason}
        logger.info("Goal assessment for stage %s: %s", journal.stage_name, assessment)
        return assessment
    if total_nodes == 0:
        assessment = {"status": "blocked", "reason": "No experiments executed in this phase."}
        logger.info("Goal assessment for stage %s: %s", journal.stage_name, assessment)
        return assessment
    reason = f"{total_nodes} attempt(s) executed with no stable implementation identified."
    assessment = {"status": "blocked", "reason": reason}
    logger.info("Goal assessment for stage %s: %s", journal.stage_name, assessment)
    return assessment


def _build_phase_summary_facts(
    *,
    journal: "Journal",
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
    artifacts = _collect_artifacts(
        journal=journal,
        limit=PHASE_ARTIFACT_LIMIT,
    )
    goal_assessment = _assess_goal_status(journal=journal)
    facts = PhaseSummaryFacts(
        phase=phase,
        plan_progress=plan_progress,
        decisions=decisions,
        experiments=experiments,
        artifacts=artifacts,
        metrics=metrics_snapshot,
        issues=issues,
        goal_assessment=goal_assessment,
    )
    logger.debug(
        "Phase summary facts ready for %s: decisions=%s experiments=%s artifacts=%s issues=%s",
        phase.phase_id,
        len(decisions),
        len(experiments),
        len(artifacts),
        len(issues),
    )
    return facts


def build_phase_summary(
    *,
    journal: "Journal",
    phase: PhaseDefinition,
    plan_progress: PhasePlanProgress,
) -> PhaseSummaryEnvelope:
    logger.info(
        "Generating phase summary for %s (%s/%s complete)",
        phase.phase_id,
        plan_progress.completed_phases,
        plan_progress.total_phases,
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
            "expected_artifacts": phase.expected_artifacts,
        },
        "plan_progress": {
            "completed": plan_progress.completed_phases,
            "total": plan_progress.total_phases,
            "label": plan_progress.current_phase_label,
        },
        "goal_assessment": facts.goal_assessment,
        "decisions": facts.decisions,
        "experiments": facts.experiments,
        "artifacts": facts.artifacts,
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
        "(3) references to important artifacts, "
        "(4) where the run stands relative to the plan, and "
        "(5) whether progress is on_track, at_risk, or blocked. "
        "Offer concrete steering suggestions if progress is uncertain."
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
