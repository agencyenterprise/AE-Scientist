"""
AgentManager: Orchestrates the staged BFTS experiment lifecycle.

High-level responsibilities:
- Validate and ingest the task description (idea) and runtime config
- Create and track stages/substages via StageMeta and stage classes
- For each substage: create a ParallelAgent, run iterations, and evaluate completion
- On main stage completion: optionally run multi-seed evaluation and aggregate plots
- Persist journals, emit progress/log events, and save checkpoints
- Transition to subsequent substages and main stages until the experiment completes
"""

import copy
import json
import logging
import pickle
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, Literal, Optional, Protocol, Tuple, cast

from pydantic import BaseModel

from ai_scientist.llm import structured_query_with_schema
from ai_scientist.treesearch.events import (
    BaseEvent,
    RunLogEvent,
    RunStageProgressEvent,
    StageSkipWindowEvent,
    SubstageCompletedEvent,
    SubstageSummaryEvent,
)

from . import stage_control
from .journal import Journal, Node
from .metrics_extraction import analyze_progress, gather_stage_metrics, identify_issues
from .multi_seed_evaluation import run_plot_aggregation
from .parallel_agent import ParallelAgent
from .phase_summary import PhaseDefinition, PhasePlanProgress, build_phase_summary
from .stage_identifiers import StageIdentifier
from .stage_skip_coordinator import SkipInProgressError, StageSkipCoordinator
from .stages.base import Stage as StageImpl
from .stages.base import StageContext, StageMeta
from .stages.stage1_baseline import Stage1Baseline
from .stages.stage2_tuning import Stage2Tuning
from .stages.stage3_plotting import Stage3Plotting
from .stages.stage4_ablation import Stage4Ablation
from .utils.config import Config, TaskDescription

logger = logging.getLogger(__name__)


class SubstageGoalResponse(BaseModel):
    goals: str


class StageClass(Protocol):
    MAIN_STAGE_SLUG: str
    DEFAULT_GOALS: str


STAGE_CLASS_BY_IDENTIFIER: Dict[StageIdentifier, StageClass] = {
    StageIdentifier.STAGE1: Stage1Baseline,
    StageIdentifier.STAGE2: Stage2Tuning,
    StageIdentifier.STAGE3: Stage3Plotting,
    StageIdentifier.STAGE4: Stage4Ablation,
}


@dataclass
class StageTransition:
    """Records transition between stages and the reasoning"""

    from_stage: str
    to_stage: str
    reason: str
    config_adjustments: Dict[str, Any]


class AgentManager:
    def __init__(
        self,
        task_desc: TaskDescription,
        cfg: Config,
        workspace_dir: Path,
        event_callback: Callable[[BaseEvent], None],
    ) -> None:
        # Ingest and validate task description (idea)

        # Store runtime configuration and IO context
        self.cfg = cfg
        self.workspace_dir = workspace_dir
        self.event_callback = event_callback
        self.task_desc = task_desc
        # Stage bookkeeping and experiment state
        self.stages: List[StageMeta] = []
        self.current_stage: Optional[StageMeta] = None
        self.journals: Dict[str, Journal] = {}
        self.stage_history: List[StageTransition] = []
        self.completed_stages: List[str] = []
        self._completed_stages: set[str] = set()
        self._final_progress_emitted: set[str] = set()
        self._substage_completed_emitted: set[str] = set()
        self._journal_history: Dict[str, List[Journal]] = {}
        self.phase_plan: list[PhaseDefinition] = []
        # Stage slugs/goals are defined in the stage classes
        # Create initial stage
        # Initialize the experiment with the first stage
        self._create_initial_stage()
        # Track last iteration logs per stage to avoid duplicate spam when a stage stalls
        self._last_logged_iteration_by_stage: Dict[str, int] = {}
        self._last_logged_node_count_by_stage: Dict[str, int] = {}
        self._attempt_iteration_by_stage: Dict[str, int] = {}
        self._forced_stage_completion_reasons: Dict[str, str] = {}
        self._stage_skip_states: Dict[str, bool] = {}
        stage_control.reset_stage_state()

    def get_max_iterations(self, *, stage_identifier: StageIdentifier) -> int:
        """Get max iterations for a stage from config."""
        return self.cfg.agent.stages.max_iters_for_stage(stage_identifier=stage_identifier)

    def get_attempt_iteration(self, stage_name: str) -> int:
        """Return how many iterations have been attempted for a stage."""
        return self._attempt_iteration_by_stage.get(stage_name, 0)

    def _get_task_desc_str(self) -> str:
        task_desc = """You are an ambitious AI researcher who is looking to publish a paper that will contribute significantly to the field.
You have an idea and you want to conduct creative experiments to gain scientific insights.
Your aim is to run experiments to gather sufficient results for a top conference paper.
Your research idea:\n\n
"""
        task_desc += (
            "Title:\n"
            + self.task_desc.title
            + "\n"
            + "Abstract:\n"
            + self.task_desc.abstract
            + "\n"
            + "Short Hypothesis:\n"
            + self.task_desc.short_hypothesis
            + "\n"
        )
        if self.task_desc.code is not None:
            logger.info("Loading code example from idea input")
            task_desc += "Code To Use:\n" + self.task_desc.code + "\n"
        else:
            logger.info("Loading example code from example_code.py")
            example_code_path = Path(__file__).parent.parent / "example_code.py"
            example_code = example_code_path.read_text()
            task_desc += "Code To Use:\n" + example_code + "\n"
        return task_desc

    def _create_initial_stage(self) -> None:
        """Create the initial stage configuration"""
        # Seed Stage 1 (baseline) with defaults defined by the stage class
        identifier = StageIdentifier.STAGE1
        initial_stage = StageMeta(
            identifier=identifier,
            goals=Stage1Baseline.DEFAULT_GOALS,
            max_iterations=self.get_max_iterations(stage_identifier=identifier),
            num_drafts=self.cfg.agent.search.num_drafts,
        )

        self.stages.append(initial_stage)
        self.current_stage = initial_stage
        self.journals[initial_stage.name] = Journal(
            summary_model=self.cfg.report.model,
            node_selection_model=self.cfg.agent.feedback.model,
            summary_temperature=self.cfg.report.temperature,
            node_selection_temperature=self.cfg.agent.feedback.temperature,
            event_callback=self.event_callback,
            stage_name=initial_stage.name,
            run_id=self.cfg.telemetry.run_id if self.cfg.telemetry else None,
        )
        self.register_phase_definition(stage_meta=initial_stage)

    def register_phase_definition(self, *, stage_meta: StageMeta) -> None:
        if any(definition.phase_id == stage_meta.name for definition in self.phase_plan):
            return
        definition = PhaseDefinition(
            phase_id=stage_meta.name,
            main_stage_number=stage_meta.number,
            stage_slug=stage_meta.slug,
            goals=stage_meta.goals,
        )
        self.phase_plan.append(definition)

    def _phase_definition_for_stage(self, *, stage_id: str) -> Optional[PhaseDefinition]:
        for definition in self.phase_plan:
            if definition.phase_id == stage_id:
                return definition
        return None

    def _stage_impl_from_meta(self, *, stage_meta: StageMeta, context: StageContext) -> StageImpl:
        if stage_meta.identifier is StageIdentifier.STAGE1:
            return Stage1Baseline(meta=stage_meta, context=context)
        if stage_meta.identifier is StageIdentifier.STAGE2:
            return Stage2Tuning(meta=stage_meta, context=context)
        if stage_meta.identifier is StageIdentifier.STAGE3:
            return Stage3Plotting(meta=stage_meta, context=context)
        if stage_meta.identifier is StageIdentifier.STAGE4:
            return Stage4Ablation(meta=stage_meta, context=context)
        raise ValueError(f"Unknown stage identifier: {stage_meta.identifier}")

    def _build_stage_impl(self, stage_meta: StageMeta, journal: Journal) -> StageImpl:
        ctx = StageContext(
            cfg=self.cfg,
            task_desc=self._curate_task_desc(stage_meta),
            stage_identifier=stage_meta.identifier,
            journal=journal,
            workspace_dir=self.workspace_dir,
            event_callback=self.event_callback,
            best_nodes_by_stage={},
        )
        return self._stage_impl_from_meta(stage_meta=stage_meta, context=ctx)

    def _publish_stage_control_state(self, stage_meta: StageMeta) -> None:
        journal = self.journals.get(stage_meta.name)
        if journal is None:
            return
        try:
            stage_obj = self._build_stage_impl(stage_meta, journal)
            stage_obj.reset_skip_state()
            can_skip, reason = stage_obj.skip_state()
            safe_reason = reason or "Stage skip state updated."
            logger.info(
                "Stage %s skip state evaluated: can_skip=%s reason=%s",
                stage_meta.name,
                can_skip,
                safe_reason,
            )
            self._update_stage_skip_state(
                stage_name=stage_meta.name,
                can_skip=can_skip,
                reason=safe_reason,
            )
            stage_control.publish_stage_state(
                stage_name=stage_meta.name,
                stage_number=stage_meta.number,
                can_be_skipped=can_skip,
                cannot_skip_reason=safe_reason,
            )
        except Exception:
            logger.exception("Failed to publish stage skip state for %s", stage_meta.name)

    def _emit_stage_skip_window_event(
        self, *, stage_name: str, state: Literal["opened", "closed"], reason: str
    ) -> None:
        try:
            self.event_callback(
                StageSkipWindowEvent(
                    stage=stage_name,
                    state=state,
                    timestamp=datetime.now(timezone.utc),
                    reason=reason,
                )
            )
        except Exception:
            logger.exception("Failed to emit stage skip window event for %s", stage_name)

    def _update_stage_skip_state(self, *, stage_name: str, can_skip: bool, reason: str) -> None:
        previous = self._stage_skip_states.get(stage_name, False)
        if can_skip and not previous:
            self._stage_skip_states[stage_name] = True
            self._emit_stage_skip_window_event(stage_name=stage_name, state="opened", reason=reason)
            logger.info("Stage %s skip window opened (reason=%s)", stage_name, reason)
        elif not can_skip and previous:
            self._stage_skip_states[stage_name] = False
            self._emit_stage_skip_window_event(stage_name=stage_name, state="closed", reason=reason)
            logger.info("Stage %s skip window closed (reason=%s)", stage_name, reason)
        else:
            self._stage_skip_states[stage_name] = can_skip

    def _clear_stage_skip_state(self, *, stage_name: str, reason: str) -> None:
        if self._stage_skip_states.get(stage_name):
            self._stage_skip_states[stage_name] = False
            self._emit_stage_skip_window_event(stage_name=stage_name, state="closed", reason=reason)
            logger.info("Stage %s skip window force-closed (reason=%s)", stage_name, reason)
        self._stage_skip_states.pop(stage_name, None)

    def _clear_all_stage_skip_states(self, *, reason: str) -> None:
        for stage_name, is_open in list(self._stage_skip_states.items()):
            if is_open:
                self._emit_stage_skip_window_event(
                    stage_name=stage_name, state="closed", reason=reason
                )
                logger.info("Stage %s skip window force-closed (reason=%s)", stage_name, reason)
        self._stage_skip_states.clear()

    def _force_stage_completion(self, *, stage_name: str, reason: str) -> None:
        self._forced_stage_completion_reasons[stage_name] = reason

    def _plan_progress_for_phase(self, *, stage_id: str) -> Optional[PhasePlanProgress]:
        for index, definition in enumerate(self.phase_plan):
            if definition.phase_id == stage_id:
                return PhasePlanProgress(
                    completed_phases=index + 1,
                    current_phase_label=definition.display_name,
                )
        return None

    def _curate_task_desc(self, stage: StageMeta) -> str:
        task_desc = self._get_task_desc_str()

        if stage.slug == Stage3Plotting.MAIN_STAGE_SLUG:
            experiments = self.task_desc.experiments
            experiment_str: Optional[str] = None

            if isinstance(experiments, list) and experiments:
                if isinstance(experiments[0], str):
                    experiment_str = "\n".join(cast(List[str], experiments))
                elif isinstance(experiments[0], dict):
                    experiments_list = cast(List[Dict[str, str]], experiments)
                    experiment_str = "\n".join(
                        [f"{k}: {v}" for d in experiments_list for k, v in d.items()]
                    )
            elif isinstance(experiments, str):
                experiment_str = experiments

            if experiment_str is not None:
                task_desc += "Experiment Plan: " + experiment_str + "\n"
        elif stage.slug == Stage4Ablation.MAIN_STAGE_SLUG:
            if isinstance(self.task_desc.risk_factors_and_limitations, list):
                risk_factors_str = "\n".join(self.task_desc.risk_factors_and_limitations)
            else:
                risk_factors_str = self.task_desc.risk_factors_and_limitations
            task_desc += "Risk Factors and Limitations: " + risk_factors_str + "\n"

        return task_desc

    def _save_checkpoint(self) -> None:
        """Save the current state of the experiment"""
        # Persist journals, config and current stage for resuming/review
        if self.current_stage is None:
            logger.warning("Cannot save checkpoint: current_stage is None")
            return
        stage_name = "stage_" + self.current_stage.name
        save_path = (
            Path(self.workspace_dir).parent
            / "logs"
            / Path(self.workspace_dir).name
            / stage_name
            / "checkpoint.pkl"
        )
        checkpoint = {
            "journals": self.journals,
            "stage_history": self.stage_history,
            "task_desc": self.task_desc,
            "cfg": self.cfg,
            "workspace_dir": self.workspace_dir,
            "current_stage": self.current_stage,
        }
        logger.info(f"Saving checkpoint to {save_path}")
        with open(save_path, "wb") as f:
            pickle.dump(checkpoint, f)

    def _create_agent_for_stage(self, stage: StageMeta) -> ParallelAgent:
        """Create a ParallelAgent configured for the given stage"""
        # Derive a stage-local copy of config and curated task description
        stage_cfg = copy.deepcopy(self.cfg)
        stage_cfg.agent.search.num_drafts = stage.num_drafts
        task_desc = self._curate_task_desc(stage)

        task_desc = f"{task_desc}\n\nCurrent Main Stage: {stage.slug}\n"
        task_desc += f"Sub-stage goals: {stage.goals}"

        # Determine carryover best nodes based on current main stage
        if stage.identifier is StageIdentifier.STAGE2:
            stage1_substages = [s for s in self.stages if s.identifier is StageIdentifier.STAGE1]
            if not stage1_substages:
                raise ValueError(f"No stage 1 substages found in {self.stages}")
            best_stage1_node = self._get_best_implementation(stage1_substages[-1].name)
            best_stage2_node = None
            best_stage3_node = None
        elif stage.identifier is StageIdentifier.STAGE3:
            stage2_substages = [s for s in self.stages if s.identifier is StageIdentifier.STAGE2]
            if not stage2_substages:
                raise ValueError(f"No stage 2 substages found in {self.stages}")
            best_stage2_node = self._get_best_implementation(stage2_substages[-1].name)
            best_stage1_node = None
            best_stage3_node = None
        elif stage.identifier is StageIdentifier.STAGE4:
            # Use the last (sub-)stage's best node
            stage3_substages = [s for s in self.stages if s.identifier is StageIdentifier.STAGE3]
            if stage3_substages:
                last_substage = stage3_substages[-1]
                best_stage3_node = self._get_best_implementation(last_substage.name)
                best_stage2_node = None
                best_stage1_node = None
            else:
                raise ValueError(f"No stage 3 substages found in {self.stages}")
        else:
            best_stage3_node = None
            best_stage2_node = None
            best_stage1_node = None

        # Construct the worker agent for this substage
        return ParallelAgent(
            task_desc=task_desc,
            cfg=stage_cfg,
            journal=self.journals[stage.name],
            stage_identifier=stage.identifier,
            best_stage3_node=best_stage3_node,
            best_stage2_node=best_stage2_node,
            best_stage1_node=best_stage1_node,
            event_callback=self.event_callback,
        )

    def _check_substage_completion(
        self, current_substage: StageMeta, journal: Journal
    ) -> Tuple[bool, str]:
        """Check if the current sub-stage is complete"""
        # Terminate if max iterations reached
        limit = current_substage.max_iterations
        if len(journal.nodes) >= limit:
            logger.info(f"Stage {current_substage.name} completed: reached max iterations")
            return True, "Reached max iterations"
        stage_obj = self._build_stage_impl(current_substage, journal)
        return stage_obj.evaluate_substage_completion()

    def _check_stage_completion(self, stage: StageMeta) -> Tuple[bool, str]:
        """Check if current stage is complete based on criteria"""
        journal = self.journals[stage.name]
        # Terminate if max iterations reached
        limit = stage.max_iterations
        if len(journal.nodes) >= limit:
            logger.info(f"Stage {stage.name} completed: reached max iterations")
            if stage.identifier is StageIdentifier.STAGE1:
                # For initial stage, if it didn't even find a working implementation until max iterations,
                # end gracefully and stop the experiment.
                logger.error(
                    f"Initial stage {stage.name} did not find a working implementation after {limit} iterations. Consider increasing the max iterations or reducing the complexity of the research idea."
                )
                logger.error(
                    f"Experiment ended: Could not find working implementation in initial stage after {limit} iterations"
                )
                self.current_stage = None  # This will cause the run loop to exit
                return True, "Failed to find working implementation"
            else:
                return True, "Reached max iterations"

        forced_reason = self._forced_stage_completion_reasons.pop(stage.name, None)
        if forced_reason is not None:
            logger.info("Stage %s marked complete via override: %s", stage.name, forced_reason)
            return True, forced_reason

        stage_obj = self._build_stage_impl(stage, journal)
        return stage_obj.evaluate_stage_completion()

    def _get_best_implementation(self, stage_name: str) -> Optional[Node]:
        """Get the best implementation from a completed stage"""
        candidates: List[Journal] = []
        current_journal = self.journals.get(stage_name)
        if current_journal is not None:
            candidates.append(current_journal)
        history = self._journal_history.get(stage_name, [])
        if history:
            candidates.extend(reversed(history))

        for journal in candidates:
            best_node = journal.get_best_node()
            if best_node:
                # Create a clean copy of the node for the next stage
                copied_node = copy.deepcopy(best_node)
                # Reset parent relationship and children
                copied_node.parent = None
                copied_node.children = set()
                return copied_node
        return None

    def _generate_substage_goal(self, main_stage_goal: str, journal: Journal) -> str:
        """Generate the next sub-stage goal based on what has been done so far.

        Args:
            main_stage_goal: The overall goal for the current main stage
            journal: Journal containing the results and progress so far

        Returns:
            str: Specific goals for the next sub-stage
        """
        # Gather context for LLM: metrics, issues and recent progress
        metrics = gather_stage_metrics(journal=journal)
        issues = identify_issues(journal=journal)
        progress = analyze_progress(journal=journal)

        # Create prompt for the LLM
        best_metric = metrics.get("best_metric")
        best_value_str = "N/A"
        if isinstance(best_metric, dict):
            val = best_metric.get("value")
            best_value_str = str(val) if val is not None else "N/A"
        prompt = f"""
        Based on the current experimental progress, generate focused goals for the next sub-stage.

        Main Stage Goals:
        {main_stage_goal}

        Current Progress:
        - Total attempts: {metrics['total_nodes']}
        - Successful implementations: {metrics['good_nodes']}
        - Best performance: {best_value_str}
        - Convergence status: {progress['convergence_status']}

        Current Issues:
        {json.dumps(issues, indent=2)}

        Recent Changes:
        {json.dumps(progress['recent_changes'], indent=2)}

        Generate specific, actionable sub-stage goals that:
        1. Address current issues and limitations
        2. Build on recent progress
        3. Move towards main stage goals
        4. Are concrete and measurable
        """

        try:
            # Get response from LLM
            response = structured_query_with_schema(
                system_message=prompt,
                user_message=None,
                model=self.cfg.agent.feedback.model,
                temperature=self.cfg.agent.feedback.temperature,
                schema_class=SubstageGoalResponse,
            )
            goal_str = f"""
            {response.goals}
            """

            return goal_str.strip()

        except Exception:
            logger.exception("Error generating sub-stage goals")
            # Provide fallback goals if LLM fails
            return """
            Sub-stage Goals:
            Continue progress on main stage objectives while addressing current issues.
            """.strip()

    def _create_next_substage(
        self, current_substage: StageMeta, journal: Journal
    ) -> Optional[StageMeta]:
        """Create the next sub-stage. Ask LLM to come up with the next sub-stage name and goals
        based on what has been done so far.
        """
        # Build the next substage metadata using stage class defaults and LLM goal
        current_stage_cls = STAGE_CLASS_BY_IDENTIFIER[current_substage.identifier]
        main_stage_goal = current_stage_cls.DEFAULT_GOALS
        identifier = current_substage.identifier
        sub_stage_goal = self._generate_substage_goal(main_stage_goal, journal)

        return StageMeta(
            identifier=identifier,
            goals="Main stage goals:\n"
            + main_stage_goal
            + "\n\nSub-stage goals:\n"
            + sub_stage_goal,
            max_iterations=self.get_max_iterations(stage_identifier=identifier),
            num_drafts=0,
        )

    def _stash_current_journal(self, *, stage_name: str) -> None:
        """Preserve the current journal before overwriting it for a new sub-stage."""
        journal = self.journals.get(stage_name)
        if journal is None:
            return
        self._journal_history.setdefault(stage_name, []).append(journal)

    def _create_next_main_stage(self, current_substage: StageMeta) -> Optional[StageMeta]:
        current_identifier = current_substage.identifier
        next_identifier = current_identifier.next_stage()
        if next_identifier is None:
            return None
        next_stage_cls = STAGE_CLASS_BY_IDENTIFIER[next_identifier]
        num_drafts = 0
        main_stage_goal = next_stage_cls.DEFAULT_GOALS

        return StageMeta(
            identifier=next_identifier,
            goals=main_stage_goal,
            max_iterations=self.get_max_iterations(stage_identifier=next_identifier),
            num_drafts=num_drafts,
        )

    def _prepare_substage(self, current_substage: StageMeta) -> bool:
        """Seed a new sub-stage with the previous best node when available.

        Returns True if preparation succeeded or was not needed; False if we expected
        a previous best but could not find it.
        """
        if self.stage_history:
            prev_stage = self.stage_history[-1].from_stage
            logger.debug(f"prev_stage: {prev_stage}")
            logger.debug(f"self.stage_history: {self.stage_history}")
            prev_best = self._get_best_implementation(prev_stage)
            if prev_best:
                self.journals[current_substage.name].append(prev_best)
                return True
            logger.error(
                f"No previous best implementation found for {current_substage.name}. Something went wrong so finishing the experiment..."
            )
            return False
        return True

    def _perform_multi_seed_eval_if_needed(
        self,
        agent: ParallelAgent,
        current_substage: StageMeta,
        step_callback: Optional[Callable[[StageMeta, Journal], None]],
    ) -> bool:
        """Run multi-seed evaluation and plot aggregation when a main stage completes.

        Returns True on success, False if a required best node could not be found.
        """
        best_node = self._get_best_implementation(current_substage.name)
        if not best_node:
            logger.error(
                f"No best node found for {current_substage.name} during multi-seed eval, something went wrong so finishing the experiment..."
            )
            return False

        seed_nodes = agent._run_multi_seed_evaluation(best_node)
        if step_callback:
            step_callback(current_substage, self.journals[current_substage.name])
        run_plot_aggregation(agent=agent, node=best_node, seed_nodes=seed_nodes)
        if step_callback:
            step_callback(current_substage, self.journals[current_substage.name])
        logger.info(f"Stage {current_substage.name} multi-seed eval done.")

        return True

    def _emit_final_progress_if_needed(
        self, *, current_substage: StageMeta, journal: Journal
    ) -> None:
        """Ensure a single final progress=1.0 event per stage."""
        if current_substage.name in self._final_progress_emitted:
            return
        final_iteration = len(journal.nodes)
        try:
            self.event_callback(
                RunStageProgressEvent(
                    stage=current_substage.name,
                    iteration=final_iteration,
                    max_iterations=current_substage.max_iterations,
                    progress=1.0,
                    total_nodes=len(journal.nodes),
                    buggy_nodes=len(journal.buggy_nodes),
                    good_nodes=len(journal.good_nodes),
                    best_metric=(
                        str(best_node.metric) if (best_node := journal.get_best_node()) else None
                    ),
                    eta_s=None,
                    latest_iteration_time_s=None,
                )
            )
        except Exception:
            logger.exception("Failed to emit final RunStageProgressEvent")
        self._final_progress_emitted.add(current_substage.name)

    def _emit_substage_completed_event(
        self, *, current_substage: StageMeta, journal: Journal, reason: str
    ) -> None:
        """Emit SubstageCompletedEvent once per substage."""
        if current_substage.name in self._substage_completed_emitted:
            return
        try:
            best_node = journal.get_best_node()
            summary: Dict[str, Any] = {
                "goals": current_substage.goals,
                "total_nodes": len(journal.nodes),
                "buggy_nodes": len(journal.buggy_nodes),
                "good_nodes": len(journal.good_nodes),
                "best_metric": (str(best_node.metric) if best_node and best_node.metric else None),
                "feedback": reason,
            }
            phase_definition = self._phase_definition_for_stage(stage_id=current_substage.name)
            plan_progress = None
            if phase_definition is not None:
                plan_progress = self._plan_progress_for_phase(stage_id=current_substage.name)
            if phase_definition is not None and plan_progress is not None:
                try:
                    phase_summary = build_phase_summary(
                        journal=journal,
                        phase=phase_definition,
                        plan_progress=plan_progress,
                    )
                    summary["phase_summary"] = phase_summary.to_dict()
                    self.event_callback(
                        SubstageSummaryEvent(
                            stage=current_substage.name,
                            summary=phase_summary.to_dict(),
                        )
                    )
                except Exception:
                    logger.exception(
                        "Failed to generate phase summary for %s", current_substage.name
                    )
            self.event_callback(
                SubstageCompletedEvent(
                    stage=current_substage.name,
                    main_stage_number=current_substage.number,
                    reason=reason,
                    summary=summary,
                )
            )
        except Exception:
            logger.exception("Failed to emit SubstageCompletedEvent")
        self._substage_completed_emitted.add(current_substage.name)

    def has_stage_completed(self, stage_name: str) -> bool:
        return stage_name in self._completed_stages

    def _run_substage(
        self,
        current_substage: StageMeta,
        agent: ParallelAgent,
        step_callback: Optional[Callable[[StageMeta, Journal], None]],
        iteration_started_callback: Callable[[StageMeta, Journal], None],
    ) -> Tuple[bool, Optional[StageMeta]]:
        """Execute iterations for a sub-stage until it completes or the main stage finishes.

        Returns a tuple: (main_stage_completed, next_substage)
        - If main_stage_completed is True, the caller should move to the next main stage
          (or stop if there is none).
        - If False and next_substage is provided, the caller should continue with that sub-stage.
        """
        stage_skip = StageSkipCoordinator(stage_identifier=current_substage.identifier)
        skip_reason_default = "Stage skipped by operator."

        while True:
            # Emit iteration log before each step; progress events are handled in step_callback.
            stage_name = current_substage.name
            journal = self.journals[stage_name]
            max_iters = current_substage.max_iterations
            node_count = len(journal.nodes)
            self._publish_stage_control_state(current_substage)
            skip_requested, skip_reason = stage_skip.consume_pending_request()
            skip_reason_text = skip_reason or skip_reason_default
            if not skip_requested:
                current_iter = self._attempt_iteration_by_stage.get(stage_name, 0) + 1
                self._attempt_iteration_by_stage[stage_name] = current_iter
            else:
                current_iter = self._attempt_iteration_by_stage.get(stage_name, 0)

            logger.debug(f"Stage {stage_name}: Iteration {current_iter}/{max_iters}")

            last_node_count = self._last_logged_node_count_by_stage.get(stage_name)
            if last_node_count is not None and node_count < last_node_count:
                # Stage restarted; reset tracking so iteration logs resume from 1.
                self._last_logged_node_count_by_stage.pop(stage_name, None)
                self._last_logged_iteration_by_stage.pop(stage_name, None)
            last_logged_iter = self._last_logged_iteration_by_stage.get(stage_name)
            if last_logged_iter is None or current_iter > last_logged_iter:
                self._last_logged_iteration_by_stage[stage_name] = current_iter
                self._last_logged_node_count_by_stage[stage_name] = node_count
                if not skip_requested:
                    try:
                        self.event_callback(
                            RunLogEvent(
                                message=f"Stage {stage_name}: Iteration {current_iter}/{max_iters}",
                                level="info",
                            )
                        )
                    except Exception:
                        # Best-effort logging; never block iteration on event errors
                        pass

            # Drive one iteration of the agent to make forward progress.
            skip_effective = skip_requested
            skip_reason_effective = skip_reason_text
            if skip_effective:
                agent.abort_active_executions(reason=skip_reason_effective)
            else:
                try:
                    iteration_started_callback(
                        current_substage, self.journals[current_substage.name]
                    )
                    agent.step()
                except SkipInProgressError as exc:
                    logger.info(
                        "Skip detected mid-iteration for stage %s: %s",
                        stage_name,
                        exc.reason,
                    )
                    skip_effective = True
                    skip_reason_effective = exc.reason
                    agent.abort_active_executions(reason=skip_reason_effective)
                else:
                    if step_callback:
                        step_callback(current_substage, self.journals[current_substage.name])

            if skip_effective:
                logger.info("Skip requested for stage %s: %s", stage_name, skip_reason_effective)
                self._force_stage_completion(stage_name=stage_name, reason=skip_reason_effective)
                try:
                    self.event_callback(
                        RunLogEvent(
                            message=f"Skipping stage {stage_name}: {skip_reason_effective}",
                            level="warn",
                        )
                    )
                except Exception:
                    pass

            skip_requested = skip_effective
            skip_reason_text = skip_reason_effective

            # Check if sub-stage is complete (check this before main stage completion)
            if skip_requested:
                substage_complete = True
                substage_feedback = skip_reason_text
            else:
                substage_complete, substage_feedback = self._check_substage_completion(
                    current_substage, self.journals[current_substage.name]
                )

            # Check if main stage is complete
            if skip_requested:
                main_stage_complete = True
                main_stage_feedback = skip_reason_text
            else:
                main_stage_complete, main_stage_feedback = self._check_stage_completion(
                    current_substage
                )
            logger.debug(f"Feedback from _check_stage_completion: {main_stage_feedback}")

            # If substage completes, emit event (even if main stage also completes)
            if substage_complete:
                self._emit_substage_completed_event(
                    current_substage=current_substage,
                    journal=self.journals[current_substage.name],
                    reason=substage_feedback,
                )

            # If main stage completes, run multi-seed eval and return
            if main_stage_complete:
                self._completed_stages.add(current_substage.name)
                self._clear_stage_skip_state(
                    stage_name=current_substage.name,
                    reason=main_stage_feedback or "Stage completed",
                )
                self._emit_final_progress_if_needed(
                    current_substage=current_substage,
                    journal=self.journals[current_substage.name],
                )
                if current_substage.name not in self._substage_completed_emitted:
                    self._emit_substage_completed_event(
                        current_substage=current_substage,
                        journal=self.journals[current_substage.name],
                        reason=main_stage_feedback,
                    )
                # After main stage completion, run multi-seed eval on the best node
                multi_seed_ok = self._perform_multi_seed_eval_if_needed(
                    agent=agent,
                    current_substage=current_substage,
                    step_callback=step_callback,
                )
                if not multi_seed_ok:
                    # If multi-seed eval failed, we should still try to advance to next stage
                    # Setting current_stage = None here would prevent that
                    # Instead, let the caller handle this case
                    pass
                return True, None

            # If substage completes but main stage doesn't, create next substage
            if substage_complete:
                # Create next sub-stage
                next_substage = self._create_next_substage(
                    current_substage=current_substage,
                    journal=self.journals[current_substage.name],
                )
                if next_substage:
                    # Record sub-stage transition
                    self.stage_history.append(
                        StageTransition(
                            from_stage=current_substage.name,
                            to_stage=next_substage.name,
                            reason=substage_feedback,
                            config_adjustments={},
                        )
                    )

                    # Setup new sub-stage
                    self._stash_current_journal(stage_name=current_substage.name)
                    self.stages.append(next_substage)
                    self.register_phase_definition(stage_meta=next_substage)
                    self.journals[next_substage.name] = Journal(
                        summary_model=self.cfg.report.model,
                        node_selection_model=self.cfg.agent.feedback.model,
                        summary_temperature=self.cfg.report.temperature,
                        node_selection_temperature=self.cfg.agent.feedback.temperature,
                        event_callback=self.event_callback,
                        stage_name=next_substage.name,
                        run_id=self.cfg.telemetry.run_id if self.cfg.telemetry else None,
                    )
                    return False, next_substage

                # If no next sub-stage could be created, end this main stage
                return True, None

    def _advance_to_next_main_stage(self) -> None:
        """Advance to the next main stage if available; otherwise finish."""
        if not self.current_stage:
            return
        # Promote the last substage to the first substage of the next main stage
        next_main_stage = self._create_next_main_stage(
            current_substage=self.stages[-1],
        )
        if next_main_stage:
            # Record main stage transition
            self.stage_history.append(
                StageTransition(
                    from_stage=self.stages[-1].name,
                    to_stage=next_main_stage.name,
                    reason=f"Moving to {next_main_stage.name}",
                    config_adjustments={},
                )
            )

            self.stages.append(next_main_stage)
            self.register_phase_definition(stage_meta=next_main_stage)
            self.journals[next_main_stage.name] = Journal(
                summary_model=self.cfg.report.model,
                node_selection_model=self.cfg.agent.feedback.model,
                summary_temperature=self.cfg.report.temperature,
                node_selection_temperature=self.cfg.agent.feedback.temperature,
                event_callback=self.event_callback,
                stage_name=next_main_stage.name,
                run_id=self.cfg.telemetry.run_id if self.cfg.telemetry else None,
            )
            self.current_stage = next_main_stage
            self._publish_stage_control_state(next_main_stage)
        else:
            # Exit the outer loop if no more main stages
            logger.info(f"Completed stage: {self.current_stage.name}")
            logger.info("No more stages to run -- exiting the loop...")
            self.current_stage = None
            self._clear_all_stage_skip_states(reason="All stages completed")
            stage_control.clear_stage_state()

    def run(
        self,
        step_callback: Optional[Callable[[StageMeta, Journal], None]],
        iteration_started_callback: Callable[[StageMeta, Journal], None],
    ) -> None:
        """Run the experiment through generated stages"""
        # Main stage loop
        while self.current_stage:
            logger.info(f"Starting main stage: {self.current_stage.slug}")
            logger.info(f"Goals: {self.current_stage.goals}")
            # Run only the current main stage
            self.run_stage(
                initial_substage=self.current_stage,
                step_callback=step_callback,
                iteration_started_callback=iteration_started_callback,
            )
            # Main stage complete - create next main stage
            self._advance_to_next_main_stage()

    def run_stage(
        self,
        initial_substage: StageMeta,
        step_callback: Optional[Callable[[StageMeta, Journal], None]],
        iteration_started_callback: Callable[[StageMeta, Journal], None],
    ) -> None:
        """Run a single main stage starting from the given sub-stage.

        This executes the sub-stage loop until the main stage completes,
        performs any post-stage evaluation, and saves a checkpoint.
        """
        current_substage: Optional[StageMeta] = initial_substage
        if current_substage is not None:
            self._publish_stage_control_state(current_substage)
        while current_substage:
            logger.info(f"Starting sub-stage: {current_substage.name}")
            logger.info(
                f"Max iterations for {current_substage.name}: {current_substage.max_iterations}"
            )
            try:
                self.event_callback(
                    RunLogEvent(
                        message=(
                            f"Starting sub-stage {current_substage.name} "
                            f"(max iterations: {current_substage.max_iterations})"
                        ),
                        level="info",
                    )
                )
            except Exception:
                pass

            with self._create_agent_for_stage(current_substage) as agent:
                # Initialize with best result from previous sub-stage if available
                if not self._prepare_substage(current_substage=current_substage):
                    self._clear_stage_skip_state(
                        stage_name=current_substage.name,
                        reason="Stage preparation failed",
                    )
                    self.current_stage = None
                    current_substage = None
                    break

                # Run until sub-stage completion or main stage completion
                main_done, maybe_next_substage = self._run_substage(
                    current_substage=current_substage,
                    agent=agent,
                    step_callback=step_callback,
                    iteration_started_callback=iteration_started_callback,
                )
                if main_done:
                    # Don't set self.current_stage = None here - let _advance_to_next_main_stage() handle it
                    # This allows the next main stage to be created properly
                    current_substage = None
                else:
                    current_substage = maybe_next_substage
        # Save checkpoint using the last completed stage (before advancing to next)
        if self.current_stage:
            self._save_checkpoint()
        else:
            self._clear_all_stage_skip_states(reason="Experiment halted")
            stage_control.clear_stage_state()

    def _gather_stage_metrics(self, journal: Journal) -> Dict[str, Any]:
        """Gather detailed metrics and analysis from the stage's nodes"""
        metrics: Dict[str, Any] = {
            "total_nodes": len(journal.nodes),
            "good_nodes": len(journal.good_nodes),
            "buggy_nodes": len(journal.buggy_nodes),
            "best_metric": None,
            "node_summaries": [],
            "vlm_feedback": [],
        }

        # Gather individual node summaries
        for node in journal.nodes:
            if node.agent is not None:
                node_summary = node.agent.generate_node_summary(node)
                metrics["node_summaries"].append(node_summary)

        # Get VLM feedback from plot analysis
        for node in journal.good_nodes:
            if node.vlm_feedback is not None:
                metrics["vlm_feedback"].append(node.vlm_feedback)

        best_node = journal.get_best_node()
        if best_node and best_node.metric is not None:
            metrics["best_metric"] = {
                "value": best_node.metric.value,
                "name": best_node.metric.name or "validation_metric",
                "maximize": bool(best_node.metric.maximize),
                "analysis": best_node.analysis,
            }

        return metrics

    def _identify_issues(self, journal: Journal) -> List[str]:
        """Identify systemic issues and challenges from the current stage's results"""
        issues = []

        # Look for patterns in leaf nodes (endpoints of improvement attempts)
        leaf_nodes = [n for n in journal.nodes if n.is_leaf]
        buggy_leaves = [n for n in leaf_nodes if n.is_buggy]

        # If we have buggy leaf nodes, it means we couldn't fix some issues
        if buggy_leaves:
            # Group similar issues
            error_patterns: Dict[str, List[str]] = {}
            for node in buggy_leaves:
                key = node.analysis if node.analysis is not None else "Unknown error"
                error_patterns.setdefault(key, []).append(node.id)

            # Report persistent issues
            for error_msg, node_ids in error_patterns.items():
                if len(node_ids) >= 2:  # If same error occurs multiple times
                    issues.append(f"Persistent issue in nodes {node_ids}: {error_msg}")

        # Include VLM-identified systemic issues
        vlm_issues = set()  # Use set to avoid duplicate issues
        for node in journal.good_nodes:
            vlm_feedback = node.vlm_feedback
            if isinstance(vlm_feedback, dict):
                # Look for systemic issues identified by VLM
                if "systemic_issues" in vlm_feedback:
                    vlm_issues.update(vlm_feedback["systemic_issues"])
                # Look for recurring patterns in plot analysis
                if "plot_analyses" in vlm_feedback:
                    for analysis in vlm_feedback["plot_analyses"]:
                        if "limitation" in analysis.get("type", "").lower():
                            vlm_issues.add(f"VLM (Node {node.id}): {analysis['analysis']}")

        issues.extend(list(vlm_issues))

        return issues

    def _analyze_progress(self, journal: Journal) -> Dict[str, Any]:
        """Analyze progress and convergence in the current stage"""
        progress: Dict[str, Any] = {
            "iterations_completed": len(journal.nodes),
            "improvements_found": 0,
            "convergence_status": "not_converged",
            "improvement_trend": [],
            "recent_changes": [],
        }

        # Analyze recent changes
        recent_nodes = journal.nodes[-3:] if len(journal.nodes) >= 3 else journal.nodes
        for node in recent_nodes:
            if not node.is_buggy:
                change = {
                    "node_id": node.id,
                    "metric": (node.metric.value if node.metric is not None else None),
                    "parent_id": node.parent.id if node.parent else None,
                    "analysis": node.analysis,
                }
                progress["recent_changes"].append(change)

        return progress
