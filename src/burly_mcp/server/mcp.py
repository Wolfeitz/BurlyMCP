"""
MCP Protocol Implementation

This module implements the Model Context Protocol (MCP) message handling,
including request parsing, response formatting, and the core protocol operations.

The MCP protocol uses JSON messages over stdin/stdout to enable AI assistants
to interact with external tools and services in a standardized way.
"""

import json
import logging
import sys
import time
from dataclasses import asdict, dataclass
from enum import Enum
from typing import Any, Dict, List, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from ..tools.registry import ToolRegistry

logger = logging.getLogger(__name__)


class MCPMethod(Enum):
    """Supported MCP methods."""

    LIST_TOOLS = "list_tools"
    CALL_TOOL = "call_tool"


@dataclass
class MCPRequest:
    """
    Represents an incoming MCP request.

    The MCP protocol expects JSON messages with a method field and optional
    parameters for tool calls.
    """

    method: str
    name: Optional[str] = None
    args: Optional[Dict[str, Any]] = None

    @classmethod
    def from_json(cls, json_data: Dict[str, Any]) -> "MCPRequest":
        """
        Parse an MCP request from JSON data.

        Args:
            json_data: Dictionary containing the parsed JSON request

        Returns:
            MCPRequest instance

        Raises:
            ValueError: If required fields are missing or invalid
        """
        method = json_data.get("method")
        if not method:
            raise ValueError("Missing required field: method")

        if method not in [m.value for m in MCPMethod]:
            raise ValueError(f"Unsupported method: {method}")

        return cls(
            method=method, name=json_data.get("name"), args=json_data.get("args", {})
        )


@dataclass
class MCPResponse:
    """
    Represents an MCP response to be sent back to the client.

    Includes standard fields for success/failure, confirmation requirements,
    and execution metrics. This class implements the standardized response
    envelope system for consistent formatting across all operations.
    """

    ok: bool
    need_confirm: bool = False
    summary: str = ""
    data: Optional[Dict[str, Any]] = None
    stdout: str = ""
    stderr: str = ""
    metrics: Optional[Dict[str, Any]] = None
    error: Optional[str] = None

    def __post_init__(self) -> None:
        """
        Post-initialization processing to ensure response consistency.

        Validates response fields and applies standardized formatting rules.
        """
        # Ensure metrics always includes basic timing information
        if self.metrics is None:
            self.metrics = {}

        # Ensure elapsed_ms is always present
        if "elapsed_ms" not in self.metrics:
            self.metrics["elapsed_ms"] = 0

        # Ensure exit_code is present for completed operations
        if "exit_code" not in self.metrics:
            self.metrics["exit_code"] = 0 if self.ok else 1

        # Truncate long output if necessary (following design requirements)
        self._truncate_output()

        # Sanitize summary for consistency
        if not self.summary:
            self.summary = "Operation completed" if self.ok else "Operation failed"

    def _truncate_output(self, max_length: int = 10000) -> None:
        """
        Truncate stdout/stderr if they exceed maximum length.

        Args:
            max_length: Maximum allowed length for output fields
        """
        truncation_indicator = "\n[truncated: output too long]"

        if len(self.stdout) > max_length:
            self.stdout = (
                self.stdout[: max_length - len(truncation_indicator)]
                + truncation_indicator
            )
            if self.metrics is not None and "stdout_trunc" not in self.metrics:
                self.metrics["stdout_trunc"] = len(self.stdout)

        if len(self.stderr) > max_length:
            self.stderr = (
                self.stderr[: max_length - len(truncation_indicator)]
                + truncation_indicator
            )
            if self.metrics is not None and "stderr_trunc" not in self.metrics:
                self.metrics["stderr_trunc"] = len(self.stderr)

    def to_json(self) -> Dict[str, Any]:
        """
        Convert the response to a JSON-serializable dictionary.

        Implements the standardized response envelope format with
        consistent field ordering and optional field handling.

        Returns:
            Dictionary representation suitable for JSON serialization
        """
        # Core response envelope - always present
        result = {"ok": self.ok, "summary": self.summary}

        # Add confirmation requirement if needed
        if self.need_confirm:
            result["need_confirm"] = self.need_confirm

        # Add error information for failed operations
        if not self.ok and self.error:
            result["error"] = self.error

        # Add structured data if present
        if self.data is not None:
            result["data"] = self.data

        # Add command output if present
        if self.stdout:
            result["stdout"] = self.stdout

        if self.stderr:
            result["stderr"] = self.stderr

        # Always include metrics for monitoring
        if self.metrics:
            result["metrics"] = self.metrics

        return result

    @classmethod
    def create_error(
        cls,
        error_msg: str,
        summary: str = "Operation failed",
        exit_code: int = 1,
        elapsed_ms: int = 0,
        stderr: str = "",
    ) -> "MCPResponse":
        """
        Factory method for creating standardized error responses.

        Args:
            error_msg: Detailed error message
            summary: Brief error summary
            exit_code: Process exit code (default 1 for errors)
            elapsed_ms: Execution time in milliseconds
            stderr: Standard error output

        Returns:
            MCPResponse configured for error reporting
        """
        return cls(
            ok=False,
            summary=summary,
            error=error_msg,
            stderr=stderr,
            metrics={"elapsed_ms": elapsed_ms, "exit_code": exit_code},
        )

    @classmethod
    def create_success(
        cls,
        summary: str,
        data: Optional[Dict[str, Any]] = None,
        stdout: str = "",
        stderr: str = "",
        need_confirm: bool = False,
        elapsed_ms: int = 0,
    ) -> "MCPResponse":
        """
        Factory method for creating standardized success responses.

        Args:
            summary: Brief description of what was accomplished
            data: Optional structured data to return
            stdout: Standard output from command execution
            stderr: Standard error output (can be present even on success)
            need_confirm: Whether confirmation is required for the operation
            elapsed_ms: Execution time in milliseconds

        Returns:
            MCPResponse configured for success reporting
        """
        return cls(
            ok=True,
            summary=summary,
            data=data,
            stdout=stdout,
            stderr=stderr,
            need_confirm=need_confirm,
            metrics={"elapsed_ms": elapsed_ms, "exit_code": 0},
        )


class MCPProtocolHandler:
    """
    Handles MCP protocol communication via stdin/stdout.

    This class manages the JSON message parsing, request routing,
    and response formatting for the MCP protocol.
    """

    def __init__(self, tool_registry: Optional["ToolRegistry"] = None):
        """
        Initialize the MCP protocol handler.

        Args:
            tool_registry: ToolRegistry instance for executing tools
        """
        self.start_time = time.time()
        self.tool_registry = tool_registry

        # Security: Rate limiting to prevent DoS
        self._request_times: List[float] = []
        self._max_requests_per_minute = 60
        self._request_window = 60  # seconds

    def read_request(self) -> Optional[MCPRequest]:
        """
        Read and parse an MCP request from stdin.

        Returns:
            MCPRequest instance if successful, None if EOF or error

        Raises:
            ValueError: If the JSON is malformed or invalid
        """
        try:
            line = sys.stdin.readline()
            if not line:
                return None  # EOF

            line = line.strip()
            if not line:
                return None  # Empty line

            # Security: Limit input size to prevent DoS
            if len(line) > 1024 * 1024:  # 1MB limit
                raise ValueError("Request too large")

            json_data = json.loads(line)

            # Security: Limit JSON object complexity
            if self._count_json_nodes(json_data) > 1000:
                raise ValueError("Request too complex")

            return MCPRequest.from_json(json_data)

        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON: {e}")
        except Exception as e:
            raise ValueError(f"Failed to parse request: {e}")

    def _count_json_nodes(self, obj: Any, depth: int = 0) -> int:
        """
        Count JSON object nodes to prevent complexity attacks.

        Args:
            obj: JSON object to analyze
            depth: Current nesting depth

        Returns:
            Total number of nodes in the JSON structure

        Raises:
            ValueError: If structure is too complex
        """
        if depth > 20:  # Max nesting depth
            raise ValueError("JSON structure too deeply nested")

        count = 1
        if isinstance(obj, dict):
            if len(obj) > 100:  # Max properties per object
                raise ValueError("JSON object too complex")
            for value in obj.values():
                count += self._count_json_nodes(value, depth + 1)
        elif isinstance(obj, list):
            if len(obj) > 50:  # Max array items
                raise ValueError("JSON array too large")
            for item in obj:
                count += self._count_json_nodes(item, depth + 1)

        return count

    def write_response(self, response: MCPResponse) -> None:
        """
        Write an MCP response to stdout using the standardized envelope format.

        Implements comprehensive error handling to ensure a response is always
        sent, even if the primary response serialization fails.

        Args:
            response: The MCPResponse to send
        """
        try:
            json_str = json.dumps(response.to_json(), separators=(",", ":"))
            print(json_str, flush=True)
        except Exception as e:
            # Fallback error response if serialization fails
            # Use minimal structure to avoid further serialization issues
            fallback_response = MCPResponse.create_error(
                error_msg=f"Response serialization failed: {str(e)}",
                summary="Internal server error",
                elapsed_ms=int((time.time() - self.start_time) * 1000),
            )

            try:
                # Try to serialize the fallback response
                fallback_json = json.dumps(
                    fallback_response.to_json(), separators=(",", ":")
                )
                print(fallback_json, flush=True)
            except Exception:
                # Ultimate fallback - minimal JSON that should always work
                minimal_error = {
                    "ok": False,
                    "summary": "Critical serialization error",
                    "error": "Unable to serialize response",
                    "metrics": {"elapsed_ms": 0, "exit_code": 1},
                }
                print(json.dumps(minimal_error, separators=(",", ":")), flush=True)

    def create_error_response(
        self, error_msg: str, summary: str = "Error"
    ) -> MCPResponse:
        """
        Create a standardized error response using the response envelope system.

        Args:
            error_msg: Detailed error message
            summary: Brief error summary

        Returns:
            MCPResponse with error information and metrics
        """
        # Security: Sanitize error messages to prevent information disclosure
        sanitized_error = self._sanitize_error_message(error_msg)

        return MCPResponse.create_error(
            error_msg=sanitized_error,
            summary=summary,
            elapsed_ms=int((time.time() - self.start_time) * 1000),
        )

    def _sanitize_error_message(self, error_msg: str) -> str:
        """
        Sanitize error messages to prevent information disclosure.

        Args:
            error_msg: Original error message

        Returns:
            Sanitized error message safe for client consumption
        """
        # Remove potentially sensitive path information
        import re

        # Replace absolute paths with generic indicators
        error_msg = re.sub(r"/[a-zA-Z0-9_/.-]+", "[PATH]", error_msg)

        # Remove stack trace information
        if "Traceback" in error_msg or 'File "' in error_msg:
            return "Internal processing error"

        # Limit error message length
        if len(error_msg) > 200:
            return error_msg[:200] + "..."

        return error_msg

    def create_success_response(
        self,
        summary: str,
        data: Optional[Dict[str, Any]] = None,
        stdout: str = "",
        stderr: str = "",
        need_confirm: bool = False,
    ) -> MCPResponse:
        """
        Create a standardized success response using the response envelope system.

        Args:
            summary: Brief description of what was accomplished
            data: Optional structured data to return
            stdout: Command output if applicable
            stderr: Command error output if applicable
            need_confirm: Whether confirmation is required

        Returns:
            MCPResponse with success information and metrics
        """
        return MCPResponse.create_success(
            summary=summary,
            data=data,
            stdout=stdout,
            stderr=stderr,
            need_confirm=need_confirm,
            elapsed_ms=int((time.time() - self.start_time) * 1000),
        )

    def handle_request(self, request: MCPRequest) -> MCPResponse:
        """
        Handle an MCP request and return the appropriate response.

        Args:
            request: The parsed MCP request

        Returns:
            MCPResponse with the result
        """
        try:
            logger.debug(f"Handling MCP request: {request.method}")

            if request.method == MCPMethod.LIST_TOOLS.value:
                response = self._handle_list_tools()
                logger.debug(f"list_tools completed successfully")
                return response
            elif request.method == MCPMethod.CALL_TOOL.value:
                logger.debug(f"Calling tool: {request.name}")
                response = self._handle_call_tool(request)
                logger.debug(
                    f"Tool {request.name} completed with status: {'success' if response.ok else 'failure'}"
                )
                return response
            else:
                logger.warning(f"Unsupported MCP method: {request.method}")
                return self.create_error_response(
                    f"Unsupported method: {request.method}", "Method not supported"
                )
        except Exception as e:
            logger.error(f"Request handling failed: {e}", exc_info=True)
            return self.create_error_response(
                f"Request handling failed: {e}", "Internal server error"
            )

    def _handle_list_tools(self) -> MCPResponse:
        """
        Handle the list_tools MCP operation.

        Returns available tools with their descriptions and schemas.
        This method gets tool information from the tool registry to ensure
        consistency between available tools and their definitions.

        Returns:
            MCPResponse with tool definitions
        """
        if not self.tool_registry:
            return self.create_error_response(
                "Tool registry not initialized", "Server configuration error"
            )

        # Get tool definitions from the registry
        # This ensures consistency between what tools are available and what schemas are returned
        tools = []

        # Define tool schemas based on the actual available tools
        # These schemas match the policy definitions and tool implementations
        tool_schemas = {
            "docker_ps": {
                "name": "docker_ps",
                "description": "List Docker containers with status information",
                "inputSchema": {
                    "type": "object",
                    "properties": {},
                    "additionalProperties": False,
                },
            },
            "disk_space": {
                "name": "disk_space",
                "description": "Check filesystem disk space usage",
                "inputSchema": {
                    "type": "object",
                    "properties": {},
                    "additionalProperties": False,
                },
            },
            "blog_stage_markdown": {
                "name": "blog_stage_markdown",
                "description": "Validate Markdown file with YAML front-matter for blog staging",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "file_path": {
                            "type": "string",
                            "description": "Path to the Markdown file to validate",
                            "pattern": "^[a-zA-Z0-9._/-]+\\.md$",
                        }
                    },
                    "required": ["file_path"],
                    "additionalProperties": False,
                },
            },
            "blog_publish_static": {
                "name": "blog_publish_static",
                "description": "Publish blog content from staging to publish directory (requires confirmation)",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "source_files": {
                            "type": "array",
                            "items": {
                                "type": "string",
                                "pattern": "^[a-zA-Z0-9._/-]+\\.md$",
                            },
                            "minItems": 1,
                            "description": "List of source files to publish",
                        },
                        "_confirm": {
                            "type": "boolean",
                            "description": "Set to true to confirm the publishing operation",
                        },
                    },
                    "required": ["source_files"],
                    "additionalProperties": False,
                },
            },
            "gotify_ping": {
                "name": "gotify_ping",
                "description": "Send a test notification via Gotify API",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "message": {
                            "type": "string",
                            "description": "Optional custom message for the test notification",
                            "maxLength": 200,
                        }
                    },
                    "additionalProperties": False,
                },
            },
        }

        # Only include tools that are actually available in the registry
        for tool_name in self.tool_registry.tools.keys():
            if tool_name in tool_schemas:
                tools.append(tool_schemas[tool_name])
            else:
                # Fallback for tools not in our schema definitions
                tools.append(
                    {
                        "name": tool_name,
                        "description": f"Tool: {tool_name}",
                        "inputSchema": {"type": "object", "additionalProperties": True},
                    }
                )

        return self.create_success_response(
            summary=f"Available tools: {len(tools)} tools found", data={"tools": tools}
        )

    def _handle_call_tool(self, request: MCPRequest) -> MCPResponse:
        """
        Handle the call_tool MCP operation.

        Routes the tool call to the appropriate handler and implements
        the confirmation workflow for mutating operations.

        Args:
            request: The MCP request with tool name and arguments

        Returns:
            MCPResponse with tool execution results
        """
        if not request.name:
            return self.create_error_response(
                "Tool name is required for call_tool", "Missing tool name"
            )

        if not self.tool_registry:
            return self.create_error_response(
                "Tool registry not initialized", "Server configuration error"
            )

        # Execute the tool through the registry
        tool_result = self.tool_registry.execute_tool(request.name, request.args or {})

        # Convert ToolResult to MCPResponse using the standardized envelope system
        if tool_result.success:
            return MCPResponse.create_success(
                summary=tool_result.summary,
                data=tool_result.data,
                stdout=tool_result.stdout,
                stderr=tool_result.stderr,
                need_confirm=tool_result.need_confirm,
                elapsed_ms=tool_result.elapsed_ms,
            )
        else:
            # For failed operations, use the error response factory
            response = MCPResponse.create_error(
                error_msg=tool_result.stderr or "Tool execution failed",
                summary=tool_result.summary,
                exit_code=tool_result.exit_code,
                elapsed_ms=tool_result.elapsed_ms,
                stderr=tool_result.stderr,
            )

            # Add additional fields for failed tool operations
            response.need_confirm = tool_result.need_confirm
            response.data = tool_result.data
            response.stdout = tool_result.stdout

            return response

    def run_protocol_loop(self) -> None:
        """
        Run the main MCP protocol loop.

        Continuously reads requests from stdin, processes them, and writes
        responses to stdout until EOF or a critical error occurs.

        This method implements the core MCP server behavior with comprehensive
        error handling and graceful shutdown.
        """
        logger.info("Starting MCP protocol loop")

        try:
            while True:
                try:
                    # Security: Check rate limiting
                    if not self._check_rate_limit():
                        error_response = self.create_error_response(
                            "Rate limit exceeded", "Too many requests"
                        )
                        self.write_response(error_response)
                        continue

                    # Read and parse the next request
                    request = self.read_request()
                    if request is None:
                        # EOF reached - normal shutdown
                        logger.info("EOF received, shutting down protocol loop")
                        break

                    logger.debug(f"Processing request: {request.method}")

                    # Reset timing for this request
                    self.start_time = time.time()

                    # Handle the request and generate response
                    response = self.handle_request(request)

                    # Send the response
                    self.write_response(response)

                    logger.debug(
                        f"Request completed in {response.metrics.get('elapsed_ms', 0) if response.metrics else 0}ms"
                    )

                except ValueError as e:
                    # Request parsing or validation error
                    logger.warning(f"Request parsing error: {e}")
                    error_response = self.create_error_response(
                        str(e), "Request parsing failed"
                    )
                    self.write_response(error_response)

                except KeyboardInterrupt:
                    # Graceful shutdown on Ctrl+C
                    logger.info("Keyboard interrupt received, shutting down")
                    break

                except Exception as e:
                    # Unexpected error - log and continue
                    logger.error(
                        f"Unexpected error in protocol loop: {e}", exc_info=True
                    )
                    error_response = self.create_error_response(
                        f"Internal server error: {str(e)}", "Unexpected server error"
                    )
                    self.write_response(error_response)

        except Exception as e:
            # Critical error that prevents the loop from continuing
            logger.critical(f"Critical error in protocol loop: {e}", exc_info=True)

        finally:
            logger.info("MCP protocol loop terminated")

    def _check_rate_limit(self) -> bool:
        """
        Check if the current request is within rate limits.

        Returns:
            True if request is allowed, False if rate limited
        """
        current_time = time.time()

        # Remove old requests outside the window
        cutoff_time = current_time - self._request_window
        self._request_times = [t for t in self._request_times if t > cutoff_time]

        # Check if we're under the limit
        if len(self._request_times) >= self._max_requests_per_minute:
            return False

        # Add current request
        self._request_times.append(current_time)
        return True
