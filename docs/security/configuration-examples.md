# Security Configuration Examples and Warnings

## Overview

This document provides comprehensive security configuration examples for Burly MCP deployments. Each configuration includes security warnings, best practices, and potential risks to help operators make informed decisions.

## Environment Configuration

### Production Environment Variables

#### Secure Configuration Template
```bash
# .env.production - Production environment template
# WARNING: This file contains sensitive information - never commit to version control
# WARNING: Ensure file permissions are 600 (readable only by owner)

# === CORE SECURITY SETTINGS ===
# WARNING: These settings directly impact security posture

# Audit logging (REQUIRED for security compliance)
AUDIT_ENABLED=true
AUDIT_LOG_LEVEL=INFO
AUDIT_RETENTION_DAYS=90
# WARNING: Disabling audit logging violates security policies

# Security validation
SECURITY_VALIDATION_ENABLED=true
FAIL_ON_SECURITY_ERRORS=true
# WARNING: Disabling security validation creates significant risk

# === AUTHENTICATION AND AUTHORIZATION ===
# WARNING: Weak authentication settings compromise entire system

# MCP client authentication
MCP_AUTH_ENABLED=true
MCP_AUTH_METHOD=token
MCP_AUTH_TOKEN_FILE=/run/secrets/mcp_auth_token
# WARNING: Never set MCP_AUTH_TOKEN directly - use file-based secrets

# API rate limiting
RATE_LIMIT_ENABLED=true
RATE_LIMIT_REQUESTS_PER_MINUTE=60
RATE_LIMIT_BURST_SIZE=10
# WARNING: Disabling rate limiting enables DoS attacks

# === DOCKER SECURITY ===
# WARNING: Docker socket access provides significant privileges

# Docker daemon connection
DOCKER_SOCKET=/var/run/docker.sock
DOCKER_TIMEOUT=30
DOCKER_TLS_VERIFY=true
# WARNING: Ensure Docker socket has proper permissions (660 or 600)
# WARNING: Never expose Docker socket over network without TLS

# Container security
CONTAINER_USER_ID=1000
CONTAINER_GROUP_ID=1000
DROP_ALL_CAPABILITIES=true
# WARNING: Running as root (UID 0) violates security policy

# === FILE SYSTEM SECURITY ===
# WARNING: Path configuration affects file system access controls

# Blog content paths
BLOG_STAGE_ROOT=/app/data/blog/stage
BLOG_PUBLISH_ROOT=/app/data/blog/publish
BLOG_MAX_FILE_SIZE=10485760  # 10MB
# WARNING: Ensure blog directories have proper ownership and permissions

# Configuration paths
CONFIG_DIR=/app/config
POLICY_FILE=/app/config/policy/tools.yaml
# WARNING: Configuration files should be read-only in production

# Log paths
LOG_DIR=/var/log/agentops
LOG_MAX_SIZE=100MB
LOG_ROTATION_COUNT=10
# WARNING: Ensure log directory has proper permissions and monitoring

# === EXTERNAL SERVICES ===
# WARNING: External service credentials require secure handling

# Gotify notifications
GOTIFY_URL=https://gotify.example.com
GOTIFY_TOKEN_FILE=/run/secrets/gotify_token
GOTIFY_TLS_VERIFY=true
# WARNING: Never set GOTIFY_TOKEN directly - use file-based secrets
# WARNING: Always use HTTPS for external service communication

# Webhook notifications
WEBHOOK_URL_FILE=/run/secrets/webhook_url
WEBHOOK_TIMEOUT=10
WEBHOOK_RETRY_COUNT=3
# WARNING: Webhook URLs may contain sensitive authentication parameters

# === RESOURCE LIMITS ===
# WARNING: Resource limits prevent DoS attacks

# Memory limits
MAX_MEMORY_MB=512
MAX_OUTPUT_SIZE=1048576  # 1MB
MAX_LOG_SIZE=10485760   # 10MB

# Execution limits
MAX_EXECUTION_TIME=300  # 5 minutes
MAX_CONCURRENT_OPERATIONS=5
MAX_FILE_OPERATIONS_PER_MINUTE=100

# Network limits
MAX_NETWORK_CONNECTIONS=10
NETWORK_TIMEOUT=30

# === DEVELOPMENT OVERRIDES ===
# WARNING: Development settings should never be used in production

# Development mode (NEVER enable in production)
DEVELOPMENT_MODE=false
DEBUG_LOGGING=false
SKIP_SECURITY_CHECKS=false
# CRITICAL WARNING: These settings bypass security controls

# Testing overrides (NEVER enable in production)
DISABLE_AUDIT_LOGGING=false
ALLOW_INSECURE_CONNECTIONS=false
DISABLE_RATE_LIMITING=false
# CRITICAL WARNING: These settings create severe security vulnerabilities
```

#### Security Validation Script
```bash
#!/bin/bash
# validate-env-security.sh - Validate environment security settings

set -euo pipefail

echo "=== Burly MCP Environment Security Validation ==="

# Check for insecure development settings
check_development_settings() {
    echo "Checking development settings..."
    
    if [[ "${DEVELOPMENT_MODE:-false}" == "true" ]]; then
        echo "ERROR: DEVELOPMENT_MODE is enabled in production"
        exit 1
    fi
    
    if [[ "${DEBUG_LOGGING:-false}" == "true" ]]; then
        echo "WARNING: DEBUG_LOGGING is enabled - may expose sensitive data"
    fi
    
    if [[ "${SKIP_SECURITY_CHECKS:-false}" == "true" ]]; then
        echo "CRITICAL: SKIP_SECURITY_CHECKS is enabled - severe security risk"
        exit 1
    fi
}

# Check authentication settings
check_authentication() {
    echo "Checking authentication settings..."
    
    if [[ "${MCP_AUTH_ENABLED:-true}" != "true" ]]; then
        echo "ERROR: MCP authentication is disabled"
        exit 1
    fi
    
    if [[ -n "${MCP_AUTH_TOKEN:-}" ]]; then
        echo "ERROR: MCP_AUTH_TOKEN should not be set directly - use MCP_AUTH_TOKEN_FILE"
        exit 1
    fi
    
    if [[ -z "${MCP_AUTH_TOKEN_FILE:-}" ]]; then
        echo "ERROR: MCP_AUTH_TOKEN_FILE is not configured"
        exit 1
    fi
}

# Check file permissions
check_file_permissions() {
    echo "Checking file permissions..."
    
    # Check .env file permissions
    if [[ -f ".env" ]]; then
        perms=$(stat -c "%a" .env)
        if [[ "$perms" != "600" ]]; then
            echo "WARNING: .env file permissions are $perms, should be 600"
        fi
    fi
    
    # Check secret files
    if [[ -n "${MCP_AUTH_TOKEN_FILE:-}" && -f "${MCP_AUTH_TOKEN_FILE}" ]]; then
        perms=$(stat -c "%a" "${MCP_AUTH_TOKEN_FILE}")
        if [[ "$perms" != "600" && "$perms" != "400" ]]; then
            echo "WARNING: Secret file permissions are $perms, should be 600 or 400"
        fi
    fi
}

# Check Docker security
check_docker_security() {
    echo "Checking Docker security settings..."
    
    if [[ "${CONTAINER_USER_ID:-1000}" == "0" ]]; then
        echo "ERROR: Container running as root (UID 0)"
        exit 1
    fi
    
    if [[ "${DROP_ALL_CAPABILITIES:-true}" != "true" ]]; then
        echo "WARNING: Not dropping all capabilities - security risk"
    fi
    
    # Check Docker socket permissions
    if [[ -S "${DOCKER_SOCKET:-/var/run/docker.sock}" ]]; then
        perms=$(stat -c "%a" "${DOCKER_SOCKET}")
        if [[ "$perms" != "660" && "$perms" != "600" ]]; then
            echo "WARNING: Docker socket permissions are $perms, should be 660 or 600"
        fi
    fi
}

# Run all checks
check_development_settings
check_authentication
check_file_permissions
check_docker_security

echo "=== Security validation complete ==="
```

### Docker Secrets Configuration

#### Production Docker Compose with Secrets
```yaml
# docker-compose.prod.yml - Production configuration with security hardening
version: '3.8'

services:
  burly-mcp:
    build:
      context: .
      dockerfile: Dockerfile
      target: production
    
    # Security: Run as non-root user
    user: "1000:1000"
    
    # Security: Read-only root filesystem
    read_only: true
    
    # Security: Drop all capabilities
    cap_drop:
      - ALL
    cap_add:
      - CHOWN      # Only for log file management
      - SETUID     # Only for user switching
      - SETGID     # Only for group management
    
    # Security: Additional security options
    security_opt:
      - no-new-privileges:true
      - apparmor:docker-default
    
    # Security: Resource limits
    deploy:
      resources:
        limits:
          memory: 512M
          cpus: '0.5'
        reservations:
          memory: 256M
          cpus: '0.25'
    
    # Security: Environment variables (non-sensitive only)
    environment:
      # Core settings
      - AUDIT_ENABLED=true
      - SECURITY_VALIDATION_ENABLED=true
      - FAIL_ON_SECURITY_ERRORS=true
      
      # Resource limits
      - MAX_MEMORY_MB=512
      - MAX_EXECUTION_TIME=300
      - MAX_OUTPUT_SIZE=1048576
      
      # File paths
      - CONFIG_DIR=/app/config
      - LOG_DIR=/var/log/agentops
      - BLOG_STAGE_ROOT=/app/data/blog/stage
      - BLOG_PUBLISH_ROOT=/app/data/blog/publish
      
      # Secret file paths (not the secrets themselves)
      - MCP_AUTH_TOKEN_FILE=/run/secrets/mcp_auth_token
      - GOTIFY_TOKEN_FILE=/run/secrets/gotify_token
      - WEBHOOK_URL_FILE=/run/secrets/webhook_url
    
    # Security: Docker secrets for sensitive data
    secrets:
      - mcp_auth_token
      - gotify_token
      - webhook_url
    
    # Security: Minimal volume mounts
    volumes:
      # Application configuration (read-only)
      - ./config:/app/config:ro
      
      # Blog data (read-write, but restricted)
      - blog_stage:/app/data/blog/stage:rw
      - blog_publish:/app/data/blog/publish:rw
      
      # Logs (read-write)
      - logs:/var/log/agentops:rw
      
      # Docker socket (read-only, with proper permissions)
      - /var/run/docker.sock:/var/run/docker.sock:ro
      
      # Temporary files (in-memory)
      - type: tmpfs
        target: /tmp
        tmpfs:
          size: 100M
          mode: 1777
    
    # Security: Network isolation
    networks:
      - burly-internal
    
    # Security: No exposed ports (MCP over stdio)
    # ports: []  # Explicitly no ports
    
    # Health check
    healthcheck:
      test: ["CMD", "python", "-c", "import burly_mcp; print('healthy')"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 40s

# Security: Custom network for isolation
networks:
  burly-internal:
    driver: bridge
    internal: true  # No external access
    ipam:
      config:
        - subnet: 172.20.0.0/16

# Security: Named volumes with proper permissions
volumes:
  blog_stage:
    driver: local
    driver_opts:
      type: none
      o: bind,uid=1000,gid=1000
      device: /opt/burly-mcp/data/blog/stage
  
  blog_publish:
    driver: local
    driver_opts:
      type: none
      o: bind,uid=1000,gid=1000
      device: /opt/burly-mcp/data/blog/publish
  
  logs:
    driver: local
    driver_opts:
      type: none
      o: bind,uid=1000,gid=1000
      device: /opt/burly-mcp/logs

# Security: External secrets (managed outside compose)
secrets:
  mcp_auth_token:
    external: true
    name: burly_mcp_auth_token_v1
  
  gotify_token:
    external: true
    name: burly_gotify_token_v1
  
  webhook_url:
    external: true
    name: burly_webhook_url_v1
```

#### Secret Management Scripts
```bash
#!/bin/bash
# manage-secrets.sh - Docker secrets management

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SECRETS_DIR="${SCRIPT_DIR}/../secrets"

# Create secrets directory with proper permissions
create_secrets_dir() {
    mkdir -p "${SECRETS_DIR}"
    chmod 700 "${SECRETS_DIR}"
    echo "Created secrets directory: ${SECRETS_DIR}"
}

# Generate secure random token
generate_token() {
    openssl rand -base64 32 | tr -d "=+/" | cut -c1-32
}

# Create Docker secret from file
create_docker_secret() {
    local secret_name="$1"
    local secret_file="$2"
    
    if [[ ! -f "$secret_file" ]]; then
        echo "ERROR: Secret file not found: $secret_file"
        exit 1
    fi
    
    # Check if secret already exists
    if docker secret ls --format "{{.Name}}" | grep -q "^${secret_name}$"; then
        echo "WARNING: Secret $secret_name already exists"
        read -p "Remove and recreate? (y/N): " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            docker secret rm "$secret_name"
        else
            echo "Skipping $secret_name"
            return
        fi
    fi
    
    # Create the secret
    docker secret create "$secret_name" "$secret_file"
    echo "Created Docker secret: $secret_name"
    
    # Secure the source file
    chmod 600 "$secret_file"
}

# Initialize secrets for new deployment
init_secrets() {
    echo "Initializing secrets for Burly MCP..."
    
    create_secrets_dir
    
    # Generate MCP authentication token
    echo "Generating MCP authentication token..."
    generate_token > "${SECRETS_DIR}/mcp_auth_token"
    create_docker_secret "burly_mcp_auth_token_v1" "${SECRETS_DIR}/mcp_auth_token"
    
    # Gotify token (user must provide)
    echo "Please enter Gotify token (or press Enter to skip):"
    read -s gotify_token
    if [[ -n "$gotify_token" ]]; then
        echo "$gotify_token" > "${SECRETS_DIR}/gotify_token"
        create_docker_secret "burly_gotify_token_v1" "${SECRETS_DIR}/gotify_token"
    fi
    
    # Webhook URL (user must provide)
    echo "Please enter webhook URL (or press Enter to skip):"
    read webhook_url
    if [[ -n "$webhook_url" ]]; then
        echo "$webhook_url" > "${SECRETS_DIR}/webhook_url"
        create_docker_secret "burly_webhook_url_v1" "${SECRETS_DIR}/webhook_url"
    fi
    
    echo "Secret initialization complete!"
    echo "WARNING: Backup the secrets directory securely and remove local files"
}

# Rotate existing secrets
rotate_secrets() {
    echo "Rotating secrets for Burly MCP..."
    
    # Generate new version numbers
    local timestamp=$(date +%Y%m%d_%H%M%S)
    
    # Rotate MCP token
    echo "Rotating MCP authentication token..."
    generate_token > "${SECRETS_DIR}/mcp_auth_token_${timestamp}"
    create_docker_secret "burly_mcp_auth_token_${timestamp}" "${SECRETS_DIR}/mcp_auth_token_${timestamp}"
    
    echo "Secret rotation complete!"
    echo "WARNING: Update docker-compose.yml to use new secret versions"
    echo "WARNING: Remove old secrets after successful deployment"
}

# List current secrets
list_secrets() {
    echo "Current Docker secrets:"
    docker secret ls --filter "name=burly_" --format "table {{.Name}}\t{{.CreatedAt}}\t{{.UpdatedAt}}"
}

# Remove old secrets
cleanup_secrets() {
    echo "Available secrets for cleanup:"
    docker secret ls --filter "name=burly_" --format "{{.Name}}"
    
    echo "Enter secret name to remove (or 'all' for all burly_ secrets):"
    read secret_name
    
    if [[ "$secret_name" == "all" ]]; then
        docker secret ls --filter "name=burly_" --format "{{.Name}}" | xargs -r docker secret rm
        echo "Removed all Burly MCP secrets"
    elif [[ -n "$secret_name" ]]; then
        docker secret rm "$secret_name"
        echo "Removed secret: $secret_name"
    fi
}

# Main menu
case "${1:-}" in
    "init")
        init_secrets
        ;;
    "rotate")
        rotate_secrets
        ;;
    "list")
        list_secrets
        ;;
    "cleanup")
        cleanup_secrets
        ;;
    *)
        echo "Usage: $0 {init|rotate|list|cleanup}"
        echo "  init    - Initialize secrets for new deployment"
        echo "  rotate  - Rotate existing secrets"
        echo "  list    - List current secrets"
        echo "  cleanup - Remove old secrets"
        exit 1
        ;;
esac
```

## Policy Configuration

### Security Policy Examples

#### Restrictive Production Policy
```yaml
# config/policy/production-tools.yaml
# WARNING: This is a restrictive production policy
# WARNING: Modifications can impact security posture

metadata:
  version: "1.0"
  environment: "production"
  last_updated: "2024-01-01T00:00:00Z"
  security_level: "high"

# Global security settings
global_settings:
  # Security: Require confirmation for all operations by default
  default_confirmation_required: true
  
  # Security: Strict timeout enforcement
  default_timeout: 30
  max_timeout: 300
  
  # Security: Output size limits to prevent DoS
  max_output_size: 1048576  # 1MB
  
  # Security: Rate limiting
  rate_limit:
    requests_per_minute: 30
    burst_size: 5
  
  # Security: Audit all operations
  audit_all_operations: true
  
  # Security: Fail securely on errors
  fail_secure: true

# Tool-specific configurations
tools:
  # Docker tools - High risk, restricted access
  docker_ps:
    enabled: true
    confirmation_required: false  # Safe read-only operation
    timeout: 30
    description: "List Docker containers"
    
    # Security: Restrict output format
    allowed_args:
      - "--format"
      - "--filter"
      - "--no-trunc"
    
    # Security: Block dangerous arguments
    blocked_args:
      - "--all"      # Don't show stopped containers
      - "--size"     # Don't show container sizes
    
    # Security: Output filtering
    output_filters:
      - pattern: "CONTAINER ID"
        replacement: "[REDACTED]"
    
    security_notes:
      - "Exposes running container information"
      - "May reveal system architecture details"

  docker_images:
    enabled: true
    confirmation_required: false
    timeout: 30
    description: "List Docker images"
    
    allowed_args:
      - "--format"
      - "--filter"
    
    blocked_args:
      - "--all"
      - "--digests"
    
    security_notes:
      - "Exposes installed software information"

  docker_inspect:
    enabled: false  # Disabled in production - too much information exposure
    confirmation_required: true
    timeout: 30
    description: "Inspect Docker containers (DISABLED)"
    
    security_notes:
      - "SECURITY: Disabled in production"
      - "Exposes detailed container configuration"
      - "May reveal sensitive environment variables"

  docker_exec:
    enabled: false  # Completely disabled - too dangerous
    confirmation_required: true
    timeout: 60
    description: "Execute commands in containers (DISABLED)"
    
    security_notes:
      - "CRITICAL: Completely disabled in production"
      - "Provides shell access to containers"
      - "Extreme privilege escalation risk"

  # Blog tools - Medium risk, controlled access
  blog_list_staged:
    enabled: true
    confirmation_required: false
    timeout: 15
    description: "List staged blog posts"
    
    # Security: Path restrictions
    allowed_paths:
      - "/app/data/blog/stage"
    
    blocked_paths:
      - "/app/data/blog/publish"
      - "/app/config"
      - "/var/log"
    
    # Security: File type restrictions
    allowed_extensions:
      - ".md"
      - ".txt"
    
    security_notes:
      - "Read-only access to staged content"

  blog_read_staged:
    enabled: true
    confirmation_required: false
    timeout: 15
    description: "Read staged blog post content"
    
    allowed_paths:
      - "/app/data/blog/stage"
    
    # Security: File size limits
    max_file_size: 1048576  # 1MB
    
    # Security: Content filtering
    content_filters:
      - pattern: "password\\s*[:=]\\s*\\S+"
        replacement: "[REDACTED]"
      - pattern: "token\\s*[:=]\\s*\\S+"
        replacement: "[REDACTED]"
    
    security_notes:
      - "Content is filtered for sensitive data"

  blog_stage:
    enabled: true
    confirmation_required: true  # Requires confirmation for write operations
    timeout: 30
    description: "Stage blog post for review"
    
    allowed_paths:
      - "/app/data/blog/stage"
    
    # Security: Filename validation
    filename_pattern: "^[a-zA-Z0-9._-]+\\.md$"
    
    # Security: Content validation
    content_validation:
      max_size: 1048576
      allowed_mime_types:
        - "text/markdown"
        - "text/plain"
      
      # Security: Block dangerous content
      blocked_patterns:
        - "<script"
        - "javascript:"
        - "data:text/html"
    
    security_notes:
      - "Write access to staging area only"
      - "Content is validated for security"

  blog_publish:
    enabled: true
    confirmation_required: true
    timeout: 60
    description: "Publish staged blog post"
    
    # Security: Additional approval required
    additional_approvals_required: 1
    
    # Security: Business hours only
    time_restrictions:
      allowed_hours: "09:00-17:00"
      allowed_days: ["monday", "tuesday", "wednesday", "thursday", "friday"]
      timezone: "UTC"
    
    # Security: Audit trail
    audit_level: "detailed"
    
    security_notes:
      - "CRITICAL: Publishing operation"
      - "Requires additional approval"
      - "Restricted to business hours"
      - "Full audit trail maintained"

  # System tools - Minimal access
  system_info:
    enabled: false  # Disabled - information disclosure risk
    confirmation_required: true
    timeout: 15
    description: "System information (DISABLED)"
    
    security_notes:
      - "SECURITY: Disabled in production"
      - "May expose system configuration"

# Security monitoring
monitoring:
  # Alert on policy violations
  alert_on_violations: true
  
  # Alert on blocked operations
  alert_on_blocked: true
  
  # Alert on unusual patterns
  anomaly_detection: true
  
  # Notification settings
  notifications:
    gotify:
      enabled: true
      priority: 8
      title: "Burly MCP Security Alert"
    
    webhook:
      enabled: true
      url_file: "/run/secrets/webhook_url"

# Compliance settings
compliance:
  # Audit retention
  audit_retention_days: 90
  
  # Required fields in audit logs
  required_audit_fields:
    - "timestamp"
    - "user_id"
    - "tool_name"
    - "operation"
    - "result"
    - "duration"
  
  # Data classification
  data_classification: "internal"
  
  # Regulatory requirements
  regulations:
    - "SOX"
    - "PCI-DSS"
    - "GDPR"
```

#### Development Policy (Less Restrictive)
```yaml
# config/policy/development-tools.yaml
# WARNING: This is a development policy - NOT for production use
# WARNING: Contains relaxed security settings for development convenience

metadata:
  version: "1.0"
  environment: "development"
  last_updated: "2024-01-01T00:00:00Z"
  security_level: "medium"

# WARNING: Development settings - more permissive
global_settings:
  default_confirmation_required: false  # More convenient for development
  default_timeout: 60
  max_timeout: 600
  max_output_size: 10485760  # 10MB - larger for development
  
  rate_limit:
    requests_per_minute: 120  # Higher rate limit
    burst_size: 20
  
  audit_all_operations: true  # Still audit everything
  fail_secure: false  # More permissive error handling

tools:
  # More permissive Docker access for development
  docker_ps:
    enabled: true
    confirmation_required: false
    timeout: 30
    allowed_args:
      - "--all"      # Allow showing all containers in dev
      - "--format"
      - "--filter"
      - "--no-trunc"
      - "--size"     # Allow size information in dev

  docker_images:
    enabled: true
    confirmation_required: false
    timeout: 30
    allowed_args:
      - "--all"
      - "--format"
      - "--filter"
      - "--digests"  # Allow digests in dev

  docker_inspect:
    enabled: true  # Enabled for development debugging
    confirmation_required: false
    timeout: 30
    
    # WARNING: Exposes detailed container information
    security_notes:
      - "WARNING: Development only - exposes container details"

  docker_exec:
    enabled: true  # Enabled but with confirmation
    confirmation_required: true
    timeout: 300   # Longer timeout for debugging
    
    # Security: Still restrict dangerous commands
    blocked_commands:
      - "rm -rf /"
      - "dd if=/dev/zero"
      - ":(){ :|:& };:"  # Fork bomb
    
    security_notes:
      - "WARNING: Provides shell access - development only"
      - "NEVER enable in production"

  # Blog tools - same as production but less restrictive
  blog_stage:
    enabled: true
    confirmation_required: false  # No confirmation needed in dev
    timeout: 30
    
    allowed_paths:
      - "/app/data/blog/stage"
      - "/tmp/blog"  # Allow temp directory in dev
    
    # More permissive file validation
    filename_pattern: "^[a-zA-Z0-9._-]+\\.(md|txt|html)$"
    
    content_validation:
      max_size: 10485760  # 10MB
      # Less restrictive content validation in dev

  blog_publish:
    enabled: true
    confirmation_required: true  # Still require confirmation
    timeout: 60
    
    # No time restrictions in development
    # time_restrictions: {}  # Commented out
    
    security_notes:
      - "Development environment - no time restrictions"

  # System tools enabled for development
  system_info:
    enabled: true
    confirmation_required: false
    timeout: 15
    
    security_notes:
      - "WARNING: Development only - exposes system info"

# Development monitoring - less strict
monitoring:
  alert_on_violations: false  # Don't alert on every violation in dev
  alert_on_blocked: false
  anomaly_detection: false    # Disable in dev to reduce noise

# Development compliance - relaxed
compliance:
  audit_retention_days: 7     # Shorter retention in dev
  data_classification: "development"
```

## Network Security Configuration

### Firewall Rules
```bash
#!/bin/bash
# firewall-rules.sh - Configure host firewall for Burly MCP

set -euo pipefail

# WARNING: These rules provide network-level security
# WARNING: Modify carefully to avoid locking yourself out

configure_iptables() {
    echo "Configuring iptables for Burly MCP..."
    
    # Flush existing rules
    iptables -F
    iptables -X
    iptables -t nat -F
    iptables -t nat -X
    
    # Default policies - deny all
    iptables -P INPUT DROP
    iptables -P FORWARD DROP
    iptables -P OUTPUT DROP
    
    # Allow loopback traffic
    iptables -A INPUT -i lo -j ACCEPT
    iptables -A OUTPUT -o lo -j ACCEPT
    
    # Allow established connections
    iptables -A INPUT -m state --state ESTABLISHED,RELATED -j ACCEPT
    iptables -A OUTPUT -m state --state ESTABLISHED,RELATED -j ACCEPT
    
    # Allow SSH (modify port as needed)
    iptables -A INPUT -p tcp --dport 22 -m state --state NEW -j ACCEPT
    iptables -A OUTPUT -p tcp --sport 22 -m state --state ESTABLISHED -j ACCEPT
    
    # Allow DNS resolution
    iptables -A OUTPUT -p udp --dport 53 -j ACCEPT
    iptables -A OUTPUT -p tcp --dport 53 -j ACCEPT
    
    # Allow HTTPS outbound (for notifications, updates)
    iptables -A OUTPUT -p tcp --dport 443 -j ACCEPT
    
    # Allow HTTP outbound (for package updates - consider restricting)
    iptables -A OUTPUT -p tcp --dport 80 -j ACCEPT
    
    # Docker-specific rules
    # Allow Docker daemon communication
    iptables -A OUTPUT -p tcp --dport 2375 -d 127.0.0.1 -j ACCEPT
    iptables -A OUTPUT -p tcp --dport 2376 -d 127.0.0.1 -j ACCEPT
    
    # Block Docker daemon from external access
    iptables -A INPUT -p tcp --dport 2375 ! -s 127.0.0.1 -j DROP
    iptables -A INPUT -p tcp --dport 2376 ! -s 127.0.0.1 -j DROP
    
    # Log dropped packets (for monitoring)
    iptables -A INPUT -j LOG --log-prefix "DROPPED INPUT: "
    iptables -A OUTPUT -j LOG --log-prefix "DROPPED OUTPUT: "
    
    echo "Firewall rules configured successfully"
    echo "WARNING: Verify connectivity before disconnecting"
}

# Save rules (Ubuntu/Debian)
save_iptables_debian() {
    iptables-save > /etc/iptables/rules.v4
    echo "Firewall rules saved to /etc/iptables/rules.v4"
}

# Save rules (CentOS/RHEL)
save_iptables_rhel() {
    service iptables save
    echo "Firewall rules saved"
}

# Configure UFW (Ubuntu alternative)
configure_ufw() {
    echo "Configuring UFW for Burly MCP..."
    
    # Reset UFW
    ufw --force reset
    
    # Default policies
    ufw default deny incoming
    ufw default deny outgoing
    ufw default deny forward
    
    # Allow SSH
    ufw allow ssh
    
    # Allow DNS
    ufw allow out 53
    
    # Allow HTTPS outbound
    ufw allow out 443/tcp
    
    # Allow HTTP outbound (consider restricting)
    ufw allow out 80/tcp
    
    # Block Docker daemon external access
    ufw deny 2375/tcp
    ufw deny 2376/tcp
    
    # Enable UFW
    ufw --force enable
    
    echo "UFW configured successfully"
}

# Main execution
case "${1:-iptables}" in
    "iptables")
        configure_iptables
        if command -v iptables-save >/dev/null; then
            save_iptables_debian
        else
            save_iptables_rhel
        fi
        ;;
    "ufw")
        configure_ufw
        ;;
    *)
        echo "Usage: $0 {iptables|ufw}"
        echo "  iptables - Configure using iptables directly"
        echo "  ufw      - Configure using UFW (Ubuntu)"
        exit 1
        ;;
esac
```

### Network Monitoring
```bash
#!/bin/bash
# network-monitor.sh - Monitor network connections for Burly MCP

set -euo pipefail

# Monitor Docker daemon connections
monitor_docker_connections() {
    echo "=== Docker Daemon Connections ==="
    
    # Check for external connections to Docker daemon
    netstat -tlnp | grep -E ":237[56]" | while read line; do
        if echo "$line" | grep -v "127.0.0.1" >/dev/null; then
            echo "WARNING: External Docker daemon connection detected: $line"
        else
            echo "OK: Local Docker daemon connection: $line"
        fi
    done
}

# Monitor Burly MCP container connections
monitor_container_connections() {
    echo "=== Container Network Connections ==="
    
    # Get Burly MCP container ID
    container_id=$(docker ps --filter "name=burly-mcp" --format "{{.ID}}" | head -1)
    
    if [[ -n "$container_id" ]]; then
        echo "Monitoring container: $container_id"
        
        # Check container network namespace
        docker exec "$container_id" netstat -tlnp 2>/dev/null || echo "No listening ports (good)"
        
        # Check outbound connections
        docker exec "$container_id" netstat -tnp 2>/dev/null | grep ESTABLISHED || echo "No established connections"
    else
        echo "Burly MCP container not found"
    fi
}

# Check for suspicious network activity
check_suspicious_activity() {
    echo "=== Suspicious Network Activity Check ==="
    
    # Check for unusual outbound connections
    netstat -tnp | grep ESTABLISHED | while read line; do
        # Extract destination IP and port
        dest=$(echo "$line" | awk '{print $3}' | cut -d: -f1)
        port=$(echo "$line" | awk '{print $3}' | cut -d: -f2)
        
        # Check for connections to unusual ports
        case "$port" in
            22|53|80|443|2375|2376)
                # Normal ports
                ;;
            *)
                echo "WARNING: Connection to unusual port: $line"
                ;;
        esac
        
        # Check for connections to private IP ranges that shouldn't be accessed
        case "$dest" in
            10.*|172.16.*|172.17.*|172.18.*|172.19.*|172.2*|172.30.*|172.31.*|192.168.*)
                # Private IPs - check if expected
                if [[ "$port" != "2375" && "$port" != "2376" ]]; then
                    echo "INFO: Connection to private IP: $line"
                fi
                ;;
        esac
    done
}

# Generate network security report
generate_report() {
    echo "=== Network Security Report - $(date) ==="
    
    monitor_docker_connections
    echo
    monitor_container_connections
    echo
    check_suspicious_activity
    echo
    
    echo "=== Firewall Status ==="
    if command -v ufw >/dev/null && ufw status | grep -q "Status: active"; then
        ufw status numbered
    elif command -v iptables >/dev/null; then
        iptables -L -n --line-numbers
    else
        echo "No firewall detected"
    fi
    
    echo "=== Report Complete ==="
}

# Continuous monitoring mode
continuous_monitor() {
    echo "Starting continuous network monitoring (Ctrl+C to stop)..."
    
    while true; do
        clear
        generate_report
        sleep 30
    done
}

# Main execution
case "${1:-report}" in
    "report")
        generate_report
        ;;
    "monitor")
        continuous_monitor
        ;;
    "docker")
        monitor_docker_connections
        ;;
    "container")
        monitor_container_connections
        ;;
    *)
        echo "Usage: $0 {report|monitor|docker|container}"
        echo "  report    - Generate one-time security report"
        echo "  monitor   - Continuous monitoring mode"
        echo "  docker    - Monitor Docker daemon connections only"
        echo "  container - Monitor container connections only"
        exit 1
        ;;
esac
```

## Security Validation and Testing

### Automated Security Tests
```bash
#!/bin/bash
# security-tests.sh - Comprehensive security testing suite

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TEST_RESULTS_DIR="${SCRIPT_DIR}/test-results"

# Create test results directory
mkdir -p "$TEST_RESULTS_DIR"

# Test 1: Configuration Security
test_configuration_security() {
    echo "=== Testing Configuration Security ==="
    
    local test_file="${TEST_RESULTS_DIR}/config-security.log"
    
    {
        echo "Testing environment variable security..."
        
        # Check for hardcoded secrets
        if grep -r "password\|secret\|token" config/ --include="*.yaml" --include="*.yml" 2>/dev/null; then
            echo "FAIL: Hardcoded secrets found in configuration"
        else
            echo "PASS: No hardcoded secrets in configuration"
        fi
        
        # Check file permissions
        find config/ -type f -exec stat -c "%a %n" {} \; | while read perms file; do
            if [[ "$perms" -gt 644 ]]; then
                echo "WARNING: Overly permissive file permissions: $file ($perms)"
            else
                echo "PASS: Secure file permissions: $file ($perms)"
            fi
        done
        
    } | tee "$test_file"
}

# Test 2: Container Security
test_container_security() {
    echo "=== Testing Container Security ==="
    
    local test_file="${TEST_RESULTS_DIR}/container-security.log"
    
    {
        echo "Testing container security configuration..."
        
        # Check if container runs as root
        if docker-compose config | grep -q "user.*root\|user.*0:0"; then
            echo "FAIL: Container configured to run as root"
        else
            echo "PASS: Container not running as root"
        fi
        
        # Check for privileged mode
        if docker-compose config | grep -q "privileged.*true"; then
            echo "FAIL: Container running in privileged mode"
        else
            echo "PASS: Container not in privileged mode"
        fi
        
        # Check capability dropping
        if docker-compose config | grep -q "cap_drop"; then
            echo "PASS: Capabilities are being dropped"
        else
            echo "WARNING: No capability dropping configured"
        fi
        
        # Check read-only filesystem
        if docker-compose config | grep -q "read_only.*true"; then
            echo "PASS: Read-only filesystem configured"
        else
            echo "WARNING: Read-only filesystem not configured"
        fi
        
    } | tee "$test_file"
}

# Test 3: Network Security
test_network_security() {
    echo "=== Testing Network Security ==="
    
    local test_file="${TEST_RESULTS_DIR}/network-security.log"
    
    {
        echo "Testing network security configuration..."
        
        # Check for exposed ports
        if docker-compose config | grep -q "ports:"; then
            echo "WARNING: Ports are exposed"
            docker-compose config | grep -A5 "ports:"
        else
            echo "PASS: No ports exposed"
        fi
        
        # Check network configuration
        if docker-compose config | grep -q "network_mode.*host"; then
            echo "FAIL: Host networking enabled"
        else
            echo "PASS: Host networking not enabled"
        fi
        
        # Check for custom networks
        if docker-compose config | grep -q "networks:"; then
            echo "PASS: Custom networks configured"
        else
            echo "WARNING: No custom networks configured"
        fi
        
    } | tee "$test_file"
}

# Test 4: Secret Management
test_secret_management() {
    echo "=== Testing Secret Management ==="
    
    local test_file="${TEST_RESULTS_DIR}/secret-management.log"
    
    {
        echo "Testing secret management configuration..."
        
        # Check for Docker secrets usage
        if docker-compose config | grep -q "secrets:"; then
            echo "PASS: Docker secrets configured"
        else
            echo "WARNING: No Docker secrets configured"
        fi
        
        # Check for environment variables with secrets
        if docker-compose config | grep -E "TOKEN=|PASSWORD=|SECRET=" | grep -v "_FILE="; then
            echo "FAIL: Secrets in environment variables"
        else
            echo "PASS: No secrets in environment variables"
        fi
        
        # Check for secret files
        if docker-compose config | grep -q "_FILE=/run/secrets/"; then
            echo "PASS: Secret files properly configured"
        else
            echo "WARNING: No secret files configured"
        fi
        
    } | tee "$test_file"
}

# Test 5: Input Validation
test_input_validation() {
    echo "=== Testing Input Validation ==="
    
    local test_file="${TEST_RESULTS_DIR}/input-validation.log"
    
    {
        echo "Testing input validation implementation..."
        
        # Test path traversal protection
        python3 -c "
import sys
sys.path.append('src')
from burly_mcp.security import InputValidator

test_cases = [
    '../etc/passwd',
    '../../root/.ssh/id_rsa',
    '/etc/shadow',
    'blog/../../../etc/passwd',
    'file.txt\x00.exe',
    '; rm -rf /',
    '\$(whoami)',
    '`id`'
]

for test_case in test_cases:
    if InputValidator.validate_filename(test_case):
        print(f'FAIL: Dangerous input accepted: {repr(test_case)}')
    else:
        print(f'PASS: Dangerous input rejected: {repr(test_case)}')
" 2>/dev/null || echo "WARNING: Could not test input validation"
        
    } | tee "$test_file"
}

# Test 6: Audit Logging
test_audit_logging() {
    echo "=== Testing Audit Logging ==="
    
    local test_file="${TEST_RESULTS_DIR}/audit-logging.log"
    
    {
        echo "Testing audit logging configuration..."
        
        # Check if audit logging is enabled
        if grep -q "AUDIT_ENABLED=true" .env.example 2>/dev/null; then
            echo "PASS: Audit logging enabled in configuration"
        else
            echo "WARNING: Audit logging not found in configuration"
        fi
        
        # Check audit log directory permissions
        if [[ -d "logs" ]]; then
            perms=$(stat -c "%a" logs)
            if [[ "$perms" -le 755 ]]; then
                echo "PASS: Audit log directory has secure permissions ($perms)"
            else
                echo "WARNING: Audit log directory has overly permissive permissions ($perms)"
            fi
        else
            echo "INFO: Audit log directory not found (may be created at runtime)"
        fi
        
    } | tee "$test_file"
}

# Test 7: Dependency Security
test_dependency_security() {
    echo "=== Testing Dependency Security ==="
    
    local test_file="${TEST_RESULTS_DIR}/dependency-security.log"
    
    {
        echo "Testing dependency security..."
        
        # Check for known vulnerabilities
        if command -v pip-audit >/dev/null; then
            echo "Running pip-audit..."
            pip-audit --desc --format=json > "${TEST_RESULTS_DIR}/pip-audit.json" 2>&1 || true
            
            if [[ -s "${TEST_RESULTS_DIR}/pip-audit.json" ]]; then
                vuln_count=$(jq '.vulnerabilities | length' "${TEST_RESULTS_DIR}/pip-audit.json" 2>/dev/null || echo "unknown")
                if [[ "$vuln_count" == "0" ]]; then
                    echo "PASS: No known vulnerabilities found"
                else
                    echo "WARNING: $vuln_count vulnerabilities found"
                fi
            fi
        else
            echo "WARNING: pip-audit not available"
        fi
        
        # Check for outdated packages
        if command -v pip >/dev/null; then
            echo "Checking for outdated packages..."
            pip list --outdated --format=json > "${TEST_RESULTS_DIR}/outdated-packages.json" 2>/dev/null || true
        fi
        
    } | tee "$test_file"
}

# Generate comprehensive security report
generate_security_report() {
    local report_file="${TEST_RESULTS_DIR}/security-report-$(date +%Y%m%d_%H%M%S).html"
    
    cat > "$report_file" << 'EOF'
<!DOCTYPE html>
<html>
<head>
    <title>Burly MCP Security Report</title>
    <style>
        body { font-family: Arial, sans-serif; margin: 20px; }
        .pass { color: green; }
        .fail { color: red; }
        .warning { color: orange; }
        .info { color: blue; }
        pre { background: #f5f5f5; padding: 10px; border-radius: 5px; }
        .section { margin: 20px 0; border: 1px solid #ddd; padding: 15px; border-radius: 5px; }
    </style>
</head>
<body>
    <h1>Burly MCP Security Report</h1>
    <p>Generated: $(date)</p>
    
EOF
    
    # Add each test result to the report
    for test_log in "${TEST_RESULTS_DIR}"/*.log; do
        if [[ -f "$test_log" ]]; then
            test_name=$(basename "$test_log" .log)
            echo "<div class='section'>" >> "$report_file"
            echo "<h2>$test_name</h2>" >> "$report_file"
            echo "<pre>" >> "$report_file"
            
            # Color-code the output
            sed -e 's/PASS:/\<span class="pass"\>PASS:\<\/span\>/g' \
                -e 's/FAIL:/\<span class="fail"\>FAIL:\<\/span\>/g' \
                -e 's/WARNING:/\<span class="warning"\>WARNING:\<\/span\>/g' \
                -e 's/INFO:/\<span class="info"\>INFO:\<\/span\>/g' \
                "$test_log" >> "$report_file"
            
            echo "</pre>" >> "$report_file"
            echo "</div>" >> "$report_file"
        fi
    done
    
    echo "</body></html>" >> "$report_file"
    
    echo "Security report generated: $report_file"
}

# Run all tests
run_all_tests() {
    echo "Running comprehensive security test suite..."
    
    test_configuration_security
    test_container_security
    test_network_security
    test_secret_management
    test_input_validation
    test_audit_logging
    test_dependency_security
    
    generate_security_report
    
    echo "All security tests completed. Results in: $TEST_RESULTS_DIR"
}

# Main execution
case "${1:-all}" in
    "all")
        run_all_tests
        ;;
    "config")
        test_configuration_security
        ;;
    "container")
        test_container_security
        ;;
    "network")
        test_network_security
        ;;
    "secrets")
        test_secret_management
        ;;
    "input")
        test_input_validation
        ;;
    "audit")
        test_audit_logging
        ;;
    "deps")
        test_dependency_security
        ;;
    "report")
        generate_security_report
        ;;
    *)
        echo "Usage: $0 {all|config|container|network|secrets|input|audit|deps|report}"
        echo "  all       - Run all security tests"
        echo "  config    - Test configuration security"
        echo "  container - Test container security"
        echo "  network   - Test network security"
        echo "  secrets   - Test secret management"
        echo "  input     - Test input validation"
        echo "  audit     - Test audit logging"
        echo "  deps      - Test dependency security"
        echo "  report    - Generate HTML report from existing results"
        exit 1
        ;;
esac
```

---

**Document Version**: 1.0  
**Last Updated**: 2024-01-01  
**Next Review**: 2024-04-01  
**Owner**: Security Team  
**Classification**: Internal Use

## Security Warnings Summary

### Critical Warnings
- **Never commit secrets to version control**
- **Always use file-based secrets in production**
- **Never run containers as root in production**
- **Never enable development mode in production**

### Important Warnings
- **Validate all file permissions before deployment**
- **Monitor Docker socket access carefully**
- **Regularly update and scan dependencies**
- **Implement proper network isolation**

### Configuration Warnings
- **Review all environment variables for security impact**
- **Test security configurations before deployment**
- **Maintain separate policies for different environments**
- **Regular security audits and penetration testing**