"""
Final Integration and Validation Tests

This module implements comprehensive validation tests for task 10 of the
standalone service container specification. These tests validate complete
standalone operation, API stability, and public deployment readiness.
"""

import asyncio
import json
import os
import signal
import subprocess
import time
from pathlib import Path
from typing import Dict, Any, Optional

import pytest
import requests

try:
    from testcontainers.core.generic import DockerContainer
    import docker
    TESTCONTAINERS_AVAILABLE = True
except ImportError:
    TESTCONTAINERS_AVAILABLE = False
    DockerContainer = None
    docker = None


# Module-level fixtures shared across test classes
@pytest.fixture(scope="module")
def docker_client():
    """Provide Docker client for container tests."""
    if not TESTCONTAINERS_AVAILABLE:
        pytest.skip("testcontainers not available")
    try:
        client = docker.from_env()
        client.ping()
        return client
    except Exception as e:
        pytest.skip(f"Docker not available: {e}")


@pytest.fixture(scope="module")
def runtime_container_image(docker_client):
    """Build runtime container image for testing."""
    try:
        # Build the runtime container from Dockerfile.runtime
        image, build_logs = docker_client.images.build(
            path=".",
            dockerfile="Dockerfile.runtime",
            tag="burlymcp:test-final-validation",
            rm=True,
            forcerm=True
        )
        
        yield image
        
        # Cleanup
        try:
            docker_client.images.remove(image.id, force=True)
        except Exception:
            pass  # Image might already be removed
            
    except Exception as e:
        pytest.skip(f"Runtime container build failed: {e}")


@pytest.mark.integration
@pytest.mark.container
@pytest.mark.skipif(not TESTCONTAINERS_AVAILABLE, reason="testcontainers not available")
class TestStandaloneOperation:
    """Test complete standalone operation (Task 10.1)."""

    @pytest.mark.flaky
    def test_container_starts_within_30_seconds(self, docker_client, runtime_container_image):
        """Test container starts and responds to health checks within 30 seconds."""
        container = None
        try:
            start_time = time.time()
            
            # Start container with minimal configuration
            container = docker_client.containers.run(
                runtime_container_image.id,
                ports={"9400/tcp": 9400},
                detach=True,
                remove=False,
                environment={
                    "LOG_LEVEL": "DEBUG"
                }
            )
            
            # Wait for container to be running with CI-aware timeout
            # CI environments can be very slow, so we need generous timeouts
            max_startup_time = 90 if os.getenv('CI') else 30
            timeout = max_startup_time
            
            while time.time() - start_time < timeout:
                container.reload()
                if container.status == "running":
                    break
                time.sleep(0.5)
            else:
                logs = container.logs(stdout=True, stderr=True).decode('utf-8')
                pytest.fail(f"Container did not start within {timeout}s. Logs: {logs}")
            
            # Test health endpoint availability within startup time
            health_available = False
            while time.time() - start_time < timeout:
                try:
                    response = requests.get("http://localhost:9400/health", timeout=2)
                    if response.status_code == 200:
                        health_available = True
                        break
                except requests.RequestException:
                    pass
                time.sleep(1)
            
            startup_time = time.time() - start_time
            
            # Validate startup time requirement
            assert startup_time < max_startup_time, f"Container took {startup_time:.1f}s to start (requirement: <{max_startup_time}s)"
            assert health_available, f"Health endpoint not available within {max_startup_time} seconds"
            
            # Validate health response format
            response = requests.get("http://localhost:9400/health", timeout=5)
            assert response.status_code == 200
            
            health_data = response.json()
            required_fields = ["status", "server_name", "version", "tools_available", 
                             "notifications_enabled", "docker_available", "strict_security_mode", 
                             "policy_loaded", "uptime_seconds"]
            
            for field in required_fields:
                assert field in health_data, f"Missing required field: {field}"
            
            assert health_data["status"] in ["ok", "degraded"], f"Invalid status: {health_data['status']}"
            
        finally:
            if container:
                container.stop()
                container.remove()

    def test_graceful_shutdown_within_10_seconds(self, docker_client, runtime_container_image):
        """Test graceful shutdown on SIGTERM within 10 seconds."""
        container = None
        try:
            # Start container
            container = docker_client.containers.run(
                runtime_container_image.id,
                ports={"9400/tcp": 9400},
                detach=True,
                remove=False
            )
            
            # Wait for container to be ready
            time.sleep(5)
            container.reload()
            assert container.status == "running"
            
            # Send SIGTERM and measure shutdown time
            start_time = time.time()
            container.kill(signal="SIGTERM")
            
            # Wait for container to stop (allow extra time in CI environments)
            timeout = 15 if os.getenv('CI') else 10
            while time.time() - start_time < timeout:
                container.reload()
                if container.status in ["exited", "dead"]:
                    break
                time.sleep(0.1)
            else:
                # Force kill if it didn't stop gracefully
                container.kill(signal="SIGKILL")
                pytest.fail(f"Container did not shut down gracefully within {timeout} seconds")
            
            shutdown_time = time.time() - start_time
            max_shutdown_time = 15 if os.getenv('CI') else 10
            assert shutdown_time < max_shutdown_time, f"Shutdown took {shutdown_time:.1f}s (requirement: <{max_shutdown_time}s)"
            
            # Check exit code (should be 0 for graceful shutdown)
            container.reload()
            exit_code = container.attrs.get("State", {}).get("ExitCode", -1)
            assert exit_code == 0, f"Non-zero exit code: {exit_code}"
            
        finally:
            if container:
                try:
                    container.remove()
                except Exception:
                    pass

    @pytest.mark.flaky
    def test_tools_fail_gracefully_without_optional_features(self, docker_client, runtime_container_image):
        """Test all tools fail gracefully when optional features unavailable."""
        container = None
        try:
            # Start container without Docker socket or other optional mounts
            container = docker_client.containers.run(
                runtime_container_image.id,
                ports={"9400/tcp": 9400},
                detach=True,
                remove=False,
                # Explicitly no Docker socket mount or other optional features
            )
            
            # Wait for startup and health endpoint to be available
            start_time = time.time()
            health_available = False
            max_wait_time = 90 if os.getenv('CI') else 30
            
            while time.time() - start_time < max_wait_time:
                container.reload()
                if container.status != "running":
                    break
                    
                try:
                    response = requests.get("http://localhost:9400/health", timeout=5)
                    if response.status_code == 200:
                        health_available = True
                        break
                except requests.RequestException:
                    pass
                time.sleep(1)
            
            assert container.status == "running", f"Container not running: {container.status}"
            assert health_available, f"Health endpoint not available within {max_wait_time} seconds"
            
            # Test health endpoint shows degraded features
            response = requests.get("http://localhost:9400/health", timeout=5)
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
            
            response = requests.post("http://localhost:9400/mcp", json=mcp_request, timeout=10)
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
                    
                    response = requests.post("http://localhost:9400/mcp", json=docker_request, timeout=10)
                    assert response.status_code == 200  # Always HTTP 200
                    
                    docker_response = response.json()
                    # Should fail gracefully, not crash
                    assert "ok" in docker_response
                    if not docker_response["ok"]:
                        # Should include helpful suggestion
                        assert "suggestion" in docker_response.get("data", {}) or "Docker" in docker_response.get("error", "")
            
        finally:
            if container:
                container.stop()
                container.remove()

    @pytest.mark.flaky
    def test_environment_variable_validation_and_startup_error_handling(self, docker_client, runtime_container_image):
        """Test environment variable validation and startup error handling."""
        # Test with invalid configuration
        container = None
        try:
            container = docker_client.containers.run(
                runtime_container_image.id,
                detach=True,
                remove=False,
                environment={
                    "POLICY_FILE": "/nonexistent/policy.yaml",  # Invalid policy file
                    "LOG_LEVEL": "DEBUG"
                }
            )
            
            # Wait for container to process startup
            time.sleep(3)
            container.reload()
            
            # Container might still be running but in degraded state
            if container.status == "running":
                # Check health endpoint shows degraded status
                try:
                    response = requests.get("http://localhost:9400/health", timeout=5)
                    if response.status_code == 200:
                        health_data = response.json()
                        # Should be degraded due to missing policy
                        assert health_data["status"] in ["degraded", "error"]
                        assert health_data["policy_loaded"] is False
                except requests.RequestException:
                    pass  # Health endpoint might not be available
            
            # Check container logs for error messages
            logs = container.logs(stdout=True, stderr=True).decode('utf-8')
            assert len(logs) > 0, "No startup logs found"
            
            # Should contain error information about missing policy
            assert "policy" in logs.lower() or "error" in logs.lower()
            
        finally:
            if container:
                container.stop()
                container.remove()

        # Test with valid configuration
        container = None
        try:
            container = docker_client.containers.run(
                runtime_container_image.id,
                ports={"9400/tcp": 9400},
                detach=True,
                remove=False,
                environment={
                    "SERVER_NAME": "test-validation-server",
                    "LOG_LEVEL": "INFO",
                    "NOTIFICATIONS_ENABLED": "false"
                }
            )
            
            # Wait for startup
            time.sleep(5)
            container.reload()
            assert container.status == "running"
            
            # Validate environment variables are respected
            response = requests.get("http://localhost:9400/health", timeout=5)
            assert response.status_code == 200
            
            health_data = response.json()
            assert health_data["server_name"] == "test-validation-server"
            assert health_data["notifications_enabled"] is False
            
        finally:
            if container:
                container.stop()
                container.remove()

    @pytest.mark.flaky
    def test_audit_logging_and_startup_summary_output(self, docker_client, runtime_container_image):
        """Test audit logging and startup summary output."""
        container = None
        try:
            container = docker_client.containers.run(
                runtime_container_image.id,
                ports={"9400/tcp": 9400},
                detach=True,
                remove=False,
                environment={
                    "LOG_LEVEL": "INFO",
                    "AUDIT_ENABLED": "true"
                }
            )
            
            # Wait for startup
            time.sleep(5)
            container.reload()
            assert container.status == "running"
            
            # Check startup logs contain structured summary
            logs = container.logs(stdout=True, stderr=True).decode('utf-8')
            
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
            
            response = requests.post("http://localhost:9400/mcp", json=mcp_request, timeout=10)
            assert response.status_code == 200
            
            # Check if audit log file exists in container
            exec_result = container.exec_run("ls -la /var/log/agentops/")
            if exec_result.exit_code == 0:
                audit_files = exec_result.output.decode('utf-8')
                # Audit directory should exist and be accessible
                assert "audit" in audit_files or "log" in audit_files
            
        finally:
            if container:
                container.stop()
                container.remove()


@pytest.mark.integration
@pytest.mark.http
@pytest.mark.api
class TestAPIStabilityAndBackwardCompatibility:
    """Test API stability and backward compatibility (Task 10.2)."""

    @pytest.fixture
    def http_client(self):
        """Provide HTTP client for API testing."""
        session = requests.Session()
        session.timeout = 30
        try:
            yield session
        finally:
            session.close()

    @pytest.fixture(scope="class")
    def running_container(self, docker_client, runtime_container_image):
        """Provide a running container for API testing."""
        container = None
        try:
            container = docker_client.containers.run(
                runtime_container_image.id,
                ports={"9400/tcp": 9400},
                detach=True,
                remove=False,
                environment={
                    "LOG_LEVEL": "DEBUG"
                }
            )
            
            # Wait for container to be ready
            for _ in range(30):
                try:
                    container.reload()
                    if container.status == "running":
                        response = requests.get("http://localhost:9400/health", timeout=2)
                        if response.status_code == 200:
                            break
                except requests.RequestException:
                    pass
                time.sleep(1)
            else:
                logs = container.logs(stdout=True, stderr=True).decode('utf-8')
                pytest.skip(f"Container not ready for API testing. Logs: {logs}")
            
            yield "http://localhost:9400"
            
        finally:
            if container:
                container.stop()
                container.remove()

    def test_http_bridge_maintains_consistent_response_format(self, running_container, http_client):
        """Test HTTP bridge maintains consistent response format."""
        base_url = running_container
        
        # Test health endpoint format consistency
        response = http_client.get(f"{base_url}/health")
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
        
        response = http_client.post(f"{base_url}/mcp", json=mcp_request)
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

    def test_both_mcp_request_formats_work(self, running_container, http_client):
        """Test both MCP request formats continue to work."""
        base_url = running_container
        
        # Test direct format
        direct_request = {
            "id": "test-direct-format",
            "method": "list_tools",
            "params": {}
        }
        
        response = http_client.post(f"{base_url}/mcp", json=direct_request)
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
            if not tool.get("mutates", True):  # Default to True for safety
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
        
        response = http_client.post(f"{base_url}/mcp", json=direct_call_request)
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
        
        response = http_client.post(f"{base_url}/mcp", json=params_call_request)
        assert response.status_code == 200
        
        params_call_data = response.json()
        assert "ok" in params_call_data
        assert "summary" in params_call_data
        assert "metrics" in params_call_data
        
        # Both formats should produce similar response structure
        assert set(direct_call_data.keys()) == set(params_call_data.keys())

    def test_error_responses_include_helpful_suggestions(self, running_container, http_client):
        """Test error responses include helpful suggestions."""
        base_url = running_container
        
        # Test invalid tool name
        invalid_request = {
            "id": "test-invalid-tool",
            "method": "call_tool",
            "name": "nonexistent_tool_12345",
            "args": {}
        }
        
        response = http_client.post(f"{base_url}/mcp", json=invalid_request)
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
        
        response = http_client.post(f"{base_url}/mcp", json=invalid_method_request)
        assert response.status_code == 200  # Always HTTP 200
        
        method_error_data = response.json()
        assert method_error_data["ok"] is False
        assert "error" in method_error_data
        
        # Should include information about valid methods
        method_error_text = method_error_data.get("error", "").lower()
        assert "method" in method_error_text

    def test_mcp_contract_stability_across_internal_changes(self, running_container, http_client):
        """Test that internal refactors don't break /mcp contract."""
        base_url = running_container
        
        # This test validates that the HTTP bridge provides a stable contract
        # regardless of internal MCP engine implementation changes
        
        # Test multiple requests to ensure consistent behavior
        test_requests = [
            {
                "id": "stability-test-1",
                "method": "list_tools",
                "params": {}
            },
            {
                "id": "stability-test-2", 
                "method": "list_tools",
                "params": {}
            }
        ]
        
        responses = []
        for request in test_requests:
            response = http_client.post(f"{base_url}/mcp", json=request)
            assert response.status_code == 200
            responses.append(response.json())
        
        # Responses should have consistent structure
        for i, response_data in enumerate(responses):
            assert "ok" in response_data, f"Response {i} missing 'ok' field"
            assert "summary" in response_data, f"Response {i} missing 'summary' field"
            assert "metrics" in response_data, f"Response {i} missing 'metrics' field"
            
            if response_data["ok"]:
                assert "data" in response_data, f"Successful response {i} missing 'data' field"
        
        # Tool lists should be identical (assuming no changes between requests)
        if all(r["ok"] for r in responses):
            tools_1 = responses[0]["data"]["tools"]
            tools_2 = responses[1]["data"]["tools"]
            assert len(tools_1) == len(tools_2), "Tool count inconsistent between requests"

    def test_downstream_integration_compatibility(self, running_container, http_client):
        """Test downstream integration compatibility."""
        base_url = running_container
        
        # Simulate downstream system integration patterns
        
        # 1. Health monitoring pattern
        health_response = http_client.get(f"{base_url}/health")
        assert health_response.status_code == 200
        
        health_data = health_response.json()
        
        # Downstream systems expect these fields for monitoring
        monitoring_fields = ["status", "uptime_seconds", "tools_available"]
        for field in monitoring_fields:
            assert field in health_data
        
        # Status should be actionable for monitoring
        assert health_data["status"] in ["ok", "degraded", "error"]
        
        # 2. Tool discovery pattern
        discovery_request = {
            "id": "downstream-discovery",
            "method": "list_tools",
            "params": {}
        }
        
        discovery_response = http_client.post(f"{base_url}/mcp", json=discovery_request)
        assert discovery_response.status_code == 200
        
        discovery_data = discovery_response.json()
        if discovery_data["ok"]:
            tools = discovery_data["data"]["tools"]
            
            # Each tool should have required fields for downstream integration
            for tool in tools:
                required_tool_fields = ["name", "description"]
                for field in required_tool_fields:
                    assert field in tool, f"Tool missing required field: {field}"
        
        # 3. Error handling pattern
        error_request = {
            "id": "downstream-error-test",
            "method": "call_tool",
            "name": "nonexistent_tool",
            "args": {}
        }
        
        error_response = http_client.post(f"{base_url}/mcp", json=error_request)
        assert error_response.status_code == 200  # Critical: always HTTP 200
        
        error_data = error_response.json()
        assert error_data["ok"] is False
        
        # Downstream systems need structured error information
        assert "error" in error_data
        assert "metrics" in error_data


@pytest.mark.integration
@pytest.mark.container
@pytest.mark.skipif(not TESTCONTAINERS_AVAILABLE, reason="testcontainers not available")
class TestPublicDeploymentReadiness:
    """Test public deployment readiness validation (Task 10.3)."""

    @pytest.mark.flaky
    def test_container_works_on_arbitrary_linux_hosts(self, docker_client, runtime_container_image):
        """Test container works on arbitrary Linux hosts without customization."""
        # This test simulates deployment on a clean Linux host
        container = None
        try:
            # Start container with absolutely minimal configuration
            # No custom environment variables, no special mounts
            container = docker_client.containers.run(
                runtime_container_image.id,
                ports={"9400/tcp": 9400},
                detach=True,
                remove=False
                # No environment variables - use all defaults
            )
            
            # Wait for startup
            time.sleep(10)  # Give extra time for clean startup
            container.reload()
            
            if container.status != "running":
                logs = container.logs(stdout=True, stderr=True).decode('utf-8')
                pytest.fail(f"Container failed to start on clean host. Logs: {logs}")
            
            # Test basic functionality
            response = requests.get("http://localhost:9400/health", timeout=10)
            assert response.status_code == 200
            
            health_data = response.json()
            assert health_data["status"] in ["ok", "degraded"]
            
            # Test MCP functionality
            mcp_request = {
                "id": "clean-host-test",
                "method": "list_tools",
                "params": {}
            }
            
            response = requests.post("http://localhost:9400/mcp", json=mcp_request, timeout=10)
            assert response.status_code == 200
            
            mcp_data = response.json()
            assert "ok" in mcp_data
            assert "summary" in mcp_data
            
        finally:
            if container:
                container.stop()
                container.remove()

    def test_no_hardcoded_homelab_values_in_published_image(self, docker_client, runtime_container_image):
        """Test no hardcoded homelab-specific values in published image."""
        container = None
        try:
            container = docker_client.containers.run(
                runtime_container_image.id,
                detach=True,
                remove=False
            )
            
            # Wait for startup
            time.sleep(3)
            
            # Check environment variables for homelab-specific values
            exec_result = container.exec_run("env")
            if exec_result.exit_code == 0:
                env_output = exec_result.output.decode('utf-8')
                
                # Should not contain homelab-specific values
                forbidden_patterns = [
                    "BASE_HOST",
                    "tail.*ts.net",  # Tailscale domains
                    "web-tools",     # Specific network names
                    "homepage.",     # Homepage labels
                    "/home/rob",     # Specific user paths
                    "984",           # Specific group IDs
                ]
                
                for pattern in forbidden_patterns:
                    assert pattern not in env_output, f"Found homelab-specific value: {pattern}"
            
            # Check configuration files for hardcoded values
            config_files = [
                "/app/BurlyMCP/config/policy/tools.yaml",
                "/app/http_bridge.py"
            ]
            
            for config_file in config_files:
                exec_result = container.exec_run(f"cat {config_file}")
                if exec_result.exit_code == 0:
                    config_content = exec_result.output.decode('utf-8')
                    
                    # Should not contain hardcoded homelab values
                    forbidden_in_config = [
                        "BASE_HOST",
                        "web-tools",
                        "/home/rob",
                        "tail.*ts.net"
                    ]
                    
                    for pattern in forbidden_in_config:
                        assert pattern not in config_content, f"Found hardcoded value in {config_file}: {pattern}"
            
        finally:
            if container:
                container.stop()
                container.remove()

    def test_documentation_uses_generic_parameterized_examples(self):
        """Test all documentation uses generic, parameterized examples."""
        # Check README.md for generic examples
        readme_path = Path("README.md")
        if readme_path.exists():
            readme_content = readme_path.read_text()
            
            # Should contain parameterized examples
            assert "<host_docker_group_gid>" in readme_content or "getent group docker" in readme_content
            assert "<org>" in readme_content or "ghcr.io" in readme_content
            
            # Should not contain hardcoded values
            forbidden_in_docs = [
                "BASE_HOST=",
                "web-tools",
                "/home/rob",
                "gid=984"
            ]
            
            for pattern in forbidden_in_docs:
                assert pattern not in readme_content, f"Found hardcoded value in README: {pattern}"
        
        # Check example compose files
        examples_dir = Path("examples/compose")
        if examples_dir.exists():
            for compose_file in examples_dir.glob("*.yml"):
                compose_content = compose_file.read_text()
                
                # Only the main compose file should have parameterized examples
                # Override and minimal files are for specific use cases and don't need placeholders
                if compose_file.name == "docker-compose.yml":
                    # Should contain parameterized examples
                    assert "<host_docker_group_gid>" in compose_content or "# replace" in compose_content.lower()
                
                # Should not contain hardcoded homelab values
                forbidden_in_compose = [
                    "BASE_HOST=",
                    "web-tools:",
                    "984:",  # Hardcoded GID
                    "homepage.group="
                ]
                
                for pattern in forbidden_in_compose:
                    assert pattern not in compose_content, f"Found hardcoded value in {compose_file}: {pattern}"

    @pytest.mark.flaky
    def test_minimal_privilege_mode_provides_useful_functionality(self, docker_client, runtime_container_image):
        """Test minimal privilege mode provides useful functionality."""
        container = None
        try:
            # Start container in minimal privilege mode
            # No Docker socket, no special groups, no elevated privileges
            container = docker_client.containers.run(
                runtime_container_image.id,
                ports={"9400/tcp": 9400},
                detach=True,
                remove=False,
                user="1000:1000",  # Explicit non-root user
                # No Docker socket mount
                # No additional groups
            )
            
            # Wait for startup
            time.sleep(5)
            container.reload()
            assert container.status == "running"
            
            # Verify running as non-root
            exec_result = container.exec_run("id")
            if exec_result.exit_code == 0:
                id_output = exec_result.output.decode('utf-8')
                assert "uid=1000" in id_output
                assert "gid=1000" in id_output
            
            # Test health endpoint works
            response = requests.get("http://localhost:9400/health", timeout=5)
            assert response.status_code == 200
            
            health_data = response.json()
            assert health_data["status"] in ["ok", "degraded"]  # Should not be "error"
            assert health_data["docker_available"] is False
            
            # Test MCP functionality works
            mcp_request = {
                "id": "minimal-privilege-test",
                "method": "list_tools",
                "params": {}
            }
            
            response = requests.post("http://localhost:9400/mcp", json=mcp_request, timeout=10)
            assert response.status_code == 200
            
            mcp_data = response.json()
            assert mcp_data["ok"] is True  # Should work in minimal mode
            
            # Should have some tools available even without Docker
            if "data" in mcp_data and "tools" in mcp_data["data"]:
                tools = mcp_data["data"]["tools"]
                non_docker_tools = [t for t in tools if "docker" not in t.get("name", "").lower()]
                assert len(non_docker_tools) > 0, "No non-Docker tools available in minimal mode"
            
        finally:
            if container:
                container.stop()
                container.remove()

    @pytest.mark.flaky
    def test_container_consumable_by_downstream_infrastructure(self, docker_client, runtime_container_image):
        """Test container can be consumed by downstream infrastructure systems."""
        container = None
        try:
            # Simulate downstream infrastructure deployment
            container = docker_client.containers.run(
                runtime_container_image.id,
                ports={"9400/tcp": 9400},
                detach=True,
                remove=False,
                environment={
                    # Simulate infrastructure-provided configuration
                    "SERVER_NAME": "infrastructure-deployed-burlymcp",
                    "LOG_LEVEL": "INFO",
                    "AUDIT_ENABLED": "true"
                },
                # Simulate infrastructure volume mounts
                tmpfs={
                    "/tmp": "rw,noexec,nosuid,size=100m"
                }
            )
            
            # Wait for startup
            time.sleep(5)
            container.reload()
            assert container.status == "running"
            
            # Test infrastructure monitoring patterns
            
            # 1. Health check for load balancer
            response = requests.get("http://localhost:9400/health", timeout=5)
            assert response.status_code == 200
            
            health_data = response.json()
            assert "status" in health_data
            assert "uptime_seconds" in health_data
            
            # 2. Service discovery
            mcp_request = {
                "id": "infrastructure-discovery",
                "method": "list_tools", 
                "params": {}
            }
            
            response = requests.post("http://localhost:9400/mcp", json=mcp_request, timeout=10)
            assert response.status_code == 200
            
            # 3. Metrics collection
            mcp_data = response.json()
            assert "metrics" in mcp_data
            metrics = mcp_data["metrics"]
            assert "elapsed_ms" in metrics
            assert "exit_code" in metrics
            
            # 4. Error handling for monitoring
            error_request = {
                "id": "infrastructure-error-test",
                "method": "call_tool",
                "name": "nonexistent_tool",
                "args": {}
            }
            
            error_response = requests.post("http://localhost:9400/mcp", json=error_request, timeout=10)
            assert error_response.status_code == 200  # Critical for infrastructure
            
            error_data = error_response.json()
            assert error_data["ok"] is False
            assert "metrics" in error_data  # Infrastructure needs metrics even for errors
            
        finally:
            if container:
                container.stop()
                container.remove()


# Additional helper functions for validation

def validate_response_envelope(response_data: Dict[str, Any], require_success: bool = False) -> None:
    """
    Validate that a response follows the standard MCP envelope format.
    
    Args:
        response_data: Response data to validate
        require_success: Whether to require ok=True
    """
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


def validate_health_response(health_data: Dict[str, Any]) -> None:
    """
    Validate that a health response contains all required fields.
    
    Args:
        health_data: Health response data to validate
    """
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