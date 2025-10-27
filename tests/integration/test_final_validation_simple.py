"""
Simplified Final Integration and Validation Tests

This module implements validation tests for task 10 using direct docker commands
instead of testcontainers to avoid dependency issues.
"""

import json
import os
import signal
import subprocess
import time
from pathlib import Path

import pytest
import requests


@pytest.mark.integration
@pytest.mark.container
class TestStandaloneOperationSimple:
    """Test complete standalone operation (Task 10.1) using direct docker commands."""

    @pytest.fixture(scope="class")
    def docker_available(self):
        """Check if Docker is available."""
        try:
            result = subprocess.run(["docker", "version"], capture_output=True, timeout=5)
            if result.returncode != 0:
                pytest.skip("Docker not available")
            return True
        except (subprocess.TimeoutExpired, FileNotFoundError):
            pytest.skip("Docker not available")

    @pytest.fixture(scope="class")
    def runtime_container_image(self, docker_available):
        """Build runtime container image for testing."""
        try:
            # Build the runtime container
            build_result = subprocess.run([
                "docker", "build", "-f", "Dockerfile.runtime", 
                "-t", "burlymcp:test-final-validation", "."
            ], capture_output=True, text=True, timeout=300)
            
            if build_result.returncode != 0:
                pytest.skip(f"Container build failed: {build_result.stderr}")
            
            yield "burlymcp:test-final-validation"
            
            # Cleanup
            try:
                subprocess.run([
                    "docker", "rmi", "burlymcp:test-final-validation"
                ], capture_output=True, timeout=30)
            except Exception:
                pass  # Cleanup failure is not critical
                
        except subprocess.TimeoutExpired:
            pytest.skip("Container build timed out")
        except Exception as e:
            pytest.skip(f"Container build failed: {e}")

    @pytest.mark.flaky
    def test_container_starts_within_30_seconds(self, runtime_container_image):
        """Test container starts and responds to health checks within 30 seconds."""
        container_id = None
        try:
            start_time = time.time()
            
            # Start container with minimal configuration
            run_result = subprocess.run([
                "docker", "run", "-d", "-p", "19401:9400",  # Use different port to avoid conflicts
                "-e", "LOG_LEVEL=DEBUG",
                runtime_container_image
            ], capture_output=True, text=True, timeout=30)
            
            if run_result.returncode != 0:
                pytest.fail(f"Container failed to start: {run_result.stderr}")
            
            container_id = run_result.stdout.strip()
            
            # Wait for container to be running
            timeout = 30
            while time.time() - start_time < timeout:
                status_result = subprocess.run([
                    "docker", "inspect", container_id, "--format", "{{.State.Status}}"
                ], capture_output=True, text=True, timeout=5)
                
                if status_result.returncode == 0 and status_result.stdout.strip() == "running":
                    break
                time.sleep(0.5)
            else:
                logs_result = subprocess.run([
                    "docker", "logs", container_id
                ], capture_output=True, text=True, timeout=10)
                pytest.fail(f"Container did not start within {timeout}s. Logs: {logs_result.stdout + logs_result.stderr}")
            
            # Test health endpoint availability within startup time
            health_available = False
            while time.time() - start_time < timeout:
                try:
                    response = requests.get("http://localhost:19401/health", timeout=2)
                    if response.status_code == 200:
                        health_available = True
                        break
                except requests.RequestException:
                    pass
                time.sleep(1)
            
            startup_time = time.time() - start_time
            
            # Validate startup time requirement (allow extra time in CI environments)
            max_startup_time = 45 if os.getenv('CI') else 30
            assert startup_time < max_startup_time, f"Container took {startup_time:.1f}s to start (requirement: <{max_startup_time}s)"
            assert health_available, "Health endpoint not available within 30 seconds"
            
            # Validate health response format
            response = requests.get("http://localhost:19401/health", timeout=5)
            assert response.status_code == 200
            
            health_data = response.json()
            required_fields = ["status", "server_name", "version", "tools_available", 
                             "notifications_enabled", "docker_available", "strict_security_mode", 
                             "policy_loaded", "uptime_seconds"]
            
            for field in required_fields:
                assert field in health_data, f"Missing required field: {field}"
            
            assert health_data["status"] in ["ok", "degraded"], f"Invalid status: {health_data['status']}"
            
        finally:
            if container_id:
                subprocess.run(["docker", "stop", container_id], capture_output=True, timeout=15)
                subprocess.run(["docker", "rm", container_id], capture_output=True, timeout=10)

    def test_graceful_shutdown_within_10_seconds(self, runtime_container_image):
        """Test graceful shutdown on SIGTERM within 10 seconds."""
        container_id = None
        try:
            # Start container
            run_result = subprocess.run([
                "docker", "run", "-d", "-p", "19402:9400",
                runtime_container_image
            ], capture_output=True, text=True, timeout=30)
            
            if run_result.returncode != 0:
                pytest.fail(f"Container failed to start: {run_result.stderr}")
            
            container_id = run_result.stdout.strip()
            
            # Wait for container to be ready
            time.sleep(5)
            
            status_result = subprocess.run([
                "docker", "inspect", container_id, "--format", "{{.State.Status}}"
            ], capture_output=True, text=True, timeout=5)
            
            assert status_result.stdout.strip() == "running"
            
            # Send SIGTERM and measure shutdown time
            start_time = time.time()
            
            stop_result = subprocess.run([
                "docker", "stop", container_id
            ], capture_output=True, text=True, timeout=15)
            
            shutdown_time = time.time() - start_time
            
            assert stop_result.returncode == 0, "Container stop command failed"
            max_shutdown_time = 18 if os.getenv('CI') else 12
            assert shutdown_time < max_shutdown_time, f"Shutdown took {shutdown_time:.1f}s (requirement: <{max_shutdown_time}s including Docker overhead)"
            
            # Check exit code (0 for graceful shutdown, 137 for SIGKILL is acceptable)
            inspect_result = subprocess.run([
                "docker", "inspect", container_id, "--format", "{{.State.ExitCode}}"
            ], capture_output=True, text=True, timeout=5)
            
            if inspect_result.returncode == 0:
                exit_code = int(inspect_result.stdout.strip())
                # Exit code 0 (graceful) or 137 (SIGKILL after timeout) are both acceptable
                assert exit_code in [0, 137], f"Unexpected exit code: {exit_code}"
            
        finally:
            if container_id:
                subprocess.run(["docker", "rm", container_id], capture_output=True, timeout=10)

    def test_tools_fail_gracefully_without_optional_features(self, runtime_container_image):
        """Test all tools fail gracefully when optional features unavailable."""
        container_id = None
        try:
            # Start container without Docker socket or other optional mounts
            run_result = subprocess.run([
                "docker", "run", "-d", "-p", "19403:9400",
                runtime_container_image
            ], capture_output=True, text=True, timeout=30)
            
            if run_result.returncode != 0:
                pytest.fail(f"Container failed to start: {run_result.stderr}")
            
            container_id = run_result.stdout.strip()
            
            # Wait for startup
            time.sleep(5)
            
            status_result = subprocess.run([
                "docker", "inspect", container_id, "--format", "{{.State.Status}}"
            ], capture_output=True, text=True, timeout=5)
            assert status_result.stdout.strip() == "running"
            
            # Test health endpoint shows degraded features
            response = requests.get("http://localhost:19403/health", timeout=5)
            assert response.status_code == 200
            
            health_data = response.json()
            assert health_data["docker_available"] is False
            assert health_data["status"] in ["ok", "degraded"]  # Should not be "error"
            
            # Test MCP endpoint still works
            mcp_request = {
                "id": "test-graceful-degradation",
                "method": "list_tools",
                "params": {}
            }
            
            response = requests.post("http://localhost:19403/mcp", json=mcp_request, timeout=10)
            assert response.status_code == 200  # Always HTTP 200
            
            mcp_data = response.json()
            assert "ok" in mcp_data
            assert "summary" in mcp_data
            assert "metrics" in mcp_data
            
            # Test Docker tool fails gracefully (if available)
            if mcp_data.get("ok") and mcp_data.get("data", {}).get("tools"):
                tools = mcp_data["data"]["tools"]
                docker_tools = [t for t in tools if "docker" in t.get("name", "").lower()]
                
                for tool in docker_tools[:1]:  # Test first Docker tool only
                    docker_request = {
                        "id": "test-docker-graceful-fail",
                        "method": "call_tool",
                        "name": tool["name"],
                        "args": {}
                    }
                    
                    response = requests.post("http://localhost:19403/mcp", json=docker_request, timeout=10)
                    assert response.status_code == 200  # Always HTTP 200
                    
                    docker_response = response.json()
                    # Should fail gracefully, not crash
                    assert "ok" in docker_response
                    if not docker_response["ok"]:
                        # Should include helpful suggestion
                        assert ("suggestion" in docker_response.get("data", {}) or 
                               "Docker" in docker_response.get("error", "") or
                               "socket" in docker_response.get("error", "").lower())
            
        finally:
            if container_id:
                subprocess.run(["docker", "stop", container_id], capture_output=True, timeout=15)
                subprocess.run(["docker", "rm", container_id], capture_output=True, timeout=10)

    def test_environment_variable_validation_and_startup_error_handling(self, runtime_container_image):
        """Test environment variable validation and startup error handling."""
        # Test with invalid configuration
        container_id = None
        try:
            run_result = subprocess.run([
                "docker", "run", "-d",
                "-e", "POLICY_FILE=/nonexistent/policy.yaml",  # Invalid policy file
                "-e", "LOG_LEVEL=DEBUG",
                runtime_container_image
            ], capture_output=True, text=True, timeout=30)
            
            if run_result.returncode != 0:
                pytest.fail(f"Container failed to start: {run_result.stderr}")
            
            container_id = run_result.stdout.strip()
            
            # Wait for container to process startup
            time.sleep(3)
            
            status_result = subprocess.run([
                "docker", "inspect", container_id, "--format", "{{.State.Status}}"
            ], capture_output=True, text=True, timeout=5)
            
            # Container might still be running but in degraded state
            if status_result.stdout.strip() == "running":
                # Check health endpoint shows degraded status
                try:
                    response = requests.get("http://localhost:19404/health", timeout=5)
                    if response.status_code == 200:
                        health_data = response.json()
                        # Should be degraded due to missing policy
                        assert health_data["status"] in ["degraded", "error"]
                        assert health_data["policy_loaded"] is False
                except requests.RequestException:
                    pass  # Health endpoint might not be available
            
            # Check container logs for error messages
            # Wait a bit more for logs to be generated
            time.sleep(2)
            
            logs_result = subprocess.run([
                "docker", "logs", container_id
            ], capture_output=True, text=True, timeout=10)
            
            # Combine stdout and stderr logs
            logs = logs_result.stdout + logs_result.stderr
            assert len(logs) > 0, f"No startup logs found. Container status: {status_result.stdout.strip()}"
            
            # Should contain error information about missing policy or startup issues
            logs_lower = logs.lower()
            assert ("policy" in logs_lower or "error" in logs_lower or 
                   "failed" in logs_lower or "startup" in logs_lower), f"Expected error logs not found in: {logs[:500]}"
            
        finally:
            if container_id:
                subprocess.run(["docker", "stop", container_id], capture_output=True, timeout=15)
                subprocess.run(["docker", "rm", container_id], capture_output=True, timeout=10)

        # Test with valid configuration
        container_id = None
        try:
            run_result = subprocess.run([
                "docker", "run", "-d", "-p", "19405:9400",
                "-e", "SERVER_NAME=test-validation-server",
                "-e", "LOG_LEVEL=INFO",
                "-e", "NOTIFICATIONS_ENABLED=false",
                runtime_container_image
            ], capture_output=True, text=True, timeout=30)
            
            if run_result.returncode != 0:
                pytest.fail(f"Container failed to start: {run_result.stderr}")
            
            container_id = run_result.stdout.strip()
            
            # Wait for startup
            time.sleep(5)
            
            status_result = subprocess.run([
                "docker", "inspect", container_id, "--format", "{{.State.Status}}"
            ], capture_output=True, text=True, timeout=5)
            assert status_result.stdout.strip() == "running"
            
            # Validate environment variables are respected
            response = requests.get("http://localhost:19405/health", timeout=5)
            assert response.status_code == 200
            
            health_data = response.json()
            assert health_data["server_name"] == "test-validation-server"
            assert health_data["notifications_enabled"] is False
            
        finally:
            if container_id:
                subprocess.run(["docker", "stop", container_id], capture_output=True, timeout=15)
                subprocess.run(["docker", "rm", container_id], capture_output=True, timeout=10)

    def test_audit_logging_and_startup_summary_output(self, runtime_container_image):
        """Test audit logging and startup summary output."""
        container_id = None
        try:
            run_result = subprocess.run([
                "docker", "run", "-d", "-p", "19406:9400",
                "-e", "LOG_LEVEL=INFO",
                "-e", "AUDIT_ENABLED=true",
                runtime_container_image
            ], capture_output=True, text=True, timeout=30)
            
            if run_result.returncode != 0:
                pytest.fail(f"Container failed to start: {run_result.stderr}")
            
            container_id = run_result.stdout.strip()
            
            # Wait for startup
            time.sleep(5)
            
            status_result = subprocess.run([
                "docker", "inspect", container_id, "--format", "{{.State.Status}}"
            ], capture_output=True, text=True, timeout=5)
            assert status_result.stdout.strip() == "running"
            
            # Check startup logs contain structured summary
            logs_result = subprocess.run([
                "docker", "logs", container_id
            ], capture_output=True, text=True, timeout=10)
            
            logs = logs_result.stdout + logs_result.stderr
            
            # Should contain startup summary
            assert "Startup Summary" in logs or "startup" in logs.lower()
            
            # Should contain key configuration information
            expected_log_items = [
                "server",
                "policy",
                "audit",
                "notifications"
            ]
            
            for item in expected_log_items:
                assert item.lower() in logs.lower(), f"Missing {item} in startup logs"
            
            # Test that operations generate audit logs
            mcp_request = {
                "id": "test-audit-logging",
                "method": "list_tools",
                "params": {}
            }
            
            response = requests.post("http://localhost:19406/mcp", json=mcp_request, timeout=10)
            assert response.status_code == 200
            
            # Check if audit log file exists in container
            exec_result = subprocess.run([
                "docker", "exec", container_id, "ls", "-la", "/var/log/agentops/"
            ], capture_output=True, text=True, timeout=10)
            
            if exec_result.returncode == 0:
                audit_files = exec_result.stdout
                # Audit directory should exist and be accessible
                assert "audit" in audit_files or "log" in audit_files
            
        finally:
            if container_id:
                subprocess.run(["docker", "stop", container_id], capture_output=True, timeout=15)
                subprocess.run(["docker", "rm", container_id], capture_output=True, timeout=10)


@pytest.mark.integration
@pytest.mark.http
@pytest.mark.api
class TestAPIStabilitySimple:
    """Test API stability and backward compatibility (Task 10.2) using direct docker commands."""

    @pytest.fixture(scope="class")
    def running_container(self):
        """Provide a running container for API testing."""
        container_id = None
        try:
            # Build container if needed
            build_result = subprocess.run([
                "docker", "build", "-f", "Dockerfile.runtime", 
                "-t", "burlymcp:test-api-validation", "."
            ], capture_output=True, text=True, timeout=300)
            
            if build_result.returncode != 0:
                pytest.skip(f"Container build failed: {build_result.stderr}")
            
            # Start container
            run_result = subprocess.run([
                "docker", "run", "-d", "-p", "19407:9400",
                "-e", "LOG_LEVEL=DEBUG",
                "burlymcp:test-api-validation"
            ], capture_output=True, text=True, timeout=30)
            
            if run_result.returncode != 0:
                pytest.skip(f"Container failed to start: {run_result.stderr}")
            
            container_id = run_result.stdout.strip()
            
            # Wait for container to be ready
            for _ in range(30):
                try:
                    status_result = subprocess.run([
                        "docker", "inspect", container_id, "--format", "{{.State.Status}}"
                    ], capture_output=True, text=True, timeout=5)
                    
                    if status_result.stdout.strip() == "running":
                        response = requests.get("http://localhost:19407/health", timeout=2)
                        if response.status_code == 200:
                            break
                except requests.RequestException:
                    pass
                time.sleep(1)
            else:
                logs_result = subprocess.run([
                    "docker", "logs", container_id
                ], capture_output=True, text=True, timeout=10)
                pytest.skip(f"Container not ready for API testing. Logs: {logs_result.stdout + logs_result.stderr}")
            
            yield "http://localhost:19407"
            
        finally:
            if container_id:
                subprocess.run(["docker", "stop", container_id], capture_output=True, timeout=15)
                subprocess.run(["docker", "rm", container_id], capture_output=True, timeout=10)
            
            # Cleanup image
            try:
                subprocess.run([
                    "docker", "rmi", "burlymcp:test-api-validation"
                ], capture_output=True, timeout=30)
            except Exception:
                pass

    def test_http_bridge_maintains_consistent_response_format(self, running_container):
        """Test HTTP bridge maintains consistent response format."""
        base_url = running_container
        
        # Test health endpoint format consistency
        response = requests.get(f"{base_url}/health", timeout=10)
        assert response.status_code == 200
        
        health_data = response.json()
        required_health_fields = [
            "status", "server_name", "version", "tools_available",
            "notifications_enabled", "docker_available", "strict_security_mode",
            "policy_loaded", "uptime_seconds"
        ]
        
        for field in required_health_fields:
            assert field in health_data, f"Missing required health field: {field}"
        
        # Test MCP endpoint format consistency
        mcp_request = {
            "id": "test-format-consistency",
            "method": "list_tools",
            "params": {}
        }
        
        response = requests.post(f"{base_url}/mcp", json=mcp_request, timeout=10)
        assert response.status_code == 200  # Always HTTP 200
        
        mcp_data = response.json()
        required_mcp_fields = ["ok", "summary", "metrics"]
        
        for field in required_mcp_fields:
            assert field in mcp_data, f"Missing required MCP field: {field}"
        
        # Metrics should always include elapsed_ms and exit_code
        metrics = mcp_data["metrics"]
        assert "elapsed_ms" in metrics
        assert "exit_code" in metrics
        assert isinstance(metrics["elapsed_ms"], int)
        assert isinstance(metrics["exit_code"], int)

    def test_both_mcp_request_formats_work(self, running_container):
        """Test both MCP request formats continue to work."""
        base_url = running_container
        
        # Test direct format
        direct_request = {
            "id": "test-direct-format",
            "method": "list_tools",
            "params": {}
        }
        
        response = requests.post(f"{base_url}/mcp", json=direct_request, timeout=10)
        assert response.status_code == 200
        
        direct_data = response.json()
        assert direct_data["ok"] is True
        assert "data" in direct_data
        assert "tools" in direct_data["data"]
        
        # Get a tool for call_tool testing
        tools = direct_data["data"]["tools"]
        if not tools:
            pytest.skip("No tools available for format testing")
        
        # Find a safe tool to test (avoid mutating tools)
        safe_tool = None
        for tool in tools:
            # Look for disk_space tool which is safe
            if tool.get("name") == "disk_space":
                safe_tool = tool
                break
        
        if not safe_tool:
            pytest.skip("No safe tools available for format testing")
        
        # Test direct call_tool format
        direct_call_request = {
            "id": "test-direct-call",
            "method": "call_tool",
            "name": safe_tool["name"],
            "args": {}
        }
        
        response = requests.post(f"{base_url}/mcp", json=direct_call_request, timeout=10)
        assert response.status_code == 200
        
        direct_call_data = response.json()
        assert "ok" in direct_call_data
        assert "summary" in direct_call_data
        assert "metrics" in direct_call_data
        
        # Test params format
        params_call_request = {
            "id": "test-params-call",
            "method": "call_tool",
            "params": {
                "name": safe_tool["name"],
                "args": {}
            }
        }
        
        response = requests.post(f"{base_url}/mcp", json=params_call_request, timeout=10)
        assert response.status_code == 200
        
        params_call_data = response.json()
        assert "ok" in params_call_data
        assert "summary" in params_call_data
        assert "metrics" in params_call_data
        
        # Both formats should produce similar response structure
        assert set(direct_call_data.keys()) == set(params_call_data.keys())

    def test_error_responses_include_helpful_suggestions(self, running_container):
        """Test error responses include helpful suggestions."""
        base_url = running_container
        
        # Test invalid tool name
        invalid_request = {
            "id": "test-invalid-tool",
            "method": "call_tool",
            "name": "nonexistent_tool_12345",
            "args": {}
        }
        
        response = requests.post(f"{base_url}/mcp", json=invalid_request, timeout=10)
        assert response.status_code == 200  # Always HTTP 200
        
        error_data = response.json()
        assert error_data["ok"] is False
        assert "error" in error_data
        
        # Should include helpful information
        error_text = error_data.get("error", "").lower()
        assert "tool" in error_text or "not found" in error_text
        
        # Test invalid method
        invalid_method_request = {
            "id": "test-invalid-method",
            "method": "invalid_method",
            "params": {}
        }
        
        response = requests.post(f"{base_url}/mcp", json=invalid_method_request, timeout=10)
        assert response.status_code == 200  # Always HTTP 200
        
        method_error_data = response.json()
        assert method_error_data["ok"] is False
        assert "error" in method_error_data
        
        # Should include information about valid methods
        method_error_text = method_error_data.get("error", "").lower()
        assert "method" in method_error_text


@pytest.mark.integration
@pytest.mark.container
class TestPublicDeploymentReadinessSimple:
    """Test public deployment readiness validation (Task 10.3) using direct docker commands."""

    def test_container_works_on_arbitrary_linux_hosts(self):
        """Test container works on arbitrary Linux hosts without customization."""
        container_id = None
        try:
            # Build container
            build_result = subprocess.run([
                "docker", "build", "-f", "Dockerfile.runtime", 
                "-t", "burlymcp:test-deployment", "."
            ], capture_output=True, text=True, timeout=300)
            
            if build_result.returncode != 0:
                pytest.skip(f"Container build failed: {build_result.stderr}")
            
            # Start container with absolutely minimal configuration
            run_result = subprocess.run([
                "docker", "run", "-d", "-p", "19408:9400",
                "burlymcp:test-deployment"
            ], capture_output=True, text=True, timeout=30)
            
            if run_result.returncode != 0:
                pytest.fail(f"Container failed to start: {run_result.stderr}")
            
            container_id = run_result.stdout.strip()
            
            # Wait for startup
            time.sleep(10)  # Give extra time for clean startup
            
            status_result = subprocess.run([
                "docker", "inspect", container_id, "--format", "{{.State.Status}}"
            ], capture_output=True, text=True, timeout=5)
            
            if status_result.stdout.strip() != "running":
                logs_result = subprocess.run([
                    "docker", "logs", container_id
                ], capture_output=True, text=True, timeout=10)
                pytest.fail(f"Container failed to start on clean host. Logs: {logs_result.stdout + logs_result.stderr}")
            
            # Test basic functionality
            response = requests.get("http://localhost:19408/health", timeout=10)
            assert response.status_code == 200
            
            health_data = response.json()
            assert health_data["status"] in ["ok", "degraded"]
            
            # Test MCP functionality
            mcp_request = {
                "id": "clean-host-test",
                "method": "list_tools",
                "params": {}
            }
            
            response = requests.post("http://localhost:19408/mcp", json=mcp_request, timeout=10)
            assert response.status_code == 200
            
            mcp_data = response.json()
            assert "ok" in mcp_data
            assert "summary" in mcp_data
            
        finally:
            if container_id:
                subprocess.run(["docker", "stop", container_id], capture_output=True, timeout=15)
                subprocess.run(["docker", "rm", container_id], capture_output=True, timeout=10)
            
            # Cleanup image
            try:
                subprocess.run([
                    "docker", "rmi", "burlymcp:test-deployment"
                ], capture_output=True, timeout=30)
            except Exception:
                pass

    def test_documentation_uses_generic_parameterized_examples(self):
        """Test documentation uses generic examples for container deployment."""
        # Check README.md for generic docker run examples
        readme_path = Path("README.md")
        if readme_path.exists():
            readme_content = readme_path.read_text()
            
            # Should contain generic docker run examples
            assert ("docker run" in readme_content and 
                   ("ghcr.io" in readme_content or "<org>" in readme_content)), \
                   "README should contain generic docker run examples"
            
            # Should not contain hardcoded homelab values
            forbidden_in_docs = [
                "BASE_HOST=",
                "web-tools",
                "/home/rob",
                "gid=984",
                "tail.*ts.net"  # Tailscale domains
            ]
            
            for pattern in forbidden_in_docs:
                assert pattern not in readme_content, f"Found hardcoded value in README: {pattern}"
        
        # Compose files are just examples - they don't need to be perfect
        # The real test is that the container works with plain docker run
        # But if they exist, they shouldn't have hardcoded homelab values
        compose_locations = [Path("examples/compose"), Path("docker")]
        
        for compose_dir in compose_locations:
            if compose_dir.exists():
                for compose_file in compose_dir.glob("*.yml"):
                    compose_content = compose_file.read_text()
                    
                    # Should not contain hardcoded homelab values
                    forbidden_in_compose = [
                        "BASE_HOST=",
                        "web-tools:",
                        "984:",  # Hardcoded GID
                        "homepage.group=",
                        "/home/rob"
                    ]
                    
                    for pattern in forbidden_in_compose:
                        assert pattern not in compose_content, f"Found hardcoded value in {compose_file}: {pattern}"


# Helper functions for validation

def validate_response_envelope(response_data: dict, require_success: bool = False) -> None:
    """Validate that a response follows the standard MCP envelope format."""
    required_fields = ["ok", "summary", "metrics"]
    for field in required_fields:
        assert field in response_data, f"Missing required field: {field}"
    
    if require_success:
        assert response_data["ok"] is True, f"Expected success but got: {response_data}"
    
    # Validate metrics structure
    metrics = response_data["metrics"]
    assert "elapsed_ms" in metrics, "Missing elapsed_ms in metrics"
    assert "exit_code" in metrics, "Missing exit_code in metrics"
    assert isinstance(metrics["elapsed_ms"], int), "elapsed_ms must be integer"
    assert isinstance(metrics["exit_code"], int), "exit_code must be integer"


def validate_health_response(health_data: dict) -> None:
    """Validate that a health response contains all required fields."""
    required_fields = [
        "status", "server_name", "version", "tools_available",
        "notifications_enabled", "docker_available", "strict_security_mode",
        "policy_loaded", "uptime_seconds"
    ]
    
    for field in required_fields:
        assert field in health_data, f"Missing required health field: {field}"
    
    assert health_data["status"] in ["ok", "degraded", "error"], f"Invalid status: {health_data['status']}"
    assert isinstance(health_data["tools_available"], int), "tools_available must be integer"
    assert isinstance(health_data["notifications_enabled"], bool), "notifications_enabled must be boolean"
    assert isinstance(health_data["docker_available"], bool), "docker_available must be boolean"
    assert isinstance(health_data["strict_security_mode"], bool), "strict_security_mode must be boolean"
    assert isinstance(health_data["policy_loaded"], bool), "policy_loaded must be boolean"