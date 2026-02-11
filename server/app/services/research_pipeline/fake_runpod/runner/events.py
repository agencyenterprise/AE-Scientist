"""Event emission methods for FakeRunner."""

import logging
import uuid
from datetime import datetime, timezone
from typing import TYPE_CHECKING

# fmt: off
# isort: off
from research_pipeline.ai_scientist.api_types import (  # type: ignore[import-not-found]
    CodexEventPayload,
    ExecutionType,
    PaperGenerationProgressEvent,
    RunCompletedEventPayload,
    RunLogEvent,
    RunningCodeEventPayload,
    RunType,
    StageCompletedEventInput as StageCompletedEvent,
    StageProgressEvent,
    StageSkipWindowEventModel,
    StageSummaryEvent,
    State as StageSkipState,
    Status6 as RunCompletedStatus,
    TokenUsageEvent,
)
# isort: on
# fmt: on
from research_pipeline.ai_scientist.telemetry.event_persistence import (  # type: ignore[import-not-found]
    PersistableEvent,
)

from ..models import (
    MIN_FAKE_CODEX_OUTLIVES_RUNFILE_SECONDS,
    MIN_FAKE_RUNFILE_RUNNING_SECONDS,
    ExecutionRecord,
)
from ..state import get_executions, get_lock, get_speed_factor
from .fake_data import (
    generate_seed_modification_task,
    generate_seed_runfile_code,
    get_paper_generation_steps,
)

if TYPE_CHECKING:
    from .core import FakeRunnerCore

logger = logging.getLogger(__name__)


class EventsMixin:
    """Mixin providing event emission methods for FakeRunner."""

    # Type hints for attributes from FakeRunnerCore
    _run_id: str
    _webhooks: "FakeRunnerCore._webhooks"  # type: ignore[name-defined]
    _persistence: "FakeRunnerCore._persistence"  # type: ignore[name-defined]
    _random_exec_time_seconds: float
    _stage_plan: list[tuple[str, int]]
    _iterations_per_stage: int

    # Type hints for methods from other mixins (only used for type checking)
    if TYPE_CHECKING:

        def _sleep(self, seconds: float) -> None: ...
        def _enqueue_event(self, *, kind: str, data: object) -> None: ...
        def _consume_stage_skip_request(self) -> str | None: ...
        def _wait_or_skip(self, *, timeout_seconds: float) -> str | None: ...
        def _store_tree_viz(self, *, stage_number: int, version: int) -> None: ...

    def _emit_stage_skip_window_event(self, *, stage_name: str, state: str, reason: str) -> None:
        """Emit a stage skip window event."""
        timestamp = datetime.now(timezone.utc).isoformat()
        payload = StageSkipWindowEventModel(
            stage=stage_name,
            state=StageSkipState(state),
            timestamp=timestamp,
            reason=reason,
        )
        logger.info(
            "[FakeRunner %s] Stage skip window %s for %s",
            self._run_id[:8],
            state,
            stage_name,
        )
        try:
            self._persistence.queue.put(
                PersistableEvent(
                    kind="stage_skip_window",
                    data=payload,
                )
            )
            logger.debug(
                "[FakeRunner %s] Enqueued stage_skip_window event (stage=%s state=%s)",
                self._run_id[:8],
                stage_name,
                state,
            )
        except Exception:
            logger.exception(
                "[FakeRunner %s] Failed to enqueue stage skip window event for stage %s",
                self._run_id[:8],
                stage_name,
            )
        self._webhooks.publish_stage_skip_window(payload)

    def _emit_code_execution_events(self, *, stage_name: str, iteration: int) -> None:
        """Emit code execution events for a single iteration."""
        _lock = get_lock()
        _executions_by_id = get_executions()

        # Use clean UUID format matching production pipeline
        execution_id = uuid.uuid4().hex
        started_at = datetime.now(timezone.utc)
        logger.debug(
            "[FakeRunner %s] Emitting code execution events execution_id=%s stage=%s iteration=%s",
            self._run_id[:8],
            execution_id,
            stage_name,
            iteration + 1,
        )
        fake_task_markdown = (
            f"# Fake Codex task for {stage_name} iteration {iteration + 1}\n\n"
            "This simulates the markdown prompt we send to Codex.\n\n"
            "## Objective\n"
            "Write `runfile.py` with a minimal experiment and then execute it.\n\n"
            "## Files\n"
            "- `runfile.py`: main script to execute\n"
        )
        fake_runfile_code = (
            "\n\n"
            "def main() -> None:\n"
            "    print('Hello from fake runfile execution')\n\n"
            "main()\n"
        )
        codex_run_type = "codex_execution"
        runfile_run_type = "runfile_execution"
        with _lock:
            _executions_by_id[execution_id] = ExecutionRecord(
                run_id=self._run_id,
                stage=stage_name,
                run_type=codex_run_type,
                started_at=started_at,
                status="running",
            )
        self._webhooks.publish_running_code(
            RunningCodeEventPayload(
                execution_id=execution_id,
                stage=stage_name,
                run_type=RunType(codex_run_type),
                execution_type=ExecutionType.stage_goal,
                code=fake_task_markdown,
                started_at=started_at.isoformat(),
                is_seed_node=False,
                is_seed_agg_node=False,
                node_index=iteration + 1,  # 1-based index
            )
        )

        # Emit Codex JSONL-like events so the UI can show Codex activity.
        self._emit_codex_events(stage_name=stage_name, node_index=iteration)

        # Simulate the moment when Codex starts executing the runfile.
        self._sleep(1)
        runfile_started_at = datetime.now(timezone.utc)
        self._webhooks.publish_running_code(
            RunningCodeEventPayload(
                execution_id=execution_id,
                stage=stage_name,
                run_type=RunType(runfile_run_type),
                execution_type=ExecutionType.stage_goal,
                code=fake_runfile_code,
                started_at=runfile_started_at.isoformat(),
                is_seed_node=False,
                is_seed_agg_node=False,
                node_index=iteration + 1,  # 1-based index
            )
        )

        # Keep the "runfile execution" shorter than the overall Codex session.
        runfile_exec_time = max(
            MIN_FAKE_RUNFILE_RUNNING_SECONDS, float(self._random_exec_time_seconds) * 0.4
        )
        _speed_factor = get_speed_factor()
        logger.debug(
            "[FakeRunner %s] Starting runfile execution execution_id=%s running_for_s=%.1f",
            self._run_id[:8],
            execution_id,
            runfile_exec_time / _speed_factor,
        )
        self._sleep(runfile_exec_time)
        runfile_completed_at = datetime.now(timezone.utc)
        runfile_exec_time = max(0.0, (runfile_completed_at - runfile_started_at).total_seconds())
        logger.debug(
            "[FakeRunner %s] Completing runfile execution execution_id=%s completed_at=%s",
            self._run_id[:8],
            execution_id,
            runfile_completed_at.isoformat(),
        )
        self._webhooks.publish_run_completed(
            RunCompletedEventPayload(
                execution_id=execution_id,
                stage=stage_name,
                run_type=RunType(runfile_run_type),
                execution_type=ExecutionType.stage_goal,
                status=RunCompletedStatus.success,
                exec_time=runfile_exec_time,
                completed_at=runfile_completed_at.isoformat(),
                is_seed_node=False,
                is_seed_agg_node=False,
                node_index=iteration + 1,  # 1-based index
            )
        )

        # Ensure codex_execution always outlives runfile_execution.
        self._sleep(MIN_FAKE_CODEX_OUTLIVES_RUNFILE_SECONDS)
        completed_at = datetime.now(timezone.utc)
        exec_time = max(0.0, (completed_at - started_at).total_seconds())
        logger.debug(
            "[FakeRunner %s] Completing codex execution execution_id=%s completed_at=%s",
            self._run_id[:8],
            execution_id,
            completed_at.isoformat(),
        )
        self._webhooks.publish_run_completed(
            RunCompletedEventPayload(
                execution_id=execution_id,
                stage=stage_name,
                run_type=RunType(codex_run_type),
                execution_type=ExecutionType.stage_goal,
                status=RunCompletedStatus.success,
                exec_time=exec_time,
                completed_at=completed_at.isoformat(),
                is_seed_node=False,
                is_seed_agg_node=False,
                node_index=iteration + 1,  # 1-based index
            )
        )
        with _lock:
            existing = _executions_by_id.get(execution_id)
            if existing is not None:
                _executions_by_id[execution_id] = existing._replace(status="success")

        # Emit metrics parsing events after node execution
        metrics_execution_id = f"{execution_id}_metrics"
        metrics_started_at = datetime.now(timezone.utc)
        self._webhooks.publish_running_code(
            RunningCodeEventPayload(
                execution_id=metrics_execution_id,
                stage=stage_name,
                run_type=RunType.runfile_execution,
                execution_type=ExecutionType.metrics,
                code="# Metrics parsing\nimport json\nwith open('metrics.json') as f:\n    metrics = json.load(f)\nprint(f'Parsed metrics: {metrics}')",
                started_at=metrics_started_at.isoformat(),
                is_seed_node=False,
                is_seed_agg_node=False,
                node_index=iteration + 1,
            )
        )
        # Metrics parsing is quick
        self._sleep(0.5)
        metrics_completed_at = datetime.now(timezone.utc)
        metrics_exec_time = max(0.0, (metrics_completed_at - metrics_started_at).total_seconds())
        self._webhooks.publish_run_completed(
            RunCompletedEventPayload(
                execution_id=metrics_execution_id,
                stage=stage_name,
                run_type=RunType.runfile_execution,
                execution_type=ExecutionType.metrics,
                status=RunCompletedStatus.success,
                exec_time=metrics_exec_time,
                completed_at=metrics_completed_at.isoformat(),
                is_seed_node=False,
                is_seed_agg_node=False,
                node_index=iteration + 1,
            )
        )

    def _emit_codex_events(self, *, stage_name: str, node_index: int) -> None:
        """Emit Codex JSONL-like events."""
        item_id = f"item_{uuid.uuid4().hex[:6]}"
        item_event = {
            "type": "item.started",
            "item": {
                "id": item_id,
                "type": "command_execution",
                "command": "bash -lc python runfile.py",
                "status": "in_progress",
            },
        }
        self._enqueue_event(
            kind="codex_event",
            data=CodexEventPayload(
                event={
                    "stage": stage_name,
                    "node": node_index,
                    "event_type": "item.started",
                    "event_content": item_event,
                }
            ),
        )
        item_completed_event = {
            "type": "item.completed",
            "item": {
                "id": item_id,
                "type": "command_execution",
                "command": "bash -lc python runfile.py",
                "status": "completed",
                "exit_code": 0,
            },
        }
        self._enqueue_event(
            kind="codex_event",
            data=CodexEventPayload(
                event={
                    "stage": stage_name,
                    "node": node_index,
                    "event_type": "item.completed",
                    "event_content": item_completed_event,
                }
            ),
        )
        turn_event = {
            "type": "turn.completed",
            "usage": {
                "input_tokens": 1200,
                "cached_input_tokens": 800,
                "output_tokens": 250,
            },
        }
        self._enqueue_event(
            kind="codex_event",
            data=CodexEventPayload(
                event={
                    "stage": stage_name,
                    "node": node_index,
                    "event_type": "turn.completed",
                    "event_content": turn_event,
                }
            ),
        )

    def _emit_progress_flow(self) -> None:
        """Emit the full progress flow for all stages."""
        total_iterations = len(self._stage_plan) * self._iterations_per_stage
        current_iter = 0
        for stage_index, (stage_name, max_iterations) in enumerate(self._stage_plan):
            logger.info(
                "[FakeRunner %s] Stage %d/%d: %s",
                self._run_id[:8],
                stage_index + 1,
                len(self._stage_plan),
                stage_name,
            )
            self._emit_stage_skip_window_event(
                stage_name=stage_name,
                state="opened",
                reason="Fake runner marked stage as skippable.",
            )
            stage_skipped = False
            stage_skip_reason: str | None = None
            iterations_to_emit = min(self._iterations_per_stage, max_iterations)
            for iteration in range(iterations_to_emit):
                pending_skip_reason = self._consume_stage_skip_request()
                if pending_skip_reason is not None:
                    stage_skipped = True
                    stage_skip_reason = pending_skip_reason
                    logger.info(
                        "[FakeRunner %s] Skip requested for stage %s: %s",
                        self._run_id[:8],
                        stage_name,
                        stage_skip_reason,
                    )
                    break
                current_iter += 1
                # Calculate progress BEFORE execution (matching real pipeline behavior)
                progress_before = max(iteration, 0) / max_iterations if max_iterations > 0 else 0.0
                logger.debug(
                    "Emitting progress run=%s stage=%s iteration=%s progress=%.2f",
                    self._run_id,
                    stage_name,
                    iteration + 1,
                    progress_before,
                )
                # Emit progress event BEFORE code execution (matching real pipeline)
                self._enqueue_event(
                    kind="run_stage_progress",
                    data=StageProgressEvent(
                        stage=stage_name,
                        iteration=iteration + 1,
                        max_iterations=max_iterations,
                        progress=progress_before,
                        total_nodes=10 + iteration,
                        buggy_nodes=iteration,
                        good_nodes=9 - iteration,
                        best_metric=f"metric-{progress_before:.2f}" if iteration > 0 else None,
                        is_seed_node=False,
                        is_seed_agg_node=False,
                    ),
                )
                # Emit intermediate token usage during iteration
                self._emit_iteration_token_usage(stage_name=stage_name, iteration=iteration)
                self._emit_code_execution_events(stage_name=stage_name, iteration=iteration)
                self._enqueue_event(
                    kind="run_log",
                    data=RunLogEvent(
                        message=f"{stage_name} iteration {iteration + 1} complete",
                        level="info",
                    ),
                )
                # Mid-stage tree viz emit on second iteration (iteration index 1)
                if iteration == 1:
                    try:
                        self._store_tree_viz(stage_number=stage_index + 1, version=iteration + 1)
                    except Exception:
                        logger.exception(
                            "Failed to store mid-stage tree viz for stage %s iteration %s",
                            stage_name,
                            iteration + 1,
                        )
                pending_skip_reason = self._wait_or_skip(timeout_seconds=20)
                if pending_skip_reason is not None:
                    stage_skipped = True
                    stage_skip_reason = pending_skip_reason
                    logger.info(
                        "[FakeRunner %s] Skip requested for stage %s during wait: %s",
                        self._run_id[:8],
                        stage_name,
                        stage_skip_reason,
                    )
                    break
                logger.info(
                    "[FakeRunner %s]   Iteration %d/%d complete (%.0f%% overall)",
                    self._run_id[:8],
                    iteration + 1,
                    iterations_to_emit,
                    (current_iter / total_iterations) * 100,
                )
            if stage_skipped:
                effective_skip_reason = stage_skip_reason or "Stage skipped by operator."
                self._enqueue_event(
                    kind="run_log",
                    data=RunLogEvent(
                        message=f"Skipping stage {stage_name}: {effective_skip_reason}",
                        level="warn",
                    ),
                )
                summary = {
                    "goals": f"Goals for {stage_name}",
                    "feedback": effective_skip_reason,
                    "good_nodes": 0,
                    "best_metric": None,
                    "buggy_nodes": 0,
                    "total_nodes": 0,
                    "llm_summary": f"Stage {stage_name} skipped.",
                    "transition_summary": f"Stage {stage_name} was skipped. Moving on to the next stage in the research pipeline.",
                }
                self._enqueue_event(
                    kind="stage_completed",
                    data=StageCompletedEvent(
                        stage=stage_name,
                        main_stage_number=stage_index + 1,
                        reason="skipped",
                        summary=summary,
                    ),
                )
                try:
                    self._enqueue_event(
                        kind="stage_summary",
                        data=StageSummaryEvent(
                            stage=stage_name,
                            summary=summary["transition_summary"],
                        ),
                    )
                except Exception:
                    logger.exception(
                        "Failed to enqueue skipped-stage stage summary for stage %s",
                        stage_name,
                    )
                self._emit_stage_skip_window_event(
                    stage_name=stage_name,
                    state="closed",
                    reason=effective_skip_reason,
                )
                continue
            # Emit seed evaluation progress events (3 seeds)
            self._emit_seed_evaluation_progress(stage_name=stage_name)

            # Emit final progress=1.0 event at stage completion
            # (matching real pipeline's _emit_final_progress_if_needed in agent_manager.py)
            try:
                self._enqueue_event(
                    kind="run_stage_progress",
                    data=StageProgressEvent(
                        stage=stage_name,
                        iteration=iterations_to_emit,
                        max_iterations=max_iterations,
                        progress=1.0,
                        total_nodes=10 + iterations_to_emit,
                        buggy_nodes=iterations_to_emit - 1,
                        good_nodes=10,
                        best_metric="metric-1.00",
                        is_seed_node=False,
                        is_seed_agg_node=False,
                    ),
                )
            except Exception:
                logger.exception("Failed to emit final progress=1.0 event for stage %s", stage_name)

            # Generate a realistic-looking transition summary based on stage
            stage_number = stage_index + 1
            transition_summaries = {
                1: "Initial Implementation successfully established a working baseline with validation accuracy of 0.847. The model architecture and training pipeline are now stable, providing a solid foundation for hyperparameter optimization in the next stage.",
                2: "Baseline Tuning improved performance to 0.891 through systematic hyperparameter search. Key findings include optimal learning rate of 1e-4 and batch size of 32. The model is now ready for creative exploration of novel techniques.",
                3: "Creative Research discovered that adding attention mechanisms boosted accuracy to 0.923. Three promising approaches were identified, with the attention-augmented variant showing the most consistent improvements across datasets.",
                4: "Ablation Studies confirmed the importance of the attention mechanism (contributing +4.2% accuracy) and validated that all proposed modifications are necessary. The final configuration achieves 0.931 accuracy with statistical significance across 5 seeds.",
            }
            transition_summary = transition_summaries.get(
                stage_number,
                f"Stage {stage_name} completed successfully with notable improvements in model performance.",
            )
            summary = {
                "goals": f"Goals for {stage_name}",
                "feedback": "Reached max iterations",
                "good_nodes": 2,
                "best_metric": f"Metrics(fake metric for {stage_name})",
                "buggy_nodes": 1,
                "total_nodes": 3,
                "llm_summary": f"Stage {stage_name} completed with synthetic findings.",
                "transition_summary": transition_summary,
            }
            logger.info("Emitting stage_completed for stage %s", stage_name)
            self._enqueue_event(
                kind="stage_completed",
                data=StageCompletedEvent(
                    stage=stage_name,
                    main_stage_number=stage_index + 1,
                    reason="completed",
                    summary=summary,
                ),
            )
            try:
                self._enqueue_event(
                    kind="stage_summary",
                    data=StageSummaryEvent(
                        stage=stage_name,
                        summary=transition_summary,
                    ),
                )
            except Exception:
                logger.exception("Failed to enqueue fake stage summary for stage %s", stage_name)
            logger.info(
                "[FakeRunner %s] Stage %d/%d complete",
                self._run_id[:8],
                stage_index + 1,
                len(self._stage_plan),
            )
            self._emit_stage_skip_window_event(
                stage_name=stage_name,
                state="closed",
                reason="Stage completed in fake runner.",
            )

        # Stage 5: Paper Generation
        logger.info("[FakeRunner %s] Starting paper generation (Stage 5)", self._run_id[:8])
        self._emit_paper_generation_flow()

    def _emit_paper_generation_flow(self) -> None:
        """Emit Stage 5 paper generation progress events."""
        paper_steps = get_paper_generation_steps()
        total_steps = len(paper_steps)
        for step_idx, (step_name, substeps, step_details) in enumerate(paper_steps):
            logger.info(
                "[FakeRunner %s] Paper step %d/%d: %s",
                self._run_id[:8],
                step_idx + 1,
                total_steps,
                step_name,
            )
            for substep_idx, substep_name in enumerate(substeps):
                step_progress = (substep_idx + 1) / len(substeps)
                overall_progress = (step_idx + step_progress) / total_steps

                self._enqueue_event(
                    kind="paper_generation_progress",
                    data=PaperGenerationProgressEvent(
                        step=step_name,
                        substep=substep_name,
                        progress=overall_progress,
                        step_progress=step_progress,
                        details={
                            **step_details,
                            "current_substep": substep_idx + 1,
                            "total_substeps": len(substeps),
                        },
                    ),
                )
                self._enqueue_event(
                    kind="run_log",
                    data=RunLogEvent(
                        message=f"Paper generation: {step_name} - {substep_name}",
                        level="info",
                    ),
                )
                # Shorter delay for paper generation steps (5s instead of 20s)
                self._sleep(5)
                logger.info(
                    "[FakeRunner %s]   %s complete (%.0f%% step)",
                    self._run_id[:8],
                    substep_name,
                    step_progress * 100,
                )

        # Log completion
        self._enqueue_event(
            kind="run_log",
            data=RunLogEvent(
                message="Paper generation completed",
                level="info",
            ),
        )
        logger.info("[FakeRunner %s] Paper generation complete", self._run_id[:8])

    def _emit_seed_evaluation_progress(self, *, stage_name: str) -> None:
        """Emit fake seed evaluation progress events (3 seeds) with is_seed_node=True."""
        num_seeds = 3
        logger.info(
            "[FakeRunner %s] Starting seed evaluation for %s (%d seeds)",
            self._run_id[:8],
            stage_name,
            num_seeds,
        )

        # Emit progress for each seed with execution events
        for seed_idx in range(num_seeds):
            seed_number = seed_idx + 1

            # Emit seed evaluation progress event BEFORE starting execution
            # (matching real pipeline behavior in parallel_agent.py:436)
            try:
                self._enqueue_event(
                    kind="run_stage_progress",
                    data=StageProgressEvent(
                        stage=stage_name,
                        iteration=seed_number,
                        max_iterations=num_seeds,
                        progress=float(seed_number) / float(num_seeds),
                        total_nodes=num_seeds,
                        buggy_nodes=0,
                        good_nodes=seed_number,
                        best_metric=None,
                        is_seed_node=True,
                        is_seed_agg_node=False,
                    ),
                )
            except Exception:
                logger.exception(
                    "Failed to emit seed eval progress event for stage %s seed %d",
                    stage_name,
                    seed_number,
                )

            # Emit intermediate token usage for seed evaluation
            self._emit_seed_token_usage(stage_name=stage_name, seed_idx=seed_idx)

            # Use clean UUID format matching production pipeline
            seed_execution_id = uuid.uuid4().hex
            seed_started_at = datetime.now(timezone.utc)

            # Emit running_code event for seed node - codex_execution (task prompt)
            seed_modification_task = generate_seed_modification_task(seed_idx)
            try:
                self._webhooks.publish_running_code(
                    RunningCodeEventPayload(
                        execution_id=seed_execution_id,
                        stage=stage_name,
                        run_type=RunType.codex_execution,
                        execution_type=ExecutionType.seed,
                        code=seed_modification_task,
                        started_at=seed_started_at.isoformat(),
                        is_seed_node=True,
                        is_seed_agg_node=False,
                        node_index=seed_number,  # 1-based seed index
                    )
                )
            except Exception:
                logger.exception(
                    "Failed to emit codex running_code for seed %d in stage %s",
                    seed_idx,
                    stage_name,
                )

            self._sleep(2)  # Simulate Codex thinking time

            # Emit running_code event for seed node - runfile_execution (generated code)
            seed_runfile_code = generate_seed_runfile_code(seed_idx)
            runfile_started_at = datetime.now(timezone.utc)
            try:
                self._webhooks.publish_running_code(
                    RunningCodeEventPayload(
                        execution_id=seed_execution_id,
                        stage=stage_name,
                        run_type=RunType.runfile_execution,
                        execution_type=ExecutionType.seed,
                        code=seed_runfile_code,
                        started_at=runfile_started_at.isoformat(),
                        is_seed_node=True,
                        is_seed_agg_node=False,
                        node_index=seed_number,  # 1-based seed index
                    )
                )
            except Exception:
                logger.exception(
                    "Failed to emit runfile running_code for seed %d in stage %s",
                    seed_idx,
                    stage_name,
                )

            self._sleep(3)  # Simulate code execution time

            # Emit run_completed event for runfile_execution
            runfile_completed_at = datetime.now(timezone.utc)
            runfile_exec_time = max(
                0.0, (runfile_completed_at - runfile_started_at).total_seconds()
            )
            try:
                self._webhooks.publish_run_completed(
                    RunCompletedEventPayload(
                        execution_id=seed_execution_id,
                        stage=stage_name,
                        run_type=RunType.runfile_execution,
                        execution_type=ExecutionType.seed,
                        status=RunCompletedStatus.success,
                        exec_time=runfile_exec_time,
                        completed_at=runfile_completed_at.isoformat(),
                        is_seed_node=True,
                        is_seed_agg_node=False,
                        node_index=seed_number,  # 1-based seed index
                    )
                )
            except Exception:
                logger.exception(
                    "Failed to emit runfile run_completed for seed %d in stage %s",
                    seed_idx,
                    stage_name,
                )

            # Emit run_completed event for codex_execution
            seed_completed_at = datetime.now(timezone.utc)
            seed_exec_time = max(0.0, (seed_completed_at - seed_started_at).total_seconds())
            try:
                self._webhooks.publish_run_completed(
                    RunCompletedEventPayload(
                        execution_id=seed_execution_id,
                        stage=stage_name,
                        run_type=RunType.codex_execution,
                        execution_type=ExecutionType.seed,
                        status=RunCompletedStatus.success,
                        exec_time=seed_exec_time,
                        completed_at=seed_completed_at.isoformat(),
                        is_seed_node=True,
                        is_seed_agg_node=False,
                        node_index=seed_number,  # 1-based seed index
                    )
                )
            except Exception:
                logger.exception(
                    "Failed to emit codex run_completed for seed %d in stage %s",
                    seed_idx,
                    stage_name,
                )

            logger.info(
                "[FakeRunner %s]   Seed %d/%d completed for %s",
                self._run_id[:8],
                seed_number,
                num_seeds,
                stage_name,
            )

        # Emit seed aggregation node execution events
        # Use clean UUID format matching production pipeline
        agg_execution_id = uuid.uuid4().hex
        agg_started_at = datetime.now(timezone.utc)
        logger.info(
            "[FakeRunner %s] Starting seed aggregation for %s",
            self._run_id[:8],
            stage_name,
        )

        # Emit aggregation progress event (start - in progress)
        try:
            self._enqueue_event(
                kind="run_stage_progress",
                data=StageProgressEvent(
                    stage=stage_name,
                    iteration=1,
                    max_iterations=1,
                    progress=0.0,
                    total_nodes=1,
                    buggy_nodes=0,
                    good_nodes=0,
                    best_metric=None,
                    is_seed_node=False,
                    is_seed_agg_node=True,
                ),
            )
        except Exception:
            logger.exception(
                "Failed to emit aggregation start progress event for stage %s", stage_name
            )

        # Emit running_code event for aggregation node
        try:
            self._webhooks.publish_running_code(
                RunningCodeEventPayload(
                    execution_id=agg_execution_id,
                    stage=stage_name,
                    run_type=RunType.codex_execution,
                    execution_type=ExecutionType.aggregation,
                    code="# Seed Aggregation\n# Combining results from all seed runs\nimport numpy as np\n\n# Aggregate metrics across seeds\nmetrics = [seed_0_metric, seed_1_metric, seed_2_metric]\nmean_metric = np.mean(metrics)\nstd_metric = np.std(metrics)",
                    started_at=agg_started_at.isoformat(),
                    is_seed_node=False,
                    is_seed_agg_node=True,
                    node_index=1,  # Single aggregation node
                )
            )
        except Exception:
            logger.exception(
                "Failed to emit running_code for seed aggregation in stage %s", stage_name
            )

        self._sleep(3)  # Simulate aggregation time

        # Emit run_completed event for aggregation node
        agg_completed_at = datetime.now(timezone.utc)
        agg_exec_time = max(0.0, (agg_completed_at - agg_started_at).total_seconds())
        try:
            self._webhooks.publish_run_completed(
                RunCompletedEventPayload(
                    execution_id=agg_execution_id,
                    stage=stage_name,
                    run_type=RunType.codex_execution,
                    execution_type=ExecutionType.aggregation,
                    status=RunCompletedStatus.success,
                    exec_time=agg_exec_time,
                    completed_at=agg_completed_at.isoformat(),
                    is_seed_node=False,
                    is_seed_agg_node=True,
                    node_index=1,  # Single aggregation node
                )
            )
            logger.info(
                "[FakeRunner %s] Seed aggregation completed for %s",
                self._run_id[:8],
                stage_name,
            )
        except Exception:
            logger.exception(
                "Failed to emit run_completed for seed aggregation in stage %s", stage_name
            )

    def _emit_iteration_token_usage(self, *, stage_name: str, iteration: int) -> None:
        """Emit intermediate token usage during a goal iteration.

        This mimics the real pipeline's behavior of emitting token usage
        events during LLM calls within each iteration.
        """
        # Vary token counts based on stage and iteration for realism
        stage_multiplier = 1.0 + (hash(stage_name) % 5) * 0.1
        iteration_variance = (iteration + 1) * 500

        # Emit token usage for Codex/planning LLM call
        codex_payload = TokenUsageEvent(
            model="openai:gpt-5.2",
            input_tokens=int((12000 + iteration_variance) * stage_multiplier),
            cached_input_tokens=int((8000 + iteration_variance * 0.5) * stage_multiplier),
            output_tokens=int((2500 + iteration * 200) * stage_multiplier),
        )
        try:
            self._webhooks.publish_token_usage(codex_payload)
        except Exception:
            logger.exception(
                "[FakeRunner %s] Failed to publish token_usage for stage %s iteration %d",
                self._run_id[:8],
                stage_name,
                iteration + 1,
            )

        # Emit token usage for feedback/evaluation LLM call
        feedback_payload = TokenUsageEvent(
            model="openai:gpt-5.2",
            input_tokens=int(4000 * stage_multiplier),
            cached_input_tokens=int(2000 * stage_multiplier),
            output_tokens=int(800 * stage_multiplier),
        )
        try:
            self._webhooks.publish_token_usage(feedback_payload)
        except Exception:
            logger.exception(
                "[FakeRunner %s] Failed to publish feedback token_usage for stage %s iteration %d",
                self._run_id[:8],
                stage_name,
                iteration + 1,
            )

    def _emit_seed_token_usage(self, *, stage_name: str, seed_idx: int) -> None:
        """Emit intermediate token usage during seed evaluation.

        Seed evaluations typically use fewer tokens as they're re-running
        existing experiments with different random seeds.
        """
        # Seed evaluations use less tokens than full iterations
        seed_payload = TokenUsageEvent(
            model="openai:gpt-5.2",
            input_tokens=3000 + seed_idx * 200,
            cached_input_tokens=2000 + seed_idx * 100,
            output_tokens=500 + seed_idx * 50,
        )
        try:
            self._webhooks.publish_token_usage(seed_payload)
        except Exception:
            logger.exception(
                "[FakeRunner %s] Failed to publish token_usage for stage %s seed %d",
                self._run_id[:8],
                stage_name,
                seed_idx,
            )
