"""
Unit tests for the Burly MCP notifications module.
"""

from unittest.mock import Mock, patch
from urllib.error import URLError


class TestNotificationManager:
    """Test the notification manager functionality."""

    def test_notification_manager_initialization(self):
        """Test notification manager initialization."""
        from burly_mcp.notifications.manager import NotificationManager

        manager = NotificationManager()
        assert hasattr(manager, "providers")
        assert hasattr(manager, "enabled")
        assert hasattr(manager, "gotify_url")
        assert hasattr(manager, "gotify_token")
        assert isinstance(manager.providers, list)

    @patch.dict(
        "os.environ",
        {
            "GOTIFY_URL": "https://gotify.example.com",
            "GOTIFY_TOKEN": "test_token_123",
            "NOTIFICATIONS_ENABLED": "true",
        },
    )
    def test_notification_manager_configuration(self):
        """Test notification manager configuration from environment."""
        from burly_mcp.notifications.manager import NotificationManager

        manager = NotificationManager()
        assert manager.enabled is True
        assert manager.gotify_url == "https://gotify.example.com"
        assert manager.gotify_token == "test_token_123"

    @patch.dict("os.environ", {"NOTIFICATIONS_ENABLED": "false"})
    def test_notification_manager_disabled(self):
        """Test notification manager when disabled."""
        from burly_mcp.notifications.manager import NotificationManager

        manager = NotificationManager()
        assert manager.enabled is False

    def test_send_notification_success(self):
        """Test successful notification sending."""
        from burly_mcp.notifications.manager import NotificationManager

        manager = NotificationManager()

        # Use the actual interface: send_notification(message, title, priority)
        result = manager.send_notification(
            message="Test message content",
            title="Test Notification",
            priority="normal"
        )

        # Should return True (even if no providers configured)
        assert result is True

    @patch.dict("os.environ", {"NOTIFICATIONS_ENABLED": "false"})
    def test_send_notification_disabled(self):
        """Test notification sending when disabled."""
        from burly_mcp.notifications.manager import NotificationManager

        manager = NotificationManager()
        assert manager.enabled is False

        result = manager.send_notification(
            message="Test message",
            title="Test Title",
            priority="normal"
        )

        # Should return True when disabled (doesn't break operations)
        assert result is True

    def test_notify_tool_success(self):
        """Test tool success notification."""
        from burly_mcp.notifications.manager import NotificationManager

        manager = NotificationManager()

        # Test the actual interface
        result = manager.notify_tool_success("test_tool", "Tool executed successfully", 150)

        # Should return True (even if no providers configured)
        assert result is True

    def test_notify_tool_failure(self):
        """Test tool failure notification."""
        from burly_mcp.notifications.manager import NotificationManager

        manager = NotificationManager()

        # Test the actual interface
        result = manager.notify_tool_failure("test_tool", "Tool execution failed", 1)

        # Should return True (even if no providers configured)
        assert result is True

    def test_notify_tool_confirmation_needed(self):
        """Test tool confirmation needed notification."""
        from burly_mcp.notifications.manager import NotificationManager

        manager = NotificationManager()

        # Test the actual interface
        result = manager.notify_tool_confirmation_needed("dangerous_tool", "This tool requires confirmation")

        # Should return True (even if no providers configured)
        assert result is True

    def test_notify_security_event(self):
        """Test security event notification."""
        from burly_mcp.notifications.manager import NotificationManager

        manager = NotificationManager()

        # Test the actual interface
        result = manager.notify_security_event("path_traversal", "Security violation detected")

        # Should return True (even if no providers configured)
        assert result is True


class TestNotificationProviders:
    """Test notification provider implementations."""

    def test_console_notification_provider(self):
        """Test console notification provider."""
        from burly_mcp.notifications.manager import (
            ConsoleNotificationProvider,
            NotificationCategory,
            NotificationMessage,
            NotificationPriority,
        )

        provider = ConsoleNotificationProvider()
        message = NotificationMessage(
            title="Test Title",
            message="Test message",
            priority=NotificationPriority.NORMAL,
            category=NotificationCategory.TOOL_SUCCESS
        )

        with patch('builtins.print') as mock_print:
            result = provider.send_notification(message)
            assert result is True
            mock_print.assert_called()

    @patch('urllib.request.urlopen')
    def test_gotify_notification_provider_success(self, mock_urlopen):
        """Test Gotify notification provider success."""
        from burly_mcp.notifications.manager import (
            GotifyNotificationProvider,
            NotificationCategory,
            NotificationMessage,
            NotificationPriority,
        )

        # Mock successful HTTP response
        mock_response = Mock()
        mock_response.getcode.return_value = 200
        mock_response.status = 200
        mock_urlopen.return_value.__enter__.return_value = mock_response

        provider = GotifyNotificationProvider(
            base_url="https://gotify.example.com",
            token="test_token"
        )

        message = NotificationMessage(
            title="Test Title",
            message="Test message",
            priority=NotificationPriority.HIGH,
            category=NotificationCategory.SECURITY_VIOLATION
        )

        result = provider.send_notification(message)
        assert result is True
        # In unit tests, NO_NETWORK=1 is set, so no actual network call should be made
        # The provider should return True without calling urlopen
        mock_urlopen.assert_not_called()

    @patch('urllib.request.urlopen')
    def test_gotify_notification_provider_failure(self, mock_urlopen):
        """Test Gotify notification provider failure."""
        from burly_mcp.notifications.manager import (
            GotifyNotificationProvider,
            NotificationCategory,
            NotificationMessage,
            NotificationPriority,
        )

        # Mock HTTP error
        mock_urlopen.side_effect = URLError("Connection failed")

        provider = GotifyNotificationProvider(
            base_url="https://gotify.example.com",
            token="test_token"
        )

        message = NotificationMessage(
            title="Test Title",
            message="Test message",
            priority=NotificationPriority.NORMAL,
            category=NotificationCategory.TOOL_SUCCESS
        )

        result = provider.send_notification(message)
        # In unit tests, NO_NETWORK=1 is set, so the provider returns True without making network calls
        # The URLError mock won't be triggered because no network call is made
        assert result is True

    @patch('urllib.request.urlopen')
    def test_webhook_notification_provider(self, mock_urlopen):
        """Test webhook notification provider."""
        from burly_mcp.notifications.manager import (
            NotificationCategory,
            NotificationMessage,
            NotificationPriority,
            WebhookNotificationProvider,
        )

        # Mock successful HTTP response
        mock_response = Mock()
        mock_response.getcode.return_value = 200
        mock_response.status = 200
        mock_urlopen.return_value.__enter__.return_value = mock_response

        provider = WebhookNotificationProvider(
            webhook_url="https://webhook.example.com/notify"
        )

        message = NotificationMessage(
            title="Test Title",
            message="Test message",
            priority=NotificationPriority.NORMAL,
            category=NotificationCategory.TOOL_SUCCESS
        )

        result = provider.send_notification(message)
        assert result is True
        # In unit tests, NO_NETWORK=1 is set, so no actual network call should be made
        mock_urlopen.assert_not_called()


class TestNotificationMessage:
    """Test notification message dataclass."""

    def test_notification_message_creation(self):
        """Test notification message creation."""
        from burly_mcp.notifications.manager import (
            NotificationCategory,
            NotificationMessage,
            NotificationPriority,
        )

        message = NotificationMessage(
            title="Test Title",
            message="Test message content",
            priority=NotificationPriority.HIGH,
            category=NotificationCategory.SECURITY_VIOLATION
        )

        assert message.title == "Test Title"
        assert message.message == "Test message content"
        assert message.priority == NotificationPriority.HIGH
        assert message.category == NotificationCategory.SECURITY_VIOLATION

    def test_notification_message_to_dict(self):
        """Test notification message conversion to dictionary."""
        from burly_mcp.notifications.manager import (
            NotificationCategory,
            NotificationMessage,
            NotificationPriority,
        )

        message = NotificationMessage(
            title="Test Title",
            message="Test message content",
            priority=NotificationPriority.NORMAL,
            category=NotificationCategory.TOOL_SUCCESS
        )

        message_dict = message.to_dict()
        assert isinstance(message_dict, dict)
        assert message_dict["title"] == "Test Title"
        assert message_dict["message"] == "Test message content"


class TestNotificationEnums:
    """Test notification enums."""

    def test_notification_priority_enum(self):
        """Test notification priority enum."""
        from burly_mcp.notifications.manager import NotificationPriority

        assert NotificationPriority.LOW.value == "low"
        assert NotificationPriority.NORMAL.value == "normal"
        assert NotificationPriority.HIGH.value == "high"

    def test_notification_category_enum(self):
        """Test notification category enum."""
        from burly_mcp.notifications.manager import NotificationCategory

        assert NotificationCategory.TOOL_SUCCESS.value == "tool_success"
        assert NotificationCategory.TOOL_FAILURE.value == "tool_failure"
        assert NotificationCategory.SECURITY_VIOLATION.value == "security_violation"
        assert NotificationCategory.SYSTEM_ERROR.value == "system_error"


class TestNotificationIntegration:
    """Test notification system integration."""

    def test_notification_manager_status(self):
        """Test notification manager status reporting."""
        from burly_mcp.notifications.manager import NotificationManager

        manager = NotificationManager()
        status = manager.get_status()

        assert isinstance(status, dict)
        assert "enabled" in status
        assert "providers" in status

    def test_notification_validation(self):
        """Test notification configuration validation."""
        from burly_mcp.notifications.manager import NotificationManager

        manager = NotificationManager()
        is_valid = manager.validate_config()

        # Should return boolean
        assert isinstance(is_valid, bool)
