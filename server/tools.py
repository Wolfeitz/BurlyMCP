"""
Tool Registry and Execution Framework

This module implements the tool registry that manages available tools and
handles their execution. Each tool is a function that performs a specific
system operation while respecting security constraints and audit requirements.

Available Tools:
- docker_ps: List Docker containers
- disk_space: Check filesystem usage
- blog_stage_markdown: Validate blog post front-matter
- blog_publish_static: Publish blog content with confirmation
- gotify_ping: Send test notifications

All tools follow a consistent interface and are executed with timeout
protection, output limiting, and comprehensive audit logging.

Tool Execution Flow:
1. Validate tool exists and arguments are valid
2. Check if confirmation is required for mutating operations
3. Execute tool with timeout and output capture
4. Log execution details for audit
5. Send notifications if configured
6. Return standardized response
"""

import glob
import json
import logging
import os
import re
import shutil
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Any, Dict, Optional

import yaml

from .audit import log_tool_execution
from .notifications import (
    notify_tool_confirmation,
    notify_tool_failure,
    notify_tool_success,
)
from .resource_limits import execute_with_timeout, get_output_limit, get_tool_timeout
from .security import (
    SecurityViolationError,
    sanitize_file_path,
    validate_blog_stage_path,
    validate_path_within_root,
)

logger = logging.getLogger(__name__)


@dataclass
class ToolResult:
    """
    Standardized result from tool execution.

    This dataclass provides a consistent interface for all tool results,
    including success/failure status, output data, and execution metrics.
    """

    success: bool
    need_confirm: bool
    summary: str
    data: Optional[Dict[str, Any]]
    stdout: str
    stderr: str
    exit_code: int
    elapsed_ms: int


class ToolRegistry:
    """
    Registry of available tools and their execution logic.

    The tool registry manages all available tools, handles their execution
    with proper security constraints, and provides a uniform interface
    for the MCP protocol handler.
    """

    def __init__(self):
        """Initialize the tool registry with available tools."""
        self.tools = {
            "docker_ps": self._docker_ps,
            "disk_space": self._disk_space,
            "blog_stage_markdown": self._blog_stage_markdown,
            "blog_publish_static": self._blog_publish_static,
            "gotify_ping": self._gotify_ping,
        }

        # Tool characteristics for audit logging
        self.tool_characteristics = {
            "docker_ps": {"mutates": False, "requires_confirm": False},
            "disk_space": {"mutates": False, "requires_confirm": False},
            "blog_stage_markdown": {"mutates": False, "requires_confirm": False},
            "blog_publish_static": {"mutates": True, "requires_confirm": True},
            "gotify_ping": {"mutates": False, "requires_confirm": False},
        }

    def execute_tool(self, tool_name: str, args: Dict[str, Any]) -> ToolResult:
        """
        Execute the specified tool with the given arguments.

        Args:
            tool_name: Name of the tool to execute
            args: Arguments to pass to the tool

        Returns:
            ToolResult with execution details and output
        """
        if tool_name not in self.tools:
            result = ToolResult(
                success=False,
                need_confirm=False,
                summary=f"Unknown tool: {tool_name}",
                data={"available_tools": list(self.tools.keys())},
                stdout="",
                stderr=f"Tool '{tool_name}' not found",
                exit_code=1,
                elapsed_ms=0,
            )

            # Log the failed tool execution
            log_tool_execution(
                tool_name=tool_name,
                args=args,
                mutates=False,
                requires_confirm=False,
                status="fail",
                exit_code=result.exit_code,
                elapsed_ms=result.elapsed_ms,
            )

            # Send failure notification
            try:
                notify_tool_failure(tool_name, result.summary, result.exit_code)
            except Exception as e:
                logger.warning(f"Notification failed for {tool_name}: {str(e)}")

            return result

        start_time = time.time()

        try:
            # TODO: Add policy validation, timeout enforcement, etc.
            result = self.tools[tool_name](args)
            result.elapsed_ms = int((time.time() - start_time) * 1000)

            # Determine tool characteristics for audit logging
            mutates = self._tool_mutates(tool_name)
            requires_confirm = self._tool_requires_confirm(tool_name)

            # Determine status for audit logging
            if result.need_confirm:
                status = "need_confirm"
            elif result.success:
                status = "ok"
            else:
                status = "fail"

            # Log the tool execution
            log_tool_execution(
                tool_name=tool_name,
                args=args,
                mutates=mutates,
                requires_confirm=requires_confirm,
                status=status,
                exit_code=result.exit_code,
                elapsed_ms=result.elapsed_ms,
                stdout_truncated=getattr(result, "stdout_truncated", 0),
                stderr_truncated=getattr(result, "stderr_truncated", 0),
            )

            # Send notifications based on execution result
            try:
                if result.need_confirm:
                    notify_tool_confirmation(tool_name, result.summary)
                elif result.success:
                    notify_tool_success(tool_name, result.summary, result.elapsed_ms)
                else:
                    notify_tool_failure(tool_name, result.summary, result.exit_code)
            except Exception as e:
                # Notification failures should not break tool execution
                logger.warning(f"Notification failed for {tool_name}: {str(e)}")

            return result

        except Exception as e:
            elapsed_ms = int((time.time() - start_time) * 1000)
            result = ToolResult(
                success=False,
                need_confirm=False,
                summary=f"Tool execution failed: {str(e)}",
                data=None,
                stdout="",
                stderr=str(e),
                exit_code=1,
                elapsed_ms=elapsed_ms,
            )

            # Log the failed tool execution
            log_tool_execution(
                tool_name=tool_name,
                args=args,
                mutates=self._tool_mutates(tool_name),
                requires_confirm=self._tool_requires_confirm(tool_name),
                status="fail",
                exit_code=result.exit_code,
                elapsed_ms=result.elapsed_ms,
            )

            # Send failure notification
            try:
                notify_tool_failure(tool_name, result.summary, result.exit_code)
            except Exception as e:
                logger.warning(f"Notification failed for {tool_name}: {str(e)}")

            return result

    def _tool_mutates(self, tool_name: str) -> bool:
        """
        Check if a tool mutates system state.

        Args:
            tool_name: Name of the tool

        Returns:
            bool: True if the tool mutates system state
        """
        return self.tool_characteristics.get(tool_name, {}).get("mutates", False)

    def _tool_requires_confirm(self, tool_name: str) -> bool:
        """
        Check if a tool requires confirmation.

        Args:
            tool_name: Name of the tool

        Returns:
            bool: True if the tool requires confirmation
        """
        return self.tool_characteristics.get(tool_name, {}).get(
            "requires_confirm", False
        )

    def _docker_ps(self, args: Dict[str, Any]) -> ToolResult:
        """
        List Docker containers using docker ps command.

        This tool executes 'docker ps --format table' to show running
        containers in a human-readable format. It handles Docker socket
        access errors gracefully and returns structured container data.
        """
        try:
            # Execute docker ps with table format for human-readable output
            cmd = [
                "docker",
                "ps",
                "--format",
                "table {{.ID}}\t{{.Image}}\t{{.Command}}\t{{.CreatedAt}}\t{{.Status}}\t{{.Ports}}\t{{.Names}}",
            ]

            # Get configured timeout and output limits for docker_ps
            timeout = get_tool_timeout("docker_ps", default_timeout=30)
            output_limit = get_output_limit(
                "docker_ps", default_limit=512 * 1024
            )  # 512KB for docker output

            result = execute_with_timeout(
                command=cmd, timeout_seconds=timeout, max_output_size=output_limit
            )

            if result.success and result.exit_code == 0:
                # Parse the output to extract container information
                lines = result.stdout.strip().split("\n")
                containers = []

                if len(lines) > 1:  # Skip header line
                    for line in lines[1:]:
                        if line.strip():  # Skip empty lines
                            parts = line.split("\t")
                            if len(parts) >= 7:
                                containers.append(
                                    {
                                        "id": parts[0].strip(),
                                        "image": parts[1].strip(),
                                        "command": parts[2].strip(),
                                        "created": parts[3].strip(),
                                        "status": parts[4].strip(),
                                        "ports": parts[5].strip(),
                                        "names": parts[6].strip(),
                                    }
                                )

                container_count = len(containers)
                summary = f"Found {container_count} running container{'s' if container_count != 1 else ''}"

                # Add truncation info to summary if output was truncated
                if result.stdout_truncated or result.stderr_truncated:
                    summary += " (output truncated)"

                return ToolResult(
                    success=True,
                    need_confirm=False,
                    summary=summary,
                    data={
                        "containers": containers,
                        "count": container_count,
                        "output_truncated": result.stdout_truncated
                        or result.stderr_truncated,
                        "original_output_size": result.original_stdout_size
                        + result.original_stderr_size,
                    },
                    stdout=result.stdout,
                    stderr=result.stderr,
                    exit_code=result.exit_code,
                    elapsed_ms=result.elapsed_ms,
                )
            else:
                # Handle Docker command errors or timeouts
                if result.timed_out:
                    summary = f"Docker command timed out after {timeout} seconds"
                    error_msg = "Command timed out"
                else:
                    error_msg = result.stderr.strip() or "Docker command failed"

                    # Check for common Docker socket access errors
                    if "permission denied" in error_msg.lower():
                        summary = "Docker access denied - check socket permissions"
                    elif "cannot connect to the docker daemon" in error_msg.lower():
                        summary = "Cannot connect to Docker daemon - is Docker running?"
                    elif "docker: command not found" in error_msg.lower():
                        summary = "Docker CLI not found - is Docker installed?"
                    else:
                        summary = (
                            f"Docker command failed with exit code {result.exit_code}"
                        )

                # Add truncation info if applicable
                if result.stdout_truncated or result.stderr_truncated:
                    summary += " (output truncated)"

                return ToolResult(
                    success=False,
                    need_confirm=False,
                    summary=summary,
                    data={
                        "error": error_msg,
                        "timed_out": result.timed_out,
                        "output_truncated": result.stdout_truncated
                        or result.stderr_truncated,
                    },
                    stdout=result.stdout,
                    stderr=result.stderr,
                    exit_code=result.exit_code,
                    elapsed_ms=result.elapsed_ms,
                )

        except Exception as e:
            return ToolResult(
                success=False,
                need_confirm=False,
                summary=f"Unexpected error executing docker ps: {str(e)}",
                data={"error": str(e)},
                stdout="",
                stderr=str(e),
                exit_code=1,
                elapsed_ms=0,
            )

    def _disk_space(self, args: Dict[str, Any]) -> ToolResult:
        """
        Check filesystem disk space using df -hT command.

        This tool shows filesystem usage in human-readable format
        with filesystem types. It handles permission and access errors
        gracefully and returns structured filesystem data.
        """
        try:
            # Execute df -hT for human-readable output with filesystem types
            cmd = ["df", "-hT"]

            # Get configured timeout and output limits for disk_space
            timeout = get_tool_timeout("disk_space", default_timeout=15)
            output_limit = get_output_limit(
                "disk_space", default_limit=256 * 1024
            )  # 256KB for filesystem output

            result = execute_with_timeout(
                command=cmd, timeout_seconds=timeout, max_output_size=output_limit
            )

            if result.success and result.exit_code == 0:
                # Parse the output to extract filesystem information
                lines = result.stdout.strip().split("\n")
                filesystems = []

                if len(lines) > 1:  # Skip header line
                    for line in lines[1:]:
                        if line.strip():  # Skip empty lines
                            parts = line.split()
                            if len(parts) >= 7:
                                # Handle cases where filesystem name contains spaces
                                filesystem = parts[0]
                                fs_type = parts[1]
                                size = parts[2]
                                used = parts[3]
                                avail = parts[4]
                                use_percent = parts[5]
                                mounted_on = " ".join(
                                    parts[6:]
                                )  # Join remaining parts for mount point

                                # Parse usage percentage as integer for analysis
                                try:
                                    usage_int = int(use_percent.rstrip("%"))
                                except ValueError:
                                    usage_int = 0

                                filesystems.append(
                                    {
                                        "filesystem": filesystem,
                                        "type": fs_type,
                                        "size": size,
                                        "used": used,
                                        "available": avail,
                                        "use_percent": use_percent,
                                        "usage_int": usage_int,
                                        "mounted_on": mounted_on,
                                    }
                                )

                # Generate summary with high usage warnings
                fs_count = len(filesystems)
                high_usage_fs = [fs for fs in filesystems if fs["usage_int"] > 80]

                if high_usage_fs:
                    high_usage_names = [fs["mounted_on"] for fs in high_usage_fs]
                    summary = f"Found {fs_count} filesystems, {len(high_usage_fs)} with >80% usage: {', '.join(high_usage_names)}"
                else:
                    summary = (
                        f"Found {fs_count} filesystems, all with healthy usage levels"
                    )

                # Add truncation info to summary if output was truncated
                if result.stdout_truncated or result.stderr_truncated:
                    summary += " (output truncated)"

                return ToolResult(
                    success=True,
                    need_confirm=False,
                    summary=summary,
                    data={
                        "filesystems": filesystems,
                        "count": fs_count,
                        "high_usage": high_usage_fs,
                        "output_truncated": result.stdout_truncated
                        or result.stderr_truncated,
                        "original_output_size": result.original_stdout_size
                        + result.original_stderr_size,
                    },
                    stdout=result.stdout,
                    stderr=result.stderr,
                    exit_code=result.exit_code,
                    elapsed_ms=result.elapsed_ms,
                )
            else:
                # Handle df command errors or timeouts
                if result.timed_out:
                    summary = f"Disk space command timed out after {timeout} seconds"
                    error_msg = "Command timed out"
                else:
                    error_msg = result.stderr.strip() or "df command failed"

                    # Check for common filesystem access errors
                    if "permission denied" in error_msg.lower():
                        summary = "Permission denied accessing some filesystems"
                    elif "no such file or directory" in error_msg.lower():
                        summary = "Some filesystems are not accessible"
                    else:
                        summary = f"Disk space command failed with exit code {result.exit_code}"

                # Add truncation info if applicable
                if result.stdout_truncated or result.stderr_truncated:
                    summary += " (output truncated)"

                return ToolResult(
                    success=False,
                    need_confirm=False,
                    summary=summary,
                    data={
                        "error": error_msg,
                        "timed_out": result.timed_out,
                        "output_truncated": result.stdout_truncated
                        or result.stderr_truncated,
                    },
                    stdout=result.stdout,
                    stderr=result.stderr,
                    exit_code=result.exit_code,
                    elapsed_ms=result.elapsed_ms,
                )

        except Exception as e:
            return ToolResult(
                success=False,
                need_confirm=False,
                summary=f"Unexpected error checking disk space: {str(e)}",
                data={"error": str(e)},
                stdout="",
                stderr=str(e),
                exit_code=1,
                elapsed_ms=0,
            )

    def _blog_stage_markdown(self, args: Dict[str, Any]) -> ToolResult:
        """
        Validate Markdown file with YAML front-matter for blog staging.

        This tool checks that blog posts have proper front-matter
        with required fields like title, date, and tags. It validates
        file access and YAML parsing, ensuring blog posts meet
        publishing requirements.
        """
        file_path = args.get("file_path", "")

        if not file_path:
            return ToolResult(
                success=False,
                need_confirm=False,
                summary="Missing required argument: file_path",
                data={"validation_errors": ["file_path is required"]},
                stdout="",
                stderr="Missing file_path argument",
                exit_code=1,
                elapsed_ms=0,
            )

        try:
            # Sanitize the input file path
            sanitized_path = sanitize_file_path(file_path)

            # Validate the file path against BLOG_STAGE_ROOT
            try:
                abs_file_path = validate_blog_stage_path(sanitized_path)
            except SecurityViolationError as e:
                return ToolResult(
                    success=False,
                    need_confirm=False,
                    summary="Path traversal detected - file must be within staging directory",
                    data={"validation_errors": ["file_path outside staging directory"]},
                    stdout="",
                    stderr=str(e),
                    exit_code=1,
                    elapsed_ms=0,
                )
            except ValueError as e:
                return ToolResult(
                    success=False,
                    need_confirm=False,
                    summary="Configuration error - BLOG_STAGE_ROOT not set",
                    data={"validation_errors": ["blog_stage_root_not_configured"]},
                    stdout="",
                    stderr=str(e),
                    exit_code=1,
                    elapsed_ms=0,
                )

            # Check if file exists and is readable
            if not os.path.exists(abs_file_path):
                return ToolResult(
                    success=False,
                    need_confirm=False,
                    summary=f"File not found: {file_path}",
                    data={"validation_errors": ["file_not_found"]},
                    stdout="",
                    stderr=f"File does not exist: {abs_file_path}",
                    exit_code=2,
                    elapsed_ms=0,
                )

            if not os.path.isfile(abs_file_path):
                return ToolResult(
                    success=False,
                    need_confirm=False,
                    summary=f"Path is not a file: {file_path}",
                    data={"validation_errors": ["not_a_file"]},
                    stdout="",
                    stderr=f"Path is not a regular file: {abs_file_path}",
                    exit_code=2,
                    elapsed_ms=0,
                )

            # Read the file content
            try:
                with open(abs_file_path, "r", encoding="utf-8") as f:
                    content = f.read()
            except PermissionError:
                return ToolResult(
                    success=False,
                    need_confirm=False,
                    summary=f"Permission denied reading file: {file_path}",
                    data={"validation_errors": ["permission_denied"]},
                    stdout="",
                    stderr=f"Permission denied: {abs_file_path}",
                    exit_code=13,
                    elapsed_ms=0,
                )
            except UnicodeDecodeError as e:
                return ToolResult(
                    success=False,
                    need_confirm=False,
                    summary=f"File encoding error: {str(e)}",
                    data={"validation_errors": ["encoding_error"]},
                    stdout="",
                    stderr=f"Unicode decode error: {str(e)}",
                    exit_code=1,
                    elapsed_ms=0,
                )

            # Parse YAML front-matter
            validation_errors = []
            front_matter = {}

            # Check for YAML front-matter delimiters
            if not content.startswith("---\n"):
                validation_errors.append(
                    "Missing YAML front-matter start delimiter (---)"
                )
            else:
                # Find the end of front-matter
                end_delimiter_match = re.search(r"\n---\n", content[4:])
                if not end_delimiter_match:
                    validation_errors.append(
                        "Missing YAML front-matter end delimiter (---)"
                    )
                else:
                    # Extract YAML content
                    yaml_content = content[4 : end_delimiter_match.start() + 4]

                    try:
                        front_matter = yaml.safe_load(yaml_content) or {}
                    except yaml.YAMLError as e:
                        validation_errors.append(f"Invalid YAML syntax: {str(e)}")
                        front_matter = {}

            # Validate required front-matter fields
            required_fields = ["title", "date", "tags"]
            for field in required_fields:
                if field not in front_matter:
                    validation_errors.append(f"Missing required field: {field}")
                elif not front_matter[field]:
                    validation_errors.append(f"Empty required field: {field}")

            # Additional validation for specific fields
            if "date" in front_matter:
                date_value = front_matter["date"]
                # Basic date format validation (YYYY-MM-DD or ISO format)
                if isinstance(date_value, str):
                    if not re.match(r"^\d{4}-\d{2}-\d{2}", date_value):
                        validation_errors.append(
                            "Date field should be in YYYY-MM-DD format"
                        )

            if "tags" in front_matter:
                tags_value = front_matter["tags"]
                if not isinstance(tags_value, list):
                    validation_errors.append("Tags field should be a list")
                elif len(tags_value) == 0:
                    validation_errors.append("Tags field should not be empty")

            # Generate summary
            if validation_errors:
                summary = f"Blog post validation failed with {len(validation_errors)} error(s)"
                success = False
            else:
                summary = f"Blog post validation passed - found {len(front_matter)} front-matter fields"
                success = True

            return ToolResult(
                success=success,
                need_confirm=False,
                summary=summary,
                data={
                    "front_matter": front_matter,
                    "validation_errors": validation_errors,
                    "file_path": file_path,
                    "file_size": len(content),
                },
                stdout=f"Validated {file_path}: {len(validation_errors)} errors found",
                stderr="\n".join(validation_errors) if validation_errors else "",
                exit_code=0 if success else 1,
                elapsed_ms=0,
            )

        except Exception as e:
            return ToolResult(
                success=False,
                need_confirm=False,
                summary=f"Unexpected error validating blog post: {str(e)}",
                data={"validation_errors": [str(e)]},
                stdout="",
                stderr=str(e),
                exit_code=1,
                elapsed_ms=0,
            )

    def _blog_publish_static(self, args: Dict[str, Any]) -> ToolResult:
        """
        Publish blog content from staging to publish directory.

        This is a mutating operation that requires confirmation.
        It copies validated blog posts to the public directory with
        safe file operations and path validation.
        """
        try:
            # Get environment variables for directory paths
            blog_stage_root = os.environ.get("BLOG_STAGE_ROOT")
            blog_publish_root = os.environ.get("BLOG_PUBLISH_ROOT")

            if not blog_stage_root:
                return ToolResult(
                    success=False,
                    need_confirm=False,
                    summary="Configuration error - BLOG_STAGE_ROOT not configured",
                    data={"error": "blog_stage_root_not_configured"},
                    stdout="",
                    stderr="BLOG_STAGE_ROOT environment variable not set",
                    exit_code=1,
                    elapsed_ms=0,
                )

            if not blog_publish_root:
                return ToolResult(
                    success=False,
                    need_confirm=False,
                    summary="Configuration error - BLOG_PUBLISH_ROOT not configured",
                    data={"error": "blog_publish_root_not_configured"},
                    stdout="",
                    stderr="BLOG_PUBLISH_ROOT environment variable not set",
                    exit_code=1,
                    elapsed_ms=0,
                )

            # Get optional file pattern filter and sanitize it
            file_pattern = sanitize_file_path(args.get("pattern", "*.md"))

            # Resolve absolute paths
            abs_stage_root = os.path.abspath(blog_stage_root)
            abs_publish_root = os.path.abspath(blog_publish_root)

            # Find files to publish in staging directory
            stage_pattern = os.path.join(abs_stage_root, file_pattern)
            files_to_publish = glob.glob(stage_pattern, recursive=True)

            # Filter to only include files (not directories)
            files_to_publish = [f for f in files_to_publish if os.path.isfile(f)]

            # Calculate relative paths for display
            relative_files = []
            for file_path in files_to_publish:
                try:
                    rel_path = os.path.relpath(file_path, abs_stage_root)
                    relative_files.append(rel_path)
                except ValueError:
                    # Skip files outside staging directory
                    continue

            # Check if confirmation was provided
            if not args.get("_confirm", False):
                return ToolResult(
                    success=False,
                    need_confirm=True,
                    summary=f"Blog publishing requires confirmation - {len(relative_files)} file(s) ready to publish",
                    data={
                        "files_to_publish": relative_files,
                        "stage_root": blog_stage_root,
                        "publish_root": blog_publish_root,
                        "pattern": file_pattern,
                    },
                    stdout=f"Files ready to publish:\n" + "\n".join(relative_files),
                    stderr="",
                    exit_code=0,
                    elapsed_ms=0,
                )

            # Confirmation provided - proceed with publishing
            if not files_to_publish:
                return ToolResult(
                    success=True,
                    need_confirm=False,
                    summary="No files found to publish",
                    data={"files_written": 0, "pattern": file_pattern},
                    stdout="No files matching pattern found in staging directory",
                    stderr="",
                    exit_code=0,
                    elapsed_ms=0,
                )

            # Ensure publish directory exists
            os.makedirs(abs_publish_root, exist_ok=True)

            # Copy files with safety checks
            files_written = 0
            copy_errors = []
            copied_files = []

            for source_file in files_to_publish:
                try:
                    # Calculate destination path
                    rel_path = os.path.relpath(source_file, abs_stage_root)

                    # Validate destination path to prevent path traversal
                    try:
                        abs_dest_file = validate_path_within_root(
                            file_path=rel_path,
                            root_directory=abs_publish_root,
                            operation_name="blog_publish",
                        )
                    except SecurityViolationError as e:
                        copy_errors.append(
                            f"Path traversal detected for {rel_path}: {str(e)}"
                        )
                        continue

                    # Create destination directory if needed
                    dest_dir = os.path.dirname(abs_dest_file)
                    os.makedirs(dest_dir, exist_ok=True)

                    # Copy the file
                    shutil.copy2(source_file, abs_dest_file)
                    files_written += 1
                    copied_files.append(rel_path)

                except PermissionError as e:
                    copy_errors.append(
                        f"Permission denied copying {rel_path}: {str(e)}"
                    )
                except OSError as e:
                    copy_errors.append(f"OS error copying {rel_path}: {str(e)}")
                except Exception as e:
                    copy_errors.append(f"Unexpected error copying {rel_path}: {str(e)}")

            # Generate summary
            if copy_errors:
                if files_written > 0:
                    summary = f"Partially completed: {files_written} files published, {len(copy_errors)} errors"
                    success = False  # Partial failure
                else:
                    summary = f"Publishing failed: {len(copy_errors)} errors, no files published"
                    success = False
            else:
                summary = f"Successfully published {files_written} file(s) to {blog_publish_root}"
                success = True

            return ToolResult(
                success=success,
                need_confirm=False,
                summary=summary,
                data={
                    "files_written": files_written,
                    "copied_files": copied_files,
                    "errors": copy_errors,
                    "stage_root": blog_stage_root,
                    "publish_root": blog_publish_root,
                },
                stdout=f"Published {files_written} files:\n" + "\n".join(copied_files),
                stderr="\n".join(copy_errors) if copy_errors else "",
                exit_code=0 if success else 1,
                elapsed_ms=0,
            )

        except Exception as e:
            return ToolResult(
                success=False,
                need_confirm=False,
                summary=f"Unexpected error during blog publishing: {str(e)}",
                data={"error": str(e)},
                stdout="",
                stderr=str(e),
                exit_code=1,
                elapsed_ms=0,
            )

    def _gotify_ping(self, args: Dict[str, Any]) -> ToolResult:
        """
        Send a test notification via Gotify API.

        This tool sends a test message to verify Gotify connectivity
        and configuration. It handles HTTP requests and network failures
        gracefully.
        """
        try:
            # Get Gotify configuration from environment
            gotify_url = os.environ.get("GOTIFY_URL", "")
            gotify_token = os.environ.get("GOTIFY_TOKEN", "")

            if not gotify_url:
                return ToolResult(
                    success=False,
                    need_confirm=False,
                    summary="Gotify URL not configured - set GOTIFY_URL environment variable",
                    data={"error": "missing_url"},
                    stdout="",
                    stderr="GOTIFY_URL environment variable not set",
                    exit_code=1,
                    elapsed_ms=0,
                )

            if not gotify_token:
                return ToolResult(
                    success=False,
                    need_confirm=False,
                    summary="Gotify token not configured - set GOTIFY_TOKEN environment variable",
                    data={"error": "missing_token"},
                    stdout="",
                    stderr="GOTIFY_TOKEN environment variable not set",
                    exit_code=1,
                    elapsed_ms=0,
                )

            # Get optional message parameters
            message = args.get("message", "Test notification from Burly MCP")
            title = args.get("title", "Burly MCP Test")
            priority = args.get("priority", 3)  # Default to normal priority

            # Validate priority range (Gotify uses 0-10)
            if not isinstance(priority, int) or priority < 0 or priority > 10:
                priority = 3

            # Construct Gotify API URL
            api_url = f"{gotify_url.rstrip('/')}/message"

            # Prepare the message payload
            payload = {"message": message, "title": title, "priority": priority}

            # Prepare the HTTP request
            data = json.dumps(payload).encode("utf-8")

            req = urllib.request.Request(
                api_url,
                data=data,
                headers={
                    "Content-Type": "application/json",
                    "X-Gotify-Key": gotify_token,
                },
                method="POST",
            )

            # Send the request with timeout
            try:
                with urllib.request.urlopen(req, timeout=10) as response:
                    response_data = response.read().decode("utf-8")
                    status_code = response.getcode()

                    if status_code == 200:
                        # Parse response to get message ID
                        try:
                            response_json = json.loads(response_data)
                            message_id = response_json.get("id")
                        except json.JSONDecodeError:
                            message_id = None

                        return ToolResult(
                            success=True,
                            need_confirm=False,
                            summary=f"Gotify notification sent successfully (priority {priority})",
                            data={
                                "message_id": message_id,
                                "title": title,
                                "message": message,
                                "priority": priority,
                                "url": gotify_url,
                            },
                            stdout=f"Notification sent: '{title}' with priority {priority}",
                            stderr="",
                            exit_code=0,
                            elapsed_ms=0,
                        )
                    else:
                        return ToolResult(
                            success=False,
                            need_confirm=False,
                            summary=f"Gotify API returned status {status_code}",
                            data={
                                "status_code": status_code,
                                "response": response_data,
                            },
                            stdout="",
                            stderr=f"HTTP {status_code}: {response_data}",
                            exit_code=1,
                            elapsed_ms=0,
                        )

            except urllib.error.HTTPError as e:
                error_msg = f"HTTP {e.code}: {e.reason}"
                try:
                    error_body = e.read().decode("utf-8")
                    if error_body:
                        error_msg += f" - {error_body}"
                except (UnicodeDecodeError, OSError, AttributeError):
                    # Silently handle decode errors without exposing internals
                    pass

                if e.code == 401:
                    summary = "Gotify authentication failed - check GOTIFY_TOKEN"
                elif e.code == 404:
                    summary = "Gotify API endpoint not found - check GOTIFY_URL"
                else:
                    summary = f"Gotify API error: {error_msg}"

                return ToolResult(
                    success=False,
                    need_confirm=False,
                    summary=summary,
                    data={"http_error": e.code, "error": error_msg},
                    stdout="",
                    stderr=error_msg,
                    exit_code=1,
                    elapsed_ms=0,
                )

            except urllib.error.URLError as e:
                if "timeout" in str(e.reason).lower():
                    summary = "Gotify request timed out - check network connectivity"
                else:
                    summary = f"Network error connecting to Gotify: {e.reason}"

                return ToolResult(
                    success=False,
                    need_confirm=False,
                    summary=summary,
                    data={"network_error": str(e.reason)},
                    stdout="",
                    stderr=str(e.reason),
                    exit_code=1,
                    elapsed_ms=0,
                )

        except Exception as e:
            return ToolResult(
                success=False,
                need_confirm=False,
                summary=f"Unexpected error sending Gotify notification: {str(e)}",
                data={"error": str(e)},
                stdout="",
                stderr=str(e),
                exit_code=1,
                elapsed_ms=0,
            )
