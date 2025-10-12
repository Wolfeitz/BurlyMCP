"""
Pytest Configuration and Fixtures

This module provides common test fixtures and configuration
for the Burly MCP server test suite.
"""

import pytest
import tempfile
import os
from pathlib import Path
from typing import Generator


@pytest.fixture
def temp_dir() -> Generator[Path, None, None]:
    """
    Provide a temporary directory for test files.
    
    Yields:
        Path to a temporary directory that is cleaned up after the test
    """
    with tempfile.TemporaryDirectory() as temp_path:
        yield Path(temp_path)


@pytest.fixture
def sample_policy_yaml() -> str:
    """
    Provide sample policy YAML content for testing.
    
    Returns:
        YAML content string for policy configuration
    """
    return """
tools:
  test_tool:
    description: "Test tool for unit tests"
    args_schema:
      type: "object"
      properties:
        message:
          type: "string"
      required: ["message"]
    command: ["echo", "{message}"]
    mutates: false
    requires_confirm: false
    timeout_sec: 10
    notify: ["failure"]

config:
  output_truncate_limit: 1024
  default_timeout_sec: 30
"""


@pytest.fixture
def mock_environment(monkeypatch) -> None:
    """
    Set up mock environment variables for testing.
    
    Args:
        monkeypatch: Pytest monkeypatch fixture
    """
    # Mock Gotify configuration
    monkeypatch.setenv("GOTIFY_ENABLED", "false")
    monkeypatch.setenv("GOTIFY_URL", "http://localhost:8080")
    monkeypatch.setenv("GOTIFY_TOKEN", "test_token")
    
    # Mock paths
    monkeypatch.setenv("BLOG_STAGE_ROOT", "/tmp/blog/stage")
    monkeypatch.setenv("BLOG_PUBLISH_ROOT", "/tmp/blog/public")
    monkeypatch.setenv("AUDIT_LOG_PATH", "/tmp/audit.jsonl")