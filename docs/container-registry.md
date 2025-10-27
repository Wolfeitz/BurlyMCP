# Container Registry Configuration

## Overview

BurlyMCP publishes official container images to GitHub Container Registry (GHCR) automatically on every push to the main branch. This document describes the registry configuration, permissions, and tagging strategy.

## Registry Details

- **Registry**: `ghcr.io`
- **Repository**: `ghcr.io/wolfeitz/burlymcp`
- **Platforms**: `linux/amd64`, `linux/arm64`
- **Base Image**: `debian:trixie-slim`

## Tagging Strategy

The automated publishing workflow creates the following tags:

### Production Tags
- `latest` - Always points to the latest successful build (watchtower compatible)
- `main` - Rolling tag that always points to the latest main branch build
- `1.0.YYYYMMDD-HHMMSS` - Semantic version with timestamp for precise tracking

### Development Tags
- `<branch>-<shortsha>` - Forensic snapshot for traceability (e.g., `main-a1b2c3d`)

### Tag Examples
```bash
# Latest stable (watchtower will auto-update to this)
ghcr.io/wolfeitz/burlymcp:latest

# Latest from main branch
ghcr.io/wolfeitz/burlymcp:main

# Specific timestamped version
ghcr.io/wolfeitz/burlymcp:1.0.20241025-143022

# Specific commit snapshot
ghcr.io/wolfeitz/burlymcp:main-a1b2c3d
```

## Permissions Configuration

### GitHub Token Permissions

The workflow uses the built-in `GITHUB_TOKEN` with the following permissions:

```yaml
permissions:
  contents: read      # Read repository contents
  packages: write     # Write to GitHub Container Registry
```

### Repository Settings

To ensure proper publishing, verify these repository settings:

1. **Actions Permissions**: 
   - Go to Settings → Actions → General
   - Ensure "Read and write permissions" is enabled for GITHUB_TOKEN

2. **Package Permissions**:
   - Go to Settings → Actions → General
   - Under "Workflow permissions", ensure "Read and write permissions" is selected

## CI Integration

### Test Requirements
The container publishing workflow only runs after the CI Pipeline completes successfully:

- **Unit tests** must pass (coverage threshold: 23%)
- **Integration tests** must pass
- **Security scans** must complete without critical issues
- **Code quality** checks must pass

If any CI job fails, container publishing is automatically blocked.

### Manual Override
You can manually trigger publishing (bypassing CI) using:
```bash
# Via GitHub UI: Actions → Publish Container Image → Run workflow
# Or via GitHub CLI:
gh workflow run publish-image.yml
```

## Image Validation

Each published image undergoes automatic validation:

### Functional Tests
- Container starts successfully within 30 seconds
- Health endpoint (`/health`) responds with valid JSON
- MCP endpoint (`/mcp`) accepts list_tools requests
- Multi-platform builds work correctly

### Security Scanning
- Trivy vulnerability scanning for CRITICAL and HIGH severity issues
- SARIF results uploaded to GitHub Security tab
- Build fails if critical vulnerabilities are found

## Usage Examples

### Pull and Run
```bash
# Pull latest stable image (recommended for production)
docker pull ghcr.io/wolfeitz/burlymcp:latest

# Run with minimal privileges (no Docker socket)
docker run --rm -p 9400:9400 ghcr.io/wolfeitz/burlymcp:latest

# Test endpoints
curl http://127.0.0.1:9400/health
curl -X POST http://127.0.0.1:9400/mcp \
  -H 'Content-Type: application/json' \
  -d '{"id":"1","method":"list_tools","params":{}}'
```

### Watchtower Integration
```bash
# Watchtower will automatically update containers using :latest tag
docker run -d --name watchtower \
  -v /var/run/docker.sock:/var/run/docker.sock \
  containrrr/watchtower \
  --interval 300 \
  --cleanup

# Your BurlyMCP container (watchtower will auto-update this)
docker run -d --name burlymcp \
  -p 9400:9400 \
  --label com.centurylinklabs.watchtower.enable=true \
  ghcr.io/wolfeitz/burlymcp:latest
```

### With Docker Socket (Optional)
```bash
# Get your docker group GID
DOCKER_GID=$(getent group docker | cut -d: -f3)

# Run with Docker socket access
docker run --rm -p 9400:9400 \
  --group-add $DOCKER_GID \
  -v /var/run/docker.sock:/var/run/docker.sock:ro \
  ghcr.io/wolfeitz/burlymcp:main
```

## Container Contract

The published container guarantees:

- **Zero-config startup**: Works with just `docker run -p 9400:9400`
- **HTTP endpoints**: `/health` (GET) and `/mcp` (POST) on port 9400
- **Non-root execution**: Runs as `mcp` user (UID 1000)
- **Graceful degradation**: Optional features fail safely when not configured
- **Security**: Minimal privileges, no Docker daemon included

## Troubleshooting

### Publishing Failures

If the workflow fails to publish:

1. **Check permissions**: Ensure GITHUB_TOKEN has `packages:write` permission
2. **Verify Dockerfile**: Ensure `Dockerfile.runtime` builds successfully locally
3. **Review logs**: Check the GitHub Actions workflow logs for specific errors

### Image Pull Issues

If you cannot pull published images:

1. **Check visibility**: Ensure the package is public in GitHub Packages
2. **Verify tag**: Confirm the tag exists using `docker manifest inspect`
3. **Authentication**: For private repos, authenticate with GitHub Container Registry

### Authentication for Private Repositories

```bash
# Login to GHCR (if repository is private)
echo $GITHUB_TOKEN | docker login ghcr.io -u USERNAME --password-stdin

# Pull private image
docker pull ghcr.io/wolfeitz/burlymcp:main
```

## Monitoring

### Automated Checks

The publishing workflow includes:
- Build success/failure notifications
- Security scan results in GitHub Security tab
- Image validation test results
- Multi-platform build verification

### Manual Verification

To manually verify a published image:

```bash
# Check image exists and get metadata
docker manifest inspect ghcr.io/wolfeitz/burlymcp:main

# Test basic functionality
docker run --rm ghcr.io/wolfeitz/burlymcp:main python3 --version

# Test HTTP endpoints
docker run -d --name test-burlymcp -p 9400:9400 ghcr.io/wolfeitz/burlymcp:main
sleep 5
curl http://localhost:9400/health
docker stop test-burlymcp && docker rm test-burlymcp
```

## Security Considerations

### Image Security
- Base image is regularly updated (`debian:trixie-slim`)
- Vulnerability scanning blocks releases with critical issues
- Non-root execution prevents privilege escalation
- Minimal attack surface with only required dependencies

### Registry Security
- Images are signed with provenance and SBOM
- Security scan results are publicly available
- Automated security updates for base image vulnerabilities

### Runtime Security
- Container runs as non-root user (`mcp:1000`)
- Optional Docker socket access requires explicit configuration
- No secrets or sensitive data embedded in image
- Environment variables can override all configuration