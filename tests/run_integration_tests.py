#!/usr/bin/env python3
"""
Integration test runner for Burly MCP.

This script provides a convenient way to run integration tests
with proper setup and configuration.
"""

import argparse
import os
import subprocess
import sys


def check_prerequisites():
    """Check if prerequisites for integration tests are available."""
    issues = []

    # Check Python modules
    try:
        import pytest
    except ImportError:
        issues.append("pytest not installed")

    try:
        import docker

        client = docker.from_env()
        client.ping()
    except Exception:
        issues.append("Docker not available or not running")

    try:
        import testcontainers
    except ImportError:
        issues.append("testcontainers not installed")

    try:
        import requests
    except ImportError:
        issues.append("requests not installed (needed for HTTP bridge testing)")

    # Check if Burly MCP is available
    try:
        result = subprocess.run(
            [sys.executable, "-c", "import burly_mcp.server.main"],
            capture_output=True,
            timeout=5,
        )
        if result.returncode != 0:
            issues.append("Burly MCP server module not available")
    except (subprocess.TimeoutExpired, FileNotFoundError):
        issues.append("Python or Burly MCP not available")

    return issues


def validate_test_execution_environment():
    """Validate that the test execution environment is properly set up."""
    issues = []
    
    # Check for HTTP bridge dependencies
    try:
        import fastapi
        import uvicorn
    except ImportError:
        issues.append("HTTP bridge dependencies not available (fastapi, uvicorn)")
    
    # Check for testcontainers
    try:
        import testcontainers
    except ImportError:
        issues.append("testcontainers not available for container testing")
    
    # Check for requests
    try:
        import requests
    except ImportError:
        issues.append("requests library not available for HTTP testing")
    
    return issues


def run_integration_tests(args):
    """Run integration tests with specified configuration."""
    # Validate environment for new test categories
    if args.only_http or args.include_container:
        env_issues = validate_test_execution_environment()
        if env_issues:
            print("Environment validation issues:")
            for issue in env_issues:
                print(f"  - {issue}")
            print("\nSome tests may be skipped due to missing dependencies.")
    
    # Base pytest command
    cmd = [
        sys.executable,
        "-m",
        "pytest",
        "tests/integration/",
        "-v",
        "--tb=short",
    ]

    # Add coverage if requested
    if args.coverage:
        cmd.extend(
            [
                "--cov=burly_mcp",
                "--cov-report=term-missing",
                "--cov-report=html:htmlcov/integration",
                "--cov-report=xml:coverage-integration.xml",
            ]
        )

    # Add markers based on arguments
    markers = []
    if not args.include_docker:
        markers.append("not docker")
    if not args.include_slow:
        markers.append("not slow")
    if args.only_mcp:
        markers.append("mcp")
    if args.only_http:
        markers.append("http")
    if args.include_container:
        markers.append("container")

    if markers:
        cmd.extend(["-m", " and ".join(markers)])

    # Add specific test file if specified
    if args.test_file:
        cmd = [c for c in cmd if c != "tests/integration/"]
        cmd.append(f"tests/integration/{args.test_file}")

    # Add specific test function if specified
    if args.test_function:
        if args.test_file:
            cmd[-1] += f"::{args.test_function}"
        else:
            cmd.append(f"-k {args.test_function}")

    # Add parallel execution if requested
    if args.parallel and args.parallel > 1:
        cmd.extend(["-n", str(args.parallel)])

    # Add timeout
    if args.timeout:
        cmd.extend(["--timeout", str(args.timeout)])

    # Set environment variables
    env = os.environ.copy()
    env["PYTHONPATH"] = "src"

    if args.verbose:
        print(f"Running command: {' '.join(cmd)}")
        print(f"Environment: PYTHONPATH={env.get('PYTHONPATH')}")

    # Run the tests
    try:
        result = subprocess.run(cmd, env=env)
        return result.returncode
    except KeyboardInterrupt:
        print("\nTests interrupted by user")
        return 130


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Run Burly MCP integration tests",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s                          # Run all integration tests
  %(prog)s --no-docker              # Skip Docker tests
  %(prog)s --no-slow                # Skip slow tests
  %(prog)s --only-mcp               # Run only MCP protocol tests
  %(prog)s --only-http              # Run only HTTP bridge tests
  %(prog)s --include-container      # Include container runtime tests
  %(prog)s --test-file test_docker_integration.py  # Run specific file
  %(prog)s --test-function test_container_lifecycle  # Run specific test
  %(prog)s --coverage               # Run with coverage reporting
  %(prog)s --parallel 4             # Run tests in parallel

Test Categories:
  unit         - Fast, isolated tests with mocks
  integration  - End-to-end tests with real services
  docker       - Tests requiring Docker daemon
  mcp          - MCP protocol functionality tests
  http         - HTTP bridge endpoint tests
  api          - HTTP API endpoint tests
  container    - Runtime container tests
  security     - Security validation tests
  slow         - Long-running tests
        """,
    )

    parser.add_argument(
        "--no-docker",
        dest="include_docker",
        action="store_false",
        help="Skip Docker-related tests",
    )
    parser.add_argument(
        "--no-slow",
        dest="include_slow",
        action="store_false",
        help="Skip slow-running tests",
    )
    parser.add_argument(
        "--only-mcp", action="store_true", help="Run only MCP protocol tests"
    )
    parser.add_argument(
        "--only-http", action="store_true", help="Run only HTTP bridge tests"
    )
    parser.add_argument(
        "--include-container", action="store_true", help="Include container runtime tests"
    )
    parser.add_argument(
        "--test-file",
        metavar="FILE",
        help="Run specific test file (e.g., test_docker_integration.py)",
    )
    parser.add_argument(
        "--test-function", metavar="FUNCTION", help="Run specific test function"
    )
    parser.add_argument(
        "--coverage", action="store_true", help="Generate coverage report"
    )
    parser.add_argument(
        "--parallel", type=int, metavar="N", help="Run tests in parallel with N workers"
    )
    parser.add_argument(
        "--timeout",
        type=int,
        metavar="SECONDS",
        default=300,
        help="Timeout for individual tests (default: 300s)",
    )
    parser.add_argument(
        "--check-only",
        action="store_true",
        help="Only check prerequisites, do not run tests",
    )
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose output")

    args = parser.parse_args()

    # Check prerequisites
    print("Checking prerequisites...")
    issues = check_prerequisites()

    if issues:
        print("Issues found:")
        for issue in issues:
            print(f"  - {issue}")

        if args.check_only:
            return 1

        print("\nSome tests may be skipped due to missing prerequisites.")
        response = input("Continue anyway? (y/N): ")
        if response.lower() not in ["y", "yes"]:
            return 1
    else:
        print("All prerequisites available.")

        if args.check_only:
            return 0

    # Run tests
    print("\nRunning integration tests...")
    return run_integration_tests(args)


if __name__ == "__main__":
    sys.exit(main())
