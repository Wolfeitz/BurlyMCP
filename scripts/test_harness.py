#!/usr/bin/env python3
"""
Burly MCP Test Harness

A command-line tool for testing and validating MCP operations against the Burly MCP server.
This harness provides comprehensive testing capabilities including:

- JSON input/output validation
- Demo scenarios with expected outputs
- Interactive testing mode
- Batch test execution
- Response validation against schemas

Usage:
    python scripts/test_harness.py --help
    python scripts/test_harness.py --demo
    python scripts/test_harness.py --interactive
    python scripts/test_harness.py --test-file scenarios.json
    python scripts/test_harness.py --validate-tool docker_ps
"""

import argparse
import json
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import jsonschema
from test_strategy import DependencyChecker, TestScenarioGenerator
from test_config import TestConfig


@dataclass
class TestScenario:
    """Represents a single test scenario for MCP operations."""
    
    name: str
    description: str
    request: Dict[str, Any]
    expected_response: Dict[str, Any]
    should_succeed: bool = True
    timeout: int = 30


@dataclass
class TestResult:
    """Represents the result of a test execution."""
    
    scenario_name: str
    success: bool
    actual_response: Optional[Dict[str, Any]]
    error_message: Optional[str]
    execution_time_ms: int
    validation_errors: List[str]


class MCPTestHarness:
    """
    Test harness for validating MCP server operations.
    
    Provides comprehensive testing capabilities for the Burly MCP server
    including request/response validation, demo scenarios, and batch testing.
    """
    
    def __init__(self, server_command: List[str] = None):
        """
        Initialize the test harness.
        
        Args:
            server_command: Command to start the MCP server (default: python -m server.main)
        """
        self.server_command = server_command or ["python", "-m", "server.main"]
        self.response_schema = self._get_response_schema()
        self.demo_scenarios = self._create_demo_scenarios()
        self.dependency_checker = None
        self.test_config = TestConfig()
    
    def _get_response_schema(self) -> Dict[str, Any]:
        """
        Get the JSON schema for validating MCP responses.
        
        Returns:
            JSON schema for MCP response validation
        """
        return {
            "type": "object",
            "properties": {
                "ok": {"type": "boolean"},
                "summary": {"type": "string"},
                "need_confirm": {"type": "boolean"},
                "data": {"type": ["object", "null"]},
                "stdout": {"type": "string"},
                "stderr": {"type": "string"},
                "error": {"type": ["string", "null"]},
                "metrics": {
                    "type": "object",
                    "properties": {
                        "elapsed_ms": {"type": "number"},
                        "exit_code": {"type": "number"}
                    },
                    "required": ["elapsed_ms", "exit_code"]
                }
            },
            "required": ["ok", "summary", "metrics"],
            "additionalProperties": False
        }
    
    def _create_demo_scenarios(self) -> List[TestScenario]:
        """
        Create comprehensive demo scenarios for testing.
        
        Returns:
            List of test scenarios covering all major functionality
        """
        scenarios = [
            # Basic list_tools operation
            TestScenario(
                name="list_tools_basic",
                description="Test basic list_tools operation",
                request={"method": "list_tools"},
                expected_response={
                    "ok": True,
                    "summary": "Available tools: 5 tools found",
                    "data": {
                        "tools": [
                            {
                                "name": "docker_ps",
                                "description": "List Docker containers with status information"
                            }
                        ]
                    }
                }
            ),
            
            # Docker container listing
            TestScenario(
                name="docker_ps_success",
                description="Test Docker container listing",
                request={
                    "method": "call_tool",
                    "name": "docker_ps",
                    "args": {}
                },
                expected_response={
                    "ok": True,
                    "summary": "Found"  # Flexible match for "Found X running containers"
                }
            ),
            
            # Disk space monitoring
            TestScenario(
                name="disk_space_success",
                description="Test disk space monitoring",
                request={
                    "method": "call_tool",
                    "name": "disk_space",
                    "args": {}
                },
                expected_response={
                    "ok": True,
                    "summary": "Found"  # Flexible match for "Found X filesystems"
                }
            ),
            
            # Blog validation with valid file
            TestScenario(
                name="blog_validate_success",
                description="Test blog Markdown validation with valid file",
                request={
                    "method": "call_tool",
                    "name": "blog_stage_markdown",
                    "args": {"file_path": "test-post.md"}
                },
                expected_response={
                    "ok": True,
                    "summary": "Blog post validation passed"
                }
            ),
            
            # Blog validation with invalid path (security test)
            TestScenario(
                name="blog_validate_path_traversal",
                description="Test path traversal prevention in blog validation",
                request={
                    "method": "call_tool",
                    "name": "blog_stage_markdown",
                    "args": {"file_path": "../../../etc/passwd"}
                },
                expected_response={
                    "ok": False,
                    "summary": "Path traversal detected - file must be within staging directory"
                },
                should_succeed=False
            ),
            
            # Blog publishing without confirmation
            TestScenario(
                name="blog_publish_no_confirm",
                description="Test blog publishing without confirmation",
                request={
                    "method": "call_tool",
                    "name": "blog_publish_static",
                    "args": {"source_files": ["test-post.md"]}
                },
                expected_response={
                    "ok": False,  # Actually fails because confirmation is required
                    "summary": "Blog publishing requires confirmation"
                }
            ),
            
            # Blog publishing with confirmation
            TestScenario(
                name="blog_publish_with_confirm",
                description="Test blog publishing with confirmation",
                request={
                    "method": "call_tool",
                    "name": "blog_publish_static",
                    "args": {
                        "source_files": ["test-post.md"],
                        "_confirm": True
                    }
                },
                expected_response={
                    "ok": True,
                    "summary": "Successfully published"
                }
            ),
            
            # Gotify configuration validation test
            TestScenario(
                name="gotify_ping_no_config",
                description="Test Gotify error handling when not configured",
                request={
                    "method": "call_tool",
                    "name": "gotify_ping",
                    "args": {"message": "Test notification from MCP harness"}
                },
                expected_response={
                    "ok": False,
                    "summary": "Gotify URL not configured - set GOTIFY_URL environment variable"
                },
                should_succeed=False
            ),
            

            
            # Invalid tool name
            TestScenario(
                name="invalid_tool_name",
                description="Test handling of invalid tool name",
                request={
                    "method": "call_tool",
                    "name": "nonexistent_tool",
                    "args": {}
                },
                expected_response={
                    "ok": False,
                    "summary": "Unknown tool"
                },
                should_succeed=False
            ),
            
            # Invalid method
            TestScenario(
                name="invalid_method",
                description="Test handling of invalid MCP method",
                request={
                    "method": "invalid_method"
                },
                expected_response={
                    "ok": False,
                    "summary": "Request parsing failed"
                },
                should_succeed=False
            ),
            
            # Malformed JSON (will be tested separately)
            TestScenario(
                name="malformed_json",
                description="Test handling of malformed JSON input",
                request={"method": "list_tools"},  # Will be corrupted during test
                expected_response={
                    "ok": False,
                    "summary": "Request parsing failed"
                },
                should_succeed=False
            )
        ]
        
        return scenarios
    
    def execute_mcp_request(self, request: Dict[str, Any], timeout: int = 30) -> Tuple[bool, Dict[str, Any], str]:
        """
        Execute an MCP request against the server.
        
        Args:
            request: MCP request dictionary
            timeout: Timeout in seconds
            
        Returns:
            Tuple of (success, response_dict, error_message)
        """
        try:
            # Start the MCP server process
            process = subprocess.Popen(
                self.server_command,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                cwd=Path(__file__).parent.parent
            )
            
            # Send the request
            request_json = json.dumps(request) + "\n"
            
            try:
                stdout, stderr = process.communicate(
                    input=request_json,
                    timeout=timeout
                )
            except subprocess.TimeoutExpired:
                process.kill()
                return False, {}, f"Request timed out after {timeout} seconds"
            
            # Parse the response
            if stdout.strip():
                try:
                    response = json.loads(stdout.strip())
                    return True, response, ""
                except json.JSONDecodeError as e:
                    return False, {}, f"Invalid JSON response: {e}\nStdout: {stdout}\nStderr: {stderr}"
            else:
                return False, {}, f"No response received\nStderr: {stderr}"
                
        except Exception as e:
            return False, {}, f"Execution error: {e}"
    
    def validate_response(self, response: Dict[str, Any]) -> List[str]:
        """
        Validate an MCP response against the expected schema.
        
        Args:
            response: Response dictionary to validate
            
        Returns:
            List of validation error messages (empty if valid)
        """
        errors = []
        
        try:
            jsonschema.validate(response, self.response_schema)
        except jsonschema.ValidationError as e:
            errors.append(f"Schema validation failed: {e.message}")
        except Exception as e:
            errors.append(f"Validation error: {e}")
        
        # Additional semantic validation
        if response.get("ok") is False and not response.get("error"):
            errors.append("Failed response should include error message")
        
        # Note: Confirmation requests can have ok=true (need user confirmation) 
        # or ok=false (validation failed before confirmation stage)
        
        return errors
    
    def run_scenario(self, scenario: TestScenario) -> TestResult:
        """
        Run a single test scenario.
        
        Args:
            scenario: Test scenario to execute
            
        Returns:
            TestResult with execution details
        """
        print(f"Running scenario: {scenario.name}")
        print(f"Description: {scenario.description}")
        
        start_time = time.time()
        
        # Handle special case for malformed JSON test
        if scenario.name == "malformed_json":
            success, response, error = self._test_malformed_json()
        else:
            success, response, error = self.execute_mcp_request(scenario.request, scenario.timeout)
        
        execution_time = int((time.time() - start_time) * 1000)
        
        # Validate response format
        validation_errors = []
        if success and response:
            validation_errors = self.validate_response(response)
        
        # Check if result matches expectation
        test_success = True
        
        # First check if we got a response at all
        if not success and scenario.should_succeed:
            test_success = False
        elif success and response:
            # Check specific expected fields with flexible matching
            for key, expected_value in scenario.expected_response.items():
                if key == "ok":
                    # Strict check for ok field
                    if response.get("ok") != expected_value:
                        validation_errors.append(f"Expected ok={expected_value}, got ok={response.get('ok')}")
                        test_success = False
                elif key == "summary":
                    # Flexible check for summary - allow partial matches
                    actual_summary = response.get("summary", "")
                    if expected_value.lower() not in actual_summary.lower():
                        validation_errors.append(f"Expected summary to contain '{expected_value}', got '{actual_summary}'")
                        test_success = False
                elif key == "data" and isinstance(expected_value, dict):
                    # For data field, check if expected keys exist
                    if "tools" in expected_value and "tools" in response.get("data", {}):
                        if len(response["data"]["tools"]) == 0:
                            validation_errors.append("Expected tools list to be non-empty")
                            test_success = False
                elif key not in response:
                    validation_errors.append(f"Missing expected field: {key}")
                    test_success = False
            
            # Additional check: if should_succeed=False, verify that ok=False
            if not scenario.should_succeed and response.get("ok") is not False:
                validation_errors.append(f"Expected operation to fail (ok=false) but got ok={response.get('ok')}")
                test_success = False
        
        return TestResult(
            scenario_name=scenario.name,
            success=test_success,
            actual_response=response if success else None,
            error_message=error if not success else None,
            execution_time_ms=execution_time,
            validation_errors=validation_errors
        )
    
    def _test_malformed_json(self) -> Tuple[bool, Dict[str, Any], str]:
        """
        Test malformed JSON handling by sending invalid JSON.
        
        Returns:
            Tuple of (success, response_dict, error_message)
        """
        try:
            process = subprocess.Popen(
                self.server_command,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                cwd=Path(__file__).parent.parent
            )
            
            # Send malformed JSON
            malformed_json = '{"method": "list_tools", "invalid": }\n'
            
            try:
                stdout, stderr = process.communicate(input=malformed_json, timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()
                return False, {}, "Malformed JSON test timed out"
            
            if stdout.strip():
                try:
                    response = json.loads(stdout.strip())
                    return True, response, ""
                except json.JSONDecodeError:
                    return False, {}, f"Server returned invalid JSON for malformed input\nStdout: {stdout}"
            else:
                return False, {}, f"No response to malformed JSON\nStderr: {stderr}"
                
        except Exception as e:
            return False, {}, f"Malformed JSON test error: {e}"
    
    def run_adaptive_tests(self) -> List[TestResult]:
        """
        Run adaptive tests based on available dependencies.
        
        This is the CORRECT way to test configurable dependencies:
        - Test actual functionality when dependencies are available
        - Test error handling when dependencies are not available  
        - Always test input validation and security
        
        Returns:
            List of test results
        """
        print("=" * 60)
        print("BURLY MCP ADAPTIVE TESTING")
        print("=" * 60)
        print()
        
        # Check what dependencies are available
        checker = DependencyChecker()
        dependencies = checker.check_all()
        
        print("Dependency Analysis:")
        for name, dep in dependencies.items():
            status = "✅ Available" if dep.available else "❌ Unavailable"
            print(f"  {name}: {status}")
            if dep.error:
                print(f"    → Will test error handling for {name}")
            else:
                print(f"    → Will test integration for {name}")
        print()
        
        # Generate appropriate test scenarios
        generator = TestScenarioGenerator(dependencies)
        scenario_groups = generator.generate_all_scenarios()
        
        # Convert to TestScenario objects and run
        results = []
        
        for group_name, scenarios in scenario_groups.items():
            print(f"--- {group_name.upper()} TESTS ---")
            
            for scenario_data in scenarios:
                # Convert expected format to match TestScenario
                expected_response = {
                    "ok": scenario_data["expected"]["ok"],
                    "summary": scenario_data["expected"]["summary_contains"]
                }
                
                scenario = TestScenario(
                    name=scenario_data["name"],
                    description=scenario_data["description"],
                    request=scenario_data["request"],
                    expected_response=expected_response,
                    should_succeed=scenario_data["expected"]["ok"]
                )
                
                result = self.run_scenario(scenario)
                results.append(result)
                
                # Print result with category
                status = "✅ PASS" if result.success else "❌ FAIL"
                category = scenario_data["category"]
                print(f"  {status} [{category}] {scenario.name} ({result.execution_time_ms}ms)")
                
                if result.validation_errors:
                    for error in result.validation_errors:
                        print(f"    ⚠️  {error}")
            
            print()
        
        return results

    def run_demo_scenarios(self, with_mocks: bool = False) -> List[TestResult]:
        """
        Run all demo scenarios.
        
        Args:
            with_mocks: Whether to start mock services for full functionality testing
        
        Returns:
            List of test results
        """
        print("=" * 60)
        print("BURLY MCP TEST HARNESS - DEMO SCENARIOS")
        if with_mocks:
            print("(WITH MOCK SERVICES FOR FULL FUNCTIONALITY TESTING)")
        print("=" * 60)
        print()
        
        mock_server = None
        
        if with_mocks:
            # Start mock Gotify server
            try:
                from mock_gotify_server import MockGotifyServer
                mock_server = MockGotifyServer()  # Auto-select port
                mock_server.start()
                
                # Update environment to point to mock server
                import os
                os.environ["GOTIFY_URL"] = mock_server.get_url()
                os.environ["GOTIFY_TOKEN"] = "test-token-12345"
                
                print(f"✅ Mock Gotify server started at {mock_server.get_url()}")
            except Exception as e:
                print(f"⚠️  Failed to start mock Gotify server: {e}")
                print("   Gotify tests will show configuration errors")
        
        try:
            results = []
            
            for scenario in self.demo_scenarios:
                print("-" * 40)
                result = self.run_scenario(scenario)
                results.append(result)
                
                # Print result summary
                status = "✅ PASS" if result.success else "❌ FAIL"
                print(f"Result: {status} ({result.execution_time_ms}ms)")
                
                if result.validation_errors:
                    print("Validation errors:")
                    for error in result.validation_errors:
                        print(f"  - {error}")
                
                if result.error_message:
                    print(f"Error: {result.error_message}")
                
                print()
            
            return results
            
        finally:
            # Clean up mock server
            if mock_server:
                mock_server.stop()
                print("🛑 Mock Gotify server stopped")
    
    def run_interactive_mode(self):
        """Run interactive testing mode."""
        print("=" * 60)
        print("BURLY MCP TEST HARNESS - INTERACTIVE MODE")
        print("=" * 60)
        print()
        print("Enter MCP requests as JSON (one per line)")
        print("Type 'quit' to exit, 'help' for available commands")
        print()
        
        while True:
            try:
                user_input = input("mcp> ").strip()
                
                if user_input.lower() in ['quit', 'exit', 'q']:
                    break
                elif user_input.lower() == 'help':
                    self._print_interactive_help()
                    continue
                elif user_input.lower() == 'demo':
                    self._run_quick_demo()
                    continue
                elif not user_input:
                    continue
                
                # Parse and execute the request
                try:
                    request = json.loads(user_input)
                except json.JSONDecodeError as e:
                    print(f"❌ Invalid JSON: {e}")
                    continue
                
                print(f"Executing: {request}")
                success, response, error = self.execute_mcp_request(request)
                
                if success:
                    validation_errors = self.validate_response(response)
                    print("✅ Response received:")
                    print(json.dumps(response, indent=2))
                    
                    if validation_errors:
                        print("⚠️  Validation warnings:")
                        for error in validation_errors:
                            print(f"  - {error}")
                else:
                    print(f"❌ Request failed: {error}")
                
                print()
                
            except KeyboardInterrupt:
                print("\nExiting interactive mode...")
                break
            except Exception as e:
                print(f"❌ Unexpected error: {e}")
    
    def _print_interactive_help(self):
        """Print help for interactive mode."""
        print()
        print("Available commands:")
        print("  help     - Show this help message")
        print("  demo     - Run a quick demo")
        print("  quit     - Exit interactive mode")
        print()
        print("Example MCP requests:")
        print('  {"method": "list_tools"}')
        print('  {"method": "call_tool", "name": "docker_ps", "args": {}}')
        print('  {"method": "call_tool", "name": "disk_space", "args": {}}')
        print()
    
    def _run_quick_demo(self):
        """Run a quick demo in interactive mode."""
        print("Running quick demo...")
        
        demo_requests = [
            {"method": "list_tools"},
            {"method": "call_tool", "name": "docker_ps", "args": {}},
            {"method": "call_tool", "name": "disk_space", "args": {}}
        ]
        
        for request in demo_requests:
            print(f"\n> {json.dumps(request)}")
            success, response, error = self.execute_mcp_request(request)
            
            if success:
                print(f"✅ {response.get('summary', 'Success')}")
            else:
                print(f"❌ {error}")
    
    def generate_test_report(self, results: List[TestResult]) -> str:
        """
        Generate a comprehensive test report.
        
        Args:
            results: List of test results
            
        Returns:
            Formatted test report string
        """
        total_tests = len(results)
        passed_tests = sum(1 for r in results if r.success)
        failed_tests = total_tests - passed_tests
        
        report = []
        report.append("=" * 60)
        report.append("BURLY MCP TEST HARNESS - FINAL REPORT")
        report.append("=" * 60)
        report.append("")
        report.append(f"Total Tests: {total_tests}")
        report.append(f"Passed: {passed_tests} ✅")
        report.append(f"Failed: {failed_tests} ❌")
        report.append(f"Success Rate: {(passed_tests/total_tests)*100:.1f}%")
        report.append("")
        
        if failed_tests > 0:
            report.append("FAILED TESTS:")
            report.append("-" * 20)
            for result in results:
                if not result.success:
                    report.append(f"❌ {result.scenario_name}")
                    if result.error_message:
                        report.append(f"   Error: {result.error_message}")
                    for error in result.validation_errors:
                        report.append(f"   Validation: {error}")
            report.append("")
        
        report.append("EXECUTION SUMMARY:")
        report.append("-" * 20)
        for result in results:
            status = "✅" if result.success else "❌"
            report.append(f"{status} {result.scenario_name} ({result.execution_time_ms}ms)")
        
        return "\n".join(report)
    
    def validate_tool_schema(self, tool_name: str) -> bool:
        """
        Validate a specific tool's schema and functionality.
        
        Args:
            tool_name: Name of the tool to validate
            
        Returns:
            True if validation passes, False otherwise
        """
        print(f"Validating tool: {tool_name}")
        
        # First, check if tool exists in list_tools
        success, response, error = self.execute_mcp_request({"method": "list_tools"})
        
        if not success:
            print(f"❌ Failed to get tool list: {error}")
            return False
        
        tools = response.get("data", {}).get("tools", [])
        tool_found = any(tool.get("name") == tool_name for tool in tools)
        
        if not tool_found:
            print(f"❌ Tool '{tool_name}' not found in available tools")
            available_tools = [tool.get("name") for tool in tools]
            print(f"Available tools: {available_tools}")
            return False
        
        print(f"✅ Tool '{tool_name}' found in tool list")
        
        # Test basic tool execution
        success, response, error = self.execute_mcp_request({
            "method": "call_tool",
            "name": tool_name,
            "args": {}
        })
        
        if success:
            validation_errors = self.validate_response(response)
            if validation_errors:
                print("⚠️  Response validation issues:")
                for error in validation_errors:
                    print(f"  - {error}")
                return False
            else:
                print(f"✅ Tool '{tool_name}' executed successfully")
                return True
        else:
            print(f"❌ Tool execution failed: {error}")
            return False


def main():
    """Main entry point for the test harness."""
    parser = argparse.ArgumentParser(
        description="Burly MCP Test Harness - Validate MCP server operations",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s --demo                    # Run demo scenarios
  %(prog)s --interactive             # Interactive testing mode
  %(prog)s --validate-tool docker_ps # Validate specific tool
  %(prog)s --server-cmd "docker run burly-mcp"  # Custom server command
        """
    )
    
    parser.add_argument(
        "--demo",
        action="store_true",
        help="Run comprehensive demo scenarios"
    )
    
    parser.add_argument(
        "--full-test",
        action="store_true",
        help="Run adaptive tests based on available dependencies (RECOMMENDED)"
    )
    
    parser.add_argument(
        "--interactive",
        action="store_true", 
        help="Run in interactive testing mode"
    )
    
    parser.add_argument(
        "--validate-tool",
        metavar="TOOL_NAME",
        help="Validate a specific tool's functionality"
    )
    
    parser.add_argument(
        "--server-cmd",
        metavar="COMMAND",
        help="Custom command to start MCP server (default: python -m server.main)"
    )
    
    parser.add_argument(
        "--timeout",
        type=int,
        default=30,
        help="Default timeout for operations in seconds (default: 30)"
    )
    
    args = parser.parse_args()
    
    # Parse server command
    server_command = None
    if args.server_cmd:
        server_command = args.server_cmd.split()
    
    # Initialize test harness
    harness = MCPTestHarness(server_command=server_command)
    
    # Execute requested operation
    if args.demo:
        results = harness.run_demo_scenarios(with_mocks=False)
        print(harness.generate_test_report(results))
        
        # Exit with error code if any tests failed
        if any(not r.success for r in results):
            sys.exit(1)
            
    elif args.full_test:
        results = harness.run_adaptive_tests()
        print(harness.generate_test_report(results))
        
        # Exit with error code if any tests failed
        if any(not r.success for r in results):
            sys.exit(1)
            
    elif args.interactive:
        harness.run_interactive_mode()
        
    elif args.validate_tool:
        success = harness.validate_tool_schema(args.validate_tool)
        if not success:
            sys.exit(1)
            
    else:
        parser.print_help()
        print("\nNo operation specified. Use --demo, --interactive, or --validate-tool")
        sys.exit(1)


if __name__ == "__main__":
    main()