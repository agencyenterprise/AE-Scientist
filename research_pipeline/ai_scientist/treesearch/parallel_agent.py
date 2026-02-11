"""
ParallelAgent: Executes breadth-first experiment iterations in parallel.

High-level responsibilities:
- Manage process pool and optional GPU assignment per worker
- Select nodes to process (draft/debug/improve) with exploration/exploitation
- Submit work to workers and collect results with timeouts
- Emit structured progress/log events during the run
- Support multi-seed evaluation and resource cleanup
"""

import logging
import multiprocessing
import pickle
import random
import signal
import uuid
from collections.abc import Callable
from concurrent.futures import Future, ProcessPoolExecutor
from functools import partial
from multiprocessing.managers import DictProxy
from types import TracebackType
from typing import List, Optional

import sentry_sdk

from ai_scientist.api_types import StageId as ApiStage

from . import execution_registry
from .codex.codex_task_types import (
    EvaluationMetricSpec,
    SeedAggregationPayload,
    SeedNodeSummary,
    StageIdea,
)
from .config import Config
from .events import BaseEvent, GpuShortageEvent, RunLogEvent, RunStageProgressEvent
from .gpu_manager import GPUManager, get_gpu_count
from .journal import Journal, Node
from .process_utils import send_signal_to_process_group
from .stage_identifiers import StageIdentifier
from .stage_skip_coordinator import SkipInProgressError, StageSkipCoordinator
from .stages.stage2_tuning import propose_next_hyperparam_idea
from .stages.stage4_ablation import propose_next_ablation_idea
from .utils.metric import WorstMetricValue
from .worker_process import ExecutionCrashedError, ExecutionTerminatedError, NodeTask, process_node

logger = logging.getLogger("ai-scientist")


def _executor_initializer(shared_state: DictProxy | None) -> None:
    if shared_state is None:
        logger.warning("Executor initializer received no shared_state; PID tracking disabled.")
        return
    execution_registry.setup_shared_pid_state(shared_state)
    logger.info("Worker process configured shared PID state (id=%s)", id(shared_state))


def _safe_pickle_test(obj: object, name: str = "object") -> bool:
    """Test if an object can be pickled"""
    try:
        pickle.dumps(obj)
        return True
    except Exception as e:
        logger.error(f"Cannot pickle {name}: {str(e)}")
        return False


class ParallelAgent:
    def __init__(
        self,
        title: str,
        task_desc: str,
        stage_goals: str,
        evaluation_metric_spec: EvaluationMetricSpec,
        cfg: Config,
        journal: Journal,
        stage_identifier: StageIdentifier,
        best_stage3_node: Node | None,
        best_stage2_node: Node | None,
        best_stage1_node: Node | None,
        event_callback: Callable[[BaseEvent], None],
    ) -> None:
        # Store run context (idea, configuration, journal, stage)
        self.title = title
        self.task_desc = task_desc
        self.stage_goals = stage_goals
        self.evaluation_metric_spec = evaluation_metric_spec
        self.cfg = cfg
        self.journal = journal
        self.stage_identifier = stage_identifier
        self.stage_skip = StageSkipCoordinator(stage_identifier=stage_identifier)
        self.event_callback = event_callback
        # Best nodes carried from previous stages to seed new work
        self.best_stage1_node = best_stage1_node  # to initialize hyperparam tuning (stage 2)
        self.best_stage2_node = best_stage2_node  # to initialize plotting code (stage 3)
        self.best_stage3_node = best_stage3_node  # to initialize ablation stuides (stage 4)

        # Configure parallelism and optional GPUs
        self.num_workers = cfg.agent.num_workers
        self.num_gpus = get_gpu_count()
        logger.info(f"num_gpus: {self.num_gpus}")
        if self.num_gpus < self.cfg.min_num_gpus:
            self._handle_gpu_shortage(
                available_gpus=self.num_gpus,
                required_gpus=self.cfg.min_num_gpus,
            )
        elif self.num_gpus == 0:
            logger.info("No GPUs detected, falling back to CPU-only mode")
        else:
            logger.info(f"Detected {self.num_gpus} GPUs")

        self.gpu_manager = GPUManager(self.num_gpus) if self.num_gpus > 0 else None

        if self.num_gpus > 0:
            self.num_workers = min(self.num_workers, self.num_gpus)
            logger.info(f"Limiting workers to {self.num_workers} to match GPU count")

        # Create process pool for parallel execution
        self.timeout = self.cfg.exec.timeout
        self._mp_context = multiprocessing.get_context("spawn")
        self.executor: ProcessPoolExecutor | None = self._create_executor()
        self._is_shutdown = False
        self._shared_pid_state = execution_registry.get_shared_pid_state()
        self._future_execution_ids: dict[Future, str] = {}
        self._future_process_ids: dict[Future, str] = {}
        # Execution IDs whose registry entries should be cleared later (not immediately).
        # This is used to keep termination state available briefly so workers can classify
        # SIGKILL as expected (e.g., timeout) and avoid Sentry noise.
        self._deferred_registry_clears: set[str] = set()
        # One-shot user feedback payloads scheduled for exactly one next run (per node id).
        # We clear the payload off the journal node immediately when scheduling, then pass it
        # to the worker explicitly.
        self._one_shot_user_feedback_payloads: dict[str, str] = {}

    @property
    def stage_name(self) -> str:
        return self.stage_identifier.prefixed_name

    def abort_active_executions(self, *, reason: str) -> None:
        pending_ids = list(self._future_execution_ids.values())
        if not pending_ids:
            logger.debug(
                "No active executions to abort for stage %s (reason=%s)",
                self.stage_name,
                reason,
            )
            return
        self.stage_skip.flag_executions_for_skip(pending_ids, reason=reason)

    # Codex-only pipeline: plan/code generation is handled inside the worker by Codex CLI.

    def _cancel_pending_futures(self, futures: list[Future]) -> None:
        if not futures:
            return
        for future in futures:
            execution_id = (
                self._future_execution_ids.pop(future)
                if future in self._future_execution_ids
                else None
            )
            process_id = (
                self._future_process_ids.pop(future) if future in self._future_process_ids else None
            )
            if not future.done():
                if future.cancel():
                    logger.info(
                        "Cancelled pending future for execution_id=%s (stage=%s)",
                        execution_id,
                        self.stage_name,
                    )
                else:
                    logger.debug(
                        "Pending future could not be cancelled (execution_id=%s stage=%s)",
                        execution_id,
                        self.stage_name,
                    )
            if execution_id:
                execution_registry.clear_execution(execution_id)
            if self.gpu_manager is not None and process_id is not None:
                if process_id in self.gpu_manager.gpu_assignments:
                    self.gpu_manager.release_gpu(process_id)
                    logger.info("Released GPU for process %s due to skip", process_id)

    def _handle_gpu_shortage(self, *, available_gpus: int, required_gpus: int) -> None:
        message = (
            "Detected "
            f"{available_gpus} GPU(s) but configuration requires at least {required_gpus}. "
            "Aborting experiment run."
        )
        logger.error(message)
        try:
            self.event_callback(RunLogEvent(message=message, level="error"))
        except Exception:
            logger.exception("Failed to emit run log event for GPU shortage.")
        try:
            self.event_callback(
                GpuShortageEvent(
                    required_gpus=required_gpus,
                    available_gpus=available_gpus,
                    message=message,
                )
            )
        except Exception:
            logger.exception("Failed to emit GPU shortage event.")
        raise RuntimeError(message)

    def _run_multi_seed_evaluation(self, node: Node) -> List[Node]:
        """
        Run multiple seeds of the same *already-generated* experiment to assess stability.

        Important behavior:
        - These seed runs **use Codex** to modify the seed values in the experiment code.
        - Codex is given explicit instructions to find and replace all seed-related values
          (e.g., `SEED = 42`, `random.seed(42)`, etc.) with the target seed value.
        - This approach ensures that hardcoded seeds in the experiment code are properly modified,
          unlike the previous approach which only prepended seed initialization.
        - Seeds are run in batches sized by num_workers (and num_gpus if applicable) to ensure
          GPU resources are properly reused between batches.

        Returns a list of nodes corresponding to the individual seed executions.
        """
        # Convert node to dict for parallel processing
        node_data = node.to_dict()

        seed_nodes: List[Node] = []
        executor = self._ensure_executor()
        next_node_index = len(self.journal.nodes)
        total_seeds = self.cfg.agent.multi_seed_eval.num_seeds

        # Batch size is determined by num_workers (GPU availability is handled per-seed)
        batch_size = self.num_workers
        logger.info(
            "Running multi-seed evaluation in batches of %s (num_workers=%s, total_seeds=%s)",
            batch_size,
            self.num_workers,
            total_seeds,
        )

        # Process seeds in batches to ensure proper GPU resource management
        completed_seeds = 0
        for batch_start in range(0, total_seeds, batch_size):
            batch_end = min(batch_start + batch_size, total_seeds)
            batch_seeds = list(range(batch_start, batch_end))
            logger.info(
                "Starting seed evaluation batch: seeds %s (batch %d/%d)",
                batch_seeds,
                (batch_start // batch_size) + 1,
                (total_seeds + batch_size - 1) // batch_size,
            )

            batch_results = self._run_seed_batch(
                node=node,
                node_data=node_data,
                seeds=batch_seeds,
                executor=executor,
                next_node_index=next_node_index,
                total_seeds=total_seeds,
                completed_seeds_before=completed_seeds,
            )
            seed_nodes.extend(batch_results)
            next_node_index += len(batch_seeds)
            completed_seeds += len(batch_seeds)

        # Run a Codex seed-aggregation task to produce a single rolled-up node with aggregate plots/metric.
        aggregation_execution_id: str | None = None
        if len(seed_nodes) >= 2:
            # Emit aggregation progress event (start)
            try:
                self.event_callback(
                    RunStageProgressEvent(
                        stage=ApiStage(self.stage_name),
                        iteration=1,
                        max_iterations=1,
                        progress=0.0,
                        total_nodes=1,
                        buggy_nodes=0,
                        good_nodes=0,
                        best_metric=None,
                        is_seed_node=False,
                        is_seed_agg_node=True,
                    )
                )
            except Exception:
                logger.exception("Failed to emit aggregation progress event (start)")

            try:
                aggregation_execution_id = uuid.uuid4().hex
                execution_registry.register_execution(
                    execution_id=aggregation_execution_id,
                    node=node,
                    stage_name=f"{self.stage_name}_seed_aggregation",
                )
                seed_payload: list[SeedNodeSummary] = []
                for seed_node in seed_nodes:
                    seed_payload.append(
                        SeedNodeSummary(
                            id=seed_node.id,
                            exp_results_dir=seed_node.exp_results_dir,
                            metric=(
                                seed_node.metric.to_dict() if seed_node.metric is not None else None
                            ),
                            plots=list(seed_node.plots),
                            plot_paths=list(seed_node.plot_paths),
                            is_buggy=bool(seed_node.is_buggy is True),
                            is_buggy_plots=bool(seed_node.is_buggy_plots is True),
                        )
                    )
                seed_aggregation = SeedAggregationPayload(
                    parent_node_id=node.id,
                    stage_name=self.stage_name,
                    seed_nodes=seed_payload,
                )
                agg_node_index = len(self.journal.nodes)
                agg_task: NodeTask = {
                    "node_data": node_data,
                    "title": self.title,
                    "task_desc": self.task_desc,
                    "stage_goals": self.stage_goals,
                    "evaluation_metric_spec": self.evaluation_metric_spec,
                    "cfg": self.cfg,
                    "gpu_id": None,
                    "memory_summary": "",
                    "stage_identifier": self.stage_identifier,
                    "seed_eval": False,
                    "seed_value": 0,
                    "seed_aggregation": seed_aggregation,
                    "stage2_hyperparam_idea": None,
                    "stage4_ablation_idea": None,
                    "event_callback": self.event_callback,
                    "execution_id": aggregation_execution_id,
                    "user_feedback_payload": "",
                    "node_index": agg_node_index,
                }
                agg_future = executor.submit(process_node, **agg_task)
                agg_data = agg_future.result(timeout=self.timeout)
                agg_node = Node.from_dict(agg_data, self.journal)
                execution_registry.attach_node(
                    execution_id=aggregation_execution_id,
                    node=agg_node,
                )
                self.journal.append(agg_node)
                logger.info(
                    "Seed aggregation node appended (execution_id=%s node_id=%s)",
                    aggregation_execution_id,
                    agg_node.id,
                )
            except ExecutionTerminatedError:
                logger.info(
                    "Seed aggregation was terminated intentionally; skipping aggregation node."
                )
            except Exception:
                logger.exception("Seed aggregation failed; proceeding without aggregation node.")
            finally:
                if aggregation_execution_id is not None:
                    try:
                        execution_registry.clear_execution(aggregation_execution_id)
                    except Exception:
                        pass

        return seed_nodes

    def _run_seed_batch(
        self,
        *,
        node: Node,
        node_data: dict,
        seeds: List[int],
        executor: ProcessPoolExecutor,
        next_node_index: int,
        total_seeds: int,
        completed_seeds_before: int,
    ) -> List[Node]:
        """
        Run a batch of seeds and wait for all to complete before returning.

        This ensures GPUs are released after each batch completes, allowing
        subsequent batches to reuse the same GPU resources.
        """
        batch_nodes: List[Node] = []
        futures: list[Future] = []
        execution_ids: list[str] = []
        seed_process_ids: list[str | None] = []

        # Submit all seeds in this batch
        for idx, seed in enumerate(seeds):
            gpu_id = None
            process_id = f"seed_{seed}_worker"
            if self.gpu_manager is not None:
                try:
                    gpu_id = self.gpu_manager.acquire_gpu(process_id)
                    logger.info(f"Assigned GPU {gpu_id} to seed {seed}")
                    seed_process_ids.append(process_id)
                except RuntimeError as e:
                    logger.warning(f"Could not acquire GPU for seed {seed}: {e}. Running on CPU")
                    seed_process_ids.append(None)
            else:
                seed_process_ids.append(None)

            execution_id = uuid.uuid4().hex
            logger.info(
                "ParallelAgent registering multi-seed execution %s (seed=%s) for node %s",
                execution_id,
                seed,
                node.id,
            )
            execution_registry.register_execution(
                execution_id=execution_id,
                node=node,
                stage_name=self.stage_name,
            )
            task: NodeTask = {
                "node_data": node_data,
                "title": self.title,
                "task_desc": self.task_desc,
                "stage_goals": self.stage_goals,
                "evaluation_metric_spec": self.evaluation_metric_spec,
                "cfg": self.cfg,
                "gpu_id": gpu_id,
                "memory_summary": "",
                "stage_identifier": self.stage_identifier,
                "seed_eval": True,
                "seed_value": seed,
                "seed_aggregation": None,
                "stage2_hyperparam_idea": None,
                "stage4_ablation_idea": None,
                "event_callback": self.event_callback,
                "execution_id": execution_id,
                "user_feedback_payload": "",
                "node_index": next_node_index + idx,
            }

            # Emit seed evaluation progress event BEFORE starting execution
            # This ensures the event is sent before aggregation events
            try:
                seed_number = completed_seeds_before + idx + 1
                self.event_callback(
                    RunStageProgressEvent(
                        stage=ApiStage(self.stage_name),
                        iteration=seed_number,
                        max_iterations=total_seeds,
                        progress=float(seed_number) / float(total_seeds),
                        total_nodes=total_seeds,
                        buggy_nodes=0,
                        good_nodes=seed_number,
                        best_metric=None,
                        is_seed_node=True,
                        is_seed_agg_node=False,
                    )
                )
            except Exception:
                logger.exception("Failed to emit seed evaluation progress event (started)")

            future = executor.submit(process_node, **task)
            futures.append(future)
            execution_ids.append(execution_id)

        # Collect results for this batch
        for idx, future in enumerate(futures):
            execution_id = execution_ids[idx]
            seed = seeds[idx]
            try:
                result_data = future.result(timeout=self.timeout)
                result_node = Node.from_dict(result_data, self.journal)
                execution_registry.attach_node(
                    execution_id=execution_id,
                    node=result_node,
                )
                parent_id_str = result_node.parent.id if result_node.parent is not None else "N/A"
                logger.debug(f"Parent node id: {parent_id_str}")
                logger.debug(f"Sanity check: actual parent node id: {node.id}")
                # Add node to journal's list and assign its step number
                self.journal.append(result_node)
                node_found = self.journal.get_node_by_id(result_node.id)
                if node_found is not None:
                    batch_nodes.append(node_found)
                logger.debug(f"Added seed {seed} result node to journal")
            except ExecutionTerminatedError:
                logger.info(
                    "Multi-seed execution %s (seed=%s) was terminated intentionally; skipping result.",
                    execution_id,
                    seed,
                )
            except ExecutionCrashedError as exc:
                logger.error(
                    "Multi-seed execution %s (seed=%s) crashed unexpectedly: %s",
                    execution_id,
                    seed,
                    exc,
                )
            except Exception:
                logger.exception(f"Error in multi-seed evaluation for seed {seed}")
            finally:
                logger.info(
                    "ParallelAgent clearing execution %s after multi-seed run for node %s (seed=%s)",
                    execution_id,
                    node.id,
                    seed,
                )
                execution_registry.clear_execution(execution_id)

                # Release GPU after this seed completes
                proc_id = seed_process_ids[idx]
                if self.gpu_manager is not None and proc_id is not None:
                    self.gpu_manager.release_gpu(proc_id)
                    logger.info(f"Released GPU for {proc_id} (seed {seed})")

        return batch_nodes

    def _get_leaves(self, node: Node) -> List[Node]:
        """Get all leaf nodes in the subtree rooted at node."""
        if not node.children:
            return [node]

        leaves = []
        for child in node.children:
            leaves.extend(self._get_leaves(child))
        return leaves

    def _select_parallel_nodes(self) -> List[Optional[Node]]:
        """Select nodes to process in parallel using a mix of exploration and exploitation."""
        # Emit that we're selecting nodes
        self.event_callback(
            RunLogEvent(
                message=f"🔍 Selecting nodes to process for iteration {len(self.journal)}...",
                level="info",
            )
        )
        stage_identifier = self.stage_identifier
        # Codex-only pipeline: all idea generation (baseline/tuning/plotting/ablation) happens inside
        # the worker via Codex, using stage goals + context embedded in codex_task.md (JSON + markdown).
        nodes_to_process: list[Optional[Node]] = []
        processed_trees: set[int] = set()
        search_cfg = self.cfg.agent.search
        logger.debug(
            "node_selection.begin stage=%s num_workers=%s total_nodes=%s good_nodes=%s buggy_nodes=%s draft_roots=%s",
            self.stage_name,
            self.num_workers,
            len(self.journal.nodes),
            len(self.journal.good_nodes),
            len(self.journal.buggy_nodes),
            len(self.journal.draft_nodes),
        )

        feedback_nodes = [node for node in self.journal.nodes if node.user_feedback_pending]
        if feedback_nodes:
            logger.debug(
                "node_selection.user_feedback_pending count=%s ids=%s",
                len(feedback_nodes),
                [n.id[:8] for n in feedback_nodes[:5]],
            )
        for node in feedback_nodes:
            if len(nodes_to_process) >= self.num_workers:
                break
            if node.is_leaf and node.parent is None and node.children:
                logger.info(
                    "Skipping root node %s for feedback re-run because it already has children; enqueuing most recent child instead.",
                    node.id[:8],
                )
                newest_child = max(node.children, key=lambda c: c.ctime)
                newest_child.is_user_feedback = node.is_user_feedback
                newest_child.user_feedback_payload = node.user_feedback_payload
                newest_child.user_feedback_pending = True
                node.user_feedback_pending = False
                # Consume feedback from the root node so it only impacts the next scheduled run.
                payload = node.user_feedback_payload or ""
                if payload:
                    self._one_shot_user_feedback_payloads[newest_child.id] = payload
                node.user_feedback_payload = None
                node.is_user_feedback = False
                feedback_nodes.append(newest_child)
                continue
            logger.info(
                "Scheduling node %s to re-run with user feedback (payload_preview=%s)",
                node.id[:8],
                (node.user_feedback_payload or "")[:120].replace("\n", " "),
            )
            node.user_feedback_pending = False
            payload = node.user_feedback_payload or ""
            if payload:
                self._one_shot_user_feedback_payloads[node.id] = payload
            node.user_feedback_payload = None
            node.is_user_feedback = False
            nodes_to_process.append(node)

        while len(nodes_to_process) < self.num_workers:
            # Drafting: create root nodes up to target drafts
            logger.debug(
                f"Checking draft nodes... num of journal.draft_nodes: {len(self.journal.draft_nodes)}, search_cfg.num_drafts: {search_cfg.num_drafts}"
            )
            if len(self.journal.draft_nodes) < search_cfg.num_drafts:
                logger.debug(
                    "node_selection.decision decision=draft reason=insufficient_draft_roots current=%s target=%s",
                    len(self.journal.draft_nodes),
                    search_cfg.num_drafts,
                )
                nodes_to_process.append(None)
                continue

            # Get viable trees
            viable_trees = [
                root
                for root in self.journal.draft_nodes
                if not all(leaf.is_buggy for leaf in self._get_leaves(root))
            ]
            logger.debug(
                "node_selection.viable_trees count=%s total_draft_roots=%s",
                len(viable_trees),
                len(self.journal.draft_nodes),
            )

            # Debugging phase (probabilistic)
            debug_roll = random.random()
            if debug_roll < search_cfg.debug_prob:
                logger.debug(
                    "node_selection.debug_roll roll=%s threshold=%s decision=debug",
                    debug_roll,
                    search_cfg.debug_prob,
                )
                logger.debug("Checking debuggable nodes")
                debuggable_nodes: list[Node] = []
                try:
                    logger.debug("Checking buggy nodes...")
                    buggy_nodes = self.journal.buggy_nodes
                    logger.debug(f"Type of buggy_nodes: {type(buggy_nodes)}")
                    logger.debug(f"Length of buggy_nodes: {len(buggy_nodes)}")

                    debuggable_nodes = [
                        n
                        for n in self.journal.buggy_nodes
                        if (
                            isinstance(n, Node)
                            and n.is_leaf
                            and n.debug_depth <= search_cfg.max_debug_depth
                        )
                    ]
                except Exception as e:
                    logger.exception(f"Error getting debuggable nodes: {e}")
                if debuggable_nodes:
                    logger.debug("Found debuggable nodes")
                    node = random.choice(debuggable_nodes)
                    logger.debug(
                        "node_selection.debug_choice node=%s debug_depth=%s max_debug_depth=%s exc_type=%s",
                        node.id[:8],
                        node.debug_depth,
                        search_cfg.max_debug_depth,
                        node.exc_type,
                    )
                    tree_root = node
                    while tree_root.parent:
                        tree_root = tree_root.parent

                    tree_id = id(tree_root)
                    if tree_id not in processed_trees or len(processed_trees) >= len(viable_trees):
                        nodes_to_process.append(node)
                        processed_trees.add(tree_id)
                        continue
            else:
                logger.debug(
                    "node_selection.debug_roll roll=%s threshold=%s decision=skip_debug",
                    debug_roll,
                    search_cfg.debug_prob,
                )

            # Stage-specific selection: Ablation Studies
            logger.debug(f"self.stage_name: {self.stage_name}")
            if stage_identifier is StageIdentifier.STAGE4:
                self.event_callback(
                    RunLogEvent(
                        message=f"🧪 Running ablation study variation #{len(self.journal) + 1}",
                        level="info",
                    )
                )
                logger.debug(
                    "node_selection.decision decision=ablation parent=%s",
                    None if self.best_stage3_node is None else self.best_stage3_node.id[:8],
                )
                nodes_to_process.append(self.best_stage3_node)
                continue
            # Stage-specific selection: Hyperparameter Tuning
            elif stage_identifier is StageIdentifier.STAGE2:
                logger.debug(
                    "node_selection.decision decision=tuning parent=%s",
                    None if self.best_stage1_node is None else self.best_stage1_node.id[:8],
                )
                nodes_to_process.append(self.best_stage1_node)
                continue
            else:  # Stage 1, 3: normal best-first search
                # Improvement phase
                logger.debug("Checking good nodes..")
                good_nodes = self.journal.good_nodes
                if not good_nodes:
                    logger.debug(
                        "node_selection.decision decision=draft reason=no_good_nodes good_nodes=0",
                    )
                    nodes_to_process.append(None)  # Back to drafting
                    continue

                # Get best node from unprocessed tree if possible
                best_node = self.journal.get_best_node()
                if best_node is None:
                    logger.debug(
                        "node_selection.decision decision=draft reason=no_best_node total_good_nodes=%s",
                        len(good_nodes),
                    )
                    nodes_to_process.append(None)
                    continue
                tree_root = best_node
                while tree_root.parent:
                    tree_root = tree_root.parent

                tree_id = id(tree_root)
                if tree_id not in processed_trees or len(processed_trees) >= len(viable_trees):
                    logger.debug(
                        "node_selection.decision decision=improve node=%s tree_root=%s processed_trees=%s viable_trees=%s",
                        best_node.id[:8],
                        tree_root.id[:8],
                        len(processed_trees),
                        len(viable_trees),
                    )
                    nodes_to_process.append(best_node)
                    processed_trees.add(tree_id)
                    continue

                # If we can't use best node (tree already processed), try next best nodes
                for node in sorted(
                    good_nodes,
                    key=lambda n: (n.metric if n.metric is not None else WorstMetricValue()),
                    reverse=True,
                ):
                    tree_root = node
                    while tree_root.parent:
                        tree_root = tree_root.parent
                    tree_id = id(tree_root)
                    if tree_id not in processed_trees or len(processed_trees) >= len(viable_trees):
                        logger.debug(
                            "node_selection.decision decision=improve_fallback node=%s tree_root=%s processed_trees=%s viable_trees=%s",
                            node.id[:8],
                            tree_root.id[:8],
                            len(processed_trees),
                            len(viable_trees),
                        )
                        nodes_to_process.append(node)
                        processed_trees.add(tree_id)
                        break

        return nodes_to_process

    def step(self, *, iteration: int, max_iterations: int) -> None:
        """Drive one iteration: select nodes, submit work, collect results, update state."""
        self.stage_skip.ensure_no_skip_pending()

        # Emit goal node progress event BEFORE starting execution
        # This ensures the event is sent before seed events (fixing race condition)
        try:
            best_node = self.journal.get_best_node()
            self.event_callback(
                RunStageProgressEvent(
                    stage=ApiStage(self.stage_name),
                    iteration=iteration,
                    max_iterations=max_iterations,
                    progress=(
                        (max(iteration - 1, 0) / max_iterations) if max_iterations > 0 else 0.0
                    ),
                    total_nodes=len(self.journal.nodes),
                    buggy_nodes=len(self.journal.buggy_nodes),
                    good_nodes=len(self.journal.good_nodes),
                    best_metric=str(best_node.metric) if best_node else None,
                    is_seed_node=False,
                    is_seed_agg_node=False,
                )
            )
        except Exception:
            logger.exception("Failed to emit goal node progress event")

        logger.debug("Selecting nodes to process")
        nodes_to_process = self._select_parallel_nodes()
        logger.debug(f"Selected nodes: {[n.id if n else None for n in nodes_to_process]}")

        draft_count = sum(1 for n in nodes_to_process if n is None)
        debug_count = sum(1 for n in nodes_to_process if n and n.is_buggy)
        improve_count = sum(1 for n in nodes_to_process if n and not n.is_buggy)

        # Emit node selection summary
        num_nodes = len([n for n in nodes_to_process if n is not None])
        activity_types = []
        if draft_count > 0:
            activity_types.append(f"{draft_count} new draft(s)")
        if debug_count > 0:
            activity_types.append(f"{debug_count} debugging")
        if improve_count > 0:
            activity_types.append(f"{improve_count} improving")
        activity_str = ", ".join(activity_types) if activity_types else "processing"
        self.event_callback(
            RunLogEvent(
                message=f"📤 Submitting {num_nodes} node(s): {activity_str}",
                level="info",
            )
        )

        if draft_count > 0:
            self.event_callback(
                RunLogEvent(message=f"Generating {draft_count} new implementation(s)", level="info")
            )
        if debug_count > 0:
            self.event_callback(
                RunLogEvent(
                    message=f"Debugging {debug_count} failed implementation(s)", level="info"
                )
            )
        if improve_count > 0:
            self.event_callback(
                RunLogEvent(
                    message=f"Improving {improve_count} working implementation(s)", level="info"
                )
            )

        # Convert nodes to serializable dicts for worker submission
        node_data_list: list[dict[str, object] | None] = []
        for node in nodes_to_process:
            if node:
                try:
                    node_dict = node.to_dict()
                    _safe_pickle_test(node_dict, f"node {node.id} data")
                    node_data_list.append(node_dict)
                except Exception as e:
                    logger.error(f"Error preparing node {node.id}: {str(e)}")
                    raise
            else:
                node_data_list.append(None)  # None means new draft

        memory_summary = self.journal.generate_summary(include_code=False)

        # Submit tasks to process pool
        logger.debug("Submitting tasks to process pool")

        executor = self._ensure_executor()
        futures: list[Future] = []
        scheduled_stage2_names: set[str] = set()
        scheduled_stage4_names: set[str] = set()
        next_node_index = len(self.journal.nodes)
        try:
            for node, node_data in zip(nodes_to_process, node_data_list):
                self.stage_skip.ensure_no_skip_pending()
                gpu_id = None
                process_id = f"worker_{len(futures)}"
                if self.gpu_manager is not None:
                    try:
                        gpu_id = self.gpu_manager.acquire_gpu(process_id)
                        logger.info(f"Assigned GPU {gpu_id} to process {process_id}")
                    except RuntimeError as e:
                        logger.warning(f"Could not acquire GPU: {e}. Running on CPU")

                seed_eval = False
                seed_value = 0
                execution_id = uuid.uuid4().hex
                node_label = node.id if node else "draft"
                logger.info(
                    "ParallelAgent registering execution %s for node %s (stage=%s, feedback=%s)",
                    execution_id,
                    node_label,
                    self.stage_name,
                    bool(node.user_feedback_payload) if node else False,
                )
                execution_registry.register_execution(
                    execution_id=execution_id,
                    node=node,
                    stage_name=self.stage_name,
                )
                user_feedback_payload = ""
                if node is not None:
                    user_feedback_payload = self._one_shot_user_feedback_payloads.pop(node.id, "")
                is_not_buggy = (
                    node_data is not None
                    and isinstance(node_data, dict)
                    and node_data.get("is_buggy") is False
                )
                stage2_hyperparam_idea: StageIdea | None = None
                if (
                    self.stage_identifier is StageIdentifier.STAGE2
                    and node is not None
                    and is_not_buggy
                ):
                    base_code = node.code or ""
                    tried_hyperparam_set: set[str] = set()
                    for prev in self.journal.nodes:
                        name = prev.hyperparam_name
                        if isinstance(name, str) and name.strip():
                            tried_hyperparam_set.add(name.strip())
                    tried_hyperparam_set |= scheduled_stage2_names
                    tried_hyperparams = sorted(tried_hyperparam_set)[:50]
                    hyperparam_idea = propose_next_hyperparam_idea(
                        base_code=base_code,
                        tried=tried_hyperparams,
                        model=self.cfg.agent.feedback.model,
                        temperature=self.cfg.agent.feedback.temperature,
                    )
                    scheduled_stage2_names.add(hyperparam_idea.name)
                    stage2_hyperparam_idea = StageIdea(
                        name=hyperparam_idea.name,
                        description=hyperparam_idea.description,
                        tried_names=list(tried_hyperparams),
                    )
                stage4_ablation_idea: StageIdea | None = None
                if (
                    self.stage_identifier is StageIdentifier.STAGE4
                    and node is not None
                    and is_not_buggy
                ):
                    base_code = node.code or ""
                    tried_ablation_set: set[str] = set()
                    for prev in self.journal.nodes:
                        name = prev.ablation_name
                        if isinstance(name, str) and name.strip():
                            tried_ablation_set.add(name.strip())
                    tried_ablation_set |= scheduled_stage4_names
                    tried_ablations = sorted(tried_ablation_set)[:50]
                    ablation_idea = propose_next_ablation_idea(
                        base_code=base_code,
                        tried=tried_ablations,
                        model=self.cfg.agent.feedback.model,
                        temperature=self.cfg.agent.feedback.temperature,
                    )
                    scheduled_stage4_names.add(ablation_idea.name)
                    stage4_ablation_idea = StageIdea(
                        name=ablation_idea.name,
                        description=ablation_idea.description,
                        tried_names=list(tried_ablations),
                    )
                task: NodeTask = {
                    "node_data": node_data,
                    "title": self.title,
                    "task_desc": self.task_desc,
                    "stage_goals": self.stage_goals,
                    "evaluation_metric_spec": self.evaluation_metric_spec,
                    "cfg": self.cfg,
                    "gpu_id": gpu_id,
                    "memory_summary": memory_summary,
                    "stage_identifier": self.stage_identifier,
                    "seed_eval": seed_eval,
                    "seed_value": seed_value,
                    "seed_aggregation": None,
                    "stage2_hyperparam_idea": stage2_hyperparam_idea,
                    "stage4_ablation_idea": stage4_ablation_idea,
                    "event_callback": self.event_callback,
                    "execution_id": execution_id,
                    "user_feedback_payload": user_feedback_payload,
                    "node_index": next_node_index,
                }
                next_node_index += 1
                future = executor.submit(process_node, **task)
                futures.append(future)
                self._future_execution_ids[future] = execution_id
                self._future_process_ids[future] = process_id

            # Collect results as they complete and update journal/state
            logger.debug("Waiting for results")
            for idx, future in enumerate(futures):
                self.stage_skip.ensure_no_skip_pending()
                current_execution_id: str | None
                current_execution_id = (
                    self._future_execution_ids.pop(future)
                    if future in self._future_execution_ids
                    else None
                )
                try:
                    logger.debug("About to get result from future")
                    result_data = future.result(timeout=self.timeout)

                    if "metric" in result_data:
                        logger.debug(f"metric type: {type(result_data['metric'])}")
                        logger.debug(f"metric contents: {result_data['metric']}")

                    result_node = Node.from_dict(result_data, self.journal)
                    if current_execution_id is not None:
                        execution_registry.attach_node(
                            execution_id=current_execution_id,
                            node=result_node,
                        )
                        entry = execution_registry.get_entry(current_execution_id)
                        if entry and entry.status == "terminated" and entry.payload:
                            result_node.is_user_feedback = True
                            result_node.user_feedback_payload = entry.payload
                            result_node.user_feedback_pending = True
                            logger.info(
                                "Result node %s inherited termination payload (%s chars) from execution %s.",
                                result_node.id[:8],
                                len(entry.payload),
                                current_execution_id,
                            )
                    logger.debug("Investigating if result node has metric")
                    logger.debug(str(result_node.metric))

                    self.journal.append(result_node)
                    logger.debug("Added result node to journal")

                    if result_node.is_buggy:
                        self.event_callback(
                            RunLogEvent(
                                message=f"Node {idx + 1}/{len(futures)} completed (buggy, will retry)",
                                level="info",
                            )
                        )
                    else:
                        metric_str = str(result_node.metric)[:50] if result_node.metric else "N/A"
                        self.event_callback(
                            RunLogEvent(
                                message=(
                                    f"Node {idx + 1}/{len(futures)} completed successfully "
                                    f"(metric: {metric_str})"
                                ),
                                level="info",
                            )
                        )

                except TimeoutError:
                    logger.warning("Worker process timed out, couldn't get the result")
                    self.event_callback(
                        RunLogEvent(
                            message=f"Node {idx + 1}/{len(futures)} timed out after {self.timeout}s",
                            level="warn",
                        )
                    )
                    if current_execution_id is not None:
                        self._handle_worker_timeout(
                            future=future,
                            execution_id=current_execution_id,
                        )
                        self._deferred_registry_clears.add(current_execution_id)
                    else:
                        self._handle_worker_timeout(future=future)
                except ExecutionTerminatedError:
                    logger.info(
                        "Execution %s was terminated intentionally; deferring node re-run.",
                        current_execution_id,
                    )
                    self.event_callback(
                        RunLogEvent(
                            message=f"Node {idx + 1}/{len(futures)} was terminated intentionally",
                            level="info",
                        )
                    )
                    continue
                except ExecutionCrashedError as exc:
                    # Emit exactly one Sentry event for a true crash. Avoid error-level logging
                    # here to prevent multiple Sentry events for the same underlying issue.
                    sentry_sdk.capture_exception(exc)
                    logger.warning(
                        "Execution %s crashed unexpectedly: %s",
                        current_execution_id,
                        exc,
                    )
                    self.event_callback(
                        RunLogEvent(
                            message=(
                                f"Node {idx + 1}/{len(futures)} crashed unexpectedly: {exc}. "
                                "Marking as buggy."
                            ),
                            level="error",
                        )
                    )
                    if current_execution_id is not None:
                        entry = execution_registry.get_entry(current_execution_id)
                        if entry and entry.node is not None:
                            entry.node.is_buggy = True
                    continue
                except Exception as exc:
                    logger.exception(
                        "Unhandled worker exception for execution %s", current_execution_id
                    )
                    sentry_sdk.capture_exception(exc)
                    self.event_callback(
                        RunLogEvent(
                            message=(
                                f"Node {idx + 1}/{len(futures)} crashed with unexpected error: {exc}. "
                                "Marking as buggy."
                            ),
                            level="error",
                        )
                    )
                    if current_execution_id is not None:
                        entry = execution_registry.get_entry(current_execution_id)
                        if entry and entry.node is not None:
                            entry.node.is_buggy = True
                    continue
                finally:
                    if current_execution_id is not None:
                        if current_execution_id in self._deferred_registry_clears:
                            logger.info(
                                "Deferring execution registry clear for %s (timeout/termination).",
                                current_execution_id,
                            )
                        else:
                            logger.info(
                                "ParallelAgent clearing execution %s after future completion",
                                current_execution_id,
                            )
                            execution_registry.clear_execution(current_execution_id)
                    completed_process_id = (
                        self._future_process_ids.pop(future)
                        if future in self._future_process_ids
                        else None
                    )
                    if (
                        self.gpu_manager is not None
                        and completed_process_id is not None
                        and completed_process_id in self.gpu_manager.gpu_assignments
                    ):
                        self.gpu_manager.release_gpu(completed_process_id)
                        logger.info(f"Released GPU for process {completed_process_id}")
        except SkipInProgressError as exc:
            logger.info(
                "Skip detected while processing stage %s inside ParallelAgent: %s",
                self.stage_name,
                exc.reason,
            )
            self.abort_active_executions(reason=exc.reason)
            self._cancel_pending_futures(futures)
            raise

    def __enter__(self) -> "ParallelAgent":
        return self

    def cleanup(self) -> None:
        """Cleanup parallel workers and resources"""
        # Release GPUs, shutdown executor, and terminate lingering processes
        if not self._is_shutdown:
            logger.info("Shutting down parallel executor...")
            try:
                # Release all GPUs
                if self.gpu_manager is not None:
                    for process_id in list(self.gpu_manager.gpu_assignments.keys()):
                        self.gpu_manager.release_gpu(process_id)

                self._shutdown_executor()

                logger.info("Executor shutdown complete")
                # Clear any deferred registry entries now that the executor is shut down.
                for execution_id in list(self._deferred_registry_clears):
                    try:
                        execution_registry.clear_execution(execution_id)
                    except Exception:
                        logger.debug(
                            "Failed to clear deferred execution registry entry %s during cleanup",
                            execution_id,
                        )
                self._deferred_registry_clears.clear()

            except Exception as e:
                logger.exception(f"Error during executor shutdown: {e}")
            finally:
                self._is_shutdown = True

    def __exit__(
        self,
        _exc_type: type[BaseException] | None,
        _exc_val: BaseException | None,
        _exc_tb: TracebackType | None,
    ) -> None:
        self.cleanup()

    def _create_executor(self) -> ProcessPoolExecutor:
        shared_state = execution_registry.get_shared_pid_state()
        initializer = (
            partial(_executor_initializer, shared_state) if shared_state is not None else None
        )
        if shared_state is None:
            logger.warning(
                "Shared PID state missing; executor will start without termination support."
            )
        return ProcessPoolExecutor(
            max_workers=self.num_workers,
            mp_context=self._mp_context,
            initializer=initializer,
        )

    def _shutdown_executor(self) -> None:
        executor = self.executor
        if executor is None:
            return
        try:
            executor.shutdown(wait=False, cancel_futures=True)
            processes = []
            if getattr(executor, "_processes", None):
                processes = list(executor._processes.values())
            for process in processes:
                if process.is_alive():
                    process.terminate()
                    process.join(timeout=1)
        finally:
            self.executor = None

    def _restart_executor(self) -> None:
        logger.warning("Restarting process pool executor after worker timeout")
        self._shutdown_executor()
        self.executor = self._create_executor()

    def _handle_worker_timeout(self, *, future: Future, execution_id: str | None = None) -> None:
        future.cancel()
        if execution_id is not None:
            reason = f"Execution timed out after {self.timeout}s"
            entry = execution_registry.get_entry(execution_id)
            node_ref = entry.node if entry is not None else None
            status, pid, _node = execution_registry.begin_termination(
                execution_id=execution_id,
                payload=reason,
            )
            if node_ref is None and _node is not None:
                node_ref = _node
            if node_ref is not None:
                existing_feedback = (node_ref.exec_time_feedback or "").strip()
                node_ref.exec_time_feedback = (
                    f"{existing_feedback}\n{reason}" if existing_feedback else reason
                )
                logger.info(
                    "Recorded timeout feedback for node %s: %s",
                    node_ref.id[:8],
                    reason,
                )
            else:
                # Draft executions are registered with node=None, and when they time out we never
                # receive a result_node to append to the journal. Without a journal entry, the
                # next iteration's memory_summary becomes "No experiments conducted yet." and the
                # codegen LLM has no signal to reduce runtime.
                existing = self.journal.get_node_by_id(execution_id)
                if existing is None:
                    timeout_node = Node(
                        id=execution_id,
                        plan="",
                        code="",
                        is_buggy=True,
                        analysis=reason,
                        exc_type="TimeoutError",
                        exec_time=float(self.timeout),
                        exec_time_feedback=reason,
                        metric=WorstMetricValue(),
                    )
                    self.journal.append(timeout_node)
                    logger.info(
                        "Created synthetic timeout node %s to preserve timeout feedback in journal.",
                        execution_id[:8],
                    )
                else:
                    existing.is_buggy = True
                    existing.analysis = reason
                    existing.exc_type = existing.exc_type or "TimeoutError"
                    existing.exec_time = existing.exec_time or float(self.timeout)
                    existing.exec_time_feedback = (
                        f"{existing.exec_time_feedback}\n{reason}".strip()
                        if existing.exec_time_feedback
                        else reason
                    )
                    existing.metric = existing.metric or WorstMetricValue()
                    logger.info("Updated existing node %s with timeout feedback.", execution_id[:8])
            if status == "ok" and pid is not None:
                try:
                    send_signal_to_process_group(pid=pid, sig=signal.SIGKILL)
                    logger.info(
                        "Sent SIGKILL to pid=%s for timed-out execution_id=%s",
                        pid,
                        execution_id,
                    )
                except ProcessLookupError:
                    logger.info(
                        "Timed-out execution_id=%s already exited before SIGKILL.",
                        execution_id,
                    )
                except PermissionError:
                    logger.exception(
                        "Permission error when terminating pid=%s for execution_id=%s",
                        pid,
                        execution_id,
                    )
            else:
                logger.warning(
                    "Unable to terminate timed-out execution_id=%s (status=%s); flagging skip pending.",
                    execution_id,
                    status,
                )
                execution_registry.flag_skip_pending(execution_id=execution_id, reason=reason)
        self._restart_executor()

    def _ensure_executor(self) -> ProcessPoolExecutor:
        if self.executor is None:
            self.executor = self._create_executor()
        return self.executor
