# Multi-stage Docker build for Burly MCP Server
# Optimized for security, performance, and minimal attack surface

# =============================================================================
# Dependencies Stage - Build and install dependencies with build cache optimization
# =============================================================================
FROM python:3.12-slim AS dependencies

# Install system dependencies needed for building Python packages
# Keep this layer stable for better caching
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    gcc \
    git \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# Set up Python environment for optimal builds
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_DEFAULT_TIMEOUT=100

WORKDIR /app

# Copy only dependency files first for better layer caching
COPY pyproject.toml ./

# Install dependencies in a separate layer for better caching
RUN pip install --upgrade pip setuptools wheel

# Install package dependencies (this layer will be cached unless pyproject.toml changes)
RUN pip install --no-deps -e . || true

# Copy source code and install the package
COPY src/ ./src/
RUN pip install -e .

# =============================================================================
# Runtime Stage - Minimal runtime environment with security hardening
# =============================================================================
FROM python:3.12-slim AS runtime

# Install only essential runtime dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    docker.io \
    curl \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean \
    && rm -rf /tmp/* /var/tmp/*

# Create application user with fixed UID for consistency across environments
RUN groupadd --gid 1000 agentops && \
    useradd --uid 1000 --gid agentops --shell /bin/bash --create-home agentops

# Set up directory structure with proper permissions
RUN mkdir -p \
    /app/config \
    /app/data/blog/stage \
    /app/data/blog/publish \
    /var/log/agentops \
    /tmp/agentops \
    && chown -R agentops:agentops /app /var/log/agentops /tmp/agentops \
    && chmod 755 /app \
    && chmod 750 /var/log/agentops /tmp/agentops

# Copy Python environment from dependencies stage
COPY --from=dependencies /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
COPY --from=dependencies /usr/local/bin /usr/local/bin

# Set working directory
WORKDIR /app

# Copy application code with proper ownership
COPY --chown=agentops:agentops src/ ./src/
COPY --chown=agentops:agentops config/ ./config/
COPY --chown=agentops:agentops pyproject.toml ./

# Set up environment variables with secure defaults
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONPATH=/app/src \
    BURLY_CONFIG_DIR=/app/config \
    BURLY_LOG_DIR=/var/log/agentops \
    POLICY_FILE=/app/config/policy/tools.yaml \
    DOCKER_SOCKET=/var/run/docker.sock \
    DOCKER_TIMEOUT=30 \
    MAX_OUTPUT_SIZE=1048576 \
    AUDIT_ENABLED=true \
    BLOG_STAGE_ROOT=/app/data/blog/stage \
    BLOG_PUBLISH_ROOT=/app/data/blog/publish \
    SERVER_NAME=burly-mcp \
    SERVER_VERSION=1.0.0

# Health check to ensure the server can start properly
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "from burly_mcp.server.main import main; print('Health check OK')" || exit 1

# Switch to non-root user for security
USER agentops

# Use exec form for proper signal handling
ENTRYPOINT ["python", "-m", "burly_mcp.server.main"]

# Security labels and metadata
LABEL org.opencontainers.image.title="Burly MCP Server" \
      org.opencontainers.image.description="Secure MCP server for system operations with multi-stage optimization" \
      org.opencontainers.image.version="1.0.0" \
      org.opencontainers.image.authors="Burly MCP Team" \
      org.opencontainers.image.source="https://github.com/your-org/burly-mcp" \
      org.opencontainers.image.licenses="MIT" \
      security.non-root="true" \
      security.user="agentops:1000" \
      security.capabilities="minimal"