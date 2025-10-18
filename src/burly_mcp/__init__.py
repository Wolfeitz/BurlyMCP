"""
Burly MCP - Secure MCP server for system operations

This package provides a secure Model Context Protocol (MCP) server implementation
with comprehensive security features, audit logging, and policy enforcement.
"""

__version__ = "1.0.0"
__author__ = "Burly MCP Team"
__description__ = "Secure MCP server for system operations"

# Import main components for public API
from .server.main import main
from .tools import ToolRegistry
from .policy import PolicyLoader, SchemaValidator, PolicyToolRegistry
from .notifications import NotificationManager

# Define public API exports
__all__ = [
    "main",
    "ToolRegistry", 
    "PolicyLoader",
    "SchemaValidator",
    "PolicyToolRegistry",
    "NotificationManager",
    "__version__",
    "__author__",
    "__description__"
]