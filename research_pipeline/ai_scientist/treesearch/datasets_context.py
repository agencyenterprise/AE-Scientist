import logging
import os
from pathlib import Path
from typing import NamedTuple, Optional

import requests
from dotenv import load_dotenv
from huggingface_hub import CacheNotFound, scan_cache_dir

from ai_scientist.api_types import ListDatasetsRequest, ListDatasetsResponse

logger = logging.getLogger("ai-scientist")
_MAX_S3_FOLDER_ENTRIES = 2000


class HFCachedRepo(NamedTuple):
    repo_id: str
    repo_type: str
    size_on_disk_bytes: int
    revision_hashes: list[str]


class LocalDataset(NamedTuple):
    dataset_name: str
    path: Path
    size_on_disk_bytes: int


class S3DatasetEntry(NamedTuple):
    s3_uri: str
    size_on_disk_bytes: int


class AvailableDatasets(NamedTuple):
    hf_cache: list[HFCachedRepo]
    local_datasets: list[LocalDataset]
    s3_folder_entries: list[S3DatasetEntry]


def get_research_pipeline_env_file() -> Path:
    return Path(__file__).resolve().parents[2] / ".env"


def _dir_size_bytes(*, root: Path) -> int:
    total = 0
    if not root.exists():
        return 0
    if root.is_file():
        try:
            return root.stat().st_size
        except OSError:
            return 0
    for p in root.rglob("*"):
        if not p.is_file():
            continue
        try:
            total += p.stat().st_size
        except OSError:
            continue
    return total


def _list_local_datasets(*, local_datasets_dir: Path) -> list[LocalDataset]:
    if local_datasets_dir == Path(""):
        logger.info("Local datasets directory is empty")
        return []
    local_datasets_dir.mkdir(parents=True, exist_ok=True)
    datasets: list[LocalDataset] = []
    for p in sorted(local_datasets_dir.iterdir(), key=lambda x: x.name):
        if not p.exists():
            continue
        size_bytes = _dir_size_bytes(root=p)
        datasets.append(
            LocalDataset(
                dataset_name=p.name,
                path=p,
                size_on_disk_bytes=size_bytes,
            )
        )
    return datasets


def _scan_hf_cache() -> list[HFCachedRepo]:
    hf_home = os.environ.get("HF_HOME", "/workspace/.cache/huggingface/")
    cache_dir = Path(hf_home) / "hub"
    if not cache_dir.exists():
        logger.info("HF cache directory does not exist at %s", cache_dir)
        return []
    try:
        info = scan_cache_dir(str(cache_dir))
    except (OSError, RuntimeError, ValueError, CacheNotFound):
        logger.exception("Error scanning HF cache directory at %s", cache_dir)
        return []
    repos: list[HFCachedRepo] = []
    for repo in sorted(info.repos, key=lambda r: (r.repo_type, r.repo_id)):
        revision_hashes = sorted([rev.commit_hash for rev in repo.revisions])
        repos.append(
            HFCachedRepo(
                repo_id=repo.repo_id,
                repo_type=repo.repo_type,
                size_on_disk_bytes=int(repo.size_on_disk),
                revision_hashes=revision_hashes,
            )
        )
    return repos


def _list_s3_folder_entries(
    *,
    datasets_aws_folder: str,
    webhook_base_url: str,
    webhook_token: str,
    run_id: str,
) -> list[S3DatasetEntry]:
    """List S3 folder entries via the server's presigned URL endpoint."""
    if not webhook_base_url or not webhook_token or not run_id:
        logger.info("Missing webhook credentials for listing S3 datasets")
        return []

    url = f"{webhook_base_url.rstrip('/')}/{run_id}/list-datasets"
    headers = {
        "Authorization": f"Bearer {webhook_token}",
        "Content-Type": "application/json",
    }
    request_payload = ListDatasetsRequest(datasets_folder=datasets_aws_folder)

    try:
        response = requests.post(
            url, headers=headers, json=request_payload.model_dump(), timeout=60
        )
        response.raise_for_status()
        list_response = ListDatasetsResponse.model_validate(response.json())
    except requests.RequestException:
        logger.exception("Error listing S3 folder entries at %s", datasets_aws_folder)
        return []

    entries: list[S3DatasetEntry] = []
    for file_info in list_response.files:
        if len(entries) >= _MAX_S3_FOLDER_ENTRIES:
            break
        entries.append(
            S3DatasetEntry(
                s3_uri=file_info.download_url,  # Use presigned download URL
                size_on_disk_bytes=file_info.size,
            )
        )
    return entries


def build_s3_download_snippet(
    *,
    datasets_aws_folder: str,  # noqa: ARG001
    local_datasets_dir: Path,
    env_file: Path,
) -> str:
    local_dir_str = str(local_datasets_dir)
    env_file_str = str(env_file)
    return (
        "Python snippet (paste into your experiment script) to download from S3 into the local datasets cache:\n"
        "\n"
        "from pathlib import Path\n"
        "import requests\n"
        "import os\n"
        "from dotenv import load_dotenv\n"
        "\n"
        "env_file = Path(" + repr(env_file_str) + ")\n"
        "load_dotenv(dotenv_path=env_file, override=False)\n"
        "\n"
        "datasets_dir = Path(" + repr(local_dir_str) + ")\n"
        "dataset_name = 'my_dataset'\n"
        "destination_file = datasets_dir / dataset_name / 'data.csv'  # Adjust filename\n"
        "destination_file.parent.mkdir(parents=True, exist_ok=True)\n"
        "\n"
        "# Copy a presigned download URL from the 'S3 datasets directory' list above\n"
        "# The URLs in the list are presigned and can be used directly with requests\n"
        "download_url = '<PASTE_PRESIGNED_URL_FROM_LIST>'\n"
        "response = requests.get(download_url, timeout=600)\n"
        "response.raise_for_status()\n"
        "destination_file.write_bytes(response.content)\n"
        "print(f'Downloaded to {destination_file}')\n"
    )


def build_s3_upload_snippet(
    *,
    datasets_aws_folder: str,
    local_datasets_dir: Path,
    env_file: Path,
) -> str:
    folder = datasets_aws_folder.strip("/")
    local_dir_str = str(local_datasets_dir)
    env_file_str = str(env_file)
    return (
        "Python snippet (paste into your experiment script) to upload a file to S3 so future runs can use it:\n"
        "\n"
        "from pathlib import Path\n"
        "import requests\n"
        "import os\n"
        "from dotenv import load_dotenv\n"
        "\n"
        "env_file = Path(" + repr(env_file_str) + ")\n"
        "load_dotenv(dotenv_path=env_file, override=False)\n"
        "\n"
        "# File to upload\n"
        "datasets_dir = Path(" + repr(local_dir_str) + ")\n"
        "source_file = datasets_dir / 'my_dataset' / 'data.csv'  # Adjust path\n"
        "if not source_file.exists():\n"
        "    raise FileNotFoundError(f'Source file not found: {source_file}')\n"
        "\n"
        "# Request presigned upload URL from server\n"
        "webhook_url = os.environ.get('TELEMETRY_WEBHOOK_URL', '')\n"
        "webhook_token = os.environ.get('TELEMETRY_WEBHOOK_TOKEN', '')\n"
        "run_id = os.environ.get('RUN_ID', '')\n"
        "relative_path = 'my_dataset/data.csv'  # Path within datasets folder\n"
        "\n"
        "url_request = requests.post(\n"
        "    f'{webhook_url.rstrip(\"/\")}/{run_id}/dataset-upload-url',\n"
        "    headers={'Authorization': f'Bearer {webhook_token}', 'Content-Type': 'application/json'},\n"
        "    json={\n"
        "        'datasets_folder': " + repr(folder) + ",\n"
        "        'relative_path': relative_path,\n"
        "        'content_type': 'application/octet-stream',\n"
        "        'file_size': source_file.stat().st_size,\n"
        "    },\n"
        "    timeout=30,\n"
        ")\n"
        "url_request.raise_for_status()\n"
        "upload_url = url_request.json()['upload_url']\n"
        "\n"
        "# Upload file using presigned URL\n"
        "with open(source_file, 'rb') as f:\n"
        "    upload_response = requests.put(\n"
        "        upload_url,\n"
        "        data=f.read(),\n"
        "        headers={'Content-Type': 'application/octet-stream'},\n"
        "        timeout=3600,\n"
        "    )\n"
        "upload_response.raise_for_status()\n"
        "print(f'Uploaded {source_file} to S3')\n"
    )


def get_available_datasets(
    local_datasets_dir: Path, datasets_aws_folder: Optional[str]
) -> AvailableDatasets:
    env_file = get_research_pipeline_env_file()
    logger.info(f"Loading environment file: {env_file}")

    load_dotenv(dotenv_path=env_file, override=False)
    logger.info(f"Environment file loaded: {env_file}")

    hf_cache = _scan_hf_cache()
    local_datasets = _list_local_datasets(local_datasets_dir=local_datasets_dir)

    s3_folder_entries: list[S3DatasetEntry] = []
    if datasets_aws_folder:
        # Get webhook credentials from environment for server-side S3 listing
        webhook_base_url = os.environ.get("TELEMETRY_WEBHOOK_URL", "")
        webhook_token = os.environ.get("TELEMETRY_WEBHOOK_TOKEN", "")
        run_id = os.environ.get("RUN_ID", "")
        s3_folder_entries = _list_s3_folder_entries(
            datasets_aws_folder=datasets_aws_folder,
            webhook_base_url=webhook_base_url,
            webhook_token=webhook_token,
            run_id=run_id,
        )

    return AvailableDatasets(
        hf_cache=hf_cache,
        local_datasets=local_datasets,
        s3_folder_entries=s3_folder_entries,
    )
