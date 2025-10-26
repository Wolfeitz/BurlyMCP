# BurlyMCP HTTP API Contract

This document defines the external API contract for the BurlyMCP HTTP Bridge. This contract MUST be treated as the external compatibility guarantee and MUST remain stable across internal refactors.

## Overview

The BurlyMCP HTTP Bridge provides two primary endpoints:
- `GET /health` - Service health and status information
- `POST /mcp` - MCP protocol communication via HTTP

## Core Principles

1. **HTTP 200 Always**: The `/mcp` endpoint MUST always return HTTP 200 status code. Errors and failures are expressed in the response body JSON envelope, never via HTTP 4xx/5xx status codes.

2. **Structured Envelope**: All responses use a consistent JSON envelope format with required fields for monitoring and audit.

3. **Metrics Required**: Every `/mcp` response MUST include `metrics.elapsed_ms` and `metrics.exit_code` for downstream audit and telemetry.

4. **Implementation Independence**: The API contract MUST NOT change when internal implementation changes (e.g., subprocess to in-process MCP engine).

## Health Endpoint

### GET /health

Returns comprehensive service health and feature availability status.

**Response Format:**
```json
{
  "status": "ok|degraded|error",
  "server_name": "burlymcp",
  "version": "1.0.0",
  "tools_available": 5,
  "notifications_enabled": true,
  "docker_available": true,
  "strict_security_mode": true,
  "policy_loaded": true,
  "uptime_seconds": 3600
}
```

**Status Values:**
- `"ok"`: MCP engine is callable AND policy loaded
- `"degraded"`: Service is usable but some features may be unavailable
- `"error"`: Service is effectively unusable

**Required Fields:**
- `server_name`: Server identifier
- `version`: Server version (aka server_version)
- `policy_loaded`: Whether policy is successfully loaded
- `strict_security_mode`: Whether strict security is enabled
- `docker_available`: Whether Docker operations are available
- `notifications_enabled`: Whether notifications are configured
- `tools_available`: Number of available tools

## MCP Endpoint

### POST /mcp

Processes MCP protocol requests via HTTP. Supports multiple request formats and always returns HTTP 200 with structured JSON envelope.

**Request Formats:**

#### Direct Format
```json
{
  "id": "request-1",
  "method": "call_tool",
  "name": "disk_space",
  "args": {}
}
```

#### Params Format
```json
{
  "id": "request-1",
  "method": "call_tool",
  "params": {
    "name": "disk_space",
    "args": {}
  }
}
```

#### List Tools Format
```json
{
  "id": "request-1",
  "method": "list_tools",
  "params": {}
}
```

**Response Envelope:**

All responses follow this standardized envelope format:

```json
{
  "ok": boolean,
  "summary": "string",
  "need_confirm": boolean,
  "data": object,
  "stdout": "string",
  "stderr": "string", 
  "error": "string",
  "metrics": {
    "elapsed_ms": number,
    "exit_code": number
  }
}
```

**Required Fields:**
- `ok`: Operation success status (boolean)
- `summary`: Brief operation summary (string)
- `metrics.elapsed_ms`: Execution time in milliseconds (number)
- `metrics.exit_code`: Process exit code (number, 0 for success)

**Optional Fields:**
- `need_confirm`: Whether confirmation is required (boolean)
- `data`: Structured response data (object)
- `stdout`: Command standard output (string)
- `stderr`: Command standard error (string)
- `error`: Error message for failed operations (string)

## API Examples

### Example 1: List Tools

**Request:**
```bash
curl -X POST http://localhost:9400/mcp \
  -H "Content-Type: application/json" \
  -d '{
    "id": "list-1",
    "method": "list_tools",
    "params": {}
  }'
```

**Response:**
```json
{
  "ok": true,
  "summary": "Available tools: 5 tools found",
  "data": {
    "tools": [
      {
        "name": "disk_space",
        "description": "Check filesystem disk space usage",
        "inputSchema": {
          "type": "object",
          "properties": {},
          "additionalProperties": false
        }
      },
      {
        "name": "docker_ps",
        "description": "List Docker containers with status information",
        "inputSchema": {
          "type": "object",
          "properties": {},
          "additionalProperties": false
        }
      }
    ]
  },
  "metrics": {
    "elapsed_ms": 45,
    "exit_code": 0
  }
}
```

### Example 2: Call Tool (Direct Format)

**Request:**
```bash
curl -X POST http://localhost:9400/mcp \
  -H "Content-Type: application/json" \
  -d '{
    "id": "disk-1",
    "method": "call_tool",
    "name": "disk_space",
    "args": {}
  }'
```

**Response:**
```json
{
  "ok": true,
  "summary": "Disk space check completed",
  "data": {
    "filesystems": [
      {
        "filesystem": "/dev/sda1",
        "size": "20G",
        "used": "12G",
        "available": "7.2G",
        "use_percent": "63%",
        "mounted_on": "/"
      }
    ]
  },
  "stdout": "Filesystem      Size  Used Avail Use% Mounted on\n/dev/sda1        20G   12G  7.2G  63% /",
  "metrics": {
    "elapsed_ms": 123,
    "exit_code": 0
  }
}
```

### Example 3: Call Tool (Params Format)

**Request:**
```bash
curl -X POST http://localhost:9400/mcp \
  -H "Content-Type: application/json" \
  -d '{
    "id": "disk-2",
    "method": "call_tool",
    "params": {
      "name": "disk_space",
      "args": {}
    }
  }'
```

**Response:** (Same as Example 2)

### Example 4: Mutating Tool Requiring Confirmation

**Request (without confirmation):**
```bash
curl -X POST http://localhost:9400/mcp \
  -H "Content-Type: application/json" \
  -d '{
    "id": "publish-1",
    "method": "call_tool",
    "name": "blog_publish_static",
    "args": {
      "source_files": ["post1.md", "post2.md"]
    }
  }'
```

**Response:**
```json
{
  "ok": false,
  "need_confirm": true,
  "summary": "blog_publish_static requires confirmation",
  "error": "Confirmation required for mutating operation",
  "data": {
    "required_arg": "_confirm",
    "required_value": true,
    "suggestion": "Add '_confirm': true to blog_publish_static arguments"
  },
  "metrics": {
    "elapsed_ms": 5,
    "exit_code": 1
  }
}
```

**Request (with confirmation):**
```bash
curl -X POST http://localhost:9400/mcp \
  -H "Content-Type: application/json" \
  -d '{
    "id": "publish-2",
    "method": "call_tool",
    "name": "blog_publish_static",
    "args": {
      "source_files": ["post1.md", "post2.md"],
      "_confirm": true
    }
  }'
```

**Response:**
```json
{
  "ok": true,
  "summary": "Published 2 files successfully",
  "data": {
    "published_files": ["post1.md", "post2.md"],
    "publish_path": "/app/data/blog/publish"
  },
  "stdout": "Published post1.md\nPublished post2.md",
  "metrics": {
    "elapsed_ms": 234,
    "exit_code": 0
  }
}
```

### Example 5: Degraded Docker Tool Response

**Request:**
```bash
curl -X POST http://localhost:9400/mcp \
  -H "Content-Type: application/json" \
  -d '{
    "id": "docker-1",
    "method": "call_tool",
    "name": "docker_ps",
    "args": {}
  }'
```

**Response (when Docker socket not available):**
```json
{
  "ok": false,
  "summary": "docker_ps unavailable",
  "error": "Docker socket not accessible in this container",
  "data": {
    "tool": "docker_ps",
    "reason": "Docker socket not accessible",
    "suggestion": "Mount /var/run/docker.sock and add docker group to enable Docker operations"
  },
  "metrics": {
    "elapsed_ms": 12,
    "exit_code": 1
  }
}
```

## Error Handling

### Validation Errors

**Request with invalid method:**
```json
{
  "ok": false,
  "summary": "Request processing failed",
  "error": "HTTP bridge error: Method must be one of: ['list_tools', 'call_tool']",
  "metrics": {
    "elapsed_ms": 2,
    "exit_code": 1
  }
}
```

### MCP Engine Communication Errors

**Engine timeout:**
```json
{
  "ok": false,
  "summary": "MCP engine timeout",
  "error": "MCP engine did not respond within timeout period (60s)",
  "metrics": {
    "elapsed_ms": 60000,
    "exit_code": 124
  }
}
```

**Engine process failure:**
```json
{
  "ok": false,
  "summary": "MCP engine process failed",
  "error": "Process exited with code 1: Policy file not found",
  "metrics": {
    "elapsed_ms": 156,
    "exit_code": 1
  }
}
```

## Compatibility Guarantees

1. **Response Envelope**: The JSON response envelope structure MUST remain stable across versions.

2. **Required Fields**: The required fields (`ok`, `summary`, `metrics.elapsed_ms`, `metrics.exit_code`) MUST always be present.

3. **HTTP Status**: The `/mcp` endpoint MUST always return HTTP 200, regardless of operation success or failure.

4. **Request Formats**: Both direct and params request formats MUST continue to be supported.

5. **Health Endpoint**: The `/health` endpoint response format MUST remain stable with all required fields.

## Version History

- **v1.0.0**: Initial API contract definition
  - Established HTTP 200 always policy for /mcp endpoint
  - Defined standardized JSON envelope format
  - Required metrics fields for audit/telemetry
  - Support for multiple request formats

## Migration Notes

When the internal MCP engine implementation changes from subprocess to in-process calls:

1. The HTTP API contract MUST remain unchanged
2. All existing request/response examples MUST continue to work
3. Response timing may improve but envelope format stays the same
4. Error messages may change but error structure remains consistent

This API contract serves as the external compatibility boundary for all downstream systems consuming the BurlyMCP HTTP Bridge.