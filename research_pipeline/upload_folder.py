import argparse
import os
import sys
from pathlib import Path
from typing import Sequence

from dotenv import load_dotenv

from ai_scientist.artifact_manager import ArtifactPublisher, ArtifactSpec

PROJECT_DIR = Path(__file__).resolve().parent
load_dotenv(PROJECT_DIR / ".env")
DEFAULT_EXCLUDES = (".venv", ".ai_scientist_venv")


def _require_env(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        raise SystemExit(f"Environment variable {name} is required")
    return value


def upload_folder(
    *,
    folder_path: Path,
    artifact_type: str,
    archive_name: str,
    exclude: Sequence[str],
) -> None:
    if not folder_path.exists():
        print(f"[folder] Path {folder_path} does not exist; skipping upload.")
        return
    if not folder_path.is_dir():
        print(f"[folder] Path {folder_path} is not a directory; skipping upload.")
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
                path=folder_path,
                packaging="zip",
                archive_name=archive_name,
                exclude_dir_names=tuple(exclude),
            )
        )
        print(f"[folder] Uploaded archive {archive_name} from {folder_path} for run {run_id}.")
    finally:
        publisher.close()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Upload a folder as an artifact.")
    parser.add_argument(
        "--folder-path",
        type=Path,
        required=True,
        help="Path to the folder to archive.",
    )
    parser.add_argument(
        "--artifact-type",
        required=True,
        help="Artifact type to record in rp_artifacts.",
    )
    parser.add_argument(
        "--archive-name",
        required=True,
        help="Optional archive filename (defaults to <folder>-folder.zip).",
    )
    parser.add_argument(
        "--exclude",
        action="append",
        default=list(DEFAULT_EXCLUDES),
        help="Directory names to exclude from the archive (can be repeated).",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    try:
        upload_folder(
            folder_path=args.folder_path,
            artifact_type=args.artifact_type,
            archive_name=args.archive_name,
            exclude=args.exclude,
        )
    except SystemExit as exc:
        print(f"[folder] {exc}")
        sys.exit(exc.code if isinstance(exc.code, int) else 1)


if __name__ == "__main__":
    main()
