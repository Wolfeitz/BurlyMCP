"""
Pytest configuration and shared fixtures for Burly MCP tests.

This module provides common test fixtures and configuration for both
unit and integration tests.
"""

import os
import tempfile
from pathlib import Path
from typing import Dict, Any, Generator
from unittest.mock import Mock, patch
import pytest


@pytest.fixture
def temp_dir():
    """Create a temporary directory for test files."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def mock_env_vars():
    """Provide mock environment variables for testing."""
    return {
        "LOG_LEVEL": "DEBUG",
        "LOG_DIR": "/tmp/test_logs",
        "POLICY_FILE": "tests/fixtures/test_policy.yaml",
        "BLOG_STAGE_ROOT": "/tmp/test_blog_stage",
        "BLOG_PUBLISH_ROOT": "/tmp/test_blog_publish",
        "DEFAULT_TIMEOUT_SEC": "10",
        "OUTPUT_TRUNCATE_LIMIT": "1024",
        "AUDIT_LOG_DIR": "/tmp/test_logs",
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
    import tempfile
    import os

    def _create_policy_file(filename: str, content: str):
        # Create file in current directory to avoid path traversal issues
        policy_file = Path(filename)
        policy_file.write_text(content)
        return policy_file

    return _create_policy_file


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
        monkeypatch.setattr("burly_mcp.tools.registry.log_tool_execution", mock_audit)
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
            "burly_mcp.tools.registry.notify_tool_confirmation", mock_notify_confirmation
        )
    except (ImportError, AttributeError):
        pass  # Module not available, skip mocking

    # Set test-friendly environment variables
    monkeypatch.setenv("AUDIT_LOG_DIR", "/tmp/test_logs")
    monkeypatch.setenv("NOTIFICATIONS_ENABLED", "false")

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
    
    config = Mock()
    config.config_dir = Path("/tmp/test_config")
    config.policy_file = Path("/tmp/test_config/policy/tools.yaml")
    config.log_dir = Path("/tmp/test_logs")
    config.docker_socket = "/var/run/docker.sock"
    config.docker_timeout = 30
    config.max_output_size = 1048576
    config.audit_enabled = True
    config.gotify_url = None
    config.gotify_token = None
    config.blog_stage_root = Path("/tmp/test_blog_stage")
    config.blog_publish_root = Path("/tmp/test_blog_publish")
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
    policy_file.write_text("""
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
""")
    
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
