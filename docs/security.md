# Security Documentation

Burly MCP is designed with security as a primary concern. This document outlines the security architecture, threat model, and best practices for secure deployment and operation.

## Security Architecture

### Defense in Depth

Burly MCP implements multiple layers of security controls:

1. **Input Validation**: All inputs validated against JSON schemas
2. **Policy Engine**: Whitelist-based tool execution with explicit permissions
3. **Audit Logging**: Comprehensive logging of all operations
4. **Container Security**: Non-root execution with minimal privileges
5. **Secret Management**: Secure handling of sensitive configuration
6. **Network Isolation**: Minimal network exposure

### Security Principles

- **Least Privilege**: Minimal permissions for all operations
- **Fail Secure**: Default to deny access when in doubt
- **Defense in Depth**: Multiple security layers
- **Audit Everything**: Comprehensive logging for compliance
- **Zero Trust**: Verify all inputs and operations

## Threat Model

### Assets

- **System Access**: Docker socket and file system access
- **Configuration Data**: Policy files and environment variables
- **Audit Logs**: Security and compliance records
- **Blog Content**: User-generated content and publications
- **Notification Channels**: External service integrations

### Threats

#### High Risk

1. **Arbitrary Code Execution**
   - **Mitigation**: Whitelist-based tool execution, input validation
   - **Detection**: Audit logging, command validation

2. **Path Traversal Attacks**
   - **Mitigation**: Path validation, chroot-like restrictions
   - **Detection**: Path pattern monitoring, audit logs

3. **Privilege Escalation**
   - **Mitigation**: Non-root container execution, capability dropping
   - **Detection**: Process monitoring, audit logging

4. **Secret Exposure**
   - **Mitigation**: Environment variables, Docker secrets
   - **Detection**: Secret scanning, audit logs

#### Medium Risk

1. **Denial of Service**
   - **Mitigation**: Resource limits, timeouts, rate limiting
   - **Detection**: Performance monitoring, audit logs

2. **Information Disclosure**
   - **Mitigation**: Output filtering, access controls
   - **Detection**: Audit logging, content analysis

3. **Configuration Tampering**
   - **Mitigation**: Read-only configuration, validation
   - **Detection**: File integrity monitoring

### Attack Vectors

- **MCP Protocol**: Malicious tool requests or parameters
- **File Operations**: Path traversal or unauthorized access
- **Docker Socket**: Container escape or privilege escalation
- **Environment Variables**: Secret injection or manipulation
- **Network Services**: External service compromise

## Security Controls

### Input Validation

All tool inputs are validated against strict JSON schemas:

```yaml
# Example: File path validation
file_path:
  type: "string"
  pattern: "^[a-zA-Z0-9._/-]+\\.md$"
  maxLength: 255
```

**Security Features:**
- Pattern matching for safe characters only
- Length limits to prevent buffer overflows
- Type validation to prevent injection attacks
- Additional properties rejection

### Policy Engine

The policy engine enforces security policies through:

- **Whitelist-Only Execution**: Only explicitly defined tools can run
- **Permission Matrices**: Fine-grained access controls per tool
- **Confirmation Requirements**: Dangerous operations require explicit approval
- **Resource Limits**: Timeouts and output size restrictions

### Audit Logging

Comprehensive audit logging captures:

```json
{
  "timestamp": "2024-01-01T12:00:00Z",
  "tool_name": "docker_ps",
  "user_context": "mcp_session_123",
  "execution_status": "success",
  "execution_time_ms": 150,
  "args_hash": "sha256:abc123...",
  "output_size": 1024,
  "security_flags": []
}
```

**Audit Features:**
- Structured JSON logging for analysis
- Sensitive data redaction
- Tamper-evident log format
- Retention policies for compliance

### Container Security

#### Non-Root Execution

```dockerfile
# Create non-privileged user
RUN useradd -u 1000 -m agentops --shell /bin/bash
USER agentops
```

#### Capability Dropping

```yaml
# Docker Compose security options
security_opt:
  - no-new-privileges:true
cap_drop:
  - ALL
cap_add:
  - CHOWN    # Only for log file management
  - SETUID   # Only for user switching
  - SETGID   # Only for group management
```

#### Read-Only Filesystem

```yaml
# Mount application as read-only
volumes:
  - ./src:/app/src:ro
  - ./config:/app/config:ro
  - logs:/var/log/agentops:rw  # Only logs writable
```

### Secret Management

#### Environment Variables (Development)

```bash
# .env file (never committed)
GOTIFY_TOKEN=your_secret_token
DOCKER_SOCKET=/var/run/docker.sock
```

#### Docker Secrets (Production)

```yaml
# docker-compose.yml
services:
  burly-mcp:
    secrets:
      - gotify_token
    environment:
      - GOTIFY_TOKEN_FILE=/run/secrets/gotify_token

secrets:
  gotify_token:
    external: true
```

## Security Validation

### Automated Security Scanning

#### Dependency Scanning

```bash
# Check for known vulnerabilities
pip-audit --desc --format=json

# Alternative: Safety
safety check --json
```

#### Static Code Analysis

```bash
# Security-focused linting
bandit -r src/ -f json -o bandit-report.json

# Additional security rules
semgrep --config=auto src/
```

#### Container Scanning

```bash
# Vulnerability scanning
trivy image --exit-code 1 --severity HIGH,CRITICAL burly-mcp:latest

# Configuration scanning
trivy config --exit-code 1 docker/
```

### Manual Security Testing

#### Path Traversal Testing

```python
# Test cases for path validation
test_paths = [
    "../etc/passwd",           # Parent directory
    "/etc/passwd",            # Absolute path
    "blog/../../../etc/passwd", # Complex traversal
    "blog/./../../etc/passwd",  # Current directory traversal
]
```

#### Input Validation Testing

```python
# Test malicious inputs
malicious_inputs = [
    {"file_path": "; rm -rf /"},     # Command injection
    {"file_path": "$(whoami)"},      # Command substitution
    {"file_path": "`id`"},           # Backtick execution
    {"file_path": "file.md\x00"},    # Null byte injection
]
```

## Incident Response

### Security Incident Classification

#### Critical (P0)
- Arbitrary code execution
- Privilege escalation
- Data breach or exposure

#### High (P1)
- Denial of service
- Authentication bypass
- Configuration tampering

#### Medium (P2)
- Information disclosure
- Policy violations
- Audit log tampering

### Response Procedures

1. **Detection**: Automated monitoring and manual reporting
2. **Assessment**: Determine scope and impact
3. **Containment**: Isolate affected systems
4. **Eradication**: Remove threat and vulnerabilities
5. **Recovery**: Restore normal operations
6. **Lessons Learned**: Update security controls

### Contact Information

- **Security Team**: security@example.com
- **Emergency Contact**: +1-555-SECURITY
- **PGP Key**: Available at keyserver.ubuntu.com

## Compliance and Governance

### Security Standards

- **OWASP Top 10**: Address common web application risks
- **CIS Controls**: Implement critical security controls
- **NIST Framework**: Follow cybersecurity framework guidelines

### Audit Requirements

- **Log Retention**: 90 days minimum for audit logs
- **Access Reviews**: Quarterly review of permissions
- **Vulnerability Management**: Monthly security scans
- **Incident Documentation**: All incidents documented and reviewed

### Privacy Considerations

- **Data Minimization**: Collect only necessary information
- **Purpose Limitation**: Use data only for intended purposes
- **Retention Limits**: Delete data when no longer needed
- **Access Controls**: Restrict access to authorized personnel

## Security Best Practices

### Deployment Security

1. **Use Docker Secrets** for production deployments
2. **Enable Audit Logging** with proper retention
3. **Configure Resource Limits** to prevent DoS
4. **Regular Security Updates** for dependencies
5. **Network Segmentation** to limit blast radius

### Operational Security

1. **Monitor Audit Logs** for suspicious activity
2. **Regular Vulnerability Scans** of containers and dependencies
3. **Access Control Reviews** for permissions and policies
4. **Incident Response Testing** through tabletop exercises
5. **Security Training** for development and operations teams

### Development Security

1. **Secure Coding Practices** following OWASP guidelines
2. **Code Review Requirements** for all security-related changes
3. **Automated Security Testing** in CI/CD pipelines
4. **Dependency Management** with vulnerability monitoring
5. **Secret Scanning** to prevent credential leaks

## Security Contacts

For security-related questions or to report vulnerabilities:

- **Email**: security@example.com
- **Response Time**: 24 hours for initial response
- **Disclosure Policy**: Coordinated disclosure preferred
- **Bug Bounty**: Contact us for program details

---

**Last Updated**: 2024-01-01  
**Next Review**: 2024-04-01  
**Document Owner**: Security Team