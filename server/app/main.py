import logging
from typing import Dict

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.middleware.auth import AuthenticationMiddleware
from app.routes import router as api_router


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

    logging.getLogger("httpx").setLevel(logging.WARNING)
    # Suppress extremely verbose DEBUG logs from PDF parsers when app LOG_LEVEL=DEBUG
    logging.getLogger("pdfminer").setLevel(logging.WARNING)
    logging.getLogger("pdfminer.psparser").setLevel(logging.WARNING)
    logging.getLogger("pdfminer.pdfinterp").setLevel(logging.WARNING)
    logging.getLogger("pdfplumber").setLevel(logging.WARNING)

    logger = logging.getLogger(__name__)
    logger.info(f"Logging configured at {settings.LOG_LEVEL} level")
    logger.info(f"Environment: {settings.RAILWAY_ENVIRONMENT_NAME}")


# Configure logging before creating the app
configure_logging()

app = FastAPI(
    title="AE Scientist API",
    version=settings.VERSION,
    description="Transform LLM conversations into actionable AE ideas",
)

# Set up CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=settings.CORS_CREDENTIALS,
    allow_methods=settings.CORS_METHODS,
    allow_headers=settings.CORS_HEADERS,
)

# Add authentication middleware
app.add_middleware(AuthenticationMiddleware)

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
