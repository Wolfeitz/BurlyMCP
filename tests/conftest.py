"""
Pytest configuration and shared fixtures for Burly MCP tests.

This module provides common test fixtures and configuration for both
unit and integration tests.
"""

import os
import tempfile
from pathlib import Path
from typing import Dict, Any
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
    return {
        "method": "call_tool",
        "name": "disk_space",
        "args": {}
    }


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
        elapsed_ms=100
    )


# Test markers
pytest_plugins = []

def pytest_configure(config):
    """Configure pytest with custom markers."""
    config.addinivalue_line(
        "markers", "unit: mark test as a unit test"
    )
    config.addinivalue_line(
        "markers", "integration: mark test as an integration test"
    )
    config.addinivalue_line(
        "markers", "docker: mark test as requiring Docker"
    )
    config.addinivalue_line(
        "markers", "slow: mark test as slow running"
    )


@pytest.fixture(scope="session")
def docker_available():
    """Check if Docker is available for testing."""
    import subprocess
    try:
        result = subprocess.run(
            ["docker", "version"], 
            capture_output=True, 
            timeout=5
        )
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
    mutates: false
    requires_confirm: false
    timeout_sec: 10
    notify_on: ["success", "failure"]
    schema:
      type: "object"
      properties:
        test_param:
          type: "string"
          description: "Test parameter"
      required: []
      additionalProperties: false

  confirm_tool:
    description: "Tool requiring confirmation"
    mutates: true
    requires_confirm: true
    timeout_sec: 15
    notify_on: ["success", "failure", "confirmation"]
    schema:
      type: "object"
      properties: {}
      required: []
      additionalProperties: false

config:
  output_truncate_limit: 1024
  default_timeout_sec: 30
  max_timeout_sec: 300
  security:
    enable_path_validation: true
    allowed_paths: ["/tmp", "/var/tmp"]
"""


@pytest.fixture
def test_policy_file(temp_dir):
    """Create temporary policy files for testing."""
    def _create_policy_file(filename: str, content: str):
        policy_file = temp_dir / filename
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
    
    # Mock audit logging - patch where it's imported
    monkeypatch.setattr("burly_mcp.tools.registry.log_tool_execution", mock_audit)
    monkeypatch.setattr("burly_mcp.audit.get_audit_logger", Mock())
    
    # Mock notifications - patch where they're imported
    monkeypatch.setattr("burly_mcp.tools.registry.notify_tool_success", mock_notify_success)
    monkeypatch.setattr("burly_mcp.tools.registry.notify_tool_failure", mock_notify_failure)
    monkeypatch.setattr("burly_mcp.tools.registry.notify_tool_confirmation", mock_notify_confirmation)
    
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