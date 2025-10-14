"""
Pluggable Notification System for MCP Operations

This module provides a flexible notification framework that can be easily
extended to support different notification providers. The system is designed
to be completely optional and configurable, allowing users to:

1. Disable notifications entirely
2. Choose from multiple notification providers
3. Configure per-tool notification preferences
4. Add custom notification providers easily

Supported Providers:
- Gotify (HTTP-based notifications)
- Console (stdout logging for development)
- Webhook (generic HTTP POST notifications)
- Custom providers via plugin interface

Design Principles:
- Provider-agnostic interface
- Graceful failure handling (notifications never break operations)
- Configurable priority levels and filtering
- Easy extensibility for new providers
"""

import json
import logging
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, List, Optional, Union

logger = logging.getLogger(__name__)


class NotificationPriority(Enum):
    """
    Notification priority levels.

    These map to different urgency levels and can be used by providers
    to determine delivery methods, sounds, or visual indicators.
    """

    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    CRITICAL = "critical"


class NotificationCategory(Enum):
    """
    Notification categories for filtering and routing.

    These help users configure which types of notifications they want
    to receive and how they should be handled.
    """

    TOOL_SUCCESS = "tool_success"
    TOOL_FAILURE = "tool_failure"
    TOOL_CONFIRMATION = "tool_confirmation"
    SECURITY_VIOLATION = "security_violation"
    SYSTEM_ERROR = "system_error"
    AUDIT_EVENT = "audit_event"


@dataclass
class NotificationMessage:
    """
    Standardized notification message format.

    This dataclass provides a consistent interface for all notification
    providers, regardless of their underlying implementation.
    """

    title: str
    message: str
    priority: NotificationPriority
    category: NotificationCategory
    tool_name: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "title": self.title,
            "message": self.message,
            "priority": self.priority.value,
            "category": self.category.value,
            "tool_name": self.tool_name,
            "metadata": self.metadata or {},
        }


class NotificationProvider(ABC):
    """
    Abstract base class for notification providers.

    All notification providers must implement this interface to ensure
    consistent behavior and easy swapping between providers.
    """

    @abstractmethod
    def send_notification(self, notification: NotificationMessage) -> bool:
        """
        Send a notification message.

        Args:
            notification: The notification message to send

        Returns:
            bool: True if notification was sent successfully, False otherwise
        """
        pass

    @abstractmethod
    def is_available(self) -> bool:
        """
        Check if the notification provider is properly configured and available.

        Returns:
            bool: True if the provider can send notifications
        """
        pass

    @abstractmethod
    def get_provider_name(self) -> str:
        """
        Get the name of this notification provider.

        Returns:
            str: Provider name for logging and configuration
        """
        pass


class ConsoleNotificationProvider(NotificationProvider):
    """
    Console notification provider for development and debugging.

    This provider outputs notifications to stdout/stderr and is useful
    for development, testing, or when no external notification system
    is available.
    """

    def send_notification(self, notification: NotificationMessage) -> bool:
        """Send notification to console output."""
        try:
            priority_symbol = {
                NotificationPriority.LOW: "ℹ️",
                NotificationPriority.NORMAL: "📢",
                NotificationPriority.HIGH: "⚠️",
                NotificationPriority.CRITICAL: "🚨",
            }.get(notification.priority, "📢")

            output = f"{priority_symbol} [{notification.category.value.upper()}] {notification.title}"
            if notification.tool_name:
                output += f" (tool: {notification.tool_name})"
            output += f"\n   {notification.message}"

            # Use stderr for high priority notifications
            if notification.priority in [
                NotificationPriority.HIGH,
                NotificationPriority.CRITICAL,
            ]:
                print(output, file=sys.stderr)
            else:
                print(output)

            return True

        except Exception as e:
            logger.error(f"Console notification failed: {str(e)}")
            return False

    def is_available(self) -> bool:
        """Console is always available."""
        return True

    def get_provider_name(self) -> str:
        """Return provider name."""
        return "console"


class GotifyNotificationProvider(NotificationProvider):
    """
    Gotify notification provider for HTTP-based notifications.

    This provider sends notifications to a Gotify server via HTTP POST.
    It supports priority mapping and includes comprehensive error handling.
    """

    def __init__(self, base_url: Optional[str] = None, token: Optional[str] = None):
        """
        Initialize Gotify provider.

        Args:
            base_url: Gotify server URL (optional, can use environment variable)
            token: Gotify app token (optional, can use environment variable)
        """
        self.base_url = base_url or os.environ.get("GOTIFY_URL", "").rstrip("/")
        self.token = token or os.environ.get("GOTIFY_TOKEN", "")
        self.timeout = int(os.environ.get("GOTIFY_TIMEOUT", "10"))

    def send_notification(self, notification: NotificationMessage) -> bool:
        """Send notification to Gotify server."""
        if not self.is_available():
            logger.warning("Gotify provider not properly configured")
            return False

        try:
            # Map our priority levels to Gotify priorities (0-10)
            gotify_priority = {
                NotificationPriority.LOW: 2,
                NotificationPriority.NORMAL: 5,
                NotificationPriority.HIGH: 8,
                NotificationPriority.CRITICAL: 10,
            }.get(notification.priority, 5)

            # Prepare the payload
            payload = {
                "title": notification.title,
                "message": notification.message,
                "priority": gotify_priority,
                "extras": {
                    "category": notification.category.value,
                    "tool_name": notification.tool_name,
                    "metadata": notification.metadata or {},
                },
            }

            # Send HTTP POST request
            url = f"{self.base_url}/message?token={self.token}"
            data = json.dumps(payload).encode("utf-8")

            req = urllib.request.Request(
                url, data=data, headers={"Content-Type": "application/json"}
            )

            with urllib.request.urlopen(req, timeout=self.timeout) as response:
                if response.status == 200:
                    logger.debug(f"Gotify notification sent: {notification.title}")
                    return True
                else:
                    logger.warning(f"Gotify returned status {response.status}")
                    return False

        except urllib.error.URLError as e:
            logger.warning(f"Gotify notification failed (network): {str(e)}")
            return False
        except Exception as e:
            logger.error(f"Gotify notification failed (unexpected): {str(e)}")
            return False

    def is_available(self) -> bool:
        """Check if Gotify is properly configured."""
        return bool(self.base_url and self.token)

    def get_provider_name(self) -> str:
        """Return provider name."""
        return "gotify"


class WebhookNotificationProvider(NotificationProvider):
    """
    Generic webhook notification provider.

    This provider sends notifications to any HTTP endpoint that accepts
    JSON POST requests. It's useful for integrating with custom systems
    or services that don't have dedicated providers.
    """

    def __init__(
        self,
        webhook_url: Optional[str] = None,
        headers: Optional[Dict[str, str]] = None,
    ):
        """
        Initialize webhook provider.

        Args:
            webhook_url: HTTP endpoint URL (optional, can use environment variable)
            headers: Additional HTTP headers (optional)
        """
        self.webhook_url = webhook_url or os.environ.get("WEBHOOK_NOTIFICATION_URL", "")
        self.timeout = int(os.environ.get("WEBHOOK_TIMEOUT", "10"))
        self.headers = headers or {}

        # Add default headers
        self.headers.setdefault("Content-Type", "application/json")
        self.headers.setdefault("User-Agent", "Burly-MCP-Server/1.0")

        # Add custom headers from environment
        custom_headers = os.environ.get("WEBHOOK_HEADERS", "")
        if custom_headers:
            try:
                self.headers.update(json.loads(custom_headers))
            except json.JSONDecodeError:
                logger.warning("Invalid WEBHOOK_HEADERS format, ignoring")

    def send_notification(self, notification: NotificationMessage) -> bool:
        """Send notification to webhook endpoint."""
        if not self.is_available():
            logger.warning("Webhook provider not properly configured")
            return False

        try:
            # Send the full notification as JSON
            payload = notification.to_dict()
            data = json.dumps(payload).encode("utf-8")

            req = urllib.request.Request(
                self.webhook_url, data=data, headers=self.headers
            )

            with urllib.request.urlopen(req, timeout=self.timeout) as response:
                if 200 <= response.status < 300:
                    logger.debug(f"Webhook notification sent: {notification.title}")
                    return True
                else:
                    logger.warning(f"Webhook returned status {response.status}")
                    return False

        except urllib.error.URLError as e:
            logger.warning(f"Webhook notification failed (network): {str(e)}")
            return False
        except Exception as e:
            logger.error(f"Webhook notification failed (unexpected): {str(e)}")
            return False

    def is_available(self) -> bool:
        """Check if webhook is properly configured."""
        return bool(self.webhook_url)

    def get_provider_name(self) -> str:
        """Return provider name."""
        return "webhook"


class NotificationManager:
    """
    Central notification manager that coordinates multiple providers.

    This class manages notification routing, filtering, and provider
    selection. It provides a simple interface for the rest of the
    application while handling the complexity of multiple providers.
    """

    def __init__(self):
        """Initialize the notification manager."""
        self.providers: List[NotificationProvider] = []
        self.enabled = self._is_notifications_enabled()
        self.category_filters = self._load_category_filters()
        self.tool_filters = self._load_tool_filters()

        if self.enabled:
            self._initialize_providers()

    def send_notification(self, notification: NotificationMessage) -> bool:
        """
        Send a notification through available providers.

        Args:
            notification: The notification to send

        Returns:
            bool: True if at least one provider sent the notification successfully
        """
        if not self.enabled:
            logger.debug("Notifications disabled, skipping")
            return True  # Return True to not break operations

        if not self._should_send_notification(notification):
            logger.debug(f"Notification filtered out: {notification.title}")
            return True

        if not self.providers:
            logger.debug("No notification providers available")
            return True

        success_count = 0
        for provider in self.providers:
            try:
                if provider.is_available() and provider.send_notification(notification):
                    success_count += 1
            except Exception as e:
                logger.error(
                    f"Provider {provider.get_provider_name()} failed: {str(e)}"
                )

        if success_count > 0:
            logger.debug(f"Notification sent via {success_count} provider(s)")
            return True
        else:
            logger.warning(
                f"All notification providers failed for: {notification.title}"
            )
            return False

    def send_tool_success(self, tool_name: str, summary: str, elapsed_ms: int) -> bool:
        """Send a tool success notification."""
        notification = NotificationMessage(
            title=f"Tool Success: {tool_name}",
            message=f"{summary} (completed in {elapsed_ms}ms)",
            priority=NotificationPriority.LOW,
            category=NotificationCategory.TOOL_SUCCESS,
            tool_name=tool_name,
            metadata={"elapsed_ms": elapsed_ms},
        )
        return self.send_notification(notification)

    def send_tool_failure(self, tool_name: str, error: str, exit_code: int) -> bool:
        """Send a tool failure notification."""
        notification = NotificationMessage(
            title=f"Tool Failed: {tool_name}",
            message=f"Error: {error} (exit code: {exit_code})",
            priority=NotificationPriority.HIGH,
            category=NotificationCategory.TOOL_FAILURE,
            tool_name=tool_name,
            metadata={"exit_code": exit_code},
        )
        return self.send_notification(notification)

    def send_tool_confirmation(self, tool_name: str, summary: str) -> bool:
        """Send a tool confirmation request notification."""
        notification = NotificationMessage(
            title=f"Confirmation Required: {tool_name}",
            message=f"{summary} - Waiting for user confirmation",
            priority=NotificationPriority.NORMAL,
            category=NotificationCategory.TOOL_CONFIRMATION,
            tool_name=tool_name,
        )
        return self.send_notification(notification)

    def send_security_violation(self, violation_type: str, details: str) -> bool:
        """Send a security violation notification."""
        notification = NotificationMessage(
            title=f"Security Violation: {violation_type}",
            message=f"Security violation detected: {details}",
            priority=NotificationPriority.CRITICAL,
            category=NotificationCategory.SECURITY_VIOLATION,
            metadata={"violation_type": violation_type},
        )
        return self.send_notification(notification)

    def _is_notifications_enabled(self) -> bool:
        """Check if notifications are enabled via configuration."""
        enabled_str = os.environ.get("NOTIFICATIONS_ENABLED", "true").lower()
        return enabled_str in ["true", "1", "yes", "on"]

    def _initialize_providers(self) -> None:
        """Initialize notification providers based on configuration."""
        provider_config = os.environ.get(
            "NOTIFICATION_PROVIDERS", "console,gotify"
        ).lower()
        provider_names = [name.strip() for name in provider_config.split(",")]

        for provider_name in provider_names:
            provider = self._create_provider(provider_name)
            if provider and provider.is_available():
                self.providers.append(provider)
                logger.info(f"Notification provider '{provider_name}' initialized")
            elif provider:
                logger.warning(
                    f"Notification provider '{provider_name}' not available (check configuration)"
                )
            else:
                logger.warning(f"Unknown notification provider: {provider_name}")

    def _create_provider(self, provider_name: str) -> Optional[NotificationProvider]:
        """Create a notification provider by name."""
        if provider_name == "console":
            return ConsoleNotificationProvider()
        elif provider_name == "gotify":
            return GotifyNotificationProvider()
        elif provider_name == "webhook":
            return WebhookNotificationProvider()
        else:
            return None

    def _load_category_filters(self) -> List[NotificationCategory]:
        """Load category filters from configuration."""
        filter_config = os.environ.get("NOTIFICATION_CATEGORIES", "").lower()
        if not filter_config:
            return list(NotificationCategory)  # Allow all categories by default

        category_names = [name.strip() for name in filter_config.split(",")]
        categories = []

        for name in category_names:
            try:
                categories.append(NotificationCategory(name))
            except ValueError:
                logger.warning(f"Unknown notification category: {name}")

        return categories or list(NotificationCategory)

    def _load_tool_filters(self) -> List[str]:
        """Load tool filters from configuration."""
        filter_config = os.environ.get("NOTIFICATION_TOOLS", "")
        if not filter_config:
            return []  # Empty list means all tools allowed

        return [name.strip() for name in filter_config.split(",")]

    def _should_send_notification(self, notification: NotificationMessage) -> bool:
        """Check if a notification should be sent based on filters."""
        # Check category filter
        if notification.category not in self.category_filters:
            return False

        # Check tool filter (if specified)
        if self.tool_filters and notification.tool_name:
            if notification.tool_name not in self.tool_filters:
                return False

        return True

    def get_status(self) -> Dict[str, Any]:
        """Get notification system status."""
        return {
            "enabled": self.enabled,
            "providers": [
                {
                    "name": provider.get_provider_name(),
                    "available": provider.is_available(),
                }
                for provider in self.providers
            ],
            "category_filters": [cat.value for cat in self.category_filters],
            "tool_filters": self.tool_filters,
        }


# Global notification manager instance
_notification_manager: Optional[NotificationManager] = None


def get_notification_manager() -> NotificationManager:
    """
    Get the global notification manager instance.

    Returns:
        NotificationManager: The global notification manager
    """
    global _notification_manager

    if _notification_manager is None:
        _notification_manager = NotificationManager()

    return _notification_manager


# Convenience functions for common notification types
def notify_tool_success(tool_name: str, summary: str, elapsed_ms: int) -> bool:
    """Send a tool success notification."""
    return get_notification_manager().send_tool_success(tool_name, summary, elapsed_ms)


def notify_tool_failure(tool_name: str, error: str, exit_code: int) -> bool:
    """Send a tool failure notification."""
    return get_notification_manager().send_tool_failure(tool_name, error, exit_code)


def notify_tool_confirmation(tool_name: str, summary: str) -> bool:
    """Send a tool confirmation request notification."""
    return get_notification_manager().send_tool_confirmation(tool_name, summary)


def notify_security_violation(violation_type: str, details: str) -> bool:
    """Send a security violation notification."""
    return get_notification_manager().send_security_violation(violation_type, details)
