# BurlyMCP Docker Compose Examples

**REFERENCE ONLY.** The authoritative interface is the container (port 9400, /health, /mcp).

These docker-compose files are provided as reference deployments. Production stacks should manage their own compose / k8s / swarm / etc.

**Security note:** mounting `/var/run/docker.sock` effectively gives BurlyMCP root-equivalent power on the host. Do not expose that mode on untrusted networks.

## Available Examples

### 1. Minimal Example (`docker-compose.minimal.yml`)
Basic container deployment with no privileges or external dependencies.
- No Docker socket access
- No persistent volumes
- HTTP endpoints only

```bash
docker compose -f docker-compose.minimal.yml up -d
```

### 2. Standard Example (`docker-compose.yml`)
Recommended configuration with optional features commented out.
- Optional blog directories
- Optional audit log persistence
- Optional Docker socket access (commented)
- Optional notifications (commented)

```bash
docker compose up -d
```

### 3. Privileged Example (`docker-compose.privileged.yml`)
Full-featured deployment with Docker socket access enabled.
- Docker socket mounted (requires host docker group GID)
- Blog directories mounted
- Audit logs persisted
- All optional features enabled

```bash
# Find your docker group GID
DOCKER_GID=$(getent group docker | cut -d: -f3)
echo "Docker group GID: $DOCKER_GID"

# Edit docker-compose.privileged.yml and replace <host_docker_group_gid> with the actual GID
# Then run:
docker compose -f docker-compose.privileged.yml up -d
```

### 4. Development Override (`docker-compose.override.yml`)
Development-friendly overrides for the standard example.
- Debug logging enabled
- Source code mounting (if building locally)
- Relaxed security constraints

```bash
# Uses docker-compose.yml + docker-compose.override.yml automatically
docker compose up -d
```

## Environment Variables

All examples support these optional environment variables:

- `BLOG_STAGE_ROOT` - Blog staging directory (default: `/app/data/blog/stage`)
- `BLOG_PUBLISH_ROOT` - Blog publish directory (default: `/app/data/blog/publish`)
- `GOTIFY_URL` - Gotify server URL for notifications
- `GOTIFY_TOKEN` - Gotify authentication token
- `LOG_LEVEL` - Logging level (default: `INFO`)
- `MAX_OUTPUT_SIZE` - Maximum tool output size (default: `1048576`)
- `AUDIT_ENABLED` - Enable audit logging (default: `true`)

## Docker Socket Access

To enable Docker operations (docker_ps, etc.), you need to:

1. Mount the Docker socket: `-v /var/run/docker.sock:/var/run/docker.sock:ro`
2. Add the container to the host's docker group: `--group-add <docker_gid>`

Find your docker group GID:
```bash
getent group docker
# Example output: docker:x:999:user
# Use GID 999 in this case
```

## Minimal Command Line Alternative

Instead of docker-compose, you can run the container directly:

```bash
# Minimal (no privileges)
docker run --rm -p 9400:9400 ghcr.io/<org>/burlymcp:main

# With Docker socket access
DOCKER_GID=$(getent group docker | cut -d: -f3)
docker run --rm -p 9400:9400 \
  --group-add $DOCKER_GID \
  -v /var/run/docker.sock:/var/run/docker.sock:ro \
  ghcr.io/<org>/burlymcp:main
```

## Testing the Deployment

After starting any example:

```bash
# Check health
curl http://localhost:9400/health

# List available tools
curl -X POST http://localhost:9400/mcp \
  -H 'content-type: application/json' \
  -d '{"id":"1","method":"list_tools","params":{}}'

# Test a basic tool
curl -X POST http://localhost:9400/mcp \
  -H 'content-type: application/json' \
  -d '{"id":"2","method":"call_tool","name":"disk_space","args":{}}'
```

## Official Contract

The only official contract BurlyMCP guarantees is:
- Published container image at `ghcr.io/<org>/burlymcp:main`
- Port 9400
- `GET /health` endpoint
- `POST /mcp` endpoint (HTTP-style MCP)

These compose files are examples only and may change without notice.