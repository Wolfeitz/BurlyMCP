"""
Unit tests for the Burly MCP audit module.
"""

import json
import os
import tempfile
from datetime import UTC, datetime
from unittest.mock import Mock, patch


class TestAuditLogger:
    """Test the audit logging functionality."""

    def test_audit_logger_initialization(self):
        """Test audit logger initialization."""
        from burly_mcp.audit import AuditLogger

        with tempfile.TemporaryDirectory() as temp_dir:
            log_file = os.path.join(temp_dir, "test_audit.jsonl")
            logger = AuditLogger(log_file_path=log_file)

            assert logger.log_file_path == log_file
            assert hasattr(logger, "sensitive_env_vars")
            assert isinstance(logger.sensitive_env_vars, list)

    def test_audit_logger_default_path(self):
        """Test audit logger with default log file path."""
        from burly_mcp.audit import AuditLogger

        with patch.dict(os.environ, {"AUDIT_LOG_DIR": "/tmp/test_audit"}):
            logger = AuditLogger()
            assert logger.log_file_path == "/tmp/test_audit/audit.jsonl"

    def test_log_tool_execution_success(self):
        """Test logging successful tool execution."""
        from burly_mcp.audit import AuditLogger

        with tempfile.TemporaryDirectory() as temp_dir:
            log_file = os.path.join(temp_dir, "test_audit.jsonl")
            logger = AuditLogger(log_file_path=log_file)

            logger.log_tool_execution(
                tool_name="test_tool",
                args={"param1": "value1", "param2": "value2"},
                mutates=False,
                requires_confirm=False,
                status="ok",
                exit_code=0,
                elapsed_ms=150,
                stdout_truncated=0,
                stderr_truncated=0,
                caller="test_client"
            )

            # Verify log file was created and contains expected data
            assert os.path.exists(log_file)
            with open(log_file) as f:
                log_line = f.readline().strip()
                log_data = json.loads(log_line)

            assert log_data["tool"] == "test_tool"
            assert log_data["status"] == "ok"
            assert log_data["exit_code"] == 0
            assert log_data["elapsed_ms"] == 150
            assert log_data["mutates"] is False
            assert log_data["requires_confirm"] is False
            assert log_data["caller"] == "test_client"

    def test_log_tool_execution_failure(self):
        """Test logging failed tool execution."""
        from burly_mcp.audit import AuditLogger

        with tempfile.TemporaryDirectory() as temp_dir:
            log_file = os.path.join(temp_dir, "test_audit.jsonl")
            logger = AuditLogger(log_file_path=log_file)

            logger.log_tool_execution(
                tool_name="failing_tool",
                args={"param": "value"},
                mutates=True,
                requires_confirm=True,
                status="fail",
                exit_code=1,
                elapsed_ms=500,
                stdout_truncated=100,
                stderr_truncated=50
            )

            with open(log_file) as f:
                log_data = json.loads(f.readline().strip())

            assert log_data["tool"] == "failing_tool"
            assert log_data["status"] == "fail"
            assert log_data["exit_code"] == 1
            assert log_data["mutates"] is True
            assert log_data["requires_confirm"] is True
            assert log_data["stdout_trunc"] == 100
            assert log_data["stderr_trunc"] == 50

    def test_log_security_violation(self):
        """Test logging security violations."""
        from burly_mcp.audit import AuditLogger

        with tempfile.TemporaryDirectory() as temp_dir:
            log_file = os.path.join(temp_dir, "test_audit.jsonl")
            logger = AuditLogger(log_file_path=log_file)

            violation_data = {
                "violation_type": "path_traversal",
                "attempted_path": "/tmp/../etc/passwd",
                "operation": "file_read"
            }

            logger.log_security_violation(violation_data)

            with open(log_file) as f:
                log_data = json.loads(f.readline().strip())

            assert log_data["tool"] == "SECURITY_VIOLATION"
            assert log_data["status"] == "security_violation"
            assert log_data["caller"] == "security_monitor"

    def test_hash_sanitized_args(self):
        """Test argument hashing with sanitization."""
        from burly_mcp.audit import AuditLogger

        logger = AuditLogger()

        # Test with sensitive data
        args_with_secrets = {
            "username": "testuser",
            "password": "secret123",
            "token": "abc123",
            "normal_param": "value"
        }

        hash1 = logger._hash_sanitized_args(args_with_secrets)
        hash2 = logger._hash_sanitized_args(args_with_secrets)

        # Same args should produce same hash
        assert hash1 == hash2
        assert len(hash1) == 64  # SHA-256 hex length

    def test_sanitize_args(self):
        """Test argument sanitization."""
        from burly_mcp.audit import AuditLogger

        logger = AuditLogger()

        args = {
            "username": "testuser",
            "password": "secret123",
            "api_key": "key123",
            "normal_param": "value",
            "nested": {
                "secret": "hidden",
                "public": "visible"
            }
        }

        sanitized = logger._sanitize_args(args)

        assert sanitized["username"] == "testuser"
        assert sanitized["password"] == "[REDACTED]"
        assert sanitized["api_key"] == "[REDACTED]"
        assert sanitized["normal_param"] == "value"
        assert sanitized["nested"]["secret"] == "[REDACTED]"
        assert sanitized["nested"]["public"] == "visible"

    def test_contains_sensitive_env_var(self):
        """Test detection of sensitive environment variables."""
        from burly_mcp.audit import AuditLogger

        logger = AuditLogger()

        # Test with sensitive env var references
        assert logger._contains_sensitive_env_var("$PASSWORD") is True
        assert logger._contains_sensitive_env_var("${TOKEN}") is True
        assert logger._contains_sensitive_env_var("API_KEY") is True

        # Test with non-sensitive values
        assert logger._contains_sensitive_env_var("normal_value") is False
        assert logger._contains_sensitive_env_var("PATH") is False

    def test_get_sensitive_env_vars(self):
        """Test getting list of sensitive environment variables."""
        from burly_mcp.audit import AuditLogger

        logger = AuditLogger()
        sensitive_vars = logger._get_sensitive_env_vars()

        assert isinstance(sensitive_vars, list)
        assert "PASSWORD" in sensitive_vars
        assert "TOKEN" in sensitive_vars
        assert "SECRET" in sensitive_vars

    @patch.dict(os.environ, {"AUDIT_SENSITIVE_ENV_VARS": "CUSTOM_SECRET,CUSTOM_KEY"})
    def test_custom_sensitive_env_vars(self):
        """Test custom sensitive environment variables."""
        from burly_mcp.audit import AuditLogger

        logger = AuditLogger()
        sensitive_vars = logger._get_sensitive_env_vars()

        assert "CUSTOM_SECRET" in sensitive_vars
        assert "CUSTOM_KEY" in sensitive_vars

    def test_get_audit_stats(self):
        """Test getting audit statistics."""
        from burly_mcp.audit import AuditLogger

        with tempfile.TemporaryDirectory() as temp_dir:
            log_file = os.path.join(temp_dir, "test_audit.jsonl")
            logger = AuditLogger(log_file_path=log_file)

            # Log some test entries
            logger.log_tool_execution(
                tool_name="tool1", args={}, mutates=False, requires_confirm=False,
                status="ok", exit_code=0, elapsed_ms=100
            )
            logger.log_tool_execution(
                tool_name="tool2", args={}, mutates=True, requires_confirm=True,
                status="fail", exit_code=1, elapsed_ms=200
            )

            stats = logger.get_audit_stats(hours=24)

            assert stats["total_operations"] == 2
            assert stats["successful_operations"] == 1
            assert stats["failed_operations"] == 1
            assert "tool1" in stats["tools_used"]
            assert "tool2" in stats["tools_used"]

    def test_get_audit_stats_no_file(self):
        """Test getting audit statistics when log file doesn't exist."""
        from burly_mcp.audit import AuditLogger

        with tempfile.TemporaryDirectory() as temp_dir:
            log_file = os.path.join(temp_dir, "nonexistent.jsonl")
            logger = AuditLogger(log_file_path=log_file)

            # Delete the file to simulate it not existing
            if os.path.exists(log_file):
                os.remove(log_file)

            stats = logger.get_audit_stats()

            assert "error" in stats
            assert stats["error"] == "audit_log_not_found"

    def test_audit_record_creation(self):
        """Test audit record dataclass creation."""

        from burly_mcp.audit import AuditRecord

        record = AuditRecord(
            ts=datetime.now(UTC).isoformat(),
            tool="test_tool",
            args_hash="abc123",
            mutates=False,
            requires_confirm=False,
            status="ok",
            exit_code=0,
            elapsed_ms=100,
            caller="test_client",
            stdout_trunc=0,
            stderr_trunc=0
        )

        assert record.tool == "test_tool"
        assert record.status == "ok"
        assert record.exit_code == 0


class TestGlobalAuditFunctions:
    """Test global audit functions."""

    def test_get_audit_logger(self):
        """Test getting global audit logger instance."""
        from burly_mcp.audit import get_audit_logger

        logger1 = get_audit_logger()
        logger2 = get_audit_logger()

        # Should return same instance
        assert logger1 is logger2

    def test_log_tool_execution_global(self):
        """Test global log_tool_execution function."""
        from burly_mcp.audit import log_tool_execution

        with tempfile.TemporaryDirectory() as temp_dir:
            log_file = os.path.join(temp_dir, "global_test.jsonl")

            with patch("burly_mcp.audit.get_audit_logger") as mock_get_logger:
                mock_logger = Mock()
                mock_get_logger.return_value = mock_logger

                log_tool_execution(
                    tool_name="global_tool",
                    args={"param": "value"},
                    mutates=False,
                    requires_confirm=False,
                    status="ok",
                    exit_code=0,
                    elapsed_ms=150
                )

                mock_logger.log_tool_execution.assert_called_once_with(
                    tool_name="global_tool",
                    args={"param": "value"},
                    mutates=False,
                    requires_confirm=False,
                    status="ok",
                    exit_code=0,
                    elapsed_ms=150,
                    stdout_truncated=0,
                    stderr_truncated=0,
                    caller="mcp_client"
                )

    def test_log_security_violation_global(self):
        """Test global log_security_violation function."""
        from burly_mcp.audit import log_security_violation

        with patch("burly_mcp.audit.get_audit_logger") as mock_get_logger:
            mock_logger = Mock()
            mock_get_logger.return_value = mock_logger

            violation_data = {"violation_type": "test", "details": "test violation"}
            log_security_violation(violation_data)

            mock_logger.log_security_violation.assert_called_once_with(violation_data)

    def test_audit_logging_error_handling(self):
        """Test audit logging error handling."""
        from burly_mcp.audit import AuditLogger

        with tempfile.TemporaryDirectory() as temp_dir:
            log_file = os.path.join(temp_dir, "test.jsonl")
            logger = AuditLogger(log_file_path=log_file)

            # Mock file write to raise an error
            with patch("builtins.open", side_effect=OSError("Write failed")):
                # Should not raise exception, just log error
                logger.log_tool_execution(
                    tool_name="test_tool",
                    args={},
                    mutates=False,
                    requires_confirm=False,
                    status="ok",
                    exit_code=0,
                    elapsed_ms=100
                )
