"""
Burly MCP Notifications Module

This module contains the notification system components that handle
sending notifications via various providers like Gotify.
"""

from .manager import (
    NotificationManager,
    get_notification_manager,
    notify_tool_confirmation,
    notify_tool_failure,
    notify_tool_success,
)

__all__ = [
    "get_notification_manager",
    "notify_tool_confirmation",
    "notify_tool_failure",
    "notify_tool_success",
    "NotificationManager",
]
