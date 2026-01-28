"""
Collect and publish research pipeline artifacts.
"""

import logging
import shutil
import tempfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal
from zipfile import ZIP_DEFLATED, ZipFile

import magic
import requests
from tenacity import (
    before_sleep_log,
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from ai_scientist.api_types import (
    ArtifactUploadedEvent,
    PresignedUploadUrlRequest,
    PresignedUploadUrlResponse,
)
from ai_scientist.telemetry.event_persistence import WebhookClient

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
    packaging: Literal["file", "zip"]
    archive_name: str | None
    exclude_dir_names: tuple[str, ...]


class PresignedUrlUploader:
    """Uploads artifacts to S3 using presigned URLs obtained from the server."""

    def __init__(
        self,
        *,
        webhook_base_url: str,
        webhook_token: str,
        run_id: str,
    ) -> None:
        self._webhook_base_url = webhook_base_url.rstrip("/")
        self._webhook_token = webhook_token
        self._run_id = run_id
        self._detector: magic.Magic | None
        try:
            self._detector = magic.Magic(mime=True)
        except Exception:
            self._detector = None

    def upload(self, *, request: ArtifactUploadRequest) -> tuple[str, str, int]:
        """Upload file using presigned URL."""
        file_size = request.local_path.stat().st_size
        content_type = self._detect_content_type(path=request.local_path)

        presigned_response = self._request_presigned_url(
            artifact_type=request.artifact_type,
            filename=request.filename,
            content_type=content_type,
            file_size=file_size,
            source_path=str(request.source_path),
        )

        self._upload_with_presigned_url(
            upload_url=presigned_response.upload_url,
            local_path=request.local_path,
            content_type=content_type,
        )

        return presigned_response.s3_key, content_type, file_size

    @retry(
        retry=retry_if_exception_type(requests.RequestException),
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, max=10),
        reraise=True,
    )
    def _request_presigned_url(
        self,
        *,
        artifact_type: str,
        filename: str,
        content_type: str,
        file_size: int,
        source_path: str,
    ) -> PresignedUploadUrlResponse:
        """Request a presigned upload URL from the server."""
        url = f"{self._webhook_base_url}/{self._run_id}/presigned-upload-url"
        headers = {
            "Authorization": f"Bearer {self._webhook_token}",
            "Content-Type": "application/json",
        }
        # Use generated type for request validation
        request_payload = PresignedUploadUrlRequest(
            artifact_type=artifact_type,
            filename=filename,
            content_type=content_type,
            file_size=file_size,
            metadata={"source_path": source_path},
        )
        response = requests.post(
            url, headers=headers, json=request_payload.model_dump(), timeout=30
        )
        response.raise_for_status()
        # Use generated type for response validation
        return PresignedUploadUrlResponse.model_validate(response.json())

    @retry(
        retry=retry_if_exception_type((requests.RequestException, OSError)),
        stop=stop_after_attempt(5),
        wait=wait_exponential(multiplier=2, max=60),
        before_sleep=before_sleep_log(logger, logging.WARNING),
        reraise=True,
    )
    def _upload_with_presigned_url(
        self,
        *,
        upload_url: str,
        local_path: Path,
        content_type: str,
    ) -> None:
        """Upload file content to S3 using presigned URL.

        Streams the file directly to avoid loading large files into memory.
        Includes retry logic for transient SSL/network errors.
        """
        file_size = local_path.stat().st_size
        headers = {
            "Content-Type": content_type,
            "Content-Length": str(file_size),
        }
        logger.info(
            "Uploading %s (%d bytes) via presigned URL",
            local_path.name,
            file_size,
        )
        try:
            with open(local_path, "rb") as f:
                response = requests.put(
                    upload_url,
                    data=f,  # Stream the file directly instead of reading into memory
                    headers=headers,
                    timeout=3600,  # 1 hour for large uploads
                )
            response.raise_for_status()
        except Exception:
            logger.exception(
                "Failed to upload %s (%d bytes) to presigned URL",
                local_path.name,
                file_size,
            )
            raise
        logger.info("Successfully uploaded file via presigned URL: %s", local_path)

    def _detect_content_type(self, *, path: Path) -> str:
        try:
            if self._detector is not None:
                return str(self._detector.from_file(filename=str(path)))
        except Exception:
            logger.exception("Failed to detect MIME type for artifact at %s", path)
        return "application/octet-stream"


class ArtifactPublisher:
    """Uploads artifacts to S3 via presigned URLs and publishes metadata via webhooks."""

    def __init__(
        self,
        *,
        run_id: str,
        webhook_base_url: str,
        webhook_token: str,
        webhook_client: WebhookClient | None,
    ) -> None:
        self._run_id = run_id
        self._temp_dir = Path(tempfile.mkdtemp(prefix="rp-artifacts-"))
        self._uploader = PresignedUrlUploader(
            webhook_base_url=webhook_base_url,
            webhook_token=webhook_token,
            run_id=run_id,
        )
        self._webhook_client = webhook_client

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
        s3_key, file_type, file_size = self._uploader.upload(request=request)
        created_at = datetime.now(timezone.utc).isoformat()

        if self._webhook_client is not None:
            try:
                self._webhook_client.publish(
                    kind="artifact_uploaded",
                    payload=ArtifactUploadedEvent(
                        artifact_type=spec.artifact_type,
                        filename=request.filename,
                        file_size=file_size,
                        file_type=file_type,
                        created_at=created_at,
                    ),
                )
                logger.info("Emitted artifact SSE event for %s", request.filename)
            except Exception:
                logger.exception("Failed to emit artifact SSE event (non-fatal)")
        else:
            logger.warning(
                "No webhook client available to emit artifact SSE event for artifact_type=%s, filename=%s, file_size=%s, file_type=%s",
                spec.artifact_type,
                request.filename,
                file_size,
                file_type,
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
