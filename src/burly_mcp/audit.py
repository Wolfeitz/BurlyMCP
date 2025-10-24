"""
Audit Logging System for MCP Operations

This module provides comprehensive audit logging for all MCP tool operations.
It creates structured JSON Lines logs that can be monitored, analyzed, and
used for security auditing and compliance purposes.

Key Features:
- JSON Lines format for easy parsing and analysis
- Environment variable redaction for security
- Structured audit records with all required fields
- Automatic log rotation and management
- Integration with tool execution pipeline

Audit Record Format:
- timestamp: ISO-8601 UTC timestamp
- tool: Name of the executed tool
- args_hash: SHA-256 hash of sanitized arguments
- mutates: Whether the operation modifies system state
- requires_confirm: Whether confirmation was required
- status: Execution status (ok|fail|need_confirm)
- exit_code: Process exit code
- elapsed_ms: Execution time in milliseconds
- caller: Identifier for the calling context
- stdout_trunc: Number of bytes truncated from stdout
- stderr_trunc: Number of bytes truncated from stderr
"""

import hashlib
import json
import logging
import os
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class AuditRecord:
    """
    Structured audit record for tool execution.

    This dataclass defines the complete audit record format with all
    required fields for security monitoring and compliance.
    """

    ts: str  # ISO-8601 UTC timestamp
    tool: str  # Tool name
    args_hash: str  # SHA-256 hash of sanitized arguments
    mutates: bool  # Whether operation modifies system state
    requires_confirm: bool  # Whether confirmation was required
    status: str  # ok|fail|need_confirm
    exit_code: int  # Process exit code
    elapsed_ms: int  # Execution time in milliseconds
    caller: str  # Calling context identifier
    stdout_trunc: int  # Bytes truncated from stdout
    stderr_trunc: int  # Bytes truncated from stderr


class AuditLogger:
    """
    Audit logger for MCP tool operations.

    This class manages audit logging with JSON Lines format, environment
    variable redaction, and automatic log rotation. It provides a secure
    and comprehensive audit trail for all system operations.
    """

    def __init__(self, log_file_path: str | None = None):
        """
        Initialize the audit logger.

        Args:
            log_file_path: Path to the audit log file (optional)
        """
        # Default log file path
        if log_file_path is None:
            log_dir = os.environ.get("AUDIT_LOG_DIR", "/var/log/agentops")
            log_file_path = os.path.join(log_dir, "audit.jsonl")

        self.log_file_path = log_file_path
        self.sensitive_env_vars = self._get_sensitive_env_vars()

        # Ensure log directory exists
        log_dir = os.path.dirname(self.log_file_path)
        os.makedirs(log_dir, exist_ok=True)

        logger.info(f"Audit logger initialized: {self.log_file_path}")

    def log_tool_execution(
        self,
        tool_name: str,
        args: dict[str, Any],
        mutates: bool,
        requires_confirm: bool,
        status: str,
        exit_code: int,
        elapsed_ms: int,
        stdout_truncated: int = 0,
        stderr_truncated: int = 0,
        caller: str = "mcp_client",
    ) -> None:
        """
        Log a tool execution event.

        Args:
            tool_name: Name of the executed tool
            args: Tool arguments (will be sanitized)
            mutates: Whether the operation modifies system state
            requires_confirm: Whether confirmation was required
            status: Execution status (ok|fail|need_confirm)
            exit_code: Process exit code
            elapsed_ms: Execution time in milliseconds
            stdout_truncated: Number of bytes truncated from stdout
            stderr_truncated: Number of bytes truncated from stderr
            caller: Identifier for the calling context
        """
        try:
            # Create audit record
            record = AuditRecord(
                ts=datetime.now(UTC).isoformat(),
                tool=tool_name,
                args_hash=self._hash_sanitized_args(args),
                mutates=mutates,
                requires_confirm=requires_confirm,
                status=status,
                exit_code=exit_code,
                elapsed_ms=elapsed_ms,
                caller=caller,
                stdout_trunc=stdout_truncated,
                stderr_trunc=stderr_truncated,
            )

            # Write to log file
            self._write_audit_record(record)

            logger.debug(f"Audit record logged: {tool_name} -> {status}")

        except Exception as e:
            logger.error(f"Failed to log audit record for {tool_name}: {str(e)}")
            # Don't raise exception - audit logging failures shouldn't break tool execution

    def log_security_violation(self, violation_data: dict[str, Any]) -> None:
        """
        Log a security violation event.

        Args:
            violation_data: Details about the security violation
        """
        try:
            # Create special audit record for security violations
            record = AuditRecord(
                ts=datetime.now(UTC).isoformat(),
                tool="SECURITY_VIOLATION",
                args_hash=self._hash_sanitized_args(violation_data),
                mutates=False,
                requires_confirm=False,
                status="security_violation",
                exit_code=1,
                elapsed_ms=0,
                caller="security_monitor",
                stdout_trunc=0,
                stderr_trunc=0,
            )

            # Write to log file
            self._write_audit_record(record)

            logger.warning(
                f"Security violation logged: {violation_data.get('violation_type', 'unknown')}"
            )

        except Exception as e:
            logger.error(f"Failed to log security violation: {str(e)}")

    def _write_audit_record(self, record: AuditRecord) -> None:
        """
        Write an audit record to the log file in JSON Lines format.

        Args:
            record: The audit record to write
        """
        try:
            # Convert to dictionary and then to JSON
            record_dict = asdict(record)
            json_line = json.dumps(record_dict, separators=(",", ":"))

            # Append to log file
            with open(self.log_file_path, "a", encoding="utf-8") as f:
                f.write(json_line + "\n")
                f.flush()  # Ensure immediate write

        except OSError as e:
            logger.error(
                f"Failed to write audit record to {self.log_file_path}: {str(e)}"
            )
            raise

    def _hash_sanitized_args(self, args: dict[str, Any]) -> str:
        """
        Create a SHA-256 hash of sanitized arguments.

        This function removes sensitive information from arguments before
        hashing to prevent exposure of secrets in audit logs.

        Args:
            args: Original arguments dictionary

        Returns:
            str: SHA-256 hash of sanitized arguments
        """
        try:
            # Create a copy and sanitize sensitive fields
            sanitized_args = self._sanitize_args(args.copy())

            # Convert to JSON string for consistent hashing
            args_json = json.dumps(
                sanitized_args, sort_keys=True, separators=(",", ":")
            )

            # Create SHA-256 hash
            hash_obj = hashlib.sha256(args_json.encode("utf-8"))
            return hash_obj.hexdigest()

        except Exception as e:
            logger.warning(f"Failed to hash arguments: {str(e)}")
            return "hash_error"

    def _sanitize_args(self, args: Any) -> Any:
        """
        Sanitize arguments by removing or redacting sensitive information.

        Args:
            args: Original arguments (usually dictionary)

        Returns:
            Sanitized arguments
        """
        if not isinstance(args, dict):
            return args

        sanitized: dict[str, Any] = {}

        for key, value in args.items():
            key_lower = key.lower()

            # Redact sensitive field names
            if any(
                sensitive in key_lower
                for sensitive in ["password", "token", "secret", "key", "auth"]
            ):
                sanitized[key] = "[REDACTED]"
            elif isinstance(value, dict):
                sanitized[key] = self._sanitize_args(value)
            elif isinstance(value, list):
                sanitized[key] = [
                    self._sanitize_args(item) if isinstance(item, dict) else item
                    for item in value
                ]
            else:
                # Check if value contains environment variable references
                if isinstance(value, str) and self._contains_sensitive_env_var(value):
                    sanitized[key] = "[REDACTED_ENV_VAR]"
                else:
                    sanitized[key] = value

        return sanitized

    def _contains_sensitive_env_var(self, value: str) -> bool:
        """
        Check if a string value contains references to sensitive environment variables.

        Args:
            value: String value to check

        Returns:
            bool: True if value contains sensitive environment variable references
        """
        if not isinstance(value, str):
            return False  # type: ignore[unreachable]

        # Check for environment variable patterns
        for env_var in self.sensitive_env_vars:
            if env_var in value or f"${env_var}" in value or f"${{{env_var}}}" in value:
                return True

        return False

    def _get_sensitive_env_vars(self) -> list[str]:
        """
        Get list of sensitive environment variable names.

        Returns:
            list: List of sensitive environment variable names
        """
        # Default sensitive environment variables
        default_sensitive = [
            "PASSWORD",
            "TOKEN",
            "SECRET",
            "KEY",
            "AUTH",
            "GOTIFY_TOKEN",
            "GOTIFY_URL",
            "API_KEY",
            "API_SECRET",
            "DATABASE_URL",
            "DB_PASSWORD",
            "REDIS_URL",
        ]

        # Add custom sensitive variables from environment
        custom_sensitive = os.environ.get("AUDIT_SENSITIVE_ENV_VARS", "").split(",")
        custom_sensitive = [var.strip() for var in custom_sensitive if var.strip()]

        return default_sensitive + custom_sensitive

    def get_audit_stats(self, hours: int = 24) -> dict[str, Any]:
        """
        Get audit statistics for the specified time period.

        Args:
            hours: Number of hours to look back

        Returns:
            dict: Audit statistics
        """
        try:
            if not os.path.exists(self.log_file_path):
                return {"error": "audit_log_not_found"}

            stats: dict[str, Any] = {
                "total_operations": 0,
                "successful_operations": 0,
                "failed_operations": 0,
                "security_violations": 0,
                "tools_used": set(),
                "time_period_hours": hours,
            }

            # Calculate cutoff time
            cutoff_time = datetime.now(UTC).timestamp() - (hours * 3600)

            # Read and analyze log file
            with open(self.log_file_path, encoding="utf-8") as f:
                for line in f:
                    try:
                        record = json.loads(line.strip())

                        # Parse timestamp
                        record_time = datetime.fromisoformat(
                            record["ts"].replace("Z", "+00:00")
                        ).timestamp()

                        if record_time >= cutoff_time:
                            stats["total_operations"] += 1

                            if record["status"] == "ok":
                                stats["successful_operations"] += 1
                            elif record["status"] in ["fail", "need_confirm"]:
                                stats["failed_operations"] += 1
                            elif record["status"] == "security_violation":
                                stats["security_violations"] += 1

                            if record["tool"] != "SECURITY_VIOLATION":
                                stats["tools_used"].add(record["tool"])

                    except (json.JSONDecodeError, KeyError, ValueError):
                        continue  # Skip malformed records

            # Convert set to list for JSON serialization
            stats["tools_used"] = list(stats["tools_used"])

            return stats

        except Exception as e:
            logger.error(f"Failed to get audit stats: {str(e)}")
            return {"error": str(e)}


# Global audit logger instance
_audit_logger: AuditLogger | None = None


def get_audit_logger(log_file_path: str | None = None) -> AuditLogger:
    """
    Get the global audit logger instance.

    Args:
        log_file_path: Optional path to the audit log file. If provided and no
                      global logger exists, creates a new logger with this path.

    Returns:
        AuditLogger: The global audit logger instance
    """
    global _audit_logger

    if _audit_logger is None:
        _audit_logger = AuditLogger(log_file_path=log_file_path)

    return _audit_logger


def log_tool_execution(
    tool_name: str,
    args: dict[str, Any],
    mutates: bool,
    requires_confirm: bool,
    status: str,
    exit_code: int,
    elapsed_ms: int,
    stdout_truncated: int = 0,
    stderr_truncated: int = 0,
    caller: str = "mcp_client",
) -> None:
    """
    Convenience function to log tool execution using the global audit logger.

    Args:
        tool_name: Name of the executed tool
        args: Tool arguments (will be sanitized)
        mutates: Whether the operation modifies system state
        requires_confirm: Whether confirmation was required
        status: Execution status (ok|fail|need_confirm)
        exit_code: Process exit code
        elapsed_ms: Execution time in milliseconds
        stdout_truncated: Number of bytes truncated from stdout
        stderr_truncated: Number of bytes truncated from stderr
        caller: Identifier for the calling context
    """
    audit_logger = get_audit_logger()
    audit_logger.log_tool_execution(
        tool_name=tool_name,
        args=args,
        mutates=mutates,
        requires_confirm=requires_confirm,
        status=status,
        exit_code=exit_code,
        elapsed_ms=elapsed_ms,
        stdout_truncated=stdout_truncated,
        stderr_truncated=stderr_truncated,
        caller=caller,
    )


def log_security_violation(violation_data: dict[str, Any]) -> None:
    """
    Convenience function to log security violations using the global audit logger.

    Args:
        violation_data: Details about the security violation
    """
    audit_logger = get_audit_logger()
    audit_logger.log_security_violation(violation_data)
