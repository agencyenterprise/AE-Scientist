import copy
import logging
import os
import time
import uuid
from dataclasses import dataclass, field
from dataclasses import fields as dataclass_fields
from pathlib import Path
from typing import Any, Callable, List, Literal, Optional, cast

from pydantic import BaseModel

from ai_scientist.llm import structured_query_with_schema

from .events import BaseEvent, BestNodeSelectedEvent, RunLogEvent
from .utils.metric import MetricValue, WorstMetricValue
from .utils.response import trim_long_string

logger = logging.getLogger(__name__)


class DataClassJsonMixin:
    """Local stub to avoid a hard dependency on `dataclasses_json` in codex-only mode."""


class NodeSelectionResponse(BaseModel):
    # Retained for backward compatibility with stored journals; not used in codex-only mode.
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
    best_node_reasoning: str | None = field(default=None, kw_only=True)

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

    # ---- VLM feedback ----
    vlm_feedback: dict[str, Any] | None = field(default=None, kw_only=True, repr=False)

    # ---- seed node ----
    is_seed_node: bool = field(default=False, kw_only=True)
    is_seed_agg_node: bool = field(default=False, kw_only=True)

    # ---- agent ----
    agent: Any | None = field(default=None, kw_only=True, repr=False)

    # ---- user feedback ----
    is_user_feedback: bool = field(default=False, kw_only=True)
    user_feedback_payload: str | None = field(default=None, kw_only=True)
    user_feedback_pending: bool = field(default=False, kw_only=True)

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
        result = object.__new__(cls)
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

    def absorb_exec_result(self, exec_result: object) -> None:
        """Absorb the result of executing the code from this node."""
        # Best-effort attribute extraction to support older callers.
        self._term_out = getattr(exec_result, "term_out", None)
        self.exec_time = getattr(exec_result, "exec_time", None)
        self.exc_type = getattr(exec_result, "exc_type", None)
        self.exc_info = getattr(exec_result, "exc_info", None)
        self.exc_stack = getattr(exec_result, "exc_stack", None)

    def absorb_plot_exec_result(self, plot_exec_result: object) -> None:
        """Absorb the result of executing the plotting code from this node."""
        self.plot_term_out = getattr(plot_exec_result, "term_out", None)
        self.plot_exec_time = getattr(plot_exec_result, "exec_time", None)
        self.plot_exc_type = getattr(plot_exec_result, "exc_type", None)
        self.plot_exc_info = getattr(plot_exec_result, "exc_info", None)
        self.plot_exc_stack = getattr(plot_exec_result, "exc_stack", None)

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

    def to_dict(self) -> dict[str, object]:
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
            "is_user_feedback": self.is_user_feedback,
            "user_feedback_payload": self.user_feedback_payload,
            "user_feedback_pending": self.user_feedback_pending,
        }

    @classmethod
    def from_dict(cls, data: dict, journal: Optional["Journal"] = None) -> "Node":
        """Create a Node from a dictionary, optionally linking to journal for relationships"""
        # Work on a copy: callers may reuse the original dict (e.g. for logging).
        data = dict(data)
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
                # Handle older format or None
                data["metric"] = (
                    WorstMetricValue() if data.get("is_buggy") else MetricValue(metric_data)
                )

        # Create node instance (ignore unknown keys)
        allowed_keys = {f.name for f in dataclass_fields(cls)}
        filtered = {k: v for k, v in data.items() if k in allowed_keys}
        node = cls(**filtered)

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

    def emit_best_node_reasoning(self, *, node: Node, reasoning: str) -> None:
        """Public helper to emit persisted best-node reasoning events."""
        self._emit_best_node_reasoning(node=node, reasoning=reasoning)

    def _emit_best_node_reasoning(self, *, node: Node, reasoning: str) -> None:
        """Persist LLM reasoning for the selected best node when telemetry is enabled."""
        if self.run_id is None:
            return
        reasoning_text = reasoning if reasoning.strip() else "No reasoning provided."
        node.best_node_reasoning = reasoning_text
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

        # Create evaluation prompt for LLM (ported from origin/main)
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
        logger.debug(
            "Building prompt with %s candidate nodes: %s",
            len(candidate_nodes),
            [n.id[:8] for n in candidate_nodes],
        )
        for node in candidate_nodes:
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
                "Adding candidate to prompt: %s (has_metric=%s is_seed=%s)",
                node.id[:8],
                node.metric is not None,
                node.is_seed_node,
            )
            prompt["Candidates"] += candidate_info

        try:
            logger.info(
                "Invoking LLM for best-node selection with %s candidates: %s",
                len(candidate_ids),
                [cid[:8] for cid in candidate_ids],
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
            if selected_node is not None:
                reasoning_text = str(selection.reasoning or "")
                self.event_callback(
                    RunLogEvent(
                        message=f"🎯 Selected best implementation: {selected_node.id[:8]}...",
                        level="info",
                    )
                )
                preview = (
                    reasoning_text[:500] + "..." if len(reasoning_text) > 500 else reasoning_text
                )
                if preview.strip():
                    self.event_callback(
                        RunLogEvent(message=f"💡 Reasoning: {preview}", level="info")
                    )
                self._emit_best_node_reasoning(node=selected_node, reasoning=reasoning_text)

                self._best_cache[sig] = selected_node
                self._best_cache_time_map[sig] = time.time()
                self._best_cache_candidate_ids_map[sig] = candidate_ids
                self._best_cache_total_nodes_count_map[sig] = total_nodes_count
                return selected_node

            # LLM returned an unknown ID; fall back to metric-based best (if available)
            logger.warning(
                "LLM returned unknown selected_id=%s; falling back to metric-based selection",
                selected_id,
            )
            nodes_with_metric = [n for n in candidate_nodes if n.metric is not None]
            selected_fallback = (
                max(nodes_with_metric, key=lambda n: cast(MetricValue, n.metric))
                if nodes_with_metric
                else None
            )
            if selected_fallback is not None:
                self._emit_best_node_reasoning(
                    node=selected_fallback,
                    reasoning=(
                        f"LLM selected unknown node id {selected_id}; "
                        "stored best metric candidate instead."
                    ),
                )
            self._best_cache[sig] = selected_fallback
            self._best_cache_time_map[sig] = time.time()
            self._best_cache_candidate_ids_map[sig] = candidate_ids
            self._best_cache_total_nodes_count_map[sig] = total_nodes_count
            return selected_fallback

        except Exception as exc:
            logger.warning(
                "Error in LLM best-node selection; falling back to metric-based selection (%s)", exc
            )
            nodes_with_metric = [n for n in candidate_nodes if n.metric is not None]
            selected_on_error = (
                max(nodes_with_metric, key=lambda n: cast(MetricValue, n.metric))
                if nodes_with_metric
                else None
            )
            if selected_on_error is not None:
                self._emit_best_node_reasoning(
                    node=selected_on_error,
                    reasoning=f"LLM selection error: {exc}. Falling back to best metric.",
                )
            self._best_cache[sig] = selected_on_error
            self._best_cache_time_map[sig] = time.time()
            self._best_cache_candidate_ids_map[sig] = candidate_ids
            self._best_cache_total_nodes_count_map[sig] = total_nodes_count
            return selected_on_error

    def generate_summary(self, include_code: bool = False) -> str:
        """Generate a deterministic summary of progress (codex-only mode)."""
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
            "Building deterministic summary from current journal state."
        )

        best = self.get_best_node(only_good=True, use_val_metric_only=True)
        best_id = best.id[:8] if best is not None else "N/A"
        best_metric = str(best.metric) if best is not None and best.metric is not None else "N/A"
        lines: list[str] = []
        lines.append(f"Stage: {self.stage_name}")
        lines.append(f"Total nodes: {len(self.nodes)}")
        lines.append(f"Good nodes: {len(self.good_nodes)}")
        lines.append(f"Buggy nodes: {len(self.buggy_nodes)}")
        lines.append(f"Best node: {best_id} (metric: {best_metric})")

        if self.good_nodes:
            recent_good = sorted(self.good_nodes, key=lambda n: n.ctime, reverse=True)[:3]
            lines.append("Recent successful experiments:")
            for n in recent_good:
                metric_str = str(n.metric) if n.metric is not None else "N/A"
                plan_preview = (n.plan or "").strip().replace("\n", " ")[:160]
                lines.append(f"- {n.id[:8]} metric={metric_str} plan={plan_preview}")
                if include_code and n.code:
                    lines.append(f"  code_chars={len(n.code)}")

        if self.buggy_nodes:
            recent_bad = sorted(self.buggy_nodes, key=lambda n: n.ctime, reverse=True)[:3]
            lines.append("Recent failures:")
            for n in recent_bad:
                exc = n.exc_type or "Unknown"
                analysis_preview = (n.analysis or "").strip().replace("\n", " ")[:160]
                lines.append(f"- {n.id[:8]} exc_type={exc} analysis={analysis_preview}")
                if n.user_feedback_payload:
                    fb_preview = n.user_feedback_payload.strip().replace("\n", " ")[:160]
                    lines.append(f"  user_feedback={fb_preview}")

        summary_text = "\n".join(lines).strip()
        logger.debug("Summary text (include_code=%s):\n%s", include_code, summary_text)
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
