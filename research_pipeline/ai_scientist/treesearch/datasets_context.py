import logging
import os
import re
import subprocess
from pathlib import Path
from typing import NamedTuple, Optional

from dotenv import load_dotenv
from huggingface_hub import scan_cache_dir

logger = logging.getLogger("ai-scientist")
_S5CMD_LINE_RE = re.compile(r"^\S+\s+\S+\s+(?P<size>\d+)\s+(?P<uri>s3://\S+)$")


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
        return []
    try:
        info = scan_cache_dir(str(cache_dir))
    except (OSError, RuntimeError, ValueError):
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
) -> list[S3DatasetEntry]:
    s3_bucket_name = str(os.environ.get("AWS_S3_BUCKET_NAME", "")).strip()
    if not s3_bucket_name:
        return []
    folder = datasets_aws_folder.strip("/")
    s3_uri = f"s3://{s3_bucket_name}/{folder}/"
    try:
        proc = subprocess.run(
            ["s5cmd", "ls", s3_uri],
            check=False,
            capture_output=True,
            text=True,
        )
    except OSError:
        return []
    if proc.returncode != 0:
        return []
    entries: list[S3DatasetEntry] = []
    for line in proc.stdout.splitlines():
        m = _S5CMD_LINE_RE.match(line.strip())
        if not m:
            continue
        entries.append(
            S3DatasetEntry(
                s3_uri=m.group("uri"),
                size_on_disk_bytes=int(m.group("size")),
            )
        )
    return entries


def build_s3_download_snippet(
    *,
    datasets_aws_folder: str,
    local_datasets_dir: Path,
    env_file: Path,
) -> str:
    folder = datasets_aws_folder.strip("/")
    local_dir_str = str(local_datasets_dir)
    env_file_str = str(env_file)
    return (
        "Python snippet (paste into your experiment script) to download from S3 into the local datasets cache:\n"
        "\n"
        "from pathlib import Path\n"
        "import subprocess\n"
        "import os\n"
        "from dotenv import load_dotenv\n"
        "\n"
        "env_file = Path(" + repr(env_file_str) + ")\n"
        "load_dotenv(dotenv_path=env_file, override=False)\n"
        "\n"
        "datasets_dir = Path(" + repr(local_dir_str) + ")\n"
        "dataset_name = 'my_dataset'\n"
        "destination_dir = datasets_dir / dataset_name\n"
        "destination_dir.mkdir(parents=True, exist_ok=True)\n"
        "\n"
        "# Choose an S3 object from the 'S3 datasets directory' list above\n"
        "s3_bucket = os.environ.get('AWS_S3_BUCKET_NAME', '')\n"
        "if not s3_bucket:\n"
        "    raise RuntimeError('AWS_S3_BUCKET_NAME is not set')\n"
        "s3_source = f's3://{s3_bucket}/" + folder + "/<CHOOSE_FROM_LIST>'\n"
        "subprocess.run(['s5cmd', 'cp', s3_source, str(destination_dir) + '/'], check=True)\n"
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
        "Python snippet (paste into your experiment script) to upload a local dataset folder to S3 so future runs can use it:\n"
        "\n"
        "from pathlib import Path\n"
        "import subprocess\n"
        "import os\n"
        "from dotenv import load_dotenv\n"
        "\n"
        "env_file = Path(" + repr(env_file_str) + ")\n"
        "load_dotenv(dotenv_path=env_file, override=False)\n"
        "\n"
        "datasets_dir = Path(" + repr(local_dir_str) + ")\n"
        "dataset_name = 'my_dataset'\n"
        "source_dir = datasets_dir / dataset_name\n"
        "if not source_dir.exists():\n"
        "    raise FileNotFoundError(f'Local dataset folder not found: {source_dir}')\n"
        "\n"
        "s3_bucket = os.environ.get('AWS_S3_BUCKET_NAME', '')\n"
        "if not s3_bucket:\n"
        "    raise RuntimeError('AWS_S3_BUCKET_NAME is not set')\n"
        "\n"
        "# Upload the entire dataset folder under the configured S3 datasets directory\n"
        "s3_destination = f's3://{s3_bucket}/" + folder + "/{dataset_name}/'\n"
        "subprocess.run(['s5cmd', 'sync', str(source_dir) + '/', s3_destination], check=True)\n"
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
        s3_folder_entries = _list_s3_folder_entries(
            datasets_aws_folder=datasets_aws_folder,
        )

    return AvailableDatasets(
        hf_cache=hf_cache,
        local_datasets=local_datasets,
        s3_folder_entries=s3_folder_entries,
    )
