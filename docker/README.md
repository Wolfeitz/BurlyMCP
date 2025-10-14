# Burly MCP Docker Deployment Guide

## Overview

This directory contains Docker configuration files for deploying the Burly MCP server in a secure, containerized environment. The deployment follows security best practices with non-root execution, resource limits, and proper isolation.

## Quick Start

1. **Copy environment template:**
   ```bash
   cp ../.env.example .env
   # Edit .env with your configuration
   ```

2. **Create required directories:**
   ```bash
   mkdir -p logs blog/stage blog/publish
   chmod 755 logs blog/stage blog/publish
   ```

3. **Build and start:**
   ```bash
   docker-compose up -d
   ```

4. **View logs:**
   ```bash
   docker-compose logs -f
   ```

## Security Features

### Container Security
- **Non-root execution**: Runs as `agentops` user (UID 1000)
- **Read-only filesystem**: Root filesystem is read-only
- **No network access**: Uses `network_mode: none` (stdin/stdout only)
- **Capability restrictions**: Drops all capabilities, adds only necessary ones
- **Resource limits**: Memory and CPU limits prevent resource exhaustion

### Volume Security
- **Policy files**: Mounted read-only to prevent tampering
- **Blog staging**: Read-only to prevent unauthorized modifications
- **Blog publish**: Write-only for publishing operations
- **Docker socket**: Read-only for monitoring only
- **Audit logs**: Proper permissions for security logging

### Runtime Security
- **No new privileges**: Prevents privilege escalation
- **Temporary filesystems**: Secure tmpfs mounts with restrictions
- **Health checks**: Monitor container health and responsiveness

## Directory Structure

```
docker/
├── Dockerfile              # Container build configuration
├── docker-compose.yml      # Deployment configuration
├── README.md              # This file
├── logs/                  # Audit logs (created automatically)
├── blog/
│   ├── stage/            # Blog staging area (read-only)
│   └── publish/          # Blog publish area (write-only)
└── .env                  # Environment configuration (create from .env.example)
```

## Configuration

### Environment Variables

Copy `.env.example` to `.env` and configure:

- **GOTIFY_URL**: Notification server URL (optional)
- **GOTIFY_TOKEN**: Notification token (optional)
- **BLOG_STAGE_ROOT**: Blog staging directory
- **BLOG_PUBLISH_ROOT**: Blog publish directory
- **OUTPUT_TRUNCATE_LIMIT**: Maximum output size
- **LOG_LEVEL**: Logging verbosity

### Volume Mounts

The docker-compose configuration includes several volume mounts:

1. **Policy Configuration** (`../policy:/app/policy:ro`)
   - Contains tool definitions and security policies
   - Mounted read-only for security

2. **Audit Logs** (`burly-mcp-logs:/var/log/agentops:rw`)
   - Persistent storage for audit logs
   - Writable for logging operations

3. **Blog Directories**
   - `./blog/stage:/app/blog/stage:ro` - Staging area (read-only)
   - `burly-mcp-blog-publish:/app/blog/publish:rw` - Publish area (writable)

4. **Docker Socket** (`/var/run/docker.sock:/var/run/docker.sock:ro`)
   - Read-only access for container monitoring
   - Required for `docker_ps` tool

## Operations

### Starting the Service

```bash
# Start in background
docker-compose up -d

# Start with logs
docker-compose up
```

### Monitoring

```bash
# View logs
docker-compose logs -f

# Check container status
docker-compose ps

# View resource usage
docker stats burly-mcp-server
```

### Maintenance

```bash
# Restart service
docker-compose restart

# Update configuration
docker-compose down
# Edit .env or docker-compose.yml
docker-compose up -d

# View audit logs
tail -f logs/audit.jsonl
```

### Stopping the Service

```bash
# Stop and remove containers
docker-compose down

# Stop, remove containers and volumes
docker-compose down -v
```

## Troubleshooting

### Common Issues

1. **Permission Errors**
   ```bash
   # Fix directory permissions
   sudo chown -R 1000:1000 logs blog
   chmod 755 logs blog/stage blog/publish
   ```

2. **Docker Socket Access**
   ```bash
   # Verify Docker socket permissions
   ls -la /var/run/docker.sock
   # Should be readable by docker group
   ```

3. **Container Won't Start**
   ```bash
   # Check logs for errors
   docker-compose logs
   
   # Verify configuration
   docker-compose config
   ```

4. **High Resource Usage**
   ```bash
   # Monitor resource usage
   docker stats burly-mcp-server
   
   # Adjust limits in docker-compose.yml
   # Reduce OUTPUT_TRUNCATE_LIMIT in .env
   ```

### Log Analysis

Audit logs are stored in JSON Lines format:

```bash
# View recent audit entries
tail -n 50 logs/audit.jsonl | jq '.'

# Filter by tool
grep '"tool":"docker_ps"' logs/audit.jsonl | jq '.'

# Monitor for failures
grep '"status":"fail"' logs/audit.jsonl | jq '.'
```

### Health Checks

The container includes health checks:

```bash
# Check health status
docker inspect burly-mcp-server | jq '.[0].State.Health'

# Manual health check
docker exec burly-mcp-server python -c "import sys; sys.exit(0)"
```

## Security Considerations

### Production Deployment

1. **Network Security**
   - Use `network_mode: none` (already configured)
   - No exposed ports (MCP uses stdin/stdout)
   - Consider firewall rules for Docker socket access

2. **File System Security**
   - Regular backup of audit logs
   - Monitor for unauthorized file changes
   - Implement log rotation

3. **Access Control**
   - Restrict Docker socket access
   - Use proper file permissions
   - Regular security audits

4. **Monitoring**
   - Set up log aggregation
   - Monitor resource usage
   - Alert on security violations

### Security Scanning

```bash
# Scan container for vulnerabilities
docker run --rm -v /var/run/docker.sock:/var/run/docker.sock \
  aquasec/trivy image burly-mcp-server

# Check for secrets in configuration
docker run --rm -v $(pwd):/src \
  zricethezav/gitleaks:latest detect --source /src
```

## Integration with Open WebUI

To use with Open WebUI:

1. **Configure MCP Connection**
   - Use stdin/stdout communication
   - No network configuration needed
   - Container handles all protocol details

2. **Example Integration**
   ```bash
   # Open WebUI can execute the container directly
   docker run --rm -i \
     --user 1000:1000 \
     -v $(pwd)/policy:/app/policy:ro \
     -v /var/run/docker.sock:/var/run/docker.sock:ro \
     burly-mcp-server
   ```

3. **Security Notes**
   - Container isolation provides security boundary
   - All operations are audited automatically
   - Confirmation required for mutating operations

## Support and Documentation

- **Main Documentation**: See `../docs/` directory
- **Policy Configuration**: See `../policy/tools.yaml`
- **Environment Setup**: See `../.env.example`
- **Security Guide**: See `../docs/security.md` (when available)

For issues and questions, check the audit logs first, then review the troubleshooting section above.