# syntax=docker/dockerfile:1

# Build arguments keep Python/runtime metadata configurable across stages.
ARG PYTHON_VERSION=3.10
ARG APP_VERSION=0.1.0

# -------- Builder stage: resolve and cache Python wheels --------
FROM python:${PYTHON_VERSION}-slim AS builder
ARG PYTHON_VERSION

ENV PIP_NO_CACHE_DIR=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY requirements.txt ./

RUN pip install --upgrade pip setuptools wheel \
    && pip wheel --wheel-dir /tmp/wheels -r requirements.txt

# -------- Frontend stage: compile the SPA with Node --------
FROM node:20 AS frontend-builder
WORKDIR /app/frontend

COPY frontend/package*.json ./
RUN npm install
COPY frontend/ ./
# Build to local dist directory for Docker context
RUN npm run build -- --outDir dist --emptyOutDir

# -------- Runtime stage: minimal image with runtime-only deps --------
FROM python:${PYTHON_VERSION}-slim
ARG PYTHON_VERSION
ARG APP_VERSION

# OCI metadata aids traceability in registries.
LABEL org.opencontainers.image.title="Enterprise Policy Insight Platform" \
      org.opencontainers.image.description="FastAPI service for EPIP (Enterprise Policy Insight Platform)." \
      org.opencontainers.image.version="${APP_VERSION}" \
      org.opencontainers.image.vendor="EPIP" \
      org.opencontainers.image.licenses="UNLICENSED" \
      org.opencontainers.image.source="https://github.com/enterprise-policy-insight-platform/epip"

ENV APP_VERSION=${APP_VERSION} \
    PIP_NO_CACHE_DIR=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app/src

WORKDIR /app

# Install curl once for the runtime health probe and clean up apt cache.
RUN apt-get update \
    && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

# Non-root user keeps the runtime hardened.
RUN useradd -m -u 1000 epip

COPY --from=builder /tmp/wheels /wheels
RUN pip install --no-cache-dir /wheels/* \
    && rm -rf /wheels

COPY src/ ./src/
COPY --from=frontend-builder /app/frontend/dist ./src/epip/static/

USER epip

EXPOSE 8000

# Basic HTTP liveness check powers orchestrator health management.
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -fsS http://localhost:8000/monitoring/health/live || exit 1

CMD ["uvicorn", "epip.main:app", "--host", "0.0.0.0", "--port", "8000"]
