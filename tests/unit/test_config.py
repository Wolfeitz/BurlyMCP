"""
Unit tests for the Burly MCP configuration module.
"""

import pytest
from unittest.mock import Mock, patch
from pathlib import Path
import os


class TestConfig:
    """Test the configuration management."""

    @patch.dict(os.environ, {}, clear=True)
    def test_config_defaults(self):
        """Test configuration with default values."""
        from burly_mcp.config import Config

        config = Config()

        # Test default paths
        assert config.config_dir == Path("/app/config")
        assert config.log_dir == Path("/var/log/agentops")

        # Test default Docker settings
        assert config.docker_socket == "/var/run/docker.sock"
        assert config.docker_timeout == 30

        # Test default security settings
        assert config.max_output_size == 1048576
        assert config.audit_enabled is True

    @patch.dict(
        os.environ,
        {
            "BURLY_CONFIG_DIR": "/custom/config",
            "BURLY_LOG_DIR": "/custom/logs",
            "DOCKER_SOCKET": "/custom/docker.sock",
            "DOCKER_TIMEOUT": "60",
            "MAX_OUTPUT_SIZE": "2097152",
            "AUDIT_ENABLED": "false",
        },
    )
    def test_config_from_environment(self):
        """Test configuration from environment variables."""
        from burly_mcp.config import Config

        config = Config()

        assert config.config_dir == Path("/custom/config")
        assert config.log_dir == Path("/custom/logs")
        assert config.docker_socket == "/custom/docker.sock"
        assert config.docker_timeout == 60
        assert config.max_output_size == 2097152
        assert config.audit_enabled is False

    @patch.dict(
        os.environ,
        {
            "GOTIFY_URL": "https://gotify.example.com",
            "GOTIFY_TOKEN": "test_token_123",
        },
    )
    def test_config_notification_settings(self):
        """Test notification configuration."""
        from burly_mcp.config import Config

        config = Config()

        assert config.gotify_url == "https://gotify.example.com"
        assert config.gotify_token == "test_token_123"

    @patch.dict(
        os.environ,
        {
            "BLOG_STAGE_ROOT": "/custom/blog/stage",
            "BLOG_PUBLISH_ROOT": "/custom/blog/publish",
        },
    )
    def test_config_blog_settings(self):
        """Test blog configuration."""
        from burly_mcp.config import Config

        config = Config()

        assert config.blog_stage_root == Path("/custom/blog/stage")
        assert config.blog_publish_root == Path("/custom/blog/publish")

    def test_config_validation_success(self, tmp_path):
        """Test successful configuration validation."""
        from burly_mcp.config import Config

        # Create required directories and files
        config_dir = tmp_path / "config"
        config_dir.mkdir()
        policy_dir = config_dir / "policy"
        policy_dir.mkdir()
        policy_file = policy_dir / "tools.yaml"
        policy_file.write_text("tools: {}")

        with patch.dict(
            os.environ,
            {
                "BURLY_CONFIG_DIR": str(config_dir),
            },
        ):
            config = Config()
            errors = config.validate()

            assert len(errors) == 0

    def test_config_validation_missing_config_dir(self):
        """Test validation with missing config directory."""
        from burly_mcp.config import Config

        with patch.dict(
            os.environ,
            {
                "BURLY_CONFIG_DIR": "/nonexistent/config",
            },
        ):
            config = Config()
            errors = config.validate()

            assert len(errors) > 0
            assert any("Config directory not found" in error for error in errors)

    def test_config_validation_missing_policy_file(self, tmp_path):
        """Test validation with missing policy file."""
        from burly_mcp.config import Config

        # Create config directory but not policy file
        config_dir = tmp_path / "config"
        config_dir.mkdir()

        with patch.dict(
            os.environ,
            {
                "BURLY_CONFIG_DIR": str(config_dir),
            },
        ):
            config = Config()
            errors = config.validate()

            assert len(errors) > 0
            assert any("Policy file not found" in error for error in errors)

    @patch.dict(
        os.environ,
        {
            "GOTIFY_URL": "https://gotify.example.com",
            # GOTIFY_TOKEN is missing
        },
    )
    def test_config_validation_missing_gotify_token(self):
        """Test validation with Gotify URL but missing token."""
        from burly_mcp.config import Config

        config = Config()
        errors = config.validate()

        assert len(errors) > 0
        assert any(
            "GOTIFY_TOKEN required when GOTIFY_URL is set" in error for error in errors
        )

    def test_config_str_representation(self):
        """Test string representation of config."""
        from burly_mcp.config import Config

        config = Config()
        config_str = str(config)

        assert "Config(" in config_str
        assert "config_dir=" in config_str
        assert "log_dir=" in config_str

    def test_config_repr_representation(self):
        """Test repr representation of config."""
        from burly_mcp.config import Config

        config = Config()
        config_repr = repr(config)

        assert "Config(" in config_repr

    @patch.dict(
        os.environ,
        {
            "DOCKER_TIMEOUT": "invalid_number",
        },
    )
    def test_config_invalid_integer_environment(self):
        """Test handling of invalid integer environment variables."""
        from burly_mcp.config import Config

        # Should handle invalid integer gracefully and use default
        config = Config()
        assert config.docker_timeout == 30  # default value

    @patch.dict(
        os.environ,
        {
            "AUDIT_ENABLED": "invalid_boolean",
        },
    )
    def test_config_invalid_boolean_environment(self):
        """Test handling of invalid boolean environment variables."""
        from burly_mcp.config import Config

        # Should handle invalid boolean gracefully
        config = Config()
        # Invalid boolean should default to False
        assert config.audit_enabled is False

    def test_config_path_resolution(self):
        """Test that paths are properly resolved."""
        from burly_mcp.config import Config

        config = Config()

        # Paths should be Path objects
        assert isinstance(config.config_dir, Path)
        assert isinstance(config.log_dir, Path)
        assert isinstance(config.blog_stage_root, Path)
        assert isinstance(config.blog_publish_root, Path)

    def test_config_policy_file_path(self):
        """Test policy file path construction."""
        from burly_mcp.config import Config

        with patch.dict(
            os.environ,
            {
                "BURLY_CONFIG_DIR": "/test/config",
            },
        ):
            config = Config()

            expected_policy_path = Path("/test/config/policy/tools.yaml")
            assert config.policy_file == expected_policy_path

    def test_config_immutability(self):
        """Test that config values can be modified after creation."""
        from burly_mcp.config import Config

        config = Config()
        original_timeout = config.docker_timeout

        # Config should allow modification for testing
        config.docker_timeout = 120
        assert config.docker_timeout == 120
        assert config.docker_timeout != original_timeout

    @patch.dict(
        os.environ,
        {
            "BURLY_CONFIG_DIR": "",  # Empty string
        },
    )
    def test_config_empty_environment_variable(self):
        """Test handling of empty environment variables."""
        from burly_mcp.config import Config

        config = Config()

        # Empty string should fall back to default
        assert config.config_dir == Path("/app/config")

    def test_config_security_settings(self):
        """Test security-related configuration settings."""
        from burly_mcp.config import Config

        config = Config()

        # Test security defaults
        assert config.max_output_size > 0
        assert isinstance(config.audit_enabled, bool)
        assert isinstance(config.docker_timeout, int)
        assert config.docker_timeout > 0
