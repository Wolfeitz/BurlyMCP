"""
Security Module for Path Traversal Protection and Validation

This module provides security functions to prevent path traversal attacks
and enforce directory boundaries for file operations. All file operations
in the MCP server should use these validation functions to ensure security.

Key Functions:
- validate_path_within_root: Prevent path traversal attacks
- sanitize_file_path: Clean and normalize file paths
- log_security_violation: Record security violations for audit

Security Principles:
- All file paths must be validated before use
- Operations are restricted to designated root directories
- Path traversal attempts are logged and rejected
- Symbolic links are resolved and validated
"""

import logging
import os
from pathlib import Path
from typing import Optional, Tuple, Dict, Any

logger = logging.getLogger(__name__)


class SecurityViolationError(Exception):
    """
    Exception raised when a security violation is detected.

    This exception is raised for path traversal attempts, unauthorized
    file access, or other security policy violations.
    """

    pass


def validate_path_within_root(
    file_path: str, root_directory: str, operation_name: str = "file_operation"
) -> str:
    """
    Validate that a file path is within the specified root directory.

    This function prevents path traversal attacks by ensuring that the
    resolved absolute path of the file is within the root directory.
    It handles symbolic links, relative paths, and other edge cases.

    Args:
        file_path: The file path to validate (can be relative or absolute)
        root_directory: The root directory that constrains file access
        operation_name: Name of the operation for logging purposes

    Returns:
        str: The validated absolute file path

    Raises:
        SecurityViolationError: If path traversal is detected
        ValueError: If inputs are invalid
    """
    if not file_path:
        raise ValueError("file_path cannot be empty")

    if not root_directory:
        raise ValueError("root_directory cannot be empty")

    try:
        # Resolve the root directory to an absolute path
        abs_root = os.path.abspath(root_directory)

        # If file_path is already absolute, use it directly
        # Otherwise, join it with the root directory
        if os.path.isabs(file_path):
            candidate_path = file_path
        else:
            candidate_path = os.path.join(abs_root, file_path)

        # Resolve to absolute path, following any symbolic links
        abs_file_path = os.path.abspath(candidate_path)

        # Check if the resolved path is within the root directory
        if (
            not abs_file_path.startswith(abs_root + os.sep)
            and abs_file_path != abs_root
        ):
            log_security_violation(
                violation_type="path_traversal",
                operation=operation_name,
                attempted_path=file_path,
                root_directory=root_directory,
                resolved_path=abs_file_path,
            )
            raise SecurityViolationError(
                f"Path traversal detected: '{file_path}' resolves outside "
                f"root directory '{root_directory}'"
            )

        logger.debug(
            f"Path validation passed for {operation_name}: "
            f"{file_path} -> {abs_file_path}"
        )
        return abs_file_path

    except (OSError, ValueError) as e:
        log_security_violation(
            violation_type="path_validation_error",
            operation=operation_name,
            attempted_path=file_path,
            root_directory=root_directory,
            error=str(e),
        )
        raise SecurityViolationError(f"Path validation failed: {str(e)}")


def sanitize_file_path(file_path: str) -> str:
    """
    Sanitize a file path by removing dangerous characters and sequences.

    This function cleans file paths to prevent injection attacks and
    normalize path separators. It removes null bytes, control characters,
    and other potentially dangerous sequences.

    Args:
        file_path: The file path to sanitize

    Returns:
        str: The sanitized file path

    Raises:
        ValueError: If the path contains dangerous characters
    """
    if not file_path:
        return ""

    # Remove null bytes and control characters
    sanitized = file_path.replace("\x00", "").replace("\r", "").replace("\n", "")

    # Check for dangerous sequences
    dangerous_sequences = ["../", "..\\", "~/", "~\\"]
    for seq in dangerous_sequences:
        if seq in sanitized:
            logger.warning(f"Dangerous sequence '{seq}' found in path: {file_path}")

    # Normalize path separators
    sanitized = os.path.normpath(sanitized)

    # Additional validation
    if len(sanitized) > 4096:  # Reasonable path length limit
        raise ValueError("File path too long (>4096 characters)")

    return sanitized


def validate_blog_stage_path(file_path: str) -> str:
    """
    Validate a file path for blog staging operations.

    This is a convenience function that validates paths against the
    BLOG_STAGE_ROOT environment variable.

    Args:
        file_path: The file path to validate

    Returns:
        str: The validated absolute file path

    Raises:
        SecurityViolationError: If path traversal is detected
        ValueError: If BLOG_STAGE_ROOT is not configured
    """
    blog_stage_root = os.environ.get("BLOG_STAGE_ROOT")
    if not blog_stage_root:
        raise ValueError("BLOG_STAGE_ROOT environment variable not configured")

    return validate_path_within_root(
        file_path=file_path, root_directory=blog_stage_root, operation_name="blog_stage"
    )


def validate_blog_publish_path(file_path: str) -> str:
    """
    Validate a file path for blog publishing operations.

    This is a convenience function that validates paths against the
    BLOG_PUBLISH_ROOT environment variable.

    Args:
        file_path: The file path to validate

    Returns:
        str: The validated absolute file path

    Raises:
        SecurityViolationError: If path traversal is detected
        ValueError: If BLOG_PUBLISH_ROOT is not configured
    """
    blog_publish_root = os.environ.get("BLOG_PUBLISH_ROOT")
    if not blog_publish_root:
        raise ValueError("BLOG_PUBLISH_ROOT environment variable not configured")

    return validate_path_within_root(
        file_path=file_path,
        root_directory=blog_publish_root,
        operation_name="blog_publish",
    )


def log_security_violation(
    violation_type: str,
    operation: str,
    attempted_path: str,
    root_directory: str,
    resolved_path: Optional[str] = None,
    error: Optional[str] = None,
) -> None:
    """
    Log a security violation for audit purposes.

    This function creates a structured log entry for security violations
    that can be monitored and analyzed. It includes all relevant context
    for investigating potential attacks.

    Args:
        violation_type: Type of violation (e.g., "path_traversal")
        operation: Name of the operation that triggered the violation
        attempted_path: The path that was attempted
        root_directory: The root directory constraint
        resolved_path: The resolved absolute path (if available)
        error: Any error message associated with the violation
    """
    violation_data = {
        "violation_type": violation_type,
        "operation": operation,
        "attempted_path": attempted_path,
        "root_directory": root_directory,
        "resolved_path": resolved_path,
        "error": error,
    }

    logger.warning(
        f"SECURITY VIOLATION: {violation_type} in {operation}", extra=violation_data
    )

    # Import here to avoid circular imports
    try:
        from .audit import log_security_violation as audit_log_security_violation

        audit_log_security_violation(violation_data)
    except ImportError:
        # Audit logging not available
        pass

    # Send security violation notification
    try:
        from .notifications.manager import notify_security_violation

        notify_security_violation(
            violation_type=violation_type,
            details=f"{operation}: {attempted_path} -> {resolved_path or 'N/A'}",
        )
    except ImportError:
        # Notifications not available
        pass


def check_file_permissions(file_path: str, required_permissions: str = "r") -> bool:
    """
    Check if the current process has the required permissions for a file.

    Args:
        file_path: Path to the file to check
        required_permissions: Required permissions ("r", "w", "rw")

    Returns:
        bool: True if permissions are sufficient, False otherwise
    """
    if not os.path.exists(file_path):
        return False

    try:
        if "r" in required_permissions and not os.access(file_path, os.R_OK):
            return False

        if "w" in required_permissions and not os.access(file_path, os.W_OK):
            return False

        return True

    except OSError:
        return False


def get_safe_file_info(file_path: str) -> Dict[str, Any]:
    """
    Get safe file information without exposing sensitive system details.

    Args:
        file_path: Path to the file

    Returns:
        dict: Safe file information (size, type, permissions)
    """
    try:
        stat_info = os.stat(file_path)
        return {
            "exists": True,
            "is_file": os.path.isfile(file_path),
            "is_directory": os.path.isdir(file_path),
            "size": stat_info.st_size,
            "readable": os.access(file_path, os.R_OK),
            "writable": os.access(file_path, os.W_OK),
        }
    except OSError:
        return {
            "exists": False,
            "is_file": False,
            "is_directory": False,
            "size": 0,
            "readable": False,
            "writable": False,
        }
