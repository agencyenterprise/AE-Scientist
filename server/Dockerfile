FROM python:3.12-slim

# Install system dependencies needed for Playwright and uv
RUN apt-get update && apt-get install -y \
    wget \
    curl \
    ca-certificates \
    libnss3 \
    libnspr4 \
    libatk1.0-0 \
    libatk-bridge2.0-0 \
    libcups2 \
    libdrm2 \
    libxss1 \
    libgtk-3-0 \
    libxrandr2 \
    libasound2 \
    libxdamage1 \
    libxcomposite1 \
    libxcursor1 \
    libxi6 \
    libgbm1 \
    libxtst6 \
    libappindicator3-1 \
    libdbus-glib-1-2 \
    libxft2 \
    libmagic1 \
    fonts-liberation \
    fonts-dejavu \
    && rm -rf /var/lib/apt/lists/*

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

WORKDIR /app

# Copy dependency files
COPY pyproject.toml uv.lock ./

# Install Python dependencies with uv (exclude dev dependencies)
RUN uv sync --frozen --no-dev

# Install Playwright browsers
RUN uv run playwright install firefox chromium webkit

# Copy application code
COPY . .

# Expose port
EXPOSE 8000

# Start the application (run migrations first)
CMD ["sh", "-c", "uv run migrate.py upgrade && uv run uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
