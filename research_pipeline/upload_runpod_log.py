import argparse
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

from ai_scientist.artifact_manager import ArtifactPublisher, ArtifactSpec

PROJECT_DIR = Path(__file__).resolve().parent
load_dotenv(PROJECT_DIR / ".env")


def _require_env(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        raise SystemExit(f"Environment variable {name} is required")
    return value


def upload_runlog(*, log_path: Path, artifact_type: str) -> None:
    if not log_path.exists():
        print(f"[runlog] Log file {log_path} not found; skipping upload.")
        return

    run_id = _require_env("RUN_ID")
    publisher = ArtifactPublisher(
        run_id=run_id,
        aws_access_key_id=_require_env("AWS_ACCESS_KEY_ID"),
        aws_secret_access_key=_require_env("AWS_SECRET_ACCESS_KEY"),
        aws_region=_require_env("AWS_REGION"),
        aws_s3_bucket_name=_require_env("AWS_S3_BUCKET_NAME"),
        database_url=_require_env("DATABASE_PUBLIC_URL"),
    )
    try:
        publisher.publish(
            spec=ArtifactSpec(
                artifact_type=artifact_type,
                path=log_path,
                packaging="file",
            )
        )
        print(f"[runlog] Uploaded {log_path} for run {run_id}.")
    finally:
        publisher.close()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Upload RunPod research_pipeline.log to S3 and record metadata."
    )
    parser.add_argument(
        "--log-path",
        default="/workspace/research_pipeline.log",
        type=Path,
        help="Path to the log file to upload.",
    )
    parser.add_argument(
        "--artifact-type",
        default="run_log",
        help="Artifact type label to record in rp_artifacts.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    try:
        upload_runlog(log_path=args.log_path, artifact_type=args.artifact_type)
    except SystemExit as exc:
        print(f"[runlog] {exc}")
        sys.exit(exc.code if isinstance(exc.code, int) else 1)


if __name__ == "__main__":
    main()
