"""
Unit tests for the Burly MCP audit module.
"""

import pytest
from unittest.mock import Mock, patch, mock_open
from pathlib import Path
import json
import logging
from datetime import datetime


class TestAuditLogger:
    """Test the audit logging functionality."""

    @patch("burly_mcp.audit.logging.getLogger")
    def test_audit_logger_initialization(self, mock_get_logger):
        """Test audit logger initialization."""
        from burly_mcp.audit import get_audit_logger

        mock_logger = Mock()
        mock_get_logger.return_value = mock_logger

        logger = get_audit_logger()

        mock_get_logger.assert_called_once_with("burly_mcp.audit")
        assert logger == mock_logger

    @patch("burly_mcp.audit.logging.getLogger")
    @patch("burly_mcp.audit.logging.FileHandler")
    def test_audit_logger_file_handler_setup(self, mock_file_handler, mock_get_logger):
        """Test audit logger file handler setup."""
        from burly_mcp.audit import setup_audit_logging

        mock_logger = Mock()
        mock_get_logger.return_value = mock_logger
        mock_handler = Mock()
        mock_file_handler.return_value = mock_handler

        log_file = "/tmp/test_audit.log"
        setup_audit_logging(log_file)

        mock_file_handler.assert_called_once_with(log_file)
        mock_logger.addHandler.assert_called_once_with(mock_handler)
        mock_logger.setLevel.assert_called_once_with(logging.INFO)

    @patch("burly_mcp.audit.get_audit_logger")
    def test_log_tool_execution_success(self, mock_get_logger):
        """Test logging successful tool execution."""
        from burly_mcp.audit import log_tool_execution

        mock_logger = Mock()
        mock_get_logger.return_value = mock_logger

        tool_name = "test_tool"
        args = {"param": "value"}
        result = {"success": True, "output": "test output"}
        user_id = "test_user"

        log_tool_execution(tool_name, args, result, user_id)

        # Verify logger was called
        mock_logger.info.assert_called_once()

        # Check the logged message contains expected information
        call_args = mock_logger.info.call_args[0][0]
        log_data = json.loads(call_args)

        assert log_data["tool_name"] == tool_name
        assert log_data["args"] == args
        assert log_data["result"] == result
        assert log_data["user_id"] == user_id
        assert log_data["event_type"] == "tool_execution"
        assert "timestamp" in log_data

    @patch("burly_mcp.audit.get_audit_logger")
    def test_log_tool_execution_failure(self, mock_get_logger):
        """Test logging failed tool execution."""
        from burly_mcp.audit import log_tool_execution

        mock_logger = Mock()
        mock_get_logger.return_value = mock_logger

        tool_name = "test_tool"
        args = {"param": "value"}
        result = {"success": False, "error": "Tool failed"}
        user_id = "test_user"

        log_tool_execution(tool_name, args, result, user_id)

        mock_logger.info.assert_called_once()

        call_args = mock_logger.info.call_args[0][0]
        log_data = json.loads(call_args)

        assert log_data["result"]["success"] is False
        assert log_data["result"]["error"] == "Tool failed"

    @patch("burly_mcp.audit.get_audit_logger")
    def test_log_security_event(self, mock_get_logger):
        """Test logging security events."""
        from burly_mcp.audit import log_security_event

        mock_logger = Mock()
        mock_get_logger.return_value = mock_logger

        event_type = "unauthorized_access"
        details = {"ip": "192.168.1.1", "user": "test_user"}
        severity = "HIGH"

        log_security_event(event_type, details, severity)

        mock_logger.warning.assert_called_once()

        call_args = mock_logger.warning.call_args[0][0]
        log_data = json.loads(call_args)

        assert log_data["event_type"] == event_type
        assert log_data["details"] == details
        assert log_data["severity"] == severity
        assert log_data["category"] == "security"

    @patch("burly_mcp.audit.get_audit_logger")
    def test_log_policy_violation(self, mock_get_logger):
        """Test logging policy violations."""
        from burly_mcp.audit import log_policy_violation

        mock_logger = Mock()
        mock_get_logger.return_value = mock_logger

        tool_name = "restricted_tool"
        violation_type = "unauthorized_tool"
        details = {"user": "test_user", "reason": "Tool not allowed"}

        log_policy_violation(tool_name, violation_type, details)

        mock_logger.error.assert_called_once()

        call_args = mock_logger.error.call_args[0][0]
        log_data = json.loads(call_args)

        assert log_data["tool_name"] == tool_name
        assert log_data["violation_type"] == violation_type
        assert log_data["details"] == details
        assert log_data["event_type"] == "policy_violation"

    @patch("burly_mcp.audit.get_audit_logger")
    def test_log_system_event(self, mock_get_logger):
        """Test logging system events."""
        from burly_mcp.audit import log_system_event

        mock_logger = Mock()
        mock_get_logger.return_value = mock_logger

        event_type = "server_start"
        details = {"version": "1.0.0", "config": "production"}

        log_system_event(event_type, details)

        mock_logger.info.assert_called_once()

        call_args = mock_logger.info.call_args[0][0]
        log_data = json.loads(call_args)

        assert log_data["event_type"] == event_type
        assert log_data["details"] == details
        assert log_data["category"] == "system"

    @patch("burly_mcp.audit.datetime")
    @patch("burly_mcp.audit.get_audit_logger")
    def test_audit_log_timestamp_format(self, mock_get_logger, mock_datetime):
        """Test that audit logs include properly formatted timestamps."""
        from burly_mcp.audit import log_tool_execution

        mock_logger = Mock()
        mock_get_logger.return_value = mock_logger

        # Mock datetime
        mock_now = datetime(2024, 1, 1, 12, 0, 0)
        mock_datetime.utcnow.return_value = mock_now

        log_tool_execution("test_tool", {}, {"success": True}, "user")

        call_args = mock_logger.info.call_args[0][0]
        log_data = json.loads(call_args)

        assert "timestamp" in log_data
        # Verify timestamp format (ISO format)
        timestamp = log_data["timestamp"]
        assert isinstance(timestamp, str)
        assert "T" in timestamp  # ISO format includes T separator

    @patch("burly_mcp.audit.get_audit_logger")
    def test_audit_log_serialization_error_handling(self, mock_get_logger):
        """Test handling of non-serializable objects in audit logs."""
        from burly_mcp.audit import log_tool_execution

        mock_logger = Mock()
        mock_get_logger.return_value = mock_logger

        # Create non-serializable object
        class NonSerializable:
            pass

        non_serializable_args = {"obj": NonSerializable()}

        # Should handle serialization error gracefully
        log_tool_execution(
            "test_tool", non_serializable_args, {"success": True}, "user"
        )

        # Logger should still be called (with serializable fallback)
        mock_logger.info.assert_called_once()

    @patch("burly_mcp.audit.Path.mkdir")
    @patch("burly_mcp.audit.Path.exists")
    def test_audit_log_directory_creation(self, mock_exists, mock_mkdir):
        """Test automatic creation of audit log directory."""
        from burly_mcp.audit import setup_audit_logging

        mock_exists.return_value = False

        log_file = "/tmp/audit/test.log"
        setup_audit_logging(log_file)

        # Should create parent directory
        mock_mkdir.assert_called_once_with(parents=True, exist_ok=True)

    @patch("burly_mcp.audit.get_audit_logger")
    def test_audit_log_context_information(self, mock_get_logger):
        """Test that audit logs include contextual information."""
        from burly_mcp.audit import log_tool_execution

        mock_logger = Mock()
        mock_get_logger.return_value = mock_logger

        log_tool_execution(
            "test_tool",
            {"param": "value"},
            {"success": True},
            "user",
            session_id="session_123",
            request_id="req_456",
        )

        call_args = mock_logger.info.call_args[0][0]
        log_data = json.loads(call_args)

        assert log_data.get("session_id") == "session_123"
        assert log_data.get("request_id") == "req_456"

    @patch("burly_mcp.audit.get_audit_logger")
    def test_audit_log_performance_metrics(self, mock_get_logger):
        """Test logging of performance metrics."""
        from burly_mcp.audit import log_performance_metrics

        mock_logger = Mock()
        mock_get_logger.return_value = mock_logger

        metrics = {
            "execution_time_ms": 150,
            "memory_usage_mb": 25.5,
            "cpu_usage_percent": 12.3,
        }

        log_performance_metrics("test_tool", metrics)

        mock_logger.info.assert_called_once()

        call_args = mock_logger.info.call_args[0][0]
        log_data = json.loads(call_args)

        assert log_data["event_type"] == "performance_metrics"
        assert log_data["tool_name"] == "test_tool"
        assert log_data["metrics"] == metrics
