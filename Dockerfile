# MedScribe Backend Dockerfile
FROM python:3.11-slim-bookworm

# Prevent apt from hanging on interactive prompts and configure python environment
ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

# Set working directory
WORKDIR /app

# Install system dependencies (Debian Bookworm ensures stable packages without trixie testing transitions)
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    libpq-dev \
    gcc \
    g++ \
    git \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better caching
COPY backend/requirements.txt /app/backend/requirements.txt

# Pre-install CPU-only PyTorch to avoid downloading multi-gigabyte CUDA wheels & prevent OOM on cloud builds
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir torch==2.3.1 torchaudio==2.3.1 --index-url https://download.pytorch.org/whl/cpu

# Install Python dependencies
RUN pip install --no-cache-dir -r backend/requirements.txt

# Install additional production dependencies
RUN pip install --no-cache-dir \
    psycopg2-binary \
    asyncpg \
    sqlalchemy[asyncio] \
    alembic \
    gunicorn \
    uvicorn[standard] \
    cryptography \
    aiofiles

# Copy application code (do NOT copy .env: secrets are provided via platform environment variables)
COPY backend/ /app/backend/
COPY data/ /app/data/

# Create necessary directories
RUN mkdir -p /app/data/chroma /app/data/uploads /app/logs

# Expose port (default 8000, Railway assigns $PORT at runtime)
EXPOSE 8000

# Health check using urllib (works across custom ports via $PORT)
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD python -c "import os, urllib.request; port = os.environ.get('PORT', '8000'); urllib.request.urlopen(f'http://localhost:{port}/health')"

# Run with uvicorn directly, outputting logs to stdout/stderr and binding to $PORT
CMD ["sh", "-c", "uvicorn backend.main:app --host 0.0.0.0 --port ${PORT:-8000}"]

