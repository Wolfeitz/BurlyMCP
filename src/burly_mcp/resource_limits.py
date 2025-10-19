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
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

try:
    import psutil
    PSUTIL_AVAILABLE = True
except ImportError:
    PSUTIL_AVAILABLE = False

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


class ResourceLimiter:
    """Resource limiter for monitoring and enforcing resource constraints."""
    
    def __init__(self, max_memory_mb: int = 512, max_cpu_percent: int = 80, max_execution_time: int = 300):
        """Initialize resource limiter.
        
        Args:
            max_memory_mb: Maximum memory usage in MB
            max_cpu_percent: Maximum CPU usage percentage
            max_execution_time: Maximum execution time in seconds
        """
        self.max_memory_mb = max_memory_mb
        self.max_cpu_percent = max_cpu_percent
        self.max_execution_time = max_execution_time
        self.monitoring_active = False
        self.resource_history = []
    
    def check_memory_usage(self, pid: Optional[int] = None) -> bool:
        """Check if memory usage is within limits.
        
        Args:
            pid: Process ID to check (current process if None)
            
        Returns:
            bool: True if within limits
        """
        if not PSUTIL_AVAILABLE:
            return True
        
        try:
            process = psutil.Process(pid) if pid else psutil.Process()
            memory_mb = process.memory_info().rss / (1024 * 1024)
            return memory_mb <= self.max_memory_mb
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            return True
    
    def check_cpu_usage(self, pid: Optional[int] = None) -> bool:
        """Check if CPU usage is within limits.
        
        Args:
            pid: Process ID to check (current process if None)
            
        Returns:
            bool: True if within limits
        """
        if not PSUTIL_AVAILABLE:
            return True
        
        try:
            process = psutil.Process(pid) if pid else psutil.Process()
            cpu_percent = process.cpu_percent(interval=0.1)
            return cpu_percent <= self.max_cpu_percent
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            return True
    
    def check_execution_time(self, start_time: float) -> bool:
        """Check if execution time is within limits.
        
        Args:
            start_time: Start time timestamp
            
        Returns:
            bool: True if within limits
        """
        elapsed = time.time() - start_time
        return elapsed <= self.max_execution_time
    
    def monitor_process(self, pid: int, duration: float = 1.0) -> Dict[str, Any]:
        """Monitor a process for resource usage.
        
        Args:
            pid: Process ID to monitor
            duration: Monitoring duration in seconds
            
        Returns:
            Dict[str, Any]: Resource usage statistics
        """
        if not PSUTIL_AVAILABLE:
            return {"error": "psutil not available"}
        
        try:
            process = psutil.Process(pid)
            start_time = time.time()
            
            # Monitor for specified duration
            memory_samples = []
            cpu_samples = []
            
            while time.time() - start_time < duration:
                try:
                    memory_mb = process.memory_info().rss / (1024 * 1024)
                    cpu_percent = process.cpu_percent(interval=0.1)
                    
                    memory_samples.append(memory_mb)
                    cpu_samples.append(cpu_percent)
                    
                    time.sleep(0.1)
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    break
            
            return {
                "memory_mb": {
                    "current": memory_samples[-1] if memory_samples else 0,
                    "peak": max(memory_samples) if memory_samples else 0,
                    "average": sum(memory_samples) / len(memory_samples) if memory_samples else 0,
                },
                "cpu_percent": {
                    "current": cpu_samples[-1] if cpu_samples else 0,
                    "peak": max(cpu_samples) if cpu_samples else 0,
                    "average": sum(cpu_samples) / len(cpu_samples) if cpu_samples else 0,
                },
                "within_limits": all([
                    max(memory_samples) <= self.max_memory_mb if memory_samples else True,
                    max(cpu_samples) <= self.max_cpu_percent if cpu_samples else True,
                ])
            }
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            return {"error": "Process not accessible"}
    
    def terminate_process(self, pid: int, force: bool = False) -> bool:
        """Terminate a process that exceeds resource limits.
        
        Args:
            pid: Process ID to terminate
            force: Whether to force kill the process
            
        Returns:
            bool: True if process was terminated
        """
        if not PSUTIL_AVAILABLE:
            return False
        
        try:
            process = psutil.Process(pid)
            
            if force:
                process.kill()
            else:
                process.terminate()
                # Wait for graceful termination
                try:
                    process.wait(timeout=5)
                except psutil.TimeoutExpired:
                    process.kill()
            
            return True
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            return False
    
    def get_process_stats(self, pid: int) -> Dict[str, Any]:
        """Get detailed process statistics.
        
        Args:
            pid: Process ID
            
        Returns:
            Dict[str, Any]: Process statistics
        """
        if not PSUTIL_AVAILABLE:
            return {"error": "psutil not available"}
        
        try:
            process = psutil.Process(pid)
            
            return {
                "pid": pid,
                "name": process.name(),
                "status": process.status(),
                "memory_mb": process.memory_info().rss / (1024 * 1024),
                "cpu_percent": process.cpu_percent(),
                "create_time": process.create_time(),
                "num_threads": process.num_threads(),
            }
        except (psutil.NoSuchProcess, psutil.AccessDenied) as e:
            return {"error": str(e)}
    
    @contextmanager
    def resource_monitor_context(self, check_interval: float = 1.0):
        """Context manager for resource monitoring.
        
        Args:
            check_interval: Interval between resource checks in seconds
        """
        self.monitoring_active = True
        start_time = time.time()
        
        def monitor_loop():
            while self.monitoring_active:
                if not self.check_memory_usage():
                    logger.warning("Memory limit exceeded")
                
                if not self.check_cpu_usage():
                    logger.warning("CPU limit exceeded")
                
                if not self.check_execution_time(start_time):
                    logger.warning("Execution time limit exceeded")
                    break
                
                time.sleep(check_interval)
        
        monitor_thread = threading.Thread(target=monitor_loop, daemon=True)
        monitor_thread.start()
        
        try:
            yield self
        finally:
            self.monitoring_active = False
            monitor_thread.join(timeout=1.0)
    
    def get_resource_usage_history(self) -> List[Dict[str, Any]]:
        """Get resource usage history.
        
        Returns:
            List[Dict[str, Any]]: Resource usage history
        """
        return self.resource_history.copy()
    
    def get_resource_usage_statistics(self) -> Dict[str, Any]:
        """Get resource usage statistics.
        
        Returns:
            Dict[str, Any]: Resource usage statistics
        """
        if not self.resource_history:
            return {"error": "No resource usage data available"}
        
        memory_values = [entry.get("memory_mb", 0) for entry in self.resource_history]
        cpu_values = [entry.get("cpu_percent", 0) for entry in self.resource_history]
        
        return {
            "memory_mb": {
                "min": min(memory_values) if memory_values else 0,
                "max": max(memory_values) if memory_values else 0,
                "average": sum(memory_values) / len(memory_values) if memory_values else 0,
            },
            "cpu_percent": {
                "min": min(cpu_values) if cpu_values else 0,
                "max": max(cpu_values) if cpu_values else 0,
                "average": sum(cpu_values) / len(cpu_values) if cpu_values else 0,
            },
            "sample_count": len(self.resource_history),
        }


class ResourceMonitor:
    """
    Monitor resource usage during tool execution.

    This class provides monitoring capabilities for CPU, memory, and other
    resource usage during tool execution. It can be used to implement
    more sophisticated resource limiting in the future.
    """

    def __init__(self) -> None:
        self.start_time: Optional[float] = None
        self.peak_memory = 0
        self.cpu_time = 0

    def start_monitoring(self) -> None:
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


# Convenience function for resource limits
def resource_limits(max_memory_mb: int = 512, max_cpu_percent: int = 80, max_execution_time: int = 300) -> ResourceLimiter:
    """Create a ResourceLimiter with specified limits.
    
    Args:
        max_memory_mb: Maximum memory usage in MB
        max_cpu_percent: Maximum CPU usage percentage  
        max_execution_time: Maximum execution time in seconds
        
    Returns:
        ResourceLimiter: Configured resource limiter
    """
    return ResourceLimiter(max_memory_mb, max_cpu_percent, max_execution_time)
