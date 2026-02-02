"""File upload endpoints for research pipeline: presigned URLs, multipart uploads, datasets."""

import logging
from typing import Dict, List, cast

from fastapi import APIRouter, Depends, HTTPException, status

from app.services import get_database
from app.services.s3_service import get_s3_service

from .auth import ResearchRunStore, verify_run_auth
from .schemas import (
    ArtifactExistsRequest,
    ArtifactExistsResponse,
    DatasetFileInfo,
    DatasetUploadUrlRequest,
    DatasetUploadUrlResponse,
    ListDatasetsRequest,
    ListDatasetsResponse,
    MultipartUploadAbortRequest,
    MultipartUploadCompleteRequest,
    MultipartUploadCompleteResponse,
    MultipartUploadInitRequest,
    MultipartUploadInitResponse,
    MultipartUploadPartUrl,
    ParentRunFileInfo,
    ParentRunFilesRequest,
    ParentRunFilesResponse,
    PresignedUploadUrlRequest,
    PresignedUploadUrlResponse,
)

router = APIRouter()
logger = logging.getLogger(__name__)

PRESIGNED_URL_EXPIRES_IN_SECONDS = 3600
MAX_DATASET_FILES = 2000


@router.post("/{run_id}/presigned-upload-url", response_model=PresignedUploadUrlResponse)
async def get_presigned_upload_url(
    run_id: str,
    payload: PresignedUploadUrlRequest,
    _: None = Depends(verify_run_auth),
) -> PresignedUploadUrlResponse:
    """Generate a presigned URL for uploading an artifact to S3."""
    db = cast(ResearchRunStore, get_database())
    run = await db.get_research_pipeline_run(run_id=run_id)
    if run is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Run not found")

    s3_key = f"research-pipeline/{run_id}/{payload.artifact_type}/{payload.filename}"

    metadata = {
        "run_id": run_id,
        "artifact_type": payload.artifact_type,
    }
    if payload.metadata:
        metadata.update(payload.metadata)

    s3_service = get_s3_service()
    upload_url = s3_service.generate_upload_url(
        s3_key=s3_key,
        content_type=payload.content_type,
        expires_in=PRESIGNED_URL_EXPIRES_IN_SECONDS,
        metadata=metadata,
    )

    logger.debug(
        "Generated presigned upload URL: run=%s type=%s filename=%s",
        run_id,
        payload.artifact_type,
        payload.filename,
    )

    return PresignedUploadUrlResponse(
        upload_url=upload_url,
        s3_key=s3_key,
        expires_in=PRESIGNED_URL_EXPIRES_IN_SECONDS,
    )


@router.post("/{run_id}/artifact-exists", response_model=ArtifactExistsResponse)
async def check_artifact_exists(
    run_id: str,
    payload: ArtifactExistsRequest,
    _: None = Depends(verify_run_auth),
) -> ArtifactExistsResponse:
    """Check if an artifact already exists in S3 and return its size."""
    db = cast(ResearchRunStore, get_database())
    run = await db.get_research_pipeline_run(run_id=run_id)
    if run is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Run not found")

    s3_key = f"research-pipeline/{run_id}/{payload.artifact_type}/{payload.filename}"

    s3_service = get_s3_service()
    if s3_service.file_exists(s3_key):
        file_info = s3_service.get_file_info(s3_key=s3_key)
        exists = True
        file_size = file_info.get("content_length")
    else:
        exists = False
        file_size = None

    logger.debug(
        "Artifact exists check: run=%s type=%s filename=%s exists=%s size=%s",
        run_id,
        payload.artifact_type,
        payload.filename,
        exists,
        file_size,
    )

    return ArtifactExistsResponse(
        exists=exists,
        s3_key=s3_key,
        file_size=file_size,
    )


@router.post("/{run_id}/multipart-upload-init", response_model=MultipartUploadInitResponse)
async def init_multipart_upload(
    run_id: str,
    payload: MultipartUploadInitRequest,
    _: None = Depends(verify_run_auth),
) -> MultipartUploadInitResponse:
    """Initiate a multipart upload for large files."""
    db = cast(ResearchRunStore, get_database())
    run = await db.get_research_pipeline_run(run_id=run_id)
    if run is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Run not found")

    s3_key = f"research-pipeline/{run_id}/{payload.artifact_type}/{payload.filename}"

    metadata = {
        "run_id": run_id,
        "artifact_type": payload.artifact_type,
    }
    if payload.metadata:
        metadata.update(payload.metadata)

    s3_service = get_s3_service()

    # Create multipart upload
    upload_id = s3_service.create_multipart_upload(
        s3_key=s3_key,
        content_type=payload.content_type,
        metadata=metadata,
    )

    # Generate presigned URLs for all parts
    part_urls = []
    for part_num in range(1, payload.num_parts + 1):
        part_url = s3_service.generate_multipart_part_url(
            s3_key=s3_key,
            upload_id=upload_id,
            part_number=part_num,
            expires_in=PRESIGNED_URL_EXPIRES_IN_SECONDS,
        )
        part_urls.append(MultipartUploadPartUrl(part_number=part_num, upload_url=part_url))

    logger.info(
        "Initiated multipart upload: run=%s type=%s filename=%s parts=%d upload_id=%s",
        run_id,
        payload.artifact_type,
        payload.filename,
        payload.num_parts,
        upload_id,
    )

    return MultipartUploadInitResponse(
        upload_id=upload_id,
        s3_key=s3_key,
        part_urls=part_urls,
        expires_in=PRESIGNED_URL_EXPIRES_IN_SECONDS,
    )


@router.post("/{run_id}/multipart-upload-complete", response_model=MultipartUploadCompleteResponse)
async def complete_multipart_upload(
    run_id: str,
    payload: MultipartUploadCompleteRequest,
    _: None = Depends(verify_run_auth),
) -> MultipartUploadCompleteResponse:
    """Complete a multipart upload."""
    db = cast(ResearchRunStore, get_database())
    run = await db.get_research_pipeline_run(run_id=run_id)
    if run is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Run not found")

    s3_service = get_s3_service()

    # Convert parts to format expected by S3
    parts: List[Dict[str, str | int]] = [
        {"PartNumber": p.part_number, "ETag": p.etag} for p in payload.parts
    ]

    try:
        s3_service.complete_multipart_upload(
            s3_key=payload.s3_key,
            upload_id=payload.upload_id,
            parts=parts,
        )
    except Exception as e:
        logger.error(
            "Failed to complete multipart upload: run=%s s3_key=%s error=%s",
            run_id,
            payload.s3_key,
            str(e),
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to complete multipart upload: {str(e)}",
        ) from e

    logger.info(
        "Completed multipart upload: run=%s type=%s filename=%s size=%d",
        run_id,
        payload.artifact_type,
        payload.filename,
        payload.file_size,
    )

    return MultipartUploadCompleteResponse(
        s3_key=payload.s3_key,
        success=True,
    )


@router.post("/{run_id}/multipart-upload-abort", status_code=status.HTTP_204_NO_CONTENT)
async def abort_multipart_upload(
    run_id: str,
    payload: MultipartUploadAbortRequest,
    _: None = Depends(verify_run_auth),
) -> None:
    """Abort a multipart upload."""
    db = cast(ResearchRunStore, get_database())
    run = await db.get_research_pipeline_run(run_id=run_id)
    if run is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Run not found")

    s3_service = get_s3_service()

    s3_service.abort_multipart_upload(
        s3_key=payload.s3_key,
        upload_id=payload.upload_id,
    )

    logger.info(
        "Aborted multipart upload: run=%s s3_key=%s upload_id=%s",
        run_id,
        payload.s3_key,
        payload.upload_id,
    )


@router.post("/{run_id}/parent-run-files", response_model=ParentRunFilesResponse)
async def get_parent_run_files(
    run_id: str,
    payload: ParentRunFilesRequest,
    _: None = Depends(verify_run_auth),
) -> ParentRunFilesResponse:
    """List files from a parent run and return presigned download URLs."""
    db = cast(ResearchRunStore, get_database())
    run = await db.get_research_pipeline_run(run_id=run_id)
    if run is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Run not found")

    s3_service = get_s3_service()
    prefix = f"research-pipeline/{payload.parent_run_id}/"

    objects = s3_service.list_objects(prefix=prefix)

    files: List[ParentRunFileInfo] = []
    for obj in objects:
        s3_key = str(obj["key"])
        filename = s3_key.split("/")[-1]
        download_url = s3_service.generate_download_url(
            s3_key=s3_key,
            expires_in=PRESIGNED_URL_EXPIRES_IN_SECONDS,
        )
        files.append(
            ParentRunFileInfo(
                s3_key=s3_key,
                filename=filename,
                size=int(obj["size"]),
                download_url=download_url,
            )
        )

    logger.debug(
        "Listed parent run files: run=%s parent_run=%s count=%d",
        run_id,
        payload.parent_run_id,
        len(files),
    )

    return ParentRunFilesResponse(
        files=files,
        expires_in=PRESIGNED_URL_EXPIRES_IN_SECONDS,
    )


@router.post("/{run_id}/list-datasets", response_model=ListDatasetsResponse)
async def list_datasets(
    run_id: str,
    payload: ListDatasetsRequest,
    _: None = Depends(verify_run_auth),
) -> ListDatasetsResponse:
    """List files in a datasets folder and return presigned download URLs."""
    db = cast(ResearchRunStore, get_database())
    run = await db.get_research_pipeline_run(run_id=run_id)
    if run is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Run not found")

    s3_service = get_s3_service()
    folder = payload.datasets_folder.strip("/")
    prefix = f"{folder}/" if folder else ""

    objects = s3_service.list_objects(prefix=prefix)

    files: List[DatasetFileInfo] = []
    for obj in objects:
        if len(files) >= MAX_DATASET_FILES:
            break
        s3_key = str(obj["key"])
        # Skip "directory" entries (keys ending with / and size 0)
        if s3_key.endswith("/") and obj["size"] == 0:
            continue
        relative_path = s3_key[len(prefix) :] if s3_key.startswith(prefix) else s3_key
        download_url = s3_service.generate_download_url(
            s3_key=s3_key,
            expires_in=PRESIGNED_URL_EXPIRES_IN_SECONDS,
        )
        files.append(
            DatasetFileInfo(
                s3_key=s3_key,
                relative_path=relative_path,
                size=int(obj["size"]),
                download_url=download_url,
            )
        )

    logger.debug(
        "Listed datasets: run=%s folder=%s count=%d",
        run_id,
        payload.datasets_folder,
        len(files),
    )

    return ListDatasetsResponse(
        files=files,
        expires_in=PRESIGNED_URL_EXPIRES_IN_SECONDS,
    )


@router.post("/{run_id}/dataset-upload-url", response_model=DatasetUploadUrlResponse)
async def get_dataset_upload_url(
    run_id: str,
    payload: DatasetUploadUrlRequest,
    _: None = Depends(verify_run_auth),
) -> DatasetUploadUrlResponse:
    """Generate a presigned URL for uploading a file to the datasets folder."""
    db = cast(ResearchRunStore, get_database())
    run = await db.get_research_pipeline_run(run_id=run_id)
    if run is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Run not found")

    folder = payload.datasets_folder.strip("/")
    relative = payload.relative_path.lstrip("/")
    s3_key = f"{folder}/{relative}" if folder else relative

    s3_service = get_s3_service()
    upload_url = s3_service.generate_upload_url(
        s3_key=s3_key,
        content_type=payload.content_type,
        expires_in=PRESIGNED_URL_EXPIRES_IN_SECONDS,
        metadata={"run_id": run_id, "type": "dataset"},
    )

    logger.debug(
        "Generated dataset upload URL: run=%s key=%s",
        run_id,
        s3_key,
    )

    return DatasetUploadUrlResponse(
        upload_url=upload_url,
        s3_key=s3_key,
        expires_in=PRESIGNED_URL_EXPIRES_IN_SECONDS,
    )
