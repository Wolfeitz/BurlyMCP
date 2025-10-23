"""
Unit tests for burly_mcp.server.main module.

Tests the main server entry point, configuration loading, initialization,
and error handling scenarios.
"""

import logging
import os
import signal
import sys
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, Mock, patch, call
import pytest

from burly_mcp.server.main import (
    setup_logging,
    load_configuration,
    initialize_policy_engine,
    initialize_audit_system,
    initialize_notification_system,
    setup_signal_handlers,
    validate_environment,
    main,
)


class TestSetupLogging:
    """Test logging configuration setup."""

    def test_setup_logging_default_level(self):
        """Test logging setup with default INFO level."""
        with patch.dict(os.environ, {}, clear=True):
            with patch("pathlib.Path.mkdir"):
                logger = setup_logging()
                assert logger.name == "burly_mcp.server.main"
                assert logging.getLogger().level == logging.INFO

    def test_setup_logging_custom_level(self):
        """Test logging setup with custom DEBUG level."""
        with patch.dict(os.environ, {"LOG_LEVEL": "DEBUG"}):
            with patch("pathlib.Path.mkdir"):
                logger = setup_logging()
                assert logging.getLogger().level == logging.DEBUG

    def test_setup_logging_invalid_level(self):
        """Test logging setup with invalid level falls back to INFO."""
        with patch.dict(os.environ, {"LOG_LEVEL": "INVALID"}):
            with patch("pathlib.Path.mkdir"):
                logger = setup_logging()
                assert logging.getLogger().level == logging.INFO

    def test_setup_logging_custom_log_dir(self):
        """Test logging setup with custom log directory."""
        with tempfile.TemporaryDirectory() as temp_dir:
            with patch.dict(os.environ, {"LOG_DIR": temp_dir}):
                logger = setup_logging()
                assert logger.name == "burly_mcp.server.main"
                # Check that log file was created
                log_file = Path(temp_dir) / "burly-mcp.log"
                assert log_file.exists()

    def test_setup_logging_permission_error(self):
        """Test logging setup handles permission errors gracefully."""
        with patch.dict(os.environ, {"LOG_DIR": "/root/restricted"}):
            with patch("pathlib.Path.mkdir", side_effect=PermissionError("Access denied")):
                with patch("logging.handlers.RotatingFileHandler") as mock_handler:
                    # Should not raise exception, just continue with console logging
                    logger = setup_logging()
                    assert logger.name == "burly_mcp.server.main"

    def test_setup_logging_file_handler_error(self):
        """Test logging setup handles file handler creation errors."""
        with tempfile.TemporaryDirectory() as temp_dir:
            with patch.dict(os.environ, {"LOG_DIR": temp_dir}):
                with patch("logging.handlers.RotatingFileHandler", side_effect=OSError("Disk full")):
                    logger = setup_logging()
                    assert logger.name == "burly_mcp.server.main"


class TestLoadConfiguration:
    """Test configuration loading from environment."""

    def test_load_configuration_defaults(self):
        """Test configuration loading with all defaults."""
        with patch.dict(os.environ, {}, clear=True):
            config = load_configuration()
            
            assert config["policy_file"] == "config/policy/tools.yaml"
            assert config["blog_stage_root"] == "/app/data/blog/stage"
            assert config["blog_publish_root"] == "/app/data/blog/public"
            assert config["default_timeout"] == 30
            assert config["output_limit"] == 10240
            assert config["audit_log_path"] == "/var/log/agentops/audit.jsonl"
            assert config["notifications_enabled"] is True
            assert config["gotify_url"] == ""
            assert config["gotify_token"] == ""
            assert config["server_name"] == "burly-mcp"
            assert config["server_version"] == "0.1.0"

    def test_load_configuration_custom_values(self):
        """Test configuration loading with custom environment values."""
        env_vars = {
            "POLICY_FILE": "/custom/policy.yaml",
            "BLOG_STAGE_ROOT": "/custom/stage",
            "BLOG_PUBLISH_ROOT": "/custom/public",
            "DEFAULT_TIMEOUT_SEC": "60",
            "OUTPUT_TRUNCATE_LIMIT": "20480",
            "AUDIT_LOG_PATH": "/custom/audit.log",
            "NOTIFICATIONS_ENABLED": "false",
            "GOTIFY_URL": "https://gotify.example.com",
            "GOTIFY_TOKEN": "secret-token",
            "SERVER_NAME": "custom-server",
            "SERVER_VERSION": "1.0.0",
        }
        
        with patch.dict(os.environ, env_vars):
            config = load_configuration()
            
            assert config["policy_file"] == "/custom/policy.yaml"
            assert config["blog_stage_root"] == "/custom/stage"
            assert config["blog_publish_root"] == "/custom/public"
            assert config["default_timeout"] == 60
            assert config["output_limit"] == 20480
            assert config["audit_log_path"] == "/custom/audit.log"
            assert config["notifications_enabled"] is False
            assert config["gotify_url"] == "https://gotify.example.com"
            assert config["gotify_token"] == "secret-token"
            assert config["server_name"] == "custom-server"
            assert config["server_version"] == "1.0.0"

    def test_load_configuration_boolean_variations(self):
        """Test configuration boolean parsing variations."""
        test_cases = [
            ("true", True),
            ("True", True),
            ("TRUE", True),
            ("1", True),
            ("yes", True),
            ("false", False),
            ("False", False),
            ("FALSE", False),
            ("0", False),
            ("no", False),
            ("", False),
            ("invalid", False),
        ]
        
        for env_value, expected in test_cases:
            with patch.dict(os.environ, {"NOTIFICATIONS_ENABLED": env_value}):
                config = load_configuration()
                assert config["notifications_enabled"] is expected


class TestInitializePolicyEngine:
    """Test policy engine initialization."""

    @patch("burly_mcp.server.main.PolicyToolRegistry")
    @patch("burly_mcp.server.main.SchemaValidator")
    @patch("burly_mcp.server.main.PolicyLoader")
    def test_initialize_policy_engine_success(self, mock_policy_loader_class, mock_schema_validator_class, mock_registry_class):
        """Test successful policy engine initialization."""
        # Setup mocks
        mock_policy_loader = Mock()
        mock_policy_loader.get_all_tools.return_value = ["tool1", "tool2", "tool3"]
        mock_policy_loader_class.return_value = mock_policy_loader
        
        mock_schema_validator = Mock()
        mock_schema_validator_class.return_value = mock_schema_validator
        
        mock_registry = Mock()
        mock_registry_class.return_value = mock_registry
        
        config = {"policy_file": "/test/policy.yaml"}
        logger = Mock()
        
        # Call function
        result = initialize_policy_engine(config, logger)
        
        # Verify calls
        mock_policy_loader_class.assert_called_once_with("/test/policy.yaml")
        mock_policy_loader.load_policy.assert_called_once()
        mock_schema_validator_class.assert_called_once()
        mock_registry_class.assert_called_once_with(mock_policy_loader, mock_schema_validator)
        mock_registry.initialize.assert_called_once()
        
        # Verify logging
        logger.info.assert_any_call("Loading policy from: /test/policy.yaml")
        logger.info.assert_any_call("Policy loaded successfully with 3 tools")
        logger.info.assert_any_call("Policy engine initialized successfully")
        
        assert result == mock_registry

    @patch("burly_mcp.server.main.PolicyLoader")
    @patch("sys.exit")
    def test_initialize_policy_engine_failure(self, mock_exit, mock_policy_loader_class):
        """Test policy engine initialization failure."""
        # Setup mock to raise exception
        mock_policy_loader_class.side_effect = Exception("Policy load failed")
        
        config = {"policy_file": "/test/policy.yaml"}
        logger = Mock()
        
        # Call function
        initialize_policy_engine(config, logger)
        
        # Verify error handling
        logger.critical.assert_any_call("Failed to initialize policy engine: Policy load failed")
        logger.critical.assert_any_call("Cannot start server without valid policy configuration")
        mock_exit.assert_called_once_with(1)


class TestInitializeAuditSystem:
    """Test audit system initialization."""

    @patch("burly_mcp.server.main.get_audit_logger")
    def test_initialize_audit_system_success(self, mock_get_audit_logger):
        """Test successful audit system initialization."""
        mock_audit_logger = Mock()
        mock_get_audit_logger.return_value = mock_audit_logger
        
        config = {"audit_log_path": "/test/audit.log"}
        logger = Mock()
        
        result = initialize_audit_system(config, logger)
        
        mock_get_audit_logger.assert_called_once_with("/test/audit.log")
        logger.info.assert_called_once_with("Audit logging initialized: /test/audit.log")
        assert result == mock_audit_logger

    @patch("burly_mcp.server.main.get_audit_logger")
    def test_initialize_audit_system_failure(self, mock_get_audit_logger):
        """Test audit system initialization failure."""
        mock_get_audit_logger.side_effect = Exception("Audit init failed")
        
        config = {"audit_log_path": "/test/audit.log"}
        logger = Mock()
        
        result = initialize_audit_system(config, logger)
        
        logger.error.assert_called_once_with("Failed to initialize audit system: Audit init failed")
        logger.warning.assert_called_once_with("Continuing without audit logging (not recommended)")
        assert result is None


class TestInitializeNotificationSystem:
    """Test notification system initialization."""

    @patch("burly_mcp.server.main.get_notification_manager")
    def test_initialize_notification_system_disabled(self, mock_get_notification_manager):
        """Test notification system when disabled."""
        config = {"notifications_enabled": False}
        logger = Mock()
        
        result = initialize_notification_system(config, logger)
        
        logger.info.assert_called_once_with("Notifications disabled by configuration")
        mock_get_notification_manager.assert_not_called()
        assert result is False

    @patch("burly_mcp.server.main.get_notification_manager")
    def test_initialize_notification_system_enabled_success(self, mock_get_notification_manager):
        """Test successful notification system initialization."""
        mock_manager = Mock()
        mock_manager.get_status.return_value = {
            "enabled": True,
            "providers": [
                {"name": "console", "available": True},
                {"name": "gotify", "available": True},
            ]
        }
        mock_get_notification_manager.return_value = mock_manager
        
        config = {"notifications_enabled": True}
        logger = Mock()
        
        result = initialize_notification_system(config, logger)
        
        mock_get_notification_manager.assert_called_once()
        logger.info.assert_called_once_with("Notifications enabled with providers: ['console', 'gotify']")
        assert result is True

    @patch("burly_mcp.server.main.get_notification_manager")
    def test_initialize_notification_system_no_providers(self, mock_get_notification_manager):
        """Test notification system with no available providers."""
        mock_manager = Mock()
        mock_manager.get_status.return_value = {
            "enabled": False,
            "providers": []
        }
        mock_get_notification_manager.return_value = mock_manager
        
        config = {"notifications_enabled": True}
        logger = Mock()
        
        result = initialize_notification_system(config, logger)
        
        logger.warning.assert_called_once_with("Notifications enabled but no providers available")
        assert result is False

    @patch("burly_mcp.server.main.get_notification_manager")
    def test_initialize_notification_system_exception(self, mock_get_notification_manager):
        """Test notification system initialization exception."""
        mock_get_notification_manager.side_effect = Exception("Notification init failed")
        
        config = {"notifications_enabled": True}
        logger = Mock()
        
        result = initialize_notification_system(config, logger)
        
        logger.error.assert_called_once_with("Failed to initialize notification system: Notification init failed")
        logger.warning.assert_called_once_with("Continuing without notifications")
        assert result is False


class TestSetupSignalHandlers:
    """Test signal handler setup."""

    @patch("signal.signal")
    def test_setup_signal_handlers(self, mock_signal):
        """Test signal handler registration."""
        logger = Mock()
        
        setup_signal_handlers(logger)
        
        # Verify signal handlers were registered
        expected_calls = [
            call(signal.SIGTERM, mock_signal.call_args_list[0][0][1]),
            call(signal.SIGINT, mock_signal.call_args_list[1][0][1]),
        ]
        
        # Check that SIGTERM and SIGINT were registered
        assert mock_signal.call_count >= 2
        assert mock_signal.call_args_list[0][0][0] == signal.SIGTERM
        assert mock_signal.call_args_list[1][0][0] == signal.SIGINT

    @patch("signal.signal")
    @patch("sys.exit")
    def test_signal_handler_execution(self, mock_exit, mock_signal):
        """Test signal handler execution."""
        logger = Mock()
        
        setup_signal_handlers(logger)
        
        # Get the signal handler function
        signal_handler = mock_signal.call_args_list[0][0][1]
        
        # Call the signal handler
        signal_handler(signal.SIGTERM, None)
        
        # Verify logging and exit
        logger.info.assert_any_call("Received SIGTERM, initiating graceful shutdown...")
        logger.info.assert_any_call("Shutdown complete")
        mock_exit.assert_called_once_with(0)


class TestValidateEnvironment:
    """Test environment validation."""

    def test_validate_environment_success(self):
        """Test successful environment validation."""
        with tempfile.TemporaryDirectory() as temp_dir:
            policy_file = Path(temp_dir) / "policy.yaml"
            policy_file.write_text("test: policy")
            
            stage_dir = Path(temp_dir) / "stage"
            stage_dir.mkdir()
            
            publish_dir = Path(temp_dir) / "publish"
            publish_dir.mkdir()
            
            audit_dir = Path(temp_dir) / "audit"
            audit_dir.mkdir()
            
            config = {
                "policy_file": str(policy_file),
                "blog_stage_root": str(stage_dir),
                "blog_publish_root": str(publish_dir),
                "audit_log_path": str(audit_dir / "audit.log"),
            }
            logger = Mock()
            
            result = validate_environment(config, logger)
            
            assert result is True
            logger.info.assert_called_once_with("Environment validation passed")

    def test_validate_environment_missing_policy(self):
        """Test environment validation with missing policy file."""
        config = {
            "policy_file": "/nonexistent/policy.yaml",
            "blog_stage_root": "",
            "blog_publish_root": "",
            "audit_log_path": "/tmp/audit.log",
        }
        logger = Mock()
        
        result = validate_environment(config, logger)
        
        assert result is False
        logger.error.assert_any_call("Environment validation failed:")
        logger.error.assert_any_call("  - Policy file not found: /nonexistent/policy.yaml")

    def test_validate_environment_directory_permissions(self):
        """Test environment validation with directory permission issues."""
        with tempfile.TemporaryDirectory() as temp_dir:
            policy_file = Path(temp_dir) / "policy.yaml"
            policy_file.write_text("test: policy")
            
            config = {
                "policy_file": str(policy_file),
                "blog_stage_root": "/root/restricted",
                "blog_publish_root": "/root/restricted",
                "audit_log_path": "/root/restricted/audit.log",
            }
            logger = Mock()
            
            with patch("os.makedirs", side_effect=PermissionError("Access denied")):
                result = validate_environment(config, logger)
                
                assert result is False
                logger.error.assert_any_call("Environment validation failed:")


class TestMain:
    """Test main function."""
    
    def setup_method(self):
        """Reset global variables before each test."""
        import sys
        if 'burly_mcp.server.main' in sys.modules:
            main_module = sys.modules['burly_mcp.server.main']
            main_module._mcp_handler = None
            main_module._logger = None

    @patch("burly_mcp.server.main.MCPProtocolHandler")
    @patch("burly_mcp.server.main.ToolRegistry")
    @patch("burly_mcp.server.main.initialize_notification_system")
    @patch("burly_mcp.server.main.initialize_audit_system")
    @patch("burly_mcp.server.main.initialize_policy_engine")
    @patch("burly_mcp.server.main.validate_environment")
    @patch("burly_mcp.server.main.load_configuration")
    @patch("burly_mcp.server.main.setup_signal_handlers")
    @patch("burly_mcp.server.main.setup_logging")
    def test_main_success(self, mock_setup_logging, mock_setup_signal_handlers,
                         mock_load_configuration, mock_validate_environment,
                         mock_initialize_policy_engine, mock_initialize_audit_system,
                         mock_initialize_notification_system, mock_tool_registry_class,
                         mock_mcp_handler_class):
        """Test successful main function execution."""
        # Setup mocks
        mock_logger = Mock()
        mock_setup_logging.return_value = mock_logger
        
        mock_config = {
            "server_name": "test-server",
            "server_version": "1.0.0",
            "policy_file": "/test/policy.yaml",
            "notifications_enabled": True,
        }
        mock_load_configuration.return_value = mock_config
        
        mock_validate_environment.return_value = True
        
        mock_policy_registry = Mock()
        mock_initialize_policy_engine.return_value = mock_policy_registry
        
        mock_audit_logger = Mock()
        mock_initialize_audit_system.return_value = mock_audit_logger
        
        mock_initialize_notification_system.return_value = True
        
        mock_tool_registry = Mock()
        mock_tool_registry.tools = {"tool1": Mock(), "tool2": Mock()}
        mock_tool_registry_class.return_value = mock_tool_registry
        
        mock_mcp_handler = Mock()
        mock_mcp_handler_class.return_value = mock_mcp_handler
        
        # Call main
        main()
        
        # Verify initialization sequence
        mock_setup_logging.assert_called_once()
        mock_setup_signal_handlers.assert_called_once_with(mock_logger)
        mock_load_configuration.assert_called_once()
        mock_validate_environment.assert_called_once_with(mock_config, mock_logger)
        mock_initialize_policy_engine.assert_called_once_with(mock_config, mock_logger)
        mock_initialize_audit_system.assert_called_once_with(mock_config, mock_logger)
        mock_initialize_notification_system.assert_called_once_with(mock_config, mock_logger)
        mock_tool_registry_class.assert_called_once()
        mock_mcp_handler_class.assert_called_once_with(tool_registry=mock_tool_registry)
        mock_mcp_handler.run_protocol_loop.assert_called_once()

    @patch("burly_mcp.server.main.validate_environment")
    @patch("burly_mcp.server.main.load_configuration")
    @patch("burly_mcp.server.main.setup_signal_handlers")
    @patch("burly_mcp.server.main.setup_logging")
    @patch("sys.exit")
    def test_main_validation_failure(self, mock_exit, mock_setup_logging,
                                   mock_setup_signal_handlers, mock_load_configuration,
                                   mock_validate_environment):
        """Test main function with environment validation failure."""
        mock_logger = Mock()
        mock_setup_logging.return_value = mock_logger
        
        mock_config = {
            "server_name": "test-server",
            "server_version": "1.0.0",
            "policy_file": "/test/policy.yaml",
            "notifications_enabled": True,
        }
        mock_load_configuration.return_value = mock_config
        
        mock_validate_environment.return_value = False
        
        # Make sys.exit actually raise SystemExit to stop execution
        mock_exit.side_effect = SystemExit(1)
        
        with pytest.raises(SystemExit):
            main()
        
        mock_logger.critical.assert_called_once_with("Environment validation failed - cannot start server")
        mock_exit.assert_called_once_with(1)

    @patch("burly_mcp.server.main.setup_logging")
    @patch("sys.exit")
    def test_main_keyboard_interrupt(self, mock_exit, mock_setup_logging):
        """Test main function with keyboard interrupt."""
        mock_logger = Mock()
        mock_setup_logging.return_value = mock_logger
        
        with patch("burly_mcp.server.main.setup_signal_handlers", side_effect=KeyboardInterrupt()):
            main()
            
            mock_logger.info.assert_any_call("Received keyboard interrupt - shutting down")
            mock_exit.assert_called_once_with(0)

    @patch("burly_mcp.server.main.setup_logging")
    @patch("sys.exit")
    def test_main_critical_exception(self, mock_exit, mock_setup_logging):
        """Test main function with critical exception."""
        mock_logger = Mock()
        mock_setup_logging.return_value = mock_logger
        
        with patch("burly_mcp.server.main.setup_signal_handlers", side_effect=Exception("Critical error")):
            main()
            
            mock_logger.critical.assert_called_once_with("Critical error during startup: Critical error", exc_info=True)
            mock_exit.assert_called_once_with(1)

    @patch("sys.exit")
    def test_main_logging_failure(self, mock_exit):
        """Test main function with logging setup failure."""
        with patch("builtins.print") as mock_print:
            with patch("burly_mcp.server.main.setup_logging", side_effect=Exception("Logging failed")):
                # Make sys.exit actually raise SystemExit to stop execution
                mock_exit.side_effect = SystemExit(1)
                
                with pytest.raises(SystemExit):
                    main()
                
                mock_print.assert_called_once_with("Critical error during startup: Logging failed", file=sys.stderr)
                mock_exit.assert_called_once_with(1)