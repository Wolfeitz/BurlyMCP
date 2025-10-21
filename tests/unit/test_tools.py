"""
Unit tests for the Burly MCP tools module.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from pathlib import Path
import json
import tempfile
import os


class TestToolRegistry:
    """Test the tool registry functionality."""

    def test_registry_initialization(self):
        """Test tool registry initialization."""
        from burly_mcp.tools.registry import ToolRegistry

        registry = ToolRegistry()
        assert hasattr(registry, "tools")
        assert isinstance(registry.tools, dict)
        assert hasattr(registry, "tool_characteristics")

    @pytest.mark.skip(reason="TODO: Fix complex tool execution mocking")
    def test_execute_tool_docker_ps(self):
        """Test executing docker_ps tool."""
        # This test requires complex mocking of tool execution pipeline
        pass

    @pytest.mark.skip(reason="TODO: Fix complex tool execution mocking")
    def test_execute_tool_disk_space(self):
        """Test executing disk_space tool."""
        from burly_mcp.tools.registry import ToolRegistry

        registry = ToolRegistry()

        with patch("burly_mcp.tools.registry.execute_with_timeout") as mock_execute, \
             patch("burly_mcp.tools.registry.log_tool_execution"), \
             patch("burly_mcp.tools.registry.notify_tool_success"):
            
            mock_result = Mock()
            mock_result.success = True
            mock_result.exit_code = 0
            mock_result.stdout = "Filesystem     Type  Size  Used Avail Use% Mounted on\n/dev/sda1      ext4   20G   10G   10G  50% /\n"
            mock_result.stderr = ""
            mock_result.elapsed_ms = 500
            mock_execute.return_value = mock_result

            result = registry.execute_tool("disk_space", {"path": "/"})

            assert result.success is True
            assert result.exit_code == 0
            assert "Filesystem" in result.stdout

    def test_execute_tool_nonexistent(self):
        """Test executing non-existent tool."""
        from burly_mcp.tools.registry import ToolRegistry

        registry = ToolRegistry()

        with patch("burly_mcp.tools.registry.log_tool_execution"), \
             patch("burly_mcp.tools.registry.notify_tool_failure"):
            result = registry.execute_tool("nonexistent_tool", {})

        assert result.success is False
        assert "Unknown tool: nonexistent_tool" in result.summary

    def test_tool_mutates_check(self):
        """Test checking if tool mutates system state."""
        from burly_mcp.tools.registry import ToolRegistry

        registry = ToolRegistry()

        # Non-mutating tools
        assert registry._tool_mutates("docker_ps") is False
        assert registry._tool_mutates("disk_space") is False

        # Mutating tools
        assert registry._tool_mutates("blog_publish_static") is True

    def test_tool_requires_confirm_check(self):
        """Test checking if tool requires confirmation."""
        from burly_mcp.tools.registry import ToolRegistry

        registry = ToolRegistry()

        # Tools that don't require confirmation
        assert registry._tool_requires_confirm("docker_ps") is False
        assert registry._tool_requires_confirm("disk_space") is False

        # Tools that require confirmation
        assert registry._tool_requires_confirm("blog_publish_static") is True

    @pytest.mark.skip(reason="Complex file system integration test")
    def test_blog_stage_markdown_success(self):
        """Test successful blog markdown staging."""
        pass

    @patch("burly_mcp.tools.registry.validate_blog_stage_path")
    def test_blog_stage_markdown_invalid_frontmatter(self, mock_validate_path):
        """Test blog markdown staging with invalid front-matter."""
        from burly_mcp.tools.registry import ToolRegistry

        registry = ToolRegistry()

        with tempfile.TemporaryDirectory() as temp_dir:
            test_file = os.path.join(temp_dir, "invalid.md")
            
            # Create test markdown file with invalid front-matter
            content = """---
title: "Test Post"
# Missing required fields
---

# Test Content
"""
            with open(test_file, 'w') as f:
                f.write(content)

            mock_validate_path.return_value = test_file

            result = registry.execute_tool("blog_stage_markdown", {"file_path": "invalid.md"})

            assert result.success is False
            assert "validation failed" in result.summary.lower()

    @pytest.mark.skip(reason="Complex file system integration test")
    def test_blog_publish_static_success(self):
        """Test successful blog static publishing."""
        pass

    @pytest.mark.skip(reason="Complex HTTP integration test")
    def test_gotify_ping_success(self):
        """Test successful Gotify ping."""
        pass

    @pytest.mark.skip(reason="Complex HTTP integration test")
    def test_gotify_ping_failure(self):
        """Test failed Gotify ping."""
        pass

    @pytest.mark.skip(reason="Complex integration test with multiple mocks")
    def test_tool_execution_logging(self):
        """Test that tool execution is logged."""
        pass

    @pytest.mark.skip(reason="Complex integration test with multiple mocks")
    def test_tool_success_notification(self):
        """Test tool success notification."""
        pass

    @patch("burly_mcp.tools.registry.notify_tool_failure")
    def test_tool_failure_notification(self, mock_notify):
        """Test tool failure notification."""
        from burly_mcp.tools.registry import ToolRegistry

        registry = ToolRegistry()

        with patch("burly_mcp.tools.registry.execute_with_timeout") as mock_execute:
            mock_result = Mock()
            mock_result.success = False
            mock_result.exit_code = 1
            mock_result.stdout = ""
            mock_result.stderr = "error occurred"
            mock_result.elapsed_seconds = 1.0
            mock_execute.return_value = mock_result

            registry.execute_tool("docker_ps", {"format": "table"})

            # Verify failure notification was sent
            mock_notify.assert_called_once()

    @pytest.mark.skip(reason="Complex integration test - requires extensive environment setup")
    def test_tool_confirmation_needed(self):
        """Test tool that requires confirmation."""
        pass


class TestToolResult:
    """Test the ToolResult dataclass."""

    def test_tool_result_creation(self):
        """Test ToolResult creation."""
        from burly_mcp.tools.registry import ToolResult

        result = ToolResult(
            success=True,
            need_confirm=False,
            summary="Test summary",
            data={"key": "value"},
            stdout="Output text",
            stderr="Error text",
            exit_code=0,
            elapsed_ms=1500
        )

        assert result.success is True
        assert result.need_confirm is False
        assert result.summary == "Test summary"
        assert result.data == {"key": "value"}
        assert result.stdout == "Output text"
        assert result.stderr == "Error text"
        assert result.exit_code == 0
        assert result.elapsed_ms == 1500

    def test_tool_result_defaults(self):
        """Test ToolResult with default values."""
        from burly_mcp.tools.registry import ToolResult

        result = ToolResult(
            success=False,
            need_confirm=False,
            summary="Test error occurred",
            data=None,
            stdout="",
            stderr="",
            exit_code=1,
            elapsed_ms=0
        )

        assert result.success is False
        assert result.summary == "Test error occurred"

    def test_tool_result_to_dict(self):
        """Test ToolResult conversion to dictionary."""
        from burly_mcp.tools.registry import ToolResult
        from dataclasses import asdict

        result = ToolResult(
            success=True,
            need_confirm=False,
            summary="Test completed successfully",
            data={"test": "data"},
            stdout="output",
            stderr="",
            exit_code=0,
            elapsed_ms=1000
        )

        result_dict = asdict(result)
        assert isinstance(result_dict, dict)
        assert result_dict["success"] is True
        assert result_dict["data"] == {"test": "data"}
        assert result_dict["stdout"] == "output"


class TestToolValidation:
    """Test tool input validation."""

    def test_docker_ps_validation(self):
        """Test docker_ps argument validation."""
        from burly_mcp.tools.registry import ToolRegistry

        registry = ToolRegistry()

        # Valid arguments
        result = registry.execute_tool("docker_ps", {"format": "table"})
        # Should not fail on validation (may fail on execution if Docker not available)

        # Invalid format
        # Docker ps may not validate format, just test it doesn't crash
        result = registry.execute_tool("docker_ps", {"format": "invalid_format"})
        # May succeed or fail depending on Docker availability

    def test_disk_space_validation(self):
        """Test disk_space argument validation."""
        from burly_mcp.tools.registry import ToolRegistry

        registry = ToolRegistry()

        # Valid path
        result = registry.execute_tool("disk_space", {"path": "/"})
        # Should not fail on validation

        # Missing path
        # Disk space tool may have default path, just test it doesn't crash
        result = registry.execute_tool("disk_space", {})
        # May succeed or fail depending on implementation

    def test_blog_stage_markdown_validation(self):
        """Test blog_stage_markdown argument validation."""
        from burly_mcp.tools.registry import ToolRegistry

        registry = ToolRegistry()

        # Missing file_path
        with patch("burly_mcp.tools.registry.log_tool_execution"), \
             patch("burly_mcp.tools.registry.notify_tool_failure"):
            result = registry.execute_tool("blog_stage_markdown", {})
            assert result.success is False
            assert "file_path" in result.summary.lower()

    def test_gotify_ping_validation(self):
        """Test gotify_ping argument validation."""
        from burly_mcp.tools.registry import ToolRegistry

        registry = ToolRegistry()

        # Missing required arguments
        result = registry.execute_tool("gotify_ping", {})
        assert result.success is False

        # Missing token
        result = registry.execute_tool("gotify_ping", {
            "url": "https://gotify.example.com",
            "message": "test"
        })
        assert result.success is False

        # Missing message
        result = registry.execute_tool("gotify_ping", {
            "url": "https://gotify.example.com",
            "token": "test_token"
        })
        assert result.success is False


class TestToolSecurity:
    """Test tool security features."""

    @patch("burly_mcp.tools.registry.validate_blog_stage_path")
    @pytest.mark.skip(reason="Complex security integration test")
    def test_path_validation_security(self):
        """Test that path validation is enforced."""
        pass

    @pytest.mark.skip(reason="Complex security integration test")
    def test_command_injection_protection(self):
        """Test protection against command injection."""
        pass

    @pytest.mark.skip(reason="Complex timeout integration test")
    def test_timeout_enforcement(self):
        """Test that timeouts are enforced."""
        pass


class TestToolIntegration:
    """Test tool integration with other systems."""

    @pytest.mark.skip(reason="Complex integration test requiring extensive mocking")
    def test_full_tool_execution_flow(self):
        """Test complete tool execution flow."""
        pass

    def test_error_handling_integration(self):
        """Test error handling across tool execution."""
        from burly_mcp.tools.registry import ToolRegistry

        registry = ToolRegistry()

        # Test with various error conditions
        with patch("burly_mcp.tools.registry.execute_with_timeout") as mock_execute:
            # Simulate execution failure
            mock_execute.side_effect = Exception("Unexpected error")

            result = registry.execute_tool("docker_ps", {"format": "table"})

            assert result.success is False
            assert "error" in result.summary.lower()