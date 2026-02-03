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
from typing import NamedTuple

from app.config import settings
from app.services.s3_service import get_s3_service


class CodeTarballInfo(NamedTuple):
    """Information about the code tarball for a pod."""

    url: str
    commit_hash: str


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
    """Get the current git commit hash.

    Checks in order:
    1. RAILWAY_GIT_COMMIT_SHA environment variable (set by Railway)
    2. Running `git rev-parse HEAD` command
    3. Fallback to timestamp-based identifier
    """
    # Check Railway environment variable first (git may not be installed in container)
    if settings.railway_git_commit_sha:
        return settings.railway_git_commit_sha[:12]

    # Try git command
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            check=True,
            cwd=Path(__file__).resolve().parents[5],  # repo root
        )
        return result.stdout.strip()[:12]  # Short hash
    except (subprocess.CalledProcessError, FileNotFoundError) as e:
        logger.warning("Failed to get git commit hash: %s", e)
        # Fallback to a timestamp-based identifier
        return f"unknown-{int(time.time())}"


def _get_research_pipeline_path() -> Path:
    """Get the path to the research_pipeline directory.

    Checks in order:
    1. RESEARCH_PIPELINE_PATH environment variable (set in Docker)
    2. Navigate from this file to repo root (for local development)
    """
    if settings.research_pipeline.path:
        research_pipeline_path = Path(settings.research_pipeline.path)
        if research_pipeline_path.exists():
            return research_pipeline_path
        raise RuntimeError(
            f"RESEARCH_PIPELINE_PATH set but directory not found: {settings.research_pipeline.path}"
        )

    # Fallback for local development: navigate from this file to repo root
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


def _get_ae_paper_review_path() -> Path | None:
    """Get the path to the ae-paper-review package.

    Returns None if the package directory doesn't exist.
    """
    repo_root = Path(__file__).resolve().parents[5]
    package_path = repo_root / "packages" / "ae-paper-review"
    if package_path.exists():
        return package_path
    logger.warning("ae-paper-review package not found at %s", package_path)
    return None


def _create_tarball(research_pipeline_path: Path) -> bytes:
    """Create a tarball of the research_pipeline and ae-paper-review directories.

    The tarball uses the path structure:
    - AE-Scientist/research_pipeline/...
    - AE-Scientist/packages/ae-paper-review/...

    When extracted to /workspace/, it creates:
    - /workspace/AE-Scientist/research_pipeline/
    - /workspace/AE-Scientist/packages/ae-paper-review/
    """
    buffer = io.BytesIO()

    with tarfile.open(fileobj=buffer, mode="w:gz") as tar:
        # Add research_pipeline files
        for item in research_pipeline_path.rglob("*"):
            if item.is_file() and not _should_exclude(item, research_pipeline_path):
                arcname = (
                    f"AE-Scientist/research_pipeline/{item.relative_to(research_pipeline_path)}"
                )
                tar.add(item, arcname=arcname)
                logger.debug("Added to tarball: %s", arcname)

        # Add ae-paper-review package files
        ae_paper_review_path = _get_ae_paper_review_path()
        if ae_paper_review_path:
            for item in ae_paper_review_path.rglob("*"):
                if item.is_file() and not _should_exclude(item, ae_paper_review_path):
                    arcname = (
                        f"AE-Scientist/packages/ae-paper-review/"
                        f"{item.relative_to(ae_paper_review_path)}"
                    )
                    tar.add(item, arcname=arcname)
                    logger.debug("Added to tarball: %s", arcname)
        else:
            logger.warning(
                "ae-paper-review package not found; tarball will not include shared review package"
            )

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


def _is_using_fake_runpod() -> bool:
    """Check if the fake runpod is being used (for local development)."""
    return settings.runpod.uses_fake_runpod


def get_code_tarball_info() -> CodeTarballInfo:
    """
    Get information about the research_pipeline code tarball.

    Assumes the tarball has already been uploaded via ensure_code_tarball_uploaded().
    This is safe to call from multiple worker processes - it only generates a URL.

    Returns:
        CodeTarballInfo with presigned URL (valid for 2 hours) and commit hash
    """
    commit_hash = _get_git_commit_hash()

    # When using fake runpod locally, skip the S3 tarball check since the code
    # is already available locally
    if _is_using_fake_runpod():
        logger.info("Fake runpod detected, skipping code tarball S3 check")
        return CodeTarballInfo(url="", commit_hash=commit_hash)

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

    return CodeTarballInfo(url=presigned_url, commit_hash=commit_hash)
