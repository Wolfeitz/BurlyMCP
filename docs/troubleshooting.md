# Troubleshooting Guide

## Overview

This guide provides systematic approaches to diagnosing and resolving common issues with Burly MCP. Issues are organized by category with step-by-step diagnostic procedures and solutions.

## Quick Diagnostic Commands

Before diving into specific issues, run these commands to gather system information:

```bash
# System status
docker-compose ps
docker-compose logs --tail=50 burly-mcp
docker system df
df -h

# Application status
docker exec burly-mcp python -c "import burly_mcp; print('Import successful')"
docker exec burly-mcp ls -la /app/config/
docker exec burly-mcp ls -la /var/log/agentops/

# Network connectivity
docker exec burly-mcp ping -c 3 8.8.8.8
docker exec burly-mcp curl -I https://httpbin.org/get

# Resource usage
docker stats burly-mcp --no-stream
```

## Container Issues

### Container Won't Start

**Symptoms:**
- Container exits immediately
- "Exited (1)" or similar status
- No response to health checks

**Diagnostic Steps:**

1. **Check container logs:**
```bash
docker-compose logs burly-mcp
docker logs $(docker-compose ps -q burly-mcp)
```

2. **Verify environment configuration:**
```bash
# Check environment file exists and is readable
ls -la .env*
cat .env | grep -v '^#' | grep -v '^$'

# Validate environment variables
docker-compose config
```

3. **Test image integrity:**
```bash
# Verify image exists and is accessible
docker images | grep burly-mcp
docker run --rm burly-mcp:latest python --version
```

**Common Causes and Solutions:**

**Missing Environment File:**
```bash
# Solution: Create environment file
cp .env.example .env
# Edit .env with appropriate values
```

**Invalid Configuration:**
```bash
# Check for syntax errors in docker-compose.yml
docker-compose config

# Validate environment variables
docker-compose run --rm burly-mcp env | sort
```

**Permission Issues:**
```bash
# Fix directory permissions
sudo chown -R 1000:1000 ./logs ./config
sudo chmod -R 755 ./config
sudo chmod -R 755 ./logs
```

**Port Conflicts:**
```bash
# Check for port conflicts
netstat -tulpn | grep :8080
lsof -i :8080

# Solution: Change port in docker-compose.yml or stop conflicting service
```

### Container Starts But Crashes

**Symptoms:**
- Container starts then exits after a few seconds
- Restart loop behavior
- Health check failures

**Diagnostic Steps:**

1. **Monitor startup sequence:**
```bash
# Watch logs in real-time
docker-compose logs -f burly-mcp

# Check exit code
docker-compose ps
```

2. **Test configuration validation:**
```bash
# Run configuration validation
docker-compose run --rm burly-mcp python -c "
from burly_mcp.config import Config
config = Config()
errors = config.validate()
if errors:
    print('Configuration errors:', errors)
else:
    print('Configuration valid')
"
```

3. **Check resource constraints:**
```bash
# Monitor resource usage during startup
docker stats burly-mcp --no-stream
```

**Common Solutions:**

**Configuration Validation Errors:**
```bash
# Check required directories exist
mkdir -p /data/blog/stage /data/blog/publish /var/log/agentops

# Verify paths in environment file
ls -la $(grep BLOG_STAGE_ROOT .env | cut -d= -f2)
ls -la $(grep BLOG_PUBLISH_ROOT .env | cut -d= -f2)
```

**Memory/Resource Issues:**
```bash
# Increase memory limits in docker-compose.yml
deploy:
  resources:
    limits:
      memory: 1G
      cpus: '1.0'
```

**Python Import Errors:**
```bash
# Test Python environment
docker-compose run --rm burly-mcp python -c "
import sys
print('Python path:', sys.path)
try:
    import burly_mcp
    print('Import successful')
except ImportError as e:
    print('Import error:', e)
"
```

## Configuration Issues

### Environment Variable Problems

**Symptoms:**
- Configuration validation errors
- Features not working as expected
- Security warnings in logs

**Diagnostic Steps:**

1. **Validate environment variables:**
```bash
# Check all environment variables are set
docker-compose run --rm burly-mcp env | grep BURLY
docker-compose run --rm burly-mcp env | grep BLOG
docker-compose run --rm burly-mcp env | grep GOTIFY
```

2. **Test configuration loading:**
```bash
# Test configuration parsing
docker-compose run --rm burly-mcp python -c "
import os
from burly_mcp.config import Config
config = Config()
print('Config dir:', config.config_dir)
print('Log dir:', config.log_dir)
print('Blog stage:', config.blog_stage_root)
print('Blog publish:', config.blog_publish_root)
"
```

**Common Issues and Solutions:**

**Missing Required Variables:**
```bash
# Check .env file has all required variables
grep -E '^(BLOG_STAGE_ROOT|BLOG_PUBLISH_ROOT)=' .env

# Add missing variables
echo "BLOG_STAGE_ROOT=/data/blog/stage" >> .env
echo "BLOG_PUBLISH_ROOT=/data/blog/publish" >> .env
```

**Invalid Path Values:**
```bash
# Verify paths exist and are accessible
docker-compose run --rm burly-mcp ls -la /data/blog/stage
docker-compose run --rm burly-mcp ls -la /data/blog/publish

# Create missing directories
mkdir -p /data/blog/stage /data/blog/publish
```

**Secret Management Issues:**
```bash
# Check Docker secrets (if using)
docker secret ls
docker-compose run --rm burly-mcp cat /run/secrets/gotify_token

# Verify environment variable secrets
docker-compose run --rm burly-mcp python -c "
import os
print('GOTIFY_TOKEN set:', bool(os.getenv('GOTIFY_TOKEN')))
print('GOTIFY_URL set:', bool(os.getenv('GOTIFY_URL')))
"
```

### Policy Configuration Issues

**Symptoms:**
- Tools not available
- Permission denied errors
- Schema validation failures

**Diagnostic Steps:**

1. **Validate policy file:**
```bash
# Check policy file exists and is readable
docker-compose run --rm burly-mcp ls -la /config/policy/tools.yaml
docker-compose run --rm burly-mcp cat /config/policy/tools.yaml
```

2. **Test YAML syntax:**
```bash
# Validate YAML syntax
docker-compose run --rm burly-mcp python -c "
import yaml
with open('/config/policy/tools.yaml', 'r') as f:
    try:
        policy = yaml.safe_load(f)
        print('YAML syntax valid')
        print('Tools defined:', list(policy.get('tools', {}).keys()))
    except yaml.YAMLError as e:
        print('YAML error:', e)
"
```

3. **Test tool registration:**
```bash
# Check tool registration
docker-compose run --rm burly-mcp python -c "
from burly_mcp.tools.registry import ToolRegistry
registry = ToolRegistry()
print('Available tools:', registry.list_tools())
"
```

**Common Solutions:**

**YAML Syntax Errors:**
```bash
# Use yamllint to check syntax
yamllint config/policy/tools.yaml

# Common fixes:
# - Fix indentation (use spaces, not tabs)
# - Quote string values with special characters
# - Ensure proper list formatting
```

**Schema Validation Errors:**
```bash
# Test individual tool schemas
docker-compose run --rm burly-mcp python -c "
import jsonschema
import yaml

with open('/config/policy/tools.yaml', 'r') as f:
    policy = yaml.safe_load(f)

for tool_name, tool_config in policy['tools'].items():
    try:
        # Validate schema structure
        schema = tool_config.get('args_schema', {})
        jsonschema.Draft7Validator.check_schema(schema)
        print(f'{tool_name}: Schema valid')
    except Exception as e:
        print(f'{tool_name}: Schema error - {e}')
"
```

## Docker Integration Issues

### Docker Socket Access Problems

**Symptoms:**
- "Cannot connect to Docker daemon" errors
- Docker commands fail within container
- Permission denied on Docker socket

**Diagnostic Steps:**

1. **Check Docker socket mount:**
```bash
# Verify socket is mounted
docker-compose run --rm burly-mcp ls -la /var/run/docker.sock

# Check socket permissions
ls -la /var/run/docker.sock
```

2. **Test Docker connectivity:**
```bash
# Test Docker commands from within container
docker-compose run --rm burly-mcp docker version
docker-compose run --rm burly-mcp docker ps
```

3. **Check user permissions:**
```bash
# Check if user is in docker group
groups $(whoami) | grep docker

# Check container user
docker-compose run --rm burly-mcp id
```

**Solutions:**

**Socket Permission Issues:**
```bash
# Add user to docker group (host system)
sudo usermod -aG docker $USER
# Logout and login again

# Or change socket permissions (less secure)
sudo chmod 666 /var/run/docker.sock
```

**Socket Mount Issues:**
```bash
# Verify docker-compose.yml has correct mount
volumes:
  - /var/run/docker.sock:/var/run/docker.sock:ro

# For rootless Docker
volumes:
  - ${XDG_RUNTIME_DIR}/docker.sock:/var/run/docker.sock:ro
```

**SELinux Issues (RHEL/CentOS):**
```bash
# Check SELinux status
sestatus

# Allow Docker socket access
sudo setsebool -P container_manage_cgroup on
sudo chcon -Rt svirt_sandbox_file_t /var/run/docker.sock
```

### Docker Command Failures

**Symptoms:**
- Docker tools return errors
- Timeout errors on Docker operations
- Incomplete or truncated output

**Diagnostic Steps:**

1. **Test Docker commands manually:**
```bash
# Test basic Docker functionality
docker-compose run --rm burly-mcp docker info
docker-compose run --rm burly-mcp docker system df
```

2. **Check timeout settings:**
```bash
# Verify timeout configuration
grep DOCKER_TIMEOUT .env
grep TOOL_TIMEOUT .env
```

3. **Monitor resource usage:**
```bash
# Check if Docker daemon is under load
docker system events &
# Run problematic command
# Check events for errors
```

**Solutions:**

**Timeout Issues:**
```bash
# Increase timeout values in .env
DOCKER_TIMEOUT=60
DEFAULT_TIMEOUT_SEC=45
```

**Resource Constraints:**
```bash
# Check Docker daemon resources
docker system df
docker system prune -f

# Increase container resources
deploy:
  resources:
    limits:
      memory: 1G
      cpus: '1.0'
```

## Network and Connectivity Issues

### Notification Service Problems

**Symptoms:**
- Gotify notifications not sent
- Webhook failures
- Network timeout errors

**Diagnostic Steps:**

1. **Test network connectivity:**
```bash
# Test basic connectivity
docker-compose run --rm burly-mcp ping -c 3 8.8.8.8
docker-compose run --rm burly-mcp nslookup google.com

# Test specific service
docker-compose run --rm burly-mcp curl -I https://your-gotify-server.com
```

2. **Verify notification configuration:**
```bash
# Check notification settings
docker-compose run --rm burly-mcp python -c "
import os
print('Notifications enabled:', os.getenv('NOTIFICATIONS_ENABLED'))
print('Providers:', os.getenv('NOTIFICATION_PROVIDERS'))
print('Gotify URL:', os.getenv('GOTIFY_URL'))
print('Gotify token set:', bool(os.getenv('GOTIFY_TOKEN')))
"
```

3. **Test notification manually:**
```bash
# Test Gotify directly
curl -X POST "https://your-gotify-server.com/message" \
  -H "X-Gotify-Key: your-token" \
  -H "Content-Type: application/json" \
  -d '{"message": "Test message", "title": "Test", "priority": 5}'
```

**Solutions:**

**DNS Resolution Issues:**
```bash
# Add DNS servers to docker-compose.yml
services:
  burly-mcp:
    dns:
      - 8.8.8.8
      - 1.1.1.1
```

**SSL Certificate Issues:**
```bash
# Test SSL connectivity
docker-compose run --rm burly-mcp openssl s_client -connect your-gotify-server.com:443

# Skip SSL verification (not recommended for production)
GOTIFY_VERIFY_SSL=false
```

**Firewall/Proxy Issues:**
```bash
# Configure proxy if needed
environment:
  - HTTP_PROXY=http://proxy.company.com:8080
  - HTTPS_PROXY=http://proxy.company.com:8080
  - NO_PROXY=localhost,127.0.0.1
```

### MCP Protocol Issues

**Symptoms:**
- MCP client cannot connect
- Protocol errors in logs
- Timeout on MCP operations

**Diagnostic Steps:**

1. **Test MCP server startup:**
```bash
# Check if MCP server is listening
docker-compose logs burly-mcp | grep -i "mcp\|server\|listening"
```

2. **Test MCP protocol manually:**
```bash
# Test MCP protocol directly
echo '{"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {"protocolVersion": "2024-11-05", "capabilities": {}, "clientInfo": {"name": "test", "version": "1.0.0"}}}' | \
docker-compose exec -T burly-mcp python -m burly_mcp.server.main
```

3. **Check client configuration:**
```bash
# Verify client MCP configuration
cat ~/.config/mcp/settings.json | jq '.mcpServers."burly-mcp"'
```

**Solutions:**

**Protocol Version Mismatch:**
```bash
# Update client configuration to match server version
{
  "mcpServers": {
    "burly-mcp": {
      "command": "docker",
      "args": ["exec", "-i", "burly-mcp", "python", "-m", "burly_mcp.server.main"],
      "env": {}
    }
  }
}
```

**Communication Issues:**
```bash
# Test stdin/stdout communication
echo "test" | docker-compose exec -T burly-mcp cat
```

## Performance Issues

### High Resource Usage

**Symptoms:**
- High CPU or memory usage
- Slow response times
- Container OOM kills

**Diagnostic Steps:**

1. **Monitor resource usage:**
```bash
# Real-time monitoring
docker stats burly-mcp

# Historical usage
docker-compose logs burly-mcp | grep -i "memory\|cpu\|resource"
```

2. **Check for resource leaks:**
```bash
# Monitor over time
while true; do
  docker stats burly-mcp --no-stream
  sleep 10
done
```

3. **Profile application:**
```bash
# Enable debug logging
LOG_LEVEL=DEBUG docker-compose up -d
docker-compose logs -f burly-mcp
```

**Solutions:**

**Memory Leaks:**
```bash
# Restart container periodically
# Add to crontab:
# 0 2 * * * docker-compose restart burly-mcp
```

**Resource Limits:**
```bash
# Adjust limits in docker-compose.yml
deploy:
  resources:
    limits:
      memory: 1G
      cpus: '1.0'
    reservations:
      memory: 256M
      cpus: '0.2'
```

**Concurrent Operations:**
```bash
# Reduce concurrent tool limit
MAX_CONCURRENT_TOOLS=3
DEFAULT_TIMEOUT_SEC=30
```

### Slow Tool Execution

**Symptoms:**
- Tools take longer than expected
- Timeout errors
- Unresponsive behavior

**Diagnostic Steps:**

1. **Test individual tools:**
```bash
# Test Docker tools
docker-compose run --rm burly-mcp docker ps
time docker-compose run --rm burly-mcp docker ps

# Test file operations
time docker-compose run --rm burly-mcp ls -la /data/blog/stage
```

2. **Check system resources:**
```bash
# Host system resources
top
iostat -x 1
df -h
```

3. **Monitor tool execution:**
```bash
# Enable debug logging for tools
LOG_LEVEL=DEBUG docker-compose restart burly-mcp
docker-compose logs -f burly-mcp | grep -i "tool\|execution\|timeout"
```

**Solutions:**

**Increase Timeouts:**
```bash
# Adjust timeout values
DEFAULT_TIMEOUT_SEC=60
DOCKER_TIMEOUT=45
```

**Optimize File Operations:**
```bash
# Use faster storage
# Mount SSD volumes for blog directories
# Enable filesystem caching
```

**System Optimization:**
```bash
# Increase file descriptor limits
ulimits:
  nofile:
    soft: 65536
    hard: 65536

# Optimize Docker daemon
# Add to /etc/docker/daemon.json:
{
  "storage-driver": "overlay2",
  "log-driver": "json-file",
  "log-opts": {
    "max-size": "10m",
    "max-file": "3"
  }
}
```

## Log Analysis and Debugging

### Log Collection

```bash
#!/bin/bash
# collect-logs.sh - Comprehensive log collection script

TIMESTAMP=$(date +%Y%m%d_%H%M%S)
LOG_DIR="burly-mcp-logs-$TIMESTAMP"
mkdir -p "$LOG_DIR"

# Container logs
docker-compose logs --no-color > "$LOG_DIR/container.log"
docker-compose logs --no-color --timestamps > "$LOG_DIR/container-timestamps.log"

# System logs
journalctl -u docker.service --since "1 hour ago" > "$LOG_DIR/docker-service.log"
dmesg | tail -100 > "$LOG_DIR/dmesg.log"

# Application logs
docker-compose exec burly-mcp find /var/log/agentops -name "*.log" -o -name "*.jsonl" | \
  xargs -I {} docker-compose exec burly-mcp cp {} /tmp/
docker cp $(docker-compose ps -q burly-mcp):/tmp/ "$LOG_DIR/app-logs/"

# Configuration
docker-compose config > "$LOG_DIR/docker-compose-config.yml"
docker-compose exec burly-mcp env | sort > "$LOG_DIR/environment.txt"

# System info
docker version > "$LOG_DIR/docker-version.txt"
docker-compose version > "$LOG_DIR/docker-compose-version.txt"
docker system df > "$LOG_DIR/docker-system-df.txt"
docker system info > "$LOG_DIR/docker-system-info.txt"

# Create archive
tar -czf "burly-mcp-logs-$TIMESTAMP.tar.gz" "$LOG_DIR"
echo "Logs collected in: burly-mcp-logs-$TIMESTAMP.tar.gz"
```

### Log Analysis Patterns

**Common Error Patterns:**
```bash
# Configuration errors
grep -i "config\|validation\|missing" container.log

# Permission errors
grep -i "permission\|denied\|access" container.log

# Network errors
grep -i "network\|connection\|timeout\|dns" container.log

# Resource errors
grep -i "memory\|cpu\|resource\|limit" container.log

# Tool execution errors
grep -i "tool\|execution\|failed\|error" container.log
```

**Performance Analysis:**
```bash
# Response time analysis
grep -E "took|duration|elapsed" container.log | \
  awk '{print $NF}' | sort -n | tail -10

# Error frequency
grep -i error container.log | \
  awk '{print $1, $2}' | sort | uniq -c | sort -nr
```

## Getting Help

### Information to Collect

When seeking help, collect this information:

1. **System Information:**
```bash
# System details
uname -a
docker version
docker-compose version
cat /etc/os-release
```

2. **Configuration:**
```bash
# Sanitized configuration (remove secrets)
docker-compose config | sed 's/GOTIFY_TOKEN=.*/GOTIFY_TOKEN=***REDACTED***/'
```

3. **Logs:**
```bash
# Recent logs with timestamps
docker-compose logs --timestamps --tail=100 burly-mcp
```

4. **Error Details:**
```bash
# Specific error messages
docker-compose logs burly-mcp | grep -i error | tail -10
```

### Support Channels

1. **GitHub Issues**: For bugs and feature requests
2. **Documentation**: Check docs/ directory for detailed guides
3. **Community Forums**: For general questions and discussions
4. **Security Issues**: Use security reporting process for vulnerabilities

### Self-Help Checklist

Before seeking help:

- [ ] Checked container logs for error messages
- [ ] Verified environment configuration
- [ ] Tested with minimal configuration
- [ ] Checked file permissions and directory access
- [ ] Verified network connectivity
- [ ] Reviewed recent changes to configuration
- [ ] Tested with latest image version
- [ ] Checked system resources (disk space, memory)
- [ ] Reviewed security logs for access issues
- [ ] Tested individual components in isolation

This troubleshooting guide should help you diagnose and resolve most common issues with Burly MCP. For complex issues, use the log collection script and provide detailed information when seeking help.