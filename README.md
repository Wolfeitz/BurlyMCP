# Burly MCP Server

A secure, policy-driven Model Context Protocol (MCP) server that enables AI assistants to safely execute system operations through a standardized interface.

## What is MCP and Why Should You Care?

The **Model Context Protocol (MCP)** is a standardized way for AI assistants to interact with external tools and services. Think of it as a secure bridge between AI systems and your infrastructure.

### The Problem MCP Solves

Traditional AI assistants are limited to text generation and can't interact with your systems directly. When you ask an AI to "check my Docker containers" or "publish my blog post," it can only give you the commands to run manually.

### The MCP Solution

MCP enables AI assistants to:
- ✅ Execute real system operations safely
- ✅ Follow strict security policies
- ✅ Provide immediate, actionable results
- ✅ Maintain comprehensive audit trails

### Why "Burly" MCP?

This implementation is "burly" because it's built with security and robustness as primary concerns:
- **Policy-driven**: Only whitelisted operations are allowed
- **Containerized**: Runs with minimal privileges in isolation
- **Audited**: Every operation is logged for compliance
- **Confirmed**: Dangerous operations require explicit approval

## Runtime Container Interface

BurlyMCP is distributed as a standalone service container that exposes HTTP endpoints for integration with downstream systems. The container provides a stable API contract that remains consistent across internal implementation changes.

### Container Contract

**Official Interface:**
- **Port**: 9400 (HTTP)
- **Health Check**: `GET /health` - Returns service status and capabilities
- **MCP Endpoint**: `POST /mcp` - Accepts MCP protocol requests via HTTP
- **Process**: Runs as PID 1 with graceful shutdown on SIGTERM (≤10 seconds)

**Published Images:**
- `ghcr.io/wolfeitz/burlymcp:main` - Latest stable build from main branch
- `ghcr.io/wolfeitz/burlymcp:<branch>-<sha>` - Specific commit builds for traceability

### Quickstart (No Privileges)

This sequence works on any clean Linux box with only Docker installed:

```bash
# Start the container
docker run --rm -p 9400:9400 ghcr.io/wolfeitz/burlymcp:main

# Test health endpoint
curl http://127.0.0.1:9400/health

# Test MCP functionality
curl -X POST http://127.0.0.1:9400/mcp \
  -H 'content-type: application/json' \
  -d '{"id":"1","method":"list_tools","params":{}}'
```

The container starts successfully without any external dependencies, configuration files, or elevated privileges.

### Deployment Options

**Minimal Mode (Recommended for testing):**
```bash
docker run --rm -p 9400:9400 ghcr.io/wolfeitz/burlymcp:main
```
- No elevated privileges required
- Basic system tools available (disk_space, etc.)
- Docker tools gracefully degrade if socket not mounted

**Privileged Mode (Docker operations):**
```bash
# Get your Docker group GID
DOCKER_GID=$(getent group docker | cut -d: -f3)

# Run with Docker socket access
docker run --rm -p 9400:9400 \
  --group-add $DOCKER_GID \
  -v /var/run/docker.sock:/var/run/docker.sock:ro \
  ghcr.io/wolfeitz/burlymcp:main
```
- Enables Docker inspection tools (docker_ps)
- **Security Warning**: Mounting Docker socket grants root-equivalent access to the host

**Production Mode (Persistent data):**
```bash
docker run -d --name burlymcp \
  -p 9400:9400 \
  -v ./logs:/var/log/agentops \
  -v ./blog/stage:/app/data/blog/stage:ro \
  -v ./blog/publish:/app/data/blog/publish:rw \
  -e GOTIFY_URL=https://<your-gotify-server> \
  -e GOTIFY_TOKEN=<your-app-token> \
  ghcr.io/wolfeitz/burlymcp:main
```

### Environment Variables

**Core Configuration:**
- `LOG_LEVEL` - Logging verbosity (DEBUG, INFO, WARNING, ERROR) [default: INFO]
- `AUDIT_LOG_PATH` - Audit log file location [default: /var/log/agentops/audit.jsonl]
- `POLICY_FILE` - Policy configuration file [default: /app/BurlyMCP/config/policy/tools.yaml]

**Blog Management:**
- `BLOG_STAGE_ROOT` - Staging directory for blog content [default: /app/data/blog/stage]
- `BLOG_PUBLISH_ROOT` - Publication directory for blog content [default: /app/data/blog/publish]

**Notifications (Optional):**
- `GOTIFY_URL` - Gotify server URL for notifications [default: disabled]
- `GOTIFY_TOKEN` - Gotify application token [default: disabled]

**Security:**
- `STRICT_SECURITY_MODE` - Enable strict security validation [default: true]
- `RATE_LIMIT_DISABLED` - Disable API rate limiting for lab use [default: false]

**Docker Integration:**
- `DOCKER_SOCKET` - Docker socket path [default: /var/run/docker.sock]
- `DOCKER_TIMEOUT` - Docker operation timeout in seconds [default: 30]

### Security Considerations

**Container Security:**
- Runs as non-root user (mcp:1000) with minimal privileges
- Uses debian:trixie-slim base image for security and size
- No Docker daemon included - only optional client capability
- Environment variable sanitization prevents secret leakage to subprocesses

**API Security:**
- Rate limiting enabled by default (60 requests/minute per IP)
- Request size limits prevent resource exhaustion (10KB max)
- Input sanitization and validation on all endpoints
- Structured error responses prevent information disclosure

**Optional Elevated Privileges:**
- Docker socket mounting is operator choice, never required
- Blog directory mounting requires proper file permissions
- Notification tokens should be provided via environment variables, not embedded

### Shutdown Behavior

The container handles shutdown gracefully:
- Responds to SIGTERM with graceful shutdown
- Completes in-flight requests within 10 seconds
- Flushes audit logs and closes file handles
- Exits with appropriate status code

**PID 1 Expectations:**
- The HTTP bridge (uvicorn) runs as PID 1 inside the container
- Handles signal forwarding and zombie process reaping
- Maintains service availability until shutdown signal received

## Quick Start

### Prerequisites

**System Requirements:**
- Docker (for container deployment)
- Linux host (any distribution with Docker support)
- Basic understanding of containerization

**Optional Dependencies:**
- Docker daemon (for Docker inspection tools)
- Gotify server (for notifications)
- Persistent storage (for audit logs and blog content)

### 1. Basic Container Test

```bash
# Pull and test the container
docker run --rm -p 9400:9400 ghcr.io/wolfeitz/burlymcp:main

# In another terminal, verify it's working
curl http://localhost:9400/health
```

### 2. Integration with Open WebUI

See [docs/open-webui.md](docs/open-webui.md) for detailed integration instructions.

### 3. Docker Compose Examples

For docker-compose deployment examples, see the [examples/compose/](examples/compose/) directory. These are reference configurations only - the official deployment method is the published container image.

## Alternative: Manual Installation

If you prefer to run without Docker:

```bash
# Install Python dependencies
pip install -e .

# Create required directories
mkdir -p ./logs ./blog/stage ./blog/publish

# Set environment variables for local development
export POLICY_FILE=config/policy/tools.yaml
export AUDIT_LOG_PATH=./logs/audit.jsonl
export LOG_DIR=./logs
export BLOG_STAGE_ROOT=./blog/stage
export BLOG_PUBLISH_ROOT=./blog/publish
export NOTIFICATIONS_ENABLED=false

# Run the MCP server
python -m burly_mcp.server.main
```

**Note:** Manual installation requires:
- Python 3.12+
- Local directories for logs and blog content
- Environment variables configured for local paths
- Docker daemon running (for Docker tools, optional)

## Available Tools

Burly MCP provides these system operation tools:

### 📦 Docker Operations
- **`docker_ps`**: List running containers with status information
- Safe read-only access to Docker daemon

### 💾 System Monitoring  
- **`disk_space`**: Check filesystem usage across mounted volumes
- Helps monitor storage capacity and usage patterns

### 📝 Blog Management
- **`blog_stage_markdown`**: Validate blog posts with YAML front-matter
- **`blog_publish_static`**: Publish validated content (requires confirmation)
- Secure file operations with path traversal protection

### 🔔 Notifications
- **`gotify_ping`**: Send test notifications via Gotify
- Optional integration for operation alerts

## Security Model

Burly MCP implements defense-in-depth security:

### 🛡️ Container Security
- Runs as non-root user (`agentops:1000`)
- Read-only filesystem with minimal writable areas
- No network ports exposed (stdin/stdout only)
- Resource limits prevent resource exhaustion

### 📋 Policy Enforcement
- All tools must be explicitly whitelisted in `policy/tools.yaml`
- JSON Schema validation for all tool arguments
- Path traversal protection for file operations
- Timeout enforcement prevents hanging operations

### 🔍 Audit and Monitoring
- Every operation logged in JSON Lines format
- Argument hashing preserves privacy while enabling audit
- Optional Gotify notifications for real-time monitoring
- Comprehensive execution metrics and error tracking

### ⚠️ Confirmation Workflow
- Mutating operations require explicit confirmation
- Two-step process prevents accidental destructive actions
- Clear indication of what will be modified

## Configuration and Deployment

### Default Internal Paths

The container includes these default paths that work without external mounts:

**Configuration Files:**
- `/app/BurlyMCP/config/policy/tools.yaml` - Default policy file (embedded in image)
- `/app/BurlyMCP/` - Complete BurlyMCP source tree

**Data Directories:**
- `/var/log/agentops/audit.jsonl` - Audit log file
- `/var/log/agentops/` - Log directory
- `/app/data/blog/stage/` - Blog staging directory
- `/app/data/blog/publish/` - Blog publication directory

**Runtime Environment:**
- `/opt/venv/` - Python virtual environment
- `/app/` - Application root directory
- User: `mcp` (UID 1000, GID 1000)

### Environment Variable Overrides

All default paths and settings can be overridden via environment variables:

**Core Configuration:**
```bash
# Logging and Audit
LOG_LEVEL=INFO                                    # DEBUG, INFO, WARNING, ERROR
AUDIT_LOG_PATH=/var/log/agentops/audit.jsonl     # Audit log file location
POLICY_FILE=/app/BurlyMCP/config/policy/tools.yaml # Policy configuration file

# Server Settings
PORT=9400                                         # HTTP server port
SERVER_NAME=burlymcp                             # Server identifier
SERVER_VERSION=0.1.0                            # Version string
STRICT_SECURITY_MODE=true                        # Enable strict security validation
```

**Blog Management:**
```bash
# Blog Content Directories
BLOG_STAGE_ROOT=/app/data/blog/stage             # Staging directory (read-only)
BLOG_PUBLISH_ROOT=/app/data/blog/publish         # Publication directory (read-write)

# Blog Tool Settings
MAX_OUTPUT_SIZE=1048576                          # Maximum tool output size (1MB)
```

**Docker Integration:**
```bash
# Docker Configuration
DOCKER_SOCKET=/var/run/docker.sock              # Docker socket path
DOCKER_TIMEOUT=30                                # Docker operation timeout (seconds)
```

**Notifications (Optional):**
```bash
# Gotify Integration
GOTIFY_URL=https://<your-gotify-server>          # Gotify server URL
GOTIFY_TOKEN=<your-application-token>            # Gotify app token
NOTIFICATIONS_ENABLED=false                      # Enable/disable notifications
```

**API Security:**
```bash
# Rate Limiting and Security
RATE_LIMIT_DISABLED=false                        # Disable rate limiting for lab use
MAX_REQUEST_SIZE=10240                           # Maximum request body size (10KB)
```

### Volume Mounts for Data Persistence

**Audit Logs (Recommended for production):**
```bash
-v ./logs:/var/log/agentops
```
- Persists audit trails across container restarts
- Enables log analysis and compliance reporting
- Directory must be writable by UID 1000

**Blog Content Management:**
```bash
-v ./blog/stage:/app/data/blog/stage:ro          # Staging content (read-only)
-v ./blog/publish:/app/data/blog/publish:rw      # Published content (read-write)
```
- Enables blog_stage_markdown and blog_publish_static tools
- Staging directory should be read-only for security
- Publish directory requires write access for UID 1000

**Custom Policy File:**
```bash
-v ./custom-policy.yaml:/app/BurlyMCP/config/policy/tools.yaml:ro
```
- Override default policy with custom tool configurations
- File must be readable by UID 1000
- Changes require container restart

### Deployment Scenarios

**Scenario 1: Development/Testing (Minimal)**
```bash
docker run --rm -p 9400:9400 ghcr.io/wolfeitz/burlymcp:main
```
- No external dependencies
- Basic system tools only
- Ephemeral audit logs
- Suitable for API testing and development

**Scenario 2: Production Monitoring (Persistent Logs)**
```bash
docker run -d --name burlymcp \
  -p 9400:9400 \
  -v ./logs:/var/log/agentops \
  -e LOG_LEVEL=WARNING \
  -e GOTIFY_URL=https://<your-notification-server> \
  -e GOTIFY_TOKEN=<your-production-token> \
  --restart unless-stopped \
  ghcr.io/wolfeitz/burlymcp:main
```
- Persistent audit logging
- Production notification integration
- Automatic restart on failure
- Reduced log verbosity

**Scenario 3: Infrastructure Operations (Docker Access)**
```bash
# Get Docker group GID
DOCKER_GID=$(getent group docker | cut -d: -f3)

docker run -d --name burlymcp-ops \
  -p 9400:9400 \
  --group-add $DOCKER_GID \
  -v /var/run/docker.sock:/var/run/docker.sock:ro \
  -v ./logs:/var/log/agentops \
  -e LOG_LEVEL=INFO \
  --restart unless-stopped \
  ghcr.io/wolfeitz/burlymcp:main
```
- **⚠️ Security Warning**: Docker socket access grants root-equivalent host access
- Enables docker_ps and container inspection tools
- Should only be used on trusted networks
- Consider firewall rules to restrict access to port 9400

**Scenario 4: Content Management (Blog Publishing)**
```bash
docker run -d --name burlymcp-blog \
  -p 9400:9400 \
  -v ./blog/content:/app/data/blog/stage:ro \
  -v ./blog/public:/app/data/blog/publish:rw \
  -v ./logs:/var/log/agentops \
  -e BLOG_STAGE_ROOT=/app/data/blog/stage \
  -e BLOG_PUBLISH_ROOT=/app/data/blog/publish \
  --restart unless-stopped \
  ghcr.io/wolfeitz/burlymcp:main
```
- Enables blog content management tools
- Staging directory mounted read-only for safety
- Publication directory requires write access
- Audit logs track all publishing operations

**Scenario 5: High Security (Air-gapped)**
```bash
docker run -d --name burlymcp-secure \
  -p 127.0.0.1:9400:9400 \
  -v ./logs:/var/log/agentops \
  -e RATE_LIMIT_DISABLED=false \
  -e STRICT_SECURITY_MODE=true \
  -e LOG_LEVEL=DEBUG \
  --read-only \
  --tmpfs /tmp:noexec,nosuid,size=100m \
  --restart unless-stopped \
  ghcr.io/wolfeitz/burlymcp:main
```
- Binds only to localhost (no external access)
- Read-only filesystem with minimal tmpfs
- Enhanced security logging
- Rate limiting enforced
- No external network dependencies

### Security Warnings and Best Practices

**Docker Socket Mounting:**
- ⚠️ **Critical**: Mounting `/var/run/docker.sock` grants root-equivalent access to the host
- Only mount Docker socket on trusted, isolated networks
- Consider using Docker-in-Docker or rootless Docker for additional isolation
- Monitor audit logs for all Docker operations

**Network Exposure:**
- Default binding (0.0.0.0:9400) exposes the service to all network interfaces
- For production, consider binding to specific interfaces: `-p 127.0.0.1:9400:9400`
- Use reverse proxy with authentication for external access
- Implement network-level access controls (firewall, VPN)

**Secrets Management:**
- Never embed secrets in container images or docker-compose files
- Use environment variables or Docker secrets for sensitive data
- Rotate Gotify tokens regularly
- Monitor audit logs for unauthorized access attempts

**File Permissions:**
- Ensure mounted directories have correct ownership (UID 1000)
- Use read-only mounts where possible (staging directories, policy files)
- Regularly review file permissions on persistent volumes
- Consider using named volumes instead of bind mounts for better isolation

### Policy Configuration

The container includes a default policy file that can be customized:

**Default Policy Location:** `/app/BurlyMCP/config/policy/tools.yaml`

**Custom Policy Override:**
```bash
# Mount custom policy file
-v ./my-policy.yaml:/app/BurlyMCP/config/policy/tools.yaml:ro
```

**Example Custom Policy:**
```yaml
tools:
  # System monitoring (safe, read-only)
  disk_space:
    description: "Check filesystem usage"
    timeout_sec: 30
    notify: ["failure"]
    mutates: false
    requires_confirm: false

  # Docker operations (requires socket mount)
  docker_ps:
    description: "List Docker containers"
    timeout_sec: 30
    notify: ["failure", "success"]
    mutates: false
    requires_confirm: false

  # Blog publishing (mutating operation)
  blog_publish_static:
    description: "Publish blog content"
    timeout_sec: 60
    notify: ["success", "failure"]
    mutates: true
    requires_confirm: true
    args_schema:
      type: "object"
      properties:
        source_file: {"type": "string"}
        target_path: {"type": "string"}
      required: ["source_file"]

  # Notifications (optional feature)
  gotify_ping:
    description: "Send test notification"
    timeout_sec: 10
    notify: ["failure"]
    mutates: false
    requires_confirm: false
```

**Policy Validation:**
- Policy files are validated at container startup
- Invalid policies prevent container from starting
- Check container logs for policy validation errors
- Use `docker logs <container>` to debug policy issues

## Development

### Local Development Setup

```bash
# Install Python dependencies
pip install -e ".[dev]"

# Run tests
pytest

# Run with coverage
pytest --cov=burly_mcp

# Format code
black src/ tests/
isort src/ tests/

# Type checking
mypy src/
```

### Core Dependencies

The Burly MCP server requires these Python packages:

**Runtime Dependencies:**
- `pydantic>=2.5.0` - Data validation and settings management
- `pyyaml>=6.0.1` - YAML parsing for policy configuration
- `jsonschema>=4.20.0` - JSON Schema validation for tool arguments
- `requests>=2.31.0` - HTTP client for Gotify notifications
- `docker>=7.0.0` - Docker API client for container operations

**Development Dependencies:**
- `pytest>=7.4.0` - Testing framework
- `pytest-cov>=4.1.0` - Test coverage reporting
- `pytest-asyncio>=0.21.0` - Async testing support
- `black>=23.0.0` - Code formatting
- `isort>=5.12.0` - Import sorting
- `flake8>=6.0.0` - Linting
- `mypy>=1.7.0` - Static type checking
- `pre-commit>=3.5.0` - Git hooks for code quality

All dependencies are automatically installed with `pip install -e ".[dev]"`

### Security Validation

Run security checks before committing code:

```bash
# Check for secrets and credentials
gitleaks detect --source . --verbose

# Scan for vulnerabilities
trivy filesystem .

# Check Python dependencies (if using npm for tooling)
npm audit --production-only

# Validate Python syntax and imports
python -c "import burly_mcp.server.main; print('Syntax OK')"
```

These security checks help ensure:
- No secrets are accidentally committed
- Dependencies don't have known vulnerabilities  
- Code follows security best practices
- All imports and syntax are valid

### Adding New Tools

1. Define the tool in `config/policy/tools.yaml`
2. Implement the tool function in `src/burly_mcp/tools/registry.py`
3. Add tests in `tests/unit/test_tools.py`
4. Update documentation

See [docs/config.md](docs/config.md) for detailed configuration options.

## Architecture

```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│   Open WebUI    │    │   Burly MCP      │    │  System Tools   │
│                 │◄──►│     Server       │◄──►│                 │
│  AI Assistant   │    │                  │    │ Docker, Files,  │
│                 │    │  Policy Engine   │    │ Notifications   │
└─────────────────┘    └──────────────────┘    └─────────────────┘
                              │
                              ▼
                       ┌──────────────┐
                       │ Audit Logs   │
                       │ (JSON Lines) │
                       └──────────────┘
```

## Documentation

- [📖 Complete Configuration Guide](docs/config.md)
- [🔒 Security Model and Threat Analysis](docs/security.md)
- [🚀 Deployment and Operations](docs/runbook.md)
- [🤖 Open WebUI Integration](docs/open-webui.md)
- [📚 Understanding MCP Protocol](docs/mcp-explained.md)

## Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Make your changes with tests
4. Run the test suite (`pytest`)
5. Commit your changes (`git commit -m 'Add amazing feature'`)
6. Push to the branch (`git push origin feature/amazing-feature`)
7. Open a Pull Request

### Development Guidelines

- All new tools must include comprehensive tests
- Security implications must be documented
- Follow the existing code style (Black + isort)
- Update documentation for user-facing changes
- Run security validation before submitting PRs:
  ```bash
  # Required security checks
  gitleaks detect --source .
  trivy filesystem .
  python -c "import burly_mcp.server.main; print('Syntax OK')"
  ```

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Graceful Degradation

BurlyMCP is designed to function gracefully when optional features are unavailable:

### Docker Tools Degradation

**When Docker socket is not mounted:**
```json
{
  "ok": false,
  "summary": "Docker unavailable",
  "error": "Docker socket not accessible in this container",
  "data": {
    "suggestion": "Mount /var/run/docker.sock and add docker group to enable Docker operations"
  }
}
```

**To enable Docker tools:**
```bash
# Find your Docker group GID
getent group docker

# Example output: docker:x:<gid>:user1,user2
# Use the numeric GID from the output

docker run -p 9400:9400 \
  --group-add <docker-group-gid> \
  -v /var/run/docker.sock:/var/run/docker.sock:ro \
  ghcr.io/wolfeitz/burlymcp:main
```

### Notification System Degradation

**When Gotify is not configured:**
- Notification tools return success but log "not configured"
- No errors or service interruption
- Operations continue normally without notifications

**To enable notifications:**
```bash
docker run -p 9400:9400 \
  -e GOTIFY_URL=https://<your-gotify-server> \
  -e GOTIFY_TOKEN=<your-app-token> \
  ghcr.io/wolfeitz/burlymcp:main
```

### Blog Tools Degradation

**When blog directories are not mounted:**
- Blog tools return structured errors with helpful suggestions
- No filesystem operations attempted
- Service remains stable and responsive

**To enable blog tools:**
```bash
docker run -p 9400:9400 \
  -v <your-content-dir>:/app/data/blog/stage:ro \
  -v <your-publish-dir>:/app/data/blog/publish:rw \
  ghcr.io/wolfeitz/burlymcp:main
```

## Troubleshooting

### Container Startup Issues

**Container fails to start:**
```bash
# Check container logs
docker logs <container-name>

# Common issues:
# 1. Port 9400 already in use
docker run -p 9401:9400 ghcr.io/wolfeitz/burlymcp:main

# 2. Permission issues with mounted volumes
sudo chown -R 1000:1000 <your-mount-directory>

# 3. Invalid policy file
docker run --rm ghcr.io/wolfeitz/burlymcp:main python -c "
import yaml
with open('/app/BurlyMCP/config/policy/tools.yaml') as f:
    print('Policy valid:', yaml.safe_load(f))
"
```

**Health check fails:**
```bash
# Test health endpoint directly
curl -v http://localhost:9400/health

# Expected response:
# HTTP/1.1 200 OK
# {"status":"ok","server_name":"burlymcp",...}

# If connection refused:
# 1. Check if container is running: docker ps
# 2. Check port mapping: docker port <container-name>
# 3. Check firewall rules
```

### Docker Socket Access Issues

**Docker tools return "unavailable" errors:**

1. **Verify Docker socket exists:**
   ```bash
   ls -la /var/run/docker.sock
   # Should show: srw-rw---- 1 root docker ... /var/run/docker.sock
   ```

2. **Find Docker group GID:**
   ```bash
   getent group docker
   # Example output: docker:x:<gid>:user1,user2
   # Use the numeric GID from the output in --group-add
   ```

3. **Test Docker access in container:**
   ```bash
   docker run --rm -it \
     --group-add <docker-gid> \
     -v /var/run/docker.sock:/var/run/docker.sock:ro \
     ghcr.io/wolfeitz/burlymcp:main \
     docker ps
   ```

4. **Common Docker socket issues:**
   ```bash
   # Permission denied
   sudo usermod -aG docker $USER
   newgrp docker  # or logout/login

   # Socket not found (Docker not running)
   sudo systemctl start docker
   sudo systemctl enable docker

   # SELinux issues (RHEL/CentOS)
   sudo setsebool -P container_manage_cgroup on
   ```

### Network and Connectivity Issues

**Cannot reach container from host:**
```bash
# Check container is listening
docker exec <container-name> netstat -tlnp | grep 9400

# Check port mapping
docker port <container-name>

# Test from inside container
docker exec <container-name> curl http://localhost:9400/health

# Test with different binding
docker run -p 127.0.0.1:9400:9400 ghcr.io/wolfeitz/burlymcp:main  # localhost only
docker run -p 0.0.0.0:9400:9400 ghcr.io/wolfeitz/burlymcp:main   # all interfaces
```

**Rate limiting issues:**
```bash
# Disable rate limiting for testing
docker run -p 9400:9400 \
  -e RATE_LIMIT_DISABLED=true \
  ghcr.io/wolfeitz/burlymcp:main

# Check rate limit headers
curl -v -X POST http://localhost:9400/mcp \
  -H 'content-type: application/json' \
  -d '{"id":"1","method":"list_tools","params":{}}'
```

### File Permission Issues

**Mounted volumes not accessible:**
```bash
# Check ownership of mounted directories
ls -la <your-mount-directory>

# Fix ownership (container runs as UID 1000)
sudo chown -R 1000:1000 <your-mount-directory>

# Test write access for blog publishing
docker run --rm \
  -v <your-publish-dir>:/app/data/blog/publish:rw \
  ghcr.io/wolfeitz/burlymcp:main \
  touch /app/data/blog/publish/test-write
```

**Audit log permission errors:**
```bash
# Create log directory with correct permissions
mkdir -p ./logs
sudo chown 1000:1000 ./logs
chmod 755 ./logs

# Test log writing
docker run --rm \
  -v ./logs:/var/log/agentops \
  ghcr.io/wolfeitz/burlymcp:main \
  touch /var/log/agentops/test.log
```

### Configuration and Policy Issues

**Invalid policy file:**
```bash
# Validate policy syntax
python3 -c "
import yaml
try:
    with open('your-policy.yaml') as f:
        policy = yaml.safe_load(f)
    print('Policy syntax valid')
    print('Tools defined:', list(policy.get('tools', {}).keys()))
except Exception as e:
    print('Policy error:', e)
"

# Test with minimal policy
cat > minimal-policy.yaml << EOF
tools:
  disk_space:
    description: "Check disk usage"
    timeout_sec: 30
    mutates: false
    requires_confirm: false
EOF

docker run --rm -p 9400:9400 \
  -v ./minimal-policy.yaml:/app/BurlyMCP/config/policy/tools.yaml:ro \
  ghcr.io/wolfeitz/burlymcp:main
```

**Environment variable issues:**
```bash
# Debug environment variables
docker run --rm \
  -e LOG_LEVEL=DEBUG \
  ghcr.io/wolfeitz/burlymcp:main \
  env | grep -E "(GOTIFY|BLOG|DOCKER|LOG)"

# Test configuration loading
docker run --rm \
  -e LOG_LEVEL=DEBUG \
  ghcr.io/wolfeitz/burlymcp:main \
  python3 -c "
from burly_mcp.config import load_runtime_config
config = load_runtime_config()
print('Config loaded successfully')
print('Blog stage root:', config.blog_stage_root)
print('Notifications enabled:', config.notifications_enabled)
"
```

### Performance and Resource Issues

**Container using too much memory:**
```bash
# Monitor resource usage
docker stats <container-name>

# Set memory limits
docker run -p 9400:9400 \
  --memory=512m \
  --memory-swap=512m \
  ghcr.io/wolfeitz/burlymcp:main

# Check for memory leaks in logs
docker logs <container-name> | grep -i "memory\|oom"
```

**Slow response times:**
```bash
# Test response time
time curl http://localhost:9400/health

# Check for blocking operations
docker exec <container-name> ps aux

# Enable debug logging
docker run -p 9400:9400 \
  -e LOG_LEVEL=DEBUG \
  ghcr.io/wolfeitz/burlymcp:main
```

### Integration Issues

**Open WebUI integration problems:**
```bash
# Test MCP endpoint directly
curl -X POST http://localhost:9400/mcp \
  -H 'content-type: application/json' \
  -d '{"id":"test","method":"list_tools","params":{}}' | jq

# Verify response format
# Should return: {"ok": true, "data": {"tools": [...]}, ...}

# Test tool execution
curl -X POST http://localhost:9400/mcp \
  -H 'content-type: application/json' \
  -d '{"id":"test","method":"call_tool","name":"disk_space","args":{}}' | jq
```

**Downstream system compatibility:**
```bash
# Test both request formats
# Format 1: Direct args
curl -X POST http://localhost:9400/mcp \
  -H 'content-type: application/json' \
  -d '{"id":"1","method":"call_tool","name":"disk_space","args":{}}'

# Format 2: Params wrapper
curl -X POST http://localhost:9400/mcp \
  -H 'content-type: application/json' \
  -d '{"id":"1","method":"call_tool","params":{"name":"disk_space","args":{}}}'

# Both should return equivalent responses
```

### Getting Help

**Collect diagnostic information:**
```bash
#!/bin/bash
# diagnostic-info.sh - Collect system information for support

echo "=== System Information ==="
uname -a
docker --version
echo

echo "=== Container Status ==="
docker ps -a | grep burlymcp
echo

echo "=== Container Logs (last 50 lines) ==="
docker logs --tail 50 <container-name>
echo

echo "=== Health Check ==="
curl -s http://localhost:9400/health | jq 2>/dev/null || curl -s http://localhost:9400/health
echo

echo "=== Network Configuration ==="
docker port <container-name>
netstat -tlnp | grep 9400
echo

echo "=== File Permissions ==="
ls -la /var/run/docker.sock 2>/dev/null || echo "Docker socket not found"
getent group docker 2>/dev/null || echo "Docker group not found"
echo

echo "=== Environment ==="
docker exec <container-name> env | grep -E "(GOTIFY|BLOG|DOCKER|LOG|RATE)" | sort
```

**Common solutions summary:**
- **Port conflicts**: Use `-p 9401:9400` or different port
- **Permission issues**: Ensure UID 1000 owns mounted directories
- **Docker access**: Use `--group-add $(getent group docker | cut -d: -f3)`
- **Network issues**: Check firewall rules and port bindings
- **Configuration errors**: Validate YAML syntax and environment variables
- **Performance issues**: Set resource limits and check for blocking operations

## Support and Community

- 🐛 **Issues**: [GitHub Issues](https://github.com/<your-org>/burly-mcp/issues)
- 💬 **Discussions**: [GitHub Discussions](https://github.com/<your-org>/burly-mcp/discussions)
- 📧 **Security**: Report security issues privately to security@<your-domain>

## Acknowledgments

- Built on the [Model Context Protocol](https://modelcontextprotocol.io/) specification
- Inspired by the need for secure AI-system integration
- Thanks to the open source community for tools and libraries

---

**⚡ Ready to give your AI assistant superpowers? Get started with Burly MCP today!**