"""
Pytest configuration and shared fixtures for Burly MCP tests.

This module provides common test fixtures and configuration for both
unit and integration tests.
"""

import tempfile
from pathlib import Path
from unittest.mock import Mock

import pytest


@pytest.fixture
def temp_dir():
    """Create a temporary directory for test files."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def mock_env_vars():
    """Provide mock environment variables for testing."""
    test_dir = Path(__file__).parent
    return {
        "LOG_LEVEL": "DEBUG",
        "LOG_DIR": str(test_dir / "fixtures" / "logs"),
        "POLICY_FILE": str(test_dir / "fixtures" / "test_policy.yaml"),
        "BLOG_STAGE_ROOT": str(test_dir / "fixtures" / "blog_stage"),
        "BLOG_PUBLISH_ROOT": str(test_dir / "fixtures" / "blog_publish"),
        "DEFAULT_TIMEOUT_SEC": "10",
        "OUTPUT_TRUNCATE_LIMIT": "1024",
        "AUDIT_LOG_DIR": str(test_dir / "fixtures" / "logs"),
        "NOTIFICATIONS_ENABLED": "false",
        "SERVER_NAME": "test-burly-mcp",
        "SERVER_VERSION": "0.0.1-test",
    }


@pytest.fixture
def mock_config(mock_env_vars, monkeypatch):
    """Set up mock environment variables for testing."""
    for key, value in mock_env_vars.items():
        monkeypatch.setenv(key, value)
    return mock_env_vars


@pytest.fixture
def sample_blog_post():
    """Provide sample blog post content for testing."""
    return """---
title: "Test Blog Post"
date: "2024-01-01"
tags: ["test", "example"]
author: "Test Author"
---

# Test Blog Post

This is a test blog post for validation testing.

## Content

Some example content here.
"""


@pytest.fixture
def invalid_blog_post():
    """Provide invalid blog post content for testing."""
    return """---
title: "Missing Date Post"
tags: ["test"]
---

# Invalid Post

This post is missing required fields.
"""


@pytest.fixture
def sample_mcp_request():
    """Provide sample MCP request data."""
    return {"method": "call_tool", "name": "disk_space", "args": {}}


@pytest.fixture
def sample_tool_result():
    """Provide sample tool result data."""
    from burly_mcp.tools.registry import ToolResult

    return ToolResult(
        success=True,
        need_confirm=False,
        summary="Test operation completed",
        data={"test": "data"},
        stdout="Test output",
        stderr="",
        exit_code=0,
        elapsed_ms=100,
    )


# Test markers and plugins
pytest_plugins = []


def pytest_configure(config):
    """Configure pytest with custom markers."""
    # Markers are now defined in pyproject.toml
    pass


def pytest_collection_modifyitems(config, items):
    """Automatically mark tests based on their location."""
    for item in items:
        # Mark tests based on directory structure
        if "unit" in str(item.fspath):
            item.add_marker(pytest.mark.unit)
        elif "integration" in str(item.fspath):
            item.add_marker(pytest.mark.integration)

        # Mark Docker-related tests
        if "docker" in str(item.fspath) or "docker" in item.name.lower():
            item.add_marker(pytest.mark.docker)

        # Mark slow tests (integration tests are typically slower)
        if "integration" in str(item.fspath):
            item.add_marker(pytest.mark.slow)


@pytest.fixture(scope="session")
def docker_available():
    """Check if Docker is available for testing."""
    import subprocess

    try:
        result = subprocess.run(["docker", "version"], capture_output=True, timeout=5)
        return result.returncode == 0
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return False


@pytest.fixture
def sample_policy_yaml():
    """Provide sample policy YAML content for testing."""
    return """
tools:
  test_tool:
    description: "Test tool for unit tests"
    args_schema:
      type: "object"
      properties:
        test_param:
          type: "string"
          description: "Test parameter"
      required: ["test_param"]
      additionalProperties: false
    command: []
    mutates: false
    requires_confirm: false
    timeout_sec: 10
    notify: ["success", "failure"]

config:
  output_truncate_limit: 1024
  default_timeout_sec: 30
  security:
    enable_path_validation: true
    allowed_paths: ["/tmp", "/var/tmp"]
"""


@pytest.fixture
def multi_tool_policy_yaml():
    """Provide sample policy YAML content with multiple tools for testing."""
    return """
tools:
  test_tool:
    description: "Test tool for unit tests"
    args_schema:
      type: "object"
      properties:
        test_param:
          type: "string"
          description: "Test parameter"
      required: []
      additionalProperties: false
    command: []
    mutates: false
    requires_confirm: false
    timeout_sec: 10
    notify: ["success", "failure"]

  confirm_tool:
    description: "Tool requiring confirmation"
    args_schema:
      type: "object"
      properties: {}
      required: []
      additionalProperties: false
    command: []
    mutates: true
    requires_confirm: true
    timeout_sec: 15
    notify: ["success", "failure", "need_confirm"]

config:
  output_truncate_limit: 1024
  default_timeout_sec: 30
  security:
    enable_path_validation: true
    allowed_paths: ["/tmp", "/var/tmp"]
"""


@pytest.fixture
def test_policy_file():
    """Create temporary policy files for testing."""

    def _create_policy_file(filename: str, content: str):
        # Create file in current directory to avoid path traversal issues
        policy_file = Path(filename)
        policy_file.write_text(content)
        return policy_file

    return _create_policy_file


@pytest.fixture(autouse=True)
def _stable_env(request, monkeypatch):
    """
    Automatically set stable environment variables for all tests.
    
    This fixture ensures test isolation by:
    - Setting MCP_ENV=test for test-specific behavior
    - Setting NO_NETWORK=1 to disable network calls in unit tests (not integration tests)
    - Setting DISABLE_DOCKER=1 to disable Docker operations in unit tests (not integration tests)
    - Setting other test-friendly environment variables
    """
    # Core test environment isolation
    monkeypatch.setenv("MCP_ENV", "test")

    # Check if this is an integration test
    is_integration_test = (
        hasattr(request, 'node') and
        any(mark.name == 'integration' for mark in request.node.iter_markers())
    )

    # Only disable Docker and network for unit tests, not integration tests
    if not is_integration_test:
        monkeypatch.setenv("NO_NETWORK", "1")
        monkeypatch.setenv("DISABLE_DOCKER", "1")

    # Test-friendly environment variables (apply to all tests)
    test_dir = Path(__file__).parent
    monkeypatch.setenv("LOG_LEVEL", "DEBUG")
    monkeypatch.setenv("LOG_DIR", str(test_dir / "fixtures" / "logs"))
    monkeypatch.setenv("POLICY_FILE", str(test_dir / "fixtures" / "test_policy.yaml"))
    monkeypatch.setenv("BLOG_STAGE_ROOT", str(test_dir / "fixtures" / "blog_stage"))
    monkeypatch.setenv("BLOG_PUBLISH_ROOT", str(test_dir / "fixtures" / "blog_publish"))
    monkeypatch.setenv("DEFAULT_TIMEOUT_SEC", "10")
    monkeypatch.setenv("OUTPUT_TRUNCATE_LIMIT", "1024")
    monkeypatch.setenv("AUDIT_LOG_DIR", str(test_dir / "fixtures" / "logs"))
    monkeypatch.setenv("NOTIFICATIONS_ENABLED", "false")
    monkeypatch.setenv("SERVER_NAME", "test-burly-mcp")
    monkeypatch.setenv("SERVER_VERSION", "0.0.1-test")


@pytest.fixture(autouse=True)
def mock_audit_and_notifications(monkeypatch):
    """Automatically mock audit logging and notifications for all tests."""
    from unittest.mock import Mock

    # Create mocks
    mock_audit = Mock()
    mock_notify_success = Mock()
    mock_notify_failure = Mock()
    mock_notify_confirmation = Mock()

    # Try to mock audit logging - only if module exists
    try:
        # Mock the imported function in the registry module
        monkeypatch.setattr("burly_mcp.tools.registry.log_tool_execution", mock_audit)
        # Also mock the audit logger itself
        monkeypatch.setattr("burly_mcp.audit.get_audit_logger", Mock())
    except (ImportError, AttributeError):
        pass  # Module not available, skip mocking

    # Try to mock notifications - only if module exists
    try:
        monkeypatch.setattr(
            "burly_mcp.tools.registry.notify_tool_success", mock_notify_success
        )
        monkeypatch.setattr(
            "burly_mcp.tools.registry.notify_tool_failure", mock_notify_failure
        )
        monkeypatch.setattr(
            "burly_mcp.tools.registry.notify_tool_confirmation",
            mock_notify_confirmation,
        )
    except (ImportError, AttributeError):
        pass  # Module not available, skip mocking

    # Return mocks for tests that need to access them
    return {
        "audit": mock_audit,
        "notify_success": mock_notify_success,
        "notify_failure": mock_notify_failure,
        "notify_confirmation": mock_notify_confirmation,
    }


# Configuration fixtures
@pytest.fixture
def mock_config_class():
    """Mock the Config class for testing."""
    from unittest.mock import Mock

    test_dir = Path(__file__).parent
    config = Mock()
    config.config_dir = test_dir / "fixtures" / "config"
    config.policy_file = test_dir / "fixtures" / "config" / "policy" / "tools.yaml"
    config.log_dir = test_dir / "fixtures" / "logs"
    config.docker_socket = "/var/run/docker.sock"
    config.docker_timeout = 30
    config.max_output_size = 1048576
    config.audit_enabled = True
    config.gotify_url = None
    config.gotify_token = None
    config.blog_stage_root = test_dir / "fixtures" / "blog_stage"
    config.blog_publish_root = test_dir / "fixtures" / "blog_publish"
    config.validate.return_value = []

    return config


@pytest.fixture
def mock_docker_client():
    """Mock Docker client for testing."""
    from unittest.mock import Mock

    client = Mock()
    client.ping.return_value = True
    client.version.return_value = {"Version": "20.10.0"}

    # Mock container operations
    container = Mock()
    container.id = "test_container_id"
    container.status = "running"
    container.logs.return_value = b"test output"
    container.wait.return_value = {"StatusCode": 0}

    client.containers.run.return_value = container
    client.containers.get.return_value = container
    client.containers.list.return_value = [container]

    # Mock image operations
    image = Mock()
    image.id = "test_image_id"
    image.tags = ["test:latest"]

    client.images.get.return_value = image
    client.images.list.return_value = [image]
    client.images.build.return_value = (image, [])

    return client


@pytest.fixture
def mock_mcp_server():
    """Mock MCP server for testing."""
    from unittest.mock import Mock

    server = Mock()
    server.list_tools.return_value = []
    server.call_tool.return_value = {"success": True, "result": "test"}

    return server


# File system fixtures
@pytest.fixture
def test_files_dir(tmp_path):
    """Create a temporary directory with test files."""
    test_dir = tmp_path / "test_files"
    test_dir.mkdir()

    # Create sample files
    (test_dir / "sample.txt").write_text("Sample content")
    (test_dir / "config.yaml").write_text("key: value")

    # Create subdirectory
    sub_dir = test_dir / "subdir"
    sub_dir.mkdir()
    (sub_dir / "nested.txt").write_text("Nested content")

    return test_dir


@pytest.fixture
def policy_config_dir(tmp_path):
    """Create a temporary policy configuration directory."""
    config_dir = tmp_path / "config"
    config_dir.mkdir()

    policy_dir = config_dir / "policy"
    policy_dir.mkdir()

    # Create a basic policy file
    policy_file = policy_dir / "tools.yaml"
    policy_file.write_text(
        """
tools:
  test_tool:
    description: "Test tool"
    args_schema:
      type: "object"
      properties: {}
      required: []
      additionalProperties: false
    command: ["echo", "test"]
    mutates: false
    requires_confirm: false
    timeout_sec: 10
    notify: ["success"]

config:
  output_truncate_limit: 1024
  default_timeout_sec: 30
"""
    )

    return config_dir


# Error simulation fixtures
@pytest.fixture
def docker_error():
    """Simulate Docker errors for testing."""
    from unittest.mock import Mock

    def create_error(error_type="APIError", message="Test error"):
        error = Mock()
        error.__class__.__name__ = error_type
        error.explanation = message
        return error

    return create_error


@pytest.fixture
def network_error():
    """Simulate network errors for testing."""
    import requests

    def create_error(status_code=500, message="Network error"):
        error = requests.exceptions.RequestException(message)
        error.response = Mock()
        error.response.status_code = status_code
        return error

    return create_error

# HTTP Bridge Testing Support
try:
    import requests
    from testcontainers.core.generic import DockerContainer
    HTTP_CLIENT_AVAILABLE = True
except ImportError:
    HTTP_CLIENT_AVAILABLE = False
    requests = None
    DockerContainer = None


@pytest.fixture
def http_client():
    """Provide HTTP client for testing HTTP endpoints."""
    if not HTTP_CLIENT_AVAILABLE:
        pytest.skip("HTTP client dependencies not available")
    
    session = requests.Session()
    session.timeout = 30  # 30 second timeout for HTTP requests
    
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def http_bridge_container():
    """
    Start HTTP bridge container for integration testing.
    
    This fixture provides a running HTTP bridge container with
    the /health and /mcp endpoints available for testing.
    """
    if not HTTP_CLIENT_AVAILABLE:
        pytest.skip("testcontainers not available")
    
    # Use the existing http_bridge.py for testing
    container = DockerContainer("python:3.12-slim")
    container.with_command("python -m http_bridge")
    container.with_exposed_ports(9400)
    container.with_env("PORT", "9400")
    container.with_env("MCP_ENV", "test")
    container.with_env("LOG_LEVEL", "DEBUG")
    
    # Mount the current directory to access http_bridge.py
    container.with_volume_mapping(".", "/app", "ro")
    container.with_working_directory("/app")
    
    try:
        container.start()
        
        # Wait for container to be ready
        host = container.get_container_host_ip()
        port = container.get_exposed_port(9400)
        base_url = f"http://{host}:{port}"
        
        # Wait for health endpoint to be available
        import time
        for _ in range(30):  # Wait up to 30 seconds
            try:
                response = requests.get(f"{base_url}/health", timeout=1)
                if response.status_code == 200:
                    break
            except requests.RequestException:
                time.sleep(1)
        else:
            pytest.skip("HTTP bridge container failed to start")
        
        yield base_url
        
    finally:
        container.stop()


@pytest.fixture
def sample_mcp_http_request():
    """Provide sample MCP HTTP request data."""
    return {
        "id": "test-request",
        "method": "list_tools",
        "params": {}
    }


@pytest.fixture
def sample_mcp_call_tool_request():
    """Provide sample MCP call_tool HTTP request data."""
    return {
        "id": "test-call-tool",
        "method": "call_tool",
        "name": "disk_space",
        "args": {"path": "/"}
    }


@pytest.fixture
def sample_mcp_call_tool_params_request():
    """Provide sample MCP call_tool HTTP request in params format."""
    return {
        "id": "test-call-tool-params",
        "method": "call_tool",
        "params": {
            "name": "disk_space",
            "args": {"path": "/"}
        }
    }


@pytest.fixture
def mock_http_bridge_config(monkeypatch):
    """Set up mock configuration for HTTP bridge testing."""
    test_dir = Path(__file__).parent
    
    # Mock configuration values for HTTP bridge
    config_values = {
        "server_name": "test-burly-mcp",
        "server_version": "0.0.1-test",
        "host": "0.0.0.0",
        "port": 9400,
        "log_level": "DEBUG",
        "policy_file": str(test_dir / "fixtures" / "test_policy.yaml"),
        "audit_enabled": True,
        "notifications_enabled": False,
        "docker_socket": "/var/run/docker.sock",
        "blog_stage_root": str(test_dir / "fixtures" / "blog_stage"),
        "blog_publish_root": str(test_dir / "fixtures" / "blog_publish"),
        "strict_security_mode": True,
        "gotify_url": "",
        "gotify_token": "",
    }
    
    # Mock the load_runtime_config function
    def mock_load_config():
        return config_values
    
    monkeypatch.setattr("http_bridge.load_runtime_config", mock_load_config)
    
    return config_values


@pytest.fixture
def mock_mcp_engine_response():
    """Provide mock MCP engine response for testing."""
    return {
        "ok": True,
        "summary": "Operation completed successfully",
        "data": {
            "tools": [
                {
                    "name": "disk_space",
                    "description": "Check disk space usage",
                    "args_schema": {
                        "type": "object",
                        "properties": {
                            "path": {"type": "string", "description": "Path to check"}
                        },
                        "required": ["path"]
                    }
                }
            ]
        },
        "metrics": {
            "elapsed_ms": 150,
            "exit_code": 0
        }
    }


@pytest.fixture
def mock_mcp_engine_error_response():
    """Provide mock MCP engine error response for testing."""
    return {
        "ok": False,
        "summary": "Tool execution failed",
        "error": "Tool 'nonexistent_tool' not found",
        "metrics": {
            "elapsed_ms": 50,
            "exit_code": 1
        }
    }


# HTTP Bridge Test Markers
def pytest_configure(config):
    """Configure pytest with HTTP bridge test markers."""
    # Add HTTP bridge specific markers
    config.addinivalue_line("markers", "http: Tests for HTTP bridge functionality")
    config.addinivalue_line("markers", "api: Tests for HTTP API endpoints")
    config.addinivalue_line("markers", "container: Tests for runtime container")


def pytest_collection_modifyitems(config, items):
    """Automatically mark tests based on their location and content."""
    for item in items:
        # Existing markers
        if "unit" in str(item.fspath):
            item.add_marker(pytest.mark.unit)
        elif "integration" in str(item.fspath):
            item.add_marker(pytest.mark.integration)

        # Mark Docker-related tests
        if "docker" in str(item.fspath) or "docker" in item.name.lower():
            item.add_marker(pytest.mark.docker)

        # Mark slow tests
        if "integration" in str(item.fspath):
            item.add_marker(pytest.mark.slow)
        
        # New HTTP bridge markers
        if "http_bridge" in str(item.fspath) or "http" in item.name.lower():
            item.add_marker(pytest.mark.http)
        
        if "api" in item.name.lower() or "_endpoint" in item.name.lower():
            item.add_marker(pytest.mark.api)
        
        if "container" in item.name.lower() or "runtime" in item.name.lower():
            item.add_marker(pytest.mark.container)