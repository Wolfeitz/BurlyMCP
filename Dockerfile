# Multi-stage Docker build for Burly MCP Server
# Optimized for security, performance, and minimal attack surface

# =============================================================================
# Dependencies Stage - Build and install dependencies
# =============================================================================
FROM python:3.12-slim as dependencies

# Install system dependencies needed for building Python packages
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Create application user early for consistent UID/GID
RUN groupadd --gid 1000 appuser && \
    useradd --uid 1000 --gid appuser --shell /bin/bash --create-home appuser

# Set up Python environment
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Install Python dependencies
WORKDIR /app
COPY pyproject.toml ./
COPY src/ ./src/
RUN pip install --upgrade pip setuptools wheel && \
    pip install -e .

# =============================================================================
# Runtime Stage - Minimal runtime environment
# =============================================================================
FROM python:3.12-slim as runtime

# Install only runtime system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    docker.io \
    curl \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# Create application user with same UID/GID as dependencies stage
RUN groupadd --gid 1000 appuser && \
    useradd --uid 1000 --gid appuser --shell /bin/bash --create-home appuser

# Set up directory structure with proper permissions
RUN mkdir -p /app/data/blog/stage /app/data/blog/public /var/log/agentops && \
    chown -R appuser:appuser /app /var/log/agentops && \
    chmod 755 /app && \
    chmod 750 /var/log/agentops

# Copy Python environment from dependencies stage
COPY --from=dependencies /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
COPY --from=dependencies /usr/local/bin /usr/local/bin

# Copy application code
WORKDIR /app
COPY --chown=appuser:appuser src/ ./src/
COPY --chown=appuser:appuser config/ ./config/
COPY --chown=appuser:appuser pyproject.toml ./

# Install the application in development mode
USER appuser
RUN pip install --user -e .

# Set up environment variables with secure defaults
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    LOG_LEVEL=INFO \
    LOG_DIR=/var/log/agentops \
    POLICY_FILE=/app/config/policy/tools.yaml \
    BLOG_STAGE_ROOT=/app/data/blog/stage \
    BLOG_PUBLISH_ROOT=/app/data/blog/public \
    DEFAULT_TIMEOUT_SEC=30 \
    OUTPUT_TRUNCATE_LIMIT=10240 \
    AUDIT_LOG_PATH=/var/log/agentops/audit.jsonl \
    NOTIFICATIONS_ENABLED=false \
    SERVER_NAME=burly-mcp \
    SERVER_VERSION=1.0.0

# Add user's local bin to PATH for installed packages
ENV PATH="/home/appuser/.local/bin:$PATH"

# Health check to ensure the server can start
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import burly_mcp; print('OK')" || exit 1

# Expose no ports (MCP uses stdin/stdout)
# EXPOSE directive intentionally omitted

# Use exec form for proper signal handling
ENTRYPOINT ["python", "-m", "burly_mcp.server.main"]

# Security: Run as non-root user
USER appuser

# Security: Use read-only root filesystem (with exceptions for writable areas)
# This should be configured at runtime with --read-only and appropriate tmpfs mounts

# Labels for metadata
LABEL org.opencontainers.image.title="Burly MCP Server" \
      org.opencontainers.image.description="Secure MCP server for system operations" \
      org.opencontainers.image.version="1.0.0" \
      org.opencontainers.image.authors="Burly MCP Team" \
      org.opencontainers.image.source="https://github.com/your-org/burly-mcp" \
      org.opencontainers.image.licenses="MIT"