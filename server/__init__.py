"""
Burly MCP Server Package

This package implements a secure Model Context Protocol (MCP) server that provides
policy-driven access to system operations. The MCP protocol enables AI assistants
to safely execute whitelisted system tasks through a standardized interface.

Key Components:
- main.py: Entry point and MCP protocol handler
- policy.py: Policy engine for security and validation
- tools.py: Tool registry and execution framework
- audit.py: Audit logging and monitoring
- notifications.py: Gotify integration for alerts

The server communicates via stdin/stdout using JSON messages according to the
MCP specification, making it suitable for integration with AI assistants like
Open WebUI.
"""

__version__ = "0.1.0"
__author__ = "Burly MCP Contributors"
