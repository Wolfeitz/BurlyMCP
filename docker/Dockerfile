# Burly MCP Server - Secure Container Build
# Uses Python 3.12 slim base with security hardening

FROM python:3.12-slim

# Security: Create non-root user with fixed UID for consistency
RUN groupadd -r agentops --gid=1000 && \
    useradd -r -g agentops --uid=1000 --home-dir=/app --shell=/bin/bash agentops

# Install system dependencies and clean up in single layer
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        docker.io \
        curl \
        ca-certificates && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/* /tmp/* /var/tmp/*

# Set working directory
WORKDIR /app

# Copy requirements and install Python dependencies
COPY pyproject.toml ./
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -e . && \
    pip cache purge

# Copy application code
COPY server/ ./server/
COPY policy/ ./policy/

# Create necessary directories with proper permissions
RUN mkdir -p /var/log/agentops /app/blog/stage /app/blog/publish && \
    chown -R agentops:agentops /app /var/log/agentops

# Security: Switch to non-root user
USER agentops

# Health check to ensure server is responsive
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD echo '{"method":"list_tools"}' | python -m server.main || exit 1

# Default command
CMD ["python", "-m", "server.main"]

# Security labels
LABEL maintainer="AgentOps Team" \
      version="1.0.0" \
      description="Secure MCP server for system operations" \
      security.non-root="true" \
      security.user="agentops:1000"