# Burly MCP Deployment Runbook

## Overview

This runbook provides step-by-step instructions for deploying and operating Burly MCP, a secure Model Context Protocol server that enables AI assistants to safely execute system operations.

## Prerequisites

Before deploying Burly MCP, ensure you have:

- Docker and Docker Compose installed
- Basic understanding of container operations
- Access to the system where you want to deploy
- (Optional) A Gotify server for notifications

## Quick Start Deployment

### 1. Clone and Setup

```bash
# Clone the repository
git clone <repository-url>
cd burly-mcp

# Copy environment template
cp .env.example .env
```

### 2. Configure Environment

Edit the `.env` file with your specific settings:

```bash
# Required: Blog directories (create these first)
BLOG_STAGE_ROOT=/path/to/your/blog/staging
BLOG_PUBLISH_ROOT=/path/to/your/blog/public

# Optional: Gotify notifications
GOTIFY_URL=https://your-gotify-server.com
GOTIFY_TOKEN=your-app-token-here

# Optional: Customize limits
TOOL_TIMEOUT_SEC=30
OUTPUT_TRUNCATE_LIMIT=10000
```

### 3. Create Required Directories

```bash
# Create blog directories
mkdir -p /path/to/your/blog/staging
mkdir -p /path/to/your/blog/public

# Create log directory
mkdir -p ./logs
chmod 755 ./logs
```

### 4. Deploy with Docker Compose

```bash
# Start the service
docker-compose up -d

# Check status
docker-compose ps

# View logs
docker-compose logs -f burly-mcp
```

## Detailed Configuration

### Directory Structure

After deployment, your directory structure should look like:

```
burly-mcp/
├── docker-compose.yml     # Container orchestration
├── .env                   # Your environment config
├── policy/
│   └── tools.yaml        # Tool definitions and policies
├── logs/
│   └── audit.jsonl       # Audit trail (created at runtime)
└── docs/                 # Documentation
```

### Policy Configuration

The `policy/tools.yaml` file defines which tools are available and their security constraints. The default configuration includes:

- **docker_ps**: List Docker containers (read-only)
- **disk_space**: Check filesystem usage (read-only)
- **blog_stage_markdown**: Validate blog content (read-only)
- **blog_publish_static**: Publish blog content (requires confirmation)
- **gotify_ping**: Send test notifications (mutating)

### Security Considerations

1. **Container Isolation**: Runs as non-root user (uid 1000)
2. **Path Restrictions**: Blog operations are confined to configured directories
3. **Docker Access**: Read-only access to Docker socket
4. **Audit Logging**: All operations logged to `logs/audit.jsonl`
5. **Confirmation Gates**: Mutating operations require explicit confirmation

## Integration with Open WebUI

### 1. Configure MCP in Open WebUI

Add Burly MCP as an MCP server in your Open WebUI configuration:

```json
{
  "mcpServers": {
    "burly-mcp": {
      "command": "docker",
      "args": ["exec", "-i", "burly-mcp", "python", "-m", "server.main"],
      "env": {},
      "disabled": false
    }
  }
}
```

### 2. Test the Connection

In Open WebUI, try these commands:
- "List my Docker containers"
- "Check disk space"
- "What tools are available?"

## Monitoring and Maintenance

### Health Checks

```bash
# Check container status
docker-compose ps

# Check recent logs
docker-compose logs --tail=50 burly-mcp

# Check audit logs
tail -f logs/audit.jsonl | jq '.'
```

### Log Rotation

Set up log rotation for audit logs:

```bash
# Add to /etc/logrotate.d/burly-mcp
/path/to/burly-mcp/logs/audit.jsonl {
    daily
    rotate 30
    compress
    delaycompress
    missingok
    notifempty
    copytruncate
}
```

### Updates and Maintenance

```bash
# Update to latest version
git pull
docker-compose pull
docker-compose up -d

# Backup configuration
tar -czf burly-mcp-backup-$(date +%Y%m%d).tar.gz .env policy/ logs/
```

## Troubleshooting

### Common Issues

**Container won't start:**
```bash
# Check logs for errors
docker-compose logs burly-mcp

# Common causes:
# - Missing .env file
# - Invalid directory paths
# - Permission issues
```

**Docker operations fail:**
```bash
# Verify Docker socket access
docker exec burly-mcp docker ps

# If fails, check docker-compose.yml socket mount
```

**Blog operations fail:**
```bash
# Check directory permissions
ls -la /path/to/blog/directories

# Ensure directories exist and are accessible
```

**Gotify notifications not working:**
```bash
# Test Gotify connection
curl -X POST "https://your-gotify-server.com/message" \
  -H "X-Gotify-Key: your-token" \
  -d '{"message": "test", "title": "test"}'
```

### Debug Mode

Enable debug logging by modifying docker-compose.yml:

```yaml
environment:
  - LOG_LEVEL=DEBUG
```

### Getting Help

1. Check the audit logs: `tail -f logs/audit.jsonl`
2. Review container logs: `docker-compose logs burly-mcp`
3. Verify configuration: `docker-compose config`
4. Test individual tools through MCP protocol

## Security Best Practices

1. **Regular Updates**: Keep Docker images and dependencies updated
2. **Audit Review**: Regularly review audit logs for suspicious activity
3. **Access Control**: Limit who can modify policy files
4. **Network Security**: Run on isolated networks when possible
5. **Backup Strategy**: Regular backups of configuration and logs

## Performance Tuning

### Resource Limits

Adjust container resources in docker-compose.yml:

```yaml
deploy:
  resources:
    limits:
      memory: 512M
      cpus: '0.5'
```

### Tool Timeouts

Adjust timeouts in .env:

```bash
TOOL_TIMEOUT_SEC=60  # Increase for slow operations
OUTPUT_TRUNCATE_LIMIT=50000  # Increase for verbose tools
```

This runbook should get you started with Burly MCP. For more detailed configuration options, see `docs/config.md`.