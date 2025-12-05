import argparse
import os
import sys
from pathlib import Path
from typing import Sequence

from dotenv import load_dotenv

from ai_scientist.artifact_manager import ArtifactPublisher, ArtifactSpec

PROJECT_DIR = Path(__file__).resolve().parent
load_dotenv(PROJECT_DIR / ".env")
DEFAULT_WORKSPACE_PATH = PROJECT_DIR / "workspaces" / "0-run"
DEFAULT_EXCLUDES = (".venv", ".ai_scientist_venv")


def _require_env(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        raise SystemExit(f"Environment variable {name} is required")
    return value


def upload_workspace(
    *,
    workspace_path: Path,
    artifact_type: str,
    archive_name: str | None,
    exclude: Sequence[str],
) -> None:
    if not workspace_path.exists():
        print(f"[workspace] Path {workspace_path} does not exist; skipping upload.")
        return
    if not workspace_path.is_dir():
        print(f"[workspace] Path {workspace_path} is not a directory; skipping upload.")
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

    archive = archive_name or f"{workspace_path.name}-workspace.zip"
    try:
        publisher.publish(
            spec=ArtifactSpec(
                artifact_type=artifact_type,
                path=workspace_path,
                packaging="zip",
                archive_name=archive,
                exclude_dir_names=tuple(exclude),
            )
        )
        print(f"[workspace] Uploaded archive {archive} from {workspace_path} for run {run_id}.")
    finally:
        publisher.close()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Upload the research pipeline workspace directory as an artifact."
    )
    parser.add_argument(
        "--workspace-path",
        type=Path,
        default=DEFAULT_WORKSPACE_PATH,
        help="Path to the workspace directory to archive.",
    )
    parser.add_argument(
        "--artifact-type",
        default="workspace_archive",
        help="Artifact type to record in rp_artifacts.",
    )
    parser.add_argument(
        "--archive-name",
        default=None,
        help="Optional archive filename (defaults to <workspace>-workspace.zip).",
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
        upload_workspace(
            workspace_path=args.workspace_path,
            artifact_type=args.artifact_type,
            archive_name=args.archive_name,
            exclude=args.exclude,
        )
    except SystemExit as exc:
        print(f"[workspace] {exc}")
        sys.exit(exc.code if isinstance(exc.code, int) else 1)


if __name__ == "__main__":
    main()
