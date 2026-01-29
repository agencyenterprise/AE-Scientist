import logging
import os
from pathlib import Path
from urllib.parse import urlparse

from ..datasets_context import (
    S3DatasetEntry,
    build_s3_download_snippet,
    build_s3_upload_snippet,
    get_available_datasets,
    get_research_pipeline_env_file,
)
from ..gpu_manager import GPUSpec

_WORKSPACE_USAGE_FILE = Path("/tmp/ae_scientist_workspace_usage.txt")
_MAX_S3_DATASET_GROUPS_FOR_PROMPT = 50
_MAX_S3_DATASET_ENTRIES_PER_GROUP_FOR_PROMPT = 30


logger = logging.getLogger("ai-scientist")


def _load_workspace_usage_file(*, usage_file: Path) -> int | None:
    if not usage_file.exists():
        return None
    try:
        raw_text = usage_file.read_text(encoding="utf-8").strip()
    except OSError:
        return None
    if not raw_text:
        return None
    try:
        return int(raw_text)
    except ValueError:
        return None


def _extract_path_from_presigned_url(url: str) -> str:
    """Extract the S3 key path from a presigned URL.

    Handles URLs like:
    - https://bucket.s3.amazonaws.com/path/to/file?AWSAccessKeyId=...
    - https://bucket.s3.region.amazonaws.com/path/to/file?AWSAccessKeyId=...
    """
    parsed = urlparse(url)
    # Remove query string and get the path, stripping leading slash
    path = parsed.path.lstrip("/")
    return path


def _format_s3_entries_for_prompt(
    *,
    datasets_aws_folder: str,
    entries: list[S3DatasetEntry],
    max_groups: int,
    max_entries_per_group: int,
) -> list[str]:
    folder = datasets_aws_folder.strip("/")
    prefix = f"{folder}/" if folder else ""

    # Group entries by folder, storing (relative_path, size_bytes, full_url)
    grouped: dict[str, list[tuple[str, int, str]]] = {}
    for entry in entries:
        presigned_url = entry.s3_uri
        size_bytes = entry.size_on_disk_bytes

        # Extract the path from the presigned URL
        key = _extract_path_from_presigned_url(presigned_url)

        # Remove the datasets folder prefix to get relative path
        relative = key[len(prefix) :] if key.startswith(prefix) else key

        # Group by first folder in relative path
        if "/" in relative:
            group = relative.split("/", 1)[0]
        else:
            group = "(root)"

        grouped.setdefault(group, []).append((relative, size_bytes, presigned_url))

    lines: list[str] = []
    for group_name in sorted(grouped.keys())[:max_groups]:
        lines.append(f"- {group_name}/")
        group_entries = grouped[group_name]
        shown = 0
        for rel_path, size_bytes, full_url in group_entries:
            if shown >= max_entries_per_group:
                break
            # Get the filename (last part of path)
            child_path = rel_path.split("/", 1)[1] if "/" in rel_path else rel_path
            lines.append(f"  - {child_path} | size={size_bytes} bytes")
            lines.append(f"    URL: '{full_url}'")
            shown += 1
        remaining = max(len(group_entries) - shown, 0)
        if remaining:
            lines.append(f"  - ... ({remaining} more)")
    return lines


def build_environment_context(*, gpu_id: int | None, gpu_spec: GPUSpec | None) -> dict[str, object]:
    """
    Best-effort capture of environment context injected into prompts:
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
    used_int = _load_workspace_usage_file(usage_file=_WORKSPACE_USAGE_FILE)
    if capacity_int and used_int is not None:
        free_bytes_val = max(capacity_int - used_int, 0)
        context["storage"] = {
            "workspace_disk_capacity_bytes": capacity_int,
            "workspace_disk_used_bytes": used_int,
            "workspace_disk_free_bytes": free_bytes_val,
        }

    # Dataset cache inventory (best effort; never fail the run because of this)
    datasets_aws_folder = str(os.environ.get("DATASETS_AWS_FOLDER", "")).strip()
    local_datasets_dir = Path(str(os.environ.get("DATASETS_LOCAL_DIR", "")).strip())
    logger.info(f"Local datasets directory: {local_datasets_dir}")
    logger.info(f"Datasets AWS folder: {datasets_aws_folder}")
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
                max_groups=_MAX_S3_DATASET_GROUPS_FOR_PROMPT,
                max_entries_per_group=_MAX_S3_DATASET_ENTRIES_PER_GROUP_FOR_PROMPT,
            )

        env_file = get_research_pipeline_env_file()
        s3_download_snippet = build_s3_download_snippet(
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
        # Never fail prompt generation due to context probing.
        pass

    # Key requirements (ported from prompt guidelines) that Codex should obey.
    context["implementation_requirements"] = {
        "working_dir_relative": "working/",
        "save_experiment_data_filename": "experiment_data.npy",
        "do_not_prompt_user": True,
    }

    return context
