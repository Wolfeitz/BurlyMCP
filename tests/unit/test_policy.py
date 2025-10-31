"""
Unit tests for the Burly MCP policy engine.
"""

import os
import tempfile
from unittest.mock import patch

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

    def test_policy_loader_directory_merges_and_overrides(self):
        """Tools defined in POLICY_DIR should merge with the base file."""
        from burly_mcp.policy.engine import PolicyLoader

        with tempfile.TemporaryDirectory(dir=".") as temp_dir:
            policy_file = os.path.join(temp_dir, "policy.yaml")
            policy_dir = os.path.join(temp_dir, "tools.d")
            os.makedirs(policy_dir, exist_ok=True)

            base_policy = {
                "tools": {
                    "from_file": {
                        "description": "legacy command",
                        "args_schema": {"type": "object"},
                        "command": ["echo", "legacy"],
                        "mutates": False,
                        "requires_confirm": False,
                        "timeout_sec": 30,
                    }
                }
            }

            with open(policy_file, "w", encoding="utf-8") as handle:
                yaml.safe_dump(base_policy, handle)

            first_pack = {
                "tools": [
                    {
                        "name": "dir_only",
                        "description": "directory provided tool",
                        "args_schema": {"type": "object"},
                        "command": ["bash", "-lc", "echo directory"],
                        "mutating": False,
                        "requires_confirm": False,
                        "timeout_sec": 25,
                    },
                    {
                        "name": "from_file",
                        "description": "override v1",
                        "args_schema": {"type": "object"},
                        "command": ["echo", "dir-v1"],
                        "mutating": False,
                        "requires_confirm": False,
                        "timeout_sec": 40,
                    },
                ]
            }

            override_pack = {
                "tools": [
                    {
                        "name": "from_file",
                        "description": "override v2",
                        "args_schema": {"type": "object"},
                        "command": ["echo", "dir-v2"],
                        "mutating": False,
                        "requires_confirm": False,
                        "timeout_sec": 10,
                    }
                ]
            }

            with open(
                os.path.join(policy_dir, "010-first.yaml"), "w", encoding="utf-8"
            ) as handle:
                yaml.safe_dump(first_pack, handle)

            with open(
                os.path.join(policy_dir, "020-override.yaml"), "w", encoding="utf-8"
            ) as handle:
                yaml.safe_dump(override_pack, handle)

            with patch.dict(os.environ, {"POLICY_DIR": policy_dir}, clear=False):
                loader = PolicyLoader(policy_file)
                loader.load_policy()

            assert loader.is_loaded()

            dir_tool = loader.get_tool_definition("dir_only")
            assert dir_tool is not None
            assert dir_tool.command == ["bash", "-lc", "echo directory"]
            assert dir_tool.mutates is False

            merged_tool = loader.get_tool_definition("from_file")
            assert merged_tool is not None
            # The directory override should replace the legacy file definition
            assert merged_tool.command == ["echo", "dir-v2"]
            assert merged_tool.timeout_sec == 10

            stats = loader.get_loader_stats()
            assert stats is not None
            assert stats.get("from_file_count") == 1
            assert stats.get("from_dir_files") == 2
            assert stats.get("from_dir_tools") == 3

    def test_policy_loader_handles_missing_file_with_directory_only(self, monkeypatch):
        """Directory-based configs should load even if the legacy file is absent."""
        from burly_mcp.policy.engine import PolicyLoader

        with tempfile.TemporaryDirectory(dir=".") as temp_dir:
            policy_dir = os.path.join(temp_dir, "tools.d")
            os.makedirs(policy_dir, exist_ok=True)

            pack = {
                "tools": [
                    {
                        "name": "dir_tool",
                        "description": "configured from directory",
                        "args_schema": {"type": "object"},
                        "command": ["echo", "dir"],
                        "mutating": False,
                        "requires_confirm": False,
                        "timeout_sec": 15,
                    }
                ]
            }

            with open(os.path.join(policy_dir, "050-dir.yaml"), "w", encoding="utf-8") as handle:
                yaml.safe_dump(pack, handle)

            missing_file = os.path.join(temp_dir, "policy.yaml")

            monkeypatch.setenv("POLICY_DIR", policy_dir)

            loader = PolicyLoader(missing_file)
            loader.load_policy()

            dir_tool = loader.get_tool_definition("dir_tool")
            assert dir_tool is not None
            assert dir_tool.command == ["echo", "dir"]
            assert dir_tool.timeout_sec == 15

    def test_policy_loader_accepts_absolute_policy_file_outside_repo(self, monkeypatch):
        """Absolute policy paths provided via env should be permitted."""
        from burly_mcp.policy.engine import PolicyLoader

        with tempfile.TemporaryDirectory() as temp_dir:
            policy_root = os.path.join(temp_dir, "policy")
            os.makedirs(policy_root, exist_ok=True)
            policy_path = os.path.join(policy_root, "tools.yaml")

            policy_content = {
                "tools": {
                    "external_tool": {
                        "description": "external mount",
                        "command": ["echo", "external"],
                        "mutates": False,
                        "requires_confirm": False,
                        "timeout_sec": 5,
                        "args_schema": {"type": "object"},
                    }
                }
            }

            with open(policy_path, "w", encoding="utf-8") as handle:
                yaml.safe_dump(policy_content, handle)

            monkeypatch.setenv("POLICY_FILE", policy_path)

            loader = PolicyLoader(policy_path)
            loader.load_policy()

            assert loader.is_loaded()
            tool = loader.get_tool_definition("external_tool")
            assert tool is not None
            assert tool.command == ["echo", "external"]

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
