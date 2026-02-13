FROM python:3.12-slim

# Install system dependencies
RUN apt-get update && apt-get install -y \
    curl \
    ca-certificates \
    libmagic1 \
    && rm -rf /var/lib/apt/lists/*

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

WORKDIR /app

# Copy dependency files (build context is repo root)
COPY paper-review-microsite/backend/pyproject.toml paper-review-microsite/backend/uv.lock ./

# Copy ae-paper-review package (needed as a dependency)
COPY packages/ae-paper-review /packages/ae-paper-review

# Install Python dependencies with uv (exclude dev dependencies)
RUN uv sync --frozen --no-dev

# Install ae-paper-review package
RUN uv pip install /packages/ae-paper-review

# Copy backend application code
COPY paper-review-microsite/backend/ .

# Expose port
EXPOSE 8000

# Start the application (run migrations, then start uvicorn)
CMD ["sh", "-c", "uv run migrate.py upgrade && uv run uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000} --workers 4"]
