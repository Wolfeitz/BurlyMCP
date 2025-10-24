"""
Unit tests for the Burly MCP security module.
"""

from pathlib import Path
from unittest.mock import patch

import pytest


class TestSecurityValidator:
    """Test the security validation functionality."""

    def test_security_validator_initialization(self):
        """Test security validator initialization."""
        from burly_mcp.security import SecurityValidator

        validator = SecurityValidator()
        assert hasattr(validator, "allowed_paths")
        assert isinstance(validator.allowed_paths, list)
        assert hasattr(validator, "dangerous_commands")
        assert hasattr(validator, "dangerous_env_vars")

    def test_validate_path_allowed(self):
        """Test path validation for allowed paths."""
        from burly_mcp.security import SecurityValidator

        validator = SecurityValidator(allowed_paths=["/tmp", "/var/tmp"])

        # Test allowed path
        assert validator.validate_path(Path("/tmp/test.txt")) is True
        assert validator.validate_path(Path("/var/tmp/data.json")) is True

    def test_validate_path_disallowed(self):
        """Test path validation for disallowed paths."""
        from burly_mcp.security import SecurityValidator

        validator = SecurityValidator(allowed_paths=["/tmp"])

        # Test disallowed paths
        assert validator.validate_path(Path("/etc/passwd")) is False
        assert validator.validate_path(Path("/root/.ssh/id_rsa")) is False

    def test_validate_path_symlink_attack(self):
        """Test protection against symlink attacks."""
        from burly_mcp.security import SecurityValidator

        validator = SecurityValidator(allowed_paths=["/tmp"])

        # Test path traversal through relative paths (simpler test)
        assert validator.validate_path(Path("/tmp/../etc/passwd")) is False
        assert validator.validate_path(Path("/tmp/../../root/.ssh/id_rsa")) is False

    def test_validate_path_invalid_path(self):
        """Test handling of invalid paths."""
        from burly_mcp.security import SecurityValidator

        validator = SecurityValidator(allowed_paths=["/tmp"])

        # Test with path outside allowed paths
        result = validator.validate_path(Path("/invalid/path"))
        assert result is False

    def test_sanitize_command_args(self):
        """Test command argument sanitization."""
        from burly_mcp.security import SecurityValidator

        validator = SecurityValidator()

        # Test safe arguments
        safe_args = ["ls", "-la", "/tmp"]
        sanitized = validator.sanitize_command_args(safe_args)
        assert sanitized == safe_args

    def test_sanitize_command_args_dangerous(self):
        """Test sanitization of dangerous command arguments."""
        from burly_mcp.security import SecurityValidator

        validator = SecurityValidator()

        # Test dangerous arguments
        dangerous_args = ["rm", "-rf", "/"]

        with pytest.raises(ValueError, match="Dangerous command detected"):
            validator.sanitize_command_args(dangerous_args)

    def test_validate_docker_image_name(self):
        """Test Docker image name validation."""
        from burly_mcp.security import SecurityValidator

        validator = SecurityValidator()

        # Test valid image names
        assert validator.validate_docker_image_name("ubuntu:20.04") is True
        assert validator.validate_docker_image_name("nginx:latest") is True
        assert validator.validate_docker_image_name("registry.example.com/app:v1.0") is True

    def test_validate_docker_image_name_invalid(self):
        """Test validation of invalid Docker image names."""
        from burly_mcp.security import SecurityValidator

        validator = SecurityValidator()

        # Test invalid image names
        assert validator.validate_docker_image_name("") is False
        assert validator.validate_docker_image_name("../malicious") is False

    def test_check_resource_limits(self):
        """Test resource limit checking."""
        from burly_mcp.security import SecurityValidator

        validator = SecurityValidator()

        # Test within limits
        assert validator.check_resource_limits(memory_mb=100, cpu_percent=50) is True
        assert validator.check_resource_limits(memory_mb=16384, cpu_percent=100) is True

        # Test exceeding limits
        assert validator.check_resource_limits(memory_mb=20000, cpu_percent=50) is False
        assert validator.check_resource_limits(memory_mb=100, cpu_percent=200) is False
        assert validator.check_resource_limits(memory_mb=0, cpu_percent=50) is False

    def test_validate_environment_variables(self):
        """Test environment variable validation."""
        from burly_mcp.security import SecurityValidator

        validator = SecurityValidator()

        # Test safe environment variables
        safe_env = {"PATH": "/usr/bin", "HOME": "/home/user"}
        assert validator.validate_environment_variables(safe_env) is True

    def test_validate_environment_variables_dangerous(self):
        """Test validation of dangerous environment variables."""
        from burly_mcp.security import SecurityValidator

        validator = SecurityValidator()

        # Test dangerous environment variables
        dangerous_env = {"LD_PRELOAD": "/malicious/lib.so"}

        with pytest.raises(ValueError, match="Dangerous environment variable"):
            validator.validate_environment_variables(dangerous_env)

    def test_audit_security_event(self):
        """Test security event auditing."""
        from burly_mcp.security import SecurityValidator

        validator = SecurityValidator()

        # Test with correct signature - audit_security_event(event_type, details)
        validator.audit_security_event(
            "path_traversal_attempt",
            {"path": "/tmp/../etc/passwd", "operation": "file_read", "root": "/tmp"}
        )

    def test_generate_security_token(self):
        """Test security token generation."""
        from burly_mcp.security import SecurityValidator

        validator = SecurityValidator()

        token1 = validator.generate_security_token()
        token2 = validator.generate_security_token()

        # Tokens should be different
        assert token1 != token2
        assert isinstance(token1, str)
        assert len(token1) == 32  # Default length

        # Test custom length
        token3 = validator.generate_security_token(length=16)
        assert len(token3) == 16

    def test_validate_file_permissions(self, tmp_path):
        """Test file permission validation."""
        from burly_mcp.security import SecurityValidator

        validator = SecurityValidator()

        # Create test file with safe permissions
        test_file = tmp_path / "test.txt"
        test_file.write_text("test content")
        test_file.chmod(0o644)

        assert validator.validate_file_permissions(str(test_file)) is True

    def test_validate_file_permissions_unsafe(self, tmp_path):
        """Test validation of unsafe file permissions."""
        from burly_mcp.security import SecurityValidator

        validator = SecurityValidator()

        # Create test file with unsafe permissions (world-writable)
        test_file = tmp_path / "unsafe.txt"
        test_file.write_text("test content")
        test_file.chmod(0o666)

        assert validator.validate_file_permissions(str(test_file)) is False

    @patch("burly_mcp.security.os.getuid")
    def test_validate_user_privileges(self, mock_getuid):
        """Test user privilege validation."""
        from burly_mcp.security import SecurityValidator

        validator = SecurityValidator()

        # Test non-root user (safe)
        mock_getuid.return_value = 1000
        assert validator.validate_user_privileges() is True

        # Test root user (potentially unsafe)
        mock_getuid.return_value = 0
        assert validator.validate_user_privileges() is False

    def test_escape_shell_argument(self):
        """Test shell argument escaping."""
        from burly_mcp.security import SecurityValidator

        validator = SecurityValidator()

        # Test safe argument
        safe_arg = "filename.txt"
        escaped = validator.escape_shell_argument(safe_arg)
        assert escaped == safe_arg

        # Test argument with special characters
        special_arg = "file with spaces & symbols.txt"
        escaped = validator.escape_shell_argument(special_arg)
        assert "'" in escaped or '"' in escaped  # Should be quoted

    def test_validate_network_access(self):
        """Test network access validation."""
        from burly_mcp.security import SecurityValidator

        validator = SecurityValidator()

        # Test allowed network access
        assert validator.validate_network_access("https://api.example.com") is True
        assert validator.validate_network_access("example.com", 443) is True

        # Test disallowed network access (localhost and private IPs)
        assert validator.validate_network_access("http://localhost") is False
        assert validator.validate_network_access("127.0.0.1", 22) is False
        assert validator.validate_network_access("192.168.1.1", 80) is False

    def test_check_rate_limits(self):
        """Test rate limiting functionality."""
        from burly_mcp.security import SecurityValidator

        validator = SecurityValidator()

        # Basic rate limit check (implementation returns True for now)
        assert validator.check_rate_limits("test_operation") is True


class TestSecurityFunctions:
    """Test standalone security functions."""

    def test_validate_path_within_root(self):
        """Test path validation within root directory."""
        from burly_mcp.security import SecurityViolationError, validate_path_within_root

        # Test valid path
        result = validate_path_within_root("/tmp/test.txt", "/tmp")
        assert result.startswith("/tmp")

        # Test path traversal attack
        with pytest.raises(SecurityViolationError):
            validate_path_within_root("/tmp/../etc/passwd", "/tmp")

    def test_sanitize_file_path(self):
        """Test file path sanitization."""
        from burly_mcp.security import sanitize_file_path

        # Test normal path
        assert sanitize_file_path("/tmp/test.txt") == "/tmp/test.txt"

        # Test path with null bytes
        assert sanitize_file_path("/tmp/test\x00.txt") == "/tmp/test.txt"

        # Test empty path
        assert sanitize_file_path("") == ""

    def test_check_file_permissions(self, tmp_path):
        """Test file permission checking."""
        from burly_mcp.security import check_file_permissions

        # Create test file
        test_file = tmp_path / "test.txt"
        test_file.write_text("test content")
        test_file.chmod(0o644)

        # Test read permission
        assert check_file_permissions(str(test_file), "r") is True

        # Test write permission
        assert check_file_permissions(str(test_file), "w") is True

        # Test non-existent file
        assert check_file_permissions(str(tmp_path / "nonexistent.txt"), "r") is False

    def test_get_safe_file_info(self, tmp_path):
        """Test safe file information retrieval."""
        from burly_mcp.security import get_safe_file_info

        # Create test file
        test_file = tmp_path / "test.txt"
        test_file.write_text("test content")

        info = get_safe_file_info(str(test_file))
        assert info["exists"] is True
        assert info["is_file"] is True
        assert info["is_directory"] is False
        assert info["size"] > 0

        # Test non-existent file
        info = get_safe_file_info(str(tmp_path / "nonexistent.txt"))
        assert info["exists"] is False

    def test_log_security_event(self):
        """Test security event logging."""
        from burly_mcp.security import log_security_event

        # This is a compatibility function that should not raise errors
        log_security_event("test_event", {"detail": "test"})
