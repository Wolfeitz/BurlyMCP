"""
Mutating Operation Confirmation System

This module implements the confirmation requirement system for mutating
operations in BurlyMCP. It ensures that operations that modify system
state require explicit confirmation before execution.

Key Features:
- Validation of _confirm requirement for mutating tools
- Structured "confirmation required" responses
- Helpful error messages explaining confirmation requirement
- Integration with tool registry for automatic enforcement

The confirmation system prevents accidental execution of mutating
operations while providing clear guidance on how to proceed.
"""

import logging
from typing import Any, Dict

logger = logging.getLogger(__name__)


def validate_mutating_operation(args: Dict[str, Any]) -> bool:
    """
    Validate that mutating operations have explicit confirmation.
    
    Checks for the presence of _confirm: true in the tool arguments
    to ensure the user has explicitly confirmed the mutating operation.
    
    Args:
        args: Tool arguments dictionary
        
    Returns:
        True if confirmation is present and valid, False otherwise
    """
    confirm_value = args.get("_confirm", False)
    
    # Accept various truthy values for confirmation
    if isinstance(confirm_value, bool):
        return confirm_value
    elif isinstance(confirm_value, str):
        return confirm_value.lower() in ["true", "1", "yes", "y"]
    elif isinstance(confirm_value, int):
        return confirm_value == 1
    else:
        return False


def require_confirmation_response(tool_name: str, operation_description: str = None) -> Dict[str, Any]:
    """
    Generate structured "confirmation required" response for mutating operations.
    
    Creates a standardized MCP response that indicates confirmation is required
    and provides clear instructions on how to proceed.
    
    Args:
        tool_name: Name of the tool requiring confirmation
        operation_description: Optional description of what the operation will do
        
    Returns:
        MCP response dictionary with confirmation requirement information
    """
    if operation_description is None:
        operation_description = f"execute {tool_name}"
    
    return {
        "ok": False,
        "need_confirm": True,
        "summary": f"Confirmation required for {tool_name}",
        "error": "This is a mutating operation and requires _confirm: true",
        "data": {
            "tool": tool_name,
            "operation": operation_description,
            "required_arg": "_confirm",
            "required_value": True,
            "suggestion": f"Add '_confirm': true to {tool_name} arguments to proceed",
            "example": {
                "method": "call_tool",
                "name": tool_name,
                "args": {
                    "_confirm": True,
                    "...": "other arguments"
                }
            }
        },
        "metrics": {"elapsed_ms": 0, "exit_code": 1}
    }


def get_mutating_tools() -> Dict[str, str]:
    """
    Get list of tools that require confirmation for mutating operations.
    
    Returns:
        Dictionary mapping tool names to their operation descriptions
    """
    return {
        "blog_publish_static": "publish blog content from staging to public directory",
        # Add other mutating tools here as they are identified
    }


def is_mutating_tool(tool_name: str) -> bool:
    """
    Check if a tool is considered a mutating operation.
    
    Args:
        tool_name: Name of the tool to check
        
    Returns:
        True if the tool is a mutating operation, False otherwise
    """
    return tool_name in get_mutating_tools()


def get_operation_description(tool_name: str) -> str:
    """
    Get human-readable description of what a mutating operation does.
    
    Args:
        tool_name: Name of the mutating tool
        
    Returns:
        Description of the operation the tool performs
    """
    mutating_tools = get_mutating_tools()
    return mutating_tools.get(tool_name, f"execute {tool_name}")


def validate_confirmation_for_tool(tool_name: str, args: Dict[str, Any]) -> Dict[str, Any] | None:
    """
    Validate confirmation requirement for a specific tool.
    
    Checks if the tool is mutating and if so, validates that proper
    confirmation has been provided. Returns None if validation passes,
    or a confirmation required response if validation fails.
    
    Args:
        tool_name: Name of the tool being executed
        args: Tool arguments dictionary
        
    Returns:
        None if validation passes, confirmation response dict if validation fails
    """
    if not is_mutating_tool(tool_name):
        # Non-mutating tools don't require confirmation
        return None
    
    if validate_mutating_operation(args):
        # Confirmation provided and valid
        logger.info(f"Confirmation validated for mutating tool: {tool_name}")
        return None
    
    # Confirmation required but not provided
    operation_description = get_operation_description(tool_name)
    logger.warning(f"Confirmation required for mutating tool {tool_name} but not provided")
    
    return require_confirmation_response(tool_name, operation_description)


def log_confirmation_attempt(tool_name: str, args: Dict[str, Any], confirmed: bool) -> None:
    """
    Log confirmation attempts for audit purposes.
    
    Args:
        tool_name: Name of the tool
        args: Tool arguments (sensitive values will be redacted)
        confirmed: Whether confirmation was provided
    """
    # Redact sensitive arguments for logging
    safe_args = {}
    for key, value in args.items():
        if key.lower() in ["password", "token", "secret", "key"]:
            safe_args[key] = "[REDACTED]"
        else:
            safe_args[key] = value
    
    logger.info(
        f"Confirmation attempt for {tool_name}: "
        f"confirmed={confirmed}, args_count={len(args)}, "
        f"has_confirm_arg={'_confirm' in args}"
    )


def enhance_tool_with_confirmation(tool_func):
    """
    Decorator to enhance tool functions with automatic confirmation checking.
    
    This decorator can be applied to tool functions to automatically
    check for confirmation requirements before execution.
    
    Args:
        tool_func: The tool function to enhance
        
    Returns:
        Enhanced tool function with confirmation checking
    """
    def wrapper(self, args: Dict[str, Any]):
        tool_name = tool_func.__name__.replace("_", "", 1)  # Remove leading underscore
        
        # Check confirmation requirement
        confirmation_response = validate_confirmation_for_tool(tool_name, args)
        if confirmation_response is not None:
            # Convert to ToolResult format
            from .registry import ToolResult
            return ToolResult(
                success=False,
                need_confirm=True,
                summary=confirmation_response["summary"],
                data=confirmation_response["data"],
                stdout="",
                stderr=confirmation_response["error"],
                exit_code=confirmation_response["metrics"]["exit_code"],
                elapsed_ms=confirmation_response["metrics"]["elapsed_ms"],
            )
        
        # Log successful confirmation
        log_confirmation_attempt(tool_name, args, True)
        
        # Proceed with original tool execution
        return tool_func(self, args)
    
    return wrapper