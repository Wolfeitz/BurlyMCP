"""
Unit tests for the policy system.

This module tests the PolicyLoader, SchemaValidator, and ToolRegistry classes
to ensure proper YAML loading, schema validation, and tool management.
"""

import pytest
import os
from pathlib import Path
from typing import Dict, Any

from server.policy import (
    PolicyLoader,
    SchemaValidator,
    ToolRegistry,
    PolicyLoadError,
    PolicyValidationError,
    SchemaValidationError,
    ToolDefinition,
    PolicyConfig,
)


class TestPolicyLoader:
    """Test cases for PolicyLoader class."""

    def test_load_valid_policy(self, test_policy_file, sample_policy_yaml: str):
        """Test loading a valid policy file."""
        policy_file = test_policy_file("test_valid_policy.yaml", sample_policy_yaml)

        loader = PolicyLoader(str(policy_file))
        loader.load_policy()

        assert loader.is_loaded()

        # Test tool loading
        tool = loader.get_tool_definition("test_tool")
        assert tool is not None
        assert tool.name == "test_tool"
        assert tool.description == "Test tool for unit tests"
        assert tool.mutates is False
        assert tool.requires_confirm is False
        assert tool.timeout_sec == 10

        # Test config loading
        config = loader.get_config()
        assert config.output_truncate_limit == 1024
        assert config.default_timeout_sec == 30

    def test_load_nonexistent_file(self):
        """Test loading a non-existent policy file."""
        loader = PolicyLoader("nonexistent.yaml")

        with pytest.raises(PolicyLoadError, match="Policy file not found"):
            loader.load_policy()

    def test_load_empty_file(self, test_policy_file):
        """Test loading an empty policy file."""
        policy_file = test_policy_file("test_empty.yaml", "")

        loader = PolicyLoader(str(policy_file))

        with pytest.raises(PolicyLoadError, match="Policy file is empty or invalid"):
            loader.load_policy()

    def test_load_invalid_yaml(self, test_policy_file):
        """Test loading a file with invalid YAML syntax."""
        policy_file = test_policy_file("test_invalid.yaml", "invalid: yaml: content: [")

        loader = PolicyLoader(str(policy_file))

        with pytest.raises(PolicyLoadError, match="invalid YAML syntax"):
            loader.load_policy()

    def test_load_missing_tools_section(self, test_policy_file):
        """Test loading a policy file without tools section."""
        policy_file = test_policy_file(
            "test_no_tools.yaml", "config:\n  default_timeout_sec: 30"
        )

        loader = PolicyLoader(str(policy_file))

        with pytest.raises(PolicyValidationError, match="must contain 'tools' section"):
            loader.load_policy()

    def test_load_invalid_tools_section(self, test_policy_file):
        """Test loading a policy file with invalid tools section."""
        policy_file = test_policy_file(
            "test_invalid_tools.yaml", "tools: not_an_object"
        )

        loader = PolicyLoader(str(policy_file))

        with pytest.raises(
            PolicyValidationError, match="'tools' section must be an object"
        ):
            loader.load_policy()

    def test_load_tool_missing_required_fields(self, test_policy_file):
        """Test loading a tool definition missing required fields."""
        policy_content = """
tools:
  incomplete_tool:
    description: "Missing required fields"
    # Missing args_schema, command, mutates, requires_confirm, timeout_sec
"""
        policy_file = test_policy_file("test_incomplete.yaml", policy_content)

        loader = PolicyLoader(str(policy_file))

        with pytest.raises(PolicyValidationError, match="missing required field"):
            loader.load_policy()

    def test_load_tool_invalid_field_types(self, test_policy_file):
        """Test loading a tool with invalid field types."""
        policy_content = """
tools:
  invalid_tool:
    description: 123  # Should be string
    args_schema: "not_an_object"  # Should be object
    command: "not_a_list"  # Should be list
    mutates: "not_a_boolean"  # Should be boolean
    requires_confirm: "not_a_boolean"  # Should be boolean
    timeout_sec: "not_an_integer"  # Should be integer
"""
        policy_file = test_policy_file("test_invalid_types.yaml", policy_content)

        loader = PolicyLoader(str(policy_file))

        with pytest.raises(PolicyValidationError, match="description must be a string"):
            loader.load_policy()

    def test_load_tool_invalid_timeout(self, test_policy_file):
        """Test loading a tool with invalid timeout values."""
        policy_content = """
tools:
  timeout_tool:
    description: "Tool with invalid timeout"
    args_schema:
      type: "object"
    command: ["echo", "test"]
    mutates: false
    requires_confirm: false
    timeout_sec: 0  # Should be positive
"""
        policy_file = test_policy_file("test_invalid_timeout.yaml", policy_content)

        loader = PolicyLoader(str(policy_file))

        with pytest.raises(
            PolicyValidationError, match="timeout_sec must be a positive integer"
        ):
            loader.load_policy()

    def test_load_tool_excessive_timeout(self, test_policy_file):
        """Test loading a tool with timeout exceeding maximum."""
        policy_content = """
tools:
  long_timeout_tool:
    description: "Tool with excessive timeout"
    args_schema:
      type: "object"
    command: ["echo", "test"]
    mutates: false
    requires_confirm: false
    timeout_sec: 400  # Exceeds 300 second maximum
"""
        policy_file = test_policy_file("test_excessive_timeout.yaml", policy_content)

        loader = PolicyLoader(str(policy_file))

        with pytest.raises(
            PolicyValidationError, match="timeout_sec exceeds maximum allowed"
        ):
            loader.load_policy()

    def test_load_tool_invalid_notify_types(self, test_policy_file):
        """Test loading a tool with invalid notify types."""
        policy_content = """
tools:
  notify_tool:
    description: "Tool with invalid notify types"
    args_schema:
      type: "object"
    command: ["echo", "test"]
    mutates: false
    requires_confirm: false
    timeout_sec: 30
    notify: ["invalid_type"]  # Not in valid types
"""
        policy_file = test_policy_file("test_invalid_notify.yaml", policy_content)

        loader = PolicyLoader(str(policy_file))

        with pytest.raises(PolicyValidationError, match="invalid notify type"):
            loader.load_policy()

    def test_path_traversal_protection(self):
        """Test protection against path traversal attacks."""
        loader = PolicyLoader("../../../etc/passwd")

        with pytest.raises(PolicyLoadError, match="potential path traversal"):
            loader.load_policy()

    def test_suspicious_path_components(self):
        """Test detection of suspicious path components."""
        # Test with a path that contains .. but doesn't exist
        loader = PolicyLoader("policy/../config.yaml")

        with pytest.raises(PolicyLoadError, match="Policy file not found"):
            loader.load_policy()

    def test_file_size_limit(self, test_policy_file):
        """Test file size limit enforcement."""
        # Create a file larger than 1MB
        large_content = "# " + "x" * (1024 * 1024 + 1)
        policy_file = test_policy_file("test_large.yaml", large_content)

        loader = PolicyLoader(str(policy_file))

        with pytest.raises(PolicyLoadError, match="exceeds maximum size limit"):
            loader.load_policy()

    def test_get_tool_before_loading(self):
        """Test accessing tools before loading policy."""
        loader = PolicyLoader("nonexistent.yaml")

        with pytest.raises(RuntimeError, match="Policy must be loaded"):
            loader.get_tool_definition("test_tool")

    def test_get_all_tools(self, test_policy_file, sample_policy_yaml: str):
        """Test getting all tool definitions."""
        policy_file = test_policy_file("test_all_tools.yaml", sample_policy_yaml)

        loader = PolicyLoader(str(policy_file))
        loader.load_policy()

        all_tools = loader.get_all_tools()
        assert len(all_tools) == 1
        assert "test_tool" in all_tools
        assert isinstance(all_tools["test_tool"], ToolDefinition)

    def test_config_with_security_section(self, test_policy_file):
        """Test loading config with nested security section."""
        policy_content = """
tools:
  test_tool:
    description: "Test tool"
    args_schema:
      type: "object"
    command: ["echo", "test"]
    mutates: false
    requires_confirm: false
    timeout_sec: 30

config:
  output_truncate_limit: 2048
  security:
    blog_stage_root: "/custom/stage"
    blog_publish_root: "/custom/publish"
    allowed_blog_extensions: [".md", ".txt"]
"""
        policy_file = test_policy_file("test_security_config.yaml", policy_content)

        loader = PolicyLoader(str(policy_file))
        loader.load_policy()

        config = loader.get_config()
        assert config.output_truncate_limit == 2048
        assert config.blog_stage_root == "/custom/stage"
        assert config.blog_publish_root == "/custom/publish"
        assert config.allowed_blog_extensions == [".md", ".txt"]


class TestSchemaValidator:
    """Test cases for SchemaValidator class."""

    def test_validate_valid_args(self):
        """Test validation of valid arguments."""
        validator = SchemaValidator()
        schema = {
            "type": "object",
            "properties": {
                "message": {"type": "string"},
                "count": {"type": "integer", "minimum": 1},
            },
            "required": ["message"],
        }
        args = {"message": "hello", "count": 5}

        # Should not raise any exception
        validator.validate_args(args, schema, "test_tool")

    def test_validate_missing_required_field(self):
        """Test validation with missing required field."""
        validator = SchemaValidator()
        schema = {
            "type": "object",
            "properties": {"message": {"type": "string"}},
            "required": ["message"],
        }
        args = {}  # Missing required 'message' field

        with pytest.raises(
            SchemaValidationError, match="Missing required field: message"
        ):
            validator.validate_args(args, schema, "test_tool")

    def test_validate_wrong_type(self):
        """Test validation with wrong argument type."""
        validator = SchemaValidator()
        schema = {"type": "object", "properties": {"count": {"type": "integer"}}}
        args = {"count": "not_an_integer"}

        with pytest.raises(
            SchemaValidationError, match="has invalid type.*Expected integer.*got str"
        ):
            validator.validate_args(args, schema, "test_tool")

    def test_validate_pattern_mismatch(self):
        """Test validation with pattern mismatch."""
        validator = SchemaValidator()
        schema = {
            "type": "object",
            "properties": {
                "email": {"type": "string", "pattern": r"^[^@]+@[^@]+\.[^@]+$"}
            },
        }
        args = {"email": "invalid_email"}

        with pytest.raises(
            SchemaValidationError, match="does not match required pattern"
        ):
            validator.validate_args(args, schema, "test_tool")

    def test_validate_min_items_violation(self):
        """Test validation with minimum items violation."""
        validator = SchemaValidator()
        schema = {
            "type": "object",
            "properties": {"items": {"type": "array", "minItems": 2}},
        }
        args = {"items": ["single_item"]}

        with pytest.raises(
            SchemaValidationError, match="must have at least 2 items.*Got 1 items"
        ):
            validator.validate_args(args, schema, "test_tool")

    def test_validate_max_length_violation(self):
        """Test validation with maximum length violation."""
        validator = SchemaValidator()
        schema = {
            "type": "object",
            "properties": {"short_text": {"type": "string", "maxLength": 5}},
        }
        args = {"short_text": "this_is_too_long"}

        with pytest.raises(
            SchemaValidationError,
            match="exceeds maximum length of 5.*Got 16 characters",
        ):
            validator.validate_args(args, schema, "test_tool")

    def test_validate_additional_properties_forbidden(self):
        """Test validation with forbidden additional properties."""
        validator = SchemaValidator()
        schema = {
            "type": "object",
            "properties": {"allowed": {"type": "string"}},
            "additionalProperties": False,
        }
        args = {"allowed": "ok", "forbidden": "not_allowed"}

        with pytest.raises(
            SchemaValidationError, match="contains unexpected properties"
        ):
            validator.validate_args(args, schema, "test_tool")

    def test_validate_invalid_schema(self):
        """Test validation with invalid schema."""
        validator = SchemaValidator()
        invalid_schema = {"type": "invalid_type"}  # Not a valid JSON Schema type
        args = {"test": "value"}

        with pytest.raises(SchemaValidationError, match="validation error"):
            validator.validate_args(args, invalid_schema, "test_tool")

    def test_validate_schema_complexity_depth(self):
        """Test schema complexity validation - excessive nesting depth."""
        validator = SchemaValidator()

        # Create deeply nested schema (over 20 levels)
        schema = {"type": "object", "properties": {}}
        current = schema["properties"]
        for i in range(25):
            current[f"level_{i}"] = {"type": "object", "properties": {}}
            current = current[f"level_{i}"]["properties"]

        args = {}

        with pytest.raises(SchemaValidationError, match="schema too deeply nested"):
            validator.validate_args(args, schema, "test_tool")

    def test_validate_schema_complexity_properties(self):
        """Test schema complexity validation - too many properties."""
        validator = SchemaValidator()

        # Create schema with over 100 properties
        properties = {}
        for i in range(101):
            properties[f"prop_{i}"] = {"type": "string"}

        schema = {"type": "object", "properties": properties}
        args = {}

        with pytest.raises(SchemaValidationError, match="schema too complex"):
            validator.validate_args(args, schema, "test_tool")

    def test_validate_schema_complexity_array_size(self):
        """Test schema complexity validation - large arrays."""
        validator = SchemaValidator()

        # Create schema with large array
        large_array = ["string"] * 51  # Over 50 items
        schema = {"type": "object", "properties": {"test": {"type": large_array}}}
        args = {}

        with pytest.raises(SchemaValidationError, match="schema array too large"):
            validator.validate_args(args, schema, "test_tool")

    def test_validate_schema_method(self):
        """Test standalone schema validation method."""
        validator = SchemaValidator()

        valid_schema = {"type": "object", "properties": {"test": {"type": "string"}}}

        # Should not raise exception
        validator.validate_schema(valid_schema, "test_tool")

        invalid_schema = {"type": "invalid_type"}

        with pytest.raises(SchemaValidationError, match="has invalid JSON schema"):
            validator.validate_schema(invalid_schema, "test_tool")

    def test_get_schema_errors(self):
        """Test getting validation errors without raising exceptions."""
        validator = SchemaValidator()
        schema = {
            "type": "object",
            "properties": {"required_field": {"type": "string"}},
            "required": ["required_field"],
        }

        # Valid args - should return empty list
        valid_args = {"required_field": "value"}
        errors = validator.get_schema_errors(valid_args, schema)
        assert errors == []

        # Invalid args - should return error list
        invalid_args = {}
        errors = validator.get_schema_errors(invalid_args, schema)
        assert len(errors) > 0
        assert any("required_field" in error for error in errors)


class TestToolRegistry:
    """Test cases for ToolRegistry class."""

    def test_initialize_registry(self, test_policy_file, sample_policy_yaml: str):
        """Test initializing the tool registry."""
        policy_file = test_policy_file("test_registry.yaml", sample_policy_yaml)

        loader = PolicyLoader(str(policy_file))
        loader.load_policy()

        validator = SchemaValidator()
        registry = ToolRegistry(loader, validator)

        assert not registry.is_initialized()

        registry.initialize()

        assert registry.is_initialized()

    def test_initialize_without_loaded_policy(self):
        """Test initializing registry without loaded policy."""
        loader = PolicyLoader("nonexistent.yaml")
        validator = SchemaValidator()
        registry = ToolRegistry(loader, validator)

        with pytest.raises(RuntimeError, match="Policy loader must be loaded"):
            registry.initialize()

    def test_get_tool(self, test_policy_file, sample_policy_yaml: str):
        """Test getting a tool from the registry."""
        policy_file = test_policy_file("test_get_tool.yaml", sample_policy_yaml)

        loader = PolicyLoader(str(policy_file))
        loader.load_policy()

        validator = SchemaValidator()
        registry = ToolRegistry(loader, validator)
        registry.initialize()

        tool = registry.get_tool("test_tool")
        assert tool is not None
        assert tool.name == "test_tool"

        # Test non-existent tool
        assert registry.get_tool("nonexistent") is None

    def test_has_tool(self, test_policy_file, sample_policy_yaml: str):
        """Test checking if tool exists in registry."""
        policy_file = test_policy_file("test_has_tool.yaml", sample_policy_yaml)

        loader = PolicyLoader(str(policy_file))
        loader.load_policy()

        validator = SchemaValidator()
        registry = ToolRegistry(loader, validator)
        registry.initialize()

        assert registry.has_tool("test_tool")
        assert not registry.has_tool("nonexistent")

    def test_get_all_tool_names(self, test_policy_file, sample_policy_yaml: str):
        """Test getting all tool names."""
        policy_file = test_policy_file("test_tool_names.yaml", sample_policy_yaml)

        loader = PolicyLoader(str(policy_file))
        loader.load_policy()

        validator = SchemaValidator()
        registry = ToolRegistry(loader, validator)
        registry.initialize()

        tool_names = registry.get_all_tool_names()
        assert tool_names == ["test_tool"]

    def test_validate_tool_args(self, test_policy_file, sample_policy_yaml: str):
        """Test validating tool arguments."""
        policy_file = test_policy_file("test_validate_args.yaml", sample_policy_yaml)

        loader = PolicyLoader(str(policy_file))
        loader.load_policy()

        validator = SchemaValidator()
        registry = ToolRegistry(loader, validator)
        registry.initialize()

        # Valid args
        registry.validate_tool_args("test_tool", {"test_param": "hello"})

        # Invalid args - missing required field
        with pytest.raises(SchemaValidationError):
            registry.validate_tool_args("test_tool", {})

        # Non-existent tool
        with pytest.raises(ValueError, match="Tool 'nonexistent' not found"):
            registry.validate_tool_args("nonexistent", {})

    def test_get_tool_metadata(self, test_policy_file, sample_policy_yaml: str):
        """Test getting tool metadata for MCP responses."""
        policy_file = test_policy_file("test_metadata.yaml", sample_policy_yaml)

        loader = PolicyLoader(str(policy_file))
        loader.load_policy()

        validator = SchemaValidator()
        registry = ToolRegistry(loader, validator)
        registry.initialize()

        metadata = registry.get_tool_metadata("test_tool")
        assert metadata is not None
        assert metadata["name"] == "test_tool"
        assert metadata["description"] == "Test tool for unit tests"
        assert "inputSchema" in metadata
        assert metadata["inputSchema"]["type"] == "object"

        # Non-existent tool
        assert registry.get_tool_metadata("nonexistent") is None

    def test_get_all_tool_metadata(self, test_policy_file, sample_policy_yaml: str):
        """Test getting metadata for all tools."""
        policy_file = test_policy_file("test_all_metadata.yaml", sample_policy_yaml)

        loader = PolicyLoader(str(policy_file))
        loader.load_policy()

        validator = SchemaValidator()
        registry = ToolRegistry(loader, validator)
        registry.initialize()

        all_metadata = registry.get_all_tool_metadata()
        assert len(all_metadata) == 1
        assert all_metadata[0]["name"] == "test_tool"

    def test_get_mutating_tools(self, test_policy_file):
        """Test getting list of mutating tools."""
        policy_content = """
tools:
  safe_tool:
    description: "Safe read-only tool"
    args_schema:
      type: "object"
    command: ["echo", "safe"]
    mutates: false
    requires_confirm: false
    timeout_sec: 10
  
  dangerous_tool:
    description: "Dangerous mutating tool"
    args_schema:
      type: "object"
    command: ["rm", "-rf"]
    mutates: true
    requires_confirm: true
    timeout_sec: 30
"""
        policy_file = test_policy_file("test_mutating.yaml", policy_content)

        loader = PolicyLoader(str(policy_file))
        loader.load_policy()

        validator = SchemaValidator()
        registry = ToolRegistry(loader, validator)
        registry.initialize()

        mutating_tools = registry.get_mutating_tools()
        assert mutating_tools == ["dangerous_tool"]

    def test_get_confirmation_required_tools(self, test_policy_file):
        """Test getting list of tools requiring confirmation."""
        policy_content = """
tools:
  auto_tool:
    description: "Automatic tool"
    args_schema:
      type: "object"
    command: ["echo", "auto"]
    mutates: false
    requires_confirm: false
    timeout_sec: 10
  
  confirm_tool:
    description: "Tool requiring confirmation"
    args_schema:
      type: "object"
    command: ["important", "operation"]
    mutates: true
    requires_confirm: true
    timeout_sec: 30
"""
        policy_file = test_policy_file("test_confirmation.yaml", policy_content)

        loader = PolicyLoader(str(policy_file))
        loader.load_policy()

        validator = SchemaValidator()
        registry = ToolRegistry(loader, validator)
        registry.initialize()

        confirmation_tools = registry.get_confirmation_required_tools()
        assert confirmation_tools == ["confirm_tool"]

    def test_registry_operations_before_initialization(
        self, test_policy_file, sample_policy_yaml: str
    ):
        """Test that registry operations fail before initialization."""
        policy_file = test_policy_file("test_before_init.yaml", sample_policy_yaml)

        loader = PolicyLoader(str(policy_file))
        loader.load_policy()

        validator = SchemaValidator()
        registry = ToolRegistry(loader, validator)

        # All operations should fail before initialization
        with pytest.raises(RuntimeError, match="Registry must be initialized"):
            registry.get_tool("test_tool")

        with pytest.raises(RuntimeError, match="Registry must be initialized"):
            registry.has_tool("test_tool")

        with pytest.raises(RuntimeError, match="Registry must be initialized"):
            registry.get_all_tool_names()

        with pytest.raises(RuntimeError, match="Registry must be initialized"):
            registry.validate_tool_args("test_tool", {})

        with pytest.raises(RuntimeError, match="Registry must be initialized"):
            registry.get_tool_metadata("test_tool")

    def test_initialize_with_invalid_tool_schema(self, test_policy_file):
        """Test initialization fails with invalid tool schema."""
        policy_content = """
tools:
  invalid_schema_tool:
    description: "Tool with invalid schema"
    args_schema:
      type: "invalid_type"  # Invalid JSON Schema type
    command: ["echo", "test"]
    mutates: false
    requires_confirm: false
    timeout_sec: 10
"""
        policy_file = test_policy_file("test_invalid_schema.yaml", policy_content)

        loader = PolicyLoader(str(policy_file))
        loader.load_policy()

        validator = SchemaValidator()
        registry = ToolRegistry(loader, validator)

        with pytest.raises(SchemaValidationError, match="has invalid schema"):
            registry.initialize()
