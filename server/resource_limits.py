"""
Resource Limits and Monitoring Module

This module provides timeout enforcement and output limiting for tool execution.
It ensures that tools cannot consume excessive resources or run indefinitely,
protecting the system from resource exhaustion attacks.

Key Functions:
- execute_with_timeout: Run commands with timeout enforcement
- truncate_output: Limit output size with truncation indicators
- monitor_resource_usage: Track resource consumption during execution

Resource Limits:
- Per-tool timeout enforcement (configurable)
- stdout/stderr truncation with clear indicators
- Memory usage monitoring (future enhancement)
- CPU usage monitoring (future enhancement)
"""

import logging
import os
import signal
import subprocess
import threading
import time
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


@dataclass
class ExecutionResult:
    """
    Result of a command execution with resource monitoring.

    This dataclass captures all relevant information about command execution
    including output, timing, and resource usage metrics.
    """

    success: bool
    exit_code: int
    stdout: str
    stderr: str
    elapsed_ms: int
    timed_out: bool
    stdout_truncated: bool
    stderr_truncated: bool
    original_stdout_size: int
    original_stderr_size: int


class TimeoutError(Exception):
    """Exception raised when a command execution times out."""

    pass


class ResourceLimitExceededError(Exception):
    """Exception raised when resource limits are exceeded."""

    pass


def execute_with_timeout(
    command: List[str],
    timeout_seconds: int = 30,
    max_output_size: int = 1024 * 1024,  # 1MB default
    cwd: Optional[str] = None,
    env: Optional[Dict[str, str]] = None,
) -> ExecutionResult:
    """
    Execute a command with timeout and output size limits.

    This function runs a subprocess with strict resource limits to prevent
    resource exhaustion. It enforces timeouts, limits output size, and
    provides detailed execution metrics.

    Args:
        command: Command and arguments to execute
        timeout_seconds: Maximum execution time in seconds
        max_output_size: Maximum size for stdout/stderr in bytes
        cwd: Working directory for command execution
        env: Environment variables for the command

    Returns:
        ExecutionResult: Detailed execution results with metrics

    Raises:
        ValueError: If command or timeout is invalid
        OSError: If command cannot be executed
    """
    if not command:
        raise ValueError("Command cannot be empty")

    if timeout_seconds <= 0:
        raise ValueError("Timeout must be positive")

    if max_output_size <= 0:
        raise ValueError("Max output size must be positive")

    logger.debug(
        f"Executing command with timeout {timeout_seconds}s: {' '.join(command)}"
    )

    start_time = time.time()

    try:
        # Start the process
        process = subprocess.Popen(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            cwd=cwd,
            env=env,
            preexec_fn=(
                os.setsid if os.name != "nt" else None
            ),  # Create process group on Unix
        )

        # Wait for completion with timeout
        try:
            stdout, stderr = process.communicate(timeout=timeout_seconds)
            timed_out = False
        except subprocess.TimeoutExpired:
            # Kill the process group to ensure all child processes are terminated
            if os.name != "nt":
                os.killpg(os.getpgid(process.pid), signal.SIGTERM)
                time.sleep(0.1)  # Give processes time to terminate gracefully
                try:
                    os.killpg(os.getpgid(process.pid), signal.SIGKILL)
                except ProcessLookupError:
                    pass  # Process already terminated
            else:
                process.terminate()
                time.sleep(0.1)
                process.kill()

            # Get any partial output
            try:
                stdout, stderr = process.communicate(timeout=1)
            except subprocess.TimeoutExpired:
                stdout, stderr = "", ""

            timed_out = True

        elapsed_ms = int((time.time() - start_time) * 1000)
        exit_code = (
            process.returncode if process.returncode is not None else 124
        )  # Timeout exit code

        # Handle output truncation
        original_stdout_size = len(stdout) if stdout else 0
        original_stderr_size = len(stderr) if stderr else 0

        stdout_truncated = original_stdout_size > max_output_size
        stderr_truncated = original_stderr_size > max_output_size

        if stdout_truncated:
            stdout = truncate_output(stdout, max_output_size, "stdout")

        if stderr_truncated:
            stderr = truncate_output(stderr, max_output_size, "stderr")

        success = not timed_out and exit_code == 0

        logger.debug(
            f"Command completed: exit_code={exit_code}, elapsed={elapsed_ms}ms, "
            f"stdout_size={original_stdout_size}, stderr_size={original_stderr_size}"
        )

        return ExecutionResult(
            success=success,
            exit_code=exit_code,
            stdout=stdout,
            stderr=stderr,
            elapsed_ms=elapsed_ms,
            timed_out=timed_out,
            stdout_truncated=stdout_truncated,
            stderr_truncated=stderr_truncated,
            original_stdout_size=original_stdout_size,
            original_stderr_size=original_stderr_size,
        )

    except FileNotFoundError as e:
        elapsed_ms = int((time.time() - start_time) * 1000)
        logger.error(f"Command not found: {command[0]}")
        return ExecutionResult(
            success=False,
            exit_code=127,  # Command not found
            stdout="",
            stderr=f"Command not found: {command[0]}",
            elapsed_ms=elapsed_ms,
            timed_out=False,
            stdout_truncated=False,
            stderr_truncated=False,
            original_stdout_size=0,
            original_stderr_size=0,
        )

    except PermissionError as e:
        elapsed_ms = int((time.time() - start_time) * 1000)
        logger.error(f"Permission denied executing command: {command[0]}")
        return ExecutionResult(
            success=False,
            exit_code=126,  # Permission denied
            stdout="",
            stderr=f"Permission denied: {command[0]}",
            elapsed_ms=elapsed_ms,
            timed_out=False,
            stdout_truncated=False,
            stderr_truncated=False,
            original_stdout_size=0,
            original_stderr_size=0,
        )

    except Exception as e:
        elapsed_ms = int((time.time() - start_time) * 1000)
        logger.error(f"Unexpected error executing command: {str(e)}")
        return ExecutionResult(
            success=False,
            exit_code=1,
            stdout="",
            stderr=f"Execution error: {str(e)}",
            elapsed_ms=elapsed_ms,
            timed_out=False,
            stdout_truncated=False,
            stderr_truncated=False,
            original_stdout_size=0,
            original_stderr_size=0,
        )


def truncate_output(output: str, max_size: int, stream_name: str = "output") -> str:
    """
    Truncate output string with clear truncation indicator.

    This function limits output size while preserving both the beginning
    and end of the output, with a clear indicator of truncation.

    Args:
        output: The output string to truncate
        max_size: Maximum allowed size in bytes
        stream_name: Name of the stream for the truncation message

    Returns:
        str: Truncated output with truncation indicator
    """
    if len(output) <= max_size:
        return output

    # Calculate sizes for head and tail portions
    truncation_msg = (
        f"\n[TRUNCATED: {stream_name} too long, showing first and last portions]\n"
    )
    available_size = max_size - len(truncation_msg)

    if available_size <= 100:  # Not enough space for meaningful content
        return output[: max_size - 50] + f"\n[TRUNCATED: {stream_name} too long]"

    # Show first 60% and last 40% of available space
    head_size = int(available_size * 0.6)
    tail_size = available_size - head_size

    head = output[:head_size]
    tail = output[-tail_size:]

    return head + truncation_msg + tail


def get_tool_timeout(tool_name: str, default_timeout: int = 30) -> int:
    """
    Get the configured timeout for a specific tool.

    This function looks up tool-specific timeout configuration from
    environment variables or returns a sensible default.

    Args:
        tool_name: Name of the tool
        default_timeout: Default timeout in seconds

    Returns:
        int: Timeout in seconds for the tool
    """
    # Check for tool-specific timeout environment variable
    env_var = f"TOOL_TIMEOUT_{tool_name.upper()}"
    timeout_str = os.environ.get(env_var)

    if timeout_str:
        try:
            timeout = int(timeout_str)
            if timeout > 0:
                return timeout
            else:
                logger.warning(
                    f"Invalid timeout value for {tool_name}: {timeout_str}, using default"
                )
        except ValueError:
            logger.warning(
                f"Invalid timeout format for {tool_name}: {timeout_str}, using default"
            )

    # Check for global timeout override
    global_timeout_str = os.environ.get("TOOL_TIMEOUT_DEFAULT")
    if global_timeout_str:
        try:
            timeout = int(global_timeout_str)
            if timeout > 0:
                return timeout
        except ValueError:
            logger.warning(
                f"Invalid global timeout format: {global_timeout_str}, using default"
            )

    return default_timeout


def get_output_limit(tool_name: str, default_limit: int = 1024 * 1024) -> int:
    """
    Get the configured output limit for a specific tool.

    Args:
        tool_name: Name of the tool
        default_limit: Default output limit in bytes

    Returns:
        int: Output limit in bytes for the tool
    """
    # Check for tool-specific output limit environment variable
    env_var = f"TOOL_OUTPUT_LIMIT_{tool_name.upper()}"
    limit_str = os.environ.get(env_var)

    if limit_str:
        try:
            limit = int(limit_str)
            if limit > 0:
                return limit
            else:
                logger.warning(
                    f"Invalid output limit for {tool_name}: {limit_str}, using default"
                )
        except ValueError:
            logger.warning(
                f"Invalid output limit format for {tool_name}: {limit_str}, using default"
            )

    # Check for global output limit override
    global_limit_str = os.environ.get("TOOL_OUTPUT_LIMIT_DEFAULT")
    if global_limit_str:
        try:
            limit = int(global_limit_str)
            if limit > 0:
                return limit
        except ValueError:
            logger.warning(
                f"Invalid global output limit format: {global_limit_str}, using default"
            )

    return default_limit


class ResourceMonitor:
    """
    Monitor resource usage during tool execution.

    This class provides monitoring capabilities for CPU, memory, and other
    resource usage during tool execution. It can be used to implement
    more sophisticated resource limiting in the future.
    """

    def __init__(self):
        self.start_time = None
        self.peak_memory = 0
        self.cpu_time = 0

    def start_monitoring(self):
        """Start resource monitoring."""
        self.start_time = time.time()
        # TODO: Implement actual resource monitoring
        # This could use psutil or similar libraries to track:
        # - Memory usage
        # - CPU usage
        # - File descriptor count
        # - Network connections

    def stop_monitoring(self) -> Dict[str, Any]:
        """
        Stop monitoring and return resource usage metrics.

        Returns:
            dict: Resource usage metrics
        """
        if self.start_time is None:
            return {}

        elapsed = time.time() - self.start_time

        # TODO: Implement actual resource collection
        return {
            "elapsed_seconds": elapsed,
            "peak_memory_mb": self.peak_memory,
            "cpu_time_seconds": self.cpu_time,
        }
