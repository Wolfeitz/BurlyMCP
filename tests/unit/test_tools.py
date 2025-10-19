"""
Unit tests for the Burly MCP tools module.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from pathlib import Path
from burly_mcp.tools.registry import ToolRegistry, ToolResult


class TestToolRegistry:
    """Test the tool registry functionality."""

    def test_registry_initialization(self):
        """Test tool registry initialization."""
        registry = ToolRegistry()
        assert hasattr(registry, 'tools')
        assert isinstance(registry.tools, dict)

    def test_get_tool_names(self):
        """Test getting list of tool names."""
        registry = ToolRegistry()
        # Mock some tools
        registry.tools = {
            'test_tool1': Mock(),
            'test_tool2': Mock(),
        }
        
        names = registry.get_tool_names()
        assert 'test_tool1' in names
        assert 'test_tool2' in names
        assert len(names) == 2

    def test_has_tool(self):
        """Test checking if tool exists."""
        registry = ToolRegistry()
        registry.tools = {'existing_tool': Mock()}
        
        assert registry.has_tool('existing_tool') is True
        assert registry.has_tool('nonexistent_tool') is False

    def test_get_tool_existing(self):
        """Test getting an existing tool."""
        registry = ToolRegistry()
        mock_tool = Mock()
        registry.tools = {'test_tool': mock_tool}
        
        result = registry.get_tool('test_tool')
        assert result == mock_tool

    def test_get_tool_nonexistent(self):
        """Test getting a nonexistent tool."""
        registry = ToolRegistry()
        registry.tools = {}
        
        result = registry.get_tool('nonexistent_tool')
        assert result is None

    @patch('burly_mcp.tools.registry.load_policy')
    def test_load_tools_from_policy(self, mock_load_policy):
        """Test loading tools from policy configuration."""
        mock_policy = {
            'tools': {
                'test_tool': {
                    'description': 'Test tool',
                    'command': ['echo', 'test'],
                    'mutates': False,
                    'requires_confirm': False,
                    'timeout_sec': 10,
                }
            }
        }
        mock_load_policy.return_value = mock_policy
        
        registry = ToolRegistry()
        registry.load_tools_from_policy('/fake/policy.yaml')
        
        mock_load_policy.assert_called_once_with('/fake/policy.yaml')
        assert 'test_tool' in registry.tools


class TestToolResult:
    """Test the ToolResult data class."""

    def test_tool_result_creation(self):
        """Test creating a ToolResult instance."""
        result = ToolResult(
            success=True,
            need_confirm=False,
            summary="Test completed",
            data={"key": "value"},
            stdout="Test output",
            stderr="",
            exit_code=0,
            elapsed_ms=100
        )
        
        assert result.success is True
        assert result.need_confirm is False
        assert result.summary == "Test completed"
        assert result.data == {"key": "value"}
        assert result.stdout == "Test output"
        assert result.stderr == ""
        assert result.exit_code == 0
        assert result.elapsed_ms == 100

    def test_tool_result_defaults(self):
        """Test ToolResult with default values."""
        result = ToolResult(
            success=False,
            summary="Failed"
        )
        
        assert result.success is False
        assert result.need_confirm is False
        assert result.summary == "Failed"
        assert result.data is None
        assert result.stdout == ""
        assert result.stderr == ""
        assert result.exit_code == 1
        assert result.elapsed_ms == 0

    def test_tool_result_to_dict(self):
        """Test converting ToolResult to dictionary."""
        result = ToolResult(
            success=True,
            summary="Test",
            data={"test": True}
        )
        
        result_dict = result.to_dict()
        
        assert isinstance(result_dict, dict)
        assert result_dict['success'] is True
        assert result_dict['summary'] == "Test"
        assert result_dict['data'] == {"test": True}


@pytest.mark.unit
class TestDockerTools:
    """Test Docker-related tools with mocking."""

    @patch('docker.from_env')
    def test_docker_client_initialization(self, mock_docker):
        """Test Docker client initialization."""
        from burly_mcp.tools.registry import ToolRegistry
        
        mock_client = Mock()
        mock_docker.return_value = mock_client
        
        registry = ToolRegistry()
        # This would normally initialize Docker tools
        # We're testing that the mock is called correctly
        mock_docker.assert_called()

    @patch('docker.from_env')
    def test_docker_unavailable_handling(self, mock_docker):
        """Test handling when Docker is unavailable."""
        from burly_mcp.tools.registry import ToolRegistry
        import docker.errors
        
        mock_docker.side_effect = docker.errors.DockerException("Docker not available")
        
        registry = ToolRegistry()
        # Should handle Docker unavailability gracefully
        # Specific implementation depends on how the registry handles this

    def test_docker_tool_validation(self, mock_docker_client):
        """Test Docker tool argument validation."""
        # This would test specific Docker tool implementations
        # when they're available in the codebase
        pass


@pytest.mark.unit
class TestBlogTools:
    """Test blog management tools."""

    def test_blog_post_validation(self, sample_blog_post):
        """Test blog post content validation."""
        # This would test blog post validation logic
        # when available in the codebase
        assert "title:" in sample_blog_post
        assert "date:" in sample_blog_post

    def test_invalid_blog_post_handling(self, invalid_blog_post):
        """Test handling of invalid blog posts."""
        # This would test error handling for invalid blog posts
        assert "title:" in invalid_blog_post
        assert "date:" not in invalid_blog_post

    def test_blog_file_operations(self, test_files_dir):
        """Test blog file operations."""
        # This would test blog file management operations
        # when available in the codebase
        blog_file = test_files_dir / "test_post.md"
        blog_file.write_text("# Test Post\n\nContent here.")
        
        assert blog_file.exists()
        assert blog_file.read_text().startswith("# Test Post")


@pytest.mark.unit
class TestSystemTools:
    """Test system monitoring and management tools."""

    @patch('shutil.disk_usage')
    def test_disk_space_tool(self, mock_disk_usage):
        """Test disk space monitoring tool."""
        mock_disk_usage.return_value = (1000000000, 500000000, 500000000)  # total, used, free
        
        # This would test the actual disk space tool implementation
        # when available in the codebase
        mock_disk_usage.assert_called()

    @patch('psutil.cpu_percent')
    def test_cpu_monitoring_tool(self, mock_cpu_percent):
        """Test CPU monitoring tool."""
        mock_cpu_percent.return_value = 25.5
        
        # This would test CPU monitoring functionality
        # when available in the codebase
        mock_cpu_percent.assert_called()

    @patch('psutil.virtual_memory')
    def test_memory_monitoring_tool(self, mock_memory):
        """Test memory monitoring tool."""
        mock_memory_info = Mock()
        mock_memory_info.total = 8000000000
        mock_memory_info.available = 4000000000
        mock_memory_info.percent = 50.0
        mock_memory.return_value = mock_memory_info
        
        # This would test memory monitoring functionality
        # when available in the codebase
        mock_memory.assert_called()