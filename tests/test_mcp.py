"""
Unit tests for the MCP protocol implementation.

This module tests the MCPRequest, MCPResponse, and MCPProtocolHandler classes
to ensure proper request parsing, response formatting, confirmation workflow,
and error handling scenarios.
"""

import json
import pytest
import sys
import time
from io import StringIO
from typing import Dict, Any
from unittest.mock import Mock, patch, MagicMock

from server.mcp import (
    MCPRequest,
    MCPResponse,
    MCPProtocolHandler,
    MCPMethod,
)


class TestMCPRequest:
    """Test cases for MCPRequest class."""

    def test_from_json_valid_list_tools(self):
        """Test parsing valid list_tools request."""
        json_data = {"method": "list_tools"}

        request = MCPRequest.from_json(json_data)

        assert request.method == "list_tools"
        assert request.name is None
        assert request.args == {}

    def test_from_json_valid_call_tool(self):
        """Test parsing valid call_tool request."""
        json_data = {
            "method": "call_tool",
            "name": "docker_ps",
            "args": {"format": "table"},
        }

        request = MCPRequest.from_json(json_data)

        assert request.method == "call_tool"
        assert request.name == "docker_ps"
        assert request.args == {"format": "table"}

    def test_from_json_call_tool_no_args(self):
        """Test parsing call_tool request without args."""
        json_data = {"method": "call_tool", "name": "disk_space"}

        request = MCPRequest.from_json(json_data)

        assert request.method == "call_tool"
        assert request.name == "disk_space"
        assert request.args == {}

    def test_from_json_missing_method(self):
        """Test parsing request with missing method field."""
        json_data = {"name": "test_tool"}

        with pytest.raises(ValueError, match="Missing required field: method"):
            MCPRequest.from_json(json_data)

    def test_from_json_empty_method(self):
        """Test parsing request with empty method field."""
        json_data = {"method": ""}

        with pytest.raises(ValueError, match="Missing required field: method"):
            MCPRequest.from_json(json_data)

    def test_from_json_unsupported_method(self):
        """Test parsing request with unsupported method."""
        json_data = {"method": "unsupported_method"}

        with pytest.raises(ValueError, match="Unsupported method: unsupported_method"):
            MCPRequest.from_json(json_data)

    def test_from_json_null_method(self):
        """Test parsing request with null method field."""
        json_data = {"method": None}

        with pytest.raises(ValueError, match="Missing required field: method"):
            MCPRequest.from_json(json_data)


class TestMCPResponse:
    """Test cases for MCPResponse class."""

    def test_create_success_basic(self):
        """Test creating basic success response."""
        response = MCPResponse.create_success("Operation completed")

        assert response.ok is True
        assert response.summary == "Operation completed"
        assert response.need_confirm is False
        assert response.data is None
        assert response.stdout == ""
        assert response.stderr == ""
        assert response.error is None
        assert response.metrics["elapsed_ms"] == 0
        assert response.metrics["exit_code"] == 0

    def test_create_success_with_data(self):
        """Test creating success response with data."""
        data = {"containers": [{"name": "test", "status": "running"}]}
        response = MCPResponse.create_success(
            "Docker containers listed",
            data=data,
            stdout="Container output",
            stderr="Warning message",
            elapsed_ms=150,
        )

        assert response.ok is True
        assert response.summary == "Docker containers listed"
        assert response.data == data
        assert response.stdout == "Container output"
        assert response.stderr == "Warning message"
        assert response.metrics["elapsed_ms"] == 150
        assert response.metrics["exit_code"] == 0

    def test_create_success_with_confirmation(self):
        """Test creating success response requiring confirmation."""
        response = MCPResponse.create_success(
            "Ready to publish", need_confirm=True, elapsed_ms=50
        )

        assert response.ok is True
        assert response.need_confirm is True
        assert response.summary == "Ready to publish"
        assert response.metrics["elapsed_ms"] == 50

    def test_create_error_basic(self):
        """Test creating basic error response."""
        response = MCPResponse.create_error("Command failed")

        assert response.ok is False
        assert response.error == "Command failed"
        assert response.summary == "Operation failed"
        assert response.need_confirm is False
        assert response.metrics["elapsed_ms"] == 0
        assert response.metrics["exit_code"] == 1

    def test_create_error_with_details(self):
        """Test creating error response with details."""
        response = MCPResponse.create_error(
            "Docker command failed",
            summary="Docker operation failed",
            exit_code=127,
            elapsed_ms=200,
            stderr="docker: command not found",
        )

        assert response.ok is False
        assert response.error == "Docker command failed"
        assert response.summary == "Docker operation failed"
        assert response.stderr == "docker: command not found"
        assert response.metrics["elapsed_ms"] == 200
        assert response.metrics["exit_code"] == 127

    def test_post_init_default_metrics(self):
        """Test post-initialization sets default metrics."""
        response = MCPResponse(ok=True)

        assert "elapsed_ms" in response.metrics
        assert "exit_code" in response.metrics
        assert response.metrics["elapsed_ms"] == 0
        assert response.metrics["exit_code"] == 0

    def test_post_init_preserves_existing_metrics(self):
        """Test post-initialization preserves existing metrics."""
        response = MCPResponse(
            ok=True, metrics={"elapsed_ms": 100, "custom_metric": "value"}
        )

        assert response.metrics["elapsed_ms"] == 100
        assert response.metrics["custom_metric"] == "value"
        assert response.metrics["exit_code"] == 0

    def test_post_init_default_summary(self):
        """Test post-initialization sets default summary."""
        success_response = MCPResponse(ok=True)
        assert success_response.summary == "Operation completed"

        error_response = MCPResponse(ok=False)
        assert error_response.summary == "Operation failed"

    def test_output_truncation(self):
        """Test output truncation for long content."""
        long_output = "x" * 15000  # Exceeds default 10000 limit

        response = MCPResponse(ok=True, stdout=long_output, stderr=long_output)

        # Check truncation occurred
        assert len(response.stdout) < len(long_output)
        assert "[truncated: output too long]" in response.stdout
        assert len(response.stderr) < len(long_output)
        assert "[truncated: output too long]" in response.stderr

        # Check metrics recorded truncation
        assert "stdout_trunc" in response.metrics
        assert "stderr_trunc" in response.metrics

    def test_to_json_success_minimal(self):
        """Test JSON serialization of minimal success response."""
        response = MCPResponse.create_success("Test completed")
        json_data = response.to_json()

        assert json_data["ok"] is True
        assert json_data["summary"] == "Test completed"
        assert "need_confirm" not in json_data  # Should be omitted when False
        assert "error" not in json_data
        assert "data" not in json_data
        assert "stdout" not in json_data
        assert "stderr" not in json_data
        assert "metrics" in json_data

    def test_to_json_success_full(self):
        """Test JSON serialization of full success response."""
        data = {"result": "success"}
        response = MCPResponse.create_success(
            "Operation completed",
            data=data,
            stdout="Command output",
            stderr="Warning",
            need_confirm=True,
            elapsed_ms=100,
        )
        json_data = response.to_json()

        assert json_data["ok"] is True
        assert json_data["summary"] == "Operation completed"
        assert json_data["need_confirm"] is True
        assert json_data["data"] == data
        assert json_data["stdout"] == "Command output"
        assert json_data["stderr"] == "Warning"
        assert json_data["metrics"]["elapsed_ms"] == 100

    def test_to_json_error(self):
        """Test JSON serialization of error response."""
        response = MCPResponse.create_error(
            "Something went wrong", summary="Command failed", stderr="Error details"
        )
        json_data = response.to_json()

        assert json_data["ok"] is False
        assert json_data["summary"] == "Command failed"
        assert json_data["error"] == "Something went wrong"
        assert json_data["stderr"] == "Error details"
        assert "need_confirm" not in json_data
        assert "data" not in json_data
        assert "stdout" not in json_data

    def test_to_json_empty_strings_omitted(self):
        """Test that empty strings are omitted from JSON output."""
        response = MCPResponse(ok=True, summary="Test", stdout="", stderr="", data=None)
        json_data = response.to_json()

        assert "stdout" not in json_data
        assert "stderr" not in json_data
        assert "data" not in json_data


class TestMCPProtocolHandler:
    """Test cases for MCPProtocolHandler class."""

    def test_init_without_tool_registry(self):
        """Test initializing handler without tool registry."""
        handler = MCPProtocolHandler()

        assert handler.tool_registry is None
        assert hasattr(handler, "start_time")
        assert hasattr(handler, "_request_times")

    def test_init_with_tool_registry(self):
        """Test initializing handler with tool registry."""
        mock_registry = Mock()
        handler = MCPProtocolHandler(tool_registry=mock_registry)

        assert handler.tool_registry is mock_registry

    @patch("sys.stdin")
    def test_read_request_valid_json(self, mock_stdin):
        """Test reading valid JSON request."""
        mock_stdin.readline.return_value = '{"method": "list_tools"}\n'

        handler = MCPProtocolHandler()
        request = handler.read_request()

        assert request is not None
        assert request.method == "list_tools"

    @patch("sys.stdin")
    def test_read_request_eof(self, mock_stdin):
        """Test reading request at EOF."""
        mock_stdin.readline.return_value = ""

        handler = MCPProtocolHandler()
        request = handler.read_request()

        assert request is None

    @patch("sys.stdin")
    def test_read_request_empty_line(self, mock_stdin):
        """Test reading empty line."""
        mock_stdin.readline.return_value = "\n"

        handler = MCPProtocolHandler()
        request = handler.read_request()

        assert request is None

    @patch("sys.stdin")
    def test_read_request_invalid_json(self, mock_stdin):
        """Test reading invalid JSON."""
        mock_stdin.readline.return_value = '{"method": invalid json}\n'

        handler = MCPProtocolHandler()

        with pytest.raises(ValueError, match="Invalid JSON"):
            handler.read_request()

    @patch("sys.stdin")
    def test_read_request_too_large(self, mock_stdin):
        """Test reading request that exceeds size limit."""
        large_request = '{"method": "' + "x" * (1024 * 1024 + 1) + '"}'
        mock_stdin.readline.return_value = large_request

        handler = MCPProtocolHandler()

        with pytest.raises(ValueError, match="Request too large"):
            handler.read_request()

    @patch("sys.stdin")
    def test_read_request_too_complex(self, mock_stdin):
        """Test reading request with excessive complexity."""
        # Create deeply nested JSON
        nested_json = {"method": "call_tool"}
        current = nested_json
        for i in range(25):  # Exceeds depth limit
            current["nested"] = {}
            current = current["nested"]

        mock_stdin.readline.return_value = json.dumps(nested_json) + "\n"

        handler = MCPProtocolHandler()

        with pytest.raises(ValueError, match="too deeply nested"):
            handler.read_request()

    @patch("sys.stdin")
    def test_read_request_too_many_properties(self, mock_stdin):
        """Test reading request with too many properties."""
        # Create object with excessive properties
        large_object = {"method": "call_tool"}
        for i in range(101):  # Exceeds property limit
            large_object[f"prop_{i}"] = "value"

        mock_stdin.readline.return_value = json.dumps(large_object) + "\n"

        handler = MCPProtocolHandler()

        with pytest.raises(ValueError, match="too complex"):
            handler.read_request()

    @patch("sys.stdin")
    def test_read_request_large_array(self, mock_stdin):
        """Test reading request with large array."""
        large_array_request = {
            "method": "call_tool",
            "args": {"items": ["item"] * 51},  # Exceeds array limit
        }

        mock_stdin.readline.return_value = json.dumps(large_array_request) + "\n"

        handler = MCPProtocolHandler()

        with pytest.raises(ValueError, match="array too large"):
            handler.read_request()

    @patch("builtins.print")
    def test_write_response_success(self, mock_print):
        """Test writing successful response."""
        handler = MCPProtocolHandler()
        response = MCPResponse.create_success("Test completed")

        handler.write_response(response)

        mock_print.assert_called_once()
        args, kwargs = mock_print.call_args
        assert kwargs.get("flush") is True

        # Verify JSON structure
        json_output = args[0]
        parsed = json.loads(json_output)
        assert parsed["ok"] is True
        assert parsed["summary"] == "Test completed"

    @patch("builtins.print")
    def test_write_response_serialization_error(self, mock_print):
        """Test writing response when serialization fails."""
        handler = MCPProtocolHandler()

        # Create response with non-serializable data
        response = MCPResponse(ok=True, data={"func": lambda x: x})

        handler.write_response(response)

        # Should have called print twice - once for failed attempt, once for fallback
        assert mock_print.call_count >= 1

        # Last call should be the fallback response
        last_call_args = mock_print.call_args_list[-1][0]
        fallback_json = last_call_args[0]
        parsed = json.loads(fallback_json)
        assert parsed["ok"] is False
        assert (
            "serialization" in parsed["summary"].lower()
            or "error" in parsed["summary"].lower()
        )

    def test_create_error_response(self):
        """Test creating standardized error response."""
        handler = MCPProtocolHandler()

        response = handler.create_error_response("Test error", "Test failed")

        assert response.ok is False
        assert response.error == "Test error"
        assert response.summary == "Test failed"
        assert "elapsed_ms" in response.metrics

    def test_create_success_response(self):
        """Test creating standardized success response."""
        handler = MCPProtocolHandler()
        data = {"result": "success"}

        response = handler.create_success_response(
            "Test completed", data=data, stdout="Output", need_confirm=True
        )

        assert response.ok is True
        assert response.summary == "Test completed"
        assert response.data == data
        assert response.stdout == "Output"
        assert response.need_confirm is True
        assert "elapsed_ms" in response.metrics

    def test_sanitize_error_message_paths(self):
        """Test error message sanitization removes paths."""
        handler = MCPProtocolHandler()

        error_msg = "File not found: /home/user/secret/file.txt"
        sanitized = handler._sanitize_error_message(error_msg)

        assert "/home/user/secret/file.txt" not in sanitized
        assert "[PATH]" in sanitized

    def test_sanitize_error_message_traceback(self):
        """Test error message sanitization removes tracebacks."""
        handler = MCPProtocolHandler()

        error_msg = 'Traceback (most recent call last):\n  File "/path/file.py", line 1'
        sanitized = handler._sanitize_error_message(error_msg)

        assert sanitized == "Internal processing error"

    def test_sanitize_error_message_length_limit(self):
        """Test error message length limiting."""
        handler = MCPProtocolHandler()

        long_error = "x" * 250
        sanitized = handler._sanitize_error_message(long_error)

        assert len(sanitized) <= 203  # 200 + "..."
        assert sanitized.endswith("...")

    def test_handle_request_list_tools(self):
        """Test handling list_tools request."""
        mock_registry = Mock()
        mock_registry.tools = {"docker_ps": Mock(), "disk_space": Mock()}

        handler = MCPProtocolHandler(tool_registry=mock_registry)
        request = MCPRequest(method="list_tools")

        response = handler.handle_request(request)

        assert response.ok is True
        assert "tools" in response.data
        assert len(response.data["tools"]) == 2

    def test_handle_request_list_tools_no_registry(self):
        """Test handling list_tools request without registry."""
        handler = MCPProtocolHandler()
        request = MCPRequest(method="list_tools")

        response = handler.handle_request(request)

        assert response.ok is False
        assert "not initialized" in response.error

    def test_handle_request_call_tool_success(self):
        """Test handling successful call_tool request."""
        mock_registry = Mock()
        mock_result = Mock()
        mock_result.success = True
        mock_result.summary = "Tool executed"
        mock_result.data = {"result": "success"}
        mock_result.stdout = "Output"
        mock_result.stderr = ""
        mock_result.need_confirm = False
        mock_result.elapsed_ms = 100
        mock_registry.execute_tool.return_value = mock_result

        handler = MCPProtocolHandler(tool_registry=mock_registry)
        request = MCPRequest(method="call_tool", name="docker_ps", args={})

        response = handler.handle_request(request)

        assert response.ok is True
        assert response.summary == "Tool executed"
        assert response.data == {"result": "success"}
        assert response.stdout == "Output"
        assert response.metrics["elapsed_ms"] == 100
        mock_registry.execute_tool.assert_called_once_with("docker_ps", {})

    def test_handle_request_call_tool_failure(self):
        """Test handling failed call_tool request."""
        mock_registry = Mock()
        mock_result = Mock()
        mock_result.success = False
        mock_result.summary = "Tool failed"
        mock_result.data = None
        mock_result.stdout = ""
        mock_result.stderr = "Error occurred"
        mock_result.need_confirm = False
        mock_result.elapsed_ms = 50
        mock_result.exit_code = 1
        mock_registry.execute_tool.return_value = mock_result

        handler = MCPProtocolHandler(tool_registry=mock_registry)
        request = MCPRequest(method="call_tool", name="docker_ps", args={})

        response = handler.handle_request(request)

        assert response.ok is False
        assert response.summary == "Tool failed"
        assert response.stderr == "Error occurred"
        assert response.metrics["elapsed_ms"] == 50
        assert response.metrics["exit_code"] == 1

    def test_handle_request_call_tool_no_name(self):
        """Test handling call_tool request without tool name."""
        handler = MCPProtocolHandler()
        request = MCPRequest(method="call_tool", name=None)

        response = handler.handle_request(request)

        assert response.ok is False
        assert "Tool name is required" in response.error

    def test_handle_request_call_tool_no_registry(self):
        """Test handling call_tool request without registry."""
        handler = MCPProtocolHandler()
        request = MCPRequest(method="call_tool", name="docker_ps")

        response = handler.handle_request(request)

        assert response.ok is False
        assert "not initialized" in response.error

    def test_handle_request_unsupported_method(self):
        """Test handling request with unsupported method."""
        handler = MCPProtocolHandler()
        request = MCPRequest(method="unsupported_method")

        response = handler.handle_request(request)

        assert response.ok is False
        assert "Unsupported method" in response.error

    def test_handle_request_exception(self):
        """Test handling request that raises exception."""
        mock_registry = Mock()
        mock_registry.execute_tool.side_effect = Exception("Unexpected error")

        handler = MCPProtocolHandler(tool_registry=mock_registry)
        request = MCPRequest(method="call_tool", name="docker_ps")

        response = handler.handle_request(request)

        assert response.ok is False
        assert "Request handling failed" in response.error

    def test_rate_limiting(self):
        """Test rate limiting functionality."""
        handler = MCPProtocolHandler()
        handler._max_requests_per_minute = 2

        # First two requests should succeed
        assert handler._check_rate_limit() is True
        assert handler._check_rate_limit() is True

        # Third request should be rate limited
        assert handler._check_rate_limit() is False

    def test_rate_limiting_window_reset(self):
        """Test rate limiting window reset."""
        handler = MCPProtocolHandler()
        handler._max_requests_per_minute = 1
        handler._request_window = 0.1  # 100ms window

        # First request succeeds
        assert handler._check_rate_limit() is True

        # Second request immediately fails
        assert handler._check_rate_limit() is False

        # Wait for window to reset
        time.sleep(0.15)

        # Should succeed again
        assert handler._check_rate_limit() is True

    @patch("sys.stdin")
    @patch("builtins.print")
    def test_run_protocol_loop_normal_operation(self, mock_print, mock_stdin):
        """Test normal protocol loop operation."""
        # Simulate two requests then EOF
        mock_stdin.readline.side_effect = [
            '{"method": "list_tools"}\n',
            '{"method": "call_tool", "name": "docker_ps"}\n',
            "",  # EOF
        ]

        mock_registry = Mock()
        mock_registry.tools = {}
        mock_result = Mock()
        mock_result.success = True
        mock_result.summary = "Success"
        mock_result.data = None
        mock_result.stdout = ""
        mock_result.stderr = ""
        mock_result.need_confirm = False
        mock_result.elapsed_ms = 10
        mock_registry.execute_tool.return_value = mock_result

        handler = MCPProtocolHandler(tool_registry=mock_registry)

        # Should complete without exception
        handler.run_protocol_loop()

        # Should have printed two responses
        assert mock_print.call_count == 2

    @patch("sys.stdin")
    @patch("builtins.print")
    def test_run_protocol_loop_parse_error(self, mock_print, mock_stdin):
        """Test protocol loop handling parse errors."""
        mock_stdin.readline.side_effect = ["invalid json\n", ""]  # EOF

        handler = MCPProtocolHandler()

        handler.run_protocol_loop()

        # Should have printed error response
        assert mock_print.call_count == 1

        # Verify error response
        error_json = mock_print.call_args_list[0][0][0]
        parsed = json.loads(error_json)
        assert parsed["ok"] is False

    def test_rate_limit_check_function(self):
        """Test rate limiting check function directly."""
        handler = MCPProtocolHandler()
        handler._max_requests_per_minute = 2

        # First two requests should succeed
        assert handler._check_rate_limit() is True
        assert handler._check_rate_limit() is True

        # Third request should be rate limited
        assert handler._check_rate_limit() is False

    @patch("sys.stdin")
    @patch("builtins.print")
    def test_run_protocol_loop_keyboard_interrupt(self, mock_print, mock_stdin):
        """Test protocol loop handling keyboard interrupt."""
        mock_stdin.readline.side_effect = KeyboardInterrupt()

        handler = MCPProtocolHandler()

        # Should complete without raising exception
        handler.run_protocol_loop()

    @patch("sys.stdin")
    @patch("builtins.print")
    def test_run_protocol_loop_unexpected_error(self, mock_print, mock_stdin):
        """Test protocol loop handling unexpected errors."""
        mock_stdin.readline.side_effect = ['{"method": "list_tools"}\n', ""]  # EOF

        # Mock handler method to raise exception
        handler = MCPProtocolHandler()
        original_handle = handler.handle_request

        def mock_handle(request):
            if request.method == "list_tools":
                raise RuntimeError("Unexpected error")
            return original_handle(request)

        handler.handle_request = mock_handle

        handler.run_protocol_loop()

        # Should have printed at least one error response
        assert mock_print.call_count >= 1

        # Verify error response exists
        error_found = False
        for call_args in mock_print.call_args_list:
            response_json = call_args[0][0]
            if response_json.strip():  # Skip empty responses
                try:
                    parsed = json.loads(response_json)
                    if not parsed["ok"] and "server error" in parsed["summary"].lower():
                        error_found = True
                        break
                except json.JSONDecodeError:
                    continue  # Skip malformed JSON

        assert error_found, "Expected to find server error response"


class TestMCPConfirmationWorkflow:
    """Test cases for MCP confirmation workflow."""

    def test_confirmation_required_response(self):
        """Test response requiring confirmation."""
        mock_registry = Mock()
        mock_result = Mock()
        mock_result.success = True
        mock_result.summary = "Ready to publish"
        mock_result.data = {"files": ["post1.md", "post2.md"]}
        mock_result.stdout = ""
        mock_result.stderr = ""
        mock_result.need_confirm = True
        mock_result.elapsed_ms = 25
        mock_registry.execute_tool.return_value = mock_result

        handler = MCPProtocolHandler(tool_registry=mock_registry)
        request = MCPRequest(
            method="call_tool",
            name="blog_publish_static",
            args={"source_files": ["post1.md"]},
        )

        response = handler.handle_request(request)

        assert response.ok is True
        assert response.need_confirm is True
        assert response.summary == "Ready to publish"
        assert response.data == {"files": ["post1.md", "post2.md"]}

    def test_confirmation_provided_success(self):
        """Test successful execution with confirmation provided."""
        mock_registry = Mock()
        mock_result = Mock()
        mock_result.success = True
        mock_result.summary = "Files published successfully"
        mock_result.data = {"files_written": 2}
        mock_result.stdout = "Published 2 files"
        mock_result.stderr = ""
        mock_result.need_confirm = False
        mock_result.elapsed_ms = 150
        mock_registry.execute_tool.return_value = mock_result

        handler = MCPProtocolHandler(tool_registry=mock_registry)
        request = MCPRequest(
            method="call_tool",
            name="blog_publish_static",
            args={"source_files": ["post1.md"], "_confirm": True},
        )

        response = handler.handle_request(request)

        assert response.ok is True
        assert response.need_confirm is False
        assert response.summary == "Files published successfully"
        assert response.data == {"files_written": 2}
        assert response.stdout == "Published 2 files"

    def test_confirmation_workflow_json_serialization(self):
        """Test JSON serialization includes confirmation fields."""
        response = MCPResponse.create_success(
            "Ready to execute", data={"preview": "operation details"}, need_confirm=True
        )

        json_data = response.to_json()

        assert json_data["ok"] is True
        assert json_data["need_confirm"] is True
        assert json_data["summary"] == "Ready to execute"
        assert json_data["data"] == {"preview": "operation details"}

    def test_confirmation_workflow_error_with_confirmation(self):
        """Test error response that still requires confirmation."""
        mock_registry = Mock()
        mock_result = Mock()
        mock_result.success = False
        mock_result.summary = "Validation failed"
        mock_result.data = {"errors": ["Invalid file format"]}
        mock_result.stdout = ""
        mock_result.stderr = "File validation error"
        mock_result.need_confirm = True  # Still needs confirmation despite error
        mock_result.elapsed_ms = 75
        mock_result.exit_code = 1
        mock_registry.execute_tool.return_value = mock_result

        handler = MCPProtocolHandler(tool_registry=mock_registry)
        request = MCPRequest(
            method="call_tool",
            name="blog_publish_static",
            args={"source_files": ["invalid.md"]},
        )

        response = handler.handle_request(request)

        assert response.ok is False
        assert response.need_confirm is True
        assert response.summary == "Validation failed"
        assert response.data == {"errors": ["Invalid file format"]}
        assert response.stderr == "File validation error"


class TestMCPErrorHandling:
    """Test cases for MCP error handling scenarios."""

    def test_tool_execution_timeout_error(self):
        """Test handling tool execution timeout."""
        mock_registry = Mock()
        mock_result = Mock()
        mock_result.success = False
        mock_result.summary = "Tool execution timed out"
        mock_result.data = None
        mock_result.stdout = "Partial output"
        mock_result.stderr = "Process terminated due to timeout"
        mock_result.need_confirm = False
        mock_result.elapsed_ms = 30000  # 30 seconds
        mock_result.exit_code = 124  # Timeout exit code
        mock_registry.execute_tool.return_value = mock_result

        handler = MCPProtocolHandler(tool_registry=mock_registry)
        request = MCPRequest(method="call_tool", name="slow_tool")

        response = handler.handle_request(request)

        assert response.ok is False
        assert response.summary == "Tool execution timed out"
        assert response.stdout == "Partial output"
        assert response.stderr == "Process terminated due to timeout"
        assert response.metrics["exit_code"] == 124
        assert response.metrics["elapsed_ms"] == 30000

    def test_tool_not_found_error(self):
        """Test handling tool not found error."""
        mock_registry = Mock()
        mock_registry.execute_tool.side_effect = ValueError(
            "Tool 'nonexistent' not found"
        )

        handler = MCPProtocolHandler(tool_registry=mock_registry)
        request = MCPRequest(method="call_tool", name="nonexistent")

        response = handler.handle_request(request)

        assert response.ok is False
        assert "Request handling failed" in response.error
        assert "Tool 'nonexistent' not found" in response.error

    def test_permission_denied_error(self):
        """Test handling permission denied errors."""
        mock_registry = Mock()
        mock_result = Mock()
        mock_result.success = False
        mock_result.summary = "Permission denied"
        mock_result.data = None
        mock_result.stdout = ""
        mock_result.stderr = "docker: permission denied"
        mock_result.need_confirm = False
        mock_result.elapsed_ms = 10
        mock_result.exit_code = 126
        mock_registry.execute_tool.return_value = mock_result

        handler = MCPProtocolHandler(tool_registry=mock_registry)
        request = MCPRequest(method="call_tool", name="docker_ps")

        response = handler.handle_request(request)

        assert response.ok is False
        assert response.summary == "Permission denied"
        assert "permission denied" in response.stderr
        assert response.metrics["exit_code"] == 126

    def test_network_error_handling(self):
        """Test handling network-related errors."""
        mock_registry = Mock()
        mock_result = Mock()
        mock_result.success = False
        mock_result.summary = "Network request failed"
        mock_result.data = None
        mock_result.stdout = ""
        mock_result.stderr = "Connection refused: Gotify server unreachable"
        mock_result.need_confirm = False
        mock_result.elapsed_ms = 5000
        mock_result.exit_code = 1
        mock_registry.execute_tool.return_value = mock_result

        handler = MCPProtocolHandler(tool_registry=mock_registry)
        request = MCPRequest(method="call_tool", name="gotify_ping")

        response = handler.handle_request(request)

        assert response.ok is False
        assert response.summary == "Network request failed"
        assert "Connection refused" in response.stderr

    def test_malformed_tool_response_handling(self):
        """Test handling malformed tool responses."""
        mock_registry = Mock()
        # Simulate tool returning malformed result
        mock_registry.execute_tool.return_value = None

        handler = MCPProtocolHandler(tool_registry=mock_registry)
        request = MCPRequest(method="call_tool", name="broken_tool")

        response = handler.handle_request(request)

        assert response.ok is False
        assert "Request handling failed" in response.error

    def test_json_serialization_error_fallback(self):
        """Test fallback when response JSON serialization fails."""
        handler = MCPProtocolHandler()

        # Create response with circular reference (non-serializable)
        circular_data = {}
        circular_data["self"] = circular_data

        response = MCPResponse(ok=True, data=circular_data)

        with patch("builtins.print") as mock_print:
            handler.write_response(response)

            # Should have called print (for fallback response)
            assert mock_print.called

            # Verify fallback response is valid JSON
            fallback_json = mock_print.call_args_list[-1][0][0]
            parsed = json.loads(fallback_json)
            assert parsed["ok"] is False

    def test_critical_serialization_error_ultimate_fallback(self):
        """Test ultimate fallback when even fallback serialization fails."""
        handler = MCPProtocolHandler()

        # Create response with non-serializable data to trigger fallback
        response = MCPResponse(ok=True, data={"func": lambda x: x})

        with patch("builtins.print") as mock_print:
            handler.write_response(response)

            # Should still print something
            assert mock_print.called

            # Should have printed a fallback response
            printed_something = False
            for call_args in mock_print.call_args_list:
                if call_args[0][0].strip():  # Non-empty output
                    printed_something = True
                    break

            assert printed_something, "Expected handler to print fallback response"

    def test_error_message_sanitization_comprehensive(self):
        """Test comprehensive error message sanitization."""
        handler = MCPProtocolHandler()

        test_cases = [
            # Path sanitization
            ("Error in /home/user/file.txt", "[PATH]"),
            ("Failed at /var/log/app.log", "[PATH]"),
            # Traceback removal
            (
                'Traceback (most recent call last):\n  File "test.py"',
                "Internal processing error",
            ),
            ('File "/path/file.py", line 42, in function', "Internal processing error"),
            # Length limiting
            ("x" * 250, "..."),
            # Normal errors should pass through
            ("Simple error message", "Simple error message"),
        ]

        for original, expected_content in test_cases:
            sanitized = handler._sanitize_error_message(original)
            if expected_content == "...":
                assert sanitized.endswith(expected_content)
            else:
                assert expected_content in sanitized

    def test_list_tools_schema_definitions(self):
        """Test that list_tools returns proper schema definitions."""
        mock_registry = Mock()
        mock_registry.tools = {
            "docker_ps": Mock(),
            "blog_stage_markdown": Mock(),
            "gotify_ping": Mock(),
        }

        handler = MCPProtocolHandler(tool_registry=mock_registry)
        request = MCPRequest(method="list_tools")

        response = handler.handle_request(request)

        assert response.ok is True
        assert "tools" in response.data

        tools = response.data["tools"]
        tool_names = [tool["name"] for tool in tools]

        assert "docker_ps" in tool_names
        assert "blog_stage_markdown" in tool_names
        assert "gotify_ping" in tool_names

        # Verify schema structure
        for tool in tools:
            assert "name" in tool
            assert "description" in tool
            assert "inputSchema" in tool
            assert tool["inputSchema"]["type"] == "object"

    def test_list_tools_unknown_tool_fallback(self):
        """Test list_tools fallback for unknown tools."""
        mock_registry = Mock()
        mock_registry.tools = {"unknown_tool": Mock()}

        handler = MCPProtocolHandler(tool_registry=mock_registry)
        request = MCPRequest(method="list_tools")

        response = handler.handle_request(request)

        assert response.ok is True
        tools = response.data["tools"]

        # Should include fallback schema for unknown tool
        unknown_tool = next(tool for tool in tools if tool["name"] == "unknown_tool")
        assert unknown_tool["description"] == "Tool: unknown_tool"
        assert unknown_tool["inputSchema"]["additionalProperties"] is True
