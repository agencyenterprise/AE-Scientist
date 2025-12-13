import copy
import json
import logging
import os
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, List, Literal, Optional, cast

from dataclasses_json import DataClassJsonMixin
from pydantic import BaseModel

from ai_scientist.llm import query, structured_query_with_schema

from .events import BaseEvent, BestNodeSelectedEvent, RunLogEvent
from .interpreter import ExecutionResult
from .utils.metric import MetricValue, WorstMetricValue
from .utils.response import trim_long_string

logger = logging.getLogger(__name__)


class NodeSelectionResponse(BaseModel):
    selected_id: str
    reasoning: str


NODE_SELECTION_SCHEMA = NodeSelectionResponse


@dataclass(eq=False)
class Node(DataClassJsonMixin):
    """A single node in the solution tree.

    Contains code, execution results, and evaluation information.
    """

    # ---- code & plan ----
    plan: str = field(default="", kw_only=True)
    overall_plan: str = field(default="", kw_only=True)
    code: str = field(default="", kw_only=True)
    plot_code: str | None = field(default=None, kw_only=True)
    plot_plan: str | None = field(default=None, kw_only=True)

    # ---- general attrs ----
    step: int | None = field(default=None, kw_only=True)
    id: str = field(default_factory=lambda: uuid.uuid4().hex, kw_only=True)
    ctime: float = field(default_factory=lambda: time.time(), kw_only=True)
    parent: Optional["Node"] = field(default=None, kw_only=True)
    children: set["Node"] = field(default_factory=set, kw_only=True)
    exp_results_dir: str | None = field(default=None, kw_only=True)

    # ---- execution info ----
    _term_out: list[str] | None = field(default=None, kw_only=True)
    exec_time: float | None = field(default=None, kw_only=True)
    exc_type: str | None = field(default=None, kw_only=True)
    exc_info: dict | None = field(default=None, kw_only=True)
    exc_stack: list[tuple] | None = field(default=None, kw_only=True)

    # ---- parsing info ----
    parse_metrics_plan: str = field(default="", kw_only=True)
    parse_metrics_code: str = field(default="", kw_only=True)
    # parse_exec_result: ExecutionResult = field(default=None, kw_only=True)
    parse_term_out: list[str] | None = field(default=None, kw_only=True)
    parse_exc_type: str | None = field(default=None, kw_only=True)
    parse_exc_info: dict | None = field(default=None, kw_only=True)
    parse_exc_stack: list[tuple] | None = field(default=None, kw_only=True)

    # ---- plot execution info ----
    plot_term_out: list[str] | None = field(default=None, kw_only=True)
    plot_exec_time: float | None = field(default=None, kw_only=True)
    plot_exc_type: str | None = field(default=None, kw_only=True)
    plot_exc_info: dict | None = field(default=None, kw_only=True)
    plot_exc_stack: list[tuple] | None = field(default=None, kw_only=True)

    # ---- evaluation ----
    # post-execution result analysis (findings/feedback)
    analysis: str | None = field(default=None, kw_only=True)
    metric: MetricValue | None = field(default=None, kw_only=True)
    # whether the agent decided that the code is buggy
    # -> always True if exc_type is not None or no valid metric
    is_buggy: bool | None = field(default=None, kw_only=True)
    is_buggy_plots: bool | None = field(default=None, kw_only=True)

    # ---- plotting ----
    plot_data: dict = field(default_factory=dict, kw_only=True)
    plots_generated: bool = field(default=False, kw_only=True)
    plots: List[str] = field(default_factory=list)  # Relative paths for visualization
    plot_paths: List[str] = field(default_factory=list)  # Absolute paths for programmatic access

    # ---- VLM feedback ----
    plot_analyses: list[dict[str, Any]] = field(default_factory=list)
    vlm_feedback_summary: List[str] = field(default_factory=list)
    datasets_successfully_tested: List[str] = field(default_factory=list)

    # ---- execution time feedback ----
    exec_time_feedback: str = field(default="", kw_only=True)

    # ---- ablation study ----
    ablation_name: str | None = field(default=None, kw_only=True)

    # ---- hyperparam tuning ----
    hyperparam_name: str | None = field(default=None, kw_only=True)

    # ---- seed node ----
    is_seed_node: bool = field(default=False, kw_only=True)
    is_seed_agg_node: bool = field(default=False, kw_only=True)

    # ---- internal helpers injected by agents ----
    _agent: Any | None = field(default=None, kw_only=True, repr=False)
    _vlm_feedback: dict[str, Any] | None = field(default=None, kw_only=True, repr=False)

    def __post_init__(self) -> None:
        # Ensure children is a set even if initialized with a list
        if isinstance(cast(Any, self.children), list):
            self.children = set(self.children)
        # Only try to add to parent's children if parent is a Node object
        if self.parent is not None and not isinstance(self.parent, str):
            self.parent.children.add(self)

    def __deepcopy__(self, memo: dict) -> "Node":
        # Create a new instance with copied attributes
        cls = self.__class__
        result = cls.__new__(cls)
        memo[id(self)] = result

        # Copy all attributes except parent and children to avoid circular references
        for k, v in self.__dict__.items():
            if k not in ("parent", "children"):
                setattr(result, k, copy.deepcopy(v, memo))

        # Handle parent and children separately
        result.parent = self.parent  # Keep the same parent reference
        result.children = set()  # Start with empty children set

        return result

    def __getstate__(self) -> dict:
        """Return state for pickling"""
        state = self.__dict__.copy()
        state["id"] = self.id
        return state

    def __setstate__(self, state: dict) -> None:
        """Set state during unpickling"""
        # Ensure all required attributes are present
        self.__dict__.update(state)

    @property
    def stage_name(self) -> Literal["draft", "debug", "improve"]:
        """
        Return the stage of the node:
        - "stage" if the node is an initial solution draft
        - "debug" if the node is the result of a debugging step
        - "improve" if the node is the result of an improvement step
        """
        if self.parent is None:
            return "draft"
        return "debug" if self.parent.is_buggy else "improve"

    def absorb_exec_result(self, exec_result: ExecutionResult) -> None:
        """Absorb the result of executing the code from this node."""
        self._term_out = exec_result.term_out
        self.exec_time = exec_result.exec_time
        self.exc_type = exec_result.exc_type
        self.exc_info = exec_result.exc_info
        self.exc_stack = exec_result.exc_stack

    def absorb_plot_exec_result(self, plot_exec_result: ExecutionResult) -> None:
        """Absorb the result of executing the plotting code from this node."""
        self.plot_term_out = plot_exec_result.term_out
        self.plot_exec_time = plot_exec_result.exec_time
        self.plot_exc_type = plot_exec_result.exc_type
        self.plot_exc_info = plot_exec_result.exc_info
        self.plot_exc_stack = plot_exec_result.exc_stack

    @property
    def term_out(self) -> str:
        """Get the terminal output of the code execution (after truncating it)."""
        if self._term_out is None:
            return ""
        return trim_long_string("".join(self._term_out))

    @property
    def is_leaf(self) -> bool:
        """Check if the node is a leaf node in the solution tree."""
        return not self.children

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Node):
            return NotImplemented
        return self.id == other.id

    def __hash__(self) -> int:
        return hash(self.id)

    @property
    def debug_depth(self) -> int:
        """
        Length of the current debug path
        - 0 if the node is not a debug node (parent is not buggy)
        - 1 if the parent is buggy but the skip parent isn't
        - n if there were n consecutive debugging steps
        """
        if self.stage_name != "debug":
            return 0
        if self.parent is None:
            return 0
        return self.parent.debug_depth + 1

    def to_dict(self) -> dict[str, object]:  # type: ignore[override]
        """Convert node to dictionary for serialization"""
        return {
            "code": self.code,
            "plan": self.plan,
            "overall_plan": self.overall_plan,
            "plot_code": self.plot_code,
            "plot_plan": self.plot_plan,
            "step": self.step,
            "id": self.id,
            "ctime": self.ctime,
            "_term_out": self._term_out,
            "parse_metrics_plan": self.parse_metrics_plan,
            "parse_metrics_code": self.parse_metrics_code,
            "parse_term_out": self.parse_term_out,
            "parse_exc_type": self.parse_exc_type,
            "parse_exc_info": self.parse_exc_info,
            "parse_exc_stack": self.parse_exc_stack,
            "exec_time": self.exec_time,
            "exc_type": self.exc_type,
            "exc_info": self.exc_info,
            "exc_stack": self.exc_stack,
            "analysis": self.analysis,
            "exp_results_dir": (
                str(Path(self.exp_results_dir).resolve().relative_to(os.getcwd()))
                if self.exp_results_dir
                else None
            ),
            "metric": {
                "value": self.metric.value if self.metric else None,
                "maximize": self.metric.maximize if self.metric else None,
                "name": self.metric.name if self.metric else None,
                "description": self.metric.description if self.metric else None,
            },
            "is_buggy": self.is_buggy,
            "is_buggy_plots": self.is_buggy_plots,
            "parent_id": None if self.parent is None else self.parent.id,
            "children": [child.id for child in self.children] if self.children else [],
            "plot_data": self.plot_data,
            "plots_generated": self.plots_generated,
            "plots": self.plots,
            "plot_paths": (
                [str(Path(p).resolve().relative_to(os.getcwd())) for p in self.plot_paths]
                if self.plot_paths
                else []
            ),
            "plot_analyses": [
                {
                    **analysis,
                    "plot_path": (
                        str(Path(analysis["plot_path"]).resolve().relative_to(os.getcwd()))
                        if analysis.get("plot_path")
                        else None
                    ),
                }
                for analysis in self.plot_analyses
            ],
            "vlm_feedback_summary": self.vlm_feedback_summary,
            "datasets_successfully_tested": self.datasets_successfully_tested,
            "ablation_name": self.ablation_name,
            "hyperparam_name": self.hyperparam_name,
            "is_seed_node": self.is_seed_node,
            "is_seed_agg_node": self.is_seed_agg_node,
            "exec_time_feedback": self.exec_time_feedback,
        }

    @classmethod
    def from_dict(cls, data: dict, journal: Optional["Journal"] = None) -> "Node":  # type: ignore[override]
        """Create a Node from a dictionary, optionally linking to journal for relationships"""
        # Remove relationship IDs from constructor data
        parent_id = data.pop("parent_id", None)
        data.pop("children", [])

        # Handle metric conversion
        metric_data = data.pop("metric", None)
        if metric_data:
            if isinstance(metric_data, dict):
                data["metric"] = MetricValue(
                    value=metric_data.get("value"),
                    maximize=metric_data.get("maximize"),
                    name=metric_data.get("name"),
                    description=metric_data.get("description"),
                )
            else:
                # Handle legacy format or None
                data["metric"] = (
                    WorstMetricValue() if data.get("is_buggy") else MetricValue(metric_data)
                )

        # Create node instance
        node = cls(**data)

        # If journal is provided, restore relationships
        if journal is not None and isinstance(parent_id, str):
            parent = journal.get_node_by_id(parent_id)
            if parent:
                node.parent = parent
                parent.children.add(node)

        return node


@dataclass
class Journal:
    """A collection of nodes representing the solution tree."""

    summary_model: str
    node_selection_model: str
    summary_temperature: float
    node_selection_temperature: float
    event_callback: Callable[[BaseEvent], None] = field(repr=False)
    stage_name: str = "unknown"
    run_id: str | None = None
    nodes: list[Node] = field(default_factory=list)
    # Multi-entry memoization to avoid repeated LLM selection calls across modes
    _best_cache: dict[str, Node | None] = field(default_factory=dict, repr=False)
    _best_cache_time_map: dict[str, float] = field(default_factory=dict, repr=False)
    _best_cache_candidate_ids_map: dict[str, list[str]] = field(default_factory=dict, repr=False)
    _best_cache_total_nodes_count_map: dict[str, int] = field(default_factory=dict, repr=False)
    # Fingerprint of node states; when this changes, invalidate the best-node cache
    _node_state_signature: str | None = field(default=None, repr=False)
    # Memoization for research summary calls, keyed by good-node IDs and include_code flag
    _summary_cache: dict[str, str] = field(default_factory=dict, repr=False)

    def __getstate__(self) -> dict:
        state = self.__dict__.copy()
        # Remove callback to avoid pickling closures/clients
        state.pop("event_callback", None)
        return state

    def __setstate__(self, state: dict) -> None:
        self.__dict__.update(state)
        # Provide a no-op callback after restore; managers can overwrite
        self.event_callback = lambda _event: None

    def __getitem__(self, idx: int) -> Node:
        return self.nodes[idx]

    def __len__(self) -> int:
        """Return the number of nodes in the journal."""
        return len(self.nodes)

    def append(self, node: Node) -> None:
        """Append a new node to the journal."""
        node.step = len(self.nodes)
        self.nodes.append(node)

    def _emit_best_node_reasoning(self, *, node: Node, reasoning: str) -> None:
        """Persist LLM reasoning for the selected best node when telemetry is enabled."""
        if self.run_id is None:
            return
        reasoning_text = reasoning if reasoning.strip() else "No reasoning provided."
        try:
            self.event_callback(
                BestNodeSelectedEvent(
                    run_id=self.run_id,
                    stage=self.stage_name,
                    node_id=str(node.step),
                    reasoning=reasoning_text,
                )
            )
        except Exception:
            logger.exception("Failed to emit BestNodeSelectedEvent for node %s", node.id)

    @property
    def draft_nodes(self) -> list[Node]:
        """Return a list of nodes representing intial coding drafts"""
        return [n for n in self.nodes if n.parent is None]

    @property
    def buggy_nodes(self) -> list[Node]:
        """Return a list of nodes that are considered buggy by the agent."""
        return [n for n in self.nodes if n.is_buggy]

    @property
    def good_nodes(self) -> list[Node]:
        """Return a list of nodes that are not considered buggy by the agent."""
        list_of_nodes = [
            {
                "step": n.step,
                "parent_step": n.parent.step if n.parent else None,
                "id": n.id,
                "is_buggy": n.is_buggy,
                "is_buggy_plots": n.is_buggy_plots,
            }
            for n in self.nodes
        ]
        logger.debug(f"all nodes ID and is_buggy/is_buggy_plots flags: {list_of_nodes}")
        return [n for n in self.nodes if n.is_buggy is False and n.is_buggy_plots is False]

    def get_node_by_id(self, node_id: str) -> Optional[Node]:
        """Get a node by its ID."""
        for node in self.nodes:
            if node.id == node_id:
                return node
        return None

    def get_metric_history(self) -> list[MetricValue]:
        """Return a list of all metric values in the journal."""
        return [n.metric for n in self.nodes if n.metric is not None]

    def _compute_nodes_state_signature(self) -> str:
        """
        Compute a fingerprint of all nodes' states that affect best-node selection.
        Cache invalidation should occur only when this fingerprint changes.
        """
        parts: list[str] = []
        for n in sorted(self.nodes, key=lambda x: x.id):
            metric_val = None
            if n.metric is not None:
                # MetricValue.value may be arbitrary; convert to a stable string
                metric_val = n.metric.value
            parts.append(
                f"{n.id}:{metric_val}:{n.is_buggy}:{n.is_buggy_plots}:{int(n.is_seed_node)}"
            )
        return "|".join(parts)

    def get_best_node(
        self, only_good: bool = True, use_val_metric_only: bool = False
    ) -> None | Node:
        """Return the best solution found so far."""
        total_nodes_count = len(self.nodes)
        buggy_count = len([n for n in self.nodes if n.is_buggy is True])
        plot_buggy_count = len([n for n in self.nodes if n.is_buggy_plots is True])
        logger.debug(
            f"get_best_node: only_good={only_good}, val_only={use_val_metric_only}, "
            f"total_nodes={total_nodes_count}, buggy={buggy_count}, plot_buggy={plot_buggy_count}"
        )

        # Invalidate cache only when node states change
        current_state_sig = self._compute_nodes_state_signature()
        if self._node_state_signature is None:
            self._node_state_signature = current_state_sig
        elif self._node_state_signature != current_state_sig:
            logger.debug("Node state changed; invalidating best-node cache.")
            self._best_cache.clear()
            self._best_cache_time_map.clear()
            self._best_cache_candidate_ids_map.clear()
            self._best_cache_total_nodes_count_map.clear()
            self._node_state_signature = current_state_sig

        if only_good:
            nodes = self.good_nodes
            if not nodes:
                logger.info(
                    "Skipping LLM best-node selection: only_good=True but there are no good candidates "
                    "(all nodes are buggy or plots flagged).",
                )
                return None
        else:
            nodes = self.nodes

        # Build a lightweight signature of the candidate set and selection mode.
        # If unchanged since last call, reuse the cached result and skip LLM work.
        def _selection_signature(nodes_for_sig: list[Node]) -> str:
            parts: list[str] = [
                f"og={only_good}",
                f"val_only={use_val_metric_only}",
                f"model={self.node_selection_model}",
            ]
            for n in sorted(nodes_for_sig, key=lambda x: x.id):
                metric_val = n.metric.value if n.metric is not None else None
                parts.append(f"{n.id}:{metric_val}:{n.is_buggy}:{n.is_buggy_plots}")
            return "|".join(str(p) for p in parts)

        # Exclude seed nodes from candidate set for selection prompt; fall back to all nodes if exclusion empties the set
        seed_node_ids = [n.id[:8] for n in nodes if n.is_seed_node]
        if seed_node_ids:
            logger.debug(f"Found {len(seed_node_ids)} seed node(s) to exclude: {seed_node_ids}")
        candidate_nodes = [n for n in nodes if not n.is_seed_node]
        if not candidate_nodes:
            candidate_nodes = nodes
            logger.debug(
                "No non-seed candidates found, falling back to all nodes (including seed nodes)"
            )
        candidate_ids = sorted([n.id for n in candidate_nodes])
        logger.debug(
            f"Candidate set for best-node selection (count={len(candidate_ids)}): "
            f"{[cid[:8] for cid in candidate_ids]}"
        )

        sig = _selection_signature(candidate_nodes)
        if sig in self._best_cache:
            # If new nodes were added but candidates didn't change (only_good=True),
            # likely new nodes are buggy
            prev_total = self._best_cache_total_nodes_count_map.get(sig)
            prev_candidates = self._best_cache_candidate_ids_map.get(sig)
            if (
                only_good
                and prev_total is not None
                and total_nodes_count > prev_total
                and prev_candidates == candidate_ids
            ):
                logger.debug(
                    "Not checking for new best node: new node(s) detected but ignored "
                    "because they are not good (buggy or plots flagged). "
                    "Using cached best-node result.",
                )
            else:
                node_or_none = self._best_cache[sig]
                cached_id = node_or_none.id if node_or_none is not None else None
                logger.debug(
                    "Skipping LLM best-node selection: candidate signature unchanged. "
                    f"Returning cached result: {cached_id}"
                )
            return self._best_cache[sig]

        if use_val_metric_only:
            nodes_with_metric = [n for n in candidate_nodes if n.metric is not None]
            if not nodes_with_metric:
                # Cache the absence as well to avoid repeated work until state changes
                self._best_cache[sig] = None
                self._best_cache_time_map[sig] = time.time()
                self._best_cache_candidate_ids_map[sig] = candidate_ids
                self._best_cache_total_nodes_count_map[sig] = total_nodes_count
                logger.info("best-node (val_only=True): no candidates with metric. Caching None.")
                return None
            selected_metric_node = max(nodes_with_metric, key=lambda n: cast(MetricValue, n.metric))
            self._best_cache[sig] = selected_metric_node
            self._best_cache_time_map[sig] = time.time()
            self._best_cache_candidate_ids_map[sig] = candidate_ids
            self._best_cache_total_nodes_count_map[sig] = total_nodes_count
            sel_metric_val = (
                selected_metric_node.metric.value if selected_metric_node.metric else None
            )
            self._emit_best_node_reasoning(
                node=selected_metric_node,
                reasoning=f"Metric-only selection (use_val_metric_only=True). Metric value: {sel_metric_val}",
            )
            logger.info(
                f"best-node (val_only=True): selected by metric -> "
                f"{selected_metric_node.id[:8]} (metric={sel_metric_val}). Cached."
            )
            return selected_metric_node

        if len(candidate_nodes) == 1:
            selected_single = candidate_nodes[0]
            self._best_cache[sig] = selected_single
            self._best_cache_time_map[sig] = time.time()
            self._best_cache_candidate_ids_map[sig] = candidate_ids
            self._best_cache_total_nodes_count_map[sig] = total_nodes_count
            self._emit_best_node_reasoning(
                node=selected_single,
                reasoning="Only one candidate available; bypassed LLM selection.",
            )
            logger.debug(
                f"Only one candidate; bypassing LLM selection. "
                f"Selected {selected_single.id[:8]}. Cached.",
            )
            return selected_single

        # Create evaluation prompt for LLM
        prompt = {
            "Introduction": (
                "You are an experienced AI researcher evaluating different implementations "
                "of an experiment to select the best one. You should consider all aspects "
                "including performance metrics, training dynamics, generated plots quality."
            ),
            "Task": (
                "Select the best implementation from the candidates below, considering all available evidence."
                "Avoid relying too heavily on the validation loss alone, because "
                "it may not be directly comparable across different objective functions "
                "or training details. If there are multiple validation losses "
                "(e.g., when evaluating multiple datasets), consider all of them and "
                "select the implementation that performs best overall."
            ),
            "Candidates": "",
        }
        # Gather info about each node
        logger.debug(
            f"Building prompt with {len(candidate_nodes)} candidate nodes: "
            f"{[n.id[:8] for n in candidate_nodes]}"
        )
        for node in candidate_nodes:
            # Always include ID for each candidate, then attach available evidence
            candidate_info = f"ID: {node.id}\n"
            if node.metric:
                candidate_info += f"Metric: {str(node.metric)}\n"
            elif node.analysis:
                candidate_info += f"Training Analysis: {node.analysis}\n"
            elif node.vlm_feedback_summary:
                candidate_info += f"VLM Feedback: {node.vlm_feedback_summary}\n"
            else:
                candidate_info += "N/A\n"
            logger.debug(
                f"Adding candidate to prompt: {node.id[:8]} "
                f"(has_metric={node.metric is not None}, is_seed={node.is_seed_node})",
            )
            prompt["Candidates"] += candidate_info

        # Verify all candidates were included
        candidates_in_prompt = prompt["Candidates"].count("ID: ")
        logger.debug(
            f"Prompt built: {candidates_in_prompt} candidate(s) in prompt text "
            f"(expected {len(candidate_nodes)})"
        )

        try:
            logger.info(
                f"Invoking LLM for best-node selection with {len(candidate_ids)} candidates: "
                f"{[cid[:8] for cid in candidate_ids]}"
            )
            selection = structured_query_with_schema(
                system_message=prompt,
                user_message=None,
                model=self.node_selection_model,
                temperature=self.node_selection_temperature,
                schema_class=NODE_SELECTION_SCHEMA,
            )

            selected_id = str(selection.selected_id)
            selected_node = next(
                (node for node in candidate_nodes if str(node.id) == selected_id), None
            )
            if selected_node:
                logger.info(f"Selected node {selected_node.id} as best implementation")
                logger.info(f"Reasoning: {selection.reasoning}")
                logger.info(
                    f"LLM-selected best node: {selected_node.id[:8]}. "
                    "Emitting events and caching result."
                )

                # Emit user-facing event with the selection reasoning
                self.event_callback(
                    RunLogEvent(
                        message=f"🎯 Selected best implementation: {selected_node.id[:8]}...",
                        level="info",
                    )
                )
                # Send detailed reasoning
                reasoning_text = str(selection.reasoning or "")
                reasoning_preview = (
                    reasoning_text[:500] + "..." if len(reasoning_text) > 500 else reasoning_text
                )
                self.event_callback(
                    RunLogEvent(message=f"💡 Reasoning: {reasoning_preview}", level="info")
                )

                self._emit_best_node_reasoning(node=selected_node, reasoning=reasoning_text)

                # Update cache
                self._best_cache[sig] = selected_node
                self._best_cache_time_map[sig] = time.time()
                self._best_cache_candidate_ids_map[sig] = candidate_ids
                self._best_cache_total_nodes_count_map[sig] = total_nodes_count
                return selected_node
            else:
                logger.warning("Falling back to metric-based selection")
                nodes_with_metric = [n for n in candidate_nodes if n.metric is not None]
                selected_fallback = (
                    max(nodes_with_metric, key=lambda n: cast(MetricValue, n.metric))
                    if nodes_with_metric
                    else None
                )
                if selected_fallback:
                    fallback_reason = (
                        f"LLM selected unknown node id {selected_id}; "
                        "stored best metric candidate instead."
                    )
                    self._emit_best_node_reasoning(
                        node=selected_fallback,
                        reasoning=fallback_reason,
                    )
                self._best_cache[sig] = selected_fallback
                self._best_cache_time_map[sig] = time.time()
                self._best_cache_candidate_ids_map[sig] = candidate_ids
                self._best_cache_total_nodes_count_map[sig] = total_nodes_count
                logger.warning(
                    f"LLM selection id not found among candidates. Falling back to metric. "
                    f"Selected: {selected_fallback.id[:8] if selected_fallback else None}. Cached."
                )
                return selected_fallback

        except Exception as e:
            logger.error(f"Error in LLM selection process: {e}")
            logger.warning("Falling back to metric-based selection")
            nodes_with_metric = [n for n in candidate_nodes if n.metric is not None]
            selected_on_error = (
                max(nodes_with_metric, key=lambda n: cast(MetricValue, n.metric))
                if nodes_with_metric
                else None
            )
            if selected_on_error:
                self._emit_best_node_reasoning(
                    node=selected_on_error,
                    reasoning=f"LLM selection error: {e}. Falling back to best metric.",
                )
            self._best_cache[sig] = selected_on_error
            self._best_cache_time_map[sig] = time.time()
            self._best_cache_candidate_ids_map[sig] = candidate_ids
            self._best_cache_total_nodes_count_map[sig] = total_nodes_count
            logger.error(
                f"Exception during LLM selection. Falling back to metric. "
                f"Selected: {selected_on_error.id[:8] if selected_on_error else None}. Cached.",
                exc_info=True,
            )
            return selected_on_error

    def generate_summary(self, include_code: bool = False) -> str:
        """Generate a summary of the research progress using LLM.

        Includes both successes and failures.
        """
        if not self.nodes:
            return "No experiments conducted yet."

        # Build cache key from the current sets of good and buggy nodes plus include_code flag.
        # We only reuse a cached summary if both lists are unchanged.
        good_ids = sorted([n.id for n in self.good_nodes])
        buggy_ids = sorted([n.id for n in self.buggy_nodes])
        cache_key = (
            f"include_code={include_code}"
            f"|good_ids={','.join(good_ids)}"
            f"|buggy_ids={','.join(buggy_ids)}"
        )
        cached_summary = self._summary_cache.get(cache_key)
        if cached_summary is not None:
            logger.debug(
                "Summary cache HIT: "
                f"include_code={include_code}, "
                f"good_nodes_count={len(good_ids)}, "
                f"buggy_nodes_count={len(buggy_ids)}. "
                "Reusing previous summary (good and buggy sets unchanged)."
            )
            return cached_summary
        logger.debug(
            "Summary cache MISS: "
            f"include_code={include_code}, "
            f"good_nodes_count={len(good_ids)}, "
            f"buggy_nodes_count={len(buggy_ids)}. "
            "Invoking LLM to generate summary."
        )

        prompt = {
            "Introduction": (
                "You are an AI researcher summarizing experimental progress. "
                "Please analyze both successful and failed experiments to provide insights "
                "for future improvements."
            ),
            "Successful Experiments": "",
            "Failed Experiments": "",
        }

        for node in self.good_nodes:
            exp_info = f"Design: {node.plan}\n  "
            exp_info += f"Results: {node.analysis}\n"
            exp_info += f"Metric: {str(node.metric)}\n"
            if include_code:
                exp_info += f"Code: {node.code}\n"
            prompt["Successful Experiments"] += exp_info

        for node in self.buggy_nodes:
            failure_info = f"Design: {node.plan}\n  "
            failure_info += f"Error Analysis: {node.analysis}\n"
            failure_info += (
                f"Error Type: {node.exc_type if node.exc_type is not None else 'Unknown'}\n"
            )
            failure_info += f"Debug Depth: {node.debug_depth}\n"
            if include_code:
                failure_info += f"Code: {node.code}\n"
            prompt["Failed Experiments"] += failure_info

        summary_resp = query(
            system_message=prompt,
            user_message=(
                "Please provide a comprehensive summary of the experimental progress that includes:\n"
                "1. Key patterns of success across working experiments\n"
                "2. Common failure patterns and pitfalls to avoid\n"
                "3. Specific recommendations for future experiments based on both successes and failures"
            ),
            model=self.summary_model,
            temperature=self.summary_temperature,
        )

        summary_text = summary_resp if isinstance(summary_resp, str) else json.dumps(summary_resp)
        # Cache and return
        self._summary_cache[cache_key] = summary_text
        logger.debug(
            "Summary cached. Key reflects include_code and current good and buggy nodes "
            f"(include_code={include_code}, good_nodes_count={len(good_ids)}, "
            f"buggy_nodes_count={len(buggy_ids)})."
        )
        return summary_text

    def to_dict(self) -> dict[str, object]:
        """Convert journal to a JSON-serializable dictionary"""
        return {
            "nodes": [node.to_dict() for node in self.nodes],
            "summary_model": self.summary_model,
            "node_selection_model": self.node_selection_model,
            "summary_temperature": self.summary_temperature,
            "node_selection_temperature": self.node_selection_temperature,
            "stage_name": self.stage_name,
            "run_id": self.run_id,
        }
