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
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Protocol, Tuple, cast

from ai_scientist.llm import FunctionSpec, query
from ai_scientist.treesearch.events import BaseEvent, RunLogEvent, RunStageProgressEvent

from .journal import Journal, Node
from .metrics_extraction import analyze_progress, gather_stage_metrics, identify_issues
from .multi_seed_evaluation import run_plot_aggregation
from .parallel_agent import ExecCallbackType, ParallelAgent
from .stages.base import Stage as StageImpl
from .stages.base import StageContext, StageMeta
from .stages.stage1_baseline import Stage1Baseline
from .stages.stage2_tuning import Stage2Tuning
from .stages.stage3_plotting import Stage3Plotting
from .stages.stage4_ablation import Stage4Ablation
from .utils.config import Config, TaskDescription

logger = logging.getLogger(__name__)


class StageClass(Protocol):
    MAIN_STAGE_SLUG: str
    DEFAULT_GOALS: str


stage_completion_eval_spec = FunctionSpec(
    name="evaluate_stage_completion",
    description="Evaluate if the current stage is complete",
    json_schema={
        "type": "object",
        "properties": {
            "is_complete": {
                "type": "boolean",
                "description": "Whether the current stage is complete",
            },
            "reasoning": {
                "type": "string",
                "description": "Detailed reasoning for the decision",
            },
            "missing_criteria": {
                "type": "array",
                "items": {"type": "string"},
                "description": "List of criteria still needed",
            },
        },
        "required": ["is_complete", "reasoning", "missing_criteria"],
    },
)


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
        self.current_stage_number = 0
        # Stage bookkeeping and experiment state
        self.stages: List[StageMeta] = []
        self.current_stage: Optional[StageMeta] = None
        self.journals: Dict[str, Journal] = {}
        self.stage_history: List[StageTransition] = []
        self.completed_stages: List[str] = []
        # Stage slugs/goals are defined in the stage classes
        # Create initial stage
        # Initialize the experiment with the first stage
        self._create_initial_stage()

    def get_max_iterations(self, stage_number: int) -> int:
        """Get max iterations for a stage from config or default"""
        return self.cfg.agent.stages.get(f"stage{stage_number}_max_iters", self.cfg.agent.steps)

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
        self.current_stage_number += 1
        initial_stage = StageMeta(
            name=f"1_{Stage1Baseline.MAIN_STAGE_SLUG}_1_preliminary",
            number=self.current_stage_number,
            slug=Stage1Baseline.MAIN_STAGE_SLUG,
            substage_number=1,
            substage_name="preliminary",
            goals=Stage1Baseline.DEFAULT_GOALS,
            max_iterations=self.get_max_iterations(self.current_stage_number),
            num_drafts=self.cfg.agent.search.num_drafts,
        )

        self.stages.append(initial_stage)
        self.current_stage = initial_stage
        self.journals[initial_stage.name] = Journal(
            summary_model=self.cfg.report.model,
            node_selection_model=self.cfg.agent.feedback.model,
            summary_temperature=self.cfg.report.temp,
            node_selection_temperature=self.cfg.agent.feedback.temp,
            event_callback=self.event_callback,
        )

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
        task_desc += f"Sub-stage: {stage.substage_number} - {stage.substage_name}\n"
        task_desc += f"Sub-stage goals: {stage.goals}"

        # Determine carryover best nodes based on current main stage
        if stage.number == 2:
            stage1_substages = [s for s in self.stages if s.number == 1]
            if not stage1_substages:
                raise ValueError(f"No stage 1 substages found in {self.stages}")
            best_stage1_node = self._get_best_implementation(stage1_substages[-1].name)
            best_stage2_node = None
            best_stage3_node = None
        elif stage.number == 3:
            stage2_substages = [s for s in self.stages if s.number == 2]
            if not stage2_substages:
                raise ValueError(f"No stage 2 substages found in {self.stages}")
            best_stage2_node = self._get_best_implementation(stage2_substages[-1].name)
            best_stage1_node = None
            best_stage3_node = None
        elif stage.number == 4:
            # Use the last (sub-)stage's best node
            stage3_substages = [s for s in self.stages if s.number == 3]
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
            stage_name=stage.name,
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
        if len(journal.nodes) >= current_substage.max_iterations:
            logger.info(f"Stage {current_substage.name} completed: reached max iterations")
            return True, "Reached max iterations"
        main_stage_num = current_substage.number

        ctx = StageContext(
            cfg=self.cfg,
            task_desc=self._curate_task_desc(current_substage),
            stage_name=current_substage.name,
            journal=journal,
            workspace_dir=self.workspace_dir,
            event_callback=self.event_callback,
            best_nodes_by_stage={},
        )
        # Delegate substage completion to the corresponding Stage implementation
        stage_obj: StageImpl
        if main_stage_num == 1:
            stage_obj = Stage1Baseline(meta=current_substage, context=ctx)
        elif main_stage_num == 2:
            stage_obj = Stage2Tuning(meta=current_substage, context=ctx)
        elif main_stage_num == 3:
            stage_obj = Stage3Plotting(meta=current_substage, context=ctx)
        elif main_stage_num == 4:
            stage_obj = Stage4Ablation(meta=current_substage, context=ctx)
        else:
            raise ValueError(f"Unknown stage number: {main_stage_num}")
        return stage_obj.evaluate_substage_completion()

    def _check_stage_completion(self, stage: StageMeta) -> Tuple[bool, str]:
        """Check if current stage is complete based on criteria"""
        journal = self.journals[stage.name]
        # Terminate if max iterations reached
        if len(journal.nodes) >= stage.max_iterations:
            logger.info(f"Stage {stage.name} completed: reached max iterations")
            if stage.number == 1:
                # For initial stage, if it didn't even find a working implementation until max iterations,
                # end gracefully and stop the experiment.
                logger.error(
                    f"Initial stage {stage.name} did not find a working implementation after {stage.max_iterations} iterations. Consider increasing the max iterations or reducing the complexity of the research idea."
                )
                logger.error(
                    f"Experiment ended: Could not find working implementation in initial stage after {stage.max_iterations} iterations"
                )
                self.current_stage = None  # This will cause the run loop to exit
                return True, "Failed to find working implementation"
            else:
                return True, "Reached max iterations"

        main_stage_num = stage.number

        ctx = StageContext(
            cfg=self.cfg,
            task_desc=self._curate_task_desc(stage),
            stage_name=stage.name,
            journal=journal,
            workspace_dir=self.workspace_dir,
            event_callback=self.event_callback,
            best_nodes_by_stage={},
        )
        # Delegate main stage completion to the Stage implementation
        stage_obj: StageImpl
        if main_stage_num == 1:
            stage_obj = Stage1Baseline(meta=stage, context=ctx)
        elif main_stage_num == 2:
            stage_obj = Stage2Tuning(meta=stage, context=ctx)
        elif main_stage_num == 3:
            stage_obj = Stage3Plotting(meta=stage, context=ctx)
        elif main_stage_num == 4:
            stage_obj = Stage4Ablation(meta=stage, context=ctx)
        else:
            raise ValueError(f"Unknown stage number: {main_stage_num}")
        return stage_obj.evaluate_stage_completion()

    def _get_best_implementation(self, stage_name: str) -> Optional[Node]:
        """Get the best implementation from a completed stage"""
        if stage_name not in self.journals:
            return None
        best_node = self.journals[stage_name].get_best_node()
        if best_node:
            # Create a clean copy of the node for the next stage
            copied_node = copy.deepcopy(best_node)
            # Reset parent relationship and children
            copied_node.parent = None
            copied_node.children = set()
            return copied_node
        return None

    def _generate_substage_goal(self, main_stage_goal: str, journal: Journal) -> Tuple[str, str]:
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

        # Define the function specification for the LLM
        substage_goal_spec = FunctionSpec(
            name="generate_substage_goals",
            description="Generate specific goals for the next experimental sub-stage",
            json_schema={
                "type": "object",
                "properties": {
                    "goals": {
                        "type": "string",
                        "description": "Detailed, specific goals for the next sub-stage",
                    },
                    "sub_stage_name": {
                        "type": "string",
                        "description": "The name of the next sub-stage",
                    },
                },
                "required": ["goals", "sub_stage_name"],
            },
        )

        try:
            # Get response from LLM
            response = query(
                system_message=prompt,
                user_message=None,
                func_spec=substage_goal_spec,
                model=self.cfg.agent.feedback.model,
                temperature=self.cfg.agent.feedback.temp,
            )
            response_dict = cast(Dict[str, Any], response)

            # Format the response into a structured goal string
            goal_str = f"""
            {response_dict['goals']}
            """

            return goal_str.strip(), str(response_dict["sub_stage_name"])

        except Exception as e:
            logger.error(f"Error generating sub-stage goals: {e}")
            # Provide fallback goals if LLM fails
            fallback = (
                """
            Sub-stage Goals:
            Continue progress on main stage objectives while addressing current issues.
            """.strip(),
                "first_attempt",
            )
            return fallback

    def _create_next_substage(
        self, current_substage: StageMeta, journal: Journal
    ) -> Optional[StageMeta]:
        """Create the next sub-stage. Ask LLM to come up with the next sub-stage name and goals
        based on what has been done so far.
        """
        # Build the next substage metadata using stage class defaults and LLM goal
        main_stage_num = current_substage.number
        sub_stage_num = current_substage.substage_number
        # Get goals and slug from the corresponding stage class
        if main_stage_num == 1:
            current_stage_cls: StageClass = Stage1Baseline
        elif main_stage_num == 2:
            current_stage_cls = Stage2Tuning
        elif main_stage_num == 3:
            current_stage_cls = Stage3Plotting
        elif main_stage_num == 4:
            current_stage_cls = Stage4Ablation
        else:
            raise ValueError(f"Unknown stage number: {main_stage_num}")
        main_stage_goal = current_stage_cls.DEFAULT_GOALS
        main_stage_name = current_stage_cls.MAIN_STAGE_SLUG
        sub_stage_goal, sub_stage_name = self._generate_substage_goal(main_stage_goal, journal)

        return StageMeta(
            name=f"{main_stage_num}_{main_stage_name}_{sub_stage_num + 1}_{sub_stage_name}",
            number=current_substage.number,
            slug=main_stage_name,
            substage_number=sub_stage_num + 1,
            substage_name=sub_stage_name,
            goals="Main stage goals:\n"
            + main_stage_goal
            + "\n\nSub-stage goals:\n"
            + sub_stage_goal,
            max_iterations=self.get_max_iterations(main_stage_num),
            num_drafts=0,
        )

    def _create_next_main_stage(self, current_substage: StageMeta) -> Optional[StageMeta]:
        main_stage_num = current_substage.number
        if main_stage_num == 4:
            return None
        # Determine next stage class and its slug/goals
        next_num = main_stage_num + 1
        if next_num == 2:
            next_stage_cls: StageClass = Stage2Tuning
        elif next_num == 3:
            next_stage_cls = Stage3Plotting
        elif next_num == 4:
            next_stage_cls = Stage4Ablation
        else:
            raise ValueError(f"Unknown next stage number: {next_num}")
        next_main_stage_name = next_stage_cls.MAIN_STAGE_SLUG
        sub_stage_num = 1
        sub_stage_name = "first_attempt"
        num_drafts = 0
        stage_number = next_num
        main_stage_goal = next_stage_cls.DEFAULT_GOALS

        return StageMeta(
            name=f"{main_stage_num + 1}_{next_main_stage_name}_{sub_stage_num}_{sub_stage_name}",
            number=stage_number,
            slug=next_main_stage_name,
            substage_number=sub_stage_num,
            substage_name=sub_stage_name,
            goals=main_stage_goal,
            max_iterations=self.get_max_iterations(main_stage_num + 1),
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
        if current_substage.number in [1, 2, 3, 4]:
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

    def _run_substage(
        self,
        current_substage: StageMeta,
        agent: ParallelAgent,
        exec_callback: ExecCallbackType,
        step_callback: Optional[Callable[[StageMeta, Journal], None]],
    ) -> Tuple[bool, Optional[StageMeta]]:
        """Execute iterations for a sub-stage until it completes or the main stage finishes.

        Returns a tuple: (main_stage_completed, next_substage)
        - If main_stage_completed is True, the caller should move to the next main stage
          (or stop if there is none).
        - If False and next_substage is provided, the caller should continue with that sub-stage.
        """
        while True:
            # Emit iteration progress before each step
            journal = self.journals[current_substage.name]
            max_iters = current_substage.max_iterations
            current_iter = len(journal.nodes) + 1
            logger.debug(f"Stage {current_substage.name}: Iteration {current_iter}/{max_iters}")
            try:
                self.event_callback(
                    RunLogEvent(
                        message=(
                            f"Stage {current_substage.name}: Iteration {current_iter}/{max_iters}"
                        ),
                        level="info",
                    )
                )
                self.event_callback(
                    RunStageProgressEvent(
                        stage=current_substage.name,
                        iteration=current_iter,
                        max_iterations=max_iters,
                        progress=min(len(journal.nodes) / max_iters, 1.0),
                        total_nodes=len(journal.nodes),
                        buggy_nodes=len(journal.buggy_nodes),
                        good_nodes=len(journal.good_nodes),
                    )
                )
            except Exception:
                # Best-effort logging; never block iteration on event errors
                pass

            agent.step(exec_callback)
            if step_callback:
                step_callback(current_substage, self.journals[current_substage.name])

            # Check if main stage is complete
            main_stage_complete, main_stage_feedback = self._check_stage_completion(
                current_substage
            )
            logger.debug(f"Feedback from _check_stage_completion: {main_stage_feedback}")
            if main_stage_complete:
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

            # Check if sub-stage is complete
            substage_complete, substage_feedback = self._check_substage_completion(
                current_substage, self.journals[current_substage.name]
            )

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
                    self.stages.append(next_substage)
                    self.journals[next_substage.name] = Journal(
                        summary_model=self.cfg.report.model,
                        node_selection_model=self.cfg.agent.feedback.model,
                        summary_temperature=self.cfg.report.temp,
                        node_selection_temperature=self.cfg.agent.feedback.temp,
                        event_callback=self.event_callback,
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
            self.journals[next_main_stage.name] = Journal(
                summary_model=self.cfg.report.model,
                node_selection_model=self.cfg.agent.feedback.model,
                summary_temperature=self.cfg.report.temp,
                node_selection_temperature=self.cfg.agent.feedback.temp,
                event_callback=self.event_callback,
            )
            self.current_stage = next_main_stage
        else:
            # Exit the outer loop if no more main stages
            logger.info(f"Completed stage: {self.current_stage.name}")
            logger.info("No more stages to run -- exiting the loop...")
            self.current_stage = None

    def run(
        self,
        exec_callback: ExecCallbackType,
        step_callback: Optional[Callable[[StageMeta, Journal], None]] = None,
    ) -> None:
        """Run the experiment through generated stages"""
        # Main stage loop
        while self.current_stage:
            logger.info(f"Starting main stage: {self.current_stage.slug}")
            logger.info(f"Goals: {self.current_stage.goals}")
            # Run only the current main stage
            self.run_stage(
                initial_substage=self.current_stage,
                exec_callback=exec_callback,
                step_callback=step_callback,
            )
            # Main stage complete - create next main stage
            self._advance_to_next_main_stage()

    def run_stage(
        self,
        initial_substage: StageMeta,
        exec_callback: ExecCallbackType,
        step_callback: Optional[Callable[[StageMeta, Journal], None]],
    ) -> None:
        """Run a single main stage starting from the given sub-stage.

        This executes the sub-stage loop until the main stage completes,
        performs any post-stage evaluation, and saves a checkpoint.
        """
        current_substage: Optional[StageMeta] = initial_substage
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
                    self.current_stage = None
                    current_substage = None
                    break

                # Run until sub-stage completion or main stage completion
                main_done, maybe_next_substage = self._run_substage(
                    current_substage=current_substage,
                    agent=agent,
                    exec_callback=exec_callback,
                    step_callback=step_callback,
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
            if hasattr(node, "_agent"):
                node_summary = node._agent._generate_node_summary(node)
                metrics["node_summaries"].append(node_summary)

        # Get VLM feedback from plot analysis
        for node in journal.good_nodes:
            if hasattr(node, "_vlm_feedback"):
                metrics["vlm_feedback"].append(node._vlm_feedback)

        best_node = journal.get_best_node()
        if best_node and best_node.metric is not None:
            metrics["best_metric"] = {
                "value": best_node.metric.value,
                "name": (
                    best_node.metric.name
                    if hasattr(best_node.metric, "name")
                    else "validation_metric"
                ),
                "maximize": (
                    best_node.metric.maximize if hasattr(best_node.metric, "maximize") else False
                ),
                "analysis": (best_node.analysis if hasattr(best_node, "analysis") else None),
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
                if hasattr(node, "analysis"):
                    # Use the error message as key to group similar issues
                    key = node.analysis if node.analysis is not None else "Unknown error"
                    error_patterns.setdefault(key, []).append(node.id)

            # Report persistent issues
            for error_msg, node_ids in error_patterns.items():
                if len(node_ids) >= 2:  # If same error occurs multiple times
                    issues.append(f"Persistent issue in nodes {node_ids}: {error_msg}")

        # Include VLM-identified systemic issues
        vlm_issues = set()  # Use set to avoid duplicate issues
        for node in journal.good_nodes:
            if hasattr(node, "_vlm_feedback"):
                vlm_feedback = node._vlm_feedback
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
                    "analysis": node.analysis if hasattr(node, "analysis") else None,
                }
                progress["recent_changes"].append(change)

        return progress
