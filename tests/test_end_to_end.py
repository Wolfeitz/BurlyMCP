"""
End-to-End Tests for Burly MCP Server

This module provides comprehensive end-to-end tests that verify complete
MCP request/response cycles, all tools through the MCP interface, and
confirmation workflows. These tests simulate real client interactions
with the MCP server to ensure the entire system works correctly.

Test Coverage:
- Complete MCP protocol request/response cycles
- All available tools through MCP interface
- Confirmation workflows for mutating operations
- Error handling and edge cases
- Protocol compliance and response formatting
"""

import json
import os
import time
from unittest.mock import Mock, patch

import pytest

from burly_mcp.server.mcp import MCPProtocolHandler, MCPRequest, MCPResponse
from burly_mcp.resource_limits import ExecutionResult
from burly_mcp.tools import ToolRegistry


class TestMCPProtocolEndToEnd:
    """End-to-end tests for complete MCP protocol cycles."""

    def setup_method(self):
        """Set up test environment for each test."""
        self.tool_registry = ToolRegistry()
        self.mcp_handler = MCPProtocolHandler(tool_registry=self.tool_registry)

        # Patch audit and notification systems for all tests
        self.audit_patcher = patch("burly_mcp.tools.registry.log_tool_execution")
        self.notify_success_patcher = patch("burly_mcp.tools.registry.notify_tool_success")
        self.notify_failure_patcher = patch("burly_mcp.tools.registry.notify_tool_failure")
        self.notify_confirm_patcher = patch("burly_mcp.tools.registry.notify_tool_confirmation")

        self.mock_audit = self.audit_patcher.start()
        self.mock_notify_success = self.notify_success_patcher.start()
        self.mock_notify_failure = self.notify_failure_patcher.start()
        self.mock_notify_confirm = self.notify_confirm_patcher.start()

    def teardown_method(self):
        """Clean up after each test."""
        self.audit_patcher.stop()
        self.notify_success_patcher.stop()
        self.notify_failure_patcher.stop()
        self.notify_confirm_patcher.stop()

    def test_list_tools_complete_cycle(self):
        """Test complete MCP cycle for list_tools operation."""
        # Create MCP request
        request_data = {"method": "list_tools"}
        request = MCPRequest.from_json(request_data)

        # Process request through MCP handler
        response = self.mcp_handler.handle_request(request)

        # Verify response structure
        assert isinstance(response, MCPResponse)
        assert response.ok is True
        assert response.need_confirm is False
        assert "Available tools" in response.summary

        # Verify response can be serialized to JSON
        json_response = response.to_json()
        assert isinstance(json_response, dict)
        assert json_response["ok"] is True
        assert "data" in json_response
        assert "tools" in json_response["data"]

        # Verify all expected tools are present
        tools = json_response["data"]["tools"]
        expected_tools = [
            "docker_ps",
            "disk_space",
            "blog_stage_markdown",
            "blog_publish_static",
            "gotify_ping",
        ]

        tool_names = [tool["name"] for tool in tools]
        for expected_tool in expected_tools:
            assert expected_tool in tool_names

        # Verify tool schemas are properly formatted
        for tool in tools:
            assert "name" in tool
            assert "description" in tool
            assert "inputSchema" in tool
            assert isinstance(tool["inputSchema"], dict)
            assert "type" in tool["inputSchema"]

        # Verify metrics are included
        assert "metrics" in json_response
        assert "elapsed_ms" in json_response["metrics"]
        assert "exit_code" in json_response["metrics"]

    def test_invalid_method_complete_cycle(self):
        """Test complete MCP cycle for invalid method."""
        # The MCP request parser validates methods, so we test handler directly
        request = MCPRequest(method="invalid_method")
        response = self.mcp_handler.handle_request(request)

        # Verify error response structure
        assert isinstance(response, MCPResponse)
        assert response.ok is False
        assert response.need_confirm is False
        assert (
            "Method not supported" in response.summary
            or "Unsupported method" in response.summary
        )

        # Verify response can be serialized to JSON
        json_response = response.to_json()
        assert isinstance(json_response, dict)
        assert json_response["ok"] is False
        assert "error" in json_response

        # Verify metrics are included even for errors
        assert "metrics" in json_response
        assert json_response["metrics"]["exit_code"] != 0

    def test_malformed_request_handling(self):
        """Test handling of malformed JSON requests."""
        # Test various malformed requests
        malformed_requests = [
            {},  # Missing method
            {"method": ""},  # Empty method
            {"method": "call_tool"},  # Missing tool name for call_tool
            {"method": "call_tool", "name": ""},  # Empty tool name
        ]

        for request_data in malformed_requests:
            if "method" not in request_data or not request_data.get("method"):
                # These should fail at request parsing
                with pytest.raises(ValueError):
                    MCPRequest.from_json(request_data)
            else:
                # These should be handled gracefully
                request = MCPRequest.from_json(request_data)
                response = self.mcp_handler.handle_request(request)

                assert response.ok is False
                json_response = response.to_json()
                assert json_response["ok"] is False

    @pytest.mark.integration
    @patch("burly_mcp.resource_limits.execute_with_timeout")
    def test_docker_ps_complete_mcp_cycle(self, mock_execute):
        """Test complete MCP cycle for docker_ps tool."""
        # Mock successful docker ps output
        docker_output = """CONTAINER ID	IMAGE	COMMAND	CREATED	STATUS	PORTS	NAMES
abc123def456	nginx:latest	"/docker-entrypoint.…"	2 hours ago	Up 2 hours	0.0.0.0:80->80/tcp	web-server"""

        mock_result = ExecutionResult(
            success=True,
            exit_code=0,
            stdout=docker_output,
            stderr="",
            timed_out=False,
            elapsed_ms=150,
            stdout_truncated=False,
            stderr_truncated=False,
            original_stdout_size=len(docker_output),
            original_stderr_size=0,
        )
        mock_execute.return_value = mock_result

        # Create MCP request
        request_data = {"method": "call_tool", "name": "docker_ps", "args": {}}
        request = MCPRequest.from_json(request_data)

        # Process request through MCP handler
        response = self.mcp_handler.handle_request(request)

        # Verify successful response
        assert response.ok is True
        assert response.need_confirm is False
        assert "Found 1 running container" in response.summary

        # Verify response serialization
        json_response = response.to_json()
        assert json_response["ok"] is True
        assert "data" in json_response
        assert "containers" in json_response["data"]
        assert len(json_response["data"]["containers"]) == 1

        # Verify container data structure
        container = json_response["data"]["containers"][0]
        assert container["id"] == "abc123def456"
        assert container["image"] == "nginx:latest"
        assert container["names"] == "web-server"

    @patch("burly_mcp.resource_limits.execute_with_timeout")
    def test_disk_space_complete_mcp_cycle(self, mock_execute):
        """Test complete MCP cycle for disk_space tool."""
        # Mock successful df output
        df_output = """Filesystem     Type      Size  Used Avail Use% Mounted on
/dev/sda1      ext4       20G  8.5G   11G  45% /
/dev/sda2      ext4      100G   85G   10G  90% /home"""

        mock_result = ExecutionResult(
            success=True,
            exit_code=0,
            stdout=df_output,
            stderr="",
            timed_out=False,
            elapsed_ms=120,
            stdout_truncated=False,
            stderr_truncated=False,
            original_stdout_size=len(df_output),
            original_stderr_size=0,
        )
        mock_execute.return_value = mock_result

        # Create MCP request
        request_data = {"method": "call_tool", "name": "disk_space", "args": {}}
        request = MCPRequest.from_json(request_data)

        # Process request through MCP handler
        response = self.mcp_handler.handle_request(request)

        # Verify successful response
        assert response.ok is True
        assert response.need_confirm is False
        assert "Found" in response.summary and "filesystems" in response.summary

        # Verify response serialization
        json_response = response.to_json()
        assert json_response["ok"] is True
        assert "data" in json_response
        assert "filesystems" in json_response["data"]
        # Should have at least the mocked filesystems
        assert len(json_response["data"]["filesystems"]) >= 2

        # Verify high usage detection
        assert "high_usage" in json_response["data"]
        assert len(json_response["data"]["high_usage"]) == 1
        assert json_response["data"]["high_usage"][0]["mounted_on"] == "/home"

    def test_blog_stage_markdown_complete_mcp_cycle(self, temp_dir):
        """Test complete MCP cycle for blog_stage_markdown tool."""
        # Create a valid blog post file
        blog_content = """---
title: "Test Blog Post"
date: "2024-01-15"
tags: ["test", "markdown"]
author: "Test Author"
---

# Test Blog Post

This is a test blog post with valid front-matter.
"""

        blog_file = temp_dir / "test-post.md"
        blog_file.write_text(blog_content)

        # Mock environment variable for staging root
        with patch.dict(os.environ, {"BLOG_STAGE_ROOT": str(temp_dir)}):
            # Create MCP request
            request_data = {
                "method": "call_tool",
                "name": "blog_stage_markdown",
                "args": {"file_path": "test-post.md"},
            }
            request = MCPRequest.from_json(request_data)

            # Process request through MCP handler
            response = self.mcp_handler.handle_request(request)

        # Verify successful response
        assert response.ok is True
        assert response.need_confirm is False
        assert "Blog post validation passed" in response.summary

        # Verify response serialization
        json_response = response.to_json()
        assert json_response["ok"] is True
        assert "data" in json_response
        assert "front_matter" in json_response["data"]

        # Verify parsed front-matter
        front_matter = json_response["data"]["front_matter"]
        assert front_matter["title"] == "Test Blog Post"
        assert front_matter["date"] == "2024-01-15"
        assert front_matter["tags"] == ["test", "markdown"]

    def test_blog_publish_confirmation_workflow_complete_cycle(self, temp_dir):
        """Test complete MCP cycle for blog_publish_static confirmation workflow."""
        # Create staging and publish directories
        stage_dir = temp_dir / "stage"
        publish_dir = temp_dir / "publish"
        stage_dir.mkdir()
        publish_dir.mkdir()

        # Create test files in staging
        test_file1 = stage_dir / "post1.md"
        test_file1.write_text("# Post 1")
        test_file2 = stage_dir / "post2.md"
        test_file2.write_text("# Post 2")

        # Mock environment variables
        with patch.dict(
            os.environ,
            {"BLOG_STAGE_ROOT": str(stage_dir), "BLOG_PUBLISH_ROOT": str(publish_dir)},
        ):
            # Step 1: Request without confirmation
            request_data = {
                "method": "call_tool",
                "name": "blog_publish_static",
                "args": {"source_files": ["post1.md", "post2.md"]},
            }
            request = MCPRequest.from_json(request_data)

            # Process request through MCP handler
            response = self.mcp_handler.handle_request(request)

            # Verify confirmation is required
            assert response.need_confirm is True
            json_response = response.to_json()
            assert json_response["need_confirm"] is True
            assert (
                "confirmation" in response.summary.lower()
                or "ready to publish" in response.summary.lower()
            )

            # Step 2: Request with confirmation
            request_data_confirmed = {
                "method": "call_tool",
                "name": "blog_publish_static",
                "args": {"source_files": ["post1.md", "post2.md"], "_confirm": True},
            }
            request_confirmed = MCPRequest.from_json(request_data_confirmed)

            # Process confirmed request
            response_confirmed = self.mcp_handler.handle_request(request_confirmed)

            # Verify successful publication
            assert response_confirmed.ok is True
            assert response_confirmed.need_confirm is False

            json_response_confirmed = response_confirmed.to_json()
            assert json_response_confirmed["ok"] is True
            # need_confirm is only included in JSON if True
            assert json_response_confirmed.get("need_confirm", False) is False

            # Verify files were actually copied
            assert (publish_dir / "post1.md").exists()
            assert (publish_dir / "post2.md").exists()

    @pytest.mark.integration
    @patch("urllib.request.urlopen")
    def test_gotify_ping_complete_mcp_cycle(self, mock_urlopen):
        """Test complete MCP cycle for gotify_ping tool."""
        # Mock successful HTTP response
        mock_response = Mock()
        mock_response.read.return_value = b'{"id": 123, "message": "Test message sent"}'
        mock_response.getcode.return_value = 200
        mock_urlopen.return_value.__enter__.return_value = mock_response

        # Mock environment variables
        with patch.dict(
            os.environ,
            {"GOTIFY_URL": "http://localhost:8080", "GOTIFY_TOKEN": "test_token_123"},
        ):
            # Create MCP request
            request_data = {
                "method": "call_tool",
                "name": "gotify_ping",
                "args": {"message": "Test notification"},
            }
            request = MCPRequest.from_json(request_data)

            # Process request through MCP handler
            response = self.mcp_handler.handle_request(request)

        # Verify successful response
        assert response.ok is True
        assert response.need_confirm is False
        assert "Gotify notification sent successfully" in response.summary

        # Verify response serialization
        json_response = response.to_json()
        assert json_response["ok"] is True
        assert "data" in json_response
        assert json_response["data"]["message_id"] == 123
        assert json_response["data"]["message"] == "Test notification"

    def test_nonexistent_tool_complete_cycle(self):
        """Test complete MCP cycle for nonexistent tool."""
        # Create MCP request for nonexistent tool
        request_data = {"method": "call_tool", "name": "nonexistent_tool", "args": {}}
        request = MCPRequest.from_json(request_data)

        # Process request through MCP handler
        response = self.mcp_handler.handle_request(request)

        # Verify error response
        assert response.ok is False
        assert response.need_confirm is False

        # Verify response serialization
        json_response = response.to_json()
        assert json_response["ok"] is False
        assert "error" in json_response
        assert (
            "not found" in json_response["error"].lower()
            or "unknown" in json_response["error"].lower()
        )

    def test_response_envelope_consistency(self):
        """Test that all responses follow the standardized envelope format."""
        test_cases = [
            # Successful list_tools
            {"method": "list_tools"},
            # Nonexistent tool
            {"method": "call_tool", "name": "nonexistent", "args": {}},
        ]

        for request_data in test_cases:
            request = MCPRequest.from_json(request_data)
            response = self.mcp_handler.handle_request(request)
            json_response = response.to_json()

            # Test the envelope format
            self._verify_envelope_format(json_response)

        # Test invalid method separately due to parsing restrictions
        invalid_request = MCPRequest(method="invalid_method")
        invalid_response = self.mcp_handler.handle_request(invalid_request)
        invalid_json_response = invalid_response.to_json()
        self._verify_envelope_format(invalid_json_response)

    def _verify_envelope_format(self, json_response):
        """Verify response follows envelope format."""
        # Verify required envelope fields
        assert "ok" in json_response
        assert "summary" in json_response
        assert "metrics" in json_response
        assert "elapsed_ms" in json_response["metrics"]
        assert "exit_code" in json_response["metrics"]

        # Verify boolean types
        assert isinstance(json_response["ok"], bool)

        # Verify conditional fields
        if not json_response["ok"]:
            # Error responses should have error field
            assert "error" in json_response

        if json_response.get("need_confirm"):
            assert isinstance(json_response["need_confirm"], bool)

    def test_error_handling_and_recovery(self):
        """Test error handling and recovery in MCP protocol."""
        # Test sequence of requests including errors
        test_sequence = [
            {"method": "list_tools"},  # Should succeed
            {"method": "call_tool", "name": "nonexistent", "args": {}},  # Should fail
            {"method": "list_tools"},  # Should succeed again
        ]

        for i, request_data in enumerate(test_sequence):
            request = MCPRequest.from_json(request_data)
            response = self.mcp_handler.handle_request(request)

            # Verify response is always valid
            assert isinstance(response, MCPResponse)
            json_response = response.to_json()
            assert isinstance(json_response, dict)

            # Verify expected outcomes
            if request_data["method"] == "list_tools":
                assert response.ok is True
            else:
                assert response.ok is False

            # Verify handler continues to work after errors
            assert "metrics" in json_response

        # Test invalid method separately
        invalid_request = MCPRequest(method="invalid_method")
        invalid_response = self.mcp_handler.handle_request(invalid_request)

        # Verify invalid method response
        assert isinstance(invalid_response, MCPResponse)
        invalid_json_response = invalid_response.to_json()
        assert isinstance(invalid_json_response, dict)
        assert invalid_response.ok is False
        assert "metrics" in invalid_json_response


class TestMCPProtocolLoop:
    """Test the MCP protocol loop with simulated stdin/stdout."""

    def setup_method(self):
        """Set up test environment for each test."""
        self.tool_registry = ToolRegistry()
        self.mcp_handler = MCPProtocolHandler(tool_registry=self.tool_registry)

        # Patch audit and notification systems
        self.audit_patcher = patch("server.tools.log_tool_execution")
        self.notify_success_patcher = patch("server.tools.notify_tool_success")
        self.notify_failure_patcher = patch("server.tools.notify_tool_failure")

        self.mock_audit = self.audit_patcher.start()
        self.mock_notify_success = self.notify_success_patcher.start()
        self.mock_notify_failure = self.notify_failure_patcher.start()

    def teardown_method(self):
        """Clean up after each test."""
        self.audit_patcher.stop()
        self.notify_success_patcher.stop()
        self.notify_failure_patcher.stop()

    def test_request_parsing_from_json_string(self):
        """Test parsing MCP requests from JSON strings."""
        # Test valid requests
        valid_requests = [
            '{"method": "list_tools"}',
            '{"method": "call_tool", "name": "docker_ps", "args": {}}',
            '{"method": "call_tool", "name": "gotify_ping", "args": {"message": "test"}}',
        ]

        for json_str in valid_requests:
            # Simulate reading from stdin
            with patch("sys.stdin.readline", return_value=json_str + "\n"):
                request = self.mcp_handler.read_request()
                assert request is not None
                assert isinstance(request, MCPRequest)
                assert request.method in ["list_tools", "call_tool"]

    def test_request_parsing_invalid_json(self):
        """Test handling of invalid JSON in requests."""
        invalid_requests = [
            '{"method": "list_tools"',  # Incomplete JSON
            '{"method":}',  # Invalid JSON syntax
            "not json at all",  # Not JSON
            '{"method": "list_tools", "extra": {"deeply": {"nested": {"object": "value"}}}}'
            * 100,  # Too complex
        ]

        for json_str in invalid_requests:
            with patch("sys.stdin.readline", return_value=json_str + "\n"):
                with pytest.raises(ValueError):
                    self.mcp_handler.read_request()

    def test_response_serialization_to_stdout(self):
        """Test response serialization and writing to stdout."""
        # Create various response types
        responses = [
            MCPResponse.create_success("Test success", data={"key": "value"}),
            MCPResponse.create_error("Test error", "Error summary"),
            MCPResponse.create_success("Confirmation needed", need_confirm=True),
        ]

        for response in responses:
            # Capture stdout
            with patch("builtins.print") as mock_print:
                self.mcp_handler.write_response(response)

                # Verify print was called
                mock_print.assert_called_once()

                # Verify the output is valid JSON
                output = mock_print.call_args[0][0]
                parsed = json.loads(output)

                # Verify required fields
                assert "ok" in parsed
                assert "summary" in parsed
                assert "metrics" in parsed

    def test_eof_handling(self):
        """Test handling of EOF (end of input)."""
        # Simulate EOF
        with patch("sys.stdin.readline", return_value=""):
            request = self.mcp_handler.read_request()
            assert request is None

    def test_empty_line_handling(self):
        """Test handling of empty lines."""
        # Simulate empty line
        with patch("sys.stdin.readline", return_value="\n"):
            request = self.mcp_handler.read_request()
            assert request is None

    def test_rate_limiting(self):
        """Test rate limiting functionality."""
        # Reset rate limiting state
        self.mcp_handler._request_times = []

        # Test normal rate
        for i in range(10):
            assert self.mcp_handler._check_rate_limit() is True

        # Test rate limit exceeded
        # Fill up the rate limit
        current_time = time.time()
        self.mcp_handler._request_times = [
            current_time
        ] * self.mcp_handler._max_requests_per_minute

        # Next request should be rate limited
        assert self.mcp_handler._check_rate_limit() is False

    def test_security_input_size_limit(self):
        """Test security limits on input size."""
        # Create oversized request
        large_request = (
            '{"method": "list_tools", "data": "' + "x" * (1024 * 1024 + 1) + '"}'
        )

        with patch("sys.stdin.readline", return_value=large_request + "\n"):
            with pytest.raises(ValueError, match="Request too large"):
                self.mcp_handler.read_request()

    def test_security_json_complexity_limit(self):
        """Test security limits on JSON complexity."""
        # Create deeply nested JSON
        nested_obj = {"level": 0}
        current = nested_obj
        for i in range(25):  # Exceed max depth of 20
            current["next"] = {"level": i + 1}
            current = current["next"]

        complex_request = {"method": "list_tools", "nested": nested_obj}
        json_str = json.dumps(complex_request)

        with patch("sys.stdin.readline", return_value=json_str + "\n"):
            with pytest.raises(ValueError, match="too deeply nested"):
                self.mcp_handler.read_request()


class TestConfirmationWorkflows:
    """Test confirmation workflows for mutating operations."""

    def setup_method(self):
        """Set up test environment for each test."""
        self.tool_registry = ToolRegistry()
        self.mcp_handler = MCPProtocolHandler(tool_registry=self.tool_registry)

        # Patch audit and notification systems
        self.audit_patcher = patch("server.tools.log_tool_execution")
        self.notify_success_patcher = patch("server.tools.notify_tool_success")
        self.notify_failure_patcher = patch("server.tools.notify_tool_failure")
        self.notify_confirm_patcher = patch("server.tools.notify_tool_confirmation")

        self.mock_audit = self.audit_patcher.start()
        self.mock_notify_success = self.notify_success_patcher.start()
        self.mock_notify_failure = self.notify_failure_patcher.start()
        self.mock_notify_confirm = self.notify_confirm_patcher.start()

    def teardown_method(self):
        """Clean up after each test."""
        self.audit_patcher.stop()
        self.notify_success_patcher.stop()
        self.notify_failure_patcher.stop()
        self.notify_confirm_patcher.stop()

    def test_blog_publish_confirmation_workflow(self, temp_dir):
        """Test complete confirmation workflow for blog publishing."""
        # Create staging and publish directories
        stage_dir = temp_dir / "stage"
        publish_dir = temp_dir / "publish"
        stage_dir.mkdir()
        publish_dir.mkdir()

        # Create test files
        (stage_dir / "post1.md").write_text("# Post 1")
        (stage_dir / "post2.md").write_text("# Post 2")

        with patch.dict(
            os.environ,
            {"BLOG_STAGE_ROOT": str(stage_dir), "BLOG_PUBLISH_ROOT": str(publish_dir)},
        ):
            # Phase 1: Initial request without confirmation
            request1 = MCPRequest.from_json(
                {
                    "method": "call_tool",
                    "name": "blog_publish_static",
                    "args": {"source_files": ["post1.md", "post2.md"]},
                }
            )

            response1 = self.mcp_handler.handle_request(request1)

            # Verify confirmation is required
            assert response1.need_confirm is True
            json_response1 = response1.to_json()
            assert json_response1["need_confirm"] is True

            # Verify files are NOT published yet
            assert not (publish_dir / "post1.md").exists()
            assert not (publish_dir / "post2.md").exists()

            # Phase 2: Request with confirmation
            request2 = MCPRequest.from_json(
                {
                    "method": "call_tool",
                    "name": "blog_publish_static",
                    "args": {
                        "source_files": ["post1.md", "post2.md"],
                        "_confirm": True,
                    },
                }
            )

            response2 = self.mcp_handler.handle_request(request2)

            # Verify successful execution
            assert response2.ok is True
            assert response2.need_confirm is False

            # Verify files are now published
            assert (publish_dir / "post1.md").exists()
            assert (publish_dir / "post2.md").exists()
            assert (publish_dir / "post1.md").read_text() == "# Post 1"
            assert (publish_dir / "post2.md").read_text() == "# Post 2"

    def test_confirmation_workflow_response_format(self, temp_dir):
        """Test that confirmation workflow responses follow proper format."""
        # Create test environment
        stage_dir = temp_dir / "stage"
        publish_dir = temp_dir / "publish"
        stage_dir.mkdir()
        publish_dir.mkdir()
        (stage_dir / "test.md").write_text("# Test")

        with patch.dict(
            os.environ,
            {"BLOG_STAGE_ROOT": str(stage_dir), "BLOG_PUBLISH_ROOT": str(publish_dir)},
        ):
            # Test confirmation required response
            request = MCPRequest.from_json(
                {
                    "method": "call_tool",
                    "name": "blog_publish_static",
                    "args": {"source_files": ["test.md"]},
                }
            )

            response = self.mcp_handler.handle_request(request)
            json_response = response.to_json()

            # Verify response structure for confirmation
            assert "need_confirm" in json_response
            assert json_response["need_confirm"] is True
            assert "ok" in json_response
            assert "summary" in json_response
            assert "metrics" in json_response

            # Verify confirmation response includes helpful information
            assert "data" in json_response or "summary" in json_response

    def test_non_mutating_tools_no_confirmation(self):
        """Test that non-mutating tools don't require confirmation."""
        # Test read-only tools
        readonly_requests = [
            {"method": "list_tools"},
            {"method": "call_tool", "name": "docker_ps", "args": {}},
            {"method": "call_tool", "name": "disk_space", "args": {}},
        ]

        for request_data in readonly_requests:
            request = MCPRequest.from_json(request_data)

            # Mock any external dependencies
            with patch("server.tools.execute_with_timeout") as mock_execute:
                mock_execute.return_value = ExecutionResult(
                    success=True,
                    exit_code=0,
                    stdout="test output",
                    stderr="",
                    timed_out=False,
                    elapsed_ms=100,
                    stdout_truncated=False,
                    stderr_truncated=False,
                    original_stdout_size=11,
                    original_stderr_size=0,
                )

                response = self.mcp_handler.handle_request(request)

            # Verify no confirmation required
            assert response.need_confirm is False
            json_response = response.to_json()
            assert json_response.get("need_confirm", False) is False

    def test_confirmation_parameter_validation(self, temp_dir):
        """Test validation of confirmation parameter."""
        # Create test environment
        stage_dir = temp_dir / "stage"
        publish_dir = temp_dir / "publish"
        stage_dir.mkdir()
        publish_dir.mkdir()
        (stage_dir / "test.md").write_text("# Test")

        with patch.dict(
            os.environ,
            {"BLOG_STAGE_ROOT": str(stage_dir), "BLOG_PUBLISH_ROOT": str(publish_dir)},
        ):
            # Test various confirmation parameter values
            confirmation_values = [True, False, "true", "false", 1, 0]

            for confirm_value in confirmation_values:
                request = MCPRequest.from_json(
                    {
                        "method": "call_tool",
                        "name": "blog_publish_static",
                        "args": {
                            "source_files": ["test.md"],
                            "_confirm": confirm_value,
                        },
                    }
                )

                response = self.mcp_handler.handle_request(request)

                # Verify response is valid regardless of confirmation value format
                assert isinstance(response, MCPResponse)
                json_response = response.to_json()
                assert "ok" in json_response
                assert "summary" in json_response


class TestMCPComplianceAndStandards:
    """Test MCP protocol compliance and standards adherence."""

    def setup_method(self):
        """Set up test environment for each test."""
        self.tool_registry = ToolRegistry()
        self.mcp_handler = MCPProtocolHandler(tool_registry=self.tool_registry)

    def test_mcp_request_format_compliance(self):
        """Test that request parsing follows MCP standards."""
        # Test required fields
        valid_requests = [
            {"method": "list_tools"},
            {"method": "call_tool", "name": "docker_ps"},
            {"method": "call_tool", "name": "gotify_ping", "args": {"message": "test"}},
        ]

        for request_data in valid_requests:
            request = MCPRequest.from_json(request_data)
            assert hasattr(request, "method")
            assert hasattr(request, "name")
            assert hasattr(request, "args")

    def test_mcp_response_format_compliance(self):
        """Test that responses follow MCP standards."""
        # Test various response types
        responses = [
            MCPResponse.create_success("Success"),
            MCPResponse.create_error("Error", "Error summary"),
            MCPResponse.create_success("Confirm needed", need_confirm=True),
        ]

        for response in responses:
            json_response = response.to_json()

            # Verify required MCP response fields
            assert "ok" in json_response
            assert isinstance(json_response["ok"], bool)

            # Verify optional fields are properly handled
            if "need_confirm" in json_response:
                assert isinstance(json_response["need_confirm"], bool)

            # Verify JSON serialization works
            json_str = json.dumps(json_response)
            parsed_back = json.loads(json_str)
            assert parsed_back["ok"] == json_response["ok"]

    def test_tool_schema_format_compliance(self):
        """Test that tool schemas follow MCP standards."""
        # Get list_tools response
        request = MCPRequest.from_json({"method": "list_tools"})
        response = self.mcp_handler.handle_request(request)

        assert response.ok is True
        json_response = response.to_json()
        tools = json_response["data"]["tools"]

        # Verify each tool schema follows MCP format
        for tool in tools:
            # Required fields
            assert "name" in tool
            assert "description" in tool
            assert "inputSchema" in tool

            # Verify schema structure
            schema = tool["inputSchema"]
            assert "type" in schema
            assert schema["type"] == "object"

            # Verify schema is valid JSON Schema
            if "properties" in schema:
                assert isinstance(schema["properties"], dict)

            if "required" in schema:
                assert isinstance(schema["required"], list)

    def test_error_response_standards(self):
        """Test that error responses follow standards."""
        # Generate various error conditions
        error_requests = [
            {"method": "call_tool", "name": "nonexistent_tool", "args": {}},
        ]

        for request_data in error_requests:
            request = MCPRequest.from_json(request_data)
            response = self.mcp_handler.handle_request(request)

            # Verify error response format
            assert response.ok is False
            json_response = response.to_json()

            assert json_response["ok"] is False
            assert "error" in json_response
            assert "summary" in json_response
            assert isinstance(json_response["error"], str)
            assert len(json_response["error"]) > 0

        # Test invalid method separately
        invalid_request = MCPRequest(method="invalid_method")
        invalid_response = self.mcp_handler.handle_request(invalid_request)

        # Verify invalid method error response format
        assert invalid_response.ok is False
        invalid_json_response = invalid_response.to_json()

        assert invalid_json_response["ok"] is False
        assert "error" in invalid_json_response
        assert "summary" in invalid_json_response
        assert isinstance(invalid_json_response["error"], str)
        assert len(invalid_json_response["error"]) > 0

    def test_metrics_consistency(self):
        """Test that metrics are consistently included in responses."""
        # Test various request types
        test_requests = [
            {"method": "list_tools"},
            {"method": "call_tool", "name": "nonexistent", "args": {}},
        ]

        for request_data in test_requests:
            request = MCPRequest.from_json(request_data)
            response = self.mcp_handler.handle_request(request)
            json_response = response.to_json()

            # Verify metrics are always present
            assert "metrics" in json_response
            metrics = json_response["metrics"]

            # Verify required metric fields
            assert "elapsed_ms" in metrics
            assert "exit_code" in metrics
            assert isinstance(metrics["elapsed_ms"], int)
            assert isinstance(metrics["exit_code"], int)
            assert metrics["elapsed_ms"] >= 0

        # Test invalid method separately
        invalid_request = MCPRequest(method="invalid_method")
        invalid_response = self.mcp_handler.handle_request(invalid_request)
        invalid_json_response = invalid_response.to_json()

        # Verify metrics are present in invalid method response too
        assert "metrics" in invalid_json_response
        invalid_metrics = invalid_json_response["metrics"]

        # Verify required metric fields
        assert "elapsed_ms" in invalid_metrics
        assert "exit_code" in invalid_metrics
        assert isinstance(invalid_metrics["elapsed_ms"], int)
        assert isinstance(invalid_metrics["exit_code"], int)
        assert invalid_metrics["elapsed_ms"] >= 0

    def test_response_envelope_consistency(self):
        """Test that all responses use consistent envelope format."""
        # Generate various response types
        test_cases = [
            # Success cases
            {"method": "list_tools"},
            # Error cases
            {"method": "call_tool", "name": "nonexistent", "args": {}},
        ]

        for request_data in test_cases:
            request = MCPRequest.from_json(request_data)
            response = self.mcp_handler.handle_request(request)
            json_response = response.to_json()

            # Verify consistent envelope structure
            required_fields = ["ok", "summary", "metrics"]
            for field in required_fields:
                assert field in json_response, f"Missing required field: {field}"

            # Verify field types
            assert isinstance(json_response["ok"], bool)
            assert isinstance(json_response["summary"], str)
            assert isinstance(json_response["metrics"], dict)

            # Verify conditional fields
            if not json_response["ok"]:
                assert "error" in json_response

            if json_response.get("need_confirm"):
                assert isinstance(json_response["need_confirm"], bool)

        # Test invalid method separately
        invalid_request = MCPRequest(method="invalid_method")
        invalid_response = self.mcp_handler.handle_request(invalid_request)
        invalid_json_response = invalid_response.to_json()

        # Verify invalid method response envelope
        required_fields = ["ok", "summary", "metrics"]
        for field in required_fields:
            assert field in invalid_json_response, f"Missing required field: {field}"

        # Verify field types
        assert isinstance(invalid_json_response["ok"], bool)
        assert isinstance(invalid_json_response["summary"], str)
        assert isinstance(invalid_json_response["metrics"], dict)

        # Verify conditional fields
        if not invalid_json_response["ok"]:
            assert "error" in invalid_json_response

        if invalid_json_response.get("need_confirm"):
            assert isinstance(invalid_json_response["need_confirm"], bool)
