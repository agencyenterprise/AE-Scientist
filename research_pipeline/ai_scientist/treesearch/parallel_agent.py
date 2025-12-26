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
import traceback
import uuid
from collections.abc import Callable
from concurrent.futures import Future, ProcessPoolExecutor
from functools import partial
from multiprocessing.managers import DictProxy
from types import TracebackType
from typing import List, Optional

from ai_scientist.llm import query, structured_query_with_schema

from . import execution_registry
from .codegen_agent import PlanAndCodeSchema
from .events import BaseEvent, GpuShortageEvent, RunLogEvent
from .gpu_manager import GPUManager, get_gpu_count
from .journal import Journal, Node
from .stages.stage2_tuning import Stage2Tuning
from .stages.stage4_ablation import Stage4Ablation
from .types import PromptType
from .utils.config import Config
from .utils.metric import WorstMetricValue
from .worker_process import ExecutionCrashedError, ExecutionTerminatedError, process_node

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
        task_desc: str,
        cfg: Config,
        journal: Journal,
        stage_name: str,
        best_stage3_node: Node | None,
        best_stage2_node: Node | None,
        best_stage1_node: Node | None,
        event_callback: Callable[[BaseEvent], None],
    ):
        # Store run context (idea, configuration, journal, stage)
        self.task_desc = task_desc
        self.cfg = cfg
        self.journal = journal
        self.stage_name = stage_name
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
        # Define the evaluation metric once at initialization
        self.evaluation_metrics = self._define_global_metrics()
        self._ablation_state: dict[str, set[str]] = {  # store ablation names
            "completed_ablations": set(),
        }
        self._hyperparam_tuning_state: dict[str, set[str]] = {  # store hyperparam tuning ideas
            "tried_hyperparams": set(),
        }
        self._shared_pid_state = execution_registry.get_shared_pid_state()
        self._future_execution_ids: dict[Future, str] = {}

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

    def _define_global_metrics(self) -> str:
        """Define the run-wide evaluation metric specification via LLM."""
        prompt = {
            "Introduction": (
                "You are an AI researcher setting up experiments. "
                "Please propose meaningful evaluation metrics that will help analyze "
                "the performance and characteristics of solutions for this research task."
            ),
            "Research idea": self.task_desc,
            "Instructions": [
                "Propose a single evaluation metric that would be useful for analyzing the performance of solutions for this research task.",
                "Note: Validation loss will be tracked separately so you don't need to include it in your response.",
                "Format your response as a list containing:",
                "- name: The name of the metric",
                "- maximize: Whether higher values are better (true/false)",
                "- description: A brief explanation of what the metric measures"
                "Your list should contain only one metric.",
            ],
        }

        response = query(
            system_message=prompt,
            user_message=None,
            model=self.cfg.agent.code.model,
            temperature=self.cfg.agent.code.temperature,
        )

        logger.debug(f"Defined eval metrics: {response}")
        response_text: str = response if isinstance(response, str) else str(response)
        return response_text

    def plan_and_code_query(self, prompt: PromptType, retries: int = 3) -> tuple[str, str]:
        """Generate a natural language plan + code in the same LLM call and split them apart."""
        last_completion: str = ""
        for _ in range(retries):
            logger.debug("ParallelAgent: calling structured plan_and_code_query")
            try:
                response = structured_query_with_schema(
                    system_message=prompt,
                    model=self.cfg.agent.code.model,
                    temperature=self.cfg.agent.code.temperature,
                    schema_class=PlanAndCodeSchema,
                )
            except Exception as exc:
                logger.warning("ParallelAgent: structured plan + code query failed, retrying...")
                logger.warning("ParallelAgent: failure details: %s", exc)
                continue

            nl_text = response.plan.strip()
            code = response.code.strip()
            last_completion = f"{nl_text}\n\n{code}"

            if nl_text and code:
                return nl_text, code

            logger.warning(
                "ParallelAgent: structured plan + code missing 'plan' or 'code', retrying...",
            )
            prompt["Parsing Feedback"] = (
                "The structured response was missing either 'plan' or 'code'. "
                "Ensure both fields are present and non-empty."
            )
        logger.error("Final plan + code extraction attempt failed, giving up...")
        return "", last_completion

    def _run_multi_seed_evaluation(self, node: Node) -> List[Node]:
        """Run multiple seeds of the same node to get statistical metrics.
        Returns a list of nodes with different random seeds."""
        # Convert node to dict for parallel processing
        node_data = node.to_dict()
        node_code = node.code

        # Submit parallel jobs for different seeds
        seed_nodes: List[Node] = []
        futures: list[Future] = []
        execution_ids: list[str] = []
        seed_process_ids: list[str | None] = []  # Track process IDs for GPU release
        executor = self._ensure_executor()
        for seed in range(self.cfg.agent.multi_seed_eval["num_seeds"]):
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

            # Add seed to node code
            node_data["code"] = (
                f"# Set random seed\nimport random\nimport numpy as np\nimport torch\n\nseed = {seed}\nrandom.seed(seed)\nnp.random.seed(seed)\ntorch.manual_seed(seed)\nif torch.cuda.is_available():\n    torch.cuda.manual_seed(seed)\n\n"
                + node_code
            )

            new_ablation_idea = None
            new_hyperparam_idea = None
            best_stage3_plot_code = None
            seed_eval = True
            memory_summary = ""
            logger.info("Starting multi-seed eval...")
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
            future = executor.submit(
                process_node,
                node_data=node_data,
                task_desc=self.task_desc,
                cfg=self.cfg,
                gpu_id=gpu_id,
                memory_summary=memory_summary,
                evaluation_metrics=self.evaluation_metrics,
                stage_name=self.stage_name,
                new_ablation_idea=new_ablation_idea,
                new_hyperparam_idea=new_hyperparam_idea,
                best_stage3_plot_code=best_stage3_plot_code,
                seed_eval=seed_eval,
                event_callback=self.event_callback,
                execution_id=execution_id,
            )
            futures.append(future)
            execution_ids.append(execution_id)

        # Collect results and release GPUs
        for idx, future in enumerate(futures):
            execution_id = execution_ids[idx]
            try:
                result_data = future.result(timeout=self.timeout)
                result_node = Node.from_dict(result_data, self.journal)
                parent_id_str = result_node.parent.id if result_node.parent is not None else "N/A"
                logger.debug(f"Parent node id: {parent_id_str}")
                logger.debug(f"Sanity check: actual parent node id: {node.id}")
                # Add node to journal's list and assign its step number
                self.journal.append(result_node)
                node_found = self.journal.get_node_by_id(result_node.id)
                if node_found is not None:
                    seed_nodes.append(node_found)
                logger.debug("Added result node to journal")
            except ExecutionTerminatedError:
                logger.info(
                    "Multi-seed execution %s was terminated intentionally; skipping result.",
                    execution_id,
                )
            except ExecutionCrashedError as exc:
                logger.error(
                    "Multi-seed execution %s crashed unexpectedly: %s",
                    execution_id,
                    exc,
                )
            except Exception as e:
                logger.error(f"Error in multi-seed evaluation: {str(e)}")
            finally:
                logger.info(
                    "ParallelAgent clearing execution %s after multi-seed run for node %s",
                    execution_id,
                    node.id,
                )
                execution_registry.clear_execution(execution_id)
                # Release GPU after this seed completes
                if self.gpu_manager is not None and idx < len(seed_process_ids):
                    proc_id = seed_process_ids[idx]
                    if proc_id is not None:
                        self.gpu_manager.release_gpu(proc_id)
                        logger.info(f"Released GPU for {proc_id}")

        return seed_nodes

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
        # For Stage 2/4 we generate ideas on main process to avoid duplicates;
        # for Stage 1/3 generation happens in workers.
        nodes_to_process: list[Optional[Node]] = []
        processed_trees: set[int] = set()
        search_cfg = self.cfg.agent.search
        logger.debug(f"self.num_workers: {self.num_workers}, ")

        feedback_nodes = [node for node in self.journal.nodes if node.user_feedback_pending]
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
                feedback_nodes.append(newest_child)
                continue
            logger.info(
                "Scheduling node %s to re-run with user feedback (payload_preview=%s)",
                node.id[:8],
                (node.user_feedback_payload or "")[:120].replace("\n", " "),
            )
            node.user_feedback_pending = False
            nodes_to_process.append(node)

        while len(nodes_to_process) < self.num_workers:
            # Drafting: create root nodes up to target drafts
            logger.debug(
                f"Checking draft nodes... num of journal.draft_nodes: {len(self.journal.draft_nodes)}, search_cfg.num_drafts: {search_cfg.num_drafts}"
            )
            if len(self.journal.draft_nodes) < search_cfg.num_drafts:
                nodes_to_process.append(None)
                continue

            # Get viable trees
            viable_trees = [
                root
                for root in self.journal.draft_nodes
                if not all(leaf.is_buggy for leaf in self._get_leaves(root))
            ]

            # Debugging phase (probabilistic)
            if random.random() < search_cfg.debug_prob:
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
                    tree_root = node
                    while tree_root.parent:
                        tree_root = tree_root.parent

                    tree_id = id(tree_root)
                    if tree_id not in processed_trees or len(processed_trees) >= len(viable_trees):
                        nodes_to_process.append(node)
                        processed_trees.add(tree_id)
                        continue

            # Stage-specific selection: Ablation Studies
            logger.debug(f"self.stage_name: {self.stage_name}")
            if self.stage_name and self.stage_name.startswith("4_"):
                self.event_callback(
                    RunLogEvent(
                        message=f"🧪 Running ablation study variation #{len(self.journal) + 1}",
                        level="info",
                    )
                )
                nodes_to_process.append(self.best_stage3_node)
                continue
            # Stage-specific selection: Hyperparameter Tuning
            elif self.stage_name and self.stage_name.startswith("2_"):
                nodes_to_process.append(self.best_stage1_node)
                continue
            else:  # Stage 1, 3: normal best-first search
                # Improvement phase
                logger.debug("Checking good nodes..")
                good_nodes = self.journal.good_nodes
                if not good_nodes:
                    nodes_to_process.append(None)  # Back to drafting
                    continue

                # Get best node from unprocessed tree if possible
                best_node = self.journal.get_best_node()
                if best_node is None:
                    nodes_to_process.append(None)
                    continue
                tree_root = best_node
                while tree_root.parent:
                    tree_root = tree_root.parent

                tree_id = id(tree_root)
                if tree_id not in processed_trees or len(processed_trees) >= len(viable_trees):
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
                        nodes_to_process.append(node)
                        processed_trees.add(tree_id)
                        break

        return nodes_to_process

    def step(self) -> None:
        """Drive one iteration: select nodes, submit work, collect results, update state."""
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
        for node, node_data in zip(nodes_to_process, node_data_list):
            gpu_id = None
            if self.gpu_manager is not None:
                try:
                    # Get current process ID for GPU assignment
                    process_id = f"worker_{len(futures)}"
                    gpu_id = self.gpu_manager.acquire_gpu(process_id)
                    logger.info(f"Assigned GPU {gpu_id} to process {process_id}")
                except RuntimeError as e:
                    logger.warning(f"Could not acquire GPU: {e}. Running on CPU")

            is_not_buggy = (
                node_data is not None
                and isinstance(node_data, dict)
                and node_data.get("is_buggy") is False
            )
            if self.stage_name and self.stage_name.startswith("2_") and is_not_buggy:
                base_stage1_code = self.best_stage1_node.code if self.best_stage1_node else ""
                tried_list = list(self._hyperparam_tuning_state["tried_hyperparams"])
                new_hyperparam_idea = Stage2Tuning.propose_next_hyperparam_idea(
                    base_stage1_code=base_stage1_code,
                    tried=tried_list,
                    model=self.cfg.agent.code.model,
                    temperature=self.cfg.agent.code.temperature,
                )
                self._hyperparam_tuning_state["tried_hyperparams"].add(new_hyperparam_idea.name)
                new_ablation_idea = None
            elif self.stage_name and self.stage_name.startswith("4_") and is_not_buggy:
                base_stage3_code = self.best_stage3_node.code if self.best_stage3_node else ""
                completed_list = list(self._ablation_state["completed_ablations"])
                new_ablation_idea = Stage4Ablation.propose_next_ablation_idea(
                    base_stage3_code=base_stage3_code,
                    completed=completed_list,
                    model=self.cfg.agent.code.model,
                    temperature=self.cfg.agent.code.temperature,
                )
                self._ablation_state["completed_ablations"].add(new_ablation_idea.name)
                new_hyperparam_idea = None
            else:
                new_ablation_idea = None
                new_hyperparam_idea = None

            best_stage3_plot_code = (
                self.best_stage3_node.plot_code if self.best_stage3_node else None
            )
            seed_eval = False
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
            future = executor.submit(
                process_node,
                node_data=node_data,
                task_desc=self.task_desc,
                cfg=self.cfg,
                gpu_id=gpu_id,
                memory_summary=memory_summary,
                evaluation_metrics=self.evaluation_metrics,
                stage_name=self.stage_name,
                new_ablation_idea=new_ablation_idea,
                new_hyperparam_idea=new_hyperparam_idea,
                best_stage3_plot_code=best_stage3_plot_code,
                seed_eval=seed_eval,
                event_callback=self.event_callback,
                execution_id=execution_id,
            )
            futures.append(future)
            self._future_execution_ids[future] = execution_id

        # Collect results as they complete and update journal/state
        logger.debug("Waiting for results")
        for i, future in enumerate(futures):
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

                # Create node and restore relationships using journal.
                # Journal acts as a database to look up a parent node,
                # and add the result node as a child.
                result_node = Node.from_dict(result_data, self.journal)
                if current_execution_id is not None:
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
                # Update hyperparam tuning state if in Stage 2
                Stage2Tuning.update_hyperparam_state(
                    stage_name=self.stage_name,
                    result_node=result_node,
                    state_set=self._hyperparam_tuning_state["tried_hyperparams"],
                )
                # Update ablation state if in Stage 4
                Stage4Ablation.update_ablation_state(
                    stage_name=self.stage_name,
                    result_node=result_node,
                    state_set=self._ablation_state["completed_ablations"],
                )

                # Add node to journal's list and assign its step number
                self.journal.append(result_node)
                logger.debug("Added result node to journal")

                if result_node.is_buggy:
                    self.event_callback(
                        RunLogEvent(
                            message=f"Node {i + 1}/{len(futures)} completed (buggy, will retry)",
                            level="info",
                        )
                    )
                else:
                    metric_str = str(result_node.metric)[:50] if result_node.metric else "N/A"
                    self.event_callback(
                        RunLogEvent(
                            message=f"Node {i + 1}/{len(futures)} completed successfully (metric: {metric_str})",
                            level="info",
                        )
                    )

            except TimeoutError:
                logger.warning("Worker process timed out, couldn't get the result")
                self.event_callback(
                    RunLogEvent(
                        message=f"Node {i + 1}/{len(futures)} timed out after {self.timeout}s",
                        level="warn",
                    )
                )
                self._handle_worker_timeout(future=future)
            except ExecutionTerminatedError:
                logger.info(
                    "Execution %s was terminated intentionally; deferring node re-run.",
                    current_execution_id,
                )
                self.event_callback(
                    RunLogEvent(
                        message=f"Node {i + 1}/{len(futures)} was terminated intentionally",
                        level="info",
                    )
                )
                continue
            except ExecutionCrashedError as exc:
                logger.error(
                    "Execution %s crashed unexpectedly: %s",
                    current_execution_id,
                    exc,
                )
                self.event_callback(
                    RunLogEvent(
                        message=(
                            f"Node {i + 1}/{len(futures)} crashed unexpectedly: {exc}. "
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
            except Exception as e:
                logger.exception(f"Error processing node: {str(e)}")

                traceback.print_exc()
                raise
            finally:
                if current_execution_id is not None:
                    logger.info(
                        "ParallelAgent clearing execution %s after future completion",
                        current_execution_id,
                    )
                    execution_registry.clear_execution(current_execution_id)
                # Release GPU for this process if it was using one
                process_id = f"worker_{i}"
                if self.gpu_manager is not None and process_id in self.gpu_manager.gpu_assignments:
                    self.gpu_manager.release_gpu(process_id)
                    logger.info(f"Released GPU for process {process_id}")

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

            except Exception as e:
                logger.exception(f"Error during executor shutdown: {e}")
            finally:
                self._is_shutdown = True

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
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

    def _handle_worker_timeout(self, *, future: Future) -> None:
        future.cancel()
        self._restart_executor()

    def _ensure_executor(self) -> ProcessPoolExecutor:
        if self.executor is None:
            self.executor = self._create_executor()
        return self.executor
