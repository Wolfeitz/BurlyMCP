"""
Integration tests for MCP protocol functionality.
"""

import json
import os
import subprocess
import time

import pytest


@pytest.fixture
def mcp_server_config(tmp_path):
    """Create MCP server configuration for testing."""
    config_dir = tmp_path / "config"
    config_dir.mkdir()

    policy_dir = config_dir / "policy"
    policy_dir.mkdir()

    # Create comprehensive test policy
    policy_content = """
tools:
  echo_test:
    description: "Echo test command for integration testing"
    args_schema:
      type: "object"
      properties:
        message:
          type: "string"
          description: "Message to echo"
      required: ["message"]
      additionalProperties: false
    command: ["echo"]
    mutates: false
    requires_confirm: false
    timeout_sec: 10
    notify: ["success"]

  sleep_test:
    description: "Sleep command for timeout testing"
    args_schema:
      type: "object"
      properties:
        seconds:
          type: "integer"
          description: "Seconds to sleep"
          minimum: 1
          maximum: 5
      required: ["seconds"]
      additionalProperties: false
    command: ["sleep"]
    mutates: false
    requires_confirm: false
    timeout_sec: 10
    notify: ["success", "failure"]

  confirm_test:
    description: "Test command requiring confirmation"
    args_schema:
      type: "object"
      properties:
        action:
          type: "string"
          description: "Action to perform"
      required: ["action"]
      additionalProperties: false
    command: ["echo", "Confirmed:"]
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

    policy_file = policy_dir / "tools.yaml"
    policy_file.write_text(policy_content)

    return config_dir


@pytest.fixture
def mcp_server_process(mcp_server_config):
    """Start MCP server process for integration testing."""
    # This would start the actual Burly MCP server
    # For now, we'll mock this or skip if not available

    env = os.environ.copy()
    env.update(
        {
            "BURLY_CONFIG_DIR": str(mcp_server_config),
            "BURLY_LOG_DIR": str(mcp_server_config / "logs"),
            "NOTIFICATIONS_ENABLED": "false",
            "AUDIT_ENABLED": "true",
        }
    )

    try:
        # Try to start the server
        process = subprocess.Popen(
            ["python", "-m", "burly_mcp.server.main"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=env,
            text=True,
        )

        # Give server time to start
        time.sleep(1)

        if process.poll() is not None:
            # Server failed to start
            stdout, stderr = process.communicate()
            pytest.skip(f"MCP server failed to start: {stderr}")

        yield process

    except FileNotFoundError:
        pytest.skip("Burly MCP server not available for integration testing")
    finally:
        if "process" in locals():
            process.terminate()
            process.wait(timeout=5)


@pytest.mark.integration
@pytest.mark.mcp
class TestMCPProtocolIntegration:
    """Integration tests for MCP protocol end-to-end functionality."""

    def test_mcp_list_tools_request(self, mcp_server_process):
        """Test MCP list_tools request."""
        request = {"method": "list_tools"}

        # Send request
        mcp_server_process.stdin.write(json.dumps(request) + "\n")
        mcp_server_process.stdin.flush()

        # Read response
        response_line = mcp_server_process.stdout.readline()
        response = json.loads(response_line)

        assert response["ok"] is True
        assert "tools" in response
        assert len(response["tools"]) > 0

        # Check for expected tools
        tool_names = [tool["name"] for tool in response["tools"]]
        assert "echo_test" in tool_names
        assert "sleep_test" in tool_names
        assert "confirm_test" in tool_names

    def test_mcp_call_tool_success(self, mcp_server_process):
        """Test successful MCP call_tool request."""
        request = {
            "method": "call_tool",
            "name": "echo_test",
            "args": {"message": "Hello Integration Test"},
        }

        # Send request
        mcp_server_process.stdin.write(json.dumps(request) + "\n")
        mcp_server_process.stdin.flush()

        # Read response
        response_line = mcp_server_process.stdout.readline()
        response = json.loads(response_line)

        assert response["ok"] is True
        assert "Hello Integration Test" in response["stdout"]
        assert response["metrics"]["exit_code"] == 0

    def test_mcp_call_tool_with_validation_error(self, mcp_server_process):
        """Test MCP call_tool with validation error."""
        request = {
            "method": "call_tool",
            "name": "echo_test",
            "args": {},  # Missing required 'message' parameter
        }

        # Send request
        mcp_server_process.stdin.write(json.dumps(request) + "\n")
        mcp_server_process.stdin.flush()

        # Read response
        response_line = mcp_server_process.stdout.readline()
        response = json.loads(response_line)

        assert response["ok"] is False
        assert (
            "validation" in response["error"].lower()
            or "required" in response["error"].lower()
        )

    def test_mcp_call_nonexistent_tool(self, mcp_server_process):
        """Test calling nonexistent tool."""
        request = {"method": "call_tool", "name": "nonexistent_tool", "args": {}}

        # Send request
        mcp_server_process.stdin.write(json.dumps(request) + "\n")
        mcp_server_process.stdin.flush()

        # Read response
        response_line = mcp_server_process.stdout.readline()
        response = json.loads(response_line)

        assert response["ok"] is False
        assert (
            "not found" in response["error"].lower()
            or "unknown" in response["error"].lower()
        )

    def test_mcp_tool_requiring_confirmation(self, mcp_server_process):
        """Test tool that requires confirmation."""
        request = {
            "method": "call_tool",
            "name": "confirm_test",
            "args": {"action": "dangerous_operation"},
        }

        # Send request
        mcp_server_process.stdin.write(json.dumps(request) + "\n")
        mcp_server_process.stdin.flush()

        # Read response
        response_line = mcp_server_process.stdout.readline()
        response = json.loads(response_line)

        # Should indicate confirmation needed
        assert response["ok"] is False or "confirm" in response.get("error", "").lower()

    def test_mcp_invalid_json_request(self, mcp_server_process):
        """Test handling of invalid JSON request."""
        invalid_request = "{ invalid json }"

        # Send invalid request
        mcp_server_process.stdin.write(invalid_request + "\n")
        mcp_server_process.stdin.flush()

        # Read response
        response_line = mcp_server_process.stdout.readline()
        response = json.loads(response_line)

        assert response["ok"] is False
        assert (
            "json" in response["error"].lower()
            or "invalid" in response["error"].lower()
        )

    def test_mcp_unsupported_method(self, mcp_server_process):
        """Test unsupported method request."""
        request = {"method": "unsupported_method"}

        # Send request
        mcp_server_process.stdin.write(json.dumps(request) + "\n")
        mcp_server_process.stdin.flush()

        # Read response
        response_line = mcp_server_process.stdout.readline()
        response = json.loads(response_line)

        assert response["ok"] is False
        assert (
            "unsupported" in response["error"].lower()
            or "unknown" in response["error"].lower()
        )

    @pytest.mark.slow
    def test_mcp_tool_timeout_handling(self, mcp_server_process):
        """Test tool timeout handling."""
        request = {
            "method": "call_tool",
            "name": "sleep_test",
            "args": {"seconds": 15},  # Longer than timeout_sec in policy
        }

        # Send request
        mcp_server_process.stdin.write(json.dumps(request) + "\n")
        mcp_server_process.stdin.flush()

        # Read response (should come back with timeout error)
        response_line = mcp_server_process.stdout.readline()
        response = json.loads(response_line)

        assert response["ok"] is False
        assert "timeout" in response["error"].lower()

    def test_mcp_multiple_sequential_requests(self, mcp_server_process):
        """Test multiple sequential MCP requests."""
        requests_and_responses = []

        # Send multiple requests
        for i in range(3):
            request = {
                "method": "call_tool",
                "name": "echo_test",
                "args": {"message": f"Test message {i}"},
            }

            mcp_server_process.stdin.write(json.dumps(request) + "\n")
            mcp_server_process.stdin.flush()

            # Read response
            response_line = mcp_server_process.stdout.readline()
            response = json.loads(response_line)

            requests_and_responses.append((request, response))

        # Verify all responses
        for i, (request, response) in enumerate(requests_and_responses):
            assert response["ok"] is True
            assert f"Test message {i}" in response["stdout"]

    def test_mcp_server_error_recovery(self, mcp_server_process):
        """Test server error recovery."""
        # Send a request that causes an error
        error_request = {"method": "call_tool", "name": "nonexistent_tool", "args": {}}

        mcp_server_process.stdin.write(json.dumps(error_request) + "\n")
        mcp_server_process.stdin.flush()

        error_response_line = mcp_server_process.stdout.readline()
        error_response = json.loads(error_response_line)
        assert error_response["ok"] is False

        # Send a valid request after the error
        valid_request = {
            "method": "call_tool",
            "name": "echo_test",
            "args": {"message": "Recovery test"},
        }

        mcp_server_process.stdin.write(json.dumps(valid_request) + "\n")
        mcp_server_process.stdin.flush()

        valid_response_line = mcp_server_process.stdout.readline()
        valid_response = json.loads(valid_response_line)

        # Server should recover and handle valid request
        assert valid_response["ok"] is True
        assert "Recovery test" in valid_response["stdout"]


@pytest.mark.integration
@pytest.mark.mcp
class TestMCPProtocolStressTest:
    """Stress tests for MCP protocol."""

    @pytest.mark.slow
    def test_mcp_rapid_requests(self, mcp_server_process):
        """Test rapid succession of MCP requests."""
        num_requests = 10
        responses = []

        # Send requests rapidly
        for i in range(num_requests):
            request = {
                "method": "call_tool",
                "name": "echo_test",
                "args": {"message": f"Rapid test {i}"},
            }

            mcp_server_process.stdin.write(json.dumps(request) + "\n")
            mcp_server_process.stdin.flush()

        # Read all responses
        for i in range(num_requests):
            response_line = mcp_server_process.stdout.readline()
            response = json.loads(response_line)
            responses.append(response)

        # Verify all responses
        assert len(responses) == num_requests
        for i, response in enumerate(responses):
            assert response["ok"] is True
            assert f"Rapid test {i}" in response["stdout"]

    @pytest.mark.slow
    @pytest.mark.flaky
    def test_mcp_concurrent_simulation(self, mcp_server_config):
        """Simulate concurrent MCP requests (multiple server instances)."""
        # This would test multiple server instances handling requests
        # For now, we'll test sequential requests with different configurations

        processes = []
        try:
            # Start multiple server processes
            for i in range(2):
                env = os.environ.copy()
                env.update(
                    {
                        "BURLY_CONFIG_DIR": str(mcp_server_config),
                        "BURLY_LOG_DIR": str(mcp_server_config / f"logs_{i}"),
                        "NOTIFICATIONS_ENABLED": "false",
                    }
                )

                process = subprocess.Popen(
                    ["python", "-m", "burly_mcp.server.main"],
                    stdin=subprocess.PIPE,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    env=env,
                    text=True,
                )
                processes.append(process)
                time.sleep(0.5)  # Stagger startup

            # Send requests to each process
            for i, process in enumerate(processes):
                if process.poll() is None:  # Process is running
                    request = {
                        "method": "call_tool",
                        "name": "echo_test",
                        "args": {"message": f"Concurrent test {i}"},
                    }

                    process.stdin.write(json.dumps(request) + "\n")
                    process.stdin.flush()

                    response_line = process.stdout.readline()
                    response = json.loads(response_line)

                    assert response["ok"] is True
                    assert f"Concurrent test {i}" in response["stdout"]

        except FileNotFoundError:
            pytest.skip("Burly MCP server not available")
        finally:
            for process in processes:
                if process.poll() is None:
                    process.terminate()
                    process.wait(timeout=5)


@pytest.mark.integration
@pytest.mark.mcp
class TestMCPProtocolSecurity:
    """Security-focused MCP protocol integration tests."""

    def test_mcp_path_traversal_protection(self, mcp_server_process):
        """Test protection against path traversal attacks."""
        # This would test tools that handle file paths
        # and ensure path traversal attacks are blocked
        pass

    def test_mcp_command_injection_protection(self, mcp_server_process):
        """Test protection against command injection."""
        # This would test that command arguments are properly sanitized
        pass

    def test_mcp_resource_limit_enforcement(self, mcp_server_process):
        """Test that resource limits are enforced."""
        # This would test memory and CPU limits during tool execution
        pass

    def test_mcp_audit_logging(self, mcp_server_config, mcp_server_process):
        """Test that audit logging works correctly."""
        request = {
            "method": "call_tool",
            "name": "echo_test",
            "args": {"message": "Audit test"},
        }

        # Send request
        mcp_server_process.stdin.write(json.dumps(request) + "\n")
        mcp_server_process.stdin.flush()

        # Read response
        response_line = mcp_server_process.stdout.readline()
        response = json.loads(response_line)

        assert response["ok"] is True

        # Check that audit log was created
        log_dir = mcp_server_config / "logs"
        if log_dir.exists():
            audit_files = list(log_dir.glob("*audit*"))
            # If audit logging is implemented, there should be audit files
            # This is a placeholder for when audit logging is fully implemented


@pytest.mark.integration
@pytest.mark.mcp
class TestMCPProtocolConfiguration:
    """Test MCP protocol with different configurations."""

    def test_mcp_with_minimal_config(self, tmp_path):
        """Test MCP server with minimal configuration."""
        config_dir = tmp_path / "minimal_config"
        config_dir.mkdir()

        policy_dir = config_dir / "policy"
        policy_dir.mkdir()

        # Minimal policy
        minimal_policy = """
tools:
  basic_echo:
    description: "Basic echo"
    args_schema:
      type: "object"
      properties: {}
      required: []
      additionalProperties: false
    command: ["echo", "basic"]
    mutates: false
    requires_confirm: false
    timeout_sec: 5

config:
  output_truncate_limit: 512
  default_timeout_sec: 10
"""

        policy_file = policy_dir / "tools.yaml"
        policy_file.write_text(minimal_policy)

        # Test with minimal config
        # This would start a server with minimal configuration
        # and verify it works correctly

    def test_mcp_with_security_config(self, tmp_path):
        """Test MCP server with enhanced security configuration."""
        config_dir = tmp_path / "security_config"
        config_dir.mkdir()

        policy_dir = config_dir / "policy"
        policy_dir.mkdir()

        # Security-focused policy
        security_policy = """
tools:
  secure_echo:
    description: "Secure echo with validation"
    args_schema:
      type: "object"
      properties:
        message:
          type: "string"
          pattern: "^[a-zA-Z0-9\\s]+$"  # Only alphanumeric and spaces
          maxLength: 100
      required: ["message"]
      additionalProperties: false
    command: ["echo"]
    mutates: false
    requires_confirm: false
    timeout_sec: 5

config:
  output_truncate_limit: 256
  default_timeout_sec: 5
  security:
    enable_path_validation: true
    allowed_paths: ["/tmp"]
    max_output_size: 1024
"""

        policy_file = policy_dir / "tools.yaml"
        policy_file.write_text(security_policy)

        # Test with security config
        # This would verify security features work correctly
