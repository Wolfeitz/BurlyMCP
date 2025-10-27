"""
Unit tests for the HTTP Bridge FastAPI application.

These tests focus on the HTTP bridge functionality in isolation,
using mocks for the MCP engine communication.
"""

import asyncio
import json
import pytest
from unittest.mock import AsyncMock, Mock, patch

# Import the FastAPI app and dependencies
try:
    from fastapi.testclient import TestClient
    from http_bridge import app, MCPRequest, MCPResponse, HealthResponse
    from http_bridge import normalize_mcp_request, sanitize_mcp_request_data
    from http_bridge import forward_to_mcp_engine, load_runtime_config
    HTTP_BRIDGE_AVAILABLE = True
except ImportError:
    HTTP_BRIDGE_AVAILABLE = False
    app = None
    TestClient = None


@pytest.mark.unit
@pytest.mark.http
@pytest.mark.skipif(not HTTP_BRIDGE_AVAILABLE, reason="HTTP bridge not available")
class TestHTTPBridgeModels:
    """Test Pydantic models for HTTP bridge."""

    def test_mcp_request_direct_format(self):
        """Test MCPRequest with direct format."""
        request_data = {
            "id": "test-1",
            "method": "call_tool",
            "name": "disk_space",
            "args": {"path": "/"}
        }
        
        request = MCPRequest(**request_data)
        assert request.id == "test-1"
        assert request.method == "call_tool"
        assert request.name == "disk_space"
        assert request.args == {"path": "/"}
        assert request.params is None

    def test_mcp_request_params_format(self):
        """Test MCPRequest with params format."""
        request_data = {
            "id": "test-2",
            "method": "call_tool",
            "params": {
                "name": "disk_space",
                "args": {"path": "/"}
            }
        }
        
        request = MCPRequest(**request_data)
        assert request.id == "test-2"
        assert request.method == "call_tool"
        assert request.name is None
        assert request.args is None
        assert request.params == {"name": "disk_space", "args": {"path": "/"}}

    def test_mcp_request_list_tools_format(self):
        """Test MCPRequest for list_tools method."""
        request_data = {
            "id": "test-3",
            "method": "list_tools",
            "params": {}
        }
        
        request = MCPRequest(**request_data)
        assert request.id == "test-3"
        assert request.method == "list_tools"
        assert request.params == {}

    def test_mcp_request_validation_invalid_method(self):
        """Test MCPRequest validation with invalid method."""
        request_data = {
            "id": "test-4",
            "method": "invalid_method"
        }
        
        with pytest.raises(ValueError, match="Method must be one of"):
            MCPRequest(**request_data)

    def test_mcp_request_validation_invalid_tool_name(self):
        """Test MCPRequest validation with invalid tool name."""
        request_data = {
            "id": "test-5",
            "method": "call_tool",
            "name": "invalid-tool-name!"  # Contains invalid characters
        }
        
        with pytest.raises(ValueError, match="Tool name must contain only"):
            MCPRequest(**request_data)

    def test_mcp_request_validation_tool_name_too_long(self):
        """Test MCPRequest validation with tool name too long."""
        request_data = {
            "id": "test-6",
            "method": "call_tool",
            "name": "a" * 101  # Too long
        }
        
        with pytest.raises(ValueError, match="Tool name too long"):
            MCPRequest(**request_data)

    def test_mcp_response_creation(self):
        """Test MCPResponse creation with required fields."""
        response_data = {
            "ok": True,
            "summary": "Operation successful",
            "data": {"result": "test"},
            "metrics": {"elapsed_ms": 150, "exit_code": 0}
        }
        
        response = MCPResponse(**response_data)
        assert response.ok is True
        assert response.summary == "Operation successful"
        assert response.data == {"result": "test"}
        assert response.metrics["elapsed_ms"] == 150
        assert response.metrics["exit_code"] == 0

    def test_mcp_response_defaults(self):
        """Test MCPResponse with default values."""
        response_data = {
            "ok": False,
            "summary": "Operation failed"
        }
        
        response = MCPResponse(**response_data)
        assert response.ok is False
        assert response.summary == "Operation failed"
        assert response.metrics["elapsed_ms"] == 0
        assert response.metrics["exit_code"] == 1  # Default for failed operations

    def test_health_response_creation(self):
        """Test HealthResponse creation."""
        health_data = {
            "status": "ok",
            "server_name": "test-server",
            "version": "1.0.0",
            "tools_available": 5,
            "notifications_enabled": False,
            "docker_available": True,
            "strict_security_mode": True,
            "policy_loaded": True,
            "uptime_seconds": 3600
        }
        
        response = HealthResponse(**health_data)
        assert response.status == "ok"
        assert response.server_name == "test-server"
        assert response.version == "1.0.0"
        assert response.tools_available == 5
        assert response.docker_available is True
        assert response.policy_loaded is True


@pytest.mark.unit
@pytest.mark.http
@pytest.mark.skipif(not HTTP_BRIDGE_AVAILABLE, reason="HTTP bridge not available")
class TestHTTPBridgeUtilities:
    """Test utility functions for HTTP bridge."""

    def test_normalize_mcp_request_direct_format(self):
        """Test request normalization for direct format."""
        request = MCPRequest(
            id="test-1",
            method="call_tool",
            name="disk_space",
            args={"path": "/"}
        )
        
        normalized = normalize_mcp_request(request)
        
        expected = {
            "id": "test-1",
            "method": "call_tool",
            "name": "disk_space",
            "args": {"path": "/"}
        }
        
        assert normalized == expected

    def test_normalize_mcp_request_params_format(self):
        """Test request normalization for params format."""
        request = MCPRequest(
            id="test-2",
            method="call_tool",
            params={"name": "disk_space", "args": {"path": "/"}}
        )
        
        normalized = normalize_mcp_request(request)
        
        expected = {
            "id": "test-2",
            "method": "call_tool",
            "name": "disk_space",
            "args": {"path": "/"}
        }
        
        assert normalized == expected

    def test_normalize_mcp_request_list_tools(self):
        """Test request normalization for list_tools."""
        request = MCPRequest(
            id="test-3",
            method="list_tools",
            params={}
        )
        
        normalized = normalize_mcp_request(request)
        
        expected = {
            "id": "test-3",
            "method": "list_tools",
            "params": {}
        }
        
        assert normalized == expected

    def test_sanitize_mcp_request_data_valid(self):
        """Test request data sanitization with valid data."""
        request_data = {
            "id": "test-1",
            "method": "call_tool",
            "name": "disk_space",
            "args": {"path": "/"}
        }
        
        # Should not raise exception
        sanitized = sanitize_mcp_request_data(request_data)
        assert sanitized == request_data

    def test_sanitize_mcp_request_data_too_large(self):
        """Test request data sanitization with oversized request."""
        # Create a request that's too large
        large_data = "x" * 20000  # 20KB of data
        request_data = {
            "id": "test-2",
            "method": "call_tool",
            "name": "test_tool",
            "args": {"large_field": large_data}
        }
        
        with pytest.raises(ValueError, match="Request too large"):
            sanitize_mcp_request_data(request_data)

    def test_sanitize_mcp_request_data_invalid_tool_name(self):
        """Test request data sanitization with invalid tool name."""
        request_data = {
            "id": "test-3",
            "method": "call_tool",
            "name": "invalid-tool!",  # Invalid characters
            "args": {}
        }
        
        with pytest.raises(ValueError, match="Tool name contains invalid characters"):
            sanitize_mcp_request_data(request_data)

    def test_sanitize_mcp_request_data_complex_args(self):
        """Test request data sanitization with overly complex arguments."""
        # Create deeply nested arguments
        nested_args = {"level1": {"level2": {"level3": {"level4": {"level5": {"level6": "too deep"}}}}}}
        request_data = {
            "id": "test-4",
            "method": "call_tool",
            "name": "test_tool",
            "args": nested_args
        }
        
        with pytest.raises(ValueError, match="Arguments too deeply nested"):
            sanitize_mcp_request_data(request_data)


@pytest.mark.unit
@pytest.mark.http
@pytest.mark.skipif(not HTTP_BRIDGE_AVAILABLE, reason="HTTP bridge not available")
class TestHTTPBridgeEndpoints:
    """Test HTTP bridge endpoints using FastAPI TestClient."""

    @pytest.fixture
    def client(self, mock_http_bridge_config):
        """Create test client with mocked configuration."""
        return TestClient(app)

    @patch('http_bridge.test_mcp_engine', new_callable=AsyncMock)
    @patch('http_bridge.check_docker_availability')
    @patch('http_bridge.check_notifications_configured')
    @patch('http_bridge.check_policy_loaded')
    def test_health_endpoint_ok_status(self, mock_policy, mock_notifications, 
                                      mock_docker, mock_mcp_test, client):
        """Test /health endpoint returns ok status when all systems healthy."""
        # Clear health cache to ensure fresh test
        import http_bridge
        http_bridge._health_cache = None
        http_bridge._health_cache_time = 0
        
        # Mock all checks to return healthy status
        mock_mcp_test.return_value = {"ok": True, "tools_count": 5}
        mock_docker.return_value = True
        mock_notifications.return_value = False
        mock_policy.return_value = True
        
        response = client.get("/health")
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["status"] == "ok"
        assert data["server_name"] == "test-burly-mcp"
        assert data["version"] == "0.0.1-test"
        assert data["tools_available"] == 5
        assert data["docker_available"] is True
        assert data["notifications_enabled"] is False
        assert data["policy_loaded"] is True
        assert data["strict_security_mode"] is True
        assert "uptime_seconds" in data

    @patch('http_bridge.test_mcp_engine', new_callable=AsyncMock)
    @patch('http_bridge.check_policy_loaded')
    def test_health_endpoint_degraded_status(self, mock_policy, mock_mcp_test, client):
        """Test /health endpoint returns degraded status when MCP engine fails."""
        # Clear health cache to ensure fresh test
        import http_bridge
        http_bridge._health_cache = None
        http_bridge._health_cache_time = 0
        
        # Mock MCP engine failure but policy loaded
        mock_mcp_test.return_value = {"ok": False, "tools_count": 0}
        mock_policy.return_value = True
        
        response = client.get("/health")
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["status"] == "degraded"
        assert data["tools_available"] == 0

    @patch('http_bridge.test_mcp_engine', new_callable=AsyncMock)
    @patch('http_bridge.check_policy_loaded')
    def test_health_endpoint_error_status(self, mock_policy, mock_mcp_test, client):
        """Test /health endpoint returns error status when both MCP and policy fail."""
        # Clear health cache to ensure fresh test
        import http_bridge
        http_bridge._health_cache = None
        http_bridge._health_cache_time = 0
        
        # Mock both MCP engine and policy failure
        mock_mcp_test.return_value = {"ok": False, "tools_count": 0}
        mock_policy.return_value = False
        
        response = client.get("/health")
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["status"] == "error"

    @patch('http_bridge.forward_to_mcp_engine')
    def test_mcp_endpoint_list_tools(self, mock_forward, client, mock_mcp_engine_response):
        """Test /mcp endpoint with list_tools request."""
        mock_forward.return_value = mock_mcp_engine_response
        
        request_data = {
            "id": "test-1",
            "method": "list_tools",
            "params": {}
        }
        
        response = client.post("/mcp", json=request_data)
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["ok"] is True
        assert data["summary"] == "Operation completed successfully"
        assert "tools" in data["data"]
        assert "metrics" in data
        assert data["metrics"]["elapsed_ms"] == 150

    @patch('http_bridge.forward_to_mcp_engine')
    def test_mcp_endpoint_call_tool_direct_format(self, mock_forward, client, mock_mcp_engine_response):
        """Test /mcp endpoint with call_tool in direct format."""
        mock_forward.return_value = mock_mcp_engine_response
        
        request_data = {
            "id": "test-2",
            "method": "call_tool",
            "name": "disk_space",
            "args": {"path": "/"}
        }
        
        response = client.post("/mcp", json=request_data)
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["ok"] is True
        # Verify the request was normalized correctly
        mock_forward.assert_called_once()
        normalized_request = mock_forward.call_args[0][0]
        assert normalized_request["method"] == "call_tool"
        assert normalized_request["name"] == "disk_space"
        assert normalized_request["args"] == {"path": "/"}

    @patch('http_bridge.forward_to_mcp_engine')
    def test_mcp_endpoint_call_tool_params_format(self, mock_forward, client, mock_mcp_engine_response):
        """Test /mcp endpoint with call_tool in params format."""
        mock_forward.return_value = mock_mcp_engine_response
        
        request_data = {
            "id": "test-3",
            "method": "call_tool",
            "params": {
                "name": "disk_space",
                "args": {"path": "/"}
            }
        }
        
        response = client.post("/mcp", json=request_data)
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["ok"] is True
        # Verify the request was normalized correctly
        mock_forward.assert_called_once()
        normalized_request = mock_forward.call_args[0][0]
        assert normalized_request["method"] == "call_tool"
        assert normalized_request["name"] == "disk_space"
        assert normalized_request["args"] == {"path": "/"}

    @patch('http_bridge.forward_to_mcp_engine')
    def test_mcp_endpoint_error_response(self, mock_forward, client, mock_mcp_engine_error_response):
        """Test /mcp endpoint with error response from MCP engine."""
        mock_forward.return_value = mock_mcp_engine_error_response
        
        request_data = {
            "id": "test-4",
            "method": "call_tool",
            "name": "nonexistent_tool",
            "args": {}
        }
        
        response = client.post("/mcp", json=request_data)
        
        # Should still return HTTP 200 (per requirements)
        assert response.status_code == 200
        data = response.json()
        
        assert data["ok"] is False
        assert data["summary"] == "Tool execution failed"
        assert "not found" in data["error"]
        assert data["metrics"]["exit_code"] == 1

    def test_mcp_endpoint_invalid_method(self, client):
        """Test /mcp endpoint with invalid method."""
        request_data = {
            "id": "test-5",
            "method": "invalid_method"
        }
        
        response = client.post("/mcp", json=request_data)
        
        # Should return HTTP 200 with error in body (per MCP bridge design)
        assert response.status_code == 200
        data = response.json()
        assert data["ok"] is False
        assert "validation" in data["summary"].lower() or "invalid" in data["error"].lower()

    def test_mcp_endpoint_invalid_tool_name(self, client):
        """Test /mcp endpoint with invalid tool name."""
        request_data = {
            "id": "test-6",
            "method": "call_tool",
            "name": "invalid-tool!",
            "args": {}
        }
        
        response = client.post("/mcp", json=request_data)
        
        # Should return HTTP 200 with error in body (per MCP bridge design)
        assert response.status_code == 200
        data = response.json()
        assert data["ok"] is False
        assert "validation" in data["summary"].lower() or "invalid" in data["error"].lower()

    def test_mcp_endpoint_oversized_request(self, client):
        """Test /mcp endpoint with oversized request."""
        # Create a large request
        large_data = "x" * 15000  # 15KB of data
        request_data = {
            "id": "test-7",
            "method": "call_tool",
            "name": "test_tool",
            "args": {"large_field": large_data}
        }
        
        response = client.post("/mcp", json=request_data)
        
        # Should return HTTP 200 with error in body (per requirements)
        assert response.status_code == 200
        data = response.json()
        
        assert data["ok"] is False
        assert "exceeds maximum size" in data["error"].lower()

    @patch('http_bridge.forward_to_mcp_engine')
    def test_mcp_endpoint_always_returns_200(self, mock_forward, client):
        """Test that /mcp endpoint always returns HTTP 200 even on internal errors."""
        # Mock forward_to_mcp_engine to raise an exception
        mock_forward.side_effect = Exception("Internal error")
        
        request_data = {
            "id": "test-8",
            "method": "list_tools",
            "params": {}
        }
        
        response = client.post("/mcp", json=request_data)
        
        # Should still return HTTP 200 (per requirements)
        assert response.status_code == 200
        data = response.json()
        
        assert data["ok"] is False
        assert "processing failed" in data["summary"].lower()
        assert "metrics" in data
        assert data["metrics"]["exit_code"] == 1


@pytest.mark.unit
@pytest.mark.http
@pytest.mark.skipif(not HTTP_BRIDGE_AVAILABLE, reason="HTTP bridge not available")
class TestHTTPBridgeMCPEngineIntegration:
    """Test HTTP bridge integration with MCP engine (mocked)."""

    @pytest.mark.asyncio
    @patch('http_bridge.asyncio.create_subprocess_exec')
    async def test_forward_to_mcp_engine_success(self, mock_subprocess):
        """Test successful communication with MCP engine."""
        # Mock subprocess
        mock_process = AsyncMock()
        mock_process.returncode = 0
        mock_process.communicate.return_value = (
            b'{"ok": true, "summary": "Success", "data": {"tools": []}}',
            b''
        )
        mock_subprocess.return_value = mock_process
        
        request = {
            "id": "test-1",
            "method": "list_tools",
            "params": {}
        }
        
        response = await forward_to_mcp_engine(request)
        
        assert response["ok"] is True
        assert response["summary"] == "Success"
        assert "metrics" in response
        assert "elapsed_ms" in response["metrics"]

    @pytest.mark.asyncio
    @patch('http_bridge.asyncio.create_subprocess_exec')
    async def test_forward_to_mcp_engine_process_failure(self, mock_subprocess):
        """Test MCP engine process failure."""
        # Mock subprocess failure
        mock_process = AsyncMock()
        mock_process.returncode = 1
        mock_process.communicate.return_value = (
            b'',
            b'Process failed with error'
        )
        mock_subprocess.return_value = mock_process
        
        request = {
            "id": "test-2",
            "method": "list_tools",
            "params": {}
        }
        
        response = await forward_to_mcp_engine(request)
        
        assert response["ok"] is False
        assert "process failed" in response["summary"].lower()
        assert response["metrics"]["exit_code"] == 1

    @pytest.mark.asyncio
    @patch('http_bridge.asyncio.create_subprocess_exec')
    async def test_forward_to_mcp_engine_timeout(self, mock_subprocess):
        """Test MCP engine timeout handling."""
        # Mock subprocess timeout
        mock_process = AsyncMock()
        mock_process.communicate.side_effect = asyncio.TimeoutError()
        mock_process.kill = AsyncMock()
        mock_process.wait = AsyncMock()
        mock_subprocess.return_value = mock_process
        
        request = {
            "id": "test-3",
            "method": "list_tools",
            "params": {}
        }
        
        response = await forward_to_mcp_engine(request)
        
        assert response["ok"] is False
        assert "timeout" in response["summary"].lower()
        assert response["metrics"]["exit_code"] == 124

    @pytest.mark.asyncio
    @patch('http_bridge.asyncio.create_subprocess_exec')
    async def test_forward_to_mcp_engine_invalid_json(self, mock_subprocess):
        """Test MCP engine invalid JSON response."""
        # Mock subprocess with invalid JSON
        mock_process = AsyncMock()
        mock_process.returncode = 0
        mock_process.communicate.return_value = (
            b'invalid json response',
            b''
        )
        mock_subprocess.return_value = mock_process
        
        request = {
            "id": "test-4",
            "method": "list_tools",
            "params": {}
        }
        
        response = await forward_to_mcp_engine(request)
        
        assert response["ok"] is False
        assert "parsing failed" in response["summary"].lower()
        assert "invalid json" in response["error"].lower()