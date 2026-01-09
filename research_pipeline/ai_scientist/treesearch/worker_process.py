import json
import logging
import multiprocessing
import os
import pickle
import subprocess
import sys
import traceback
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from typing import Callable, Literal, TypedDict

import humanize  # pyright: ignore[reportMissingImports]

from ai_scientist.llm import structured_query_with_schema

from . import execution_registry
from .codex_cli_runner import CodexCliRunner
from .datasets_context import (
    S3DatasetEntry,
    build_s3_download_snippet,
    build_s3_upload_snippet,
    get_available_datasets,
    get_research_pipeline_env_file,
)
from .events import BaseEvent, RunCompletedEvent, RunLogEvent, RunningCodeEvent
from .gpu_manager import GPUSpec, get_gpu_specs
from .journal import Node
from .node_result_contract import (
    NodeResultContractContext,
    codex_node_result_contract_prompt_lines_common,
    count_working_pngs,
)
from .seed_aggregation import (
    codex_node_result_contract_prompt_lines as codex_seed_agg_contract_lines,
)
from .seed_aggregation import codex_seed_aggregation_instructions_lines
from .stage_identifiers import StageIdentifier
from .stages.node_result_contracts import (
    codex_node_result_contract_prompt_lines_for_stage,
    validate_node_result_contract_for_stage,
)
from .utils.config import Config as AppConfig
from .utils.config import apply_log_level
from .utils.metric import WorstMetricValue
from .utils.response import trim_long_string, wrap_code
from .vlm_function_specs import REVIEW_RESPONSE_SCHEMA, TrainingReview

logger = logging.getLogger("ai-scientist")
WORKSPACE_USAGE_FILE = Path("/tmp/ae_scientist_workspace_usage.txt")
_MAX_S3_DATASET_GROUPS_FOR_PROMPT = 50
_MAX_S3_DATASET_ENTRIES_PER_GROUP_FOR_PROMPT = 30
RESEARCH_PIPELINE_ROOT = Path(__file__).resolve().parents[2]


def _summarize_execution_with_llm(
    *,
    cfg: AppConfig,
    task_desc: str,
    stage_identifier: StageIdentifier,
    term_out: str,
    exc_type: str | None,
    exec_time: float,
) -> TrainingReview | None:
    prompt = {
        "Introduction": (
            "Analyze the execution output, determine if there were any bugs, and provide a summary of the findings. "
            "If there is a bug, summarize the failure and propose a concrete fix direction."
        ),
        "Research idea": task_desc,
        "Stage": stage_identifier.name,
        "Execution output": wrap_code(term_out, lang=""),
        "Exception type": str(exc_type or ""),
        "Execution time (seconds)": exec_time,
    }
    try:
        response = structured_query_with_schema(
            system_message=prompt,
            user_message=None,
            model=cfg.agent.feedback.model,
            temperature=cfg.agent.feedback.temperature,
            schema_class=REVIEW_RESPONSE_SCHEMA,
        )
    except Exception:  # noqa: BLE001
        logger.exception("Failed to summarize execution output via LLM.")
        return None
    return response


def _attach_parent(*, child_node: Node, parent_node: Node) -> None:
    # We intentionally attach relationships here so that `Node.to_dict()` emits `parent_id`,
    # which `Node.from_dict(..., journal=...)` uses to reconstruct the tree in the main process.
    child_node.parent = parent_node


def _legacy_available_datasets_text(*, environment_context: dict[str, object]) -> str:
    datasets = environment_context.get("datasets")
    if not isinstance(datasets, dict):
        return "You may use any dataset from any source, but avoid re-downloading available data."
    hf_lines = datasets.get("hf_cache_lines")
    local_lines = datasets.get("local_datasets_lines")
    s3_lines = datasets.get("s3_folder_lines")
    s3_download_snippet = datasets.get("s3_download_snippet")
    s3_upload_snippet = datasets.get("s3_upload_snippet")
    local_dir = str(datasets.get("datasets_local_dir", "")).strip()

    out: list[str] = []
    out.append("You may use any dataset from any source, but avoid re-downloading available data.")
    out.append("")
    out.append("**Hugging Face cache (already cached):**")
    if isinstance(hf_lines, list):
        out.extend([str(x) for x in hf_lines])
    else:
        out.append("- (unknown)")
    out.append("")
    out.append(
        f"**Local datasets (already downloaded):** (use subfolders per dataset under {local_dir})"
    )
    if isinstance(local_lines, list):
        out.extend([str(x) for x in local_lines])
    else:
        out.append("- (unknown)")
    if isinstance(s3_lines, list) and s3_lines:
        out.append("")
        out.append(
            "**Some datasets are available on S3, you can download them if you need to (the download is very fast):**"
        )
        out.extend([str(x) for x in s3_lines])
        if isinstance(s3_download_snippet, str) and s3_download_snippet.strip():
            out.append("")
            out.append(
                "**How to download from S3 into the local dataset cache (paste into your script):**"
            )
            out.append("")
            out.append(s3_download_snippet.strip())
        if isinstance(s3_upload_snippet, str) and s3_upload_snippet.strip():
            out.append("")
            out.append(
                "**How to upload a dataset to S3 for future runs (paste into your script):**"
            )
            out.append("")
            out.append(s3_upload_snippet.strip())
    return "\n".join(out).strip()


def _legacy_gpu_text(*, environment_context: dict[str, object]) -> str:
    gpu = environment_context.get("gpu")
    if not isinstance(gpu, dict):
        return ""
    gpu_id = gpu.get("gpu_id")
    gpu_spec = gpu.get("gpu_spec")
    if gpu_id is None or gpu_spec is None:
        return ""
    if not isinstance(gpu_spec, dict):
        return ""
    name = str(gpu_spec.get("name", "GPU"))
    mem = gpu_spec.get("memory_total_mib")
    mem_str = str(mem) if mem is not None else "unknown"
    return (
        "\n\n**Available Hardware**: You have access to ONE "
        f"{name} GPU with {mem_str}MiB VRAM.\n"
        "\n**GPU Selection**: Respect `CUDA_VISIBLE_DEVICES` (already set). Typically you should use `cuda:0`."
    )


def _legacy_storage_text(*, environment_context: dict[str, object]) -> str:
    storage = environment_context.get("storage")
    if not isinstance(storage, dict):
        return ""
    cap_h = storage.get("workspace_disk_capacity_human")
    free_h = storage.get("workspace_disk_free_human")
    if not isinstance(cap_h, str) or not isinstance(free_h, str):
        return ""
    return (
        "\n\n**Storage Availability**: "
        f"a dedicated workspace volume of ~{cap_h}; {free_h} free right now on your workspace volume. "
        "Use disk space responsibly when downloading datasets."
    )


def _legacy_impl_guideline_lines(
    *,
    cfg: AppConfig,
    environment_context: dict[str, object],
) -> list[str]:
    """
    Legacy prompt parity: copy the core “Implementation guideline” bullets used by MinimalAgent.
    """
    lines: list[str] = []
    lines.extend(
        [
            "CRITICAL GPU REQUIREMENTS - Your code MUST include ALL of these:",
            "  - At the start of your code, add these lines to handle GPU/CPU:",
        ]
    )
    gpu = environment_context.get("gpu")
    gpu_id = gpu.get("gpu_id") if isinstance(gpu, dict) else None
    if isinstance(gpu_id, int):
        lines.extend(
            [
                "    ```python",
                "    # CUDA_VISIBLE_DEVICES is already set; prefer cuda:0 inside the process",
                "    device = torch.device('cuda:0')",
                "    print(f'Using device: {device}')",
                "    ```",
            ]
        )
    else:
        lines.extend(
            [
                "    ```python",
                "    device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')",
                "    print(f'Using device: {device}')",
                "    ```",
            ]
        )
    lines.extend(
        [
            "  - ALWAYS move models to device using the `.to(device)` method",
            "  - ALWAYS move input tensors to device using the `.to(device)` method",
            "  - ALWAYS move model related tensors to device using the `.to(device)` method",
            "  - For optimizers, create them AFTER moving model to device",
            "  - When using DataLoader, move batch tensors to device in training loop: `batch = {k: v.to(device) for k, v in batch.items() if isinstance(v, torch.Tensor)}`",
            "CRITICAL MODEL INPUT GUIDELINES:",
            "  - Always pay extra attention to the input to the model being properly normalized",
            "  - This is extremely important because the input to the model's forward pass directly affects the output, and the loss function is computed based on the output",
        ]
    )
    num_syn_datasets = int(cfg.experiment.num_syn_datasets)
    if num_syn_datasets > 1:
        lines.extend(
            [
                f"You MUST evaluate your solution on at least {num_syn_datasets} different datasets to ensure robustness:",
                "  - Use dataset sizes appropriate to the experiment at hand",
                "  - Use standard benchmark datasets when available",
                f"  - If using synthetic data, generate at least {num_syn_datasets} variants with different characteristics",
                "  - For very large datasets (>10GB), use streaming=True to avoid memory issues",
                "  - Report metrics separately for each dataset",
                "  - Compute and report the average metric across all datasets",
            ]
        )
    lines.extend(
        [
            "For generative modeling tasks, you must:",
            "  - Generate a set of samples from your model",
            "  - Compare these samples with ground truth data using appropriate visualizations",
            "  - When saving plots, always use the 'working_dir' variable that will be defined at the start of the script",
            "  - Make sure to give each figure a unique and appropriate name based on the dataset it represents, rather than reusing the same filename.",
            "Important code structure requirements:",
            "  - Do NOT put any execution code inside 'if __name__ == \"__main__\":' block",
            "  - All code should be at the global scope or in functions that are called from the global scope",
            "  - The script should execute immediately when run, without requiring any special entry point",
            "The code should start with:",
            "  import os",
            "  working_dir = os.path.join(os.getcwd(), 'working')",
            "  os.makedirs(working_dir, exist_ok=True)",
            "The code should be a single-file python program that is self-contained and can be executed as-is.",
            "No parts of the code should be skipped, don't terminate the code execution before finishing the script.",
            "Your response should only contain a single code block.",
            f"Be aware of the running time of the code, it should complete within {humanize.naturaldelta(cfg.exec.timeout)}.",
            'You can also use the "./working" directory to store any temporary files that your code needs to create.',
            "Data saving requirements:",
            "- Save all plottable data (metrics, losses, predictions, etc.) as numpy arrays using np.save()",
            "- Make sure to use a filename 'experiment_data.npy' to save the data. Do not use any other filename.",
        ]
    )
    return lines


def _legacy_stage_intro(*, stage_identifier: StageIdentifier) -> str:
    if stage_identifier is StageIdentifier.STAGE1:
        return (
            "You are an AI researcher who is looking to publish a paper that will contribute significantly to the field. "
            "Your first task is to write a python code to implement a solid baseline based on your research idea provided below, "
            "from data preparation to model training, as well as evaluation and visualization. "
            "Focus on getting a simple but working implementation first, before any sophisticated improvements. "
            "We will explore more advanced variations in later stages."
        )
    if stage_identifier is StageIdentifier.STAGE2:
        return (
            "You are an experienced AI researcher. You are provided with a previously developed baseline implementation. "
            "Your task is to implement hyperparameter tuning to improve performance WITHOUT changing the model architecture."
        )
    if stage_identifier is StageIdentifier.STAGE3:
        return (
            "You are an experienced AI researcher. You are provided with a previously developed implementation. "
            "Your task is to explore novel improvements and run experiments to reveal new insights, and produce plots."
        )
    if stage_identifier is StageIdentifier.STAGE4:
        return (
            "You are an experienced AI researcher. You are provided with a previously developed implementation. "
            "Your task is to conduct systematic ablations that reveal the contribution of each component, and produce comparison plots."
        )
    return "You are an experienced AI researcher."


def _legacy_stage1_design_sketch_guideline_lines() -> list[str]:
    return [
        "This first experiment design should be relatively simple, without extensive hyper-parameter optimization.",
        "Take the Memory section into consideration when proposing the design.",
        "The solution sketch should be 6-10 sentences.",
        "Don't suggest to do EDA.",
        "Use real public datasets appropriate to the task.",
        "If the research idea specifies dataset URLs or names, use those.",
        "Otherwise, research where suitable datasets are available (common sources: HuggingFace, GitHub, academic repositories, etc.).",
        "Only fall back to synthetic data if no suitable dataset is available or synthetic generation is essential to the experiment.",
    ]


def _legacy_plotting_guideline_lines(*, experiment_code_hint: str) -> list[str]:
    return [
        "AVAILABLE DATA:",
        "Experiment Data: experiment_data.npy",
        "REQUIREMENTS:",
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
        "Use the following experiment code to infer the data to plot: " + experiment_code_hint,
        "Example to extract data from experiment_data: experiment_data['dataset_name_1']['metrics']['train']",
    ]


def _format_s3_entries_for_prompt(
    *,
    datasets_aws_folder: str,
    entries: list[S3DatasetEntry],
) -> list[str]:
    folder = datasets_aws_folder.strip("/")
    prefix = f"{folder}/" if folder else ""

    grouped: dict[str, list[tuple[str, int]]] = {}
    for entry in entries:
        s3_uri = entry.s3_uri
        size_bytes = entry.size_on_disk_bytes
        without_scheme = s3_uri.removeprefix("s3://")
        parts = without_scheme.split("/", 1)
        key = parts[1] if len(parts) == 2 else ""
        relative = key[len(prefix) :] if key.startswith(prefix) else key
        group = relative.split("/", 1)[0] if "/" in relative else "(root)"
        grouped.setdefault(group, []).append((relative, size_bytes))

    lines: list[str] = []
    for group_name in sorted(grouped.keys())[:_MAX_S3_DATASET_GROUPS_FOR_PROMPT]:
        lines.append(f"- {group_name}/")
        group_entries = grouped[group_name]
        shown = 0
        for rel_path, size_bytes in group_entries:
            if shown >= _MAX_S3_DATASET_ENTRIES_PER_GROUP_FOR_PROMPT:
                break
            child_path = rel_path.split("/", 1)[1] if "/" in rel_path else rel_path
            lines.append(f"  - {child_path} | size={size_bytes} bytes")
            shown += 1
        remaining = max(len(group_entries) - shown, 0)
        if remaining:
            lines.append(f"  - ... ({remaining} more)")
    return lines


def _load_workspace_usage_file() -> int | None:
    if not WORKSPACE_USAGE_FILE.exists():
        return None
    try:
        raw_text = WORKSPACE_USAGE_FILE.read_text(encoding="utf-8").strip()
    except OSError:
        logger.debug(
            "Could not read workspace usage file at %s", WORKSPACE_USAGE_FILE, exc_info=True
        )
        return None
    if not raw_text:
        return None
    try:
        return int(raw_text)
    except ValueError:
        logger.debug(
            "Malformed workspace usage file contents at %s: %s", WORKSPACE_USAGE_FILE, raw_text
        )
        return None


def _build_environment_context(
    *, gpu_id: int | None, gpu_spec: GPUSpec | None
) -> dict[str, object]:
    """
    Best-effort capture of environment context that the legacy codegen agent used to inject into prompts:
    - disk capacity/usage hints
    - dataset cache inventory (HF + local + S3)
    - S3 copy snippets
    """
    context: dict[str, object] = {
        "gpu": {
            "gpu_id": gpu_id,
            "gpu_spec": gpu_spec,
            "cuda_visible_devices": os.environ.get("CUDA_VISIBLE_DEVICES"),
            # We set CUDA_VISIBLE_DEVICES to a single value in this worker process.
            # Inside the experiment script, frameworks like PyTorch typically see that as cuda:0.
            "recommended_device": "cuda:0" if gpu_id is not None else "cpu",
        }
    }

    # Disk usage hints (optional)
    capacity_raw = os.environ.get("PIPELINE_WORKSPACE_DISK_CAPACITY_BYTES", "")
    capacity_int = int(capacity_raw) if capacity_raw.isdigit() else 0
    used_int = _load_workspace_usage_file()
    if capacity_int and used_int is not None:
        free_bytes_val = max(capacity_int - used_int, 0)
        context["storage"] = {
            "workspace_disk_capacity_bytes": capacity_int,
            "workspace_disk_used_bytes": used_int,
            "workspace_disk_free_bytes": free_bytes_val,
            "workspace_disk_capacity_human": humanize.naturalsize(capacity_int, binary=True),
            "workspace_disk_free_human": humanize.naturalsize(free_bytes_val, binary=True),
        }

    # Dataset cache inventory (best effort; never fail the run because of this)
    datasets_aws_folder = str(os.environ.get("DATASETS_AWS_FOLDER", "")).strip()
    local_datasets_dir = Path(str(os.environ.get("DATASETS_LOCAL_DIR", "")).strip())
    try:
        datasets_info = get_available_datasets(
            local_datasets_dir=local_datasets_dir, datasets_aws_folder=datasets_aws_folder
        )
        hf_lines: list[str] = []
        for repo in datasets_info.hf_cache:
            revs = ", ".join(repo.revision_hashes)
            hf_lines.append(
                f"- {repo.repo_id} ({repo.repo_type}) | size={repo.size_on_disk_bytes} bytes | revisions=[{revs}]"
            )
        if not hf_lines:
            hf_lines.append("- (none detected)")

        local_lines: list[str] = []
        for ds in datasets_info.local_datasets:
            local_lines.append(
                f"- {ds.dataset_name} | path={ds.path} | size={ds.size_on_disk_bytes} bytes"
            )
        if not local_lines:
            local_lines.append(
                f"- (empty) Create a subfolder per dataset under {local_datasets_dir}"
            )

        s3_lines: list[str] = []
        if datasets_info.s3_folder_entries:
            s3_lines = _format_s3_entries_for_prompt(
                datasets_aws_folder=datasets_aws_folder,
                entries=datasets_info.s3_folder_entries,
            )

        env_file = get_research_pipeline_env_file()
        s3_download_snippet = build_s3_download_snippet(
            datasets_aws_folder=datasets_aws_folder,
            local_datasets_dir=local_datasets_dir,
            env_file=env_file,
        )
        s3_upload_snippet = build_s3_upload_snippet(
            datasets_aws_folder=datasets_aws_folder,
            local_datasets_dir=local_datasets_dir,
            env_file=env_file,
        )

        context["datasets"] = {
            "datasets_local_dir": str(local_datasets_dir),
            "datasets_aws_folder": datasets_aws_folder,
            "hf_cache_lines": hf_lines,
            "local_datasets_lines": local_lines,
            "s3_folder_lines": s3_lines,
            "s3_download_snippet": s3_download_snippet,
            "s3_upload_snippet": s3_upload_snippet,
        }
    except (OSError, RuntimeError, ValueError):
        logger.exception("Failed building datasets context for Codex input", exc_info=True)

    # Key requirements (ported from legacy prompt guidelines) that Codex should obey.
    context["implementation_requirements"] = {
        "working_dir_relative": "working/",
        "save_experiment_data_filename": "experiment_data.npy",
        "do_not_prompt_user": True,
    }

    return context


class NodeTask(TypedDict):
    node_data: dict[str, object] | None
    task_desc: str
    evaluation_metric_spec: dict[str, object]
    cfg: AppConfig
    memory_summary: str
    stage_identifier: StageIdentifier
    seed_eval: bool
    seed_value: int
    seed_aggregation: dict[str, object] | None
    event_callback: Callable[[BaseEvent], None]
    gpu_id: int | None
    execution_id: str
    user_feedback_payload: str


class ExecutionTerminatedError(RuntimeError):
    """Raised when the execution was intentionally terminated via user action."""

    def __init__(self, execution_id: str, *, exec_time: float | None) -> None:
        super().__init__(f"Execution {execution_id} terminated intentionally")
        self.execution_id = execution_id
        self.exec_time = exec_time


class ExecutionCrashedError(RuntimeError):
    """Raised when the Codex process died unexpectedly."""

    def __init__(self, execution_id: str, *, exec_time: float | None) -> None:
        super().__init__(f"Execution {execution_id} crashed unexpectedly")
        self.execution_id = execution_id
        self.exec_time = exec_time


def _ensure_worker_log_level(*, cfg: AppConfig) -> None:
    try:
        apply_log_level(level_name=cfg.log_level)
    except (ValueError, TypeError):
        pass


def _prepare_workspace(*, cfg: AppConfig, process_id: str) -> tuple[Path, Path]:
    workspace_path = Path(cfg.workspace_dir) / f"process_{process_id}"
    workspace_path.mkdir(parents=True, exist_ok=True)
    working_dir_path = workspace_path / "working"
    working_dir_path.mkdir(parents=True, exist_ok=True)
    return workspace_path, working_dir_path


def _ensure_codex_venv(*, research_pipeline_root: Path) -> Path:
    """
    Ensure a shared Codex venv exists for the research_pipeline codebase.

    We intentionally avoid creating per-workspace venvs (e.g. per process workspace) because that
    leads to repeated installs across runs. Instead, Codex is run with env vars that point to this
    shared venv so `python` / `pip` resolve consistently.
    """
    venv_dir = research_pipeline_root / ".venv"
    venv_python = venv_dir / "bin" / "python"
    if venv_python.exists():
        return venv_dir
    subprocess.run(
        [sys.executable, "-m", "venv", str(venv_dir)],
        check=True,
        cwd=str(research_pipeline_root),
        env=os.environ.copy(),
        capture_output=True,
        text=True,
    )
    return venv_dir


def _build_codex_env(*, venv_dir: Path) -> dict[str, str]:
    env = os.environ.copy()
    bin_dir = venv_dir / "bin"
    env["VIRTUAL_ENV"] = str(venv_dir)
    env["PATH"] = f"{bin_dir}{os.pathsep}{env.get('PATH', '')}"
    env["PIP_REQUIRE_VIRTUALENV"] = "1"
    env["PYTHONNOUSERSITE"] = "1"
    openai_api_key = env.get("OPENAI_API_KEY")
    if openai_api_key:
        env["CODEX_API_KEY"] = openai_api_key
    # Encourage CLI tools to behave in non-interactive / CI mode.
    env["CI"] = "1"
    env["NO_UPDATE_NOTIFIER"] = "1"
    env["DISABLE_UPDATE_NOTIFIER"] = "1"
    env["npm_config_update_notifier"] = "false"
    return env


def _configure_gpu_for_worker(*, gpu_id: int | None) -> GPUSpec | None:
    if gpu_id is None:
        os.environ["CUDA_VISIBLE_DEVICES"] = ""
        return None
    os.environ["CUDA_VISIBLE_DEVICES"] = str(gpu_id)
    return get_gpu_specs(gpu_id)


def _load_parent_node(*, node_data: dict[str, object] | None) -> Node | None:
    if node_data is None:
        return None
    return Node.from_dict(node_data, journal=None)


def _abort_if_skip_requested(*, execution_id: str) -> None:
    skip_pending, reason = execution_registry.is_skip_pending(execution_id)
    if skip_pending:
        logger.info(
            "Skip pending for execution_id=%s (reason=%s); aborting before Codex run.",
            execution_id,
            reason,
        )
        raise ExecutionTerminatedError(execution_id=execution_id, exec_time=0.0)


def _write_codex_input_file(
    *,
    workspace_dir: Path,
    execution_id: str,
    task_desc: str,
    evaluation_metric_spec: dict[str, object],
    memory_summary: str,
    stage_identifier: StageIdentifier,
    parent_node: Node | None,
    seed_eval: bool,
    seed_value: int,
    seed_aggregation: dict[str, object] | None,
    gpu_id: int | None,
    gpu_spec: GPUSpec | None,
    cfg: AppConfig,
    user_feedback_payload: str,
) -> Path:
    payload: dict[str, object] = {
        "execution_id": execution_id,
        "research_idea": task_desc,
        "evaluation_metric_spec": evaluation_metric_spec,
        "memory_summary": memory_summary,
        "stage_identifier": stage_identifier.name,
        "seed_eval": seed_eval,
        "seed_value": seed_value,
        "seed_aggregation": seed_aggregation,
        "gpu_id": gpu_id,
        "agent_file_name": cfg.exec.agent_file_name,
        "timeout_seconds": cfg.exec.timeout,
        "parent_node": parent_node.to_dict() if parent_node is not None else None,
        "user_feedback_payload": user_feedback_payload,
        "environment_context": _build_environment_context(gpu_id=gpu_id, gpu_spec=gpu_spec),
    }
    path = workspace_dir / "codex_input.json"
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return path


def _write_codex_task_file(
    *,
    workspace_dir: Path,
    execution_id: str,
    stage_identifier: StageIdentifier,
    stage_name: str,
    timeout_seconds: int,
    agent_file_name: str,
    input_json_file: Path,
    output_json_file: Path,
    venv_dir: Path,
    cfg: AppConfig,
) -> Path:
    task_path = workspace_dir / "codex_task.md"
    # Construct a prompt-like payload in the task file so Codex has all needed context.
    # We embed the key sections as markdown; Codex reads task_file as plain text.
    try:
        input_obj = json.loads((workspace_dir / input_json_file.name).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        input_obj = {}
    if not isinstance(input_obj, dict):
        input_obj = {}
    env_ctx = input_obj.get("environment_context")
    env_ctx_dict = env_ctx if isinstance(env_ctx, dict) else {}
    memory_summary = str(input_obj.get("memory_summary") or "").strip()
    eval_metric_spec = input_obj.get("evaluation_metric_spec")
    eval_metric_str = json.dumps(eval_metric_spec, indent=2) if eval_metric_spec is not None else ""
    parent_node_obj = input_obj.get("parent_node")
    base_code = ""
    exec_time_feedback = ""
    parent_term_out = ""
    parent_analysis = ""
    parent_exc_type = ""
    parent_vlm_feedback_summary = ""
    user_feedback_payload = str(input_obj.get("user_feedback_payload") or "").strip()
    if isinstance(parent_node_obj, dict):
        base_code = str(parent_node_obj.get("code") or "")
        exec_time_feedback = str(parent_node_obj.get("exec_time_feedback") or "")
        parent_analysis = str(parent_node_obj.get("analysis") or "").strip()
        parent_exc_type = str(parent_node_obj.get("exc_type") or "").strip()
        raw_term_out = parent_node_obj.get("_term_out")
        if isinstance(raw_term_out, list):
            parent_term_out = trim_long_string("".join([str(x) for x in raw_term_out]))
        raw_vlm = parent_node_obj.get("vlm_feedback_summary")
        if isinstance(raw_vlm, list):
            parent_vlm_feedback_summary = "\n".join([str(x) for x in raw_vlm]).strip()

    context_sections: list[str] = []
    context_sections.append("## Task context")
    context_sections.append("")
    context_sections.append("### Introduction")
    context_sections.append(_legacy_stage_intro(stage_identifier=stage_identifier))
    context_sections.append("")
    context_sections.append("### Research idea")
    context_sections.append(str(input_obj.get("research_idea") or "").strip())
    context_sections.append("")
    context_sections.append("### Memory")
    context_sections.append(memory_summary if memory_summary else "(empty)")
    context_sections.append("")
    context_sections.append("### Installed Packages")
    context_sections.append(
        "A Python virtualenv is already set up and active at "
        f"`{venv_dir}` (so `python` / `pip` resolve to that environment). "
        "Reuse it; do not create a new venv. Install missing packages into this venv only if required."
        + _legacy_gpu_text(environment_context=env_ctx_dict)
        + _legacy_storage_text(environment_context=env_ctx_dict)
    )
    context_sections.append("")
    context_sections.append("### Available Datasets")
    context_sections.append(_legacy_available_datasets_text(environment_context=env_ctx_dict))
    context_sections.append("")
    context_sections.append("### Evaluation Metric(s)")
    context_sections.append(eval_metric_str if eval_metric_str else "(none)")
    context_sections.append("")
    context_sections.append("### Implementation guideline")
    context_sections.extend(
        [
            f"- {line}"
            for line in _legacy_impl_guideline_lines(cfg=cfg, environment_context=env_ctx_dict)
        ]
    )

    if stage_identifier is StageIdentifier.STAGE1:
        context_sections.append("")
        context_sections.append("### Experiment design sketch guideline (Stage 1 baseline)")
        context_sections.extend(
            [f"- {line}" for line in _legacy_stage1_design_sketch_guideline_lines()]
        )

    if stage_identifier is StageIdentifier.STAGE2:
        context_sections.append("")
        context_sections.append("### Stage 2 hyperparameter-tuning requirements")
        context_sections.extend(
            [
                "- DO NOT change model architecture from the previous stage.",
                "- Choose ONE hyperparameter tuning idea for this run and set `hyperparam_name` in node_result.json accordingly.",
                "- Save data in `working/experiment_data.npy` with a structure like:",
                "- ```python",
                "- experiment_data = {",
                "-     'hyperparam_tuning_type_1': {",
                "-         'dataset_name_1': {",
                "-             'metrics': {'train': [], 'val': []},",
                "-             'losses': {'train': [], 'val': []},",
                "-             'predictions': [],",
                "-             'ground_truth': [],",
                "-         },",
                "-     },",
                "- }",
                "- ```",
            ]
        )

    if stage_identifier is StageIdentifier.STAGE4:
        context_sections.append("")
        context_sections.append("### Stage 4 ablation requirements")
        context_sections.extend(
            [
                "- Choose ONE ablation idea for this run and set `ablation_name` in node_result.json accordingly.",
                "- Save data in `working/experiment_data.npy` with a structure like:",
                "- ```python",
                "- experiment_data = {",
                "-     'ablation_type_1': {",
                "-         'dataset_name_1': {",
                "-             'metrics': {'train': [], 'val': []},",
                "-             'losses': {'train': [], 'val': []},",
                "-             'predictions': [],",
                "-             'ground_truth': [],",
                "-         },",
                "-     },",
                "- }",
                "- ```",
            ]
        )

    if base_code.strip():
        context_sections.append("")
        context_sections.append("### Base code you are working on (from parent node)")
        context_sections.append("```python")
        context_sections.append(base_code.rstrip())
        context_sections.append("```")
    if parent_term_out.strip():
        context_sections.append("")
        context_sections.append("### Previous execution output (from parent node)")
        context_sections.append(parent_term_out.strip())
    if parent_exc_type:
        context_sections.append("")
        context_sections.append("### Previous exception type (from parent node)")
        context_sections.append(parent_exc_type)
    if parent_analysis:
        context_sections.append("")
        context_sections.append("### Previous analysis / summary (from parent node)")
        context_sections.append(parent_analysis)
    if parent_vlm_feedback_summary:
        context_sections.append("")
        context_sections.append("### Feedback based on generated plots (from parent node)")
        context_sections.append(parent_vlm_feedback_summary)
    if exec_time_feedback.strip():
        context_sections.append("")
        context_sections.append("### Feedback about execution time")
        context_sections.append(exec_time_feedback.strip())
    if user_feedback_payload:
        context_sections.append("")
        context_sections.append("### User feedback")
        context_sections.append(user_feedback_payload)

    if stage_identifier in (StageIdentifier.STAGE3, StageIdentifier.STAGE4):
        context_sections.append("")
        context_sections.append("### Plotting code guideline")
        experiment_code_hint = (
            "Use the final experiment code you wrote in the agent file to infer what data exists in experiment_data.npy."
            if not base_code
            else base_code
        )
        context_sections.extend(
            [
                f"- {line}"
                for line in _legacy_plotting_guideline_lines(
                    experiment_code_hint=experiment_code_hint
                )
            ]
        )
    context_block = "\n".join(context_sections).strip() + "\n\n"

    is_seed_aggregation = isinstance(input_obj.get("seed_aggregation"), dict)
    if is_seed_aggregation:
        # Override stage contract for seed-aggregation runs: keep common contract + add explicit
        # aggregation requirements (including is_seed_agg_node=true).
        contract_lines = (
            codex_node_result_contract_prompt_lines_common() + codex_seed_agg_contract_lines()
        )
        seed_agg_instructions = "\n".join(codex_seed_aggregation_instructions_lines()).strip()
        seed_agg_block = seed_agg_instructions + "\n\n"
    else:
        contract_lines = codex_node_result_contract_prompt_lines_for_stage(
            stage_identifier=stage_identifier
        )
        seed_agg_block = ""
    contract_block = "\n".join(contract_lines).strip() + "\n\n"

    task_text = (
        "You are an autonomous coding agent running inside a sandboxed workspace.\\n"
        "You must not ask the user for input; proceed with reasonable defaults.\\n"
        "You have full permission to install packages, download data, edit files, and run commands.\\n\\n"
        f"## Context\\n- execution_id: `{execution_id}`\\n"
        f"- stage_identifier: `{stage_identifier.name}`\\n"
        f"- stage_name: `{stage_name}`\\n"
        f"- wall_clock_timeout_seconds: {timeout_seconds}\\n\\n"
        "## Inputs\\n"
        f"- Read `{input_json_file.name}` for the full task context.\\n"
        "  - Use `environment_context.datasets` for available datasets and S3 download/upload snippets.\\n"
        "  - Use `environment_context.gpu` for GPU id/specs and `recommended_device`.\\n\\n"
        f"{seed_agg_block}"
        "## Required outputs (MUST)\\n"
        f"- Write a complete Node dict to `{output_json_file.name}` using the same schema as Node.to_dict.\\n"
        f"- Write your final experiment code to `{agent_file_name}`.\\n"
        "- Ensure any experiment artifacts are placed in `./working/` (e.g., `experiment_data.npy`, plots, etc.).\\n"
        "- For plots: write `.png` files into `./working/`. You MAY leave `plots`/`plot_paths` empty in `node_result.json`; the runner collects paths automatically.\\n\\n"
        f"{contract_block}"
        "## Hard requirements\\n"
        "- Create and use `working_dir = os.path.join(os.getcwd(), 'working')` and save artifacts there.\\n"
        "- Save plottable data to `working/experiment_data.npy` via `np.save(...)`.\\n"
        "- Avoid re-downloading data if it's already present in the dataset caches described in `codex_input.json`.\\n\\n"
        "## Metric requirement\\n"
        "- Read `evaluation_metric_spec` from `codex_input.json` and use it as the primary metric definition.\\n"
        "- Populate `metric` in `node_result.json` with:\\n"
        "  - `metric.name` exactly matching `evaluation_metric_spec.name`\\n"
        "  - `metric.maximize` exactly matching `evaluation_metric_spec.maximize`\\n"
        "  - `metric.description` matching `evaluation_metric_spec.description`\\n"
        "  - `metric.value` as a numeric value from your evaluation run\\n\\n"
        "## Seed requirement\\n"
        "- Read `seed_eval` and `seed_value` from `codex_input.json`.\\n"
        "- If `seed_eval` is true, you MUST make the experiment deterministic by setting seeds in the final experiment code:\\n"
        "  - `random.seed(seed_value)`\\n"
        "  - `numpy.random.seed(seed_value)`\\n"
        "  - If torch is used: `torch.manual_seed(seed_value)` and if CUDA is available `torch.cuda.manual_seed_all(seed_value)`\\n"
        "- If torch is used, also set `torch.backends.cudnn.deterministic = True` and `torch.backends.cudnn.benchmark = False`.\\n"
        '- If `seed_eval` is true, set `is_seed_node=true` in node_result.json and include the seed in your `plan` text (e.g. "Seed: 3").\\n\\n'
        "## GPU requirement\\n"
        "- If `environment_context.gpu.gpu_id` is not null, you MUST use the GPU when applicable (training/inference).\\n"
        "- Respect `CUDA_VISIBLE_DEVICES` (already set). Typically you should use `torch.device('cuda:0')`.\\n\\n"
        "## Execution contract\\n"
        "- Run any commands you need.\\n"
        f"- Run the final experiment with: `python {agent_file_name}`.\\n"
        "- If the run fails, iterate (edit/install/rerun) until it succeeds or time runs out.\\n"
    )
    task_path.write_text(context_block + task_text, encoding="utf-8")
    return task_path


def _load_node_result(*, output_json_file: Path) -> dict[str, object] | None:
    if not output_json_file.exists():
        return None
    try:
        parsed = json.loads(output_json_file.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        logger.debug("Failed reading node_result.json at %s", output_json_file, exc_info=True)
        return None
    if not isinstance(parsed, dict):
        return None
    return parsed


def _move_experiment_artifacts(
    *,
    cfg: AppConfig,
    child_node: Node,
    working_dir: Path,
    event_callback: Callable[[BaseEvent], None],
) -> None:
    if not working_dir.exists():
        return
    base_dir = Path(cfg.workspace_dir).parent
    run_name = Path(cfg.workspace_dir).name
    exp_results_dir = (
        base_dir
        / "logs"
        / run_name
        / "experiment_results"
        / f"experiment_{child_node.id}_proc_{os.getpid()}"
    )
    child_node.exp_results_dir = str(exp_results_dir)
    exp_results_dir.mkdir(parents=True, exist_ok=True)
    logger.debug(
        "artifacts.begin node=%s working_dir=%s exp_results_dir=%s",
        child_node.id[:8],
        working_dir,
        exp_results_dir,
    )

    workspace_dir = working_dir.parent
    for fname in (
        "codex_input.json",
        "codex_task.md",
        "codex_session.log",
        "codex_events.jsonl",
        "node_result.json",
    ):
        src = workspace_dir / fname
        if not src.exists():
            continue
        dst = exp_results_dir / fname
        try:
            dst.write_bytes(src.read_bytes())
        except OSError:
            logger.debug("artifacts.copy_failed src=%s dst=%s", src, dst, exc_info=True)
        else:
            logger.debug("artifacts.copied src=%s dst=%s bytes=%s", src, dst, dst.stat().st_size)

    summary_path = working_dir / "summary.json"
    if summary_path.exists():
        try:
            summary_text = summary_path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            logger.debug(
                "artifacts.summary_json read_failed path=%s",
                summary_path,
                exc_info=True,
            )
        else:
            logger.debug(
                "artifacts.summary_json captured path=%s chars=%s preview=\n%s",
                summary_path,
                len(summary_text),
                trim_long_string(string=summary_text, threshold=2000, k=700),
            )

    code_src = (working_dir.parent / cfg.exec.agent_file_name).resolve()
    if code_src.exists():
        code_text = code_src.read_text(encoding="utf-8")
        (exp_results_dir / "experiment_code.py").write_text(code_text, encoding="utf-8")
        logger.debug(
            "artifacts.experiment_code captured path=%s chars=%s preview=\n%s",
            exp_results_dir / "experiment_code.py",
            len(code_text),
            trim_long_string(string=code_text, threshold=2400, k=800),
        )

    npy_files = list(working_dir.glob("*.npy"))
    if npy_files:
        logger.debug(
            "artifacts.npy_files count=%s names=%s",
            len(npy_files),
            [p.name for p in npy_files],
        )
    for exp_data_file in npy_files:
        exp_data_path = exp_results_dir / exp_data_file.name
        exp_data_file.resolve().rename(exp_data_path)

    plot_files_found = list(working_dir.glob("*.png"))
    if plot_files_found:
        event_callback(
            RunLogEvent(message=f"✓ Generated {len(plot_files_found)} plot file(s)", level="info")
        )
        logger.debug(
            "artifacts.png_files count=%s names=%s",
            len(plot_files_found),
            [p.name for p in plot_files_found],
        )
    for plot_file in plot_files_found:
        final_path = exp_results_dir / plot_file.name
        plot_file.resolve().rename(final_path)
        web_path = (
            f"../../logs/{Path(cfg.workspace_dir).name}/experiment_results/"
            f"experiment_{child_node.id}_proc_{os.getpid()}/{plot_file.name}"
        )
        child_node.plots.append(web_path)
        child_node.plot_paths.append(str(final_path.absolute()))
    logger.debug(
        "artifacts.done node=%s exp_results_dir=%s plots=%s npy_files=%s",
        child_node.id[:8],
        exp_results_dir,
        len(child_node.plots),
        len(npy_files),
    )


def process_node(
    *,
    node_data: dict[str, object] | None,
    task_desc: str,
    evaluation_metric_spec: dict[str, object],
    cfg: AppConfig,
    memory_summary: str,
    stage_identifier: StageIdentifier,
    seed_eval: bool,
    seed_value: int,
    seed_aggregation: dict[str, object] | None,
    event_callback: Callable[[BaseEvent], None],
    gpu_id: int | None,
    execution_id: str,
    user_feedback_payload: str,
) -> dict[str, object]:
    _ensure_worker_log_level(cfg=cfg)
    process_id = multiprocessing.current_process().name
    workspace_dir, working_dir = _prepare_workspace(cfg=cfg, process_id=process_id)
    gpu_spec = _configure_gpu_for_worker(gpu_id=gpu_id)
    venv_dir = _ensure_codex_venv(research_pipeline_root=RESEARCH_PIPELINE_ROOT)
    codex_env = _build_codex_env(venv_dir=venv_dir)

    parent_node = _load_parent_node(node_data=node_data)
    stage_name = stage_identifier.prefixed_name
    logger.debug(
        "worker.begin execution_id=%s process_id=%s stage=%s seed_eval=%s seed_value=%s gpu_id=%s parent=%s workspace_dir=%s working_dir=%s",
        execution_id[:8],
        process_id,
        stage_name,
        seed_eval,
        seed_value,
        gpu_id,
        None if parent_node is None else parent_node.id[:8],
        workspace_dir,
        working_dir,
    )
    if seed_aggregation is not None:
        logger.debug(
            "worker.seed_aggregation enabled execution_id=%s keys=%s",
            execution_id[:8],
            sorted(list(seed_aggregation.keys()))[:30],
        )
    if user_feedback_payload.strip():
        logger.debug(
            "worker.user_feedback provided execution_id=%s payload_preview=%s",
            execution_id[:8],
            user_feedback_payload[:200].replace("\n", " "),
        )

    _abort_if_skip_requested(execution_id=execution_id)

    output_json_file = workspace_dir / "node_result.json"
    input_json_file = _write_codex_input_file(
        workspace_dir=workspace_dir,
        execution_id=execution_id,
        task_desc=task_desc,
        evaluation_metric_spec=evaluation_metric_spec,
        memory_summary=memory_summary,
        stage_identifier=stage_identifier,
        parent_node=parent_node,
        seed_eval=seed_eval,
        seed_value=seed_value,
        seed_aggregation=seed_aggregation,
        gpu_id=gpu_id,
        gpu_spec=gpu_spec,
        cfg=cfg,
        user_feedback_payload=user_feedback_payload,
    )
    logger.debug(
        "codex.input.written execution_id=%s path=%s stage=%s metric_name=%s seed_eval=%s seed_value=%s",
        execution_id[:8],
        input_json_file,
        stage_name,
        str(evaluation_metric_spec.get("name") or ""),
        seed_eval,
        seed_value,
    )
    try:
        codex_input_text = input_json_file.read_text(encoding="utf-8", errors="replace")
    except OSError:
        logger.debug(
            "codex.input.read_failed execution_id=%s path=%s",
            execution_id[:8],
            input_json_file,
            exc_info=True,
        )
    else:
        logger.debug(
            "codex.input.contents execution_id=%s path=%s chars=%s\n%s",
            execution_id[:8],
            input_json_file,
            len(codex_input_text),
            codex_input_text,
        )
    task_file = _write_codex_task_file(
        workspace_dir=workspace_dir,
        execution_id=execution_id,
        stage_identifier=stage_identifier,
        stage_name=stage_name,
        timeout_seconds=cfg.exec.timeout,
        agent_file_name=cfg.exec.agent_file_name,
        input_json_file=input_json_file,
        output_json_file=output_json_file,
        venv_dir=venv_dir,
        cfg=cfg,
    )
    logger.debug(
        "codex.task.written execution_id=%s path=%s chars=%s",
        execution_id[:8],
        task_file,
        len(task_file.read_text(encoding="utf-8", errors="replace")),
    )
    try:
        codex_task_text = task_file.read_text(encoding="utf-8", errors="replace")
    except OSError:
        logger.debug(
            "codex.task.read_failed execution_id=%s path=%s",
            execution_id[:8],
            task_file,
            exc_info=True,
        )
    else:
        logger.debug(
            "codex.task.contents execution_id=%s path=%s chars=%s\n%s",
            execution_id[:8],
            task_file,
            len(codex_task_text),
            codex_task_text,
        )

    runner = CodexCliRunner(
        workspace_dir=workspace_dir,
        timeout_seconds=cfg.exec.timeout,
        argv=[
            "codex",
            "exec",
            "--full-auto",
            "--sandbox",
            "danger-full-access",
            "--skip-git-repo-check",
            "--json",
        ],
        env=codex_env,
    )

    started_at = datetime.now(timezone.utc)
    event_callback(RunLogEvent(message="Executing via Codex CLI...", level="info"))
    event_callback(
        RunningCodeEvent(
            execution_id=execution_id,
            stage_name=stage_name,
            code="(Codex-managed)",
            started_at=started_at,
        )
    )

    def _pid_tracker(pid: int) -> None:
        execution_registry.update_pid(execution_id=execution_id, pid=pid)

    def _termination_checker() -> bool:
        return execution_registry.is_terminated(execution_id=execution_id)

    term_out, exec_time, exc_type, exc_info = runner.run(
        task_file=task_file,
        pid_callback=_pid_tracker,
        termination_checker=_termination_checker,
        success_file=output_json_file,
        stream_callback=lambda msg: event_callback(RunLogEvent(message=msg, level="info")),
    )
    logger.debug(
        "codex.run.completed execution_id=%s status=%s exec_time_s=%s exc_type=%s exc_info=%s workspace_dir=%s session_log=%s events_jsonl=%s",
        execution_id[:8],
        "success" if exc_type is None else "failed",
        exec_time,
        exc_type,
        exc_info,
        workspace_dir,
        workspace_dir / "codex_session.log",
        workspace_dir / "codex_events.jsonl",
    )

    completed_at = datetime.now(timezone.utc)
    status: Literal["success", "failed"] = "success" if exc_type is None else "failed"
    event_callback(
        RunCompletedEvent(
            execution_id=execution_id,
            stage_name=stage_name,
            status=status,
            exec_time=exec_time,
            completed_at=completed_at,
        )
    )
    if exc_type is None:
        execution_registry.mark_completed(execution_id=execution_id)
    else:
        execution_registry.clear_pid(execution_id=execution_id)

    node_result = _load_node_result(output_json_file=output_json_file)
    if node_result is None:
        logger.debug(
            "codex.output.missing_node_result execution_id=%s expected_path=%s",
            execution_id[:8],
            output_json_file,
        )
        child_node = Node(
            id=execution_id,
            plan="",
            code="",
            is_buggy=True,
            analysis="Codex did not produce a valid node_result.json.",
            exc_type=exc_type or "CodexError",
            exec_time=exec_time,
        )
        child_node.absorb_exec_result(
            SimpleNamespace(
                term_out=term_out,
                exec_time=exec_time,
                exc_type=exc_type,
                exc_info=exc_info,
                exc_stack=None,
            )
        )
        child_node.exc_info = exc_info or {}
        child_node.metric = WorstMetricValue()
        if parent_node is not None:
            _attach_parent(child_node=child_node, parent_node=parent_node)
        _move_experiment_artifacts(
            cfg=cfg,
            child_node=child_node,
            working_dir=working_dir,
            event_callback=event_callback,
        )
        result_data = child_node.to_dict()
        pickle.dumps(result_data)
        return result_data

    node_result["id"] = execution_id
    node_result["parent_id"] = None if parent_node is None else parent_node.id
    logger.debug(
        "codex.output.node_result_loaded execution_id=%s keys=%s plan_preview=%s",
        execution_id[:8],
        sorted(list(node_result.keys()))[:40],
        str(node_result.get("plan") or "")[:200].replace("\n", " "),
    )

    contract_ctx = NodeResultContractContext(
        stage_identifier=stage_identifier,
        is_seed_aggregation=seed_aggregation is not None,
        seed_eval=seed_eval,
        seed_value=seed_value,
        working_png_count=count_working_pngs(working_dir=working_dir),
    )
    contract_errors = validate_node_result_contract_for_stage(
        node_result=node_result,
        ctx=contract_ctx,
    )
    if contract_errors:
        logger.debug(
            "codex.output.contract_failed execution_id=%s errors_count=%s errors=%s",
            execution_id[:8],
            len(contract_errors),
            contract_errors,
        )
        child_node = Node(
            id=execution_id,
            plan=str(node_result.get("plan") or ""),
            code=str(node_result.get("code") or ""),
            is_buggy=True,
            is_buggy_plots=True,
            analysis=(
                "Codex node_result contract violation(s):\n- " + "\n- ".join(contract_errors)
            ),
            exc_type=exc_type or "CodexContractError",
            exec_time=exec_time,
        )
        child_node.metric = WorstMetricValue()
        if parent_node is not None:
            _attach_parent(child_node=child_node, parent_node=parent_node)
        child_node.absorb_exec_result(
            SimpleNamespace(
                term_out=term_out,
                exec_time=exec_time,
                exc_type=exc_type,
                exc_info=exc_info,
                exc_stack=None,
            )
        )
        child_node.exc_info = exc_info or {}
        _move_experiment_artifacts(
            cfg=cfg,
            child_node=child_node,
            working_dir=working_dir,
            event_callback=event_callback,
        )
        result_data = child_node.to_dict()
        pickle.dumps(result_data)
        return result_data

    try:
        child_node = Node.from_dict(dict(node_result), journal=None)
    except Exception as exc:  # noqa: BLE001
        # Never crash the worker on schema drift: mark the node buggy and return a valid Node dict.
        tb = traceback.format_exc()
        child_node = Node(
            id=execution_id,
            plan=str(node_result.get("plan") or ""),
            code=str(node_result.get("code") or ""),
            is_buggy=True,
            is_buggy_plots=True,
            analysis=(
                "Failed to parse node_result.json into Node.\n"
                f"Exception: {exc}\n\n"
                f"Traceback:\n{tb}"
            ),
            exc_type=exc_type or "NodeParseError",
            exec_time=exec_time,
        )
        child_node.metric = WorstMetricValue()
        if parent_node is not None:
            _attach_parent(child_node=child_node, parent_node=parent_node)
    logger.debug(
        "worker.node_parsed execution_id=%s is_buggy=%s is_buggy_plots=%s metric=%s plan_preview=%s analysis_preview=%s plot_analyses=%s vlm_feedback_summary=%s datasets_successfully_tested=%s",
        execution_id[:8],
        child_node.is_buggy,
        child_node.is_buggy_plots,
        None if child_node.metric is None else str(child_node.metric),
        (child_node.plan or "")[:160].replace("\n", " "),
        (str(child_node.analysis or ""))[:160].replace("\n", " "),
        len(child_node.plot_analyses),
        len(child_node.vlm_feedback_summary),
        len(child_node.datasets_successfully_tested),
    )
    child_node.absorb_exec_result(
        SimpleNamespace(
            term_out=term_out,
            exec_time=exec_time,
            exc_type=exc_type,
            exc_info=exc_info,
            exc_stack=None,
        )
    )
    child_node.exec_time = exec_time
    child_node.exc_type = exc_type
    child_node.exc_info = exc_info or {}
    if parent_node is not None and child_node.parent is None:
        _attach_parent(child_node=child_node, parent_node=parent_node)
    if child_node.metric is None:
        child_node.metric = WorstMetricValue()
        child_node.is_buggy = True if child_node.is_buggy is None else child_node.is_buggy
    if child_node.analysis is None or not str(child_node.analysis).strip():
        llm_review = _summarize_execution_with_llm(
            cfg=cfg,
            task_desc=task_desc,
            stage_identifier=stage_identifier,
            term_out="".join(term_out),
            exc_type=exc_type,
            exec_time=float(exec_time),
        )
        if llm_review is not None:
            summary = str(llm_review.summary or "").strip()
            if summary:
                child_node.analysis = summary
            if llm_review.is_bug:
                child_node.is_buggy = True

    _move_experiment_artifacts(
        cfg=cfg,
        child_node=child_node,
        working_dir=working_dir,
        event_callback=event_callback,
    )

    result_data = child_node.to_dict()
    pickle.dumps(result_data)
    return result_data


def process_node_task(task: NodeTask) -> dict[str, object]:
    return process_node(
        node_data=task["node_data"],
        task_desc=task["task_desc"],
        evaluation_metric_spec=task["evaluation_metric_spec"],
        cfg=task["cfg"],
        memory_summary=task["memory_summary"],
        stage_identifier=task["stage_identifier"],
        seed_eval=task["seed_eval"],
        seed_value=task["seed_value"],
        seed_aggregation=task["seed_aggregation"],
        event_callback=task["event_callback"],
        gpu_id=task["gpu_id"],
        execution_id=task["execution_id"],
        user_feedback_payload=task["user_feedback_payload"],
    )
