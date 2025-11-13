"""
Helpers for multi-seed evaluation and plot aggregation.

Responsibilities:
- Build aggregation nodes that summarize multi-seed runs
- Prompt the LLM to generate aggregation plotting code using seed results
"""

from pathlib import Path
from typing import List, Protocol, Tuple

from .interpreter import Interpreter
from .journal import Node
from .types import PromptType
from .utils.config import Config as AppConfig


class SupportsSeedAgent(Protocol):
    def plan_and_code_query(self, *, prompt: PromptType, retries: int = 3) -> Tuple[str, str]:
        pass

    @property
    def cfg(
        self,
    ) -> AppConfig:  # needs .workspace_dir, .exec (timeout, format_tb_ipython, agent_file_name)
        ...


def generate_seed_eval_aggregation_node(*, node: Node, agg_plotting_code: str) -> Node:
    # Create a special node that contains only plotting aggregation code
    return Node(
        plan="Aggregate results from multiple seeds",
        code="# plotting aggregation code",
        plot_code=agg_plotting_code,
        parent=node,
        is_seed_node=True,
        is_seed_agg_node=True,
    )


def aggregate_seed_eval_results(
    *, agent: SupportsSeedAgent, seed_nodes: List[Node], parent_node: Node
) -> str:
    # Build a guidance list the LLM should follow when writing aggregation code
    prompt_guideline: list[str] = []
    prompt_guideline += [
        "REQUIREMENTS: ",
        "The code should start with:",
        "  import matplotlib.pyplot as plt",
        "  import numpy as np",
        "  import os",
        "  working_dir = os.path.join(os.getcwd(), 'working')",
        "Create standard visualizations of experiment results",
        "Save all plots to working_dir",
        "Include training/validation curves if available",
        "ONLY plot data that exists in experiment_data.npy - DO NOT make up or simulate any values",
        "Use basic matplotlib without custom styles",
        "Each plot should be in a separate try-except block",
        "Always close figures after saving",
        "Always include a title for each plot, and be sure to use clear subtitles—such as 'Left: Ground Truth, Right: Generated Samples'—while also specifying the type of dataset being used.",
        "Make sure to use descriptive names for figures when saving e.g. always include the dataset name and the type of plot in the name",
        "When there are many similar figures to plot (e.g. generated samples at each epoch), make sure to plot only at a suitable interval of epochs so that you only plot at most 5 figures.",
        "Example to extract data from experiment_data: experiment_data['dataset_name_1']['metrics']['train']",
        "Make sure to add legend for standard error bars and means if applicable",
    ]
    plotting_prompt: PromptType = {
        "Introduction": (
            "You are an expert in data visualization and plotting. "
            "You are given a set of evaluation results and the code that was used to plot them. "
            "Your task is to write a new plotting code that aggregate the results "
            "e.g. for example, by adding mean values and standard error bars to the plots."
        ),
        "Instructions": {},
    }
    plotting_instructions: dict[str, str | list[str]] = {}
    # Enforce response format and plug in reference plotting snippets from seed nodes
    plotting_instructions |= {
        "Response format": (
            "Your response should be a brief outline/sketch of your proposed solution in natural language (7-10 sentences), "
            "followed by a single markdown code block (wrapped in ```) which implements this solution and prints out the evaluation metric(s) if applicable. "
            "There should be no additional headings or text in your response. Just natural language text followed by a newline and then the markdown code block. "
        )
    }
    plotting_instructions |= {
        "Plotting code guideline": prompt_guideline,
    }
    plotting_instructions |= {
        "Plotting code reference": (
            "plotting code 1:\n" + (seed_nodes[0].plot_code or "") + "\n\n"
            "plotting code 2:\n" + (seed_nodes[1].plot_code or "") + "\n\n"
            "plotting code 3:\n" + (seed_nodes[2].plot_code or "") + "\n\n"
        ),
        "Experiment Data Path": (
            f"{seed_nodes[0].exp_results_dir or ''}/experiment_data.npy\n"
            f"{seed_nodes[1].exp_results_dir or ''}/experiment_data.npy\n"
            f"{seed_nodes[2].exp_results_dir or ''}/experiment_data.npy\n"
        ),
    }
    plotting_prompt["Instructions"] = plotting_instructions
    # Attach instructions and call the LLM to produce aggregation code
    plan, code = agent.plan_and_code_query(prompt=plotting_prompt)
    return code


def run_plot_aggregation(*, agent: SupportsSeedAgent, node: Node, seed_nodes: List[Node]) -> Node:
    if not seed_nodes:
        return node
    try:
        # Create aggregation plotting code
        agg_plotting_code = aggregate_seed_eval_results(
            agent=agent, seed_nodes=seed_nodes, parent_node=node
        )

        # Create a special aggregation node
        agg_node = generate_seed_eval_aggregation_node(
            node=node, agg_plotting_code=agg_plotting_code
        )
        agg_node.parent = node

        # Execute aggregation plotting code
        process_interpreter = Interpreter(
            working_dir=agent.cfg.workspace_dir,
            timeout=agent.cfg.exec.timeout,
            format_tb_ipython=agent.cfg.exec.format_tb_ipython,
            agent_file_name=agent.cfg.exec.agent_file_name,
            env_vars=None,
        )
        try:
            working_dir = process_interpreter.working_dir
            _ = process_interpreter.run(agg_plotting_code, True)
            process_interpreter.cleanup_session()
            # Save aggregated plots
            plots_dir = Path(working_dir) / "working"
            if plots_dir.exists():
                base_dir = Path(agent.cfg.workspace_dir).parent
                run_name = Path(agent.cfg.workspace_dir).name
                exp_results_dir = (
                    base_dir
                    / "logs"
                    / run_name
                    / "experiment_results"
                    / f"seed_aggregation_{agg_node.id}"
                )
                exp_results_dir.mkdir(parents=True, exist_ok=True)

                # Save plotting code
                with open(exp_results_dir / "aggregation_plotting_code.py", "w") as f:
                    f.write(agg_plotting_code)

                # Move generated plots
                for plot_file in plots_dir.glob("*.png"):
                    final_path = exp_results_dir / plot_file.name
                    plot_file.resolve().rename(final_path)
                    web_path = f"../../logs/{Path(agent.cfg.workspace_dir).name}/experiment_results/seed_aggregation_{agg_node.id}/{plot_file.name}"
                    agg_node.plots.append(web_path)
                    agg_node.plot_paths.append(str(final_path.absolute()))

            agg_node.is_buggy = False
            agg_node.exp_results_dir = str(exp_results_dir)
            return agg_node
        finally:
            if process_interpreter:
                process_interpreter.cleanup_session()
    except Exception:
        return node
