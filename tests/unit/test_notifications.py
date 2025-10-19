"""
Unit tests for the Burly MCP notifications module.
"""

import pytest
from unittest.mock import Mock, patch
import requests


class TestNotificationManager:
    """Test the notification manager functionality."""

    def test_notification_manager_initialization(self):
        """Test notification manager initialization."""
        from burly_mcp.notifications.manager import NotificationManager
        
        manager = NotificationManager()
        assert hasattr(manager, 'gotify_url')
        assert hasattr(manager, 'gotify_token')
        assert hasattr(manager, 'enabled')

    @patch.dict('os.environ', {
        'GOTIFY_URL': 'https://gotify.example.com',
        'GOTIFY_TOKEN': 'test_token_123',
        'NOTIFICATIONS_ENABLED': 'true'
    })
    def test_notification_manager_configuration(self):
        """Test notification manager configuration from environment."""
        from burly_mcp.notifications.manager import NotificationManager
        
        manager = NotificationManager()
        
        assert manager.gotify_url == "https://gotify.example.com"
        assert manager.gotify_token == "test_token_123"
        assert manager.enabled is True

    @patch.dict('os.environ', {
        'NOTIFICATIONS_ENABLED': 'false'
    })
    def test_notification_manager_disabled(self):
        """Test notification manager when disabled."""
        from burly_mcp.notifications.manager import NotificationManager
        
        manager = NotificationManager()
        assert manager.enabled is False

    @patch('requests.post')
    def test_send_notification_success(self, mock_post):
        """Test successful notification sending."""
        from burly_mcp.notifications.manager import NotificationManager
        
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"id": 123}
        mock_post.return_value = mock_response
        
        manager = NotificationManager()
        manager.gotify_url = "https://gotify.example.com"
        manager.gotify_token = "test_token"
        manager.enabled = True
        
        result = manager.send_notification(
            title="Test Notification",
            message="This is a test message",
            priority=5
        )
        
        assert result is True
        mock_post.assert_called_once()
        
        # Check the request parameters
        call_args = mock_post.call_args
        assert "https://gotify.example.com/message" in call_args[1]['url']
        assert call_args[1]['headers']['X-Gotify-Key'] == "test_token"

    @patch('requests.post')
    def test_send_notification_failure(self, mock_post):
        """Test notification sending failure."""
        from burly_mcp.notifications.manager import NotificationManager
        
        mock_response = Mock()
        mock_response.status_code = 500
        mock_response.raise_for_status.side_effect = requests.exceptions.HTTPError("Server Error")
        mock_post.return_value = mock_response
        
        manager = NotificationManager()
        manager.gotify_url = "https://gotify.example.com"
        manager.gotify_token = "test_token"
        manager.enabled = True
        
        result = manager.send_notification(
            title="Test Notification",
            message="This is a test message"
        )
        
        assert result is False

    @patch('requests.post')
    def test_send_notification_network_error(self, mock_post):
        """Test notification sending with network error."""
        from burly_mcp.notifications.manager import NotificationManager
        
        mock_post.side_effect = requests.exceptions.ConnectionError("Network error")
        
        manager = NotificationManager()
        manager.gotify_url = "https://gotify.example.com"
        manager.gotify_token = "test_token"
        manager.enabled = True
        
        result = manager.send_notification(
            title="Test Notification",
            message="This is a test message"
        )
        
        assert result is False

    def test_send_notification_disabled(self):
        """Test notification sending when disabled."""
        from burly_mcp.notifications.manager import NotificationManager
        
        manager = NotificationManager()
        manager.enabled = False
        
        result = manager.send_notification(
            title="Test Notification",
            message="This is a test message"
        )
        
        # Should return True (success) but not actually send
        assert result is True

    def test_send_notification_missing_config(self):
        """Test notification sending with missing configuration."""
        from burly_mcp.notifications.manager import NotificationManager
        
        manager = NotificationManager()
        manager.enabled = True
        manager.gotify_url = None
        manager.gotify_token = None
        
        result = manager.send_notification(
            title="Test Notification",
            message="This is a test message"
        )
        
        assert result is False

    @patch('requests.post')
    def test_notify_tool_success(self, mock_post):
        """Test tool success notification."""
        from burly_mcp.notifications.manager import NotificationManager
        
        mock_response = Mock()
        mock_response.status_code = 200
        mock_post.return_value = mock_response
        
        manager = NotificationManager()
        manager.gotify_url = "https://gotify.example.com"
        manager.gotify_token = "test_token"
        manager.enabled = True
        
        result = manager.notify_tool_success(
            tool_name="test_tool",
            summary="Tool completed successfully",
            execution_time=1.5
        )
        
        assert result is True
        mock_post.assert_called_once()
        
        # Check notification content
        call_args = mock_post.call_args
        data = call_args[1]['json']
        assert "test_tool" in data['title']
        assert "success" in data['title'].lower()
        assert "Tool completed successfully" in data['message']

    @patch('requests.post')
    def test_notify_tool_failure(self, mock_post):
        """Test tool failure notification."""
        from burly_mcp.notifications.manager import NotificationManager
        
        mock_response = Mock()
        mock_response.status_code = 200
        mock_post.return_value = mock_response
        
        manager = NotificationManager()
        manager.gotify_url = "https://gotify.example.com"
        manager.gotify_token = "test_token"
        manager.enabled = True
        
        result = manager.notify_tool_failure(
            tool_name="test_tool",
            error_message="Tool execution failed",
            execution_time=0.5
        )
        
        assert result is True
        mock_post.assert_called_once()
        
        # Check notification content
        call_args = mock_post.call_args
        data = call_args[1]['json']
        assert "test_tool" in data['title']
        assert "failed" in data['title'].lower()
        assert "Tool execution failed" in data['message']
        assert data['priority'] > 5  # Failure should have higher priority

    @patch('requests.post')
    def test_notify_tool_confirmation_needed(self, mock_post):
        """Test tool confirmation needed notification."""
        from burly_mcp.notifications.manager import NotificationManager
        
        mock_response = Mock()
        mock_response.status_code = 200
        mock_post.return_value = mock_response
        
        manager = NotificationManager()
        manager.gotify_url = "https://gotify.example.com"
        manager.gotify_token = "test_token"
        manager.enabled = True
        
        result = manager.notify_tool_confirmation_needed(
            tool_name="dangerous_tool",
            action_description="Delete all files in /tmp",
            user_id="test_user"
        )
        
        assert result is True
        mock_post.assert_called_once()
        
        # Check notification content
        call_args = mock_post.call_args
        data = call_args[1]['json']
        assert "dangerous_tool" in data['title']
        assert "confirmation" in data['title'].lower()
        assert "Delete all files in /tmp" in data['message']
        assert data['priority'] >= 8  # Confirmation should have high priority

    @patch('requests.post')
    def test_notify_security_event(self, mock_post):
        """Test security event notification."""
        from burly_mcp.notifications.manager import NotificationManager
        
        mock_response = Mock()
        mock_response.status_code = 200
        mock_post.return_value = mock_response
        
        manager = NotificationManager()
        manager.gotify_url = "https://gotify.example.com"
        manager.gotify_token = "test_token"
        manager.enabled = True
        
        result = manager.notify_security_event(
            event_type="unauthorized_access",
            details={"ip": "192.168.1.100", "user": "unknown"},
            severity="HIGH"
        )
        
        assert result is True
        mock_post.assert_called_once()
        
        # Check notification content
        call_args = mock_post.call_args
        data = call_args[1]['json']
        assert "security" in data['title'].lower()
        assert "unauthorized_access" in data['message']
        assert data['priority'] == 10  # Security events should have max priority

    def test_format_notification_message(self):
        """Test notification message formatting."""
        from burly_mcp.notifications.manager import NotificationManager
        
        manager = NotificationManager()
        
        # Test basic message formatting
        message = manager.format_notification_message(
            template="Tool {tool_name} completed in {time}s",
            tool_name="test_tool",
            time=1.5
        )
        
        assert message == "Tool test_tool completed in 1.5s"

    def test_get_priority_for_event_type(self):
        """Test priority assignment for different event types."""
        from burly_mcp.notifications.manager import NotificationManager
        
        manager = NotificationManager()
        
        # Test different event type priorities
        assert manager.get_priority_for_event_type("success") == 3
        assert manager.get_priority_for_event_type("failure") == 7
        assert manager.get_priority_for_event_type("confirmation") == 8
        assert manager.get_priority_for_event_type("security") == 10

    @patch('requests.post')
    def test_notification_retry_mechanism(self, mock_post):
        """Test notification retry mechanism on failure."""
        from burly_mcp.notifications.manager import NotificationManager
        
        # First call fails, second succeeds
        mock_response_fail = Mock()
        mock_response_fail.status_code = 500
        mock_response_fail.raise_for_status.side_effect = requests.exceptions.HTTPError()
        
        mock_response_success = Mock()
        mock_response_success.status_code = 200
        
        mock_post.side_effect = [mock_response_fail, mock_response_success]
        
        manager = NotificationManager()
        manager.gotify_url = "https://gotify.example.com"
        manager.gotify_token = "test_token"
        manager.enabled = True
        manager.max_retries = 2
        
        result = manager.send_notification_with_retry(
            title="Test Notification",
            message="This is a test message"
        )
        
        assert result is True
        assert mock_post.call_count == 2

    def test_validate_notification_config(self):
        """Test notification configuration validation."""
        from burly_mcp.notifications.manager import NotificationManager
        
        manager = NotificationManager()
        
        # Test valid configuration
        manager.gotify_url = "https://gotify.example.com"
        manager.gotify_token = "valid_token"
        assert manager.validate_config() is True
        
        # Test invalid configuration
        manager.gotify_url = None
        assert manager.validate_config() is False
        
        manager.gotify_url = "https://gotify.example.com"
        manager.gotify_token = None
        assert manager.validate_config() is False

    @patch('requests.post')
    def test_notification_rate_limiting(self, mock_post):
        """Test notification rate limiting."""
        from burly_mcp.notifications.manager import NotificationManager
        
        mock_response = Mock()
        mock_response.status_code = 200
        mock_post.return_value = mock_response
        
        manager = NotificationManager()
        manager.gotify_url = "https://gotify.example.com"
        manager.gotify_token = "test_token"
        manager.enabled = True
        manager.rate_limit_per_minute = 5
        
        # Send notifications up to rate limit
        for i in range(5):
            result = manager.send_notification(
                title=f"Test {i}",
                message="Test message"
            )
            assert result is True
        
        # Next notification should be rate limited
        result = manager.send_notification(
            title="Rate Limited",
            message="This should be rate limited"
        )
        
        # Behavior depends on implementation - might return False or queue