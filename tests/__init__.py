"""
Test Suite for Burly MCP Server

This package contains comprehensive tests for the Burly MCP server,
including unit tests, integration tests, and security tests.

Test Structure:
- test_policy.py: Policy engine and validation tests
- test_tools.py: Tool execution and registry tests
- test_audit.py: Audit logging system tests
- test_notifications.py: Gotify notification tests
- test_security.py: Security constraint and validation tests
- test_integration.py: End-to-end MCP protocol tests

Running Tests:
    pytest                    # Run all tests
    pytest -v                 # Verbose output
    pytest --cov=server       # With coverage report
    pytest tests/test_policy.py  # Run specific test file

Test Configuration:
Tests use pytest with coverage reporting and are configured
in pyproject.toml with appropriate markers and options.
"""

__version__ = "0.1.0"