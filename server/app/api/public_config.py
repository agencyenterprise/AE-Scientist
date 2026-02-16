"""
Public configuration endpoints.
"""

import logging

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.config import settings
from app.services.s3_service import get_s3_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/public-config", tags=["public-config"])


class PublicConfigResponse(BaseModel):
    """Public configuration values exposed to the frontend."""

    pipeline_monitor_max_runtime_hours: int
    min_balance_cents_for_research_pipeline: int
    min_balance_cents_for_paper_review: int


# S3 key for the best paper example
BEST_PAPER_S3_KEY = "best_paper/paper.pdf"
# URL expiration time in seconds (1 hour)
BEST_PAPER_URL_EXPIRATION = 3600


@router.get("", response_model=PublicConfigResponse)
async def get_public_config() -> PublicConfigResponse:
    return PublicConfigResponse(
        pipeline_monitor_max_runtime_hours=settings.pipeline_monitor_max_runtime_hours,
        min_balance_cents_for_research_pipeline=settings.min_balance_cents_for_research_pipeline,
        min_balance_cents_for_paper_review=settings.min_balance_cents_for_paper_review,
    )


@router.get("/best-paper-url")
async def get_best_paper_download_url() -> dict[str, str]:
    """
    Generate a temporary signed URL for downloading the best paper example.
    The URL expires after 1 hour.
    """
    try:
        s3_service = get_s3_service()
        if not s3_service.file_exists(BEST_PAPER_S3_KEY):
            raise HTTPException(status_code=404, detail="Best paper file not found")

        download_url = s3_service.generate_download_url(
            BEST_PAPER_S3_KEY, expires_in=BEST_PAPER_URL_EXPIRATION
        )
        return {"download_url": download_url}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to generate best paper download URL: {e}")
        raise HTTPException(status_code=500, detail="Failed to generate download URL") from e
