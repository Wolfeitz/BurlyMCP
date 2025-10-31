"""
Policy engine for Burly MCP server.

This module provides policy loading, validation, and enforcement for MCP tools.
It ensures that only whitelisted tools can be executed and that all tool
arguments are validated against their defined schemas.
"""

import logging
import os
from dataclasses import dataclass
from typing import Any

import jsonschema
import yaml

from .dir_loader import DEFAULT_POLICY_FILE, load_tools_from_sources


class PolicyLoadError(Exception):
    """Raised when policy file cannot be loaded or is invalid."""

    pass


class PolicyValidationError(Exception):
    """Raised when policy content fails validation."""

    pass


class SchemaValidationError(Exception):
    """Raised when tool arguments fail schema validation."""

    pass


@dataclass
class ToolDefinition:
    """Definition of a tool with its configuration and validation schema."""

    name: str
    description: str
    args_schema: dict[str, Any]
    command: list[str]
    mutates: bool
    requires_confirm: bool
    timeout_sec: int
    notify: list[str]


@dataclass
class PolicyConfig:
    """Global policy configuration settings."""

    output_truncate_limit: int
    default_timeout_sec: int
    audit_log_path: str
    blog_stage_root: str
    blog_publish_root: str
    allowed_blog_extensions: list[str]


class PolicyLoader:
    """
    Loads and validates tool policies from YAML configuration files.

    The PolicyLoader is responsible for:
    - Reading YAML policy files
    - Validating policy structure and required fields
    - Creating ToolDefinition objects for each configured tool
    - Providing access to global configuration settings
    """

    def __init__(self, policy_file_path: str = "config/policy/tools.yaml"):
        """
        Initialize PolicyLoader with path to policy file.

        Args:
            policy_file_path: Path to the YAML policy file
        """
        self.policy_file_path = policy_file_path
        self._tools: dict[str, ToolDefinition] = {}
        self._config: PolicyConfig | None = None
        self._loaded = False
        self._loader_stats: dict[str, Any] | None = None

    def load_policy(self) -> None:
        """
        Load and validate policy from YAML file.

        Raises:
            PolicyLoadError: If file cannot be read or parsed
            PolicyValidationError: If policy content is invalid
        """
        logger = logging.getLogger(__name__)

        try:
            # Validate and canonicalize policy file path
            canonical_path = os.path.realpath(self.policy_file_path)
            allowed_base = os.path.realpath(".")

            allowed_roots = {allowed_base}

            # Always allow the default container policy path and any explicit override
            default_policy_root = os.path.dirname(os.path.realpath(DEFAULT_POLICY_FILE))
            allowed_roots.add(default_policy_root)

            env_policy_file = os.getenv("POLICY_FILE")
            if env_policy_file:
                allowed_roots.add(os.path.dirname(os.path.realpath(env_policy_file)))

            def _is_within_root(path: str, root: str) -> bool:
                normalized_root = os.path.normpath(root)
                if normalized_root == os.sep:
                    normalized_root = os.sep
                return path.startswith(normalized_root.rstrip(os.sep) + os.sep) or path == normalized_root

            allowed = any(
                _is_within_root(canonical_path, root)
                for root in allowed_roots
                if root
            )

            default_policy_path = os.path.realpath(DEFAULT_POLICY_FILE)
            if canonical_path == default_policy_path:
                allowed = True
            elif env_policy_file:
                env_policy_path = os.path.realpath(env_policy_file)
                if canonical_path == env_policy_path:
                    allowed = True

            if not allowed:
                raise PolicyLoadError(
                    "Policy file path not allowed - potential path traversal"
                )

            # Additional security: Check for suspicious path components
            path_components = canonical_path.split(os.sep)
            if any(component in ["..", ".", "~"] for component in path_components):
                raise PolicyLoadError("Policy file path contains suspicious components")

            policy_data: dict[str, Any] = {"tools": {}}

            if os.path.exists(canonical_path):
                # Update to use canonical path
                self.policy_file_path = canonical_path

                # Read and parse YAML file with size limits
                file_size = os.path.getsize(self.policy_file_path)
                if file_size > 1024 * 1024:  # 1MB limit
                    raise PolicyLoadError("Policy file exceeds maximum size limit")

                with open(self.policy_file_path, encoding="utf-8") as f:
                    content = f.read(1024 * 1024)  # Additional read limit
                    try:
                        # Use safe_load with custom loader to prevent YAML bombs
                        parsed = yaml.safe_load(content)
                        if parsed is None:
                            raise PolicyLoadError("Policy file is empty or invalid")
                        if not isinstance(parsed, dict):
                            raise PolicyLoadError("Policy file must contain a YAML object")
                        policy_data = parsed
                    except yaml.YAMLError:
                        raise PolicyLoadError("Policy file contains invalid YAML syntax")
            else:
                # Use canonical path for downstream logging and directory loading
                self.policy_file_path = canonical_path
                logger.info(
                    "Policy file not found at %s; continuing with directory configurations only",
                    canonical_path,
                )

            # Validate policy structure
            self._validate_policy_structure(policy_data)

            # Load tools from legacy file plus directory overrides
            merged_tools, loader_stats = load_tools_from_sources(
                logger=logger,
                policy_file_override=self.policy_file_path,
            )

            # Persist loader stats for diagnostics and testing.
            self._loader_stats = dict(loader_stats)

            enabled_tool_map: dict[str, dict[str, Any]] = {}
            disabled_tools: list[str] = []

            for tool in merged_tools:
                name = (tool or {}).get("name")
                if not name:
                    continue

                if tool.get("enabled") is False:
                    disabled_tools.append(name)
                    continue

                normalized = dict(tool)
                normalized.pop("name", None)
                normalized.pop("enabled", None)

                # Support alternate field names used by directory configs
                if "mutates" not in normalized and "mutating" in normalized:
                    normalized["mutates"] = bool(normalized.pop("mutating"))

                enabled_tool_map[name] = normalized

            loader_stats["enabled_tools"] = len(enabled_tool_map)
            loader_stats["disabled_tools"] = len(disabled_tools)

            if disabled_tools:
                logger.info(
                    "Policy tools disabled via configuration: %s",
                    ", ".join(sorted(disabled_tools)),
                )

            invalid_entries = loader_stats.get("invalid", [])
            if invalid_entries:
                logger.warning(
                    "Skipped %d invalid policy definitions", len(invalid_entries)
                )

            logger.info(
                "Policy tools active: enabled=%d disabled=%d invalid=%d",
                loader_stats.get("enabled_tools", 0),
                loader_stats.get("disabled_tools", 0),
                len(invalid_entries),
            )

            # Load tools from legacy file plus directory overrides
            merged_tools, loader_stats = load_tools_from_sources(
                logger=logger,
                policy_file_override=self.policy_file_path,
            )

            enabled_tool_map: dict[str, dict[str, Any]] = {}
            disabled_tools: list[str] = []

            for tool in merged_tools:
                name = (tool or {}).get("name")
                if not name:
                    continue

                if tool.get("enabled") is False:
                    disabled_tools.append(name)
                    continue

                normalized = dict(tool)
                normalized.pop("name", None)
                normalized.pop("enabled", None)

                # Support alternate field names used by directory configs
                if "mutates" not in normalized and "mutating" in normalized:
                    normalized["mutates"] = bool(normalized.pop("mutating"))

                enabled_tool_map[name] = normalized

            loader_stats["enabled_tools"] = len(enabled_tool_map)
            loader_stats["disabled_tools"] = len(disabled_tools)

            if disabled_tools:
                logger.info(
                    "Policy tools disabled via configuration: %s",
                    ", ".join(sorted(disabled_tools)),
                )

            invalid_entries = loader_stats.get("invalid", [])
            if invalid_entries:
                logger.warning(
                    "Skipped %d invalid policy definitions", len(invalid_entries)
                )

            logger.info(
                "Policy tools active: enabled=%d disabled=%d invalid=%d",
                loader_stats.get("enabled_tools", 0),
                loader_stats.get("disabled_tools", 0),
                len(invalid_entries),
            )

            # Load tools
            self._load_tools(enabled_tool_map)

            # Load global configuration
            self._load_config(policy_data.get("config", {}))

            self._loaded = True

        except OSError:
            raise PolicyLoadError(
                "Failed to read policy file: access denied or file not found"
            )

    def _validate_policy_structure(self, policy_data: dict[str, Any]) -> None:
        """
        Validate the overall structure of the policy file.

        Args:
            policy_data: Parsed YAML data

        Raises:
            PolicyValidationError: If structure is invalid
        """
        if not isinstance(policy_data, dict):
            raise PolicyValidationError("Policy file must contain a YAML object")

        # Check for required top-level sections
        if "tools" not in policy_data:
            raise PolicyValidationError("Policy file must contain 'tools' section")

        if not isinstance(policy_data["tools"], (dict, list)):
            raise PolicyValidationError("'tools' section must be an object or list")

        if "config" in policy_data and not isinstance(policy_data["config"], dict):
            raise PolicyValidationError("'config' section must be an object")

    def get_loader_stats(self) -> dict[str, Any] | None:
        """Return the most recent loader statistics snapshot."""

        return dict(self._loader_stats) if self._loader_stats is not None else None

    def _load_tools(self, tools_data: dict[str, Any]) -> None:
        """
        Load and validate tool definitions.

        Args:
            tools_data: Tools section from policy file

        Raises:
            PolicyValidationError: If any tool definition is invalid
        """
        self._tools = {}

        for tool_name, tool_config in tools_data.items():
            try:
                self._validate_tool_definition(tool_name, tool_config)

                # Create ToolDefinition object
                tool_def = ToolDefinition(
                    name=tool_name,
                    description=tool_config["description"],
                    args_schema=tool_config["args_schema"],
                    command=tool_config["command"],
                    mutates=tool_config["mutates"],
                    requires_confirm=tool_config["requires_confirm"],
                    timeout_sec=tool_config["timeout_sec"],
                    notify=tool_config.get("notify", []),
                )

                self._tools[tool_name] = tool_def

            except KeyError as e:
                raise PolicyValidationError(
                    f"Tool '{tool_name}' missing required field: {e}"
                )
            except (TypeError, ValueError) as e:
                raise PolicyValidationError(
                    f"Tool '{tool_name}' has invalid configuration: {e}"
                )

    def _validate_tool_definition(
        self, tool_name: str, tool_config: dict[str, Any]
    ) -> None:
        """
        Validate a single tool definition.

        Args:
            tool_name: Name of the tool
            tool_config: Tool configuration dictionary

        Raises:
            PolicyValidationError: If tool definition is invalid
        """
        if not isinstance(tool_config, dict):
            raise PolicyValidationError(
                f"Tool '{tool_name}' configuration must be an object"
            )

        # Required fields
        required_fields = [
            "description",
            "args_schema",
            "command",
            "mutates",
            "requires_confirm",
            "timeout_sec",
        ]

        for field in required_fields:
            if field not in tool_config:
                raise PolicyValidationError(
                    f"Tool '{tool_name}' missing required field: {field}"
                )

        # Validate field types
        if not isinstance(tool_config["description"], str):
            raise PolicyValidationError(
                f"Tool '{tool_name}' description must be a string"
            )

        if not isinstance(tool_config["args_schema"], dict):
            raise PolicyValidationError(
                f"Tool '{tool_name}' args_schema must be an object"
            )

        if not isinstance(tool_config["command"], list):
            raise PolicyValidationError(f"Tool '{tool_name}' command must be a list")

        if not isinstance(tool_config["mutates"], bool):
            raise PolicyValidationError(f"Tool '{tool_name}' mutates must be a boolean")

        if not isinstance(tool_config["requires_confirm"], bool):
            raise PolicyValidationError(
                f"Tool '{tool_name}' requires_confirm must be a boolean"
            )

        if (
            not isinstance(tool_config["timeout_sec"], int)
            or tool_config["timeout_sec"] <= 0
        ):
            raise PolicyValidationError(
                f"Tool '{tool_name}' timeout_sec must be a positive integer"
            )

        # Security: Enforce maximum timeout to prevent resource exhaustion
        if tool_config["timeout_sec"] > 300:  # 5 minutes max
            raise PolicyValidationError(
                f"Tool '{tool_name}' timeout_sec exceeds maximum allowed (300 seconds)"
            )

        # Validate optional notify field
        if "notify" in tool_config:
            if not isinstance(tool_config["notify"], list):
                raise PolicyValidationError(f"Tool '{tool_name}' notify must be a list")

            valid_notify_types = ["success", "failure", "need_confirm"]
            for notify_type in tool_config["notify"]:
                if notify_type not in valid_notify_types:
                    raise PolicyValidationError(
                        f"Tool '{tool_name}' invalid notify type: {notify_type}. "
                        f"Valid types: {valid_notify_types}"
                    )

    def _load_config(self, config_data: dict[str, Any]) -> None:
        """
        Load global configuration settings.

        Args:
            config_data: Config section from policy file
        """
        # Set defaults
        defaults = {
            "output_truncate_limit": 10240,
            "default_timeout_sec": 30,
            "audit_log_path": "/var/log/agentops/audit.jsonl",
            "blog_stage_root": "/app/data/blog/stage",
            "blog_publish_root": "/app/data/blog/public",
            "allowed_blog_extensions": [".md", ".markdown"],
        }

        # Override with values from config file
        config_values: dict[str, Any] = defaults.copy()
        config_values.update(config_data)

        # Handle nested security config
        if "security" in config_data:
            security_config = config_data["security"]
            if "blog_stage_root" in security_config:
                config_values["blog_stage_root"] = security_config["blog_stage_root"]
            if "blog_publish_root" in security_config:
                config_values["blog_publish_root"] = security_config[
                    "blog_publish_root"
                ]
            if "allowed_blog_extensions" in security_config:
                config_values["allowed_blog_extensions"] = security_config[
                    "allowed_blog_extensions"
                ]

        self._config = PolicyConfig(
            output_truncate_limit=int(config_values["output_truncate_limit"]),
            default_timeout_sec=int(config_values["default_timeout_sec"]),
            audit_log_path=str(config_values["audit_log_path"]),
            blog_stage_root=str(config_values["blog_stage_root"]),
            blog_publish_root=str(config_values["blog_publish_root"]),
            allowed_blog_extensions=[
                str(ext) for ext in config_values["allowed_blog_extensions"]
            ],
        )

    def get_tool_definition(self, tool_name: str) -> ToolDefinition | None:
        """
        Get tool definition by name.

        Args:
            tool_name: Name of the tool

        Returns:
            ToolDefinition if found, None otherwise

        Raises:
            RuntimeError: If policy has not been loaded
        """
        if not self._loaded:
            raise RuntimeError("Policy must be loaded before accessing tools")

        return self._tools.get(tool_name)

    def get_all_tools(self) -> dict[str, ToolDefinition]:
        """
        Get all tool definitions.

        Returns:
            Dictionary mapping tool names to ToolDefinition objects

        Raises:
            RuntimeError: If policy has not been loaded
        """
        if not self._loaded:
            raise RuntimeError("Policy must be loaded before accessing tools")

        return self._tools.copy()

    def get_config(self) -> PolicyConfig:
        """
        Get global policy configuration.

        Returns:
            PolicyConfig object

        Raises:
            RuntimeError: If policy has not been loaded
        """
        if not self._loaded:
            raise RuntimeError("Policy must be loaded before accessing config")

        assert self._config is not None, "Config should be loaded"  # nosec B101
        return self._config

    def is_loaded(self) -> bool:
        """
        Check if policy has been successfully loaded.

        Returns:
            True if policy is loaded, False otherwise
        """
        return self._loaded


class SchemaValidator:
    """
    Validates tool arguments against JSON Schema definitions.

    The SchemaValidator provides JSON Schema 2020-12 validation for tool
    arguments, ensuring that all inputs conform to the expected structure
    and types before tool execution.
    """

    def __init__(self) -> None:
        """Initialize SchemaValidator with JSON Schema 2020-12 support."""
        # Use Draft 2020-12 validator for modern JSON Schema support
        self._validator_class = jsonschema.Draft202012Validator

    def validate_args(
        self, args: dict[str, Any], schema: dict[str, Any], tool_name: str
    ) -> None:
        """
        Validate tool arguments against a JSON schema.

        Args:
            args: Arguments to validate
            schema: JSON schema to validate against
            tool_name: Name of the tool (for error messages)

        Raises:
            SchemaValidationError: If validation fails with descriptive error message
        """
        try:
            # Validate schema complexity to prevent DoS
            self._validate_schema_complexity(schema, tool_name)

            # Create validator instance
            validator = self._validator_class(schema)

            # Validate arguments
            errors = list(validator.iter_errors(args))

            if errors:
                # Format validation errors into a descriptive message
                error_messages = []
                for error in errors:
                    # Build path to the invalid field
                    field_path = (
                        ".".join(str(p) for p in error.absolute_path)
                        if error.absolute_path
                        else "root"
                    )

                    # Create descriptive error message
                    if error.validator == "required":
                        missing_field = (
                            error.message.split("'")[1]
                            if "'" in error.message
                            else "unknown"
                        )
                        error_messages.append(
                            f"Missing required field: {missing_field}"
                        )
                    elif error.validator == "type":
                        expected_type = error.schema.get("type", "unknown")
                        actual_value = error.instance
                        error_messages.append(
                            f"Field '{field_path}' has invalid type. "
                            f"Expected {expected_type}, got {type(actual_value).__name__}: {actual_value}"
                        )
                    elif error.validator == "pattern":
                        pattern = error.schema.get("pattern", "unknown")
                        actual_value = error.instance
                        error_messages.append(
                            f"Field '{field_path}' does not match required pattern '{pattern}'. "
                            f"Got: {actual_value}"
                        )
                    elif error.validator == "minItems":
                        min_items = error.schema.get("minItems", 0)
                        actual_length = (
                            len(error.instance)
                            if hasattr(error.instance, "__len__")
                            else 0
                        )
                        error_messages.append(
                            f"Field '{field_path}' must have at least {min_items} items. "
                            f"Got {actual_length} items"
                        )
                    elif error.validator == "maxLength":
                        max_length = error.schema.get("maxLength", 0)
                        actual_length = (
                            len(error.instance)
                            if hasattr(error.instance, "__len__")
                            else 0
                        )
                        error_messages.append(
                            f"Field '{field_path}' exceeds maximum length of {max_length}. "
                            f"Got {actual_length} characters"
                        )
                    elif error.validator == "additionalProperties":
                        error_messages.append(
                            f"Field '{field_path}' contains unexpected properties. "
                            f"Only defined properties are allowed"
                        )
                    else:
                        # Generic error message for other validation failures
                        error_messages.append(f"Field '{field_path}': {error.message}")

                # Combine all error messages
                combined_errors = "; ".join(error_messages)
                raise SchemaValidationError(
                    f"Tool '{tool_name}' argument validation failed: {combined_errors}"
                )

        except jsonschema.SchemaError as e:
            # Schema itself is invalid
            raise SchemaValidationError(
                f"Tool '{tool_name}' has invalid JSON schema: {e.message}"
            )
        except Exception as e:
            # Unexpected error during validation
            raise SchemaValidationError(
                f"Tool '{tool_name}' validation error: {str(e)}"
            )

    def validate_schema(self, schema: dict[str, Any], tool_name: str) -> None:
        """
        Validate that a JSON schema is well-formed.

        Args:
            schema: JSON schema to validate
            tool_name: Name of the tool (for error messages)

        Raises:
            SchemaValidationError: If schema is invalid
        """
        try:
            # Check if schema is valid by creating a validator
            self._validator_class.check_schema(schema)
        except jsonschema.SchemaError as e:
            raise SchemaValidationError(
                f"Tool '{tool_name}' has invalid JSON schema: {e.message}"
            )
        except Exception as e:
            raise SchemaValidationError(
                f"Tool '{tool_name}' schema validation error: {str(e)}"
            )

    def _validate_schema_complexity(
        self, schema: dict[str, Any], tool_name: str
    ) -> None:
        """
        Validate schema complexity to prevent resource exhaustion.

        Args:
            schema: JSON schema to validate
            tool_name: Name of the tool (for error messages)

        Raises:
            SchemaValidationError: If schema is too complex
        """

        def count_schema_nodes(obj: Any, depth: int = 0) -> int:
            if depth > 20:  # Max nesting depth
                raise SchemaValidationError(
                    f"Tool '{tool_name}' schema too deeply nested"
                )

            count = 1
            if isinstance(obj, dict):
                if len(obj) > 100:  # Max properties per object
                    raise SchemaValidationError(
                        f"Tool '{tool_name}' schema too complex"
                    )
                for value in obj.values():
                    count += count_schema_nodes(value, depth + 1)
            elif isinstance(obj, list):
                if len(obj) > 50:  # Max array items
                    raise SchemaValidationError(
                        f"Tool '{tool_name}' schema array too large"
                    )
                for item in obj:
                    count += count_schema_nodes(item, depth + 1)

            return count

        total_nodes = count_schema_nodes(schema)
        if total_nodes > 1000:  # Max total schema nodes
            raise SchemaValidationError(f"Tool '{tool_name}' schema too complex")

    def get_schema_errors(
        self, args: dict[str, Any], schema: dict[str, Any]
    ) -> list[str]:
        """
        Get list of validation errors without raising an exception.

        Args:
            args: Arguments to validate
            schema: JSON schema to validate against

        Returns:
            List of error messages, empty if validation passes
        """
        try:
            validator = self._validator_class(schema)
            errors = list(validator.iter_errors(args))

            error_messages = []
            for error in errors:
                field_path = (
                    ".".join(str(p) for p in error.absolute_path)
                    if error.absolute_path
                    else "root"
                )
                error_messages.append(f"{field_path}: {error.message}")

            return error_messages

        except Exception:
            return ["Schema validation failed due to internal error"]


class ToolRegistry:
    """
    Manages available tools and provides lookup and validation methods.

    The ToolRegistry acts as a central registry for all available tools,
    providing methods to look up tools, validate their existence, and
    get tool metadata for MCP protocol responses.
    """

    def __init__(self, policy_loader: PolicyLoader, schema_validator: SchemaValidator):
        """
        Initialize ToolRegistry with policy loader and schema validator.

        Args:
            policy_loader: PolicyLoader instance for accessing tool definitions
            schema_validator: SchemaValidator instance for argument validation
        """
        self.policy_loader = policy_loader
        self.schema_validator = schema_validator
        self._tools: dict[str, ToolDefinition] = {}
        self._initialized = False

    def initialize(self) -> None:
        """
        Initialize the registry by loading tools from policy.

        Raises:
            RuntimeError: If policy loader is not loaded
            SchemaValidationError: If any tool has invalid schema
        """
        if not self.policy_loader.is_loaded():
            raise RuntimeError(
                "Policy loader must be loaded before initializing registry"
            )

        # Load all tools from policy
        self._tools = self.policy_loader.get_all_tools()

        # Validate all tool schemas
        for tool_name, tool_def in self._tools.items():
            try:
                self.schema_validator.validate_schema(tool_def.args_schema, tool_name)
            except SchemaValidationError as e:
                raise SchemaValidationError(
                    f"Tool '{tool_name}' has invalid schema: {e}"
                )

        self._initialized = True

    def is_initialized(self) -> bool:
        """
        Check if registry has been initialized.

        Returns:
            True if initialized, False otherwise
        """
        return self._initialized

    def get_tool(self, tool_name: str) -> ToolDefinition | None:
        """
        Get tool definition by name.

        Args:
            tool_name: Name of the tool to retrieve

        Returns:
            ToolDefinition if found, None otherwise

        Raises:
            RuntimeError: If registry is not initialized
        """
        if not self._initialized:
            raise RuntimeError("Registry must be initialized before accessing tools")

        return self._tools.get(tool_name)

    def has_tool(self, tool_name: str) -> bool:
        """
        Check if a tool exists in the registry.

        Args:
            tool_name: Name of the tool to check

        Returns:
            True if tool exists, False otherwise

        Raises:
            RuntimeError: If registry is not initialized
        """
        if not self._initialized:
            raise RuntimeError("Registry must be initialized before checking tools")

        return tool_name in self._tools

    def get_all_tool_names(self) -> list[str]:
        """
        Get list of all available tool names.

        Returns:
            List of tool names

        Raises:
            RuntimeError: If registry is not initialized
        """
        if not self._initialized:
            raise RuntimeError("Registry must be initialized before accessing tools")

        return list(self._tools.keys())

    def get_all_tools(self) -> dict[str, ToolDefinition]:
        """
        Get all tool definitions.

        Returns:
            Dictionary mapping tool names to ToolDefinition objects

        Raises:
            RuntimeError: If registry is not initialized
        """
        if not self._initialized:
            raise RuntimeError("Registry must be initialized before accessing tools")

        return self._tools.copy()

    def validate_tool_args(self, tool_name: str, args: dict[str, Any]) -> None:
        """
        Validate arguments for a specific tool.

        Args:
            tool_name: Name of the tool
            args: Arguments to validate

        Raises:
            ValueError: If tool does not exist
            SchemaValidationError: If arguments are invalid
            RuntimeError: If registry is not initialized
        """
        if not self._initialized:
            raise RuntimeError(
                "Registry must be initialized before validating arguments"
            )

        tool_def = self.get_tool(tool_name)
        if tool_def is None:
            raise ValueError(f"Tool '{tool_name}' not found in registry")

        self.schema_validator.validate_args(args, tool_def.args_schema, tool_name)

    def get_tool_metadata(self, tool_name: str) -> dict[str, Any] | None:
        """
        Get tool metadata for MCP protocol responses.

        Args:
            tool_name: Name of the tool

        Returns:
            Dictionary with tool metadata or None if tool not found

        Raises:
            RuntimeError: If registry is not initialized
        """
        if not self._initialized:
            raise RuntimeError("Registry must be initialized before accessing metadata")

        tool_def = self.get_tool(tool_name)
        if tool_def is None:
            return None

        return {
            "name": tool_def.name,
            "description": tool_def.description,
            "inputSchema": {
                "type": "object",
                "properties": tool_def.args_schema.get("properties", {}),
                "required": tool_def.args_schema.get("required", []),
                "additionalProperties": tool_def.args_schema.get(
                    "additionalProperties", False
                ),
            },
        }

    def get_all_tool_metadata(self) -> list[dict[str, Any]]:
        """
        Get metadata for all tools for MCP list_tools response.

        Returns:
            List of tool metadata dictionaries

        Raises:
            RuntimeError: If registry is not initialized
        """
        if not self._initialized:
            raise RuntimeError("Registry must be initialized before accessing metadata")

        metadata_list = []
        for tool_name in self._tools.keys():
            metadata = self.get_tool_metadata(tool_name)
            if metadata:
                metadata_list.append(metadata)

        return metadata_list

    def get_mutating_tools(self) -> list[str]:
        """
        Get list of tools that mutate system state.

        Returns:
            List of tool names that have mutates=True

        Raises:
            RuntimeError: If registry is not initialized
        """
        if not self._initialized:
            raise RuntimeError("Registry must be initialized before accessing tools")

        return [name for name, tool_def in self._tools.items() if tool_def.mutates]

    def get_confirmation_required_tools(self) -> list[str]:
        """
        Get list of tools that require confirmation.

        Returns:
            List of tool names that have requires_confirm=True

        Raises:
            RuntimeError: If registry is not initialized
        """
        if not self._initialized:
            raise RuntimeError("Registry must be initialized before accessing tools")

        return [
            name for name, tool_def in self._tools.items() if tool_def.requires_confirm
        ]
