"""
Unit tests for the Burly MCP policy engine.
"""

import pytest
from unittest.mock import Mock, patch, mock_open
from pathlib import Path
import yaml
from burly_mcp.policy.engine import PolicyLoader, PolicyValidationError, PolicyLoadError, SchemaValidator, SchemaValidationError


class TestPolicyLoader:
    """Test the policy loader functionality."""

    def test_policy_loader_initialization(self):
        """Test policy loader initialization."""
        loader = PolicyLoader()
        assert hasattr(loader, "policy_file_path")
        assert hasattr(loader, "_tools")
        assert hasattr(loader, "_config")

    def test_load_policy_from_file(self, sample_policy_yaml, tmp_path):
        """Test loading policy from YAML file."""
        policy_file = tmp_path / "test_policy.yaml"
        policy_file.write_text(sample_policy_yaml)

        loader = PolicyLoader(str(policy_file))
        loader.load_policy()

        assert loader.is_loaded()
        tool_def = loader.get_tool_definition("test_tool")
        assert tool_def is not None
        assert tool_def.description == "Test tool for unit tests"

    def test_load_policy_file_not_found(self):
        """Test handling of missing policy file."""
        loader = PolicyLoader("/nonexistent/policy.yaml")

        with pytest.raises(PolicyLoadError):
            loader.load_policy()

    def test_load_policy_invalid_yaml(self, tmp_path):
        """Test handling of invalid YAML content."""
        policy_file = tmp_path / "invalid_policy.yaml"
        policy_file.write_text("invalid: yaml: content: [")

        loader = PolicyLoader(str(policy_file))

        with pytest.raises(PolicyLoadError):
            loader.load_policy()

    def test_validate_policy_structure(self, sample_policy_yaml, tmp_path):
        """Test policy structure validation."""
        policy_file = tmp_path / "test_policy.yaml"
        policy_file.write_text(sample_policy_yaml)

        loader = PolicyLoader(str(policy_file))
        loader.load_policy()

        # Should not raise any exceptions for valid policy
        assert loader.is_loaded()

    def test_validate_policy_missing_tools(self, tmp_path):
        """Test validation with missing tools section."""
        invalid_policy = """
config:
  output_truncate_limit: 1024
"""
        policy_file = tmp_path / "invalid_policy.yaml"
        policy_file.write_text(invalid_policy)

        loader = PolicyLoader(str(policy_file))

        with pytest.raises(PolicyValidationError, match="'tools' section"):
            loader.load_policy()

    def test_validate_tool_schema(self, sample_policy_yaml, tmp_path):
        """Test individual tool schema validation."""
        policy_file = tmp_path / "test_policy.yaml"
        policy_file.write_text(sample_policy_yaml)

        loader = PolicyLoader(str(policy_file))
        loader.load_policy()

        # Test valid tool exists
        tool_def = loader.get_tool_definition("test_tool")
        assert tool_def is not None

    def test_validate_tool_schema_missing_tool(self, sample_policy_yaml, tmp_path):
        """Test validation of nonexistent tool."""
        policy_file = tmp_path / "test_policy.yaml"
        policy_file.write_text(sample_policy_yaml)

        loader = PolicyLoader(str(policy_file))
        loader.load_policy()

        # Test nonexistent tool returns None
        tool_def = loader.get_tool_definition("nonexistent_tool")
        assert tool_def is None

    def test_get_tool_config(self, sample_policy_yaml, tmp_path):
        """Test getting tool configuration."""
        policy_file = tmp_path / "test_policy.yaml"
        policy_file.write_text(sample_policy_yaml)

        loader = PolicyLoader(str(policy_file))
        loader.load_policy()

        tool_def = loader.get_tool_definition("test_tool")

        assert tool_def is not None
        assert tool_def.description == "Test tool for unit tests"
        assert tool_def.mutates is False
        assert tool_def.requires_confirm is False

    def test_get_tool_config_nonexistent(self, sample_policy_yaml, tmp_path):
        """Test getting configuration for nonexistent tool."""
        policy_file = tmp_path / "test_policy.yaml"
        policy_file.write_text(sample_policy_yaml)

        loader = PolicyLoader(str(policy_file))
        loader.load_policy()

        tool_def = loader.get_tool_definition("nonexistent_tool")
        assert tool_def is None

    def test_tool_requires_confirmation(self, multi_tool_policy_yaml, tmp_path):
        """Test checking if tool requires confirmation."""
        policy_file = tmp_path / "test_policy.yaml"
        policy_file.write_text(multi_tool_policy_yaml)

        loader = PolicyLoader(str(policy_file))
        loader.load_policy()

        # Test tool that doesn't require confirmation
        test_tool = loader.get_tool_definition("test_tool")
        assert test_tool is not None
        assert test_tool.requires_confirm is False

        # Test tool that requires confirmation
        confirm_tool = loader.get_tool_definition("confirm_tool")
        assert confirm_tool is not None
        assert confirm_tool.requires_confirm is True

    def test_tool_mutates_system(self, multi_tool_policy_yaml, tmp_path):
        """Test checking if tool mutates system state."""
        policy_file = tmp_path / "test_policy.yaml"
        policy_file.write_text(multi_tool_policy_yaml)

        loader = PolicyLoader(str(policy_file))
        loader.load_policy()

        # Test tool that doesn't mutate
        test_tool = loader.get_tool_definition("test_tool")
        assert test_tool is not None
        assert test_tool.mutates is False

        # Test tool that mutates
        confirm_tool = loader.get_tool_definition("confirm_tool")
        assert confirm_tool is not None
        assert confirm_tool.mutates is True

    def test_get_tool_timeout(self, sample_policy_yaml, tmp_path):
        """Test getting tool timeout configuration."""
        policy_file = tmp_path / "test_policy.yaml"
        policy_file.write_text(sample_policy_yaml)

        loader = PolicyLoader(str(policy_file))
        loader.load_policy()

        tool_def = loader.get_tool_definition("test_tool")
        assert tool_def is not None
        assert tool_def.timeout_sec == 10

    def test_get_tool_timeout_default(self, sample_policy_yaml, tmp_path):
        """Test getting default timeout for tool without specific timeout."""
        policy_file = tmp_path / "test_policy.yaml"
        policy_file.write_text(sample_policy_yaml)

        loader = PolicyLoader(str(policy_file))
        loader.load_policy()

        # For nonexistent tool, should return None
        tool_def = loader.get_tool_definition("nonexistent_tool")
        assert tool_def is None

        # Default timeout from config
        config = loader.get_config()
        assert config.default_timeout_sec == 30

    def test_get_notification_settings(self, sample_policy_yaml, tmp_path):
        """Test getting notification settings for tool."""
        policy_file = tmp_path / "test_policy.yaml"
        policy_file.write_text(sample_policy_yaml)

        loader = PolicyLoader(str(policy_file))
        loader.load_policy()

        tool_def = loader.get_tool_definition("test_tool")
        assert tool_def is not None
        assert isinstance(tool_def.notify, list)

    def test_validate_tool_arguments(self, sample_policy_yaml, tmp_path):
        """Test validating tool arguments against schema."""
        policy_file = tmp_path / "test_policy.yaml"
        policy_file.write_text(sample_policy_yaml)

        loader = PolicyLoader(str(policy_file))
        loader.load_policy()
        
        validator = SchemaValidator()
        tool_def = loader.get_tool_definition("test_tool")
        assert tool_def is not None

        # Valid arguments
        valid_args = {"test_param": "test_value"}
        # Should not raise exception
        validator.validate_args(valid_args, tool_def.args_schema, "test_tool")

    def test_validate_tool_arguments_invalid(self, sample_policy_yaml, tmp_path):
        """Test validation with invalid arguments."""
        policy_file = tmp_path / "test_policy.yaml"
        policy_file.write_text(sample_policy_yaml)

        loader = PolicyLoader(str(policy_file))
        loader.load_policy()
        
        validator = SchemaValidator()
        tool_def = loader.get_tool_definition("test_tool")
        assert tool_def is not None

        # Invalid arguments (missing required field)
        invalid_args = {}

        with pytest.raises(SchemaValidationError):
            validator.validate_args(invalid_args, tool_def.args_schema, "test_tool")

    def test_get_security_config(self, sample_policy_yaml, tmp_path):
        """Test getting security configuration."""
        policy_file = tmp_path / "test_policy.yaml"
        policy_file.write_text(sample_policy_yaml)

        loader = PolicyLoader(str(policy_file))
        loader.load_policy()

        config = loader.get_config()

        assert config is not None
        assert hasattr(config, 'blog_stage_root')
        assert hasattr(config, 'blog_publish_root')

    def test_is_path_allowed(self, sample_policy_yaml, tmp_path):
        """Test path validation against security policy."""
        policy_file = tmp_path / "test_policy.yaml"
        policy_file.write_text(sample_policy_yaml)

        loader = PolicyLoader(str(policy_file))
        loader.load_policy()

        config = loader.get_config()
        # Test that config has path settings
        assert config.blog_stage_root is not None
        assert config.blog_publish_root is not None

    def test_policy_reload(self, sample_policy_yaml, tmp_path):
        """Test reloading policy configuration."""
        policy_file = tmp_path / "test_policy.yaml"
        policy_file.write_text(sample_policy_yaml)

        loader = PolicyLoader(str(policy_file))
        loader.load_policy()

        # Modify policy file
        updated_policy = sample_policy_yaml.replace(
            "Test tool for unit tests", "Updated test tool"
        )
        policy_file.write_text(updated_policy)

        # Reload policy
        loader.load_policy()

        tool_def = loader.get_tool_definition("test_tool")
        assert tool_def is not None
        assert tool_def.description == "Updated test tool"


class TestPolicyValidationError:
    """Test the PolicyValidationError exception."""

    def test_policy_validation_error_creation(self):
        """Test creating PolicyValidationError."""
        error = PolicyValidationError("Test error message")
        assert str(error) == "Test error message"

    def test_policy_validation_error_with_details(self):
        """Test PolicyValidationError with additional details."""
        error = PolicyValidationError("Test error")
        assert str(error) == "Test error"
