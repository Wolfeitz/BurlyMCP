"""
HTTP Bridge for BurlyMCP

This module implements a FastAPI HTTP bridge that provides REST endpoints
for the BurlyMCP service. It translates HTTP requests to MCP protocol
messages and provides a stable API contract for downstream systems.

Key Features:
- /health endpoint for service health monitoring
- /mcp endpoint for MCP protocol communication via HTTP
- Request format normalization (direct args vs params wrapper)
- Comprehensive error handling with structured responses
- Always returns HTTP 200 with JSON envelope for /mcp endpoint
- Metrics tracking for audit and telemetry

The HTTP bridge isolates the MCP engine behind a single call boundary,
allowing the internal implementation to change (subprocess to in-process)
without affecting the external API contract.
"""

import asyncio
import json
import logging
import os
import re
import subprocess
import time
from pathlib import Path
from typing import Any, Dict, Optional, Union

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from pydantic import BaseModel, Field, validator

# Rate limiting imports - conditional based on availability
try:
    from slowapi import Limiter, _rate_limit_exceeded_handler
    from slowapi.util import get_remote_address
    from slowapi.errors import RateLimitExceeded
    RATE_LIMITING_AVAILABLE = True
except ImportError:
    # Graceful degradation if slowapi not available
    RATE_LIMITING_AVAILABLE = False
    Limiter = None
    RateLimitExceeded = None

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Global state for tracking uptime and health
_start_time = time.time()
_health_cache: Optional[Dict[str, Any]] = None
_health_cache_time = 0
_health_cache_ttl = 30  # Cache health status for 30 seconds

# Security configuration
MAX_REQUEST_SIZE = 10 * 1024  # 10KB maximum request size
RATE_LIMIT_DEFAULT = "60/minute"  # Default rate limit for /mcp endpoint
TOOL_NAME_PATTERN = re.compile(r'^[a-zA-Z0-9_]+$')  # Valid tool name pattern


class MCPRequest(BaseModel):
    """
    Unified MCP request model supporting multiple formats.
    
    Supports both direct format:
    {"id": "1", "method": "call_tool", "name": "disk_space", "args": {}}
    
    And params format:
    {"id": "1", "method": "call_tool", "params": {"name": "disk_space", "args": {}}}
    """
    id: str = Field(..., description="Request identifier")
    method: str = Field(..., description="MCP method name")
    name: Optional[str] = Field(None, description="Tool name for direct format")
    args: Optional[Dict[str, Any]] = Field(None, description="Tool arguments for direct format")
    params: Optional[Dict[str, Any]] = Field(None, description="Parameters wrapper format")

    @validator('method')
    def validate_method(cls, v):
        """Validate that method is a supported MCP method."""
        allowed_methods = ['list_tools', 'call_tool']
        if v not in allowed_methods:
            raise ValueError(f"Method must be one of: {allowed_methods}")
        return v

    @validator('name')
    def validate_tool_name(cls, v):
        """Validate tool name format for security."""
        if v is not None:
            if not TOOL_NAME_PATTERN.match(v):
                raise ValueError("Tool name must contain only alphanumeric characters and underscores")
            if len(v) > 100:  # Reasonable limit for tool names
                raise ValueError("Tool name too long (max 100 characters)")
        return v

    @validator('params')
    def validate_params_format(cls, v, values):
        """Validate params format when used."""
        if v is not None:
            method = values.get('method')
            if method == 'call_tool':
                if 'name' not in v:
                    raise ValueError("params format requires 'name' field for call_tool")
                # Validate tool name in params format too
                tool_name = v.get('name')
                if tool_name and not TOOL_NAME_PATTERN.match(str(tool_name)):
                    raise ValueError("Tool name in params must contain only alphanumeric characters and underscores")
        return v


class MCPResponse(BaseModel):
    """
    Standardized MCP response envelope.
    
    This model ensures consistent response format across all operations,
    including required fields for metrics and error handling.
    """
    ok: bool = Field(..., description="Operation success status")
    summary: str = Field(..., description="Brief operation summary")
    need_confirm: Optional[bool] = Field(None, description="Whether confirmation is required")
    data: Optional[Dict[str, Any]] = Field(None, description="Structured response data")
    stdout: Optional[str] = Field(None, description="Command standard output")
    stderr: Optional[str] = Field(None, description="Command standard error")
    error: Optional[str] = Field(None, description="Error message for failed operations")
    metrics: Dict[str, Any] = Field(default_factory=dict, description="Execution metrics")

    def __init__(self, **data):
        super().__init__(**data)
        # Ensure metrics always includes required fields
        if 'elapsed_ms' not in self.metrics:
            self.metrics['elapsed_ms'] = 0
        if 'exit_code' not in self.metrics:
            self.metrics['exit_code'] = 0 if self.ok else 1


class HealthResponse(BaseModel):
    """
    Health check response with comprehensive system status.
    
    Provides detailed information about service health, feature availability,
    and system configuration for monitoring and debugging.
    """
    status: str = Field(..., description="Overall health status: ok, degraded, or error")
    server_name: str = Field(..., description="Server identifier")
    version: str = Field(..., description="Server version")
    tools_available: int = Field(..., description="Number of available tools")
    notifications_enabled: bool = Field(..., description="Whether notifications are configured")
    docker_available: bool = Field(..., description="Whether Docker operations are available")
    strict_security_mode: bool = Field(..., description="Whether strict security is enabled")
    policy_loaded: bool = Field(..., description="Whether policy is successfully loaded")
    uptime_seconds: Optional[int] = Field(None, description="Server uptime in seconds")


def is_rate_limiting_enabled() -> bool:
    """
    Check if rate limiting should be enabled.
    
    Rate limiting is enabled by default but can be disabled via
    RATE_LIMIT_DISABLED environment variable for lab/air-gapped deployments.
    
    Returns:
        True if rate limiting should be enabled, False otherwise
    """
    return (
        RATE_LIMITING_AVAILABLE and 
        os.environ.get("RATE_LIMIT_DISABLED", "false").lower() not in ["true", "1", "yes"]
    )


def sanitize_mcp_request_data(request_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Sanitize MCP request data to prevent injection attacks.
    
    Args:
        request_data: Raw request data dictionary
        
    Returns:
        Sanitized request data
        
    Raises:
        ValueError: If request data is invalid or potentially malicious
    """
    # Check request size
    request_str = json.dumps(request_data, separators=(',', ':'))
    if len(request_str.encode('utf-8')) > MAX_REQUEST_SIZE:
        raise ValueError(f"Request too large (max {MAX_REQUEST_SIZE} bytes)")
    
    # Validate tool name if present
    tool_name = None
    if 'name' in request_data:
        tool_name = request_data['name']
    elif 'params' in request_data and isinstance(request_data['params'], dict):
        tool_name = request_data['params'].get('name')
    
    if tool_name is not None:
        if not isinstance(tool_name, str):
            raise ValueError("Tool name must be a string")
        if not TOOL_NAME_PATTERN.match(tool_name):
            raise ValueError("Tool name contains invalid characters")
        if len(tool_name) > 100:
            raise ValueError("Tool name too long")
    
    # Validate arguments depth and complexity
    args = None
    if 'args' in request_data:
        args = request_data['args']
    elif 'params' in request_data and isinstance(request_data['params'], dict):
        args = request_data['params'].get('args')
    
    if args is not None:
        _validate_args_complexity(args, max_depth=5, max_items=100)
    
    return request_data


def _validate_args_complexity(obj: Any, max_depth: int, max_items: int, current_depth: int = 0) -> None:
    """
    Validate that arguments don't exceed complexity limits.
    
    Args:
        obj: Object to validate
        max_depth: Maximum nesting depth allowed
        max_items: Maximum number of items in collections
        current_depth: Current nesting depth
        
    Raises:
        ValueError: If complexity limits are exceeded
    """
    if current_depth > max_depth:
        raise ValueError(f"Arguments too deeply nested (max depth: {max_depth})")
    
    if isinstance(obj, dict):
        if len(obj) > max_items:
            raise ValueError(f"Too many dictionary items (max: {max_items})")
        for key, value in obj.items():
            if not isinstance(key, str) or len(key) > 100:
                raise ValueError("Dictionary keys must be strings with max 100 characters")
            _validate_args_complexity(value, max_depth, max_items, current_depth + 1)
    
    elif isinstance(obj, list):
        if len(obj) > max_items:
            raise ValueError(f"Too many list items (max: {max_items})")
        for item in obj:
            _validate_args_complexity(item, max_depth, max_items, current_depth + 1)
    
    elif isinstance(obj, str):
        if len(obj) > 10000:  # 10KB limit for individual strings
            raise ValueError("String value too long")


# Initialize FastAPI application
app = FastAPI(
    title="BurlyMCP HTTP Bridge",
    description="HTTP API bridge for BurlyMCP Model Context Protocol server",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# Initialize rate limiting if available and enabled
rate_limiter = None
if is_rate_limiting_enabled():
    rate_limiter = Limiter(key_func=get_remote_address)
    app.state.limiter = rate_limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)


def load_runtime_config() -> Dict[str, Any]:
    """
    Load runtime configuration from environment variables.
    
    Uses the centralized Config class with container-internal defaults
    that work without external mounts or configuration files.
    
    Returns:
        Dictionary containing all configuration settings
    """
    try:
        # Try to import from the src package structure
        from src.burly_mcp.config import Config
    except ImportError:
        # Fallback for different import paths
        import sys
        sys.path.insert(0, 'src')
        from burly_mcp.config import Config
    
    # Load configuration using the centralized Config class
    config_obj = Config.load_runtime_config()
    
    # Convert to dictionary for compatibility with existing code
    return config_obj.to_dict()


def sanitize_environment_for_subprocess() -> Dict[str, str]:
    """
    Create sanitized environment for MCP engine subprocess.
    
    Removes sensitive environment variables while preserving
    necessary system variables for proper library function.
    
    Returns:
        Sanitized environment dictionary
    """
    env = os.environ.copy()
    
    # Remove secrets from child processes
    sensitive_vars = [
        "GOTIFY_TOKEN",
        "DOCKER_HOST"  # If set, could expose Docker daemon
    ]
    
    for var in sensitive_vars:
        env.pop(var, None)
    
    return env


def normalize_mcp_request(request: MCPRequest) -> Dict[str, Any]:
    """
    Normalize different request formats to standard MCP format.
    
    Handles both direct format and params wrapper format,
    converting them to a consistent internal representation.
    
    Args:
        request: The incoming MCPRequest
        
    Returns:
        Normalized request dictionary
    """
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
        if request.method == "call_tool":
            return {
                "id": request.id,
                "method": request.method,
                "name": request.params.get("name"),
                "args": request.params.get("args", {})
            }
        else:
            # For list_tools and other methods
            return {
                "id": request.id,
                "method": request.method,
                "params": request.params
            }
    
    # Handle list_tools format: {"method": "list_tools", "params": {}}
    return {
        "id": request.id,
        "method": request.method,
        "params": {}
    }


async def forward_to_mcp_engine(normalized_request: Dict[str, Any]) -> Dict[str, Any]:
    """
    Forward request to MCP engine with comprehensive error handling.
    
    This function isolates the MCP engine behind a single call boundary,
    allowing the implementation to change from subprocess to in-process
    without affecting the HTTP API contract.
    
    The bridge treats the MCP engine as an interchangeable backend:
    - Today: subprocess that runs `python -m burly_mcp.server.main`
    - Future: direct import and in-process calls
    
    The HTTP schema MUST NOT depend on whether the engine runs as subprocess.
    
    Args:
        normalized_request: Normalized MCP request dictionary
        
    Returns:
        MCP response dictionary with standardized envelope
    """
    start_time = time.time()
    
    try:
        # Prepare sanitized environment for subprocess
        env = sanitize_environment_for_subprocess()
        
        # Create subprocess to run MCP engine
        # This is the current implementation - may become in-process in future
        process = await asyncio.create_subprocess_exec(
            "python", "-m", "burly_mcp.server.main",
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=env,
            # Process management settings
            preexec_fn=None,  # Don't inherit signal handlers
            start_new_session=True  # Create new process group
        )
        
        # Send request as JSON line (MCP protocol over stdin/stdout)
        request_json = json.dumps(normalized_request) + "\n"
        
        try:
            stdout, stderr = await asyncio.wait_for(
                process.communicate(request_json.encode('utf-8')),
                timeout=60.0  # 60 second timeout for tool execution
            )
        except asyncio.TimeoutError:
            # Kill the process if it times out
            try:
                process.kill()
                await process.wait()
            except Exception:
                pass  # Process might already be dead
            
            elapsed_ms = int((time.time() - start_time) * 1000)
            return {
                "ok": False,
                "summary": "MCP engine timeout",
                "error": "MCP engine did not respond within timeout period (60s)",
                "metrics": {"elapsed_ms": elapsed_ms, "exit_code": 124}
            }
        
        elapsed_ms = int((time.time() - start_time) * 1000)
        
        # Handle process exit codes
        if process.returncode != 0:
            error_msg = stderr.decode('utf-8', errors='replace').strip()
            logger.warning(f"MCP engine process failed with exit code {process.returncode}: {error_msg}")
            return {
                "ok": False,
                "summary": "MCP engine process failed",
                "error": f"Process exited with code {process.returncode}: {error_msg}",
                "metrics": {"elapsed_ms": elapsed_ms, "exit_code": process.returncode}
            }
        
        # Parse response from stdout
        stdout_str = stdout.decode('utf-8', errors='replace').strip()
        if not stdout_str:
            stderr_str = stderr.decode('utf-8', errors='replace').strip()
            logger.error(f"Empty response from MCP engine. stderr: {stderr_str}")
            return {
                "ok": False,
                "summary": "Empty response from MCP engine",
                "error": "No response received from MCP engine",
                "data": {"stderr": stderr_str} if stderr_str else None,
                "metrics": {"elapsed_ms": elapsed_ms, "exit_code": 1}
            }
        
        try:
            # Parse the JSON response from MCP engine
            response = json.loads(stdout_str)
            
            # Ensure response has required metrics for audit/telemetry
            if "metrics" not in response:
                response["metrics"] = {}
            
            # Always include elapsed_ms and exit_code in metrics
            response["metrics"]["elapsed_ms"] = elapsed_ms
            if "exit_code" not in response["metrics"]:
                response["metrics"]["exit_code"] = 0 if response.get("ok", False) else 1
            
            # Log successful communication
            logger.debug(f"MCP engine response: ok={response.get('ok')}, elapsed={elapsed_ms}ms")
            
            return response
            
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON from MCP engine: {e}. Raw output: {stdout_str[:500]}")
            return {
                "ok": False,
                "summary": "Response parsing failed",
                "error": f"Invalid JSON from MCP engine: {e}",
                "data": {"raw_output": stdout_str[:1000]},  # First 1KB for debugging
                "metrics": {"elapsed_ms": elapsed_ms, "exit_code": 1}
            }
        
    except Exception as e:
        elapsed_ms = int((time.time() - start_time) * 1000)
        logger.error(f"MCP engine communication failed: {e}", exc_info=True)
        return {
            "ok": False,
            "summary": "MCP engine communication failed",
            "error": f"Failed to communicate with MCP engine: {str(e)}",
            "metrics": {"elapsed_ms": elapsed_ms, "exit_code": 1}
        }


def check_docker_availability() -> bool:
    """
    Check if Docker operations are available.
    
    Returns:
        True if Docker socket is accessible, False otherwise
    """
    # Use the feature detection framework for consistency
    try:
        from src.burly_mcp.feature_detection import get_feature_detector
        feature_detector = get_feature_detector()
        docker_status = feature_detector.check_docker_availability()
        return docker_status.available
    except ImportError:
        # Fallback to simple check if feature detection not available
        try:
            config = load_runtime_config()
            docker_socket = Path(config["docker_socket"])
            return docker_socket.exists() and docker_socket.is_socket()
        except Exception:
            return False


def check_notifications_configured() -> bool:
    """
    Check if notifications are properly configured.
    
    Returns:
        True if Gotify URL and token are configured, False otherwise
    """
    # Use the feature detection framework for consistency
    try:
        from src.burly_mcp.feature_detection import get_feature_detector
        feature_detector = get_feature_detector()
        notifications_status = feature_detector.check_notifications_configured()
        return notifications_status.available
    except ImportError:
        # Fallback to simple check if feature detection not available
        config = load_runtime_config()
        return bool(config.get("gotify_url") and config.get("gotify_token"))


def check_policy_loaded() -> bool:
    """
    Check if policy file is accessible and valid.
    
    Returns:
        True if policy file exists and is readable, False otherwise
    """
    # Use the feature detection framework for consistency
    try:
        from src.burly_mcp.feature_detection import get_feature_detector
        feature_detector = get_feature_detector()
        policy_status = feature_detector.check_policy_loaded()
        return policy_status.available
    except ImportError:
        # Fallback to simple check if feature detection not available
        config = load_runtime_config()
        policy_file = Path(config["policy_file"])
        try:
            return policy_file.exists() and policy_file.is_file()
        except Exception:
            return False


async def test_mcp_engine() -> Dict[str, Any]:
    """
    Perform a quick health test of the MCP engine.
    
    Returns:
        Dictionary with test results
    """
    try:
        # Simple list_tools request to test engine
        test_request = {
            "id": "health-check",
            "method": "list_tools",
            "params": {}
        }
        
        response = await forward_to_mcp_engine(test_request)
        return {
            "ok": response.get("ok", False),
            "tools_count": len(response.get("data", {}).get("tools", [])) if response.get("data") else 0
        }
        
    except Exception as e:
        return {
            "ok": False,
            "error": str(e),
            "tools_count": 0
        }


@app.get("/health", response_model=HealthResponse)
async def health_check():
    """
    Comprehensive health check endpoint.
    
    Returns detailed system status including feature availability,
    configuration status, and service health. Uses caching to avoid
    expensive checks on every request.
    
    MUST include: server_name, version (aka server_version), policy_loaded,
    strict_security_mode, docker_available, notifications_enabled, and tools_available.
    
    MUST return status: "ok" only if MCP engine is callable AND policy loaded;
    otherwise MUST return "degraded". MUST NOT return "error" unless the service
    is effectively unusable.
    
    Returns:
        HealthResponse with comprehensive system status
    """
    global _health_cache, _health_cache_time
    
    current_time = time.time()
    
    # Use cached health status if still valid (reduces load on health checks)
    if _health_cache and (current_time - _health_cache_time) < _health_cache_ttl:
        return HealthResponse(**_health_cache)
    
    # Perform comprehensive health checks
    config = load_runtime_config()
    
    # Check MCP engine health with quick test
    mcp_test = await test_mcp_engine()
    mcp_healthy = mcp_test.get("ok", False)
    tools_count = mcp_test.get("tools_count", 0)
    
    # Check system feature detection
    docker_available = check_docker_availability()
    notifications_enabled = check_notifications_configured()
    policy_loaded = check_policy_loaded()
    
    # Check blog directories accessibility
    blog_stage_accessible = False
    blog_publish_accessible = False
    try:
        stage_path = Path(config["blog_stage_root"])
        publish_path = Path(config["blog_publish_root"])
        blog_stage_accessible = stage_path.exists() and stage_path.is_dir()
        blog_publish_accessible = publish_path.exists() and publish_path.is_dir()
    except Exception:
        pass  # Graceful degradation
    
    # Determine overall status according to requirements
    # "ok" only if MCP engine is callable AND policy loaded
    # "degraded" for other cases where service is still usable
    # "error" only if service is effectively unusable
    if mcp_healthy and policy_loaded:
        status = "ok"
    elif policy_loaded or mcp_healthy:  # At least one core component working
        status = "degraded"
    else:  # Neither MCP engine nor policy working - service unusable
        status = "error"
    
    # Build comprehensive health response with all required fields
    health_data = {
        "status": status,
        "server_name": config["server_name"],
        "version": config["server_version"],  # aka server_version
        "tools_available": tools_count,
        "notifications_enabled": notifications_enabled,
        "docker_available": docker_available,
        "strict_security_mode": config["strict_security_mode"],
        "policy_loaded": policy_loaded,
        "uptime_seconds": int(current_time - _start_time)
    }
    
    # Cache the result to avoid expensive checks on every request
    _health_cache = health_data
    _health_cache_time = current_time
    
    logger.debug(f"Health check: status={status}, mcp_healthy={mcp_healthy}, "
                f"policy_loaded={policy_loaded}, tools={tools_count}")
    
    return HealthResponse(**health_data)


async def _rate_limit_exceeded_handler(request: Request, exc: RateLimitExceeded):
    """
    Custom rate limit exceeded handler that returns MCP-style JSON envelope.
    
    This ensures rate limit errors are returned as HTTP 200 with structured
    JSON response, maintaining the API contract for /mcp endpoint.
    """
    if request.url.path == "/mcp":
        # For /mcp endpoint, return structured error envelope
        error_response = {
            "ok": False,
            "summary": "Rate limit exceeded",
            "error": f"Too many requests: {exc.detail}",
            "data": {
                "retry_after": getattr(exc, 'retry_after', None),
                "suggestion": "Reduce request frequency or set RATE_LIMIT_DISABLED=true for lab environments"
            },
            "metrics": {"elapsed_ms": 0, "exit_code": 429}
        }
        return JSONResponse(status_code=200, content=error_response)
    else:
        # For other endpoints, use standard HTTP 429
        return JSONResponse(
            status_code=429,
            content={"detail": exc.detail},
            headers={"Retry-After": str(getattr(exc, 'retry_after', 60))}
        )


# Apply rate limiting decorator conditionally
def apply_rate_limit(func):
    """Apply rate limiting to endpoint if enabled."""
    if rate_limiter:
        return rate_limiter.limit(RATE_LIMIT_DEFAULT)(func)
    return func


@app.post("/mcp")
@apply_rate_limit
async def mcp_endpoint(request: Request, mcp_request: MCPRequest):
    """
    MCP protocol endpoint via HTTP with security measures.
    
    Accepts MCP requests in multiple formats, normalizes them,
    forwards to the MCP engine, and returns standardized responses.
    
    Security features:
    - Rate limiting (60/minute by default, configurable via RATE_LIMIT_DISABLED)
    - Request size validation (10KB maximum)
    - Input sanitization for tool names and arguments
    - Complexity validation to prevent resource exhaustion
    
    CRITICAL: This endpoint MUST always return HTTP 200 with a JSON
    envelope. Errors and failures are expressed in the response body,
    never via HTTP 4xx/5xx status codes.
    
    Args:
        request: FastAPI Request object (for rate limiting)
        mcp_request: MCP request in supported format
        
    Returns:
        JSON response with standardized envelope
    """
    start_time = time.time()
    
    try:
        # Validate request size at the HTTP level
        content_length = request.headers.get('content-length')
        if content_length and int(content_length) > MAX_REQUEST_SIZE:
            elapsed_ms = int((time.time() - start_time) * 1000)
            return JSONResponse(
                status_code=200,
                content={
                    "ok": False,
                    "summary": "Request too large",
                    "error": f"Request body exceeds maximum size of {MAX_REQUEST_SIZE} bytes",
                    "data": {
                        "max_size_bytes": MAX_REQUEST_SIZE,
                        "suggestion": "Reduce request payload size"
                    },
                    "metrics": {"elapsed_ms": elapsed_ms, "exit_code": 1}
                }
            )
        
        # Additional sanitization of the request data
        try:
            request_dict = mcp_request.dict()
            sanitize_mcp_request_data(request_dict)
        except ValueError as e:
            elapsed_ms = int((time.time() - start_time) * 1000)
            return JSONResponse(
                status_code=200,
                content={
                    "ok": False,
                    "summary": "Invalid request format",
                    "error": f"Request validation failed: {str(e)}",
                    "data": {
                        "suggestion": "Check request format and reduce complexity"
                    },
                    "metrics": {"elapsed_ms": elapsed_ms, "exit_code": 1}
                }
            )
        
        # Normalize request format
        normalized_request = normalize_mcp_request(mcp_request)
        
        # Forward to MCP engine
        mcp_response = await forward_to_mcp_engine(normalized_request)
        
        # Ensure response has required fields and return as JSON
        # Always return HTTP 200 - errors are in the response body
        return JSONResponse(
            status_code=200,
            content=mcp_response
        )
        
    except Exception as e:
        # Fallback error response - still HTTP 200
        elapsed_ms = int((time.time() - start_time) * 1000)
        
        # Sanitize error message to avoid information disclosure
        error_msg = "An unexpected error occurred"
        if "validation" in str(e).lower() or "invalid" in str(e).lower():
            error_msg = "Request validation failed"
        elif "timeout" in str(e).lower():
            error_msg = "Request timeout"
        
        error_response = {
            "ok": False,
            "summary": "Request processing failed",
            "error": error_msg,
            "metrics": {"elapsed_ms": elapsed_ms, "exit_code": 1}
        }
        
        # Log full error details for debugging (but don't expose to client)
        logger.error(f"MCP endpoint error: {e}", exc_info=True)
        
        return JSONResponse(
            status_code=200,  # Always HTTP 200
            content=error_response
        )


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """
    Global exception handler to ensure we never return non-200 responses
    from the /mcp endpoint, maintaining the API contract.
    """
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    
    # For /mcp endpoint, always return HTTP 200 with error envelope
    if request.url.path == "/mcp":
        error_response = {
            "ok": False,
            "summary": "Internal server error",
            "error": "An unexpected error occurred",
            "metrics": {"elapsed_ms": 0, "exit_code": 1}
        }
        return JSONResponse(status_code=200, content=error_response)
    
    # For other endpoints, use standard HTTP error responses
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error"}
    )


# Override the default rate limit handler if rate limiting is enabled
if rate_limiter:
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """
    Handle validation errors to ensure /mcp endpoint always returns HTTP 200.
    """
    # For /mcp endpoint, return HTTP 200 with structured error
    if request.url.path == "/mcp":
        # Convert validation errors to JSON-serializable format
        validation_errors = []
        for error in exc.errors():
            serializable_error = {
                "type": error.get("type", "unknown"),
                "location": error.get("loc", []),
                "message": error.get("msg", "Validation error"),
                "input": str(error.get("input", ""))
            }
            validation_errors.append(serializable_error)
        
        error_response = {
            "ok": False,
            "summary": "Request validation failed",
            "error": "Invalid request format or parameters",
            "data": {
                "validation_errors": validation_errors,
                "suggestion": "Check request format and parameter types"
            },
            "metrics": {"elapsed_ms": 0, "exit_code": 1}
        }
        return JSONResponse(status_code=200, content=error_response)
    
    # For other endpoints, use standard HTTP 422
    return JSONResponse(
        status_code=422,
        content={"detail": exc.errors()}
    )


# Application startup
@app.on_event("startup")
async def startup_event():
    """
    Application startup event handler.
    
    Logs startup information and validates basic configuration.
    """
    config = load_runtime_config()
    
    logger.info("=== BurlyMCP HTTP Bridge Starting ===")
    logger.info(f"Server: {config['server_name']} v{config['server_version']}")
    logger.info(f"Policy file: {config['policy_file']}")
    logger.info(f"Audit logging: {'enabled' if config['audit_enabled'] else 'disabled'}")
    logger.info(f"Notifications: {'enabled' if config['notifications_enabled'] else 'disabled'}")
    logger.info(f"Docker socket: {config['docker_socket']}")
    logger.info(f"Security: Rate limiting {'enabled' if is_rate_limiting_enabled() else 'disabled'}")
    logger.info(f"Security: Max request size {MAX_REQUEST_SIZE} bytes")
    logger.info(f"Listening on: {config['host']}:{config['port']}")
    logger.info("HTTP Bridge ready - /health and /mcp endpoints available")


@app.on_event("shutdown")
async def shutdown_event():
    """
    Application shutdown event handler.
    """
    logger.info("BurlyMCP HTTP Bridge shutting down")


if __name__ == "__main__":
    import uvicorn
    
    config = load_runtime_config()
    
    uvicorn.run(
        "http_bridge:app",
        host=config["host"],
        port=config["port"],
        log_level=config["log_level"].lower(),
        access_log=True
    )