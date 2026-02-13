"""
AE Paper Review - FastAPI Application.

Simplified standalone server for paper reviews.
"""

import logging
import sys
from contextlib import asynccontextmanager
from typing import AsyncIterator, Dict

import sentry_sdk
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.gzip import GZipMiddleware

from app.config import settings
from app.middleware.auth import AuthenticationMiddleware
from app.routes import router as api_router
from app.services.database import DatabaseManager
from app.services.paper_review_service import recover_stale_paper_reviews


def _init_sentry() -> None:
    """Initialize Sentry for error tracking."""
    if settings.sentry_dsn:
        sentry_sdk.init(
            dsn=settings.sentry_dsn,
            environment=settings.sentry_environment or "development",
            traces_sample_rate=1.0,
            send_default_pii=True,
        )


def configure_logging() -> None:
    """Configure logging for the application."""
    log_level = getattr(logging, settings.server.log_level.upper(), logging.INFO)

    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)

    # Clear any existing handlers to avoid duplicate logs
    root_logger.handlers.clear()

    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(log_level)

    # Human-readable format
    handler.setFormatter(
        logging.Formatter(
            fmt="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
    )
    root_logger.addHandler(handler)

    logger = logging.getLogger(__name__)
    logger.info("Logging configured at %s level", settings.server.log_level)

    # Reduce noise from third-party libraries
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("pdfminer").setLevel(logging.WARNING)
    logging.getLogger("pdfplumber").setLevel(logging.WARNING)


# Configure logging before creating the app
configure_logging()

# Initialize Sentry
_init_sentry()


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    """Application lifespan handler."""
    logger = logging.getLogger(__name__)
    logger.info("Starting AE Paper Review")

    # Recover any paper reviews that were interrupted by a previous server restart
    await recover_stale_paper_reviews()

    try:
        yield
    finally:
        logger.info("Shutting down AE Paper Review")
        await DatabaseManager.close_all_pools()


app = FastAPI(
    title="AE Paper Review API",
    version="1.0.0",
    description="AI-powered paper review service",
    lifespan=lifespan,
)

# Add authentication middleware
app.add_middleware(AuthenticationMiddleware)

# Set up CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=list(settings.server.cors_origins),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Enable gzip compression for large JSON payloads
app.add_middleware(GZipMiddleware, minimum_size=500)

# Include API routes
app.include_router(api_router)


@app.get("/")
async def root() -> Dict[str, str]:
    """Get basic API information."""
    return {"message": "AE Paper Review API"}


@app.get("/health")
async def health_check() -> Dict[str, str]:
    """Check API health status."""
    return {"status": "healthy"}
