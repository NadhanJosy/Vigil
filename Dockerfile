# ============================================================
# Vigil Backend — Dockerfile
# ============================================================

FROM python:3.11-slim AS base

WORKDIR /app

# Install runtime dependencies
RUN apt-get update && \
    apt-get install -y --no-install-recommends curl libpq-dev && \
    rm -rf /var/lib/apt/lists/*

# Copy requirements first for layer caching
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY backend/ .

# Create non-root user
RUN useradd -m vigil && chown -R vigil:vigil /app
USER vigil

# Expose port (use PORT env variable from Railway)
ENV PORT=8000
EXPOSE ${PORT}

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
  CMD curl -f http://localhost:${PORT}/health || exit 1

# Run with uvicorn (use PORT env variable for Railway compatibility)
CMD ["sh", "-c", "uvicorn api:app --host 0.0.0.0 --port $PORT --workers 1"]
