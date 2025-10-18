"""
Burly MCP Server Module

This module contains the core MCP protocol implementation and server components.
It provides the main entry point and protocol handling for the Burly MCP server.
"""

from .main import main
from .mcp import MCPProtocolHandler

__all__ = [
    "main",
    "MCPProtocolHandler",
]