# Notification System Configuration

The Burly MCP Server includes a flexible, pluggable notification system that can be completely disabled or configured to work with various notification providers.

## Quick Start

### Disable Notifications (Default for Privacy)
```bash
export NOTIFICATIONS_ENABLED=false
```

### Enable Console Notifications (Development)
```bash
export NOTIFICATIONS_ENABLED=true
export NOTIFICATION_PROVIDERS=console
```

### Enable Gotify Notifications
```bash
export NOTIFICATIONS_ENABLED=true
export NOTIFICATION_PROVIDERS=gotify
export GOTIFY_URL=https://your-gotify-server.com
export GOTIFY_TOKEN=your-app-token
```

## Supported Providers

### 1. Console Provider
Outputs notifications to stdout/stderr. Perfect for development and debugging.

**Configuration:**
```bash
export NOTIFICATION_PROVIDERS=console
```

**Features:**
- Always available (no external dependencies)
- Uses emoji indicators for priority levels
- High/critical notifications go to stderr
- No additional configuration required

### 2. Gotify Provider
Sends notifications to a Gotify server via HTTP API.

**Configuration:**
```bash
export NOTIFICATION_PROVIDERS=gotify
export GOTIFY_URL=https://your-gotify-server.com
export GOTIFY_TOKEN=your-app-token
export GOTIFY_TIMEOUT=10  # Optional: HTTP timeout in seconds
```

**Features:**
- Priority mapping (Low=2, Normal=5, High=8, Critical=10)
- Includes metadata in notification extras
- Network error handling with graceful fallback
- Configurable timeout

### 3. Webhook Provider
Sends notifications to any HTTP endpoint that accepts JSON POST requests.

**Configuration:**
```bash
export NOTIFICATION_PROVIDERS=webhook
export WEBHOOK_NOTIFICATION_URL=https://your-webhook-endpoint.com/notify
export WEBHOOK_TIMEOUT=10  # Optional: HTTP timeout in seconds
export WEBHOOK_HEADERS='{"Authorization": "Bearer your-token"}'  # Optional: JSON
```

**Features:**
- Generic HTTP POST with JSON payload
- Configurable headers for authentication
- Works with any webhook-compatible service
- Full notification data in JSON format

### 4. Multiple Providers
You can enable multiple providers simultaneously:

```bash
export NOTIFICATION_PROVIDERS=console,gotify,webhook
```

Notifications will be sent to all available providers. If one fails, others continue working.

## Filtering and Control

### Category Filtering
Control which types of notifications are sent:

```bash
# Only send failures and security violations
export NOTIFICATION_CATEGORIES=tool_failure,security_violation

# Send all notification types (default)
export NOTIFICATION_CATEGORIES=tool_success,tool_failure,tool_confirmation,security_violation,system_error,audit_event
```

### Tool Filtering
Control which tools can send notifications:

```bash
# Only allow notifications from specific tools
export NOTIFICATION_TOOLS=docker_ps,blog_publish_static

# Allow all tools (default - empty means all allowed)
export NOTIFICATION_TOOLS=
```

### Complete Disable
```bash
export NOTIFICATIONS_ENABLED=false
```

## Notification Types

### Tool Success
Sent when a tool completes successfully.
- **Priority:** Low
- **Includes:** Tool name, summary, execution time

### Tool Failure
Sent when a tool fails or encounters an error.
- **Priority:** High
- **Includes:** Tool name, error message, exit code

### Tool Confirmation
Sent when a tool requires user confirmation (mutating operations).
- **Priority:** Normal
- **Includes:** Tool name, operation summary

### Security Violation
Sent when security violations are detected (path traversal, etc.).
- **Priority:** Critical
- **Includes:** Violation type, details

## Example Configurations

### Development Setup
```bash
export NOTIFICATIONS_ENABLED=true
export NOTIFICATION_PROVIDERS=console
export NOTIFICATION_CATEGORIES=tool_failure,security_violation
```

### Production Setup with Gotify
```bash
export NOTIFICATIONS_ENABLED=true
export NOTIFICATION_PROVIDERS=gotify
export GOTIFY_URL=https://notifications.yourcompany.com
export GOTIFY_TOKEN=your-secure-token
export NOTIFICATION_CATEGORIES=tool_failure,security_violation,tool_confirmation
```

### Multi-Provider Setup
```bash
export NOTIFICATIONS_ENABLED=true
export NOTIFICATION_PROVIDERS=console,gotify,webhook
export GOTIFY_URL=https://gotify.yourcompany.com
export GOTIFY_TOKEN=gotify-token
export WEBHOOK_NOTIFICATION_URL=https://hooks.slack.com/services/your/slack/webhook
export NOTIFICATION_CATEGORIES=tool_failure,security_violation
```

### Privacy-First Setup (Recommended Default)
```bash
export NOTIFICATIONS_ENABLED=false
```

## Adding Custom Providers

The notification system is designed to be easily extensible. To add a new provider:

1. Create a class that inherits from `NotificationProvider`
2. Implement the required methods:
   - `send_notification(notification: NotificationMessage) -> bool`
   - `is_available() -> bool`
   - `get_provider_name() -> str`
3. Add your provider to the `_create_provider()` method in `NotificationManager`

Example custom provider:
```python
class SlackNotificationProvider(NotificationProvider):
    def __init__(self):
        self.webhook_url = os.environ.get("SLACK_WEBHOOK_URL", "")
    
    def send_notification(self, notification: NotificationMessage) -> bool:
        # Implementation here
        pass
    
    def is_available(self) -> bool:
        return bool(self.webhook_url)
    
    def get_provider_name(self) -> str:
        return "slack"
```

## Security Considerations

1. **Sensitive Data:** The notification system automatically redacts sensitive information from tool arguments before including them in notifications.

2. **Network Security:** All HTTP-based providers (Gotify, Webhook) use proper timeout handling and error recovery.

3. **Failure Isolation:** Notification failures never break tool execution - they fail gracefully and log warnings.

4. **Privacy by Default:** Notifications are disabled by default to protect user privacy.

5. **Configuration Security:** Store sensitive tokens and URLs in environment variables, never in code.

## Troubleshooting

### Notifications Not Sending
1. Check if notifications are enabled: `NOTIFICATIONS_ENABLED=true`
2. Verify provider configuration (URLs, tokens, etc.)
3. Check logs for error messages
4. Test with console provider first

### Gotify Issues
1. Verify server URL is accessible
2. Check app token permissions
3. Test with curl: `curl -X POST "https://your-gotify/message?token=TOKEN" -H "Content-Type: application/json" -d '{"title":"test","message":"test"}'`

### Webhook Issues
1. Verify endpoint accepts JSON POST requests
2. Check authentication headers
3. Test with curl to verify endpoint works

### Too Many/Few Notifications
1. Adjust category filters: `NOTIFICATION_CATEGORIES`
2. Adjust tool filters: `NOTIFICATION_TOOLS`
3. Consider disabling success notifications in production

## Performance Impact

The notification system is designed to have minimal performance impact:
- Notifications are sent asynchronously and don't block tool execution
- Failed notifications are logged but don't retry automatically
- Network timeouts are configurable and reasonable (10s default)
- The system gracefully handles provider unavailability