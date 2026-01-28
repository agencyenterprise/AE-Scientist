"""
Packages the research_pipeline folder as a tarball and uploads to S3 for RunPod pods.

Uses git commit hash as a cache key to avoid re-uploading the same code version.
"""

import io
import logging
import subprocess
import tarfile
import time
from pathlib import Path

from app.services.s3_service import get_s3_service

logger = logging.getLogger(__name__)

# Directories/files to exclude from the tarball
EXCLUDE_PATTERNS = {
    ".venv",
    "__pycache__",
    ".mypy_cache",
    ".ruff_cache",
    ".pytest_cache",
    ".git",
    ".env",
    "*.pyc",
    "*.pyo",
    "*.egg-info",
    ".DS_Store",
}

# S3 key prefix for code tarballs
CODE_TARBALL_PREFIX = "run-code"

# Presigned URL expiration (2 hours)
PRESIGNED_URL_EXPIRY_SECONDS = 7200


def _get_git_commit_hash() -> str:
    """Get the current git commit hash."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            check=True,
            cwd=Path(__file__).resolve().parents[5],  # repo root
        )
        return result.stdout.strip()[:12]  # Short hash
    except subprocess.CalledProcessError as e:
        logger.warning("Failed to get git commit hash: %s", e)
        # Fallback to a timestamp-based identifier
        return f"unknown-{int(time.time())}"


def _get_research_pipeline_path() -> Path:
    """Get the path to the research_pipeline directory."""
    # Navigate from this file to the repo root, then to research_pipeline
    repo_root = Path(__file__).resolve().parents[5]
    research_pipeline_path = repo_root / "research_pipeline"
    if not research_pipeline_path.exists():
        raise RuntimeError(f"research_pipeline directory not found at {research_pipeline_path}")
    return research_pipeline_path


def _should_exclude(path: Path, base_path: Path) -> bool:
    """Check if a path should be excluded from the tarball."""
    rel_path = path.relative_to(base_path)

    # Check each part of the path against exclude patterns
    for part in rel_path.parts:
        if part in EXCLUDE_PATTERNS:
            return True
        # Check wildcard patterns
        for pattern in EXCLUDE_PATTERNS:
            if pattern.startswith("*") and part.endswith(pattern[1:]):
                return True

    return False


def _create_tarball(research_pipeline_path: Path) -> bytes:
    """Create a tarball of the research_pipeline directory, excluding unnecessary files.

    The tarball uses the path structure AE-Scientist/research_pipeline/... so that
    when extracted to /workspace/, it creates /workspace/AE-Scientist/research_pipeline/.
    """
    buffer = io.BytesIO()

    with tarfile.open(fileobj=buffer, mode="w:gz") as tar:
        for item in research_pipeline_path.rglob("*"):
            if item.is_file() and not _should_exclude(item, research_pipeline_path):
                arcname = (
                    f"AE-Scientist/research_pipeline/{item.relative_to(research_pipeline_path)}"
                )
                tar.add(item, arcname=arcname)
                logger.debug("Added to tarball: %s", arcname)

    buffer.seek(0)
    return buffer.read()


def _get_s3_key(commit_hash: str) -> str:
    """Get the S3 key for a code tarball."""
    return f"{CODE_TARBALL_PREFIX}/{commit_hash}/research_pipeline.tar.gz"


def ensure_code_tarball_uploaded() -> str:
    """
    Ensure the code tarball is uploaded to S3. Call this once during deployment.

    This function:
    1. Gets the current git commit hash
    2. Checks if the tarball already exists in S3
    3. If not, creates and uploads it

    Returns:
        The S3 key of the uploaded tarball
    """
    commit_hash = _get_git_commit_hash()
    s3_key = _get_s3_key(commit_hash)
    s3_service = get_s3_service()

    if s3_service.file_exists(s3_key):
        logger.info("Code tarball already exists in S3: %s", s3_key)
    else:
        logger.info("Creating and uploading code tarball for commit %s", commit_hash)
        research_pipeline_path = _get_research_pipeline_path()
        tarball_data = _create_tarball(research_pipeline_path)

        s3_service.s3_client.put_object(
            Bucket=s3_service.bucket_name,
            Key=s3_key,
            Body=tarball_data,
            ContentType="application/gzip",
            Metadata={
                "commit_hash": commit_hash,
                "source": "code_packager",
            },
        )
        logger.info("Uploaded code tarball to S3: %s (size: %d bytes)", s3_key, len(tarball_data))

    return s3_key


def get_code_tarball_url() -> str:
    """
    Get a presigned URL for the research_pipeline code tarball.

    Assumes the tarball has already been uploaded via ensure_code_tarball_uploaded().
    This is safe to call from multiple worker processes - it only generates a URL.

    Returns:
        Presigned S3 URL for the code tarball (valid for 2 hours)
    """
    commit_hash = _get_git_commit_hash()
    s3_key = _get_s3_key(commit_hash)
    s3_service = get_s3_service()

    if not s3_service.file_exists(s3_key):
        raise RuntimeError(
            f"Code tarball not found in S3: {s3_key}. "
            "Run 'python -m app.cli.upload_code_tarball' during deployment."
        )

    presigned_url = s3_service.generate_download_url(s3_key, PRESIGNED_URL_EXPIRY_SECONDS)
    logger.debug(
        "Generated presigned URL for code tarball (expires in %ds)", PRESIGNED_URL_EXPIRY_SECONDS
    )

    return presigned_url
