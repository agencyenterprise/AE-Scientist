import argparse
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

from ai_scientist.artifact_manager import ArtifactPublisher, ArtifactSpec
from ai_scientist.telemetry.event_persistence import WebhookClient

PROJECT_DIR = Path(__file__).resolve().parent
load_dotenv(PROJECT_DIR / ".env")


def _require_env(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        raise SystemExit(f"Environment variable {name} is required")
    return value


def upload_file(*, file_path: Path, artifact_type: str) -> None:
    if not file_path.exists():
        print(f"[file] File {file_path} not found; skipping upload.")
        return

    run_id = _require_env("RUN_ID")

    # Note: This script only uploads to S3. Database persistence happens via webhooks.
    # If you need webhook support, set TELEMETRY_WEBHOOK_URL and TELEMETRY_WEBHOOK_TOKEN.
    webhook_url = os.environ.get("TELEMETRY_WEBHOOK_URL")
    webhook_token = os.environ.get("TELEMETRY_WEBHOOK_TOKEN")
    webhook_client = None
    if webhook_url and webhook_token:
        webhook_client = WebhookClient(base_url=webhook_url, token=webhook_token, run_id=run_id)

    publisher = ArtifactPublisher(
        run_id=run_id,
        aws_access_key_id=_require_env("AWS_ACCESS_KEY_ID"),
        aws_secret_access_key=_require_env("AWS_SECRET_ACCESS_KEY"),
        aws_region=_require_env("AWS_REGION"),
        aws_s3_bucket_name=_require_env("AWS_S3_BUCKET_NAME"),
        webhook_client=webhook_client,
    )
    try:
        publisher.publish(
            spec=ArtifactSpec(
                artifact_type=artifact_type,
                path=file_path,
                packaging="file",
            )
        )
        print(f"[file] Uploaded {file_path} for run {run_id}.")
    finally:
        publisher.close()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Upload file to S3 and record metadata.")
    parser.add_argument(
        "--file-path",
        type=Path,
        required=True,
        help="Path to the file to upload.",
    )
    parser.add_argument(
        "--artifact-type",
        required=True,
        help="Artifact type label to record in rp_artifacts.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    try:
        upload_file(file_path=args.file_path, artifact_type=args.artifact_type)
    except SystemExit as exc:
        print(f"[file] {exc}")
        sys.exit(exc.code if isinstance(exc.code, int) else 1)


if __name__ == "__main__":
    main()
