"""
Unit tests for the Burly MCP server components.
"""

import pytest
from unittest.mock import Mock, patch
from burly_mcp.server.mcp import MCPRequest, MCPResponse, MCPProtocolHandler


class TestMCPRequest:
    """Test MCP request parsing and validation."""
    
    def test_valid_request_parsing(self):
        """Test parsing of valid MCP requests."""
        json_data = {
            "method": "list_tools"
        }
        request = MCPRequest.from_json(json_data)
        assert request.method == "list_tools"
        assert request.name is None
        assert request.args == {}
    
    def test_call_tool_request_parsing(self):
        """Test parsing of call_tool requests."""
        json_data = {
            "method": "call_tool",
            "name": "disk_space",
            "args": {"path": "/tmp"}
        }
        request = MCPRequest.from_json(json_data)
        assert request.method == "call_tool"
        assert request.name == "disk_space"
        assert request.args == {"path": "/tmp"}
    
    def test_missing_method_raises_error(self):
        """Test that missing method raises ValueError."""
        json_data = {"name": "test"}
        with pytest.raises(ValueError, match="Missing required field: method"):
            MCPRequest.from_json(json_data)
    
    def test_unsupported_method_raises_error(self):
        """Test that unsupported method raises ValueError."""
        json_data = {"method": "unsupported_method"}
        with pytest.raises(ValueError, match="Unsupported method"):
            MCPRequest.from_json(json_data)


class TestMCPResponse:
    """Test MCP response creation and serialization."""
    
    def test_success_response_creation(self):
        """Test creation of success responses."""
        response = MCPResponse.create_success(
            summary="Test completed",
            data={"result": "success"},
            stdout="Test output"
        )
        assert response.ok is True
        assert response.summary == "Test completed"
        assert response.data == {"result": "success"}
        assert response.stdout == "Test output"
        assert response.metrics["exit_code"] == 0
    
    def test_error_response_creation(self):
        """Test creation of error responses."""
        response = MCPResponse.create_error(
            error_msg="Test failed",
            summary="Operation failed",
            exit_code=1
        )
        assert response.ok is False
        assert response.error == "Test failed"
        assert response.summary == "Operation failed"
        assert response.metrics["exit_code"] == 1
    
    def test_response_serialization(self):
        """Test response serialization to JSON."""
        response = MCPResponse.create_success(
            summary="Test completed",
            data={"test": True}
        )
        json_data = response.to_json()
        
        assert json_data["ok"] is True
        assert json_data["summary"] == "Test completed"
        assert json_data["data"] == {"test": True}
        assert "metrics" in json_data
    
    def test_output_truncation(self):
        """Test that long output gets truncated."""
        long_output = "x" * 20000  # Longer than default limit
        response = MCPResponse(
            ok=True,
            stdout=long_output
        )
        
        assert len(response.stdout) < len(long_output)
        assert "[truncated: output too long]" in response.stdout


class TestMCPProtocolHandler:
    """Test MCP protocol handler functionality."""
    
    def test_handler_initialization(self):
        """Test protocol handler initialization."""
        mock_registry = Mock()
        handler = MCPProtocolHandler(tool_registry=mock_registry)
        
        assert handler.tool_registry == mock_registry
        assert hasattr(handler, '_request_times')
    
    @patch('sys.stdin')
    def test_read_request_success(self, mock_stdin):
        """Test successful request reading."""
        mock_stdin.readline.return_value = '{"method": "list_tools"}\n'
        
        handler = MCPProtocolHandler()
        request = handler.read_request()
        
        assert request is not None
        assert request.method == "list_tools"
    
    @patch('sys.stdin')
    def test_read_request_eof(self, mock_stdin):
        """Test EOF handling in request reading."""
        mock_stdin.readline.return_value = ''
        
        handler = MCPProtocolHandler()
        request = handler.read_request()
        
        assert request is None
    
    @patch('sys.stdin')
    def test_read_request_invalid_json(self, mock_stdin):
        """Test invalid JSON handling."""
        mock_stdin.readline.return_value = 'invalid json\n'
        
        handler = MCPProtocolHandler()
        with pytest.raises(ValueError, match="Invalid JSON"):
            handler.read_request()
    
    def test_handle_list_tools_no_registry(self):
        """Test list_tools handling without registry."""
        handler = MCPProtocolHandler()
        request = MCPRequest(method="list_tools")
        
        response = handler.handle_request(request)
        
        assert response.ok is False
        assert "Tool registry not initialized" in response.error
    
    def test_handle_unsupported_method(self):
        """Test handling of unsupported methods."""
        handler = MCPProtocolHandler()
        request = MCPRequest(method="unsupported")
        
        response = handler.handle_request(request)
        
        assert response.ok is False
        assert "Unsupported method" in response.error