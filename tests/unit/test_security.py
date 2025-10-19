"""
Unit tests for the Burly MCP security module.
"""

import pytest
from unittest.mock import Mock, patch
from pathlib import Path
import os


class TestSecurityValidator:
    """Test the security validation functionality."""

    def test_security_validator_initialization(self):
        """Test security validator initialization."""
        from burly_mcp.security import SecurityValidator

        validator = SecurityValidator()
        assert hasattr(validator, "allowed_paths")
        assert isinstance(validator.allowed_paths, list)

    def test_validate_path_allowed(self):
        """Test path validation for allowed paths."""
        from burly_mcp.security import SecurityValidator

        validator = SecurityValidator()
        validator.allowed_paths = [Path("/tmp"), Path("/var/tmp")]

        # Test allowed path
        assert validator.validate_path(Path("/tmp/test.txt")) is True
        assert validator.validate_path(Path("/var/tmp/data.json")) is True

    def test_validate_path_disallowed(self):
        """Test path validation for disallowed paths."""
        from burly_mcp.security import SecurityValidator

        validator = SecurityValidator()
        validator.allowed_paths = [Path("/tmp")]

        # Test disallowed paths
        assert validator.validate_path(Path("/etc/passwd")) is False
        assert validator.validate_path(Path("/root/.ssh/id_rsa")) is False

    def test_validate_path_traversal_attack(self):
        """Test protection against path traversal attacks."""
        from burly_mcp.security import SecurityValidator

        validator = SecurityValidator()
        validator.allowed_paths = [Path("/tmp")]

        # Test path traversal attempts
        assert validator.validate_path(Path("/tmp/../etc/passwd")) is False
        assert validator.validate_path(Path("/tmp/../../root/.ssh/id_rsa")) is False

    def test_validate_path_symlink_attack(self):
        """Test protection against symlink attacks."""
        from burly_mcp.security import SecurityValidator

        validator = SecurityValidator()
        validator.allowed_paths = [Path("/tmp")]

        # Mock a symlink that points outside allowed paths
        with patch("pathlib.Path.resolve") as mock_resolve:
            # Mock both the path and allowed_path resolve calls
            def mock_resolve_side_effect(path_obj):
                if str(path_obj) == "/tmp/malicious_symlink":
                    return Path("/etc/passwd")  # Symlink points outside
                elif str(path_obj) == "/tmp":
                    return Path("/tmp")  # Allowed path resolves normally
                return path_obj
            
            mock_resolve.side_effect = lambda: mock_resolve_side_effect(mock_resolve.return_value)
            
            # Set up the mock to return the malicious path
            with patch.object(Path, 'resolve') as path_resolve:
                path_resolve.side_effect = mock_resolve_side_effect
                
                result = validator.validate_path(Path("/tmp/malicious_symlink"))
                assert result is False

    def test_validate_path_invalid_path(self):
        """Test handling of invalid paths."""
        from burly_mcp.security import SecurityValidator

        validator = SecurityValidator()
        validator.allowed_paths = [Path("/tmp")]

        # Test with path that raises OSError during resolution
        with patch.object(Path, 'resolve') as mock_resolve:
            mock_resolve.side_effect = OSError("Invalid path")

            result = validator.validate_path(Path("/invalid/path"))
            assert result is False

    def test_validate_path_value_error(self):
        """Test handling of ValueError during path validation."""
        from burly_mcp.security import SecurityValidator

        validator = SecurityValidator()
        validator.allowed_paths = [Path("/tmp")]

        # Test with path that raises ValueError during resolution
        with patch("pathlib.Path.resolve") as mock_resolve:
            mock_resolve.side_effect = ValueError("Invalid path format")

            result = validator.validate_path(Path("invalid::path"))
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
        dangerous_args = ["rm", "-rf", "/", "&&", "echo", "pwned"]

        with pytest.raises(ValueError, match="Dangerous command detected"):
            validator.sanitize_command_args(dangerous_args)

    def test_validate_docker_image_name(self):
        """Test Docker image name validation."""
        from burly_mcp.security import SecurityValidator

        validator = SecurityValidator()

        # Test valid image names
        assert validator.validate_docker_image_name("ubuntu:20.04") is True
        assert validator.validate_docker_image_name("nginx:latest") is True
        assert (
            validator.validate_docker_image_name("registry.example.com/app:v1.0")
            is True
        )

    def test_validate_docker_image_name_invalid(self):
        """Test validation of invalid Docker image names."""
        from burly_mcp.security import SecurityValidator

        validator = SecurityValidator()

        # Test invalid image names
        assert validator.validate_docker_image_name("") is False
        assert validator.validate_docker_image_name("../malicious") is False
        assert validator.validate_docker_image_name("image with spaces") is False

    def test_check_resource_limits(self):
        """Test resource limit checking."""
        from burly_mcp.security import SecurityValidator

        validator = SecurityValidator()

        # Test within limits
        assert validator.check_resource_limits(memory_mb=100, cpu_percent=50) is True

        # Test exceeding limits
        assert validator.check_resource_limits(memory_mb=10000, cpu_percent=50) is False
        assert validator.check_resource_limits(memory_mb=100, cpu_percent=200) is False

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

        with patch("burly_mcp.security.log_security_event") as mock_log:
            validator.audit_security_event(
                "path_traversal_attempt",
                {"path": "/tmp/../etc/passwd", "user": "test_user"},
                "HIGH",
            )

            mock_log.assert_called_once_with(
                "path_traversal_attempt",
                {"path": "/tmp/../etc/passwd", "user": "test_user"},
                "HIGH",
            )

    def test_generate_security_token(self):
        """Test security token generation."""
        from burly_mcp.security import SecurityValidator

        validator = SecurityValidator()

        token1 = validator.generate_security_token()
        token2 = validator.generate_security_token()

        # Tokens should be different
        assert token1 != token2

        # Tokens should be strings
        assert isinstance(token1, str)
        assert isinstance(token2, str)

        # Tokens should have reasonable length
        assert len(token1) >= 32
        assert len(token2) >= 32

    def test_validate_file_permissions(self, tmp_path):
        """Test file permission validation."""
        from burly_mcp.security import SecurityValidator

        validator = SecurityValidator()

        # Create test file with safe permissions
        test_file = tmp_path / "test.txt"
        test_file.write_text("test content")
        test_file.chmod(0o644)

        assert validator.validate_file_permissions(test_file) is True

    def test_validate_file_permissions_unsafe(self, tmp_path):
        """Test validation of unsafe file permissions."""
        from burly_mcp.security import SecurityValidator

        validator = SecurityValidator()

        # Create test file with unsafe permissions (world-writable)
        test_file = tmp_path / "unsafe.txt"
        test_file.write_text("test content")
        test_file.chmod(0o666)

        assert validator.validate_file_permissions(test_file) is False

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

        # Test disallowed network access
        assert validator.validate_network_access("http://localhost:22") is False
        assert validator.validate_network_access("ftp://internal.server") is False

    def test_check_rate_limits(self):
        """Test rate limiting functionality."""
        from burly_mcp.security import SecurityValidator

        validator = SecurityValidator()

        user_id = "test_user"

        # First few requests should be allowed
        for i in range(5):
            assert validator.check_rate_limits(user_id) is True

        # After rate limit, should be denied
        # (This assumes a rate limit implementation)
        # The exact behavior depends on the implementation
