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
        "AUDIT_LOG_PATH": "/tmp/test_audit.jsonl",
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