#!/usr/bin/env python3
"""
Test Configuration for Burly MCP

This module provides configuration management for testing that works
across different environments without hardcoded local paths.
"""

import os
import tempfile
from pathlib import Path
from typing import Dict, Optional


class TestConfig:
    """Manages test configuration in a portable way."""
    
    def __init__(self, base_dir: Optional[str] = None):
        """
        Initialize test configuration.
        
        Args:
            base_dir: Base directory for test files (defaults to current directory)
        """
        self.base_dir = Path(base_dir or os.getcwd())
        self.temp_dir = None
        
    def setup_test_environment(self, use_temp_dirs: bool = False) -> Dict[str, str]:
        """
        Set up test environment variables.
        
        Args:
            use_temp_dirs: Whether to use temporary directories for isolation
            
        Returns:
            Dictionary of environment variables to set
        """
        if use_temp_dirs:
            self.temp_dir = tempfile.mkdtemp(prefix="burly_mcp_test_")
            base_path = Path(self.temp_dir)
        else:
            base_path = self.base_dir
        
        # Create necessary directories
        log_dir = base_path / "logs"
        blog_stage = base_path / "test_data" / "blog" / "stage"
        blog_publish = base_path / "test_data" / "blog" / "publish"
        
        log_dir.mkdir(parents=True, exist_ok=True)
        blog_stage.mkdir(parents=True, exist_ok=True)
        blog_publish.mkdir(parents=True, exist_ok=True)
        
        # Create test blog post if it doesn't exist
        test_post = blog_stage / "test-post.md"
        if not test_post.exists():
            test_post.write_text("""---
title: "Test Blog Post"
date: "2024-01-15"
author: "Test Author"
tags: ["test", "demo"]
---

# Test Blog Post

This is a test blog post for validating the Burly MCP server functionality.

## Content

- Test content validation
- YAML front-matter parsing
- Markdown processing

The post includes proper front-matter and valid Markdown content for testing purposes.
""")
        
        return {
            "LOG_DIR": str(log_dir),
            "LOG_LEVEL": "INFO",
            "POLICY_FILE": str(self.base_dir / "policy" / "tools.yaml"),
            "BLOG_STAGE_ROOT": str(blog_stage),
            "BLOG_PUBLISH_ROOT": str(blog_publish),
            "DEFAULT_TIMEOUT_SEC": "30",
            "OUTPUT_TRUNCATE_LIMIT": "10240",
            "AUDIT_LOG_PATH": str(log_dir / "audit.jsonl"),
            "AUDIT_LOG_DIR": str(log_dir),
            "NOTIFICATIONS_ENABLED": "false",
            "GOTIFY_URL": "",
            "GOTIFY_TOKEN": "",
            "SERVER_NAME": "burly-mcp",
            "SERVER_VERSION": "0.1.0"
        }
    
    def setup_mock_environment(self, mock_gotify_url: str) -> Dict[str, str]:
        """
        Set up environment for testing with mock services.
        
        Args:
            mock_gotify_url: URL of the mock Gotify server
            
        Returns:
            Dictionary of environment variables to set
        """
        env = self.setup_test_environment()
        env.update({
            "NOTIFICATIONS_ENABLED": "true",
            "GOTIFY_URL": mock_gotify_url,
            "GOTIFY_TOKEN": "test-token-12345"
        })
        return env
    
    def cleanup(self):
        """Clean up temporary directories if created."""
        if self.temp_dir and os.path.exists(self.temp_dir):
            import shutil
            shutil.rmtree(self.temp_dir)
    
    def get_expected_responses(self) -> Dict[str, Dict]:
        """
        Get expected responses that work across different environments.
        
        Returns:
            Dictionary of expected responses for different scenarios
        """
        return {
            "docker_available": {
                "summary_contains": ["Found", "containers"],
                "ok": True
            },
            "docker_unavailable": {
                "summary_contains": ["Docker", "not available", "command not found"],
                "ok": False
            },
            "gotify_configured": {
                "summary_contains": ["notification", "sent", "success"],
                "ok": True
            },
            "gotify_not_configured": {
                "summary_contains": ["not configured", "URL", "environment"],
                "ok": False
            },
            "gotify_unreachable": {
                "summary_contains": ["endpoint", "not found", "network", "connection"],
                "ok": False
            },
            "blog_validation_success": {
                "summary_contains": ["validation passed", "front-matter"],
                "ok": True
            },
            "blog_path_traversal": {
                "summary_contains": ["Path traversal", "detected", "outside"],
                "ok": False
            },
            "blog_publish_needs_confirm": {
                "summary_contains": ["confirmation", "required", "publishing"],
                "ok": False
            },
            "list_tools_success": {
                "summary_contains": ["tools found", "Available"],
                "ok": True
            }
        }


def main():
    """Demonstrate test configuration setup."""
    config = TestConfig()
    
    print("=== Test Configuration Demo ===\n")
    
    # Show basic environment setup
    env = config.setup_test_environment()
    print("Basic Test Environment:")
    for key, value in env.items():
        print(f"  {key}={value}")
    
    print("\n" + "="*50)
    
    # Show mock environment setup
    mock_env = config.setup_mock_environment("http://127.0.0.1:9999")
    print("\nMock Service Environment:")
    for key, value in mock_env.items():
        if key in ["NOTIFICATIONS_ENABLED", "GOTIFY_URL", "GOTIFY_TOKEN"]:
            print(f"  {key}={value}")
    
    print("\n" + "="*50)
    
    # Show expected responses
    responses = config.get_expected_responses()
    print("\nExpected Response Patterns:")
    for scenario, expected in responses.items():
        print(f"  {scenario}:")
        print(f"    ok: {expected['ok']}")
        print(f"    summary_contains: {expected['summary_contains']}")
    
    config.cleanup()


if __name__ == "__main__":
    main()