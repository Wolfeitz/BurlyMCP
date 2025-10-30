# Security Best Practices for Burly MCP

## Overview

This document provides comprehensive security best practices for deploying, configuring, and operating Burly MCP in production environments. These practices are designed to minimize security risks while maintaining operational efficiency.

## Deployment Security

### Container Security Hardening

#### 1. Use Non-Root User
```dockerfile
# Always run as non-privileged user
RUN useradd -u 1000 -m agentops --shell /bin/bash
USER agentops
```

**Why**: Prevents privilege escalation attacks and limits damage from container escape.

#### 2. Drop Unnecessary Capabilities
```yaml
# docker-compose.yml
services:
  burly-mcp:
    cap_drop:
      - ALL
    cap_add:
      - CHOWN      # Only for log file management
      - SETUID     # Only for user switching if needed
      - SETGID     # Only for group management if needed
```

**Why**: Reduces attack surface by removing unnecessary kernel capabilities.

#### 3. Use Read-Only Root Filesystem
```yaml
# docker-compose.yml
services:
  burly-mcp:
    read_only: true
    tmpfs:
      - /tmp:noexec,nosuid,size=100m
    volumes:
      - logs:/var/log/agentops:rw
```

**Why**: Prevents runtime tampering and malware persistence.

#### 4. Enable Security Options
```yaml
# docker-compose.yml
services:
  burly-mcp:
    security_opt:
      - no-new-privileges:true
      - apparmor:docker-default
    sysctls:
      - net.ipv4.ip_unprivileged_port_start=0
```

**Why**: Prevents privilege escalation and enables additional security layers.

### Network Security

#### 1. Disable Network Access When Possible
```yaml
# docker-compose.yml
services:
  burly-mcp:
    network_mode: none  # For MCP over stdio
```

**Why**: Eliminates network-based attack vectors.

#### 2. Use Custom Networks for Multi-Container Setups
```yaml
# docker-compose.yml
networks:
  burly-internal:
    driver: bridge
    internal: true
    
services:
  burly-mcp:
    networks:
      - burly-internal
```

**Why**: Provides network isolation and controlled communication.

#### 3. Implement Network Policies
```yaml
# If using Kubernetes
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: burly-mcp-policy
spec:
  podSelector:
    matchLabels:
      app: burly-mcp
  policyTypes:
  - Ingress
  - Egress
  egress:
  - to: []
    ports:
    - protocol: TCP
      port: 443  # Only HTTPS outbound
```

**Why**: Controls network traffic and prevents lateral movement.

## Configuration Security

### Secret Management

#### 1. Use Docker Secrets (Production)
```yaml
# docker-compose.yml
version: '3.8'
services:
  burly-mcp:
    secrets:
      - gotify_token
      - docker_registry_auth
    environment:
      - GOTIFY_TOKEN_FILE=/run/secrets/gotify_token

secrets:
  gotify_token:
    external: true
  docker_registry_auth:
    external: true
```

**Best Practices**:
- Never hardcode secrets in images or compose files
- Use external secret management systems
- Rotate secrets regularly
- Audit secret access

#### 2. Environment Variable Security
```bash
# .env.example - Template only, never commit actual .env
GOTIFY_TOKEN=your_secret_token_here
DOCKER_SOCKET=/var/run/docker.sock
AUDIT_ENABLED=true
LOG_LEVEL=INFO

# Security warnings in comments
# WARNING: GOTIFY_TOKEN contains sensitive data - never commit to version control
# WARNING: Ensure DOCKER_SOCKET has proper permissions (660 or 600)
```

**Best Practices**:
- Use `.env.example` as template
- Add security warnings for sensitive variables
- Validate environment variables on startup
- Use strong, unique tokens

#### 3. Configuration Validation
```python
# Example configuration validation
import os
from pathlib import Path

class SecurityConfig:
    def __init__(self):
        self.validate_environment()
        self.validate_file_permissions()
        self.validate_secrets()
    
    def validate_environment(self):
        """Validate security-critical environment variables"""
        required_vars = ['GOTIFY_TOKEN', 'AUDIT_ENABLED']
        for var in required_vars:
            if not os.getenv(var):
                raise ValueError(f"Required security variable {var} not set")
    
    def validate_file_permissions(self):
        """Validate file permissions for security"""
        sensitive_files = [
            '/run/secrets/gotify_token',
            '/config/policy/tools.yaml'
        ]
        for file_path in sensitive_files:
            path = Path(file_path)
            if path.exists():
                stat = path.stat()
                if stat.st_mode & 0o077:  # Check for world/group permissions
                    raise ValueError(f"Insecure permissions on {file_path}")
```

### Policy Configuration

#### 1. Principle of Least Privilege
```yaml
# config/policy/tools.yaml
tools:
  docker_ps:
    enabled: true
    confirmation_required: false
    timeout: 30
    allowed_args:
      - "--format"
      - "--filter"
    blocked_args:
      - "--all"  # Prevent showing stopped containers
      
  docker_exec:
    enabled: false  # Disabled by default - high risk
    confirmation_required: true
    timeout: 60
    
  blog_publish:
    enabled: true
    confirmation_required: true  # Always require confirmation for publishing
    allowed_paths:
      - "/app/blog/stage/*"
    blocked_paths:
      - "/app/blog/publish/*"  # Prevent direct publish access
```

**Best Practices**:
- Start with minimal permissions
- Require confirmation for dangerous operations
- Use path restrictions for file operations
- Regular policy reviews and updates

#### 2. Input Validation Rules
```yaml
# config/policy/validation.yaml
validation_rules:
  file_paths:
    pattern: "^[a-zA-Z0-9._/-]+\\.(md|txt|json)$"
    max_length: 255
    blocked_patterns:
      - "\\.\\."  # Prevent path traversal
      - "^/"      # Prevent absolute paths
      - "\\x00"   # Prevent null bytes
      
  docker_commands:
    allowed_commands:
      - "ps"
      - "images"
      - "inspect"
    blocked_commands:
      - "exec"
      - "run"
      - "rm"
      - "rmi"
```

## Operational Security

### Monitoring and Alerting

#### 1. Security Event Monitoring
```python
# Example security monitoring
import logging
import json
from datetime import datetime

class SecurityMonitor:
    def __init__(self):
        self.security_logger = logging.getLogger('security')
        
    def log_security_event(self, event_type, details, severity='INFO'):
        """Log security events in structured format"""
        event = {
            'timestamp': datetime.utcnow().isoformat(),
            'event_type': event_type,
            'severity': severity,
            'details': details,
            'source': 'burly-mcp'
        }
        self.security_logger.info(json.dumps(event))
        
        # Alert on high-severity events
        if severity in ['ERROR', 'CRITICAL']:
            self.send_alert(event)
    
    def monitor_failed_authentications(self, client_id, reason):
        """Monitor authentication failures"""
        self.log_security_event(
            'authentication_failure',
            {'client_id': client_id, 'reason': reason},
            'WARNING'
        )
    
    def monitor_policy_violations(self, tool_name, violation_type):
        """Monitor policy violations"""
        self.log_security_event(
            'policy_violation',
            {'tool_name': tool_name, 'violation': violation_type},
            'ERROR'
        )
```

#### 2. Audit Log Analysis
```bash
#!/bin/bash
# audit-analysis.sh - Analyze audit logs for security events

# Check for suspicious patterns
grep -E "(authentication_failure|policy_violation|path_traversal)" /var/log/agentops/audit.jsonl

# Check for unusual tool usage
jq -r 'select(.tool_name == "docker_exec") | .timestamp + " " + .details.command' /var/log/agentops/audit.jsonl

# Check for failed operations
jq -r 'select(.execution_status == "failed") | .timestamp + " " + .tool_name + " " + .error_message' /var/log/agentops/audit.jsonl

# Generate daily security report
python3 /app/scripts/security-report.py --date $(date +%Y-%m-%d)
```

### Incident Response

#### 1. Security Incident Classification
```python
# security_incidents.py
from enum import Enum

class IncidentSeverity(Enum):
    CRITICAL = "critical"    # Immediate threat to system security
    HIGH = "high"           # Significant security risk
    MEDIUM = "medium"       # Moderate security concern
    LOW = "low"            # Minor security issue
    INFO = "info"          # Security-related information

class IncidentType(Enum):
    AUTHENTICATION_FAILURE = "auth_failure"
    AUTHORIZATION_BYPASS = "authz_bypass"
    POLICY_VIOLATION = "policy_violation"
    PATH_TRAVERSAL = "path_traversal"
    COMMAND_INJECTION = "command_injection"
    CONTAINER_ESCAPE = "container_escape"
    RESOURCE_EXHAUSTION = "resource_exhaustion"
    SUSPICIOUS_ACTIVITY = "suspicious_activity"

def classify_incident(event_data):
    """Classify security incidents based on event data"""
    if 'path_traversal' in event_data.get('details', {}):
        return IncidentType.PATH_TRAVERSAL, IncidentSeverity.HIGH
    elif event_data.get('tool_name') == 'docker_exec':
        return IncidentType.AUTHORIZATION_BYPASS, IncidentSeverity.CRITICAL
    # Add more classification logic
```

#### 2. Automated Response Actions
```python
# automated_response.py
class SecurityResponse:
    def __init__(self):
        self.blocked_clients = set()
        
    def handle_incident(self, incident_type, severity, details):
        """Handle security incidents with automated responses"""
        
        if severity == IncidentSeverity.CRITICAL:
            self.emergency_shutdown(details)
        elif incident_type == IncidentType.PATH_TRAVERSAL:
            self.block_client(details.get('client_id'))
        elif incident_type == IncidentType.RESOURCE_EXHAUSTION:
            self.apply_rate_limiting(details.get('client_id'))
            
    def emergency_shutdown(self, details):
        """Emergency shutdown for critical incidents"""
        logging.critical(f"EMERGENCY SHUTDOWN: {details}")
        # Implement graceful shutdown
        
    def block_client(self, client_id):
        """Block malicious client"""
        self.blocked_clients.add(client_id)
        logging.warning(f"Blocked client: {client_id}")
```

## Development Security

### Secure Coding Practices

#### 1. Input Validation
```python
# secure_validation.py
import re
from pathlib import Path
from typing import Optional

class InputValidator:
    # Safe filename pattern
    SAFE_FILENAME = re.compile(r'^[a-zA-Z0-9._-]+\.(md|txt|json|yaml)$')
    
    # Path traversal detection
    TRAVERSAL_PATTERNS = [
        re.compile(r'\.\.'),      # Parent directory
        re.compile(r'^/'),        # Absolute path
        re.compile(r'\\'),        # Windows path separator
        re.compile(r'\x00'),      # Null byte
    ]
    
    @classmethod
    def validate_filename(cls, filename: str) -> bool:
        """Validate filename for security"""
        if not filename or len(filename) > 255:
            return False
            
        if not cls.SAFE_FILENAME.match(filename):
            return False
            
        for pattern in cls.TRAVERSAL_PATTERNS:
            if pattern.search(filename):
                return False
                
        return True
    
    @classmethod
    def validate_path(cls, path: str, allowed_base: Path) -> Optional[Path]:
        """Validate and resolve path safely"""
        try:
            # Convert to Path object
            path_obj = Path(path)
            
            # Resolve to absolute path
            resolved = path_obj.resolve()
            
            # Check if within allowed base
            if not resolved.is_relative_to(allowed_base):
                return None
                
            return resolved
            
        except (OSError, ValueError):
            return None
```

#### 2. Output Sanitization
```python
# output_sanitizer.py
import re
import json

class OutputSanitizer:
    # Patterns for sensitive data
    SENSITIVE_PATTERNS = [
        re.compile(r'password["\s]*[:=]["\s]*[^\s"]+', re.IGNORECASE),
        re.compile(r'token["\s]*[:=]["\s]*[^\s"]+', re.IGNORECASE),
        re.compile(r'key["\s]*[:=]["\s]*[^\s"]+', re.IGNORECASE),
        re.compile(r'secret["\s]*[:=]["\s]*[^\s"]+', re.IGNORECASE),
    ]
    
    @classmethod
    def sanitize_output(cls, output: str) -> str:
        """Remove sensitive data from output"""
        sanitized = output
        
        for pattern in cls.SENSITIVE_PATTERNS:
            sanitized = pattern.sub('[REDACTED]', sanitized)
            
        return sanitized
    
    @classmethod
    def sanitize_logs(cls, log_data: dict) -> dict:
        """Sanitize log data before writing"""
        sanitized = log_data.copy()
        
        # Remove sensitive fields
        sensitive_fields = ['password', 'token', 'secret', 'key']
        for field in sensitive_fields:
            if field in sanitized:
                sanitized[field] = '[REDACTED]'
                
        return sanitized
```

### Security Testing

#### 1. Security Test Cases
```python
# test_security.py
import pytest
from burly_mcp.security import InputValidator, OutputSanitizer

class TestInputValidation:
    def test_path_traversal_prevention(self):
        """Test path traversal attack prevention"""
        malicious_paths = [
            "../etc/passwd",
            "../../root/.ssh/id_rsa",
            "/etc/shadow",
            "blog/../../../etc/passwd",
            "blog/./../../etc/passwd",
        ]
        
        for path in malicious_paths:
            assert not InputValidator.validate_filename(path)
    
    def test_null_byte_injection(self):
        """Test null byte injection prevention"""
        malicious_inputs = [
            "file.txt\x00.exe",
            "blog.md\x00",
            "\x00/etc/passwd",
        ]
        
        for input_str in malicious_inputs:
            assert not InputValidator.validate_filename(input_str)
    
    def test_command_injection_prevention(self):
        """Test command injection prevention"""
        malicious_commands = [
            "; rm -rf /",
            "$(whoami)",
            "`id`",
            "| cat /etc/passwd",
        ]
        
        for cmd in malicious_commands:
            assert not InputValidator.validate_filename(cmd)

class TestOutputSanitization:
    def test_secret_redaction(self):
        """Test sensitive data redaction"""
        sensitive_output = '''
        password: secret123
        api_token: abc123def456
        secret_key: mysecret
        '''
        
        sanitized = OutputSanitizer.sanitize_output(sensitive_output)
        assert 'secret123' not in sanitized
        assert 'abc123def456' not in sanitized
        assert 'mysecret' not in sanitized
        assert '[REDACTED]' in sanitized
```

#### 2. Penetration Testing Scripts
```bash
#!/bin/bash
# security-tests.sh - Basic security testing

echo "=== Burly MCP Security Tests ==="

# Test 1: Path traversal attempts
echo "Testing path traversal protection..."
python3 -c "
from burly_mcp.tools.blog_tools import BlogTools
blog = BlogTools()
try:
    blog.read_file('../../../etc/passwd')
    print('FAIL: Path traversal not blocked')
except Exception as e:
    print('PASS: Path traversal blocked')
"

# Test 2: Command injection attempts
echo "Testing command injection protection..."
python3 -c "
from burly_mcp.tools.docker_tools import DockerTools
docker = DockerTools()
try:
    docker.list_containers('; rm -rf /')
    print('FAIL: Command injection not blocked')
except Exception as e:
    print('PASS: Command injection blocked')
"

# Test 3: Resource limits
echo "Testing resource limits..."
timeout 5s python3 -c "
import time
while True:
    time.sleep(0.1)
" && echo "FAIL: No timeout enforcement" || echo "PASS: Timeout enforced"

echo "=== Security Tests Complete ==="
```

## Compliance and Governance

### Security Policies

#### 1. Access Control Policy
```yaml
# access-control-policy.yaml
access_control:
  default_policy: deny
  
  roles:
    admin:
      permissions:
        - docker:*
        - blog:*
        - system:*
      confirmation_required: true
      
    operator:
      permissions:
        - docker:ps
        - docker:images
        - blog:read
        - blog:stage
      confirmation_required: false
      
    readonly:
      permissions:
        - docker:ps
        - blog:read
      confirmation_required: false
  
  tools:
    docker_exec:
      minimum_role: admin
      additional_approvals: 2
      
    blog_publish:
      minimum_role: operator
      business_hours_only: true
```

#### 2. Data Classification
```yaml
# data-classification.yaml
data_classification:
  public:
    - blog_content
    - documentation
    - public_configurations
    
  internal:
    - audit_logs
    - performance_metrics
    - non_sensitive_configs
    
  confidential:
    - authentication_tokens
    - api_keys
    - user_credentials
    
  restricted:
    - encryption_keys
    - security_policies
    - incident_reports

retention_policies:
  audit_logs: 90_days
  performance_metrics: 30_days
  security_incidents: 7_years
```

### Audit and Compliance

#### 1. Compliance Checklist
```markdown
# Security Compliance Checklist

## Monthly Tasks
- [ ] Review access control policies
- [ ] Analyze security audit logs
- [ ] Update vulnerability assessments
- [ ] Test incident response procedures
- [ ] Review and rotate secrets

## Quarterly Tasks
- [ ] Conduct security risk assessment
- [ ] Update threat model
- [ ] Review security training materials
- [ ] Test disaster recovery procedures
- [ ] Audit third-party integrations

## Annual Tasks
- [ ] Comprehensive security audit
- [ ] Penetration testing
- [ ] Security policy review
- [ ] Compliance certification renewal
- [ ] Security architecture review
```

#### 2. Audit Trail Requirements
```python
# audit_requirements.py
from dataclasses import dataclass
from datetime import datetime
from typing import Dict, Any

@dataclass
class AuditEvent:
    timestamp: datetime
    user_id: str
    session_id: str
    tool_name: str
    action: str
    parameters: Dict[str, Any]
    result: str
    duration_ms: int
    source_ip: str
    user_agent: str
    
    def to_audit_log(self) -> Dict[str, Any]:
        """Convert to audit log format"""
        return {
            'timestamp': self.timestamp.isoformat(),
            'user_id': self.user_id,
            'session_id': self.session_id,
            'tool_name': self.tool_name,
            'action': self.action,
            'parameters_hash': hash(str(self.parameters)),
            'result': self.result,
            'duration_ms': self.duration_ms,
            'source_ip': self.source_ip,
            'user_agent': self.user_agent,
        }
```

## Emergency Procedures

### Security Incident Response

#### 1. Incident Response Playbook
```markdown
# Security Incident Response Playbook

## Phase 1: Detection and Analysis (0-15 minutes)
1. **Identify** the security incident
2. **Classify** severity level (Critical/High/Medium/Low)
3. **Notify** security team and stakeholders
4. **Document** initial findings

## Phase 2: Containment (15-60 minutes)
1. **Isolate** affected systems
2. **Preserve** evidence and logs
3. **Implement** temporary controls
4. **Communicate** with stakeholders

## Phase 3: Eradication (1-24 hours)
1. **Remove** threats and vulnerabilities
2. **Patch** security weaknesses
3. **Update** security controls
4. **Validate** system integrity

## Phase 4: Recovery (1-72 hours)
1. **Restore** systems from clean backups
2. **Monitor** for recurring issues
3. **Gradually** restore normal operations
4. **Document** lessons learned

## Phase 5: Post-Incident (1-2 weeks)
1. **Conduct** post-incident review
2. **Update** security procedures
3. **Implement** preventive measures
4. **Report** to management and regulators
```

#### 2. Emergency Contacts
```yaml
# emergency-contacts.yaml
emergency_contacts:
  security_team:
    primary: "security@company.com"
    phone: "+1-555-SECURITY"
    escalation: "ciso@company.com"
    
  incident_response:
    coordinator: "ir-coordinator@company.com"
    technical_lead: "ir-tech@company.com"
    communications: "ir-comms@company.com"
    
  external_resources:
    cyber_insurance: "+1-555-CYBER-INS"
    legal_counsel: "legal@company.com"
    law_enforcement: "911"
    
response_times:
  critical: "15 minutes"
  high: "1 hour"
  medium: "4 hours"
  low: "24 hours"
```

---

**Document Version**: 1.0  
**Last Updated**: 2024-01-01  
**Next Review**: 2024-04-01  
**Owner**: Security Team  
**Classification**: Internal Use