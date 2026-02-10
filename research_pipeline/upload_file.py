import argparse
import logging
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

from ai_scientist.api_types import ArtifactType
from ai_scientist.artifact_manager import ArtifactPublisher, ArtifactSpec
from ai_scientist.telemetry.event_persistence import WebhookClient

# Configure logging to output to stderr so errors are visible in upload logs
logging.basicConfig(
    level=logging.INFO,
    format="[%(levelname)s] %(name)s: %(message)s",
    stream=sys.stderr,
)

PROJECT_DIR = Path(__file__).resolve().parent
load_dotenv(PROJECT_DIR / ".env")


def _require_env(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        raise SystemExit(f"Environment variable {name} is required")
    return value


def upload_file(*, file_path: Path, artifact_type: ArtifactType) -> None:
    logger = logging.getLogger(__name__)
    logger.info("[file] Starting upload: file_path=%s, artifact_type=%s", file_path, artifact_type)

    if not file_path.exists():
        logger.warning("[file] File %s not found; skipping upload.", file_path)
        print(f"[file] File {file_path} not found; skipping upload.")
        return

    run_id = _require_env("RUN_ID")
    webhook_url = _require_env("TELEMETRY_WEBHOOK_URL")
    webhook_token = _require_env("TELEMETRY_WEBHOOK_TOKEN")

    logger.info("[file] Configuration: run_id=%s, webhook_url=%s", run_id, webhook_url)

    webhook_client = WebhookClient(base_url=webhook_url, token=webhook_token, run_id=run_id)

    publisher = ArtifactPublisher(
        run_id=run_id,
        webhook_base_url=webhook_url,
        webhook_token=webhook_token,
        webhook_client=webhook_client,
    )
    try:
        logger.info("[file] Calling publisher.publish() for artifact_type=%s", artifact_type)
        future = publisher.publish(
            spec=ArtifactSpec(
                artifact_type=artifact_type,
                path=file_path,
                packaging="file",
                archive_name=None,
                exclude_dir_names=(),
            )
        )
        logger.info("[file] publisher.publish() returned future=%s", future)

        # Wait for the webhook to complete so the artifact is recorded in the database
        # before the script exits. The webhook runs in a daemon thread which would be
        # killed if we exit without waiting.
        if future is not None:
            logger.info("[file] Waiting for webhook Future to complete...")
            try:
                future.result(timeout=60)  # Wait up to 60 seconds for webhook
                logger.info("[file] Webhook Future completed successfully")
            except Exception:
                logger.exception(
                    "[file] Webhook notification failed (artifact uploaded to S3 but may not appear in DB)"
                )
        else:
            logger.info(
                "[file] No webhook Future returned (artifact may have been skipped or no webhook client)"
            )

        print(f"[file] Uploaded {file_path} for run {run_id}.")
        logger.info("[file] Upload complete for %s", file_path)
    finally:
        publisher.close()
        logger.info("[file] Publisher closed")


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
        upload_file(file_path=args.file_path, artifact_type=ArtifactType(args.artifact_type))
    except SystemExit as exc:
        print(f"[file] {exc}")
        sys.exit(exc.code if isinstance(exc.code, int) else 1)


if __name__ == "__main__":
    main()
