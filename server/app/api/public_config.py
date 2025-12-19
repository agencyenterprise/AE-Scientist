"""
Public configuration endpoints.
"""

from fastapi import APIRouter

from app.config import settings

router = APIRouter(prefix="/public-config", tags=["public-config"])


@router.get("")
async def get_public_config() -> dict[str, int]:
    return {"pipeline_monitor_max_runtime_hours": settings.PIPELINE_MONITOR_MAX_RUNTIME_HOURS}

