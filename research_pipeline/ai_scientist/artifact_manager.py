"""
Collect and publish research pipeline artifacts.
"""

from __future__ import annotations

import logging
import shutil
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Literal
from zipfile import ZIP_DEFLATED, ZipFile

import boto3
import magic
import psycopg2

from ai_scientist.telemetry.event_persistence import _parse_database_url

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ArtifactUploadRequest:
    """Concrete upload payload."""

    artifact_type: str
    filename: str
    local_path: Path
    source_path: Path


@dataclass(frozen=True)
class ArtifactSpec:
    """Declarative description of an artifact to publish."""

    artifact_type: str
    path: Path
    packaging: Literal["file", "zip"] = "file"
    archive_name: str | None = None
    exclude_dir_names: tuple[str, ...] = tuple()


class S3ArtifactUploader:
    def __init__(
        self,
        *,
        bucket_name: str,
        region: str,
        aws_access_key_id: str,
        aws_secret_access_key: str,
    ) -> None:
        self._bucket_name = bucket_name
        self._client = boto3.client(
            "s3",
            aws_access_key_id=aws_access_key_id,
            aws_secret_access_key=aws_secret_access_key,
            region_name=region,
        )
        self._detector: magic.Magic | None
        try:
            self._detector = magic.Magic(mime=True)
        except Exception:
            self._detector = None

    def upload(self, *, request: ArtifactUploadRequest, run_id: str) -> tuple[str, str, int]:
        file_size = request.local_path.stat().st_size
        content_type = self._detect_content_type(path=request.local_path)
        s3_key = f"research-pipeline/{run_id}/{request.artifact_type}/{request.filename}"
        metadata = {
            "run_id": run_id,
            "artifact_type": request.artifact_type,
            "source_path": str(request.source_path),
        }
        sanitized_metadata = {
            key: self._sanitize_ascii(value=value) for key, value in metadata.items()
        }
        extra_args = {"ContentType": content_type, "Metadata": sanitized_metadata}
        self._client.upload_file(
            Filename=str(request.local_path),
            Bucket=self._bucket_name,
            Key=s3_key,
            ExtraArgs=extra_args,
        )
        return s3_key, content_type, file_size

    def _detect_content_type(self, *, path: Path) -> str:
        try:
            if self._detector is not None:
                return str(self._detector.from_file(filename=str(path)))
        except Exception:
            logger.exception("Failed to detect MIME type for artifact at %s", path)
        return "application/octet-stream"

    def _sanitize_ascii(self, *, value: str) -> str:
        try:
            value.encode("ascii")
            return value
        except Exception:
            normalized = value.encode("ascii", "ignore").decode("ascii")
            return normalized or "n/a"


class ArtifactRepository:
    def __init__(self, *, database_url: str) -> None:
        self._pg_config = _parse_database_url(database_url)

    def insert(
        self,
        *,
        run_id: str,
        artifact_type: str,
        filename: str,
        file_size: int,
        file_type: str,
        s3_key: str,
        source_path: str,
    ) -> None:
        with psycopg2.connect(**self._pg_config) as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO rp_artifacts (
                        run_id,
                        artifact_type,
                        filename,
                        file_size,
                        file_type,
                        s3_key,
                        source_path
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                    """,
                    (
                        run_id,
                        artifact_type,
                        filename,
                        file_size,
                        file_type,
                        s3_key,
                        source_path,
                    ),
                )
                conn.commit()


class ArtifactPublisher:
    """Uploads artifacts to S3 and stores metadata in Postgres."""

    def __init__(
        self,
        *,
        run_id: str,
        aws_access_key_id: str,
        aws_secret_access_key: str,
        aws_region: str,
        aws_s3_bucket_name: str,
        database_url: str,
    ) -> None:
        self._run_id = run_id
        self._temp_dir = Path(tempfile.mkdtemp(prefix="rp-artifacts-"))
        self._uploader = S3ArtifactUploader(
            bucket_name=aws_s3_bucket_name,
            region=aws_region,
            aws_access_key_id=aws_access_key_id,
            aws_secret_access_key=aws_secret_access_key,
        )
        self._repository = ArtifactRepository(database_url=database_url)

    def publish(self, *, spec: ArtifactSpec) -> None:
        request = self._build_request(spec=spec)
        if request is None:
            logger.info(
                "Skipping artifact %s because nothing was found at %s",
                spec.artifact_type,
                spec.path,
            )
            return
        logger.info("Uploading %s artifact from %s", spec.artifact_type, spec.path)
        s3_key, file_type, file_size = self._uploader.upload(request=request, run_id=self._run_id)
        self._repository.insert(
            run_id=self._run_id,
            artifact_type=spec.artifact_type,
            filename=request.filename,
            file_size=file_size,
            file_type=file_type,
            s3_key=s3_key,
            source_path=str(request.source_path),
        )

    def close(self) -> None:
        shutil.rmtree(self._temp_dir, ignore_errors=True)

    def _build_request(self, *, spec: ArtifactSpec) -> ArtifactUploadRequest | None:
        if spec.packaging == "zip":
            return self._build_zip_request(spec=spec)
        return self._build_file_request(spec=spec)

    def _build_zip_request(self, *, spec: ArtifactSpec) -> ArtifactUploadRequest | None:
        source_dir = spec.path
        if not source_dir.exists() or not source_dir.is_dir():
            logger.warning("Zip source missing for artifact %s: %s", spec.artifact_type, source_dir)
            return None
        exclude = set(spec.exclude_dir_names)
        if not self._directory_has_files(target=source_dir, excluded=exclude):
            return None
        archive_name = spec.archive_name or f"{source_dir.name}.zip"
        archive_path = self._temp_dir / archive_name
        files_added = 0
        with ZipFile(archive_path, mode="w", compression=ZIP_DEFLATED) as archive:
            for candidate in source_dir.rglob("*"):
                if not candidate.is_file():
                    continue
                relative_path = candidate.relative_to(source_dir)
                if self._is_excluded(relative_path=relative_path, excluded=exclude):
                    continue
                archive.write(candidate, arcname=str(relative_path))
                files_added += 1
        if files_added == 0:
            archive_path.unlink(missing_ok=True)
            return None
        return ArtifactUploadRequest(
            artifact_type=spec.artifact_type,
            filename=archive_name,
            local_path=archive_path,
            source_path=source_dir,
        )

    def _build_file_request(self, *, spec: ArtifactSpec) -> ArtifactUploadRequest | None:
        file_path = spec.path
        if not file_path.exists() or not file_path.is_file():
            logger.warning("Artifact file not found for %s: %s", spec.artifact_type, file_path)
            return None
        return ArtifactUploadRequest(
            artifact_type=spec.artifact_type,
            filename=file_path.name,
            local_path=file_path,
            source_path=file_path,
        )

    def _directory_has_files(self, *, target: Path, excluded: set[str]) -> bool:
        for candidate in target.rglob("*"):
            if not candidate.is_file():
                continue
            relative_path = candidate.relative_to(target)
            if not self._is_excluded(relative_path=relative_path, excluded=excluded):
                return True
        return False

    def _is_excluded(self, *, relative_path: Path, excluded: set[str]) -> bool:
        return any(part in excluded for part in relative_path.parts)
