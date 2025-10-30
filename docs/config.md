# Configuration Guide

## Overview

Burly MCP uses environment variables and YAML policy files for configuration. This guide explains every configuration option, its purpose, and recommended values.

## Environment Variables

### Required Configuration

#### `BLOG_STAGE_ROOT`
- **Purpose**: Root directory for blog staging operations
- **Type**: Absolute file path
- **Security**: All blog staging operations are restricted to this directory and its subdirectories
- **Example**: `/home/user/blog/staging`
- **Why it matters**: Prevents path traversal attacks by establishing a security boundary

#### `BLOG_PUBLISH_ROOT`
- **Purpose**: Root directory for blog publishing operations
- **Type**: Absolute file path
- **Security**: Blog publishing operations can only write to this directory and its subdirectories
- **Example**: `/var/www/html/blog`
- **Why it matters**: Isolates published content and prevents accidental overwrites of system files

### Optional Configuration

#### `GOTIFY_URL`
- **Purpose**: Base URL for Gotify notification server
- **Type**: HTTP/HTTPS URL
- **Default**: None (notifications disabled)
- **Example**: `https://gotify.example.com`
- **Why it matters**: Enables real-time notifications of MCP operations for monitoring

#### `GOTIFY_TOKEN`
- **Purpose**: Application token for Gotify API authentication
- **Type**: String token
- **Default**: None (notifications disabled)
- **Security**: Keep this secret! Don't commit to version control
- **Example**: `AaBbCcDd123456`
- **Why it matters**: Authenticates notification requests to prevent unauthorized access

#### `TOOL_TIMEOUT_SEC`
- **Purpose**: Maximum execution time for any tool operation
- **Type**: Integer (seconds)
- **Default**: `30`
- **Range**: 1-300 (5 minutes max recommended)
- **Why it matters**: Prevents runaway processes from consuming resources indefinitely

#### `OUTPUT_TRUNCATE_LIMIT`
- **Purpose**: Maximum characters in tool output before truncation
- **Type**: Integer (characters)
- **Default**: `10000`
- **Range**: 1000-100000
- **Why it matters**: Prevents memory exhaustion from tools that produce excessive output

#### `LOG_LEVEL`
- **Purpose**: Controls verbosity of application logging
- **Type**: String
- **Default**: `INFO`
- **Options**: `DEBUG`, `INFO`, `WARNING`, `ERROR`
- **Why it matters**: DEBUG mode helps troubleshoot issues but may expose sensitive information

## Policy Configuration (`policy/tools.yaml`)

BurlyMCP now supports combining the legacy single policy file with a directory
of "tool packs". At startup the server:

* Loads the file pointed to by `POLICY_FILE` (default: `/config/policy/tools.yaml`).
* Loads every `*.yaml` under the directory pointed to by `POLICY_DIR`
  (default: `/config/tools.d`).
* Merges tool definitions by name with **last file wins** precedence. Disabled
  tools (`enabled: false`) are skipped but still reported in startup logs.

The example configs under `examples/config/` can be mounted directly into the
container (for example, `baseline.yaml` → `/config/tools.d/baseline.yaml`).

### File Structure

The policy file defines available tools and their security constraints:

```yaml
tools:
  tool_name:
    description: "Human-readable description"
    args_schema: {...}  # JSON Schema for argument validation
    command: [...]      # Command to execute
    mutates: bool       # Whether tool modifies system state
    requires_confirm: bool  # Whether to require confirmation
    timeout_sec: int    # Tool-specific timeout
    notify: [...]       # Notification events to send
```

### Tool Definitions

#### `docker_ps`
```yaml
docker_ps:
  description: "List Docker containers with status and basic info"
  args_schema:
    type: "object"
    properties: {}
    additionalProperties: false
  command: ["docker", "ps", "--format", "table {{.Names}}\t{{.Status}}\t{{.Ports}}"]
  mutates: false
  requires_confirm: false
  timeout_sec: 10
  notify: []
```

**Configuration Rationale:**
- **No arguments**: Reduces attack surface
- **Table format**: Provides structured, readable output
- **Short timeout**: Container listing should be fast
- **No confirmation**: Read-only operation is safe
- **No notifications**: Routine operation doesn't need alerts

#### `disk_space`
```yaml
disk_space:
  description: "Show filesystem usage summary"
  args_schema:
    type: "object"
    properties: {}
    additionalProperties: false
  command: ["df", "-hT"]
  mutates: false
  requires_confirm: false
  timeout_sec: 5
  notify: []
```

**Configuration Rationale:**
- **Human-readable format (-h)**: Easy to understand output
- **Show filesystem types (-T)**: Helps identify mount types
- **Very short timeout**: Disk queries should be instant
- **No confirmation**: Read-only system information

#### `blog_stage_markdown`
```yaml
blog_stage_markdown:
  description: "Validate Markdown file front-matter for blog staging"
  args_schema:
    type: "object"
    properties:
      file_path:
        type: "string"
        pattern: "^[a-zA-Z0-9._/-]+\\.md$"
    required: ["file_path"]
    additionalProperties: false
  command: ["python", "-c", "import server.tools; server.tools.blog_stage_markdown()"]
  mutates: false
  requires_confirm: false
  timeout_sec: 5
  notify: []
```

**Configuration Rationale:**
- **File path validation**: Regex ensures only .md files with safe characters
- **Python execution**: Uses internal validation logic
- **No confirmation**: Validation is read-only
- **Short timeout**: File parsing should be quick

#### `blog_publish_static`
```yaml
blog_publish_static:
  description: "Copy staged blog files to publish directory"
  args_schema:
    type: "object"
    properties:
      source_dir:
        type: "string"
        pattern: "^[a-zA-Z0-9._/-]+$"
      _confirm:
        type: "boolean"
    required: ["source_dir"]
    additionalProperties: false
  command: ["python", "-c", "import server.tools; server.tools.blog_publish_static()"]
  mutates: true
  requires_confirm: true
  timeout_sec: 30
  notify: ["success", "failure"]
```

**Configuration Rationale:**
- **Mutates system**: Copies files, changes published content
- **Requires confirmation**: Prevents accidental publishing
- **Longer timeout**: File operations may take time
- **Notifications**: Important to know when publishing succeeds/fails
- **Confirmation parameter**: `_confirm` must be explicitly set to true

#### `gotify_ping`
```yaml
gotify_ping:
  description: "Send a test message to Gotify notification service"
  args_schema:
    type: "object"
    properties:
      message:
        type: "string"
        maxLength: 1000
      _confirm:
        type: "boolean"
    required: ["message"]
    additionalProperties: false
  command: ["python", "-c", "import server.tools; server.tools.gotify_ping()"]
  mutates: true
  requires_confirm: true
  timeout_sec: 10
  notify: ["success", "failure"]
```

**Configuration Rationale:**
- **Message length limit**: Prevents abuse of notification system
- **Requires confirmation**: Prevents spam notifications
- **Network timeout**: Allows for network latency
- **Mutates system**: Sends external notifications

### Schema Validation

Each tool's `args_schema` uses JSON Schema Draft 2020-12 for argument validation:

#### Common Patterns

**String with pattern validation:**
```yaml
file_path:
  type: "string"
  pattern: "^[a-zA-Z0-9._/-]+\\.md$"  # Only safe characters, .md extension
```

**String with length limits:**
```yaml
message:
  type: "string"
  maxLength: 1000  # Prevent excessive input
```

**Boolean flags:**
```yaml
_confirm:
  type: "boolean"  # Explicit confirmation required
```

**No additional properties:**
```yaml
additionalProperties: false  # Reject unexpected arguments
```

### Security Configuration

#### Timeout Strategy
- **Read-only tools**: 5-10 seconds (should be fast)
- **File operations**: 30 seconds (may involve I/O)
- **Network operations**: 10-15 seconds (account for latency)
- **Never exceed**: 300 seconds (5 minutes absolute maximum)

#### Confirmation Requirements
- **All mutating operations**: Must require confirmation
- **Read-only operations**: No confirmation needed
- **External communications**: Always require confirmation

#### Notification Strategy
- **Success notifications**: Priority 3 (low)
- **Confirmation requests**: Priority 5 (normal)
- **Failure notifications**: Priority 8 (high)

## Docker Configuration

### Container Security

```yaml
# docker-compose.yml security settings
user: "1000:1000"  # Non-root user
read_only: true    # Read-only filesystem
security_opt:
  - no-new-privileges:true  # Prevent privilege escalation
```

### Volume Mounts

```yaml
volumes:
  # Policy files (read-only)
  - ./policy:/app/policy:ro
  
  # Blog staging (read-only)
  - ${BLOG_STAGE_ROOT}:/blog/staging:ro
  
  # Blog publishing (read-write)
  - ${BLOG_PUBLISH_ROOT}:/blog/publish:rw
  
  # Audit logs (read-write)
  - ./logs:/var/log/agentops:rw
  
  # Docker socket (read-only)
  - /var/run/docker.sock:/var/run/docker.sock:ro
```

**Mount Rationale:**
- **Policy read-only**: Prevents runtime modification of security policies
- **Staging read-only**: Source files shouldn't be modified during validation
- **Publish read-write**: Destination needs write access for publishing
- **Logs read-write**: Audit trail needs write access
- **Docker socket read-only**: Prevents container manipulation

### Resource Limits

```yaml
deploy:
  resources:
    limits:
      memory: 512M      # Reasonable for Python application
      cpus: '0.5'       # Half CPU core maximum
    reservations:
      memory: 128M      # Minimum guaranteed memory
```

## Configuration Validation

### Startup Checks

The server validates configuration at startup:

1. **Environment variables**: Required variables must be set
2. **Directory access**: Blog directories must exist and be accessible
3. **Policy file**: Must be valid YAML with required fields
4. **Schema validation**: All tool schemas must be valid JSON Schema
5. **Docker access**: Docker socket must be accessible (if docker tools enabled)

### Runtime Validation

During operation:

1. **Argument validation**: All tool arguments validated against schemas
2. **Path traversal checks**: File paths validated against allowed roots
3. **Timeout enforcement**: All operations terminated if they exceed limits
4. **Output truncation**: Large outputs truncated to prevent memory issues

## Best Practices

### Security
1. **Minimal permissions**: Only grant necessary access
2. **Regular updates**: Keep policies and configurations current
3. **Audit review**: Regularly check audit logs for anomalies
4. **Secret management**: Never commit secrets to version control

### Performance
1. **Appropriate timeouts**: Balance responsiveness with reliability
2. **Output limits**: Prevent memory exhaustion from verbose tools
3. **Resource limits**: Constrain container resource usage

### Monitoring
1. **Enable notifications**: Get alerts for important operations
2. **Log rotation**: Prevent audit logs from filling disk
3. **Health checks**: Monitor container and service health

This configuration guide ensures you understand every setting and can tune Burly MCP for your specific needs while maintaining security.