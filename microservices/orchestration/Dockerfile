# ============================================================================
# Enterprise Orchestration Service Dockerfile - Production Ready
# Microsoft Semantic Kernel Agent Orchestration Framework
# ============================================================================
# Multi-stage build for optimized, secure, and production-ready container

# Stage 1: Build stage
FROM python:3.11-slim as builder

# Set build environment variables
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1
ENV PIP_NO_CACHE_DIR=1
ENV PIP_DISABLE_PIP_VERSION_CHECK=1

# Install build dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    gcc \
    g++ \
    make \
    libffi-dev \
    libssl-dev \
    libpq-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Create virtual environment
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

    # Copy and install Python dependencies
    COPY orchestration/requirements.txt .
RUN pip install --upgrade pip setuptools wheel && \
    pip install --no-cache-dir -r requirements.txt

# Stage 2: Runtime stage
FROM python:3.11-slim as runtime

# Set runtime environment variables
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONPATH=/app
ENV PATH="/opt/venv/bin:$PATH"
ENV SERVICE_NAME=orchestration
ENV SERVICE_VERSION=1.0.0

# Install runtime dependencies only
RUN apt-get update && apt-get install -y \
    libpq5 \
    curl \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# Copy virtual environment from builder stage
COPY --from=builder /opt/venv /opt/venv

# Create application directory
WORKDIR /app

# Create non-root user with specific UID/GID for security
RUN groupadd -r orchestration -g 1001 && \
    useradd -r -g orchestration -u 1001 -d /app -s /bin/bash orchestration

# Copy shared modules first (for better layer caching)
COPY --chown=orchestration:orchestration shared /app/shared

# Copy application code with proper ownership
COPY --chown=orchestration:orchestration orchestration/ .

# Create necessary directories with proper permissions
RUN mkdir -p /app/logs /app/data /app/tmp && \
    chown -R orchestration:orchestration /app && \
    chmod -R 755 /app

# Switch to non-root user
USER orchestration

# Set resource limits and security options
# Note: These will be enforced by Kubernetes/container runtime
ENV OMP_NUM_THREADS=2
ENV MALLOC_ARENA_MAX=2

# Health check with proper timeout and retry logic
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD curl -f http://localhost:8001/health || exit 1

# Expose port
EXPOSE 8001

# Add labels for better container management
LABEL maintainer="Enterprise Agentic AI Team" \
      version="1.0.0" \
      description="Enterprise Orchestration Service with Microsoft Semantic Kernel" \
      service="orchestration" \
      environment="production"

# Use exec form for proper signal handling
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8001", "--workers", "1", "--access-log", "--log-level", "info"]
