# Container Security Guide

This document outlines the security posture of the BurlyMCP Runtime Container and provides guidance for secure deployment.

## Security Architecture

### Non-Root Execution

The BurlyMCP container runs as a dedicated non-root user (`mcp`, UID 1000) by default:

- **User**: `mcp` (UID 1000, GID 1000)
- **Home Directory**: `/home/mcp`
- **Shell**: `/bin/bash`
- **Working Directory**: `/app`

**Security Benefit**: Limits the impact of potential container escapes and follows the principle of least privilege.

### File System Permissions

The container uses restrictive file system permissions:

```
/app                    - 755 (mcp:mcp) - Application directory
/var/log/agentops       - 750 (mcp:mcp) - Audit logs (owner + group read/write)
/app/data/blog/stage    - 755 (mcp:mcp) - Blog staging (read-only by default)
/app/data/blog/publish  - 755 (mcp:mcp) - Blog publishing
```

**Security Benefit**: Prevents unauthorized access to sensitive files and limits write access to necessary directories only.

### Network Security

The container exposes a single HTTP port (9400) with configurable security features:

- **Rate Limiting**: 60 requests/minute per IP (enabled by default)
- **Request Size Limits**: 10KB maximum request body
- **Input Validation**: Strict validation of tool names and arguments
- **Error Handling**: No information disclosure in error responses

## Deployment Modes

### Minimal Mode (Recommended for Production)

**Command**:
```bash
docker run -p 9400:9400 ghcr.io/<org>/burlymcp:main
```

**Security Characteristics**:
- ✅ No elevated privileges required
- ✅ No host file system access
- ✅ No Docker socket access
- ✅ Rate limiting enabled
- ✅ Strict input validation
- ✅ Non-root execution

**Available Features**:
- HTTP endpoints (/health, /mcp)
- System information tools (disk_space, system_info)
- Blog tools (if directories mounted)
- Audit logging (container-internal)

**Limitations**:
- Docker operations unavailable
- Host file system access unavailable
- Notifications require configuration

### Privileged Mode (Use with Caution)

**Command**:
```bash
# Get Docker group GID
DOCKER_GID=$(getent group docker | cut -d: -f3)

# Run with Docker socket access
docker run -p 9400:9400 \
  --group-add $DOCKER_GID \
  -v /var/run/docker.sock:/var/run/docker.sock:ro \
  ghcr.io/<org>/burlymcp:main
```

**Security Implications**:
- ⚠️ **HIGH RISK**: Docker socket access grants root-equivalent privileges on the host
- ⚠️ Container can inspect, start, stop, and modify any container on the host
- ⚠️ Container can mount host file systems through Docker operations
- ⚠️ Potential for container escape through Docker API abuse

**Additional Features**:
- Docker container inspection (docker_ps, docker_inspect)
- Docker image management
- Container lifecycle operations

**Security Mitigations**:
- Mount Docker socket read-only when possible
- Use network isolation (don't expose on public networks)
- Monitor Docker API usage through audit logs
- Consider using Docker-in-Docker instead of socket mounting

## Security Configuration

### Environment Variables

#### Security Controls

- `STRICT_SECURITY_MODE=true` (default) - Enable strict security validation
- `RATE_LIMIT_DISABLED=false` (default) - Enable rate limiting
- `AUDIT_ENABLED=true` (default) - Enable audit logging

#### Rate Limiting

- `RATE_LIMIT_DISABLED=true` - Disable rate limiting (lab environments only)
- Default: 60 requests/minute per IP address
- Overrides return structured JSON errors, not HTTP 429

#### Request Validation

- Maximum request size: 10KB
- Tool name validation: alphanumeric and underscore only
- Argument complexity limits: max 5 levels deep, 100 items per collection
- String length limits: 10KB per string value

### Security Validation on Startup

The container performs comprehensive security validation on startup:

1. **User Privilege Check**: Ensures non-root execution
2. **File Permission Validation**: Verifies secure directory permissions
3. **Docker Socket Assessment**: Evaluates Docker access configuration
4. **Environment Security**: Validates security-related environment variables
5. **Network Configuration**: Checks listening configuration

**Startup Behavior**:
- **Errors**: Container exits with non-zero code
- **Warnings**: Container starts but logs security concerns
- **Success**: Container starts normally

## Security Monitoring

### Audit Logging

All operations are logged to `/var/log/agentops/audit.jsonl`:

```json
{
  "timestamp": "2024-01-01T12:00:00Z",
  "operation": "call_tool",
  "tool_name": "docker_ps",
  "user_id": "system",
  "success": true,
  "duration_ms": 150,
  "request_id": "req-123"
}
```

**Security Events Logged**:
- Tool executions (success/failure)
- Security validation failures
- Rate limit violations
- Invalid request attempts
- Container startup/shutdown

### Health Monitoring

The `/health` endpoint provides security status information:

```json
{
  "status": "ok",
  "strict_security_mode": true,
  "docker_available": false,
  "notifications_enabled": false,
  "policy_loaded": true
}
```

**Security Indicators**:
- `strict_security_mode`: Security validation enabled
- `docker_available`: Docker socket access status
- `policy_loaded`: Policy file validation status

## Security Best Practices

### Deployment

1. **Use Minimal Mode by Default**: Only enable privileged features when necessary
2. **Network Isolation**: Don't expose on public networks without additional security layers
3. **Regular Updates**: Keep container images updated with security patches
4. **Monitor Logs**: Implement log monitoring for security events
5. **Resource Limits**: Set appropriate CPU and memory limits

### Docker Socket Access

If Docker socket access is required:

1. **Read-Only Mount**: Use `:ro` flag when possible
2. **Network Isolation**: Don't expose on untrusted networks
3. **Audit Monitoring**: Monitor all Docker API calls
4. **Principle of Least Privilege**: Only grant access to specific containers/images
5. **Consider Alternatives**: Use Docker-in-Docker or remote Docker API when possible

### Configuration Management

1. **Secrets Management**: Use Docker secrets or external secret management
2. **Environment Variables**: Don't include secrets in environment variables
3. **Configuration Files**: Mount configuration files read-only
4. **Policy Updates**: Regularly review and update policy files

## Threat Model

### Threats Mitigated

- **Container Escape**: Non-root execution limits impact
- **Resource Exhaustion**: Rate limiting and request size limits
- **Information Disclosure**: Structured error responses without stack traces
- **Command Injection**: Input validation and sanitization
- **Path Traversal**: Path validation and sandboxing

### Residual Risks

- **Docker Socket Access**: Root-equivalent privileges when enabled
- **Network Attacks**: HTTP endpoint exposed (mitigate with network controls)
- **Supply Chain**: Dependencies and base image vulnerabilities
- **Configuration Errors**: Misconfigured deployments

### Security Assumptions

- **Host Security**: Assumes secure host operating system
- **Network Security**: Assumes appropriate network controls
- **Image Integrity**: Assumes trusted container registry
- **Operator Security**: Assumes secure deployment practices

## Incident Response

### Security Event Detection

Monitor for these security indicators:

- Repeated rate limit violations
- Invalid tool name attempts
- Oversized request attempts
- Docker socket access without authorization
- Unexpected container restarts

### Response Procedures

1. **Immediate**: Review audit logs for attack patterns
2. **Short-term**: Isolate affected containers from network
3. **Medium-term**: Analyze attack vectors and update security controls
4. **Long-term**: Review and update security policies

### Forensics

Audit logs provide forensic evidence:
- Request timestamps and sources
- Tool execution details
- Security validation results
- Container lifecycle events

## Compliance Considerations

### Security Standards

The container design addresses common security frameworks:

- **CIS Docker Benchmark**: Non-root execution, minimal privileges
- **NIST Cybersecurity Framework**: Identify, Protect, Detect, Respond
- **OWASP Container Security**: Input validation, secure defaults

### Regulatory Requirements

Consider these requirements for regulated environments:

- **Audit Logging**: Comprehensive operation logging
- **Access Controls**: Role-based access through policy files
- **Data Protection**: Secure handling of sensitive information
- **Incident Response**: Security event detection and response

## Security Updates

### Update Process

1. Monitor security advisories for dependencies
2. Test security updates in non-production environments
3. Deploy updates using rolling deployment strategies
4. Validate security posture after updates

### Version Management

- Use specific image tags, not `latest`
- Maintain security patch history
- Test compatibility with security updates
- Document security-relevant configuration changes