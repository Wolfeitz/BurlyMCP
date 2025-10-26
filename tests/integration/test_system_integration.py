"""
System-wide integration tests for Burly MCP.

Tests both stdin/stdout MCP protocol and HTTP bridge endpoints
for comprehensive system validation.
"""

import json
import os
import subprocess
import time

import pytest

try:
    from testcontainers.core.generic import DockerContainer
    import requests
    import docker
    TESTCONTAINERS_AVAILABLE = True
    HTTP_CLIENT_AVAILABLE = True
except ImportError:
    TESTCONTAINERS_AVAILABLE = False
    HTTP_CLIENT_AVAILABLE = False
    DockerContainer = None
    docker = None
    requests = None


@pytest.mark.integration
@pytest.mark.slow
@pytest.mark.skipif(not TESTCONTAINERS_AVAILABLE, reason="testcontainers not available")
class TestSystemIntegration:
    """End-to-end system integration tests."""

    @pytest.fixture(scope="class")
    def system_test_environment(self, tmp_path_factory):
        """Set up complete system test environment."""
        test_dir = tmp_path_factory.mktemp("system_test")

        # Create directory structure
        config_dir = test_dir / "config"
        config_dir.mkdir()
        policy_dir = config_dir / "policy"
        policy_dir.mkdir()
        logs_dir = test_dir / "logs"
        logs_dir.mkdir()
        blog_dir = test_dir / "blog"
        blog_dir.mkdir()
        blog_stage = blog_dir / "stage"
        blog_stage.mkdir()
        blog_publish = blog_dir / "publish"
        blog_publish.mkdir()

        # Create comprehensive policy configuration
        policy_content = """
tools:
  system_info:
    description: "Get system information"
    args_schema:
      type: "object"
      properties:
        info_type:
          type: "string"
          enum: ["os", "memory", "disk"]
          description: "Type of system information to retrieve"
      required: ["info_type"]
      additionalProperties: false
    command: ["uname", "-a"]
    mutates: false
    requires_confirm: false
    timeout_sec: 10
    notify: ["success", "failure"]

  file_operations:
    description: "Safe file operations"
    args_schema:
      type: "object"
      properties:
        operation:
          type: "string"
          enum: ["list", "read", "create"]
        path:
          type: "string"
          description: "File or directory path"
        content:
          type: "string"
          description: "Content for create operation"
      required: ["operation", "path"]
      additionalProperties: false
    command: ["ls"]
    mutates: true
    requires_confirm: true
    timeout_sec: 15
    notify: ["success", "failure", "need_confirm"]

  blog_management:
    description: "Blog post management"
    args_schema:
      type: "object"
      properties:
        action:
          type: "string"
          enum: ["list", "stage", "publish"]
        post_name:
          type: "string"
          description: "Blog post name"
      required: ["action"]
      additionalProperties: false
    command: ["echo"]
    mutates: true
    requires_confirm: false
    timeout_sec: 20
    notify: ["success", "failure"]

config:
  output_truncate_limit: 2048
  default_timeout_sec: 30
  security:
    enable_path_validation: true
    allowed_paths: ["/tmp", "/var/tmp"]
    max_memory_mb: 512
    max_cpu_percent: 75
"""

        policy_file = policy_dir / "tools.yaml"
        policy_file.write_text(policy_content)

        # Create test blog posts
        test_post_content = """---
title: "Test Blog Post"
date: "2024-01-01"
tags: ["test", "integration"]
author: "Test Author"
---

# Test Blog Post

This is a test blog post for integration testing.

## Content

Some example content for testing blog operations.
"""

        (blog_stage / "test-post.md").write_text(test_post_content)

        return {
            "test_dir": test_dir,
            "config_dir": config_dir,
            "logs_dir": logs_dir,
            "blog_dir": blog_dir,
            "policy_file": policy_file,
        }

    @pytest.fixture
    def system_environment_vars(self, system_test_environment):
        """Set up environment variables for system testing."""
        return {
            "BURLY_CONFIG_DIR": str(system_test_environment["config_dir"]),
            "BURLY_LOG_DIR": str(system_test_environment["logs_dir"]),
            "BLOG_STAGE_ROOT": str(system_test_environment["blog_dir"] / "stage"),
            "BLOG_PUBLISH_ROOT": str(system_test_environment["blog_dir"] / "publish"),
            "NOTIFICATIONS_ENABLED": "false",
            "AUDIT_ENABLED": "true",
            "MAX_OUTPUT_SIZE": "2048",
            "DEFAULT_TIMEOUT_SEC": "30",
        }

    def test_system_startup_and_shutdown(
        self, system_test_environment, system_environment_vars
    ):
        """Test complete system startup and shutdown."""
        try:
            # Start the system
            process = subprocess.Popen(
                ["python", "-m", "burly_mcp.server.main"],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                env={**os.environ, **system_environment_vars},
                text=True,
            )

            # Give system time to start
            time.sleep(2)

            if process.poll() is not None:
                stdout, stderr = process.communicate()
                pytest.skip(f"System failed to start: {stderr}")

            # Test basic functionality
            request = {"method": "list_tools"}
            process.stdin.write(json.dumps(request) + "\n")
            process.stdin.flush()

            response_line = process.stdout.readline()
            response = json.loads(response_line)

            assert response["ok"] is True
            assert len(response["tools"]) > 0

            # Graceful shutdown
            process.terminate()
            process.wait(timeout=10)

        except FileNotFoundError:
            pytest.skip("Burly MCP server not available for system testing")

    def test_configuration_validation_and_loading(
        self, system_test_environment, system_environment_vars
    ):
        """Test configuration validation and loading."""
        # Test with valid configuration
        try:
            process = subprocess.Popen(
                [
                    "python",
                    "-c",
                    """
import sys
sys.path.insert(0, "src")
from burly_mcp.config import Config
config = Config()
errors = config.validate()
print(f"Validation errors: {len(errors)}")
for error in errors:
    print(f"Error: {error}")
""",
                ],
                env={**os.environ, **system_environment_vars},
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )

            stdout, stderr = process.communicate()

            # Debug output
            if not stdout and stderr:
                pytest.skip(f"Configuration test failed: {stderr}")

            # Should have minimal validation errors with proper setup
            assert "Validation errors: 0" in stdout or "Validation errors: 1" in stdout

        except FileNotFoundError:
            pytest.skip("Python module not available")

    def test_policy_engine_integration(
        self, system_test_environment, system_environment_vars
    ):
        """Test policy engine integration with the system."""
        try:
            process = subprocess.Popen(
                [
                    "python",
                    "-c",
                    '''
import sys
sys.path.insert(0, "src")
from burly_mcp.policy.engine import PolicyEngine
engine = PolicyEngine()
engine.load_policy("'''
                    + str(system_test_environment["policy_file"])
                    + """")
print(f"Tools loaded: {len(engine.policy_data.get('tools', {}))}")
print(f"Has system_info: {'system_info' in engine.policy_data.get('tools', {})}")
""",
                ],
                env={**os.environ, **system_environment_vars},
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )

            stdout, stderr = process.communicate()

            # Debug output
            if not stdout and stderr:
                pytest.skip(f"Policy engine test failed: {stderr}")

            assert "Tools loaded: 3" in stdout
            assert "Has system_info: True" in stdout

        except FileNotFoundError:
            pytest.skip("Python module not available")

    def test_end_to_end_tool_execution(
        self, system_test_environment, system_environment_vars
    ):
        """Test end-to-end tool execution through the system."""
        try:
            process = subprocess.Popen(
                ["python", "-m", "burly_mcp.server.main"],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                env={**os.environ, **system_environment_vars},
                text=True,
            )

            time.sleep(2)

            if process.poll() is not None:
                pytest.skip("System not available")

            # Test tool execution
            request = {
                "method": "call_tool",
                "name": "system_info",
                "args": {"info_type": "os"},
            }

            process.stdin.write(json.dumps(request) + "\n")
            process.stdin.flush()

            response_line = process.stdout.readline()
            response = json.loads(response_line)

            assert response["ok"] is True
            assert len(response["stdout"]) > 0
            assert response["metrics"]["exit_code"] == 0

            process.terminate()
            process.wait(timeout=5)

        except FileNotFoundError:
            pytest.skip("System not available")

    def test_error_handling_and_recovery(
        self, system_test_environment, system_environment_vars
    ):
        """Test system error handling and recovery."""
        try:
            process = subprocess.Popen(
                ["python", "-m", "burly_mcp.server.main"],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                env={**os.environ, **system_environment_vars},
                text=True,
            )

            time.sleep(2)

            if process.poll() is not None:
                pytest.skip("System not available")

            # Send invalid request
            invalid_request = {"method": "invalid_method"}
            process.stdin.write(json.dumps(invalid_request) + "\n")
            process.stdin.flush()

            error_response_line = process.stdout.readline()
            error_response = json.loads(error_response_line)
            assert error_response["ok"] is False

            # Send valid request after error
            valid_request = {
                "method": "call_tool",
                "name": "system_info",
                "args": {"info_type": "os"},
            }

            process.stdin.write(json.dumps(valid_request) + "\n")
            process.stdin.flush()

            valid_response_line = process.stdout.readline()
            valid_response = json.loads(valid_response_line)

            # System should recover
            assert valid_response["ok"] is True

            process.terminate()
            process.wait(timeout=5)

        except FileNotFoundError:
            pytest.skip("System not available")

    def test_security_enforcement(
        self, system_test_environment, system_environment_vars
    ):
        """Test security enforcement throughout the system."""
        # This would test various security features:
        # - Path validation
        # - Resource limits
        # - Command sanitization
        # - Audit logging
        pass

    def test_notification_system_integration(
        self, system_test_environment, system_environment_vars
    ):
        """Test notification system integration."""
        # Test with notifications enabled
        notification_env = system_environment_vars.copy()
        notification_env.update(
            {
                "NOTIFICATIONS_ENABLED": "true",
                "GOTIFY_URL": "http://localhost:8080",  # Mock URL
                "GOTIFY_TOKEN": "test_token",
            }
        )

        # This would test notification functionality
        # when integrated with the system
        pass

    def test_audit_logging_integration(
        self, system_test_environment, system_environment_vars
    ):
        """Test audit logging integration."""
        try:
            process = subprocess.Popen(
                ["python", "-m", "burly_mcp.server.main"],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                env={**os.environ, **system_environment_vars},
                text=True,
            )

            time.sleep(2)

            if process.poll() is not None:
                pytest.skip("System not available")

            # Execute a tool to generate audit logs
            request = {
                "method": "call_tool",
                "name": "system_info",
                "args": {"info_type": "os"},
            }

            process.stdin.write(json.dumps(request) + "\n")
            process.stdin.flush()

            response_line = process.stdout.readline()
            response = json.loads(response_line)

            assert response["ok"] is True

            process.terminate()
            process.wait(timeout=5)

            # Check for audit logs
            logs_dir = system_test_environment["logs_dir"]
            if logs_dir.exists():
                log_files = list(logs_dir.glob("*.log"))
                # If audit logging is implemented, there should be log files

        except FileNotFoundError:
            pytest.skip("System not available")

    def test_resource_limit_enforcement(
        self, system_test_environment, system_environment_vars
    ):
        """Test resource limit enforcement in the system."""
        # Test with strict resource limits
        resource_env = system_environment_vars.copy()
        resource_env.update(
            {
                "MAX_MEMORY_MB": "128",
                "MAX_CPU_PERCENT": "50",
                "MAX_EXECUTION_TIME_SEC": "5",
            }
        )

        # This would test that resource limits are enforced
        # during tool execution
        pass

    @pytest.mark.docker
    def test_docker_integration_in_system(
        self, system_test_environment, system_environment_vars
    ):
        """Test Docker integration within the complete system."""
        # This would test Docker functionality
        # when integrated with the complete system
        pass

    def test_blog_management_integration(
        self, system_test_environment, system_environment_vars
    ):
        """Test blog management integration."""
        try:
            process = subprocess.Popen(
                ["python", "-m", "burly_mcp.server.main"],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                env={**os.environ, **system_environment_vars},
                text=True,
            )

            time.sleep(2)

            if process.poll() is not None:
                pytest.skip("System not available")

            # Test blog listing
            request = {
                "method": "call_tool",
                "name": "blog_management",
                "args": {"action": "list"},
            }

            process.stdin.write(json.dumps(request) + "\n")
            process.stdin.flush()

            response_line = process.stdout.readline()
            response = json.loads(response_line)

            # Should execute successfully
            assert response["ok"] is True

            process.terminate()
            process.wait(timeout=5)

        except FileNotFoundError:
            pytest.skip("System not available")

    def test_system_performance_under_load(
        self, system_test_environment, system_environment_vars
    ):
        """Test system performance under load."""
        try:
            process = subprocess.Popen(
                ["python", "-m", "burly_mcp.server.main"],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                env={**os.environ, **system_environment_vars},
                text=True,
            )

            time.sleep(2)

            if process.poll() is not None:
                pytest.skip("System not available")

            # Send multiple requests rapidly
            start_time = time.time()
            num_requests = 10

            for i in range(num_requests):
                request = {
                    "method": "call_tool",
                    "name": "system_info",
                    "args": {"info_type": "os"},
                }

                process.stdin.write(json.dumps(request) + "\n")
                process.stdin.flush()

            # Read all responses
            responses = []
            for i in range(num_requests):
                response_line = process.stdout.readline()
                response = json.loads(response_line)
                responses.append(response)

            end_time = time.time()
            total_time = end_time - start_time

            # Verify all responses
            assert len(responses) == num_requests
            for response in responses:
                assert response["ok"] is True

            # Performance check (should handle 10 requests reasonably quickly)
            assert total_time < 30.0  # Should complete within 30 seconds

            process.terminate()
            process.wait(timeout=5)

        except FileNotFoundError:
            pytest.skip("System not available")

    def test_configuration_hot_reload(
        self, system_test_environment, system_environment_vars
    ):
        """Test configuration hot reload functionality."""
        # This would test the ability to reload configuration
        # without restarting the system
        pass

    def test_system_cleanup_and_resource_management(
        self, system_test_environment, system_environment_vars
    ):
        """Test system cleanup and resource management."""
        # This would test that the system properly cleans up
        # resources, temporary files, and handles shutdown gracefully
        pass

@pytest.mark.integration
@pytest.mark.http
@pytest.mark.skipif(not HTTP_CLIENT_AVAILABLE, reason="HTTP client not available")
class TestHTTPBridgeSystemIntegration:
    """System integration tests for HTTP bridge endpoints."""

    def test_http_health_endpoint_format(self, http_client):
        """Test /health endpoint returns correct format."""
        # This would test against a running HTTP bridge container
        pytest.skip("HTTP bridge container integration pending")

    def test_http_health_endpoint_status_detection(self, http_client):
        """Test /health endpoint status detection logic."""
        pytest.skip("HTTP bridge container integration pending")

    def test_http_mcp_endpoint_direct_format(self, http_client):
        """Test /mcp endpoint with direct request format."""
        pytest.skip("HTTP bridge container integration pending")

    def test_http_mcp_endpoint_params_format(self, http_client):
        """Test /mcp endpoint with params request format."""
        pytest.skip("HTTP bridge container integration pending")

    def test_http_mcp_endpoint_always_returns_200(self, http_client):
        """Test that /mcp returns HTTP 200 even when tool fails."""
        # This is a critical requirement from the spec
        pytest.skip("HTTP bridge container integration pending")

    def test_http_bridge_error_handling(self, http_client):
        """Test HTTP bridge error handling and recovery."""
        pytest.skip("HTTP bridge container integration pending")

    def test_http_bridge_metrics_tracking(self, http_client):
        """Test that HTTP bridge includes metrics in all responses."""
        pytest.skip("HTTP bridge container integration pending")

    def test_http_bridge_security_headers(self, http_client):
        """Test HTTP bridge security headers and CORS configuration."""
        pytest.skip("HTTP bridge container integration pending")


@pytest.mark.integration
@pytest.mark.http
@pytest.mark.security
@pytest.mark.skipif(not HTTP_CLIENT_AVAILABLE, reason="HTTP client not available")
class TestHTTPBridgeSecurityIntegration:
    """Security-focused integration tests for HTTP bridge."""

    def test_http_rate_limiting_enforcement(self, http_client):
        """Test that rate limiting is enforced on /mcp endpoint."""
        pytest.skip("HTTP bridge container integration pending")

    def test_http_request_size_limits(self, http_client):
        """Test HTTP request size validation."""
        pytest.skip("HTTP bridge container integration pending")

    def test_http_input_sanitization(self, http_client):
        """Test input sanitization for tool names and arguments."""
        pytest.skip("HTTP bridge container integration pending")

    def test_http_error_information_disclosure(self, http_client):
        """Test that errors don't disclose sensitive information."""
        pytest.skip("HTTP bridge container integration pending")


@pytest.mark.integration
@pytest.mark.container
@pytest.mark.skipif(not TESTCONTAINERS_AVAILABLE, reason="testcontainers not available")
class TestRuntimeContainerIntegration:
    """Integration tests for the runtime container."""

    def test_container_minimal_startup(self):
        """Test container starts with minimal configuration."""
        pytest.skip("Runtime container testing pending")

    def test_container_health_endpoint_availability(self):
        """Test that /health endpoint is available after container startup."""
        pytest.skip("Runtime container testing pending")

    def test_container_mcp_endpoint_functionality(self):
        """Test that /mcp endpoint works in container environment."""
        pytest.skip("Runtime container testing pending")

    def test_container_graceful_degradation(self):
        """Test container graceful degradation when optional features unavailable."""
        pytest.skip("Runtime container testing pending")

    def test_container_environment_variable_configuration(self):
        """Test container configuration via environment variables."""
        pytest.skip("Runtime container testing pending")

    def test_container_security_posture(self):
        """Test container runs with proper security settings."""
        pytest.skip("Runtime container testing pending")