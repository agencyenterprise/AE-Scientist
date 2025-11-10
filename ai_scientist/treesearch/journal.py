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
from rich import print

from ai_scientist.llm.query import FunctionSpec, query

from .events import BaseEvent, RunLogEvent
from .interpreter import ExecutionResult
from .utils.metric import MetricValue, WorstMetricValue
from .utils.response import trim_long_string

logger = logging.getLogger(__name__)

node_selection_spec = FunctionSpec(
    name="select_best_implementation",
    description="Select the best implementation based on comprehensive analysis",
    json_schema={
        "type": "object",
        "properties": {
            "selected_id": {
                "type": "string",
                "description": "ID of the selected best implementation",
            },
            "reasoning": {
                "type": "string",
                "description": "Detailed explanation of why this implementation was chosen",
            },
        },
        "required": ["selected_id", "reasoning"],
    },
)


@dataclass(eq=False)
class Node(DataClassJsonMixin):
    """A single node in the solution tree. Contains code, execution results, and evaluation information."""

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
        # Ensure id is included in the state
        if hasattr(self, "id"):
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

    def to_dict(self, encode_json: bool = False) -> dict[str, object]:  # type: ignore[override]
        """Convert node to dictionary for serialization"""
        return {
            "code": self.code,
            "plan": self.plan,
            "overall_plan": (self.overall_plan if hasattr(self, "overall_plan") else None),
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
                "name": self.metric.name if self.metric and hasattr(self.metric, "name") else None,
                "description": (
                    self.metric.description
                    if self.metric and hasattr(self.metric, "description")
                    else None
                ),
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
class InteractiveSession(DataClassJsonMixin):
    """
    A collection of nodes for an interaction session
    (when the agent interacts with a Jupyter notebook-like interface).
    """

    nodes: list[Node] = field(default_factory=list)
    completed: bool = False

    def append(self, node: Node) -> None:
        node.step = len(self.nodes)
        self.nodes.append(node)

    def generate_nb_trace(self, include_prompt: bool, comment_headers: bool = True) -> str:
        """Generate a trace of the interactive session in IPython format."""
        trace = []
        header_prefix = "## " if comment_headers else ""
        for n in self.nodes:
            if n.step is not None:
                trace.append(f"\n{header_prefix}In [{n.step + 1}]:\n")
                trace.append(n.code)
                trace.append(f"\n{header_prefix}Out [{n.step + 1}]:\n")
                trace.append(n.term_out)

        if include_prompt and self.nodes:
            last_step_index = (self.nodes[-1].step or 0) + 2
            trace.append(f"\n{header_prefix}In [{last_step_index}]:\n")

        return "\n".join(trace).strip()


@dataclass
class Journal:
    """A collection of nodes representing the solution tree."""

    summary_model: str
    node_selection_model: str
    event_callback: Callable[[BaseEvent], None] = field(repr=False)
    nodes: list[Node] = field(default_factory=list)

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
            [
                n.step,
                n.parent.step if n.parent else None,
                n.id,
                n.is_buggy,
                n.is_buggy_plots,
            ]
            for n in self.nodes
        ]
        print(f"[purple]all nodes ID and is_buggy/is_buggy_plots flags: {list_of_nodes}[/purple]")
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

    def get_best_node(
        self, only_good: bool = True, use_val_metric_only: bool = False
    ) -> None | Node:
        """Return the best solution found so far."""
        if only_good:
            nodes = self.good_nodes
            if not nodes:
                return None
        else:
            nodes = self.nodes

        if use_val_metric_only:
            nodes_with_metric = [n for n in nodes if n.metric is not None]
            if not nodes_with_metric:
                return None
            return max(nodes_with_metric, key=lambda n: cast(MetricValue, n.metric))

        if len(nodes) == 1:
            return nodes[0]

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
                "it may not be directly comparable across different objective functions or training details. "
                "If there are multiple validation losses (e.g., when evaluating multiple datasets), "
                "consider all of them and select the implementation that performs best overall."
            ),
            "Candidates": "",
        }
        # Gather info about each node
        for node in nodes:
            if not node.is_seed_node:
                candidate_info = (
                    f"ID: {node.id}\n" f"Metric: {str(node.metric)}\n"
                    if node.metric
                    else (
                        "N/A\n" f"Training Analysis: {node.analysis}\n"
                        if hasattr(node, "analysis")
                        else (
                            "N/A\n" f"VLM Feedback: {node.vlm_feedback_summary}\n"
                            if hasattr(node, "vlm_feedback_summary")
                            else "N/A\n"
                        )
                    )
                )
                prompt["Candidates"] += candidate_info

        try:
            selection = query(
                system_message=prompt,
                user_message=None,
                func_spec=node_selection_spec,
                model=self.node_selection_model,
                temperature=1.0,  # gpt-5 family requires temperature=1.0
            )

            # Find and return the selected node
            if not isinstance(selection, dict):
                logger.warning("Falling back to metric-based selection")
                nodes_with_metric = [n for n in nodes if n.metric is not None]
                return (
                    max(nodes_with_metric, key=lambda n: cast(MetricValue, n.metric))
                    if nodes_with_metric
                    else None
                )

            selected_id = str(selection.get("selected_id", ""))
            selected_node = next((node for node in nodes if str(node.id) == selected_id), None)
            if selected_node:
                logger.info(f"Selected node {selected_node.id} as best implementation")
                logger.info(f"Reasoning: {selection.get('reasoning', '')}")

                # Emit user-facing event with the selection reasoning
                self.event_callback(
                    RunLogEvent(
                        message=f"🎯 Selected best implementation: {selected_node.id[:8]}...",
                        level="info",
                    )
                )
                # Send detailed reasoning
                reasoning_text = str(selection.get("reasoning", ""))
                reasoning_preview = (
                    reasoning_text[:500] + "..." if len(reasoning_text) > 500 else reasoning_text
                )
                self.event_callback(
                    RunLogEvent(message=f"💡 Reasoning: {reasoning_preview}", level="info")
                )

                return selected_node
            else:
                logger.warning("Falling back to metric-based selection")
                nodes_with_metric = [n for n in nodes if n.metric is not None]
                return (
                    max(nodes_with_metric, key=lambda n: cast(MetricValue, n.metric))
                    if nodes_with_metric
                    else None
                )

        except Exception as e:
            logger.error(f"Error in LLM selection process: {e}")
            logger.warning("Falling back to metric-based selection")
            nodes_with_metric = [n for n in nodes if n.metric is not None]
            return (
                max(nodes_with_metric, key=lambda n: cast(MetricValue, n.metric))
                if nodes_with_metric
                else None
            )

    def generate_summary(self, include_code: bool = False) -> str:
        """Generate a summary of the research progress using LLM, including both successes and failures."""
        if not self.nodes:
            return "No experiments conducted yet."

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
                f"Error Type: {node.exc_type if hasattr(node, 'exc_type') else 'Unknown'}\n"
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
            temperature=0.3,
        )

        return summary_resp if isinstance(summary_resp, str) else json.dumps(summary_resp)

    def to_dict(self) -> dict[str, list[dict[str, object]] | str]:
        """Convert journal to a JSON-serializable dictionary"""
        return {
            "nodes": [node.to_dict() for node in self.nodes],
            "summary_model": self.summary_model,
            "node_selection_model": self.node_selection_model,
        }
