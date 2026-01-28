import argparse
import os
import sys
from pathlib import Path

import requests
from dotenv import load_dotenv
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from ai_scientist.api_types import ParentRunFileInfo, ParentRunFilesRequest, ParentRunFilesResponse

PROJECT_DIR = Path(__file__).resolve().parent
load_dotenv(PROJECT_DIR / ".env")


def _require_env(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        raise SystemExit(f"Environment variable {name} is required")
    return value


@retry(
    retry=retry_if_exception_type(requests.RequestException),
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, max=10),
    reraise=True,
)
def fetch_parent_run_files(
    *,
    webhook_base_url: str,
    webhook_token: str,
    run_id: str,
    parent_run_id: str,
) -> list[ParentRunFileInfo]:
    """Fetch list of files from parent run with presigned download URLs."""
    url = f"{webhook_base_url.rstrip('/')}/{run_id}/parent-run-files"
    headers = {
        "Authorization": f"Bearer {webhook_token}",
        "Content-Type": "application/json",
    }
    # Use generated type for request validation
    request_payload = ParentRunFilesRequest(parent_run_id=parent_run_id)
    response = requests.post(url, headers=headers, json=request_payload.model_dump(), timeout=60)
    response.raise_for_status()
    # Use generated type for response validation
    files_response = ParentRunFilesResponse.model_validate(response.json())
    return files_response.files


@retry(
    retry=retry_if_exception_type(requests.RequestException),
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, max=30),
    reraise=True,
)
def download_file(*, download_url: str, output_path: Path) -> None:
    """Download a file using a presigned URL."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    response = requests.get(download_url, timeout=600, stream=True)
    response.raise_for_status()
    with open(output_path, "wb") as f:
        for chunk in response.iter_content(chunk_size=8192):
            f.write(chunk)


def download_parent_run(*, parent_run_id: str, output_dir: Path) -> None:
    """Download all files from a parent run to the output directory."""
    run_id = _require_env("RUN_ID")
    webhook_url = _require_env("TELEMETRY_WEBHOOK_URL")
    webhook_token = _require_env("TELEMETRY_WEBHOOK_TOKEN")

    print(f"[parent-run] Fetching file list for parent run {parent_run_id}...")
    files = fetch_parent_run_files(
        webhook_base_url=webhook_url,
        webhook_token=webhook_token,
        run_id=run_id,
        parent_run_id=parent_run_id,
    )

    if not files:
        print(f"[parent-run] No files found for parent run {parent_run_id}.")
        return

    print(f"[parent-run] Found {len(files)} files to download.")

    prefix = f"research-pipeline/{parent_run_id}/"
    for file_info in files:
        relative_path = file_info.s3_key
        if relative_path.startswith(prefix):
            relative_path = relative_path[len(prefix) :]

        output_path = output_dir / relative_path
        print(f"[parent-run] Downloading {file_info.s3_key} ({file_info.size} bytes)...")
        download_file(download_url=file_info.download_url, output_path=output_path)

    print(f"[parent-run] Downloaded {len(files)} files to {output_dir}.")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Download parent run data using presigned URLs.")
    parser.add_argument(
        "--parent-run-id",
        required=True,
        help="ID of the parent run to download data from.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        required=True,
        help="Output directory for downloaded files.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    try:
        download_parent_run(parent_run_id=args.parent_run_id, output_dir=args.output)
    except SystemExit as exc:
        print(f"[parent-run] {exc}")
        sys.exit(exc.code if isinstance(exc.code, int) else 1)
    except Exception as exc:
        print(f"[parent-run] Error: {exc}")
        sys.exit(1)


if __name__ == "__main__":
    main()
