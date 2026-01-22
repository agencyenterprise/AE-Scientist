import asyncio
import logging
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
from app.services.research_pipeline.monitor import pipeline_monitor
from app.services.research_pipeline.runpod import get_supported_gpu_types, warm_gpu_price_cache
from app.validation import validate_configuration

# Initialize Sentry (must be done before FastAPI app is created)
if settings.SENTRY_DSN and settings.RAILWAY_ENVIRONMENT_NAME != "development":
    sentry_sdk.init(
        dsn=settings.SENTRY_DSN,
        environment=settings.SENTRY_ENVIRONMENT or settings.RAILWAY_ENVIRONMENT_NAME,
        traces_sample_rate=1.0,
        send_default_pii=True,
    )


def configure_logging() -> None:
    """Configure logging for the application."""
    # Set logging level from environment variable
    log_level = getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO)

    # Configure root logger
    logging.basicConfig(
        level=log_level,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # Set specific loggers to appropriate levels
    # Reduce noise from third-party libraries
    if settings.is_production:
        # In production, suppress HTTP request logs to reduce noise
        logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    else:
        # In development, show HTTP requests for debugging
        logging.getLogger("uvicorn.access").setLevel(logging.INFO)

    # Reduce noise from HTTP client debug logs (httpx/httpcore)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("httpcore.http11").setLevel(logging.WARNING)
    logging.getLogger("httpcore.connection").setLevel(logging.WARNING)
    # Reduce noise from urllib3 (used by requests and some SDKs)
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("urllib3.connectionpool").setLevel(logging.WARNING)
    # Suppress extremely verbose DEBUG logs from PDF parsers when app LOG_LEVEL=DEBUG
    logging.getLogger("pdfminer").setLevel(logging.WARNING)
    logging.getLogger("pdfminer.psparser").setLevel(logging.WARNING)
    logging.getLogger("pdfminer.pdfinterp").setLevel(logging.WARNING)
    logging.getLogger("pdfplumber").setLevel(logging.WARNING)

    logger = logging.getLogger(__name__)
    logger.info("Logging configured at %s level", settings.LOG_LEVEL)
    logger.info("Environment: %s", settings.RAILWAY_ENVIRONMENT_NAME)


# Configure logging before creating the app
configure_logging()

# Validate application configuration
validate_configuration()


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    await pipeline_monitor.start()
    asyncio.create_task(
        coro=warm_gpu_price_cache(gpu_types=get_supported_gpu_types()),
        name="runpod_gpu_price_warmup",
    )
    try:
        yield
    finally:
        await pipeline_monitor.stop()
        await DatabaseManager.close_all_pools()


app = FastAPI(
    title="AE Scientist API",
    version=settings.VERSION,
    description="Transform LLM conversations into actionable AE ideas",
    lifespan=lifespan,
)

# Add authentication middleware
app.add_middleware(AuthenticationMiddleware)

# Set up CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=settings.CORS_CREDENTIALS,
    allow_methods=settings.CORS_METHODS,
    allow_headers=settings.CORS_HEADERS,
)

# Enable gzip compression for large JSON payloads while keeping SSE uncompressed
app.add_middleware(GZipMiddleware, minimum_size=500)

# Include API routes
app.include_router(api_router)


@app.get("/")
async def root() -> Dict[str, str]:
    """Get basic API information."""
    return {"message": settings.API_TITLE}


@app.get("/health")
async def health_check() -> Dict[str, str]:
    """Check API health status."""
    return {"status": "healthy"}
