"""
Main API router for AE Paper Review.

Aggregates all API routes from individual modules.
"""

from fastapi import APIRouter

from app.api.auth import router as auth_router
from app.api.models import router as models_router
from app.api.paper_reviews import router as paper_reviews_router

router = APIRouter(prefix="/api")

# Include sub-routers
router.include_router(auth_router)
router.include_router(models_router)
router.include_router(paper_reviews_router)
