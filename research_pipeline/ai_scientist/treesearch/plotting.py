import base64
import logging
import os
from typing import List, Protocol, Tuple

from pydantic import BaseModel, Field

from ai_scientist.llm import query, structured_query_with_schema

from .journal import Node
from .types import PromptType
from .utils.config import Config as AppConfig
from .vlm_function_specs import plot_selection_spec, vlm_feedback_spec

logger = logging.getLogger(__name__)


class SupportsPlottingAgent(Protocol):
    stage_name: str
    cfg: AppConfig

    def plan_and_code_query(self, *, prompt: PromptType, retries: int) -> Tuple[str, str]:
        pass


def generate_plotting_code(
    *,
    agent: SupportsPlottingAgent,
    node: Node,
    plot_code_from_prev_stage: str | None,
) -> str:
    prompt_guideline: list[str] = [
        "AVAILABLE DATA: ",
        "Experiment Data: experiment_data.npy",
    ]
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
        "Use the following experiment code to infer the data to plot: " + node.code,
        "Example to extract data from experiment_data: experiment_data['dataset_name_1']['metrics']['train']",
    ]
    prompt_guideline += [
        "Example data loading and plot saving code: ",
        """
                try:
                    experiment_data = np.load(os.path.join(working_dir, 'experiment_data.npy'), allow_pickle=True).item()
                except Exception as e:
                    print(f'Error loading experiment data: {e}')

                try:
                    # First plot
                    plt.figure()
                    # ... plotting code ...
                    plt.savefig('working_dir/[plot_name_1].png')
                    plt.close()
                except Exception as e:
                    print(f"Error creating plot1: {e}")
                    plt.close()  # Always close figure even if error occurs

                try:
                    # Second plot
                    plt.figure()
                    # ... plotting code ...
                    plt.savefig('working_dir/[plot_name_2].png')
                    plt.close()
                except Exception as e:
                    print(f"Error creating plot2: {e}")
                    plt.close()
        """,
    ]

    plotting_prompt: PromptType = {
        "Instructions": {},
    }
    plotting_instructions: dict[str, str | list[str]] = {}
    plotting_instructions |= {
        "Plotting code guideline": prompt_guideline,
    }
    plotting_prompt["Instructions"] = plotting_instructions

    # If provided, allow seeding from a prior stage's plotting code (currently used for Stage 4).
    if agent.stage_name.startswith("4_") and plot_code_from_prev_stage:
        prompt_guideline.extend(
            [
                "IMPORTANT: This is an ablation study. Use the following base plotting code as a starting point:",
                "Base plotting code: \n" + plot_code_from_prev_stage,
                "Modify the base plotting code to:",
                "1. Keep the same numpy data structure and plotting style",
                "2. Add comparison plots between ablation and baseline results",
                "3. Add ablation-specific visualizations if needed",
                "4. Include clear labels indicating which plots are from ablation vs baseline",
                "5. Use consistent naming conventions for saved files",
            ]
        )

    plan, code = agent.plan_and_code_query(prompt=plotting_prompt, retries=3)
    logger.debug("----- LLM code start (stage3 plotting) -----")
    logger.debug(code)
    logger.debug("----- LLM code end (stage3 plotting) -----")
    if not code.strip().startswith("import"):
        code = "import matplotlib.pyplot as plt\nimport numpy as np\n\n" + code
    node.plot_code = code
    node.plot_plan = plan
    return code


def _encode_image_to_base64(image_path: str) -> str | None:
    try:
        with open(image_path, "rb") as image_file:
            return base64.b64encode(image_file.read()).decode("utf-8")
    except Exception:
        return None


def _infer_image_mime_type(image_path: str) -> str:
    p = image_path.lower()
    if p.endswith(".png"):
        return "image/png"
    if p.endswith(".jpg") or p.endswith(".jpeg"):
        return "image/jpeg"
    # Default to PNG if unknown
    return "image/png"


class DatasetsSuccessfullyTestedResult(BaseModel):
    reasoning: str = Field(
        description=(
            "A brief explanation of which datasets are considered successfully tested and why, "
            "based on the plot analyses and VLM feedback."
        ),
    )
    datasets_successfully_tested: List[str] = Field(
        description=(
            "List of dataset names that are successfully tested. "
            "Return an empty list if no datasets are successfully tested."
        ),
    )


def determine_datasets_successfully_tested(
    *, agent: SupportsPlottingAgent, node: Node
) -> List[str]:
    plot_analyses = ""
    plot_analyses_list = node.plot_analyses
    for i, plot_analysis in enumerate(plot_analyses_list):
        plot_analyses += f"plot {i + 1}: {plot_analysis['analysis']}\n"

    determine_prompt: dict[str, object] = {
        "Introduction": (
            "You are an AI researcher analyzing experiment results. "
            "Based on the plot analyses and feedback, determine which datasets are successfully tested. "
            "Provide your reasoning and list the dataset names that are successfully executed, "
            "or indicate that none are successfully executed."
        ),
        "Plot analyses": plot_analyses,
        "VLM feedback summary": node.vlm_feedback_summary,
        "Original plotting code": node.plot_code or "",
    }

    retry_count = 0
    retry_limit = 5
    while retry_count < retry_limit:
        try:
            result = structured_query_with_schema(
                system_message=determine_prompt,
                model=agent.cfg.agent.feedback.model,
                temperature=agent.cfg.agent.feedback.temp,
                schema_class=DatasetsSuccessfullyTestedResult,
            )
        except Exception:
            retry_count += 1
            continue

        datasets_raw = result.datasets_successfully_tested
        datasets = [ds.strip() for ds in datasets_raw if isinstance(ds, str) and ds.strip()]
        if datasets:
            return datasets
        retry_count += 1

    return [""]


def analyze_plots_with_vlm(*, agent: SupportsPlottingAgent, node: Node) -> None:
    logger.debug(f"analyze_plots_with_vlm called for node {node.id}")
    logger.debug(f"node.plots count: {len(node.plots) if node.plots else 0}")
    logger.debug(f"node.plot_paths count: {len(node.plot_paths) if node.plot_paths else 0}")
    logger.debug(f"node.plots: {node.plots[:3] if node.plots else 'None'}...")
    logger.debug(f"node.plot_paths: {node.plot_paths[:3] if node.plot_paths else 'None'}...")

    if not node.plot_paths:
        warning_msg = (
            "=" * 100
            + "\n"
            + "!" * 100
            + "\n"
            + "!" * 100
            + "\n"
            + "!" * 100
            + "\n"
            + "⚠️  ⚠️  ⚠️  BIG WARNING: plot_paths is EMPTY but plots list has items! ⚠️  ⚠️  ⚠️\n"
            + f"⚠️  Node ID: {node.id}\n"
            + f"⚠️  plots count: {len(node.plots) if node.plots else 0}\n"
            + f"⚠️  plot_paths count: {len(node.plot_paths) if node.plot_paths else 0}\n"
            + "⚠️  This means VLM analysis cannot proceed (no actual plot files to analyze)\n"
            + "⚠️  Setting is_buggy_plots = False (assuming plots are fine, but unverified)\n"
            + "⚠️  This can happen if:\n"
            + "⚠️    1. Exception occurred during file moving (plots populated but plot_paths not)\n"
            + "⚠️    2. Plots were populated from a previous attempt/retry\n"
            + "⚠️    3. plot_paths list was cleared/reset somewhere\n"
            + "!" * 100
            + "\n"
            + "!" * 100
            + "\n"
            + "!" * 100
            + "\n"
            + "=" * 100
        )
        logger.warning(warning_msg)
        # Set is_buggy_plots to False to allow the node to be considered "good"
        # but mark that we couldn't verify the plots
        node.is_buggy_plots = False
        return
    if len(node.plot_paths) <= 10:
        selected_plots = node.plot_paths
    else:
        prompt_select_plots = {
            "Introduction": (
                "You are an experienced AI researcher analyzing experimental results. "
                "You have been provided with plots from a machine learning experiment. "
                "Please select 10 most relevant plots to analyze. "
                "For similar plots (e.g. generated samples at each epoch), select only at most 5 plots at a suitable interval of epochs."
                "Format your response as a list of plot paths, where each plot path includes the full path to the plot file."
            ),
            "Plot paths": node.plot_paths,
        }
        try:
            response_select_plots = query(
                system_message=prompt_select_plots,
                user_message=None,
                func_spec=plot_selection_spec,
                model=agent.cfg.agent.feedback.model,
                temperature=agent.cfg.agent.feedback.temp,
            )
            selected_plots = node.plot_paths[:10]
            if isinstance(response_select_plots, dict):
                candidate = response_select_plots.get("selected_plots", [])
                valid_plots: list[str] = []
                if isinstance(candidate, list):
                    for plot_path in candidate:
                        if (
                            isinstance(plot_path, str)
                            and os.path.exists(plot_path)
                            and plot_path.lower().endswith((".png", ".jpg", ".jpeg"))
                        ):
                            valid_plots.append(plot_path)
                if valid_plots:
                    selected_plots = valid_plots
        except Exception:
            selected_plots = node.plot_paths[:10]

    # Log which plots will be sent to the VLM
    try:
        logger.debug(f"Selected {len(selected_plots)} plot(s) for VLM analysis: {selected_plots}")
        logger.debug(
            f"VLM feedback model: {agent.cfg.agent.vlm_feedback.model}, "
            f"temperature: {agent.cfg.agent.vlm_feedback.temp}"
        )
    except Exception:
        logger.debug("Failed to log selected plots for VLM analysis (non-fatal).")

    text_part = {
        "type": "text",
        "text": (
            "You are an experienced AI researcher analyzing experimental results. "
            "You have been provided with plots from a machine learning experiment. "
            f"This experiment is based on the following research idea: {agent.stage_name}"
            "Please analyze these plots and provide detailed insights about the results. "
            "If you don't receive any plots, say 'No plots received'. "
            "Never make up plot analysis. "
            "Please return the analyzes with strict order of uploaded images, but DO NOT include any word "
            "like 'the first plot'."
        ),
    }

    image_parts: list[dict] = []
    for plot_path in selected_plots:
        encoded = _encode_image_to_base64(plot_path)
        if not encoded:
            logger.warning("Skipping plot for VLM (failed to base64 encode): %s", plot_path)
            continue
        mime = _infer_image_mime_type(plot_path)
        image_parts.append(
            {
                "type": "image_url",
                "image_url": {
                    "url": f"data:{mime};base64,{encoded}",
                    "detail": "low",
                },
            }
        )

    user_message = [text_part] + image_parts

    response = query(
        system_message=None,
        user_message=user_message,
        func_spec=vlm_feedback_spec,
        model=agent.cfg.agent.vlm_feedback.model,
        temperature=agent.cfg.agent.vlm_feedback.temp,
    )
    # Log raw response for debugging/traceability
    logger.debug(f"VLM plot analysis raw response type: {type(response)}")
    try:
        logger.debug(f"VLM plot analysis raw response: {response}")
    except Exception:
        logger.debug("VLM plot analysis raw response: <unprintable>")

    if not isinstance(response, dict):
        warning_msg = (
            "=" * 100
            + "\n"
            + "!" * 100
            + "\n"
            + "!" * 100
            + "\n"
            + "!" * 100
            + "\n"
            + "⚠️  ⚠️  ⚠️  BIG WARNING: VLM analysis response is not a dict! ⚠️  ⚠️  ⚠️\n"
            + f"⚠️  Node ID: {node.id}\n"
            + f"⚠️  Response type: {type(response)}\n"
            + "⚠️  This means VLM analysis failed or returned unexpected format\n"
            + "⚠️  Setting is_buggy_plots = False (assuming plots are fine, but unverified)\n"
            + "⚠️  Execution will continue, but plots were not validated by VLM\n"
            + "!" * 100
            + "\n"
            + "!" * 100
            + "\n"
            + "!" * 100
            + "\n"
            + "=" * 100
        )
        logger.warning(warning_msg)
        # Set is_buggy_plots to False to allow the node to be considered "good"
        # but mark that we couldn't verify the plots via VLM
        node.is_buggy_plots = False
        return
    valid_plots_received = bool(response.get("valid_plots_received"))
    node.is_buggy_plots = not valid_plots_received
    # Sanitize plot_analyses to ensure a list of dicts with at least {"analysis": str, "plot_path": str|None}
    plot_analyses_val = response.get("plot_analyses")
    if isinstance(plot_analyses_val, list):
        sanitized: list[dict] = []
        had_nondict = False
        for index, analysis in enumerate(plot_analyses_val):
            if isinstance(analysis, dict):
                sanitized_item = dict(analysis)
            else:
                had_nondict = True
                sanitized_item = {"analysis": str(analysis)}
            if index < len(node.plot_paths) and "plot_path" not in sanitized_item:
                sanitized_item["plot_path"] = node.plot_paths[index]
            sanitized.append(sanitized_item)
        if had_nondict:
            logger.debug(
                "Coerced non-dict entries in plot_analyses into dicts with 'analysis' text."
            )
        node.plot_analyses = sanitized

    vlm_summary_val = response.get("vlm_feedback_summary")
    if isinstance(vlm_summary_val, list):
        node.vlm_feedback_summary = [str(x) for x in vlm_summary_val]
    elif isinstance(vlm_summary_val, str):
        node.vlm_feedback_summary = [vlm_summary_val]
    node.datasets_successfully_tested = determine_datasets_successfully_tested(
        agent=agent, node=node
    )
