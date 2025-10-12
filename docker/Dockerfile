# Burly MCP Server - Secure Container Image
#
# This Dockerfile creates a hardened container for running the Burly MCP server
# with minimal privileges and security-focused configuration.
#
# Security Features:
# - Non-root user execution (agentops:1000)
# - Minimal base image (python:3.12-slim)
# - No unnecessary packages or tools
# - Read-only filesystem where possible
# - Explicit volume mounts for data directories

FROM python:3.12-slim

# Create non-root user for security
# Using UID 1000 for compatibility with common Docker setups
RUN groupadd -r agentops -g 1000 && \
    useradd -r -g agentops -u 1000 -m -s /bin/bash agentops

# Install system dependencies
# Only install what's absolutely necessary for the application
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        docker.io \
        curl \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy Python dependencies and install them
# Do this before copying source code to leverage Docker layer caching
COPY pyproject.toml ./
RUN pip install --no-cache-dir -e .

# Copy application source code
COPY server/ ./server/
COPY policy/ ./policy/

# Create necessary directories with proper permissions
RUN mkdir -p /var/log/agentops /app/data/blog/stage /app/data/blog/public && \
    chown -R agentops:agentops /var/log/agentops /app/data && \
    chmod 755 /var/log/agentops && \
    chmod 755 /app/data/blog/stage && \
    chmod 755 /app/data/blog/public

# Switch to non-root user
USER agentops

# Expose no ports (MCP uses stdin/stdout)
# This container communicates only via stdin/stdout for security

# Health check to verify the application can start
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import server; print('OK')" || exit 1

# Set environment variables
ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1

# Default command
CMD ["python", "-m", "server.main"]