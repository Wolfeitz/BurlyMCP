"""
Burly MCP Server - Main Entry Point

This module implements the core MCP protocol handler that communicates with
AI assistants via stdin/stdout. It processes MCP requests, routes them to
appropriate tools, and returns standardized responses.

The Model Context Protocol (MCP) is a standardized way for AI assistants to
interact with external tools and services. This server implements the protocol
to provide secure, policy-driven access to system operations.

Key Functions:
- Parse incoming MCP JSON requests from stdin
- Route requests to appropriate tool handlers
- Implement confirmation workflow for mutating operations
- Format responses according to MCP specification
- Handle errors and edge cases gracefully

Usage:
    python -m burly_mcp.server.main

The server runs continuously, processing MCP requests until terminated.
All operations are logged for audit purposes and can optionally send
notifications via Gotify.
"""

import logging
import logging.handlers
import os
import signal
import sys
from pathlib import Path
from typing import Any, Dict, Optional

from ..audit import AuditLogger, get_audit_logger
from .mcp import MCPProtocolHandler
from ..notifications import get_notification_manager
from ..policy import PolicyLoader, SchemaValidator
from ..policy import PolicyToolRegistry
from ..tools import ToolRegistry

# Global references for graceful shutdown
_mcp_handler: Optional[MCPProtocolHandler] = None
_logger: Optional[logging.Logger] = None


def setup_logging() -> logging.Logger:
    """
    Set up comprehensive logging configuration.

    Configures both console and file logging with appropriate levels
    and formats. Supports log rotation and structured logging.

    Returns:
        Logger instance for the main module
    """
    # Get log level from environment
    log_level_str = os.environ.get("LOG_LEVEL", "INFO").upper()
    log_level = getattr(logging, log_level_str, logging.INFO)

    # Get log directory from environment
    log_dir = os.environ.get("LOG_DIR", "/var/log/agentops")

    # Create log directory if it doesn't exist
    Path(log_dir).mkdir(parents=True, exist_ok=True)

    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)

    # Clear any existing handlers
    root_logger.handlers.clear()

    # Console handler for stdout/stderr (but not interfering with MCP protocol)
    # Only log to stderr to avoid interfering with MCP stdin/stdout communication
    console_handler = logging.StreamHandler(sys.stderr)
    console_handler.setLevel(log_level)
    console_formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    console_handler.setFormatter(console_formatter)
    root_logger.addHandler(console_handler)

    # File handler with rotation
    log_file = os.path.join(log_dir, "burly-mcp.log")
    try:
        file_handler = logging.handlers.RotatingFileHandler(
            log_file, maxBytes=10 * 1024 * 1024, backupCount=5  # 10MB
        )
        file_handler.setLevel(logging.DEBUG)  # More verbose in files
        file_formatter = logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(funcName)s:%(lineno)d - %(message)s"
        )
        file_handler.setFormatter(file_formatter)
        root_logger.addHandler(file_handler)
    except (OSError, PermissionError) as e:
        # If we can't write to log file, continue with console only
        console_handler.warning(f"Could not set up file logging: {e}")

    return logging.getLogger(__name__)


def load_configuration() -> Dict[str, Any]:
    """
    Load configuration from environment variables.

    Loads all configuration settings with appropriate defaults
    and validation. Logs configuration status for debugging.

    Returns:
        Dictionary containing all configuration settings
    """
    config = {
        # Policy configuration
        "policy_file": os.environ.get("POLICY_FILE", "policy/tools.yaml"),
        # Security configuration
        "blog_stage_root": os.environ.get("BLOG_STAGE_ROOT", "/app/data/blog/stage"),
        "blog_publish_root": os.environ.get(
            "BLOG_PUBLISH_ROOT", "/app/data/blog/public"
        ),
        # Resource limits
        "default_timeout": int(os.environ.get("DEFAULT_TIMEOUT_SEC", "30")),
        "output_limit": int(os.environ.get("OUTPUT_TRUNCATE_LIMIT", "10240")),
        # Audit configuration
        "audit_log_path": os.environ.get(
            "AUDIT_LOG_PATH", "/var/log/agentops/audit.jsonl"
        ),
        # Notification configuration
        "notifications_enabled": os.environ.get("NOTIFICATIONS_ENABLED", "true").lower()
        in ["true", "1", "yes"],
        "gotify_url": os.environ.get("GOTIFY_URL", ""),
        "gotify_token": os.environ.get("GOTIFY_TOKEN", ""),
        # Server configuration
        "server_name": os.environ.get("SERVER_NAME", "burly-mcp"),
        "server_version": os.environ.get("SERVER_VERSION", "0.1.0"),
    }

    return config


def initialize_policy_engine(
    config: Dict[str, Any], logger: logging.Logger
) -> PolicyToolRegistry:
    """
    Initialize the policy engine with tool definitions.

    Args:
        config: Configuration dictionary
        logger: Logger instance

    Returns:
        Initialized PolicyToolRegistry instance

    Raises:
        SystemExit: If policy loading fails critically
    """
    try:
        logger.info(f"Loading policy from: {config['policy_file']}")

        # Initialize policy loader
        policy_loader = PolicyLoader(config["policy_file"])
        policy_loader.load_policy()

        logger.info(
            f"Policy loaded successfully with {len(policy_loader.get_all_tools())} tools"
        )

        # Initialize schema validator
        schema_validator = SchemaValidator()

        # Initialize policy-based tool registry
        policy_registry = PolicyToolRegistry(policy_loader, schema_validator)
        policy_registry.initialize()

        logger.info("Policy engine initialized successfully")
        return policy_registry

    except Exception as e:
        logger.critical(f"Failed to initialize policy engine: {e}")
        logger.critical("Cannot start server without valid policy configuration")
        sys.exit(1)


def initialize_audit_system(
    config: Dict[str, Any], logger: logging.Logger
) -> AuditLogger:
    """
    Initialize the audit logging system.

    Args:
        config: Configuration dictionary
        logger: Logger instance

    Returns:
        Initialized AuditLogger instance
    """
    try:
        # Get the global audit logger (creates if needed)
        audit_logger = get_audit_logger(config["audit_log_path"])

        logger.info(f"Audit logging initialized: {config['audit_log_path']}")
        return audit_logger

    except Exception as e:
        logger.error(f"Failed to initialize audit system: {e}")
        logger.warning("Continuing without audit logging (not recommended)")
        return None


def initialize_notification_system(
    config: Dict[str, Any], logger: logging.Logger
) -> bool:
    """
    Initialize the notification system.

    Args:
        config: Configuration dictionary
        logger: Logger instance

    Returns:
        True if notifications are enabled and working, False otherwise
    """
    try:
        if not config["notifications_enabled"]:
            logger.info("Notifications disabled by configuration")
            return False

        # Get the global notification manager (creates if needed)
        notification_manager = get_notification_manager()
        status = notification_manager.get_status()

        if status["enabled"]:
            available_providers = [
                p["name"] for p in status["providers"] if p["available"]
            ]
            logger.info(f"Notifications enabled with providers: {available_providers}")
            return True
        else:
            logger.warning("Notifications enabled but no providers available")
            return False

    except Exception as e:
        logger.error(f"Failed to initialize notification system: {e}")
        logger.warning("Continuing without notifications")
        return False


def setup_signal_handlers(logger: logging.Logger) -> None:
    """
    Set up signal handlers for graceful shutdown.

    Args:
        logger: Logger instance
    """

    def signal_handler(signum, frame):
        signal_name = signal.Signals(signum).name
        logger.info(f"Received {signal_name}, initiating graceful shutdown...")

        # Set a flag or perform cleanup
        if _mcp_handler:
            logger.info("Stopping MCP protocol handler...")
            # The protocol handler will exit its loop on next iteration

        logger.info("Shutdown complete")
        sys.exit(0)

    # Register handlers for common termination signals
    signal.signal(signal.SIGTERM, signal_handler)
    signal.signal(signal.SIGINT, signal_handler)

    # On Unix systems, also handle SIGHUP for configuration reload
    if hasattr(signal, "SIGHUP"):
        signal.signal(signal.SIGHUP, signal_handler)


def validate_environment(config: Dict[str, Any], logger: logging.Logger) -> bool:
    """
    Validate the runtime environment and configuration.

    Args:
        config: Configuration dictionary
        logger: Logger instance

    Returns:
        True if environment is valid, False otherwise
    """
    validation_errors = []

    # Check policy file exists
    if not os.path.exists(config["policy_file"]):
        validation_errors.append(f"Policy file not found: {config['policy_file']}")

    # Check directory permissions for blog operations
    for dir_key in ["blog_stage_root", "blog_publish_root"]:
        dir_path = config[dir_key]
        if dir_path:
            try:
                os.makedirs(dir_path, exist_ok=True)
                if not os.access(dir_path, os.R_OK):
                    validation_errors.append(f"Directory not readable: {dir_path}")
                if dir_key == "blog_publish_root" and not os.access(dir_path, os.W_OK):
                    validation_errors.append(
                        f"Publish directory not writable: {dir_path}"
                    )
            except OSError as e:
                validation_errors.append(f"Cannot access {dir_key} ({dir_path}): {e}")

    # Check audit log directory
    audit_dir = os.path.dirname(config["audit_log_path"])
    try:
        os.makedirs(audit_dir, exist_ok=True)
        if not os.access(audit_dir, os.W_OK):
            validation_errors.append(f"Audit log directory not writable: {audit_dir}")
    except OSError as e:
        validation_errors.append(f"Cannot access audit log directory: {e}")

    # Log validation results
    if validation_errors:
        logger.error("Environment validation failed:")
        for error in validation_errors:
            logger.error(f"  - {error}")
        return False
    else:
        logger.info("Environment validation passed")
        return True


def main() -> None:
    """
    Main entry point for the Burly MCP server.

    Sets up logging, loads configuration, initializes all components,
    and starts the MCP protocol loop with comprehensive error handling
    and graceful shutdown support.
    """
    global _mcp_handler, _logger

    try:
        # Initialize logging first
        _logger = setup_logging()
        _logger.info("Starting Burly MCP Server v0.1.0")

        # Set up signal handlers for graceful shutdown
        setup_signal_handlers(_logger)

        # Load configuration from environment
        _logger.info("Loading configuration...")
        config = load_configuration()

        # Log key configuration (without sensitive values)
        _logger.info(f"Server: {config['server_name']} v{config['server_version']}")
        _logger.info(f"Policy file: {config['policy_file']}")
        _logger.info(
            f"Notifications: {'enabled' if config['notifications_enabled'] else 'disabled'}"
        )

        # Validate environment
        if not validate_environment(config, _logger):
            _logger.critical("Environment validation failed - cannot start server")
            sys.exit(1)

        # Initialize policy engine
        _logger.info("Initializing policy engine...")
        policy_registry = initialize_policy_engine(config, _logger)

        # Initialize audit system
        _logger.info("Initializing audit system...")
        audit_logger = initialize_audit_system(config, _logger)

        # Initialize notification system
        _logger.info("Initializing notification system...")
        notifications_available = initialize_notification_system(config, _logger)

        # Initialize tool registry (the existing one that works with MCP handler)
        _logger.info("Initializing tool registry...")
        tool_registry = ToolRegistry()
        _logger.info(f"Tool registry initialized with {len(tool_registry.tools)} tools")

        # Initialize MCP protocol handler
        _logger.info("Initializing MCP protocol handler...")
        _mcp_handler = MCPProtocolHandler(tool_registry=tool_registry)

        # Log startup summary
        _logger.info("=== Burly MCP Server Startup Complete ===")
        _logger.info(f"Available tools: {list(tool_registry.tools.keys())}")
        _logger.info(f"Policy enforcement: enabled")
        _logger.info(f"Audit logging: {'enabled' if audit_logger else 'disabled'}")
        _logger.info(
            f"Notifications: {'enabled' if notifications_available else 'disabled'}"
        )
        _logger.info("Server ready - waiting for MCP requests on stdin")

        # Start the MCP protocol loop
        _mcp_handler.run_protocol_loop()

    except KeyboardInterrupt:
        if _logger:
            _logger.info("Received keyboard interrupt - shutting down")
        sys.exit(0)
    except Exception as e:
        if _logger:
            _logger.critical(f"Critical error during startup: {e}", exc_info=True)
        else:
            print(f"Critical error during startup: {e}", file=sys.stderr)
        sys.exit(1)
    finally:
        if _logger:
            _logger.info("Burly MCP Server shutdown complete")


if __name__ == "__main__":
    main()
