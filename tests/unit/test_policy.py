"""
Unit tests for the Burly MCP policy engine.
"""

import pytest
from unittest.mock import Mock, patch, mock_open
from pathlib import Path
import yaml
from burly_mcp.policy.engine import PolicyEngine, PolicyValidationError


class TestPolicyEngine:
    """Test the policy engine functionality."""

    def test_policy_engine_initialization(self):
        """Test policy engine initialization."""
        engine = PolicyEngine()
        assert hasattr(engine, 'policy_data')
        assert hasattr(engine, 'tools')
        assert hasattr(engine, 'config')

    def test_load_policy_from_file(self, sample_policy_yaml, tmp_path):
        """Test loading policy from YAML file."""
        policy_file = tmp_path / "test_policy.yaml"
        policy_file.write_text(sample_policy_yaml)
        
        engine = PolicyEngine()
        engine.load_policy(str(policy_file))
        
        assert 'tools' in engine.policy_data
        assert 'test_tool' in engine.policy_data['tools']
        assert engine.policy_data['tools']['test_tool']['description'] == "Test tool for unit tests"

    def test_load_policy_file_not_found(self):
        """Test handling of missing policy file."""
        engine = PolicyEngine()
        
        with pytest.raises(FileNotFoundError):
            engine.load_policy("/nonexistent/policy.yaml")

    def test_load_policy_invalid_yaml(self, tmp_path):
        """Test handling of invalid YAML content."""
        policy_file = tmp_path / "invalid_policy.yaml"
        policy_file.write_text("invalid: yaml: content: [")
        
        engine = PolicyEngine()
        
        with pytest.raises(yaml.YAMLError):
            engine.load_policy(str(policy_file))

    def test_validate_policy_structure(self, sample_policy_yaml, tmp_path):
        """Test policy structure validation."""
        policy_file = tmp_path / "test_policy.yaml"
        policy_file.write_text(sample_policy_yaml)
        
        engine = PolicyEngine()
        engine.load_policy(str(policy_file))
        
        # Should not raise any exceptions for valid policy
        engine.validate_policy()

    def test_validate_policy_missing_tools(self, tmp_path):
        """Test validation with missing tools section."""
        invalid_policy = """
config:
  output_truncate_limit: 1024
"""
        policy_file = tmp_path / "invalid_policy.yaml"
        policy_file.write_text(invalid_policy)
        
        engine = PolicyEngine()
        engine.load_policy(str(policy_file))
        
        with pytest.raises(PolicyValidationError, match="Missing 'tools' section"):
            engine.validate_policy()

    def test_validate_tool_schema(self, sample_policy_yaml, tmp_path):
        """Test individual tool schema validation."""
        policy_file = tmp_path / "test_policy.yaml"
        policy_file.write_text(sample_policy_yaml)
        
        engine = PolicyEngine()
        engine.load_policy(str(policy_file))
        
        # Test valid tool
        is_valid = engine.validate_tool_schema('test_tool')
        assert is_valid is True

    def test_validate_tool_schema_missing_tool(self, sample_policy_yaml, tmp_path):
        """Test validation of nonexistent tool."""
        policy_file = tmp_path / "test_policy.yaml"
        policy_file.write_text(sample_policy_yaml)
        
        engine = PolicyEngine()
        engine.load_policy(str(policy_file))
        
        with pytest.raises(PolicyValidationError, match="Tool 'nonexistent_tool' not found"):
            engine.validate_tool_schema('nonexistent_tool')

    def test_get_tool_config(self, sample_policy_yaml, tmp_path):
        """Test getting tool configuration."""
        policy_file = tmp_path / "test_policy.yaml"
        policy_file.write_text(sample_policy_yaml)
        
        engine = PolicyEngine()
        engine.load_policy(str(policy_file))
        
        tool_config = engine.get_tool_config('test_tool')
        
        assert tool_config is not None
        assert tool_config['description'] == "Test tool for unit tests"
        assert tool_config['mutates'] is False
        assert tool_config['requires_confirm'] is False

    def test_get_tool_config_nonexistent(self, sample_policy_yaml, tmp_path):
        """Test getting configuration for nonexistent tool."""
        policy_file = tmp_path / "test_policy.yaml"
        policy_file.write_text(sample_policy_yaml)
        
        engine = PolicyEngine()
        engine.load_policy(str(policy_file))
        
        tool_config = engine.get_tool_config('nonexistent_tool')
        assert tool_config is None

    def test_tool_requires_confirmation(self, multi_tool_policy_yaml, tmp_path):
        """Test checking if tool requires confirmation."""
        policy_file = tmp_path / "test_policy.yaml"
        policy_file.write_text(multi_tool_policy_yaml)
        
        engine = PolicyEngine()
        engine.load_policy(str(policy_file))
        
        # Test tool that doesn't require confirmation
        assert engine.tool_requires_confirmation('test_tool') is False
        
        # Test tool that requires confirmation
        assert engine.tool_requires_confirmation('confirm_tool') is True

    def test_tool_mutates_system(self, multi_tool_policy_yaml, tmp_path):
        """Test checking if tool mutates system state."""
        policy_file = tmp_path / "test_policy.yaml"
        policy_file.write_text(multi_tool_policy_yaml)
        
        engine = PolicyEngine()
        engine.load_policy(str(policy_file))
        
        # Test tool that doesn't mutate
        assert engine.tool_mutates_system('test_tool') is False
        
        # Test tool that mutates
        assert engine.tool_mutates_system('confirm_tool') is True

    def test_get_tool_timeout(self, sample_policy_yaml, tmp_path):
        """Test getting tool timeout configuration."""
        policy_file = tmp_path / "test_policy.yaml"
        policy_file.write_text(sample_policy_yaml)
        
        engine = PolicyEngine()
        engine.load_policy(str(policy_file))
        
        timeout = engine.get_tool_timeout('test_tool')
        assert timeout == 10

    def test_get_tool_timeout_default(self, sample_policy_yaml, tmp_path):
        """Test getting default timeout for tool without specific timeout."""
        policy_file = tmp_path / "test_policy.yaml"
        policy_file.write_text(sample_policy_yaml)
        
        engine = PolicyEngine()
        engine.load_policy(str(policy_file))
        
        # For nonexistent tool, should return default from config
        timeout = engine.get_tool_timeout('nonexistent_tool')
        assert timeout == 30  # default from config

    def test_get_notification_settings(self, sample_policy_yaml, tmp_path):
        """Test getting notification settings for tool."""
        policy_file = tmp_path / "test_policy.yaml"
        policy_file.write_text(sample_policy_yaml)
        
        engine = PolicyEngine()
        engine.load_policy(str(policy_file))
        
        notifications = engine.get_notification_settings('test_tool')
        assert 'success' in notifications
        assert 'failure' in notifications

    def test_validate_tool_arguments(self, sample_policy_yaml, tmp_path):
        """Test validating tool arguments against schema."""
        policy_file = tmp_path / "test_policy.yaml"
        policy_file.write_text(sample_policy_yaml)
        
        engine = PolicyEngine()
        engine.load_policy(str(policy_file))
        
        # Valid arguments
        valid_args = {"test_param": "test_value"}
        is_valid = engine.validate_tool_arguments('test_tool', valid_args)
        assert is_valid is True

    def test_validate_tool_arguments_invalid(self, sample_policy_yaml, tmp_path):
        """Test validation with invalid arguments."""
        policy_file = tmp_path / "test_policy.yaml"
        policy_file.write_text(sample_policy_yaml)
        
        engine = PolicyEngine()
        engine.load_policy(str(policy_file))
        
        # Invalid arguments (missing required field)
        invalid_args = {}
        
        with pytest.raises(PolicyValidationError):
            engine.validate_tool_arguments('test_tool', invalid_args)

    def test_get_security_config(self, sample_policy_yaml, tmp_path):
        """Test getting security configuration."""
        policy_file = tmp_path / "test_policy.yaml"
        policy_file.write_text(sample_policy_yaml)
        
        engine = PolicyEngine()
        engine.load_policy(str(policy_file))
        
        security_config = engine.get_security_config()
        
        assert security_config is not None
        assert security_config['enable_path_validation'] is True
        assert '/tmp' in security_config['allowed_paths']

    def test_is_path_allowed(self, sample_policy_yaml, tmp_path):
        """Test path validation against security policy."""
        policy_file = tmp_path / "test_policy.yaml"
        policy_file.write_text(sample_policy_yaml)
        
        engine = PolicyEngine()
        engine.load_policy(str(policy_file))
        
        # Allowed path
        assert engine.is_path_allowed('/tmp/test.txt') is True
        
        # Disallowed path
        assert engine.is_path_allowed('/etc/passwd') is False

    def test_policy_reload(self, sample_policy_yaml, tmp_path):
        """Test reloading policy configuration."""
        policy_file = tmp_path / "test_policy.yaml"
        policy_file.write_text(sample_policy_yaml)
        
        engine = PolicyEngine()
        engine.load_policy(str(policy_file))
        
        # Modify policy file
        updated_policy = sample_policy_yaml.replace("Test tool for unit tests", "Updated test tool")
        policy_file.write_text(updated_policy)
        
        # Reload policy
        engine.reload_policy()
        
        tool_config = engine.get_tool_config('test_tool')
        assert tool_config['description'] == "Updated test tool"


class TestPolicyValidationError:
    """Test the PolicyValidationError exception."""

    def test_policy_validation_error_creation(self):
        """Test creating PolicyValidationError."""
        error = PolicyValidationError("Test error message")
        assert str(error) == "Test error message"

    def test_policy_validation_error_with_details(self):
        """Test PolicyValidationError with additional details."""
        error = PolicyValidationError("Test error", details={"field": "value"})
        assert str(error) == "Test error"
        assert error.details == {"field": "value"}