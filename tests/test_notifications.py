"""
Notification System Tests

This module provides comprehensive tests for the notification system,
including Gotify API integration, failure handling, and priority assignment.
Tests cover all notification providers and the notification manager.
"""

import json
import os
import pytest
from unittest.mock import Mock, patch, MagicMock
from urllib.error import HTTPError, URLError

from server.notifications import (
    NotificationManager,
    NotificationMessage,
    NotificationPriority,
    NotificationCategory,
    GotifyNotificationProvider,
    ConsoleNotificationProvider,
    WebhookNotificationProvider,
    get_notification_manager,
)


class TestNotificationMessage:
    """Test NotificationMessage dataclass functionality."""

    def test_notification_message_creation(self):
        """Test creating a notification message with all fields."""
        message = NotificationMessage(
            title="Test Title",
            message="Test message content",
            priority=NotificationPriority.HIGH,
            category=NotificationCategory.TOOL_SUCCESS,
            tool_name="test_tool",
            metadata={"key": "value"},
        )

        assert message.title == "Test Title"
        assert message.message == "Test message content"
        assert message.priority == NotificationPriority.HIGH
        assert message.category == NotificationCategory.TOOL_SUCCESS
        assert message.tool_name == "test_tool"
        assert message.metadata == {"key": "value"}

    def test_notification_message_to_dict(self):
        """Test converting notification message to dictionary."""
        message = NotificationMessage(
            title="Test Title",
            message="Test message",
            priority=NotificationPriority.NORMAL,
            category=NotificationCategory.TOOL_FAILURE,
            tool_name="test_tool",
            metadata={"elapsed_ms": 150},
        )

        result = message.to_dict()

        assert result["title"] == "Test Title"
        assert result["message"] == "Test message"
        assert result["priority"] == "normal"
        assert result["category"] == "tool_failure"
        assert result["tool_name"] == "test_tool"
        assert result["metadata"]["elapsed_ms"] == 150

    def test_notification_message_minimal(self):
        """Test creating notification message with minimal required fields."""
        message = NotificationMessage(
            title="Minimal",
            message="Content",
            priority=NotificationPriority.LOW,
            category=NotificationCategory.AUDIT_EVENT,
        )

        assert message.tool_name is None
        assert message.metadata is None

        result = message.to_dict()
        assert result["tool_name"] is None
        assert result["metadata"] == {}


class TestConsoleNotificationProvider:
    """Test console notification provider."""

    def test_console_provider_is_available(self):
        """Test that console provider is always available."""
        provider = ConsoleNotificationProvider()
        assert provider.is_available() is True
        assert provider.get_provider_name() == "console"

    @patch("builtins.print")
    def test_console_provider_send_normal_priority(self, mock_print):
        """Test console provider sends normal priority to stdout."""
        provider = ConsoleNotificationProvider()
        message = NotificationMessage(
            title="Test Success",
            message="Operation completed",
            priority=NotificationPriority.NORMAL,
            category=NotificationCategory.TOOL_SUCCESS,
            tool_name="test_tool",
        )

        result = provider.send_notification(message)

        assert result is True
        mock_print.assert_called_once()
        call_args = mock_print.call_args[0][0]
        assert "📢 [TOOL_SUCCESS] Test Success" in call_args
        assert "(tool: test_tool)" in call_args
        assert "Operation completed" in call_args

    @patch("builtins.print")
    def test_console_provider_send_high_priority(self, mock_print):
        """Test console provider sends high priority to stderr."""
        provider = ConsoleNotificationProvider()
        message = NotificationMessage(
            title="Critical Error",
            message="System failure detected",
            priority=NotificationPriority.CRITICAL,
            category=NotificationCategory.SYSTEM_ERROR,
        )

        result = provider.send_notification(message)

        assert result is True
        mock_print.assert_called_once()
        # Verify stderr was used for critical priority
        call_kwargs = mock_print.call_args[1]
        assert call_kwargs.get("file") is not None  # stderr

    @patch("builtins.print")
    def test_console_provider_handles_exception(self, mock_print):
        """Test console provider handles print exceptions gracefully."""
        mock_print.side_effect = Exception("Print failed")
        provider = ConsoleNotificationProvider()
        message = NotificationMessage(
            title="Test",
            message="Test",
            priority=NotificationPriority.NORMAL,
            category=NotificationCategory.TOOL_SUCCESS,
        )

        result = provider.send_notification(message)

        assert result is False


class TestGotifyNotificationProvider:
    """Test Gotify notification provider."""

    def test_gotify_provider_initialization(self):
        """Test Gotify provider initialization with parameters."""
        provider = GotifyNotificationProvider(
            base_url="http://test.example.com", token="test_token_123"
        )

        assert provider.base_url == "http://test.example.com"
        assert provider.token == "test_token_123"
        assert provider.get_provider_name() == "gotify"

    def test_gotify_provider_initialization_from_env(self):
        """Test Gotify provider initialization from environment variables."""
        with patch.dict(
            os.environ,
            {
                "GOTIFY_URL": "http://env.example.com/",
                "GOTIFY_TOKEN": "env_token",
                "GOTIFY_TIMEOUT": "15",
            },
        ):
            provider = GotifyNotificationProvider()

            assert (
                provider.base_url == "http://env.example.com"
            )  # trailing slash removed
            assert provider.token == "env_token"
            assert provider.timeout == 15

    def test_gotify_provider_is_available(self):
        """Test Gotify provider availability check."""
        # Provider with both URL and token
        provider = GotifyNotificationProvider(
            base_url="http://test.example.com", token="test_token"
        )
        assert provider.is_available() is True

        # Provider missing URL
        provider = GotifyNotificationProvider(token="test_token")
        assert provider.is_available() is False

        # Provider missing token
        provider = GotifyNotificationProvider(base_url="http://test.example.com")
        assert provider.is_available() is False

    @patch("urllib.request.urlopen")
    def test_gotify_provider_send_success(self, mock_urlopen):
        """Test successful Gotify notification sending."""
        # Mock successful HTTP response
        mock_response = Mock()
        mock_response.status = 200
        mock_urlopen.return_value.__enter__.return_value = mock_response

        provider = GotifyNotificationProvider(
            base_url="http://test.example.com", token="test_token"
        )

        message = NotificationMessage(
            title="Test Notification",
            message="Test message content",
            priority=NotificationPriority.HIGH,
            category=NotificationCategory.TOOL_SUCCESS,
            tool_name="test_tool",
            metadata={"elapsed_ms": 250},
        )

        result = provider.send_notification(message)

        assert result is True
        mock_urlopen.assert_called_once()

        # Verify request details
        request = mock_urlopen.call_args[0][0]
        assert request.full_url == "http://test.example.com/message?token=test_token"
        assert request.get_method() == "POST"
        assert request.get_header("Content-type") == "application/json"

        # Verify payload
        payload = json.loads(request.data.decode("utf-8"))
        assert payload["title"] == "Test Notification"
        assert payload["message"] == "Test message content"
        assert payload["priority"] == 8  # HIGH priority maps to 8
        assert payload["extras"]["category"] == "tool_success"
        assert payload["extras"]["tool_name"] == "test_tool"
        assert payload["extras"]["metadata"]["elapsed_ms"] == 250

    def test_gotify_provider_priority_mapping(self):
        """Test priority level mapping to Gotify priorities."""
        provider = GotifyNotificationProvider(
            base_url="http://test.example.com", token="test_token"
        )

        test_cases = [
            (NotificationPriority.LOW, 2),
            (NotificationPriority.NORMAL, 5),
            (NotificationPriority.HIGH, 8),
            (NotificationPriority.CRITICAL, 10),
        ]

        with patch("urllib.request.urlopen") as mock_urlopen:
            mock_response = Mock()
            mock_response.status = 200
            mock_urlopen.return_value.__enter__.return_value = mock_response

            for priority, expected_gotify_priority in test_cases:
                message = NotificationMessage(
                    title="Test",
                    message="Test",
                    priority=priority,
                    category=NotificationCategory.TOOL_SUCCESS,
                )

                provider.send_notification(message)

                # Get the last request payload
                request = mock_urlopen.call_args[0][0]
                payload = json.loads(request.data.decode("utf-8"))
                assert payload["priority"] == expected_gotify_priority

    @patch("urllib.request.urlopen")
    def test_gotify_provider_http_error(self, mock_urlopen):
        """Test Gotify provider handling HTTP errors."""
        # Mock HTTP 401 error
        mock_urlopen.side_effect = HTTPError(
            url="http://test.example.com/message",
            code=401,
            msg="Unauthorized",
            hdrs={},
            fp=None,
        )

        provider = GotifyNotificationProvider(
            base_url="http://test.example.com", token="invalid_token"
        )

        message = NotificationMessage(
            title="Test",
            message="Test",
            priority=NotificationPriority.NORMAL,
            category=NotificationCategory.TOOL_SUCCESS,
        )

        result = provider.send_notification(message)

        assert result is False

    @patch("urllib.request.urlopen")
    def test_gotify_provider_network_error(self, mock_urlopen):
        """Test Gotify provider handling network errors."""
        # Mock network connection error
        mock_urlopen.side_effect = URLError("Connection refused")

        provider = GotifyNotificationProvider(
            base_url="http://unreachable.example.com", token="test_token"
        )

        message = NotificationMessage(
            title="Test",
            message="Test",
            priority=NotificationPriority.NORMAL,
            category=NotificationCategory.TOOL_SUCCESS,
        )

        result = provider.send_notification(message)

        assert result is False

    @patch("urllib.request.urlopen")
    def test_gotify_provider_non_200_response(self, mock_urlopen):
        """Test Gotify provider handling non-200 HTTP responses."""
        # Mock HTTP 500 response
        mock_response = Mock()
        mock_response.status = 500
        mock_urlopen.return_value.__enter__.return_value = mock_response

        provider = GotifyNotificationProvider(
            base_url="http://test.example.com", token="test_token"
        )

        message = NotificationMessage(
            title="Test",
            message="Test",
            priority=NotificationPriority.NORMAL,
            category=NotificationCategory.TOOL_SUCCESS,
        )

        result = provider.send_notification(message)

        assert result is False

    def test_gotify_provider_not_available(self):
        """Test Gotify provider when not properly configured."""
        provider = GotifyNotificationProvider()  # No URL or token

        message = NotificationMessage(
            title="Test",
            message="Test",
            priority=NotificationPriority.NORMAL,
            category=NotificationCategory.TOOL_SUCCESS,
        )

        result = provider.send_notification(message)

        assert result is False


class TestWebhookNotificationProvider:
    """Test webhook notification provider."""

    def test_webhook_provider_initialization(self):
        """Test webhook provider initialization."""
        provider = WebhookNotificationProvider(
            webhook_url="http://webhook.example.com/notify",
            headers={"Authorization": "Bearer token123"},
        )

        assert provider.webhook_url == "http://webhook.example.com/notify"
        assert provider.headers["Authorization"] == "Bearer token123"
        assert provider.headers["Content-Type"] == "application/json"
        assert provider.get_provider_name() == "webhook"

    def test_webhook_provider_initialization_from_env(self):
        """Test webhook provider initialization from environment."""
        with patch.dict(
            os.environ,
            {
                "WEBHOOK_NOTIFICATION_URL": "http://env.webhook.com",
                "WEBHOOK_TIMEOUT": "20",
                "WEBHOOK_HEADERS": '{"X-API-Key": "secret123"}',
            },
        ):
            provider = WebhookNotificationProvider()

            assert provider.webhook_url == "http://env.webhook.com"
            assert provider.timeout == 20
            assert provider.headers["X-API-Key"] == "secret123"

    def test_webhook_provider_is_available(self):
        """Test webhook provider availability check."""
        # Provider with URL
        provider = WebhookNotificationProvider(webhook_url="http://webhook.example.com")
        assert provider.is_available() is True

        # Provider without URL
        provider = WebhookNotificationProvider()
        assert provider.is_available() is False

    @patch("urllib.request.urlopen")
    def test_webhook_provider_send_success(self, mock_urlopen):
        """Test successful webhook notification sending."""
        # Mock successful HTTP response
        mock_response = Mock()
        mock_response.status = 200
        mock_urlopen.return_value.__enter__.return_value = mock_response

        provider = WebhookNotificationProvider(
            webhook_url="http://webhook.example.com/notify"
        )

        message = NotificationMessage(
            title="Webhook Test",
            message="Test webhook message",
            priority=NotificationPriority.NORMAL,
            category=NotificationCategory.TOOL_FAILURE,
            tool_name="webhook_tool",
        )

        result = provider.send_notification(message)

        assert result is True
        mock_urlopen.assert_called_once()

        # Verify request details
        request = mock_urlopen.call_args[0][0]
        assert request.full_url == "http://webhook.example.com/notify"
        assert request.get_method() == "POST"

        # Verify payload is the full notification dict
        payload = json.loads(request.data.decode("utf-8"))
        assert payload["title"] == "Webhook Test"
        assert payload["message"] == "Test webhook message"
        assert payload["priority"] == "normal"
        assert payload["category"] == "tool_failure"
        assert payload["tool_name"] == "webhook_tool"

    @patch("urllib.request.urlopen")
    def test_webhook_provider_http_error(self, mock_urlopen):
        """Test webhook provider handling HTTP errors."""
        mock_urlopen.side_effect = HTTPError(
            url="http://webhook.example.com/notify",
            code=404,
            msg="Not Found",
            hdrs={},
            fp=None,
        )

        provider = WebhookNotificationProvider(
            webhook_url="http://webhook.example.com/notify"
        )

        message = NotificationMessage(
            title="Test",
            message="Test",
            priority=NotificationPriority.NORMAL,
            category=NotificationCategory.TOOL_SUCCESS,
        )

        result = provider.send_notification(message)

        assert result is False


class TestNotificationManager:
    """Test notification manager functionality."""

    def test_notification_manager_initialization(self):
        """Test notification manager initialization."""
        with patch.dict(
            os.environ,
            {
                "NOTIFICATIONS_ENABLED": "true",
                "NOTIFICATION_PROVIDERS": "console,gotify",
                "GOTIFY_URL": "http://test.example.com",
                "GOTIFY_TOKEN": "test_token",
            },
        ):
            manager = NotificationManager()

            assert manager.enabled is True
            assert len(manager.providers) >= 1  # At least console should be available

    def test_notification_manager_disabled(self):
        """Test notification manager when disabled."""
        with patch.dict(os.environ, {"NOTIFICATIONS_ENABLED": "false"}):
            manager = NotificationManager()

            assert manager.enabled is False
            assert len(manager.providers) == 0

    def test_notification_manager_send_disabled(self):
        """Test sending notification when manager is disabled."""
        with patch.dict(os.environ, {"NOTIFICATIONS_ENABLED": "false"}):
            manager = NotificationManager()

            message = NotificationMessage(
                title="Test",
                message="Test",
                priority=NotificationPriority.NORMAL,
                category=NotificationCategory.TOOL_SUCCESS,
            )

            result = manager.send_notification(message)

            # Should return True to not break operations
            assert result is True

    def test_notification_manager_send_success(self):
        """Test successful notification sending through manager."""
        with patch.dict(
            os.environ,
            {"NOTIFICATIONS_ENABLED": "true", "NOTIFICATION_PROVIDERS": "console"},
        ):
            manager = NotificationManager()

            with patch.object(
                manager.providers[0], "send_notification", return_value=True
            ) as mock_send:
                message = NotificationMessage(
                    title="Test Success",
                    message="Test message",
                    priority=NotificationPriority.NORMAL,
                    category=NotificationCategory.TOOL_SUCCESS,
                )

                result = manager.send_notification(message)

                assert result is True
                mock_send.assert_called_once_with(message)

    def test_notification_manager_send_failure(self):
        """Test notification sending when all providers fail."""
        with patch.dict(
            os.environ,
            {"NOTIFICATIONS_ENABLED": "true", "NOTIFICATION_PROVIDERS": "console"},
        ):
            manager = NotificationManager()

            with patch.object(
                manager.providers[0], "send_notification", return_value=False
            ):
                message = NotificationMessage(
                    title="Test Failure",
                    message="Test message",
                    priority=NotificationPriority.NORMAL,
                    category=NotificationCategory.TOOL_SUCCESS,
                )

                result = manager.send_notification(message)

                assert result is False

    def test_notification_manager_multiple_providers(self):
        """Test notification manager with multiple providers."""
        with patch.dict(
            os.environ,
            {
                "NOTIFICATIONS_ENABLED": "true",
                "NOTIFICATION_PROVIDERS": "console,gotify",
                "GOTIFY_URL": "http://test.example.com",
                "GOTIFY_TOKEN": "test_token",
            },
        ):
            manager = NotificationManager()

            # Should have both console and gotify providers
            provider_names = [p.get_provider_name() for p in manager.providers]
            assert "console" in provider_names
            assert "gotify" in provider_names

    def test_notification_manager_category_filtering(self):
        """Test notification filtering by category."""
        with patch.dict(
            os.environ,
            {
                "NOTIFICATIONS_ENABLED": "true",
                "NOTIFICATION_PROVIDERS": "console",
                "NOTIFICATION_CATEGORIES": "tool_failure,security_violation",
            },
        ):
            manager = NotificationManager()

            # Should send tool_failure notification
            message_failure = NotificationMessage(
                title="Tool Failed",
                message="Test failure",
                priority=NotificationPriority.HIGH,
                category=NotificationCategory.TOOL_FAILURE,
            )

            with patch.object(
                manager.providers[0], "send_notification", return_value=True
            ) as mock_send:
                result = manager.send_notification(message_failure)
                assert result is True
                mock_send.assert_called_once()

            # Should filter out tool_success notification
            message_success = NotificationMessage(
                title="Tool Success",
                message="Test success",
                priority=NotificationPriority.LOW,
                category=NotificationCategory.TOOL_SUCCESS,
            )

            with patch.object(manager.providers[0], "send_notification") as mock_send:
                result = manager.send_notification(message_success)
                assert result is True  # Returns True but doesn't call provider
                mock_send.assert_not_called()

    def test_notification_manager_tool_filtering(self):
        """Test notification filtering by tool name."""
        with patch.dict(
            os.environ,
            {
                "NOTIFICATIONS_ENABLED": "true",
                "NOTIFICATION_PROVIDERS": "console",
                "NOTIFICATION_TOOLS": "docker_ps,gotify_ping",
            },
        ):
            manager = NotificationManager()

            # Should send notification for allowed tool
            message_allowed = NotificationMessage(
                title="Docker Success",
                message="Docker command succeeded",
                priority=NotificationPriority.LOW,
                category=NotificationCategory.TOOL_SUCCESS,
                tool_name="docker_ps",
            )

            with patch.object(
                manager.providers[0], "send_notification", return_value=True
            ) as mock_send:
                result = manager.send_notification(message_allowed)
                assert result is True
                mock_send.assert_called_once()

            # Should filter out notification for non-allowed tool
            message_filtered = NotificationMessage(
                title="Disk Success",
                message="Disk command succeeded",
                priority=NotificationPriority.LOW,
                category=NotificationCategory.TOOL_SUCCESS,
                tool_name="disk_space",
            )

            with patch.object(manager.providers[0], "send_notification") as mock_send:
                result = manager.send_notification(message_filtered)
                assert result is True  # Returns True but doesn't call provider
                mock_send.assert_not_called()

    def test_notification_manager_convenience_methods(self):
        """Test notification manager convenience methods."""
        with patch.dict(
            os.environ,
            {"NOTIFICATIONS_ENABLED": "true", "NOTIFICATION_PROVIDERS": "console"},
        ):
            manager = NotificationManager()

            with patch.object(
                manager, "send_notification", return_value=True
            ) as mock_send:
                # Test tool success notification
                result = manager.send_tool_success(
                    "test_tool", "Operation completed", 150
                )
                assert result is True

                call_args = mock_send.call_args[0][0]
                assert call_args.title == "Tool Success: test_tool"
                assert "Operation completed" in call_args.message
                assert "150ms" in call_args.message
                assert call_args.priority == NotificationPriority.LOW
                assert call_args.category == NotificationCategory.TOOL_SUCCESS
                assert call_args.tool_name == "test_tool"
                assert call_args.metadata["elapsed_ms"] == 150

                # Test tool failure notification
                result = manager.send_tool_failure("test_tool", "Command failed", 1)
                assert result is True

                call_args = mock_send.call_args[0][0]
                assert call_args.title == "Tool Failed: test_tool"
                assert "Command failed" in call_args.message
                assert "exit code: 1" in call_args.message
                assert call_args.priority == NotificationPriority.HIGH
                assert call_args.category == NotificationCategory.TOOL_FAILURE

                # Test tool confirmation notification
                result = manager.send_tool_confirmation(
                    "test_tool", "Confirm operation"
                )
                assert result is True

                call_args = mock_send.call_args[0][0]
                assert call_args.title == "Confirmation Required: test_tool"
                assert "Confirm operation" in call_args.message
                assert "Waiting for user confirmation" in call_args.message
                assert call_args.priority == NotificationPriority.NORMAL
                assert call_args.category == NotificationCategory.TOOL_CONFIRMATION

                # Test security violation notification
                result = manager.send_security_violation(
                    "path_traversal", "Attempted ../../../etc/passwd"
                )
                assert result is True

                call_args = mock_send.call_args[0][0]
                assert call_args.title == "Security Violation: path_traversal"
                assert "Attempted ../../../etc/passwd" in call_args.message
                assert call_args.priority == NotificationPriority.CRITICAL
                assert call_args.category == NotificationCategory.SECURITY_VIOLATION

    def test_notification_manager_get_status(self):
        """Test notification manager status reporting."""
        with patch.dict(
            os.environ,
            {
                "NOTIFICATIONS_ENABLED": "true",
                "NOTIFICATION_PROVIDERS": "console,gotify",
                "NOTIFICATION_CATEGORIES": "tool_failure,security_violation",
                "NOTIFICATION_TOOLS": "docker_ps,gotify_ping",
                "GOTIFY_URL": "http://test.example.com",
                "GOTIFY_TOKEN": "test_token",
            },
        ):
            manager = NotificationManager()
            status = manager.get_status()

            assert status["enabled"] is True
            assert len(status["providers"]) >= 1
            assert "console" in [p["name"] for p in status["providers"]]
            assert status["category_filters"] == ["tool_failure", "security_violation"]
            assert status["tool_filters"] == ["docker_ps", "gotify_ping"]

    def test_notification_manager_provider_exception_handling(self):
        """Test notification manager handles provider exceptions gracefully."""
        with patch.dict(
            os.environ,
            {"NOTIFICATIONS_ENABLED": "true", "NOTIFICATION_PROVIDERS": "console"},
        ):
            manager = NotificationManager()

            # Mock provider to raise exception
            with patch.object(
                manager.providers[0],
                "send_notification",
                side_effect=Exception("Provider error"),
            ):
                message = NotificationMessage(
                    title="Test",
                    message="Test",
                    priority=NotificationPriority.NORMAL,
                    category=NotificationCategory.TOOL_SUCCESS,
                )

                result = manager.send_notification(message)

                # Should return False when all providers fail
                assert result is False


class TestNotificationManagerGlobal:
    """Test global notification manager functions."""

    def test_get_notification_manager_singleton(self):
        """Test that get_notification_manager returns singleton instance."""
        # Clear any existing global instance
        import server.notifications

        server.notifications._notification_manager = None

        manager1 = get_notification_manager()
        manager2 = get_notification_manager()

        assert manager1 is manager2

    def test_convenience_functions(self):
        """Test global convenience functions."""
        with patch("server.notifications.get_notification_manager") as mock_get_manager:
            mock_manager = Mock()
            mock_get_manager.return_value = mock_manager

            from server.notifications import (
                notify_tool_success,
                notify_tool_failure,
                notify_tool_confirmation,
                notify_security_violation,
            )

            # Test each convenience function
            notify_tool_success("test_tool", "Success", 100)
            mock_manager.send_tool_success.assert_called_once_with(
                "test_tool", "Success", 100
            )

            notify_tool_failure("test_tool", "Error", 1)
            mock_manager.send_tool_failure.assert_called_once_with(
                "test_tool", "Error", 1
            )

            notify_tool_confirmation("test_tool", "Confirm")
            mock_manager.send_tool_confirmation.assert_called_once_with(
                "test_tool", "Confirm"
            )

            notify_security_violation("violation", "Details")
            mock_manager.send_security_violation.assert_called_once_with(
                "violation", "Details"
            )


class TestNotificationIntegration:
    """Integration tests for notification system with real scenarios."""

    def test_notification_priority_assignment(self):
        """Test that different scenarios get appropriate priority levels."""
        with patch.dict(
            os.environ,
            {"NOTIFICATIONS_ENABLED": "true", "NOTIFICATION_PROVIDERS": "console"},
        ):
            manager = NotificationManager()

            with patch.object(
                manager.providers[0], "send_notification", return_value=True
            ) as mock_send:
                # Tool success should be LOW priority
                manager.send_tool_success("docker_ps", "Listed containers", 150)
                assert mock_send.call_args[0][0].priority == NotificationPriority.LOW

                # Tool failure should be HIGH priority
                manager.send_tool_failure("docker_ps", "Docker not running", 1)
                assert mock_send.call_args[0][0].priority == NotificationPriority.HIGH

                # Tool confirmation should be NORMAL priority
                manager.send_tool_confirmation(
                    "blog_publish", "Ready to publish 3 files"
                )
                assert mock_send.call_args[0][0].priority == NotificationPriority.NORMAL

                # Security violation should be CRITICAL priority
                manager.send_security_violation(
                    "path_traversal", "Attempted ../../../etc/passwd"
                )
                assert (
                    mock_send.call_args[0][0].priority == NotificationPriority.CRITICAL
                )

    def test_notification_failure_handling_graceful(self):
        """Test that notification failures don't break operations."""
        with patch.dict(
            os.environ,
            {
                "NOTIFICATIONS_ENABLED": "true",
                "NOTIFICATION_PROVIDERS": "gotify",
                "GOTIFY_URL": "http://unreachable.example.com",
                "GOTIFY_TOKEN": "test_token",
            },
        ):
            manager = NotificationManager()

            # Even if Gotify is unreachable, operations should continue
            result = manager.send_tool_success("test_tool", "Success", 100)

            # Should return False for failed notification but not raise exception
            assert result is False

    def test_notification_multiple_provider_fallback(self):
        """Test notification sending with multiple providers where some fail."""
        with patch.dict(
            os.environ,
            {
                "NOTIFICATIONS_ENABLED": "true",
                "NOTIFICATION_PROVIDERS": "console,gotify,webhook",
                "GOTIFY_URL": "http://test.example.com",
                "GOTIFY_TOKEN": "test_token",
                "WEBHOOK_NOTIFICATION_URL": "http://webhook.example.com",
            },
        ):
            manager = NotificationManager()

            message = NotificationMessage(
                title="Test",
                message="Test",
                priority=NotificationPriority.NORMAL,
                category=NotificationCategory.TOOL_SUCCESS,
            )

            # Mock providers: console succeeds, gotify fails, webhook succeeds
            with (
                patch.object(
                    manager.providers[0], "send_notification", return_value=True
                ),
                patch.object(
                    manager.providers[1], "send_notification", return_value=False
                ),
                patch.object(
                    manager.providers[2], "send_notification", return_value=True
                ),
            ):

                result = manager.send_notification(message)

                # Should succeed if at least one provider succeeds
                assert result is True
