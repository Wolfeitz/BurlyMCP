"""
Gotify Notification System for Burly MCP Server

This module implements optional Gotify integration for sending notifications
about tool executions. Notifications help administrators monitor AI assistant
activities and receive alerts for important events.

Notification Priorities:
- Success (3): Normal operations completed successfully
- Need Confirm (5): Operations requiring user confirmation
- Failure (8): Operations that failed or encountered errors

The notification system is designed to be non-blocking - if Gotify is
unavailable or misconfigured, tool execution continues normally with
only warning logs generated.

Configuration:
Notifications are configured via environment variables:
- GOTIFY_URL: Base URL of the Gotify server
- GOTIFY_TOKEN: Application token for authentication
- GOTIFY_ENABLED: Whether notifications are enabled (default: false)

Example Usage:
```python
notifier = GotifyNotifier()
notifier.send_success("docker_ps", "Listed 3 running containers")
notifier.send_failure("disk_space", "Permission denied accessing /root")
```
"""

import os
import requests
import logging
from typing import Optional, Dict, Any
from enum import IntEnum


class NotificationPriority(IntEnum):
    """
    Gotify notification priority levels.
    
    These priorities determine how notifications are displayed
    and handled by Gotify clients.
    """
    SUCCESS = 3
    NEED_CONFIRM = 5
    FAILURE = 8


class GotifyNotifier:
    """
    Gotify notification client for MCP tool execution alerts.
    
    This class handles sending notifications to a Gotify server
    with appropriate priority levels and error handling.
    """
    
    def __init__(self):
        """
        Initialize the Gotify notifier with configuration from environment.
        
        Configuration is loaded from environment variables:
        - GOTIFY_URL: Base URL of the Gotify server
        - GOTIFY_TOKEN: Application token for authentication
        - GOTIFY_ENABLED: Whether notifications are enabled
        """
        self.enabled = os.getenv("GOTIFY_ENABLED", "false").lower() == "true"
        self.base_url = os.getenv("GOTIFY_URL", "")
        self.token = os.getenv("GOTIFY_TOKEN", "")
        self.logger = logging.getLogger(__name__)
        
        if self.enabled and (not self.base_url or not self.token):
            self.logger.warning(
                "Gotify notifications enabled but URL or token not configured"
            )
            self.enabled = False
    
    def send_success(self, tool_name: str, message: str) -> bool:
        """
        Send a success notification for a completed tool execution.
        
        Args:
            tool_name: Name of the tool that succeeded
            message: Success message to send
            
        Returns:
            True if notification was sent successfully, False otherwise
        """
        return self._send_notification(
            title=f"✅ {tool_name} completed",
            message=message,
            priority=NotificationPriority.SUCCESS
        )
    
    def send_need_confirm(self, tool_name: str, message: str) -> bool:
        """
        Send a confirmation request notification.
        
        Args:
            tool_name: Name of the tool requiring confirmation
            message: Confirmation request message
            
        Returns:
            True if notification was sent successfully, False otherwise
        """
        return self._send_notification(
            title=f"⚠️ {tool_name} needs confirmation",
            message=message,
            priority=NotificationPriority.NEED_CONFIRM
        )
    
    def send_failure(self, tool_name: str, message: str) -> bool:
        """
        Send a failure notification for a failed tool execution.
        
        Args:
            tool_name: Name of the tool that failed
            message: Failure message to send
            
        Returns:
            True if notification was sent successfully, False otherwise
        """
        return self._send_notification(
            title=f"❌ {tool_name} failed",
            message=message,
            priority=NotificationPriority.FAILURE
        )
    
    def _send_notification(
        self,
        title: str,
        message: str,
        priority: NotificationPriority
    ) -> bool:
        """
        Send a notification to the Gotify server.
        
        Args:
            title: Notification title
            message: Notification message body
            priority: Notification priority level
            
        Returns:
            True if notification was sent successfully, False otherwise
        """
        if not self.enabled:
            return False
        
        try:
            url = f"{self.base_url}/message"
            params = {"token": self.token}
            data = {
                "title": title,
                "message": message,
                "priority": priority.value
            }
            
            response = requests.post(
                url,
                params=params,
                json=data,
                timeout=10  # 10 second timeout
            )
            
            if response.status_code == 200:
                self.logger.debug(f"Notification sent: {title}")
                return True
            else:
                self.logger.warning(
                    f"Failed to send notification: HTTP {response.status_code}"
                )
                return False
                
        except requests.exceptions.RequestException as e:
            self.logger.warning(f"Failed to send notification: {e}")
            return False
        except Exception as e:
            self.logger.error(f"Unexpected error sending notification: {e}")
            return False
    
    def test_connection(self) -> bool:
        """
        Test the connection to the Gotify server.
        
        Returns:
            True if connection is successful, False otherwise
        """
        return self.send_success("gotify_ping", "Test notification from Burly MCP")