"""
Collect and publish research pipeline artifacts.
"""

import logging
import math
import shutil
import tempfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Literal
from zipfile import ZIP_DEFLATED, ZipFile

import humanize
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
    ArtifactExistsRequest,
    ArtifactExistsResponse,
    ArtifactUploadedEvent,
    MultipartUploadCompleteRequest,
    MultipartUploadInitRequest,
    MultipartUploadInitResponse,
    MultipartUploadPart,
    PresignedUploadUrlRequest,
    PresignedUploadUrlResponse,
    RunLogEvent,
)
from ai_scientist.telemetry.event_persistence import WebhookClient

logger = logging.getLogger(__name__)

# Threshold for using multipart upload (100 MB)
MULTIPART_THRESHOLD_BYTES = 100 * 1024 * 1024

# Part size for multipart upload (100 MB)
MULTIPART_PART_SIZE_BYTES = 100 * 1024 * 1024


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
        progress_callback: Callable[[str], None],
    ) -> None:
        self._webhook_base_url = webhook_base_url.rstrip("/")
        self._webhook_token = webhook_token
        self._run_id = run_id
        self._progress_callback = progress_callback
        self._detector: magic.Magic | None
        try:
            self._detector = magic.Magic(mime=True)
        except Exception:
            self._detector = None

    def _log_progress(self, message: str) -> None:
        """Log progress message and call callback if available."""
        logger.info(message)
        print(message, flush=True)
        self._progress_callback(message)

    def upload(self, *, request: ArtifactUploadRequest) -> tuple[str, str, int]:
        """Upload file using presigned URL or multipart upload for large files."""
        file_size = request.local_path.stat().st_size
        content_type = self._detect_content_type(path=request.local_path)

        # Use multipart upload for large files
        if file_size > MULTIPART_THRESHOLD_BYTES:
            self._log_progress(
                f"[upload] Starting multipart upload for {request.filename} "
                f"({humanize.naturalsize(file_size, binary=True)})"
            )
            return self._upload_multipart(
                request=request,
                content_type=content_type,
                file_size=file_size,
            )

        # Use simple presigned URL upload for smaller files
        self._log_progress(
            f"[upload] Starting upload for {request.filename} ({humanize.naturalsize(file_size, binary=True)})"
        )
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

        self._log_progress(f"[upload] Completed upload for {request.filename}")
        return presigned_response.s3_key, content_type, file_size

    def _upload_multipart(
        self,
        *,
        request: ArtifactUploadRequest,
        content_type: str,
        file_size: int,
    ) -> tuple[str, str, int]:
        """Upload large file using multipart upload."""
        num_parts = math.ceil(file_size / MULTIPART_PART_SIZE_BYTES)

        self._log_progress(
            f"[upload] Initiating multipart upload: {num_parts} parts of "
            f"{humanize.naturalsize(MULTIPART_PART_SIZE_BYTES, binary=True)} each"
        )

        # Request multipart upload initialization
        init_response = self._init_multipart_upload(
            artifact_type=request.artifact_type,
            filename=request.filename,
            content_type=content_type,
            file_size=file_size,
            num_parts=num_parts,
            source_path=str(request.source_path),
        )

        upload_id = init_response.upload_id
        s3_key = init_response.s3_key
        part_urls = {p.part_number: p.upload_url for p in init_response.part_urls}

        completed_parts: list[MultipartUploadPart] = []

        try:
            # Upload each part
            with open(request.local_path, "rb") as f:
                for part_num in range(1, num_parts + 1):
                    # Calculate part size (last part may be smaller)
                    part_start = (part_num - 1) * MULTIPART_PART_SIZE_BYTES
                    part_end = min(part_start + MULTIPART_PART_SIZE_BYTES, file_size)
                    part_size = part_end - part_start

                    # Read part data
                    f.seek(part_start)
                    part_data = f.read(part_size)

                    self._log_progress(
                        f"[upload] Uploading part {part_num}/{num_parts} "
                        f"({humanize.naturalsize(part_size, binary=True)})"
                    )

                    # Upload part with retry
                    etag = self._upload_part(
                        upload_url=part_urls[part_num],
                        part_data=part_data,
                        part_number=part_num,
                    )

                    completed_parts.append(MultipartUploadPart(PartNumber=part_num, ETag=etag))

                    progress_pct = int(part_num / num_parts * 100)
                    self._log_progress(
                        f"[upload] Part {part_num}/{num_parts} complete ({progress_pct}%)"
                    )

            # Complete multipart upload
            self._log_progress("[upload] Completing multipart upload...")
            self._complete_multipart_upload(
                upload_id=upload_id,
                s3_key=s3_key,
                parts=completed_parts,
                artifact_type=request.artifact_type,
                filename=request.filename,
                file_size=file_size,
                content_type=content_type,
            )

            self._log_progress(f"[upload] Multipart upload completed for {request.filename}")
            return s3_key, content_type, file_size

        except Exception:
            # Abort multipart upload on failure
            self._log_progress("[upload] Upload failed, aborting multipart upload...")
            try:
                self._abort_multipart_upload(upload_id=upload_id, s3_key=s3_key)
            except Exception:
                logger.exception("Failed to abort multipart upload")
            raise

    @retry(
        retry=retry_if_exception_type(requests.RequestException),
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, max=10),
        reraise=True,
    )
    def _init_multipart_upload(
        self,
        *,
        artifact_type: str,
        filename: str,
        content_type: str,
        file_size: int,
        num_parts: int,
        source_path: str,
    ) -> MultipartUploadInitResponse:
        """Request multipart upload initialization from the server."""
        url = f"{self._webhook_base_url}/{self._run_id}/multipart-upload-init"
        headers = {
            "Authorization": f"Bearer {self._webhook_token}",
            "Content-Type": "application/json",
        }
        request_payload = MultipartUploadInitRequest(
            artifact_type=artifact_type,
            filename=filename,
            content_type=content_type,
            file_size=file_size,
            part_size=MULTIPART_PART_SIZE_BYTES,
            num_parts=num_parts,
            metadata={"source_path": source_path},
        )
        response = requests.post(
            url, headers=headers, json=request_payload.model_dump(), timeout=60
        )
        response.raise_for_status()
        return MultipartUploadInitResponse.model_validate(response.json())

    @retry(
        retry=retry_if_exception_type((requests.RequestException, OSError)),
        stop=stop_after_attempt(5),
        wait=wait_exponential(multiplier=2, max=60),
        before_sleep=before_sleep_log(logger, logging.WARNING),
        reraise=True,
    )
    def _upload_part(
        self,
        *,
        upload_url: str,
        part_data: bytes,
        part_number: int,
    ) -> str:
        """Upload a single part and return its ETag."""
        headers = {
            "Content-Length": str(len(part_data)),
        }
        try:
            response = requests.put(
                upload_url,
                data=part_data,
                headers=headers,
                timeout=600,  # 10 minutes per part
            )
            response.raise_for_status()
            etag = response.headers.get("ETag", "").strip('"')
            if not etag:
                raise ValueError(f"No ETag returned for part {part_number}")
            return etag
        except Exception:
            logger.exception("Failed to upload part %d", part_number)
            raise

    @retry(
        retry=retry_if_exception_type(requests.RequestException),
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, max=10),
        reraise=True,
    )
    def _complete_multipart_upload(
        self,
        *,
        upload_id: str,
        s3_key: str,
        parts: list[MultipartUploadPart],
        artifact_type: str,
        filename: str,
        file_size: int,
        content_type: str,
    ) -> None:
        """Complete the multipart upload."""
        url = f"{self._webhook_base_url}/{self._run_id}/multipart-upload-complete"
        headers = {
            "Authorization": f"Bearer {self._webhook_token}",
            "Content-Type": "application/json",
        }
        request_payload = MultipartUploadCompleteRequest(
            upload_id=upload_id,
            s3_key=s3_key,
            parts=parts,
            artifact_type=artifact_type,
            filename=filename,
            file_size=file_size,
            content_type=content_type,
        )
        response = requests.post(
            url,
            headers=headers,
            json=request_payload.model_dump(by_alias=True),
            timeout=60,
        )
        response.raise_for_status()

    def _abort_multipart_upload(self, *, upload_id: str, s3_key: str) -> None:
        """Abort a multipart upload."""
        url = f"{self._webhook_base_url}/{self._run_id}/multipart-upload-abort"
        headers = {
            "Authorization": f"Bearer {self._webhook_token}",
            "Content-Type": "application/json",
        }
        payload = {"upload_id": upload_id, "s3_key": s3_key}
        try:
            response = requests.post(url, headers=headers, json=payload, timeout=30)
            response.raise_for_status()
        except Exception:
            logger.exception("Failed to abort multipart upload")

    @retry(
        retry=retry_if_exception_type(requests.RequestException),
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, max=10),
        reraise=True,
    )
    def check_artifact_exists(
        self,
        *,
        artifact_type: str,
        filename: str,
    ) -> ArtifactExistsResponse:
        """Check if an artifact already exists in S3.

        Returns:
            ArtifactExistsResponse with exists, s3_key, and file_size fields
        """
        url = f"{self._webhook_base_url}/{self._run_id}/artifact-exists"
        headers = {
            "Authorization": f"Bearer {self._webhook_token}",
            "Content-Type": "application/json",
        }
        request_payload = ArtifactExistsRequest(
            artifact_type=artifact_type,
            filename=filename,
        )
        response = requests.post(
            url, headers=headers, json=request_payload.model_dump(), timeout=30
        )
        response.raise_for_status()
        return ArtifactExistsResponse.model_validate(response.json())

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
        self._log_progress(
            f"[upload] Uploading {local_path.name} ({humanize.naturalsize(file_size, binary=True)}) "
            "via presigned URL"
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
        self._log_progress(f"[upload] Successfully uploaded {local_path.name}")

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
        self._webhook_client = webhook_client

        # Create progress callback that sends run_log events
        def progress_callback(message: str) -> None:
            if self._webhook_client is not None:
                try:
                    self._webhook_client.publish(
                        kind="run_log",
                        payload=RunLogEvent(message=message, level="info"),
                    )
                except Exception:
                    logger.debug("Failed to publish progress event", exc_info=True)

        self._uploader = PresignedUrlUploader(
            webhook_base_url=webhook_base_url,
            webhook_token=webhook_token,
            run_id=run_id,
            progress_callback=progress_callback,
        )

    def publish(self, *, spec: ArtifactSpec) -> None:
        request = self._build_request(spec=spec)
        if request is None:
            logger.info(
                "Skipping artifact %s because nothing was found at %s",
                spec.artifact_type,
                spec.path,
            )
            return

        # Check if artifact already exists with same size (skip duplicate uploads)
        local_file_size = request.local_path.stat().st_size
        try:
            exists_response = self._uploader.check_artifact_exists(
                artifact_type=request.artifact_type,
                filename=request.filename,
            )
            if exists_response.exists and exists_response.file_size == local_file_size:
                logger.info(
                    "Skipping upload of %s artifact - already exists in S3 with same size (%d bytes)",
                    spec.artifact_type,
                    local_file_size,
                )
                return
            if exists_response.exists:
                logger.info(
                    "Artifact %s exists but size differs (local=%d, s3=%s) - re-uploading",
                    spec.artifact_type,
                    local_file_size,
                    exists_response.file_size,
                )
        except Exception:
            logger.warning(
                "Failed to check if artifact %s exists; proceeding with upload",
                spec.artifact_type,
                exc_info=True,
            )

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
            logger.info(
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
        logger.info("Creating zip archive %s from %s", archive_name, source_dir)
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
        archive_size = archive_path.stat().st_size
        logger.info(
            "Created zip archive %s with %d files (%s)",
            archive_name,
            files_added,
            humanize.naturalsize(archive_size, binary=True),
        )
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
