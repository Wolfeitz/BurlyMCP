"""
Audit Logging System for Burly MCP Server

This module implements comprehensive audit logging for all tool executions.
Every operation is logged with detailed metadata for security monitoring,
compliance, and debugging purposes.

The audit system writes JSON Lines format logs that can be easily processed
by log analysis tools. Each audit record includes:
- Timestamp and tool identification
- Sanitized argument hash for privacy
- Execution status and metrics
- Security-relevant metadata

Audit logs are essential for:
- Security monitoring and incident response
- Compliance with operational requirements
- Performance analysis and optimization
- Debugging tool execution issues

Log Format:
Each line is a JSON object with standardized fields following the
JSON Lines specification for easy parsing and analysis.
"""

import json
import time
import hashlib
import logging
from datetime import datetime, timezone
from typing import Dict, Any, Optional
from dataclasses import dataclass, asdict
from pathlib import Path


@dataclass
class AuditRecord:
    """
    Structured audit record for tool execution.
    
    This dataclass defines the standard fields logged for every
    tool execution, providing comprehensive audit trail information.
    """
    ts: str  # ISO-8601 UTC timestamp
    tool: str  # Tool name that was executed
    args_hash: str  # SHA-256 hash of sanitized arguments
    mutates: bool  # Whether the tool modifies system state
    requires_confirm: bool  # Whether confirmation was required
    status: str  # Execution status: ok|fail|need_confirm
    exit_code: int  # Process exit code
    elapsed_ms: int  # Execution time in milliseconds
    caller: str  # Identifier for the calling system
    stdout_trunc: int  # Number of stdout bytes truncated
    stderr_trunc: int  # Number of stderr bytes truncated


class AuditLogger:
    """
    Audit logging system for MCP tool executions.
    
    The audit logger provides secure, structured logging of all tool
    executions with proper sanitization of sensitive information.
    """
    
    def __init__(self, log_path: str = "/var/log/agentops/audit.jsonl"):
        """
        Initialize the audit logger with the specified log file path.
        
        Args:
            log_path: Path to the audit log file (JSON Lines format)
        """
        self.log_path = Path(log_path)
        self.logger = logging.getLogger(__name__)
        
        # Ensure log directory exists
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        
        # TODO: Set up log rotation and retention policies
    
    def log_execution(
        self,
        tool_name: str,
        args: Dict[str, Any],
        mutates: bool,
        requires_confirm: bool,
        status: str,
        exit_code: int,
        elapsed_ms: int,
        caller: str = "mcp_client",
        stdout_trunc: int = 0,
        stderr_trunc: int = 0
    ) -> None:
        """
        Log a tool execution with full audit details.
        
        Args:
            tool_name: Name of the executed tool
            args: Tool arguments (will be sanitized and hashed)
            mutates: Whether the tool modifies system state
            requires_confirm: Whether confirmation was required
            status: Execution status (ok|fail|need_confirm)
            exit_code: Process exit code
            elapsed_ms: Execution time in milliseconds
            caller: Identifier for the calling system
            stdout_trunc: Number of stdout bytes truncated
            stderr_trunc: Number of stderr bytes truncated
        """
        # Create sanitized hash of arguments
        args_hash = self._create_args_hash(args)
        
        # Create audit record
        record = AuditRecord(
            ts=datetime.now(timezone.utc).isoformat(),
            tool=tool_name,
            args_hash=args_hash,
            mutates=mutates,
            requires_confirm=requires_confirm,
            status=status,
            exit_code=exit_code,
            elapsed_ms=elapsed_ms,
            caller=caller,
            stdout_trunc=stdout_trunc,
            stderr_trunc=stderr_trunc
        )
        
        # Write to audit log
        self._write_audit_record(record)
    
    def _create_args_hash(self, args: Dict[str, Any]) -> str:
        """
        Create a SHA-256 hash of sanitized arguments.
        
        This method removes sensitive information from arguments
        before hashing to protect privacy while maintaining
        audit trail integrity.
        
        Args:
            args: Original tool arguments
            
        Returns:
            SHA-256 hash of sanitized arguments
        """
        # TODO: Implement argument sanitization
        # Remove sensitive fields like passwords, tokens, etc.
        sanitized_args = self._sanitize_args(args)
        
        # Create deterministic JSON representation
        args_json = json.dumps(sanitized_args, sort_keys=True)
        
        # Return SHA-256 hash
        return hashlib.sha256(args_json.encode()).hexdigest()
    
    def _sanitize_args(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """
        Remove sensitive information from arguments.
        
        This method identifies and redacts sensitive fields
        to prevent logging of secrets or personal information.
        
        Args:
            args: Original arguments
            
        Returns:
            Sanitized arguments with sensitive fields redacted
        """
        # TODO: Implement comprehensive sanitization
        # Common sensitive field names to redact
        sensitive_fields = {
            'password', 'token', 'secret', 'key', 'auth',
            'credential', 'private', 'confidential'
        }
        
        sanitized = {}
        for key, value in args.items():
            if any(sensitive in key.lower() for sensitive in sensitive_fields):
                sanitized[key] = "[REDACTED]"
            else:
                sanitized[key] = value
        
        return sanitized
    
    def _write_audit_record(self, record: AuditRecord) -> None:
        """
        Write an audit record to the log file.
        
        Args:
            record: AuditRecord to write
        """
        try:
            with open(self.log_path, 'a', encoding='utf-8') as f:
                json.dump(asdict(record), f, ensure_ascii=False)
                f.write('\n')
        except Exception as e:
            self.logger.error(f"Failed to write audit record: {e}")
            # TODO: Implement fallback logging mechanism