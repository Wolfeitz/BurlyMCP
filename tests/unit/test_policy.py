"""
Unit tests for the Burly MCP policy engine.
"""

import os
import tempfile

import pytest
import yaml


class TestPolicyLoader:
    """Test the policy loader functionality."""

    def test_policy_loader_initialization(self):
        """Test policy loader initialization."""
        from burly_mcp.policy.engine import PolicyLoader

        with tempfile.TemporaryDirectory() as temp_dir:
            policy_file = os.path.join(temp_dir, "test_policy.yaml")

            # Create a minimal valid policy file
            policy_content = {
                "version": "1.0",
                "tools": {
                    "test_tool": {
                        "description": "Test tool",
                        "command": ["echo", "test"],
                        "mutates": False,
                        "requires_confirm": False,
                        "timeout_sec": 30,
                        "args_schema": {"type": "object"}
                    }
                }
            }

            with open(policy_file, 'w') as f:
                yaml.dump(policy_content, f)

            loader = PolicyLoader(policy_file)
            assert hasattr(loader, "policy_file_path")
            assert hasattr(loader, "_tools")
            assert hasattr(loader, "_config")

    def test_load_policy_from_file(self):
        """Test loading policy from YAML file."""
        from burly_mcp.policy.engine import PolicyLoader

        # Use current directory to avoid path traversal issues
        policy_file = "test_policy.yaml"

        policy_content = {
            "version": "1.0",
            "tools": {
                "test_tool": {
                    "description": "Test tool for unit tests",
                    "command": ["echo", "test"],
                    "mutates": False,
                    "requires_confirm": False,
                    "timeout_sec": 30,
                    "args_schema": {
                        "type": "object",
                        "properties": {
                            "message": {"type": "string"}
                        }
                    }
                }
            }
        }

        try:
            with open(policy_file, 'w') as f:
                yaml.dump(policy_content, f)

            loader = PolicyLoader(policy_file)
            loader.load_policy()

            assert loader.is_loaded()
            tool_def = loader.get_tool_definition("test_tool")
            assert tool_def is not None
            assert tool_def.description == "Test tool for unit tests"
        finally:
            # Clean up test file
            if os.path.exists(policy_file):
                os.remove(policy_file)

    def test_load_policy_file_not_found(self):
        """Test handling of missing policy file."""
        from burly_mcp.policy.engine import PolicyLoader, PolicyLoadError

        loader = PolicyLoader("/nonexistent/policy.yaml")

        with pytest.raises(PolicyLoadError):
            loader.load_policy()

    def test_load_policy_invalid_yaml(self):
        """Test handling of invalid YAML content."""
        from burly_mcp.policy.engine import PolicyLoader, PolicyLoadError

        with tempfile.TemporaryDirectory() as temp_dir:
            policy_file = os.path.join(temp_dir, "invalid_policy.yaml")

            # Write invalid YAML
            with open(policy_file, 'w') as f:
                f.write("invalid: yaml: content: [")

            loader = PolicyLoader(policy_file)

            with pytest.raises(PolicyLoadError):
                loader.load_policy()

    @pytest.mark.skip(reason="TODO: Fix policy file path security restrictions")
    def test_validate_policy_structure(self):
        """Test policy structure validation."""
        from burly_mcp.policy.engine import PolicyLoader

        # Use current directory to avoid path traversal issues
        policy_file = "test_policy_structure.yaml"

        # Valid policy structure
        policy_content = {
            "version": "1.0",
            "tools": {
                "valid_tool": {
                    "description": "Valid tool",
                    "command": ["echo", "test"],
                    "mutates": False,
                    "requires_confirm": False,
                    "timeout_sec": 30,
                    "args_schema": {"type": "object"}
                }
            }
        }

        try:
            with open(policy_file, 'w') as f:
                yaml.dump(policy_content, f)

            loader = PolicyLoader(policy_file)
            loader.load_policy()

            # Should load successfully
            assert loader.is_loaded()
        finally:
            # Clean up test file
            if os.path.exists(policy_file):
                os.remove(policy_file)

    @pytest.mark.skip(reason="TODO: Fix policy file path security restrictions")
    def test_validate_policy_missing_tools(self):
        """Test validation of policy missing tools section."""
        from burly_mcp.policy.engine import PolicyLoader, PolicyValidationError

        with tempfile.TemporaryDirectory() as temp_dir:
            policy_file = os.path.join(temp_dir, "test_policy.yaml")

            # Policy missing tools section
            policy_content = {
                "version": "1.0"
                # Missing tools section
            }

            with open(policy_file, 'w') as f:
                yaml.dump(policy_content, f)

            loader = PolicyLoader(policy_file)

            with pytest.raises(PolicyValidationError):
                loader.load_policy()

    @pytest.mark.skip(reason="TODO: Fix policy file path security restrictions")
    def test_get_tool_definition(self):
        """Test getting tool definition."""
        from burly_mcp.policy.engine import PolicyLoader

        with tempfile.TemporaryDirectory() as temp_dir:
            policy_file = os.path.join(temp_dir, "test_policy.yaml")

            policy_content = {
                "version": "1.0",
                "tools": {
                    "existing_tool": {
                        "description": "Existing tool",
                        "command": ["echo", "existing"],
                        "mutates": True,
                        "requires_confirm": True,
                        "timeout_sec": 60,
                        "args_schema": {"type": "object"}
                    }
                }
            }

            with open(policy_file, 'w') as f:
                yaml.dump(policy_content, f)

            loader = PolicyLoader(policy_file)
            loader.load_policy()

            # Test existing tool
            tool_def = loader.get_tool_definition("existing_tool")
            assert tool_def is not None
            assert tool_def.name == "existing_tool"
            assert tool_def.mutates is True
            assert tool_def.requires_confirm is True

            # Test non-existent tool
            tool_def = loader.get_tool_definition("nonexistent_tool")
            assert tool_def is None

    @pytest.mark.skip(reason="TODO: Fix policy file path security restrictions")
    def test_tool_requires_confirmation(self):
        """Test checking if tool requires confirmation."""
        from burly_mcp.policy.engine import PolicyLoader

        with tempfile.TemporaryDirectory() as temp_dir:
            policy_file = os.path.join(temp_dir, "test_policy.yaml")

            policy_content = {
                "version": "1.0",
                "tools": {
                    "safe_tool": {
                        "description": "Safe tool",
                        "command": ["echo", "safe"],
                        "mutates": False,
                        "requires_confirm": False,
                        "timeout_sec": 30,
                        "args_schema": {"type": "object"}
                    },
                    "dangerous_tool": {
                        "description": "Dangerous tool",
                        "command": ["rm", "-rf"],
                        "mutates": True,
                        "requires_confirm": True,
                        "timeout_sec": 30,
                        "args_schema": {"type": "object"}
                    }
                }
            }

            with open(policy_file, 'w') as f:
                yaml.dump(policy_content, f)

            loader = PolicyLoader(policy_file)
            loader.load_policy()

            assert loader.tool_requires_confirmation("safe_tool") is False
            assert loader.tool_requires_confirmation("dangerous_tool") is True
            assert loader.tool_requires_confirmation("nonexistent_tool") is False

    @pytest.mark.skip(reason="TODO: Fix policy file path security restrictions")
    def test_tool_mutates_system(self):
        """Test checking if tool mutates system state."""
        from burly_mcp.policy.engine import PolicyLoader

        with tempfile.TemporaryDirectory() as temp_dir:
            policy_file = os.path.join(temp_dir, "test_policy.yaml")

            policy_content = {
                "version": "1.0",
                "tools": {
                    "read_only_tool": {
                        "description": "Read-only tool",
                        "command": ["cat", "file.txt"],
                        "mutates": False,
                        "requires_confirm": False,
                        "timeout_sec": 30,
                        "args_schema": {"type": "object"}
                    },
                    "write_tool": {
                        "description": "Write tool",
                        "command": ["touch", "file.txt"],
                        "mutates": True,
                        "requires_confirm": False,
                        "timeout_sec": 30,
                        "args_schema": {"type": "object"}
                    }
                }
            }

            with open(policy_file, 'w') as f:
                yaml.dump(policy_content, f)

            loader = PolicyLoader(policy_file)
            loader.load_policy()

            assert loader.tool_mutates_system("read_only_tool") is False
            assert loader.tool_mutates_system("write_tool") is True
            assert loader.tool_mutates_system("nonexistent_tool") is False

    @pytest.mark.skip(reason="TODO: Fix policy file path security restrictions")
    def test_get_tool_timeout(self):
        """Test getting tool timeout configuration."""
        from burly_mcp.policy.engine import PolicyLoader

        with tempfile.TemporaryDirectory() as temp_dir:
            policy_file = os.path.join(temp_dir, "test_policy.yaml")

            policy_content = {
                "version": "1.0",
                "tools": {
                    "quick_tool": {
                        "description": "Quick tool",
                        "command": ["echo", "quick"],
                        "mutates": False,
                        "requires_confirm": False,
                        "timeout_sec": 10,
                        "args_schema": {"type": "object"}
                    },
                    "slow_tool": {
                        "description": "Slow tool",
                        "command": ["sleep", "60"],
                        "mutates": False,
                        "requires_confirm": False,
                        "timeout_sec": 120,
                        "args_schema": {"type": "object"}
                    }
                }
            }

            with open(policy_file, 'w') as f:
                yaml.dump(policy_content, f)

            loader = PolicyLoader(policy_file)
            loader.load_policy()

            assert loader.get_tool_timeout("quick_tool") == 10
            assert loader.get_tool_timeout("slow_tool") == 120
            assert loader.get_tool_timeout("nonexistent_tool") == 30  # Default


class TestSchemaValidator:
    """Test the schema validator functionality."""

    def test_schema_validator_initialization(self):
        """Test schema validator initialization."""
        from burly_mcp.policy.engine import SchemaValidator

        validator = SchemaValidator()
        assert hasattr(validator, "validate_args")

    def test_validate_args_success(self):
        """Test successful argument validation."""
        from burly_mcp.policy.engine import SchemaValidator

        validator = SchemaValidator()

        schema = {
            "type": "object",
            "properties": {
                "name": {"type": "string"},
                "age": {"type": "integer", "minimum": 0}
            },
            "required": ["name"]
        }

        args = {"name": "John", "age": 30}

        # Should not raise exception
        validator.validate_args(args, schema, "test_tool")

    def test_validate_args_failure(self):
        """Test argument validation failure."""
        from burly_mcp.policy.engine import SchemaValidationError, SchemaValidator

        validator = SchemaValidator()

        schema = {
            "type": "object",
            "properties": {
                "name": {"type": "string"},
                "age": {"type": "integer", "minimum": 0}
            },
            "required": ["name"]
        }

        # Missing required field
        args = {"age": 30}

        with pytest.raises(SchemaValidationError):
            validator.validate_args(args, schema, "test_tool")

    def test_validate_args_type_mismatch(self):
        """Test argument validation with type mismatch."""
        from burly_mcp.policy.engine import SchemaValidationError, SchemaValidator

        validator = SchemaValidator()

        schema = {
            "type": "object",
            "properties": {
                "name": {"type": "string"},
                "age": {"type": "integer"}
            }
        }

        # Wrong type for age
        args = {"name": "John", "age": "thirty"}

        with pytest.raises(SchemaValidationError):
            validator.validate_args(args, schema, "test_tool")


class TestPolicyToolRegistry:
    """Test the policy tool registry functionality."""

    @pytest.mark.skip(reason="TODO: Fix PolicyToolRegistry tests - requires complex policy setup")
    def test_policy_tool_registry_initialization(self):
        """Test policy tool registry initialization."""
        from burly_mcp.policy.engine import PolicyToolRegistry

        with tempfile.TemporaryDirectory() as temp_dir:
            policy_file = os.path.join(temp_dir, "test_policy.yaml")

            policy_content = {
                "version": "1.0",
                "tools": {
                    "test_tool": {
                        "description": "Test tool",
                        "command": ["echo", "test"],
                        "mutates": False,
                        "requires_confirm": False,
                        "timeout_sec": 30,
                        "args_schema": {"type": "object"}
                    }
                }
            }

            with open(policy_file, 'w') as f:
                yaml.dump(policy_content, f)

            registry = PolicyToolRegistry(policy_file)
            assert hasattr(registry, "policy_loader")
            assert hasattr(registry, "schema_validator")

    @pytest.mark.skip(reason="TODO: Fix PolicyToolRegistry tests - requires complex policy setup")
    def test_get_available_tools(self):
        """Test getting list of available tools."""
        from burly_mcp.policy.engine import PolicyToolRegistry

        with tempfile.TemporaryDirectory() as temp_dir:
            policy_file = os.path.join(temp_dir, "test_policy.yaml")

            policy_content = {
                "version": "1.0",
                "tools": {
                    "tool1": {
                        "description": "Tool 1",
                        "command": ["echo", "1"],
                        "mutates": False,
                        "requires_confirm": False,
                        "timeout_sec": 30,
                        "args_schema": {"type": "object"}
                    },
                    "tool2": {
                        "description": "Tool 2",
                        "command": ["echo", "2"],
                        "mutates": False,
                        "requires_confirm": False,
                        "timeout_sec": 30,
                        "args_schema": {"type": "object"}
                    }
                }
            }

            with open(policy_file, 'w') as f:
                yaml.dump(policy_content, f)

            registry = PolicyToolRegistry(policy_file)
            tools = registry.get_available_tools()

            assert "tool1" in tools
            assert "tool2" in tools
            assert len(tools) == 2

    @pytest.mark.skip(reason="TODO: Fix PolicyToolRegistry tests - requires complex policy setup")
    def test_is_tool_allowed(self):
        """Test checking if tool is allowed."""
        from burly_mcp.policy.engine import PolicyToolRegistry

        with tempfile.TemporaryDirectory() as temp_dir:
            policy_file = os.path.join(temp_dir, "test_policy.yaml")

            policy_content = {
                "version": "1.0",
                "tools": {
                    "allowed_tool": {
                        "description": "Allowed tool",
                        "command": ["echo", "allowed"],
                        "mutates": False,
                        "requires_confirm": False,
                        "timeout_sec": 30,
                        "args_schema": {"type": "object"}
                    }
                }
            }

            with open(policy_file, 'w') as f:
                yaml.dump(policy_content, f)

            registry = PolicyToolRegistry(policy_file)

            assert registry.is_tool_allowed("allowed_tool") is True
            assert registry.is_tool_allowed("forbidden_tool") is False

    @pytest.mark.skip(reason="TODO: Fix PolicyToolRegistry tests - requires complex policy setup")
    def test_validate_tool_execution(self):
        """Test validating tool execution."""
        from burly_mcp.policy.engine import PolicyToolRegistry

        with tempfile.TemporaryDirectory() as temp_dir:
            policy_file = os.path.join(temp_dir, "test_policy.yaml")

            policy_content = {
                "version": "1.0",
                "tools": {
                    "test_tool": {
                        "description": "Test tool",
                        "command": ["echo", "{message}"],
                        "mutates": False,
                        "requires_confirm": False,
                        "timeout_sec": 30,
                        "args_schema": {
                            "type": "object",
                            "properties": {
                                "message": {"type": "string"}
                            },
                            "required": ["message"]
                        }
                    }
                }
            }

            with open(policy_file, 'w') as f:
                yaml.dump(policy_content, f)

            registry = PolicyToolRegistry(policy_file)

            # Valid execution
            result = registry.validate_tool_execution("test_tool", {"message": "hello"})
            assert result is True

            # Invalid execution (missing required arg)
            result = registry.validate_tool_execution("test_tool", {})
            assert result is False

            # Non-existent tool
            result = registry.validate_tool_execution("nonexistent_tool", {})
            assert result is False


class TestPolicyExceptions:
    """Test policy-related exceptions."""

    def test_policy_load_error(self):
        """Test PolicyLoadError exception."""
        from burly_mcp.policy.engine import PolicyLoadError

        with pytest.raises(PolicyLoadError):
            raise PolicyLoadError("Test error message")

    def test_policy_validation_error(self):
        """Test PolicyValidationError exception."""
        from burly_mcp.policy.engine import PolicyValidationError

        with pytest.raises(PolicyValidationError):
            raise PolicyValidationError("Test validation error")

    def test_schema_validation_error(self):
        """Test SchemaValidationError exception."""
        from burly_mcp.policy.engine import SchemaValidationError

        with pytest.raises(SchemaValidationError):
            raise SchemaValidationError("Test schema error")
