import asyncio
import logging
import sys
from contextlib import asynccontextmanager
from typing import AsyncIterator, Dict

import sentry_sdk
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pythonjsonlogger.json import JsonFormatter
from starlette.middleware.gzip import GZipMiddleware

from app.api.mcp_server import router as mcp_router
from app.config import settings
from app.middleware.auth import AuthenticationMiddleware
from app.routes import router as api_router
from app.services.database import DatabaseManager
from app.services.paper_review_service import recover_stale_paper_reviews
from app.services.redis_streams import close_redis, init_redis
from app.services.research_pipeline.monitor import pipeline_monitor
from app.services.research_pipeline.runpod import get_supported_gpu_types, warm_gpu_price_cache
from app.validation import validate_configuration

# Initialize Sentry (must be done before FastAPI app is created)
if settings.sentry_dsn and settings.server.railway_environment_name != "development":
    sentry_sdk.init(
        dsn=settings.sentry_dsn,
        environment=settings.sentry_environment or settings.server.railway_environment_name,
        traces_sample_rate=1.0,
        send_default_pii=True,
    )


def configure_logging() -> None:
    """Configure logging for the application."""
    # Set logging level from environment variable
    log_level = getattr(logging, settings.server.log_level.upper(), logging.INFO)

    # Configure root logger with JSON format in production for Railway
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)

    # Clear any existing handlers to avoid duplicate logs (e.g., from uvicorn)
    root_logger.handlers.clear()

    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(log_level)

    if settings.is_production:
        # JSON format for Railway - includes structured fields for better log parsing
        handler.setFormatter(
            JsonFormatter(
                fmt="%(asctime)s %(name)s %(levelname)s %(message)s",
                rename_fields={"asctime": "timestamp", "levelname": "level", "name": "logger"},
            )
        )
    else:
        # Human-readable format for local development
        handler.setFormatter(
            logging.Formatter(
                fmt="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
                datefmt="%Y-%m-%d %H:%M:%S",
            )
        )
    root_logger.addHandler(handler)

    logger = logging.getLogger(__name__)
    logger.info("Logging configured at %s level", settings.server.log_level)

    # Set specific loggers to appropriate levels
    # Reduce noise from third-party libraries
    if settings.is_production:
        # In production, log HTTP requests for debugging
        logging.getLogger("uvicorn.access").setLevel(logging.INFO)
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
    logger.info("Logging configured at %s level", settings.server.log_level)


# Configure logging before creating the app
configure_logging()

# Validate application configuration
validate_configuration()


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    # Initialize Redis for SSE event streaming
    await init_redis()

    # Recover any paper reviews that were interrupted by a previous server restart
    await recover_stale_paper_reviews()

    await pipeline_monitor.start()
    asyncio.create_task(
        coro=warm_gpu_price_cache(gpu_types=get_supported_gpu_types()),
        name="runpod_gpu_price_warmup",
    )
    try:
        yield
    finally:
        await close_redis()
        await pipeline_monitor.stop()
        await DatabaseManager.close_all_pools()


app = FastAPI(
    title="AE Scientist API",
    version=settings.server.version,
    description="Transform LLM conversations into actionable AE ideas",
    lifespan=lifespan,
)

# Add authentication middleware
app.add_middleware(AuthenticationMiddleware)

# Set up CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=list(settings.server.cors_origins),
    allow_credentials=settings.server.cors_credentials,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Enable gzip compression for large JSON payloads while keeping SSE uncompressed
app.add_middleware(GZipMiddleware, minimum_size=500)

# Include API routes
app.include_router(api_router)

# Include MCP server at root level (not under /api)
app.include_router(mcp_router)


@app.get("/")
async def root() -> Dict[str, str]:
    """Get basic API information."""
    return {"message": settings.server.api_title}


@app.get("/health")
async def health_check() -> Dict[str, str]:
    """Check API health status."""
    return {"status": "healthy"}
