"""
Integration tests for Burly MCP tools.

This module provides integration tests that verify tool functionality
with real system interactions, including Docker CLI, file system operations,
and Gotify API integration. Tests use mocking and temporary resources
to ensure safe and repeatable testing.
"""

import json
import os
from unittest.mock import Mock, patch

import pytest

from burly_mcp.resource_limits import ExecutionResult
from burly_mcp.tools.registry import ToolRegistry


@pytest.mark.integration
class TestDockerIntegration:
    """Integration tests for Docker CLI operations."""

    def setup_method(self):
        """Set up test environment for each test."""
        self.registry = ToolRegistry()

        # Patch audit and notification systems for all tests
        self.audit_patcher = patch("burly_mcp.tools.registry.log_tool_execution")
        self.notify_success_patcher = patch("burly_mcp.tools.registry.notify_tool_success")
        self.notify_failure_patcher = patch("burly_mcp.tools.registry.notify_tool_failure")

        self.mock_audit = self.audit_patcher.start()
        self.mock_notify_success = self.notify_success_patcher.start()
        self.mock_notify_failure = self.notify_failure_patcher.start()

    def teardown_method(self):
        """Clean up after each test."""
        self.audit_patcher.stop()
        self.notify_success_patcher.stop()
        self.notify_failure_patcher.stop()

    @pytest.mark.integration
    @patch("burly_mcp.tools.registry.execute_with_timeout")
    def test_docker_ps_success_with_containers(self, mock_execute):
        """Test docker_ps with successful container listing."""
        # Mock successful docker ps output
        docker_output = """CONTAINER ID	IMAGE	COMMAND	CREATED	STATUS	PORTS	NAMES
abc123def456	nginx:latest	"/docker-entrypoint.…"	2 hours ago	Up 2 hours	0.0.0.0:80->80/tcp	web-server
def456ghi789	redis:alpine	"docker-entrypoint.s…"	1 hour ago	Up 1 hour	6379/tcp	cache-server"""

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

        # Execute docker_ps tool
        result = self.registry.execute_tool("docker_ps", {})

        # Verify successful execution
        assert result.success is True
        assert result.need_confirm is False
        assert "Found 2 running containers" in result.summary
        assert result.exit_code == 0
        assert result.elapsed_ms >= 0  # elapsed_ms is overridden by tool registry

        # Verify parsed container data
        assert "containers" in result.data
        containers = result.data["containers"]
        assert len(containers) == 2

        # Verify first container
        assert containers[0]["id"] == "abc123def456"
        assert containers[0]["image"] == "nginx:latest"
        assert containers[0]["names"] == "web-server"
        assert containers[0]["ports"] == "0.0.0.0:80->80/tcp"

        # Verify second container
        assert containers[1]["id"] == "def456ghi789"
        assert containers[1]["image"] == "redis:alpine"
        assert containers[1]["names"] == "cache-server"

        # Verify command was called correctly
        mock_execute.assert_called_once()
        call_args = mock_execute.call_args[1]
        assert call_args["command"][0] == "docker"
        assert call_args["command"][1] == "ps"
        assert "--format" in call_args["command"]

    @pytest.mark.integration
    @patch("burly_mcp.tools.registry.execute_with_timeout")
    def test_docker_ps_no_containers(self, mock_execute):
        """Test docker_ps with no running containers."""
        # Mock docker ps output with only header
        docker_output = "CONTAINER ID	IMAGE	COMMAND	CREATED	STATUS	PORTS	NAMES"

        mock_result = ExecutionResult(
            success=True,
            exit_code=0,
            stdout=docker_output,
            stderr="",
            timed_out=False,
            elapsed_ms=100,
            stdout_truncated=False,
            stderr_truncated=False,
            original_stdout_size=len(docker_output),
            original_stderr_size=0,
        )
        mock_execute.return_value = mock_result

        # Execute docker_ps tool
        result = self.registry.execute_tool("docker_ps", {})

        # Verify successful execution with no containers
        assert result.success is True
        assert "Found 0 running containers" in result.summary
        assert result.data["count"] == 0
        assert len(result.data["containers"]) == 0

    @pytest.mark.integration
    @patch("burly_mcp.tools.registry.execute_with_timeout")
    def test_docker_ps_permission_denied(self, mock_execute):
        """Test docker_ps with permission denied error."""
        mock_result = ExecutionResult(
            success=False,
            exit_code=1,
            stdout="",
            stderr="permission denied while trying to connect to the Docker daemon socket",
            timed_out=False,
            elapsed_ms=50,
            stdout_truncated=False,
            stderr_truncated=False,
            original_stdout_size=0,
            original_stderr_size=65,
        )
        mock_execute.return_value = mock_result

        # Execute docker_ps tool
        result = self.registry.execute_tool("docker_ps", {})

        # Verify error handling
        assert result.success is False
        assert "Docker access denied - check socket permissions" in result.summary
        assert result.exit_code == 1
        assert "permission denied" in result.data["error"]

    @pytest.mark.integration
    @patch("burly_mcp.tools.registry.execute_with_timeout")
    def test_docker_ps_daemon_not_running(self, mock_execute):
        """Test docker_ps when Docker daemon is not running."""
        mock_result = ExecutionResult(
            success=False,
            exit_code=1,
            stdout="",
            stderr="Cannot connect to the Docker daemon at unix:///var/run/docker.sock",
            timed_out=False,
            elapsed_ms=75,
            stdout_truncated=False,
            stderr_truncated=False,
            original_stdout_size=0,
            original_stderr_size=62,
        )
        mock_execute.return_value = mock_result

        # Execute docker_ps tool
        result = self.registry.execute_tool("docker_ps", {})

        # Verify error handling
        assert result.success is False
        assert "Cannot connect to Docker daemon - is Docker running?" in result.summary
        assert result.exit_code == 1

    @pytest.mark.integration
    @patch("burly_mcp.tools.registry.execute_with_timeout")
    def test_docker_ps_command_not_found(self, mock_execute):
        """Test docker_ps when Docker CLI is not installed."""
        mock_result = ExecutionResult(
            success=False,
            exit_code=127,
            stdout="",
            stderr="docker: command not found",
            timed_out=False,
            elapsed_ms=25,
            stdout_truncated=False,
            stderr_truncated=False,
            original_stdout_size=0,
            original_stderr_size=23,
        )
        mock_execute.return_value = mock_result

        # Execute docker_ps tool
        result = self.registry.execute_tool("docker_ps", {})

        # Verify error handling
        assert result.success is False
        assert "Docker CLI not found - is Docker installed?" in result.summary
        assert result.exit_code == 127

    @pytest.mark.integration
    @patch("burly_mcp.tools.registry.execute_with_timeout")
    def test_docker_ps_timeout(self, mock_execute):
        """Test docker_ps with command timeout."""
        mock_result = ExecutionResult(
            success=False,
            exit_code=124,  # timeout exit code
            stdout="",
            stderr="",
            timed_out=True,
            elapsed_ms=30000,  # 30 seconds
            stdout_truncated=False,
            stderr_truncated=False,
            original_stdout_size=0,
            original_stderr_size=0,
        )
        mock_execute.return_value = mock_result

        # Execute docker_ps tool
        result = self.registry.execute_tool("docker_ps", {})

        # Verify timeout handling
        assert result.success is False
        assert "Docker command timed out" in result.summary
        assert result.data["timed_out"] is True

    @pytest.mark.integration
    @patch("burly_mcp.tools.registry.execute_with_timeout")
    def test_docker_ps_output_truncation(self, mock_execute):
        """Test docker_ps with truncated output."""
        # Create large output that would be truncated
        large_output = "CONTAINER ID	IMAGE	COMMAND	CREATED	STATUS	PORTS	NAMES\n"
        large_output += 'abc123def456	nginx:latest	"/docker-entrypoint.…"	2 hours ago	Up 2 hours	0.0.0.0:80->80/tcp	web-server'

        mock_result = ExecutionResult(
            success=True,
            exit_code=0,
            stdout=large_output[:100] + "[truncated: output too long]",
            stderr="",
            timed_out=False,
            elapsed_ms=200,
            stdout_truncated=True,
            stderr_truncated=False,
            original_stdout_size=len(large_output),
            original_stderr_size=0,
        )
        mock_execute.return_value = mock_result

        # Execute docker_ps tool
        result = self.registry.execute_tool("docker_ps", {})

        # Verify truncation handling
        assert result.success is True
        assert "(output truncated)" in result.summary
        assert result.data["output_truncated"] is True
        assert result.data["original_output_size"] == len(large_output)


class TestFileSystemIntegration:
    """Integration tests for file system operations."""

    def setup_method(self):
        """Set up test environment for each test."""
        self.registry = ToolRegistry()

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

    @patch("burly_mcp.tools.registry.execute_with_timeout")
    def test_disk_space_success(self, mock_execute):
        """Test disk_space with successful filesystem listing."""
        # Mock successful df -hT output
        df_output = """Filesystem     Type      Size  Used Avail Use% Mounted on
/dev/sda1      ext4       20G  8.5G   11G  45% /
tmpfs          tmpfs     2.0G     0  2.0G   0% /dev/shm
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

        # Execute disk_space tool
        result = self.registry.execute_tool("disk_space", {})

        # Verify successful execution
        assert result.success is True
        assert result.need_confirm is False
        assert result.exit_code == 0
        assert result.elapsed_ms >= 0  # elapsed_ms is overridden by tool registry

        # Verify parsed filesystem data
        assert "filesystems" in result.data
        filesystems = result.data["filesystems"]
        assert len(filesystems) == 3

        # Verify root filesystem
        root_fs = filesystems[0]
        assert root_fs["filesystem"] == "/dev/sda1"
        assert root_fs["type"] == "ext4"
        assert root_fs["size"] == "20G"
        assert root_fs["used"] == "8.5G"
        assert root_fs["available"] == "11G"
        assert root_fs["use_percent"] == "45%"
        assert root_fs["usage_int"] == 45
        assert root_fs["mounted_on"] == "/"

        # Verify high usage detection
        assert "high_usage" in result.data
        high_usage_fs = result.data["high_usage"]
        assert len(high_usage_fs) == 1
        assert high_usage_fs[0]["mounted_on"] == "/home"
        assert high_usage_fs[0]["usage_int"] == 90

        # Verify summary includes warning
        assert "1 with >80% usage: /home" in result.summary

    @patch("burly_mcp.tools.registry.execute_with_timeout")
    def test_disk_space_healthy_usage(self, mock_execute):
        """Test disk_space with all filesystems having healthy usage."""
        # Mock df output with low usage
        df_output = """Filesystem     Type      Size  Used Avail Use% Mounted on
/dev/sda1      ext4       20G  4.0G   15G  25% /
tmpfs          tmpfs     2.0G     0  2.0G   0% /dev/shm
/dev/sda2      ext4      100G   30G   65G  32% /home"""

        mock_result = ExecutionResult(
            success=True,
            exit_code=0,
            stdout=df_output,
            stderr="",
            timed_out=False,
            elapsed_ms=100,
            stdout_truncated=False,
            stderr_truncated=False,
            original_stdout_size=len(df_output),
            original_stderr_size=0,
        )
        mock_execute.return_value = mock_result

        # Execute disk_space tool
        result = self.registry.execute_tool("disk_space", {})

        # Verify healthy usage summary
        assert result.success is True
        assert "all with healthy usage levels" in result.summary
        assert len(result.data["high_usage"]) == 0

    @patch("burly_mcp.tools.registry.execute_with_timeout")
    def test_disk_space_permission_denied(self, mock_execute):
        """Test disk_space with permission denied error."""
        mock_result = ExecutionResult(
            success=False,
            exit_code=1,
            stdout="",
            stderr="df: /restricted: Permission denied",
            timed_out=False,
            elapsed_ms=50,
            stdout_truncated=False,
            stderr_truncated=False,
            original_stdout_size=0,
            original_stderr_size=32,
        )
        mock_execute.return_value = mock_result

        # Execute disk_space tool
        result = self.registry.execute_tool("disk_space", {})

        # Verify error handling
        assert result.success is False
        assert "Permission denied accessing some filesystems" in result.summary
        assert result.exit_code == 1

    def test_blog_stage_markdown_valid_file(self, temp_dir):
        """Test blog_stage_markdown with valid Markdown file."""
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
            # Execute blog_stage_markdown tool
            result = self.registry.execute_tool(
                "blog_stage_markdown", {"file_path": "test-post.md"}
            )

        # Verify successful validation
        assert result.success is True
        assert result.need_confirm is False
        assert "Blog post validation passed" in result.summary
        assert result.exit_code == 0

        # Verify parsed front-matter
        assert "front_matter" in result.data
        front_matter = result.data["front_matter"]
        assert front_matter["title"] == "Test Blog Post"
        assert front_matter["date"] == "2024-01-15"
        assert front_matter["tags"] == ["test", "markdown"]
        assert front_matter["author"] == "Test Author"

        # Verify no validation errors
        assert len(result.data["validation_errors"]) == 0

    def test_blog_stage_markdown_missing_front_matter(self, temp_dir):
        """Test blog_stage_markdown with missing front-matter."""
        # Create blog post without front-matter
        blog_content = """# Test Blog Post

This is a test blog post without front-matter.
"""

        blog_file = temp_dir / "invalid-post.md"
        blog_file.write_text(blog_content)

        # Mock environment variable for staging root
        with patch.dict(os.environ, {"BLOG_STAGE_ROOT": str(temp_dir)}):
            # Execute blog_stage_markdown tool
            result = self.registry.execute_tool(
                "blog_stage_markdown", {"file_path": "invalid-post.md"}
            )

        # Verify validation failure
        assert result.success is False
        assert "Blog post validation failed" in result.summary
        assert result.exit_code == 1

        # Verify validation errors
        errors = result.data["validation_errors"]
        assert any(
            "Missing YAML front-matter start delimiter" in error for error in errors
        )

    def test_blog_stage_markdown_invalid_yaml(self, temp_dir):
        """Test blog_stage_markdown with invalid YAML syntax."""
        # Create blog post with invalid YAML
        blog_content = """---
title: "Test Blog Post
date: 2024-01-15
tags: [test, markdown
---

# Test Blog Post

This is a test blog post with invalid YAML.
"""

        blog_file = temp_dir / "invalid-yaml.md"
        blog_file.write_text(blog_content)

        # Mock environment variable for staging root
        with patch.dict(os.environ, {"BLOG_STAGE_ROOT": str(temp_dir)}):
            # Execute blog_stage_markdown tool
            result = self.registry.execute_tool(
                "blog_stage_markdown", {"file_path": "invalid-yaml.md"}
            )

        # Verify validation failure
        assert result.success is False
        assert "Blog post validation failed" in result.summary

        # Verify YAML syntax error
        errors = result.data["validation_errors"]
        assert any("Invalid YAML syntax" in error for error in errors)

    def test_blog_stage_markdown_missing_required_fields(self, temp_dir):
        """Test blog_stage_markdown with missing required fields."""
        # Create blog post missing required fields
        blog_content = """---
title: "Test Blog Post"
# Missing date and tags
---

# Test Blog Post

This is a test blog post missing required fields.
"""

        blog_file = temp_dir / "missing-fields.md"
        blog_file.write_text(blog_content)

        # Mock environment variable for staging root
        with patch.dict(os.environ, {"BLOG_STAGE_ROOT": str(temp_dir)}):
            # Execute blog_stage_markdown tool
            result = self.registry.execute_tool(
                "blog_stage_markdown", {"file_path": "missing-fields.md"}
            )

        # Verify validation failure
        assert result.success is False
        assert "Blog post validation failed" in result.summary

        # Verify missing field errors
        errors = result.data["validation_errors"]
        assert "Missing required field: date" in errors
        assert "Missing required field: tags" in errors

    def test_blog_stage_markdown_path_traversal_protection(self):
        """Test blog_stage_markdown path traversal protection."""
        # Mock environment variable for staging root
        with patch.dict(os.environ, {"BLOG_STAGE_ROOT": "/app/blog/stage"}):
            # Execute blog_stage_markdown tool with path traversal attempt
            result = self.registry.execute_tool(
                "blog_stage_markdown", {"file_path": "../../../etc/passwd"}
            )

        # Verify security violation (may be caught at different levels)
        assert result.success is False
        assert (
            "Path traversal detected" in result.summary
            or "outside staging directory" in result.summary
            or "Permission denied" in result.summary
        )
        assert result.exit_code == 1

    def test_blog_stage_markdown_file_not_found(self, temp_dir):
        """Test blog_stage_markdown with non-existent file."""
        # Mock environment variable for staging root
        with patch.dict(os.environ, {"BLOG_STAGE_ROOT": str(temp_dir)}):
            # Execute blog_stage_markdown tool with non-existent file
            result = self.registry.execute_tool(
                "blog_stage_markdown", {"file_path": "nonexistent.md"}
            )

        # Verify file not found error
        assert result.success is False
        assert "File not found" in result.summary
        assert result.exit_code == 2

    def test_blog_publish_static_confirmation_required(self, temp_dir):
        """Test blog_publish_static requires confirmation."""
        # Create staging and publish directories
        stage_dir = temp_dir / "stage"
        publish_dir = temp_dir / "publish"
        stage_dir.mkdir()
        publish_dir.mkdir()

        # Create a test file in staging
        test_file = stage_dir / "test.md"
        test_file.write_text("# Test Content")

        # Mock environment variables
        with patch.dict(
            os.environ,
            {"BLOG_STAGE_ROOT": str(stage_dir), "BLOG_PUBLISH_ROOT": str(publish_dir)},
        ):
            # Execute blog_publish_static without confirmation
            result = self.registry.execute_tool(
                "blog_publish_static", {"pattern": "*.md"}
            )

        # Verify confirmation is required
        # Note: success can be False when confirmation is needed
        assert result.need_confirm is True
        assert (
            "Ready to publish" in result.summary
            or "confirmation" in result.summary.lower()
            or "requires confirmation" in result.summary.lower()
        )

    def test_blog_publish_static_with_confirmation(self, temp_dir):
        """Test blog_publish_static with confirmation provided."""
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
            # Execute blog_publish_static with confirmation
            result = self.registry.execute_tool(
                "blog_publish_static", {"pattern": "*.md", "_confirm": True}
            )

        # Verify successful publication
        assert result.success is True
        assert result.need_confirm is False
        assert (
            "published" in result.summary.lower() or "copied" in result.summary.lower()
        )

        # Verify files were copied
        assert (publish_dir / "post1.md").exists()
        assert (publish_dir / "post2.md").exists()
        assert (publish_dir / "post1.md").read_text() == "# Post 1"
        assert (publish_dir / "post2.md").read_text() == "# Post 2"

        # Verify data includes file count
        if "files_written" in result.data:
            assert result.data["files_written"] >= 2


@pytest.mark.integration
class TestGotifyIntegration:
    """Integration tests for Gotify API operations."""

    def setup_method(self):
        """Set up test environment for each test."""
        self.registry = ToolRegistry()

        # Patch audit and notification systems for all tests
        self.audit_patcher = patch("burly_mcp.tools.registry.log_tool_execution")
        self.notify_success_patcher = patch("burly_mcp.tools.registry.notify_tool_success")
        self.notify_failure_patcher = patch("burly_mcp.tools.registry.notify_tool_failure")

        self.mock_audit = self.audit_patcher.start()
        self.mock_notify_success = self.notify_success_patcher.start()
        self.mock_notify_failure = self.notify_failure_patcher.start()

    def teardown_method(self):
        """Clean up after each test."""
        self.audit_patcher.stop()
        self.notify_success_patcher.stop()
        self.notify_failure_patcher.stop()

    @pytest.mark.integration
    @patch("urllib.request.urlopen")
    def test_gotify_ping_success(self, mock_urlopen):
        """Test gotify_ping with successful API response."""
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
            # Execute gotify_ping tool
            result = self.registry.execute_tool(
                "gotify_ping", {"message": "Test notification"}
            )

        # Verify successful execution
        assert result.success is True
        assert result.need_confirm is False
        assert "Gotify notification sent successfully" in result.summary
        assert result.exit_code == 0

        # Verify API response data
        assert "message_id" in result.data
        assert result.data["message_id"] == 123
        assert result.data["message"] == "Test notification"
        assert result.data["title"] == "Burly MCP Test"
        assert result.data["priority"] == 3

        # Verify HTTP request was made correctly
        mock_urlopen.assert_called_once()
        call_args = mock_urlopen.call_args[0][0]  # Get the Request object
        assert call_args.full_url == "http://localhost:8080/message"
        assert call_args.get_method() == "POST"

    @pytest.mark.integration
    @patch("urllib.request.urlopen")
    def test_gotify_ping_authentication_error(self, mock_urlopen):
        """Test gotify_ping with authentication error."""
        # Mock HTTP 401 error
        from urllib.error import HTTPError

        mock_urlopen.side_effect = HTTPError(
            url="http://localhost:8080/message",
            code=401,
            msg="Unauthorized",
            hdrs={},
            fp=None,
        )

        # Mock environment variables
        with patch.dict(
            os.environ,
            {"GOTIFY_URL": "http://localhost:8080", "GOTIFY_TOKEN": "invalid_token"},
        ):
            # Execute gotify_ping tool
            result = self.registry.execute_tool(
                "gotify_ping", {"message": "Test notification"}
            )

        # Verify authentication error handling
        assert result.success is False
        assert (
            "Authentication failed" in result.summary
            or "401" in result.summary
            or "authentication failed" in result.summary.lower()
        )
        assert result.exit_code != 0

    @pytest.mark.integration
    @patch("urllib.request.urlopen")
    def test_gotify_ping_server_error(self, mock_urlopen):
        """Test gotify_ping with server error."""
        # Mock HTTP 500 error
        from urllib.error import HTTPError

        mock_urlopen.side_effect = HTTPError(
            url="http://localhost:8080/message",
            code=500,
            msg="Internal Server Error",
            hdrs={},
            fp=None,
        )

        # Mock environment variables
        with patch.dict(
            os.environ,
            {"GOTIFY_URL": "http://localhost:8080", "GOTIFY_TOKEN": "test_token"},
        ):
            # Execute gotify_ping tool
            result = self.registry.execute_tool(
                "gotify_ping", {"message": "Test notification"}
            )

        # Verify server error handling
        assert result.success is False
        assert "server error" in result.summary.lower() or "500" in result.summary
        assert result.exit_code != 0

    @pytest.mark.integration
    @patch("urllib.request.urlopen")
    def test_gotify_ping_network_error(self, mock_urlopen):
        """Test gotify_ping with network connectivity error."""
        # Mock network error
        from urllib.error import URLError

        mock_urlopen.side_effect = URLError("Connection refused")

        # Mock environment variables
        with patch.dict(
            os.environ,
            {"GOTIFY_URL": "http://unreachable:8080", "GOTIFY_TOKEN": "test_token"},
        ):
            # Execute gotify_ping tool
            result = self.registry.execute_tool(
                "gotify_ping", {"message": "Test notification"}
            )

        # Verify network error handling
        assert result.success is False
        assert (
            "network error" in result.summary.lower()
            or "connection" in result.summary.lower()
        )
        assert result.exit_code != 0

    @pytest.mark.integration
    def test_gotify_ping_missing_configuration(self):
        """Test gotify_ping with missing configuration."""
        # Execute gotify_ping without environment variables
        with patch.dict(os.environ, {}, clear=True):
            # Clear feature detector cache to ensure fresh configuration check
            from burly_mcp.feature_detection import get_feature_detector
            feature_detector = get_feature_detector()
            feature_detector.clear_cache()
            
            result = self.registry.execute_tool(
                "gotify_ping", {"message": "Test notification"}
            )

        # Verify configuration error
        assert result.success is False
        assert (
            "configuration" in result.summary.lower()
            or "not configured" in result.summary.lower()
        )
        assert result.exit_code != 0

    @pytest.mark.integration
    @patch("urllib.request.urlopen")
    def test_gotify_ping_custom_priority(self, mock_urlopen):
        """Test gotify_ping with custom priority level."""
        # Mock successful HTTP response
        mock_response = Mock()
        mock_response.read.return_value = (
            b'{"id": 124, "message": "High priority message"}'
        )
        mock_response.getcode.return_value = 200
        mock_urlopen.return_value.__enter__.return_value = mock_response

        # Mock environment variables
        with patch.dict(
            os.environ,
            {"GOTIFY_URL": "http://localhost:8080", "GOTIFY_TOKEN": "test_token"},
        ):
            # Clear feature detector cache to ensure fresh configuration check
            from burly_mcp.feature_detection import get_feature_detector
            feature_detector = get_feature_detector()
            feature_detector.clear_cache()
            
            # Execute gotify_ping tool with custom priority
            result = self.registry.execute_tool(
                "gotify_ping", {"message": "High priority notification", "priority": 8}
            )

        # Verify successful execution
        assert result.success is True
        assert "Gotify notification sent successfully" in result.summary

        # Verify priority was included in request
        mock_urlopen.assert_called_once()
        call_args = mock_urlopen.call_args[0][0]  # Get the Request object

        # Parse the request data to verify priority
        request_data = json.loads(call_args.data.decode("utf-8"))
        assert request_data["priority"] == 8
        assert request_data["message"] == "High priority notification"

    @pytest.mark.integration
    @patch("urllib.request.urlopen")
    def test_gotify_ping_invalid_json_response(self, mock_urlopen):
        """Test gotify_ping with invalid JSON response."""
        # Mock response with invalid JSON
        mock_response = Mock()
        mock_response.read.return_value = b"Invalid JSON response"
        mock_response.getcode.return_value = 200
        mock_urlopen.return_value.__enter__.return_value = mock_response

        # Mock environment variables
        with patch.dict(
            os.environ,
            {"GOTIFY_URL": "http://localhost:8080", "GOTIFY_TOKEN": "test_token"},
        ):
            # Execute gotify_ping tool
            result = self.registry.execute_tool(
                "gotify_ping", {"message": "Test notification"}
            )

        # Verify JSON parsing - tool may succeed even with invalid JSON response
        # The tool considers HTTP 200 as success regardless of response format
        assert result.success is True  # Tool succeeds on HTTP 200
        assert (
            result.data["message_id"] is None
        )  # But message_id will be None due to JSON parse failure


class TestToolRegistryIntegration:
    """Integration tests for the complete tool registry system."""

    def setup_method(self):
        """Set up test environment for each test."""
        self.registry = ToolRegistry()

        # Patch audit and notification systems for all tests
        self.audit_patcher = patch("burly_mcp.tools.registry.log_tool_execution")
        self.notify_success_patcher = patch("burly_mcp.tools.registry.notify_tool_success")
        self.notify_failure_patcher = patch("burly_mcp.tools.registry.notify_tool_failure")

        self.mock_audit = self.audit_patcher.start()
        self.mock_notify_success = self.notify_success_patcher.start()
        self.mock_notify_failure = self.notify_failure_patcher.start()

    def teardown_method(self):
        """Clean up after each test."""
        self.audit_patcher.stop()
        self.notify_success_patcher.stop()
        self.notify_failure_patcher.stop()

    def test_unknown_tool_execution(self):
        """Test execution of unknown tool."""
        result = self.registry.execute_tool("nonexistent_tool", {})

        # Verify error handling
        assert result.success is False
        assert "Unknown tool: nonexistent_tool" in result.summary
        assert result.exit_code == 1

        # Verify available tools are listed
        assert "available_tools" in result.data
        available_tools = result.data["available_tools"]
        expected_tools = [
            "docker_ps",
            "disk_space",
            "blog_stage_markdown",
            "blog_publish_static",
            "gotify_ping",
        ]
        for tool in expected_tools:
            assert tool in available_tools

    def test_tool_execution_audit_and_notification(self, mock_audit_and_notifications):
        """Test that tool execution triggers audit logging and notifications."""
        # Mock successful docker_ps execution
        with patch("burly_mcp.tools.registry.execute_with_timeout") as mock_execute:
            mock_result = ExecutionResult(
                success=True,
                exit_code=0,
                stdout="CONTAINER ID	IMAGE	COMMAND	CREATED	STATUS	PORTS	NAMES",
                stderr="",
                timed_out=False,
                elapsed_ms=100,
                stdout_truncated=False,
                stderr_truncated=False,
                original_stdout_size=50,
                original_stderr_size=0,
            )
            mock_execute.return_value = mock_result

            # Execute tool
            result = self.registry.execute_tool("docker_ps", {})

        # Verify successful execution
        assert result.success is True

        # Verify audit logging was called (mocked in setup)
        mock_audit_and_notifications["audit"].assert_called_once()
        audit_call = mock_audit_and_notifications["audit"].call_args[1]
        assert audit_call["tool_name"] == "docker_ps"
        assert audit_call["status"] == "ok"
        assert audit_call["mutates"] is False
        assert audit_call["requires_confirm"] is False

        # Verify notification was sent (mocked in setup)
        mock_audit_and_notifications["notify_success"].assert_called_once()
        notify_call = mock_audit_and_notifications["notify_success"].call_args[0]
        assert notify_call[0] == "docker_ps"  # tool_name
        assert "Found 0 running containers" in notify_call[1]  # summary

    def test_tool_execution_failure_audit_and_notification(
        self, mock_audit_and_notifications
    ):
        """Test that failed tool execution triggers appropriate audit and notifications."""
        # Mock failed docker_ps execution
        with patch("burly_mcp.tools.registry.execute_with_timeout") as mock_execute:
            mock_result = ExecutionResult(
                success=False,
                exit_code=1,
                stdout="",
                stderr="permission denied",
                timed_out=False,
                elapsed_ms=50,
                stdout_truncated=False,
                stderr_truncated=False,
                original_stdout_size=0,
                original_stderr_size=17,
            )
            mock_execute.return_value = mock_result

            # Execute tool
            result = self.registry.execute_tool("docker_ps", {})

        # Verify failed execution
        assert result.success is False

        # Verify audit logging was called with failure status (mocked in setup)
        mock_audit_and_notifications["audit"].assert_called_once()
        audit_call = mock_audit_and_notifications["audit"].call_args[1]
        assert audit_call["tool_name"] == "docker_ps"
        assert audit_call["status"] == "fail"
        assert audit_call["exit_code"] == 1

        # Verify failure notification was sent (mocked in setup)
        mock_audit_and_notifications["notify_failure"].assert_called_once()
        notify_call = mock_audit_and_notifications["notify_failure"].call_args[0]
        assert notify_call[0] == "docker_ps"  # tool_name
        assert notify_call[2] == 1  # exit_code

    def test_tool_characteristics_lookup(self):
        """Test tool characteristics are correctly identified."""
        # Test read-only tools
        assert self.registry._tool_mutates("docker_ps") is False
        assert self.registry._tool_requires_confirm("docker_ps") is False
        assert self.registry._tool_mutates("disk_space") is False
        assert self.registry._tool_requires_confirm("disk_space") is False

        # Test mutating tool
        assert self.registry._tool_mutates("blog_publish_static") is True
        assert self.registry._tool_requires_confirm("blog_publish_static") is True

        # Test non-existent tool (should return defaults)
        assert self.registry._tool_mutates("nonexistent") is False
        assert self.registry._tool_requires_confirm("nonexistent") is False
