# Design Document

## Overview

This design transforms BurlyMCP from a docker-compose orchestrated application into a standalone service container that exposes HTTP endpoints. The transformation creates a self-contained Docker image with an HTTP bridge that provides `/health` and `/mcp` endpoints, making it consumable by downstream infrastructure systems without requiring docker-compose orchestration.

BurlyMCP is an open, public project. The Runtime Container MUST run on arbitrary Linux hosts, not just our internal environment. All host-specific values (paths, notification endpoints, group IDs, etc.) MUST be configurable at runtime via environment variables or optional mounts. Defaults MUST be safe and functional without elevated privileges or external services.

The design maintains all existing MCP functionality while adding HTTP accessibility, implements graceful degradation for optional features, and ensures the container can run on any Linux host with configurable defaults.

## Architecture

```mermaid
graph TB
    subgraph "Standalone Container (Port 9400)"
        A[HTTP Bridge<br/>FastAPI + uvicorn] --> B[MCP Engine<br/>burly_mcp.server.main]
        A --> C[Health Check Handler]
        
        B --> D[Tool Registry]
        B --> E[Policy Engine]
        B --> F[Audit Logger]
        B --> G[Notification Manager]
        
        D --> H[Docker Tools]
        D --> I[Blog Tools]
        D --> J[System Tools]
        
        K[Default Policy<br/>Embedded in Image] --> E
        L[Default Config<br/>Environment Variables] --> B
    end
    
    subgraph "External Systems (Optional)"
        M[Docker Socket<br/>/var/run/docker.sock] -.-> H
        N[Gotify Server] -.-> G
        O[Blog Directories<br/>Mounted Volumes] -.-> I
        P[Audit Log Volume] -.-> F
    end
    
    subgraph "Downstream Consumers"
        Q[Open WebUI] --> A
        R[System Tools Stack] --> A
        S[Monitoring Systems] --> C
    end
    
    style A fill:#e1f5fe
    style B fill:#f3e5f5
    style K fill:#e8f5e8
    style L fill:#e8f5e8

Note: MCP Engine may initially run as a subprocess (python -m ...) but MAY later become an in-process import. The HTTP Bridge API MUST NOT change when that refactor happens.
```

## Components and Interfaces

### HTTP Bridge (http_bridge.py)

**Purpose**: FastAPI application that provides HTTP endpoints and bridges to the MCP engine

**Interface**: 
- `GET /health` → Health check endpoint
- `POST /mcp` → MCP request/response endpoint

**Implementation**:
```python
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import subprocess
import json
import asyncio
from typing import Dict, Any, Optional

class MCPRequest(BaseModel):
    id: str
    method: str
    name: Optional[str] = None
    args: Optional[Dict[str, Any]] = None
    params: Optional[Dict[str, Any]] = None

class HealthResponse(BaseModel):
    status: str
    version: str
    tools_available: int
    notifications_enabled: bool
    docker_available: bool

app = FastAPI(title="BurlyMCP HTTP Bridge", version="1.0.0")

@app.get("/health", response_model=HealthResponse)
async def health_check():
    # Implementation details below

@app.post("/mcp")
async def mcp_endpoint(request: MCPRequest):
    # Implementation details below
```

**Responsibilities**:
- Accept HTTP requests and convert to MCP JSON format
- Communicate with MCP engine via subprocess or in-process calls
- Handle both request formats: direct args and params wrapper
- Provide structured error responses for failed operations
- Maintain API stability across internal refactors
- `/mcp` MUST always return HTTP 200 with a JSON body of shape:
  ```json
  {
    "ok": <bool>,
    "summary": <string>,
    "error": <string|optional>,
    "data": <object|optional>,
    "metrics": { "elapsed_ms": <int>, "exit_code": <int> }
  }
  ```
  Validation errors, unavailable features, and security denials MUST be expressed in that envelope instead of using non-200 HTTP codes.

### Canonical Runtime Dockerfile (Dockerfile.runtime)

**Purpose**: Single source of truth for the deployable container image

**Base Image**: `debian:trixie-slim` for security and minimal size

**Structure**:
```dockerfile
FROM debian:trixie-slim

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    python3 \
    python3-venv \
    python3-pip \
    docker.io \
    curl \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Create virtual environment
RUN python3 -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Copy and install BurlyMCP
COPY . /app/BurlyMCP/
WORKDIR /app/BurlyMCP
RUN pip install -e .

# Install HTTP bridge dependencies
COPY http_bridge.py /app/
RUN pip install fastapi uvicorn==0.30.6

# Create runtime user
RUN useradd -u 1000 -m mcp

# Set up directories and permissions
RUN mkdir -p /var/log/agentops /app/data/blog/stage /app/data/blog/publish && \
    chown -R mcp:mcp /app /var/log/agentops

# Environment configuration
ENV PORT=9400
EXPOSE 9400

USER mcp
CMD ["uvicorn", "http_bridge:app", "--host", "0.0.0.0", "--port", "9400"]
```

The Runtime Container MUST:
- Include a default policy file (e.g. config/policy/tools.yaml) baked into the image
- Create /var/log/agentops and /app/data/... paths at build time
- Successfully start uvicorn http_bridge:app without any bind mounts, extra env vars, or access to /var/run/docker.sock

Security requirement: The Runtime Container MUST NOT run or include a Docker daemon. If Docker inspection tooling is provided, it MUST operate using the host's mounted /var/run/docker.sock and (optionally) a Docker CLI binary or client library. It MUST fail gracefully if neither is available.

**Key Features**:
- Self-contained with all dependencies
- Non-root execution (mcp user, UID 1000)
- Embedded default policy and configuration
- No external file dependencies
- Configurable via environment variables

### Configuration Management

**Default Configuration Embedded in Container**:
```python
# Default paths (container-internal)
DEFAULT_CONFIG = {
    "policy_file": "/app/BurlyMCP/config/policy/tools.yaml",
    "audit_log_path": "/var/log/agentops/audit.jsonl",
    "blog_stage_root": "/app/data/blog/stage",
    "blog_publish_root": "/app/data/blog/publish",
    "log_dir": "/var/log/agentops",
    "docker_socket": "/var/run/docker.sock",
    "docker_timeout": 30,
    "max_output_size": 1048576,
    "audit_enabled": True,
    "notifications_enabled": False,  # Safe default
    "gotify_url": "",
    "gotify_token": "",
    "server_name": "burlymcp",
    "server_version": "0.1.0",
    "strict_security_mode": True,
}

# Environment variable overrides
def load_runtime_config():
    config = DEFAULT_CONFIG.copy()
    
    # Allow override of any setting via environment
    for key, default_value in config.items():
        env_key = key.upper()
        env_value = os.environ.get(env_key)
        
        if env_value is not None:
            # Type conversion based on default value type
            if isinstance(default_value, bool):
                config[key] = env_value.lower() in ['true', '1', 'yes']
            elif isinstance(default_value, int):
                config[key] = int(env_value)
            else:
                config[key] = env_value
    
    return config
```

**Environment Variables for Runtime Configuration**:
- `POLICY_FILE` - Override default policy file location
- `AUDIT_LOG_PATH` - Override audit log location
- `BLOG_STAGE_ROOT` - Override blog staging directory
- `BLOG_PUBLISH_ROOT` - Override blog publish directory
- `DOCKER_SOCKET` - Override Docker socket path
- `GOTIFY_URL` - Gotify server URL (optional)
- `GOTIFY_TOKEN` - Gotify authentication token (optional)
- `LOG_LEVEL` - Logging level (DEBUG, INFO, WARNING, ERROR)

### Graceful Degradation System

**Docker Operations**:
```python
def check_docker_availability():
    """Check if Docker socket is accessible"""
    try:
        import docker
        client = docker.from_env()
        client.ping()
        return True
    except Exception:
        return False

def execute_docker_tool(tool_name, args):
    """Execute Docker tool with graceful degradation"""
    if not check_docker_availability():
        return {
            "ok": False,
            "summary": "Docker unavailable",
            "error": "Docker socket not accessible in this container",
            "data": {
                "suggestion": "Mount /var/run/docker.sock to enable Docker operations"
            }
        }
    
    # Normal Docker tool execution
    return execute_normal_docker_tool(tool_name, args)
```

**Notification System**:
```python
def send_notification(message, priority=3):
    """Send notification with graceful degradation"""
    if not config.get("gotify_url") or not config.get("gotify_token"):
        logger.debug(f"Notification not sent (not configured): {message}")
        return {"sent": False, "reason": "not_configured"}
    
    try:
        # Attempt to send notification
        response = send_gotify_notification(message, priority)
        return {"sent": True, "response": response}
    except Exception as e:
        logger.warning(f"Notification failed: {e}")
        return {"sent": False, "reason": str(e)}

def validate_mutating_operation(args: Dict[str, Any]) -> bool:
    """Validate mutating operations require explicit confirmation"""
    return args.get("_confirm", False) is True

def require_confirmation_response(tool_name: str) -> Dict[str, Any]:
    """Generate confirmation required response for mutating operations"""
    return {
        "ok": False,
        "need_confirm": True,
        "summary": f"{tool_name} requires confirmation",
        "error": "Confirmation required for mutating operation",
        "data": {
            "required_arg": "_confirm",
            "required_value": True,
            "suggestion": f"Add '_confirm': true to {tool_name} arguments"
        },
        "metrics": {"elapsed_ms": 0, "exit_code": 1}
    }
```

**Security Rule for Mutating Operations**:
Tools that represent mutating operations (e.g. blog_publish_static) MUST require explicit _confirm: true, and MUST return a structured "confirmation required" response (need_confirm: true) if _confirm is missing — not perform the mutation by default.
```

### HTTP Bridge Implementation Details

**Health Check Endpoint**:
```python
@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Comprehensive health check with system status"""
    
    # Check MCP engine availability
    try:
        # Quick test of MCP engine
        test_result = await test_mcp_engine()
        mcp_healthy = test_result.get("ok", False)
    except Exception:
        mcp_healthy = False
    
    # Check optional features
    docker_available = check_docker_availability()
    notifications_enabled = bool(config.get("gotify_url"))
    
    # Count available tools
    tools_count = len(get_available_tools())
    
    return HealthResponse(
        status="ok" if mcp_healthy else "degraded",
        version=get_version(),
        tools_available=tools_count,
        notifications_enabled=notifications_enabled,
        docker_available=docker_available
    )
```

**MCP Endpoint with Format Normalization**:
```python
@app.post("/mcp")
async def mcp_endpoint(request: MCPRequest):
    """Handle MCP requests with format normalization"""
    
    try:
        # Normalize request format
        normalized_request = normalize_mcp_request(request)
        
        # Forward to MCP engine
        mcp_response = await forward_to_mcp_engine(normalized_request)
        
        # Ensure response has required fields
        return ensure_response_format(mcp_response)
        
    except Exception as e:
        logger.error(f"MCP request failed: {e}")
        return {
            "ok": False,
            "summary": "Request processing failed",
            "error": str(e),
            "metrics": {"elapsed_ms": 0, "exit_code": 1}
        }

def normalize_mcp_request(request: MCPRequest) -> Dict[str, Any]:
    """Normalize different request formats to standard MCP format"""
    
    # Handle direct format: {"method": "call_tool", "name": "disk_space", "args": {}}
    if request.name is not None:
        return {
            "id": request.id,
            "method": request.method,
            "name": request.name,
            "args": request.args or {}
        }
    
    # Handle params format: {"method": "call_tool", "params": {"name": "disk_space", "args": {}}}
    if request.params is not None:
        return {
            "id": request.id,
            "method": request.method,
            "name": request.params.get("name"),
            "args": request.params.get("args", {})
        }
    
    # Handle list_tools format: {"method": "list_tools", "params": {}}
    return {
        "id": request.id,
        "method": request.method,
        "params": request.params or {}
    }
```

### Container Publishing Pipeline

**GitHub Actions Workflow** (`.github/workflows/publish-image.yml`):
```yaml
name: Publish Container Image

on:
  push:
    branches: [main]

jobs:
  publish:
    runs-on: ubuntu-latest
    permissions:
      contents: read
      packages: write
    
    steps:
      - name: Checkout
        uses: actions/checkout@v4
      
      - name: Set up Docker Buildx
        uses: docker/setup-buildx-action@v3
      
      - name: Login to GitHub Container Registry
        uses: docker/login-action@v3
        with:
          registry: ghcr.io
          username: ${{ github.actor }}
          password: ${{ secrets.GITHUB_TOKEN }}
      
      - name: Extract metadata
        id: meta
        uses: docker/metadata-action@v5
        with:
          images: ghcr.io/${{ github.repository_owner }}/burlymcp
          tags: |
            type=ref,event=branch
            type=sha,prefix={{branch}}-
            type=raw,value=main,enable={{is_default_branch}}
      
      - name: Build and push
        uses: docker/build-push-action@v5
        with:
          context: .
          file: ./Dockerfile.runtime  # MUST remain the canonical build target
          push: true
          tags: ${{ steps.meta.outputs.tags }}
          labels: ${{ steps.meta.outputs.labels }}
          cache-from: type=gha
          cache-to: type=gha,mode=max
```

The workflow MUST publish at least two tags:
- `main` for "latest stable on default branch"
- `<branch>-<shortsha>` for traceability in debugging
```

### Example Compose Migration

**Current Location**: Root `docker-compose.yml` (authoritative)
**New Location**: `examples/compose/docker-compose.yml` (reference only)

**Example Compose with Generic Configuration**:
```yaml
# EXAMPLE ONLY
# This docker-compose.yml is provided as a reference deployment.
# Production stacks should manage their own compose / k8s / swarm / etc.
# The only official contract BurlyMCP guarantees is:
#   - Published container image
#   - Port 9400
#   - /health  (GET)
#   - /mcp     (POST, Streamable HTTP-style MCP)
#
# Optional extras like mounting /var/run/docker.sock,
# or binding log directories, are operator decisions.

services:
  burlymcp:
    image: ghcr.io/<org>/burlymcp:main
    container_name: burlymcp-example
    
    ports:
      - "9400:9400"
    
    environment:
      # Optional: Configure blog directories
      - BLOG_STAGE_ROOT=/app/data/blog/stage
      - BLOG_PUBLISH_ROOT=/app/data/blog/publish
      
      # Optional: Enable notifications
      # - GOTIFY_URL=https://your-gotify-server.com
      # - GOTIFY_TOKEN=your-token-here
      
      # Optional: Adjust logging
      - LOG_LEVEL=INFO
    
    volumes:
      # Optional: Persist audit logs
      - ./logs:/var/log/agentops
      
      # Optional: Blog content directories
      - ./blog/stage:/app/data/blog/stage:ro
      - ./blog/publish:/app/data/blog/publish:rw
    
    # OPTIONAL: to allow container to inspect host Docker,
    # replace <host_docker_group_gid> with the numeric GID of your `docker` group:
    #   getent group docker
    # group_add:
    #   - "<host_docker_group_gid>"
    # volumes:
    #   - /var/run/docker.sock:/var/run/docker.sock:ro
    
    restart: unless-stopped
    
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:9400/health"]
      interval: 30s
      timeout: 10s
      retries: 3

# Minimal/no-privilege run:
# docker run --rm -p 9400:9400 ghcr.io/<org>/burlymcp:main
# curl http://127.0.0.1:9400/health
# 
# That MUST return status "ok" or "degraded", not crash.
```

## Data Models

### HTTP Request/Response Models

```python
from pydantic import BaseModel
from typing import Dict, Any, Optional, Union

class MCPRequest(BaseModel):
    """Unified MCP request model supporting multiple formats"""
    id: str
    method: str
    name: Optional[str] = None
    args: Optional[Dict[str, Any]] = None
    params: Optional[Dict[str, Any]] = None

class MCPResponse(BaseModel):
    """Standardized MCP response envelope"""
    ok: bool
    summary: str
    need_confirm: Optional[bool] = None
    data: Optional[Dict[str, Any]] = None
    stdout: Optional[str] = None
    stderr: Optional[str] = None
    error: Optional[str] = None
    metrics: Optional[Dict[str, Any]] = None

class HealthResponse(BaseModel):
    """Health check response with system status"""
    status: str  # "ok", "degraded", "error"
    server_name: str
    version: str
    tools_available: int
    notifications_enabled: bool
    docker_available: bool
    strict_security_mode: bool
    policy_loaded: bool
    uptime_seconds: Optional[int] = None
```

### Configuration Model

```python
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

@dataclass
class RuntimeConfig:
    """Runtime configuration with defaults and validation"""
    
    # Core paths (container-internal defaults)
    policy_file: Path = Path("/app/BurlyMCP/config/policy/tools.yaml")
    audit_log_path: Path = Path("/var/log/agentops/audit.jsonl")
    log_dir: Path = Path("/var/log/agentops")
    
    # Blog configuration
    blog_stage_root: Path = Path("/app/data/blog/stage")
    blog_publish_root: Path = Path("/app/data/blog/publish")
    
    # Docker configuration
    docker_socket: Path = Path("/var/run/docker.sock")
    docker_timeout: int = 30
    
    # Security settings
    max_output_size: int = 1048576  # 1MB
    audit_enabled: bool = True
    
    # Notification settings
    notifications_enabled: bool = False
    gotify_url: Optional[str] = None
    gotify_token: Optional[str] = None
    
    # Server settings
    port: int = 9400
    host: str = "0.0.0.0"
    log_level: str = "INFO"
    server_name: str = "burlymcp"
    server_version: str = "0.1.0"
    strict_security_mode: bool = True
    
    def validate(self) -> list[str]:
        """Validate configuration and return errors"""
        errors = []
        
        # Check required files exist
        if not self.policy_file.exists():
            errors.append(f"Policy file not found: {self.policy_file}")
        
        # Check directory permissions
        for dir_path in [self.log_dir, self.blog_stage_root.parent]:
            if not dir_path.exists():
                try:
                    dir_path.mkdir(parents=True, exist_ok=True)
                except OSError as e:
                    errors.append(f"Cannot create directory {dir_path}: {e}")
        
        # Validate notification config
        if self.notifications_enabled:
            if not self.gotify_url:
                errors.append("GOTIFY_URL required when notifications enabled")
            if not self.gotify_token:
                errors.append("GOTIFY_TOKEN required when notifications enabled")
        
        return errors
```

## Error Handling

### HTTP Bridge Error Handling

**Request Validation Errors**:
```python
@app.exception_handler(ValidationError)
async def validation_exception_handler(request: Request, exc: ValidationError):
    return JSONResponse(
        status_code=400,
        content={
            "ok": False,
            "summary": "Invalid request format",
            "error": "Request validation failed",
            "details": exc.errors(),
            "metrics": {"elapsed_ms": 0, "exit_code": 1}
        }
    )
```

**MCP Engine Communication Errors**:
```python
async def forward_to_mcp_engine(request: Dict[str, Any]) -> Dict[str, Any]:
    """Forward request to MCP engine with error handling"""
    try:
        # Attempt subprocess communication
        process = await asyncio.create_subprocess_exec(
            "python", "-m", "burly_mcp.server.main",
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        
        # Send request
        request_json = json.dumps(request) + "\n"
        stdout, stderr = await process.communicate(request_json.encode())
        
        if process.returncode != 0:
            raise RuntimeError(f"MCP engine failed: {stderr.decode()}")
        
        # Parse response
        response = json.loads(stdout.decode())
        return response
        
    except json.JSONDecodeError as e:
        return {
            "ok": False,
            "summary": "Response parsing failed",
            "error": f"Invalid JSON from MCP engine: {e}",
            "metrics": {"elapsed_ms": 0, "exit_code": 1}
        }
    except Exception as e:
        return {
            "ok": False,
            "summary": "MCP engine communication failed",
            "error": str(e),
            "metrics": {"elapsed_ms": 0, "exit_code": 1}
        }
```

### Graceful Degradation Patterns

**Feature Availability Checks**:
```python
class FeatureChecker:
    """Check availability of optional features"""
    
    @staticmethod
    def docker_available() -> bool:
        """Check if Docker operations are available"""
        try:
            docker_socket = Path("/var/run/docker.sock")
            return docker_socket.exists() and docker_socket.is_socket()
        except Exception:
            return False
    
    @staticmethod
    def notifications_configured() -> bool:
        """Check if notifications are properly configured"""
        return bool(config.gotify_url and config.gotify_token)
    
    @staticmethod
    def blog_directories_accessible() -> bool:
        """Check if blog directories are accessible"""
        try:
            return (
                config.blog_stage_root.exists() and
                config.blog_publish_root.exists() and
                os.access(config.blog_publish_root, os.W_OK)
            )
        except Exception:
            return False

def get_degraded_tool_response(tool_name: str, reason: str) -> Dict[str, Any]:
    """Generate consistent degraded response for unavailable tools"""
    return {
        "ok": False,
        "summary": f"{tool_name} unavailable",
        "error": f"Feature not available: {reason}",
        "data": {
            "tool": tool_name,
            "reason": reason,
            "suggestion": get_feature_suggestion(tool_name)
        },
        "metrics": {"elapsed_ms": 0, "exit_code": 1}
    }

def get_feature_suggestion(tool_name: str) -> str:
    """Provide helpful suggestions for enabling features"""
    suggestions = {
        "docker_ps": "Mount /var/run/docker.sock and add docker group to enable Docker operations",
        "blog_publish_static": "Mount blog directories with proper permissions",
        "gotify_ping": "Set GOTIFY_URL and GOTIFY_TOKEN environment variables"
    }
    return suggestions.get(tool_name, "Check container configuration and mounts")
```

## Testing Strategy

### Container Testing

**Black Box HTTP Testing**:
```python
import pytest
import requests
import docker
from testcontainers.compose import DockerCompose

@pytest.fixture(scope="session")
def burlymcp_container():
    """Start BurlyMCP container for testing"""
    with DockerCompose(".", compose_file_name="docker-compose.test.yml") as compose:
        # Wait for container to be ready
        host = compose.get_service_host("burlymcp", 9400)
        port = compose.get_service_port("burlymcp", 9400)
        
        # Wait for health check
        for _ in range(30):
            try:
                response = requests.get(f"http://{host}:{port}/health", timeout=1)
                if response.status_code == 200:
                    break
            except requests.RequestException:
                time.sleep(1)
        else:
            pytest.fail("Container failed to start")
        
        yield f"http://{host}:{port}"

def test_health_endpoint(burlymcp_container):
    """Test health endpoint returns expected format"""
    response = requests.get(f"{burlymcp_container}/health")
    
    assert response.status_code == 200
    data = response.json()
    
    assert "status" in data
    assert "version" in data
    assert "tools_available" in data
    assert isinstance(data["tools_available"], int)

def test_mcp_list_tools(burlymcp_container):
    """Test MCP list_tools endpoint"""
    request_data = {
        "id": "test-1",
        "method": "list_tools",
        "params": {}
    }
    
    response = requests.post(f"{burlymcp_container}/mcp", json=request_data)
    
    assert response.status_code == 200
    data = response.json()
    
    assert data["ok"] is True
    assert "data" in data
    assert "tools" in data["data"]
    assert isinstance(data["data"]["tools"], list)

def test_mcp_call_tool_direct_format(burlymcp_container):
    """Test MCP call_tool with direct format"""
    request_data = {
        "id": "test-2",
        "method": "call_tool",
        "name": "disk_space",
        "args": {}
    }
    
    response = requests.post(f"{burlymcp_container}/mcp", json=request_data)
    
    assert response.status_code == 200
    data = response.json()
    
    assert "ok" in data
    assert "summary" in data
    assert "metrics" in data

def test_graceful_degradation_docker_unavailable(burlymcp_container):
    """Test Docker tools fail gracefully when Docker unavailable"""
    request_data = {
        "id": "test-3",
        "method": "call_tool",
        "name": "docker_ps",
        "args": {}
    }
    
    response = requests.post(f"{burlymcp_container}/mcp", json=request_data)
    
    assert response.status_code == 200
    data = response.json()
    
    # Should fail gracefully, not crash
    assert "ok" in data
    if not data["ok"]:
        assert "Docker" in data.get("error", "")
        assert "suggestion" in data.get("data", {})
```

### Integration Testing

**MCP Protocol Compatibility**:
```python
def test_mcp_protocol_compatibility():
    """Test that HTTP bridge maintains MCP protocol compatibility"""
    
    # Test both request formats produce equivalent results
    direct_request = {
        "id": "test",
        "method": "call_tool", 
        "name": "disk_space",
        "args": {}
    }
    
    params_request = {
        "id": "test",
        "method": "call_tool",
        "params": {
            "name": "disk_space",
            "args": {}
        }
    }
    
    direct_response = requests.post(f"{container}/mcp", json=direct_request)
    params_response = requests.post(f"{container}/mcp", json=params_request)
    
    # Both should succeed and have same structure
    assert direct_response.status_code == 200
    assert params_response.status_code == 200
    
    direct_data = direct_response.json()
    params_data = params_response.json()
    
    # Response structure should be identical
    assert set(direct_data.keys()) == set(params_data.keys())
    assert direct_data["ok"] == params_data["ok"]
```

## Security Implementation

### Container Security

**Runtime User Configuration**:
```dockerfile
# Create dedicated runtime user
RUN useradd -u 1000 -m mcp --shell /bin/bash

# Set up secure directory permissions
RUN mkdir -p /var/log/agentops /app/data && \
    chown -R mcp:mcp /app /var/log/agentops && \
    chmod 750 /var/log/agentops

USER mcp
```

**Environment Variable Sanitization**:
```python
def sanitize_environment_for_subprocess():
    """Create sanitized environment for MCP engine subprocess"""
    env = os.environ.copy()
    
    # Remove secrets from child processes
    sensitive_vars = [
        "GOTIFY_TOKEN",
        "DOCKER_HOST"
    ]
    
    for var in sensitive_vars:
        env.pop(var, None)
    
    return env

# Note: Child subprocesses that talk to the MCP engine MUST receive 
# a sanitized environment with secrets (like GOTIFY_TOKEN) removed.
# Do not strip HOME or USER from the main process as this can break libraries.
```

### API Security

**Request Validation and Rate Limiting**:
```python
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

# Rate limiting is REQUIRED for /mcp in public deployments,
# but MAY be disabled via RATE_LIMIT_DISABLED=true for offline/lab use
rate_limit_enabled = os.environ.get("RATE_LIMIT_DISABLED", "false").lower() != "true"

if rate_limit_enabled:
    limiter = Limiter(key_func=get_remote_address)
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

@app.post("/mcp")
@limiter.limit("60/minute") if rate_limit_enabled else lambda f: f
async def mcp_endpoint(request: Request, mcp_request: MCPRequest):
    """Rate-limited MCP endpoint"""
    # Implementation with rate limiting
```

**Input Sanitization**:
```python
def sanitize_mcp_request(request: MCPRequest) -> MCPRequest:
    """Sanitize MCP request to prevent injection attacks"""
    
    # Limit request size
    request_str = json.dumps(request.dict())
    if len(request_str) > 10000:  # 10KB limit
        raise ValueError("Request too large")
    
    # Sanitize tool names (alphanumeric and underscore only)
    if request.name and not re.match(r'^[a-zA-Z0-9_]+$', request.name):
        raise ValueError("Invalid tool name format")
    
    # Limit argument complexity
    if request.args and count_nested_objects(request.args) > 100:
        raise ValueError("Request arguments too complex")
    
    return request
```

## Migration Strategy

### Phase 1: Create HTTP Bridge and Runtime Dockerfile

1. **Create `http_bridge.py`** with FastAPI implementation
2. **Create `Dockerfile.runtime`** with canonical container definition
3. **Test basic HTTP endpoints** with existing MCP engine
4. **Validate container builds** from repo root successfully

### Phase 2: Implement Graceful Degradation

1. **Add feature detection** for Docker, notifications, blog directories
2. **Implement degraded responses** for unavailable features
3. **Test zero-config startup** with minimal container run
4. **Validate error handling** for missing optional dependencies

### Phase 3: Move Docker Compose to Examples

1. **Create `examples/compose/` directory**
2. **Move existing compose files** with generic configuration
3. **Add explanatory comments** about optional nature
4. **Remove homelab-specific values** and add parameterization
5. **Update documentation** to clarify container vs compose contracts

### Phase 4: Set Up Container Publishing

1. **Create GitHub Actions workflow** for automated publishing
2. **Configure GHCR publishing** with proper tags and metadata
3. **Test automated builds** on push to main branch
4. **Validate published images** work independently

### Phase 5: Update Documentation and Testing

1. **Add Runtime Contract section** to README with examples
2. **Document environment variables** and configuration options
3. **Create container integration tests** for black-box validation
4. **Update existing tests** to work with new structure

### Validation Criteria

**Container Independence**:
- Container starts successfully with `docker run -p 9400:9400 ghcr.io/<org>/burlymcp:main`
- Health endpoint returns 200 OK without external dependencies
- MCP list_tools works without Docker socket or special mounts
- All tools fail gracefully when optional features unavailable

**API Stability**:
- Both direct and params request formats supported
- Response envelope maintains consistent structure
- Error responses include helpful suggestions
- HTTP bridge survives MCP engine refactors
- The /mcp request/response contract MUST remain stable across internal refactors of the MCP engine. Refactors MAY replace the subprocess call with direct function invocation, but MUST NOT require downstream systems (Open WebUI, system-tools stack, etc.) to change how they call /mcp

**Security Posture**:
- Container runs as non-root user (mcp:1000)
- No hardcoded secrets or paths in image
- Graceful handling of missing optional mounts
- Rate limiting and input validation on HTTP endpoints

**Public Portability**:
- No homelab-specific configuration in published image
- All defaults work on arbitrary Linux hosts
- Documentation includes generic examples only
- Example compose files use parameterized values