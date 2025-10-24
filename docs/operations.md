# Operations Guide

## Overview

This operations guide provides a comprehensive overview of running Burly MCP in production environments. It serves as a central reference for deployment, monitoring, maintenance, and troubleshooting procedures.

## Quick Reference

### Essential Commands

```bash
# Status and health checks
docker-compose ps                              # Container status
docker-compose logs --tail=50 burly-mcp      # Recent logs
docker exec burly-mcp python -c "from burly_mcp.health import HealthChecker; from burly_mcp.config import Config; print(HealthChecker(Config()).check_health())"

# Configuration validation
docker-compose config                          # Validate compose file
docker-compose run --rm burly-mcp python -c "from burly_mcp.config import Config; print(Config().validate())"

# Resource monitoring
docker stats burly-mcp --no-stream           # Resource usage
df -h /var/log/agentops                       # Log disk usage
tail -f /var/log/agentops/audit.jsonl | jq   # Live audit log

# Maintenance operations
docker-compose restart burly-mcp              # Restart service
docker-compose pull && docker-compose up -d  # Update to latest
docker system prune -f                        # Clean up Docker
```

### Emergency Procedures

**Service Down:**
```bash
# 1. Check container status
docker-compose ps

# 2. Check logs for errors
docker-compose logs --tail=100 burly-mcp

# 3. Restart service
docker-compose restart burly-mcp

# 4. If restart fails, recreate container
docker-compose down && docker-compose up -d
```

**High Resource Usage:**
```bash
# 1. Check resource consumption
docker stats burly-mcp --no-stream

# 2. Check for resource leaks
docker-compose logs burly-mcp | grep -i "memory\|cpu\|timeout"

# 3. Restart if necessary
docker-compose restart burly-mcp

# 4. Adjust resource limits if needed
# Edit docker-compose.yml deploy.resources section
```

**Disk Space Issues:**
```bash
# 1. Check disk usage
df -h
du -sh /var/log/agentops/*

# 2. Rotate logs manually
logrotate -f /etc/logrotate.d/burly-mcp

# 3. Clean up Docker
docker system prune -f
docker volume prune -f

# 4. Archive old audit logs
tar -czf audit-logs-$(date +%Y%m%d).tar.gz /var/log/agentops/audit.jsonl.*
```

## Environment Management

### Development Environment

**Setup:**
```bash
# Clone and configure
git clone <repository>
cd burly-mcp
cp .env.example .env.development

# Configure for development
cat >> .env.development << EOF
LOG_LEVEL=DEBUG
DEVELOPMENT_MODE=true
NOTIFICATIONS_ENABLED=false
BLOG_STAGE_ROOT=./test_data/blog/stage
BLOG_PUBLISH_ROOT=./test_data/blog/publish
EOF

# Create test directories
mkdir -p ./test_data/blog/{stage,publish} ./logs

# Start development environment
docker-compose --env-file .env.development up -d
```

**Development Workflow:**
```bash
# Make changes to code
# Rebuild and restart
docker-compose build burly-mcp
docker-compose restart burly-mcp

# Test changes
docker-compose exec burly-mcp python -m pytest tests/

# Check logs
docker-compose logs -f burly-mcp
```

### Staging Environment

**Deployment:**
```bash
# Deploy to staging
git checkout staging
docker-compose --env-file .env.staging pull
docker-compose --env-file .env.staging up -d

# Verify deployment
docker-compose ps
curl -f http://staging-burly-mcp/health || echo "Health check failed"

# Run integration tests
docker-compose exec burly-mcp python -m pytest tests/integration/
```

**Staging Validation:**
```bash
# Test MCP protocol
echo '{"jsonrpc": "2.0", "id": 1, "method": "tools/list"}' | \
  docker-compose exec -T burly-mcp python -m burly_mcp.server.main

# Test tool execution
echo '{"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": {"name": "docker_ps", "arguments": {}}}' | \
  docker-compose exec -T burly-mcp python -m burly_mcp.server.main

# Verify notifications
docker-compose exec burly-mcp python -c "
from burly_mcp.notifications.manager import NotificationManager
from burly_mcp.config import Config
manager = NotificationManager(Config())
manager.send_notification('Test notification', 'Staging deployment verification')
"
```

### Production Environment

**Pre-deployment Checklist:**
- [ ] Staging tests passed
- [ ] Security scan completed
- [ ] Backup procedures verified
- [ ] Monitoring configured
- [ ] Rollback plan prepared
- [ ] Change window scheduled
- [ ] Team notifications sent

**Production Deployment:**
```bash
# 1. Backup current state
./scripts/backup.sh

# 2. Deploy new version
git checkout production
docker-compose --env-file .env.production pull
docker-compose --env-file .env.production up -d

# 3. Verify deployment
./scripts/health-check.sh
./scripts/smoke-test.sh

# 4. Monitor for issues
tail -f /var/log/agentops/audit.jsonl | jq
```

**Post-deployment Verification:**
```bash
# Health checks
curl -f http://burly-mcp/health
docker-compose ps | grep -v "Up"

# Functional tests
./scripts/functional-tests.sh

# Performance baseline
./scripts/performance-test.sh

# Monitor metrics
# Check Grafana dashboards
# Verify alerting is working
```

## Monitoring and Alerting

### Key Metrics to Monitor

**Application Metrics:**
- Tool execution rate and success rate
- Response time percentiles (50th, 95th, 99th)
- Active connections
- Error rates by tool type
- Audit log growth rate

**System Metrics:**
- CPU and memory usage
- Disk space and I/O
- Network connectivity
- Container health status
- Docker daemon health

**Security Metrics:**
- Failed authentication attempts
- Privilege escalation attempts
- Unusual tool usage patterns
- Configuration changes
- Security policy violations

### Alert Thresholds

**Critical Alerts (Immediate Response):**
- Service down > 1 minute
- Error rate > 50% for 2 minutes
- Disk space > 95%
- Memory usage > 90%
- Security policy violations

**Warning Alerts (Response within 1 hour):**
- Error rate > 10% for 5 minutes
- Response time > 30 seconds (95th percentile)
- Disk space > 85%
- Memory usage > 80%
- Unusual usage patterns

**Info Alerts (Daily Review):**
- High audit log growth
- Configuration changes
- New tool usage patterns
- Performance degradation trends

### Monitoring Setup

**Prometheus Configuration:**
```yaml
# Add to prometheus.yml
scrape_configs:
  - job_name: 'burly-mcp'
    static_configs:
      - targets: ['burly-mcp:8080']
    scrape_interval: 30s
    metrics_path: /metrics
```

**Grafana Dashboard Import:**
```bash
# Import Burly MCP dashboard
curl -X POST \
  http://grafana:3000/api/dashboards/db \
  -H 'Content-Type: application/json' \
  -d @monitoring/grafana/burly-mcp-dashboard.json
```

**Alertmanager Integration:**
```yaml
# Add to alertmanager.yml
receivers:
  - name: 'burly-mcp-alerts'
    slack_configs:
      - api_url: 'YOUR_SLACK_WEBHOOK'
        channel: '#ops-alerts'
        title: 'Burly MCP Alert'
        text: '{{ range .Alerts }}{{ .Annotations.summary }}{{ end }}'
```

## Maintenance Procedures

### Regular Maintenance Tasks

**Daily:**
- Check service health and logs
- Monitor resource usage
- Review security alerts
- Verify backup completion

**Weekly:**
- Update dependencies (security patches)
- Review audit logs for anomalies
- Test backup restoration
- Performance trend analysis

**Monthly:**
- Full security scan
- Capacity planning review
- Documentation updates
- Disaster recovery test

**Quarterly:**
- Security audit
- Performance optimization
- Architecture review
- Team training updates

### Maintenance Scripts

**Daily Health Check:**
```bash
#!/bin/bash
# daily-health-check.sh

echo "=== Daily Health Check - $(date) ==="

# Service status
echo "Service Status:"
docker-compose ps

# Resource usage
echo -e "\nResource Usage:"
docker stats burly-mcp --no-stream

# Disk space
echo -e "\nDisk Space:"
df -h /var/log/agentops

# Recent errors
echo -e "\nRecent Errors:"
docker-compose logs --since 24h burly-mcp | grep -i error | tail -5

# Audit log summary
echo -e "\nAudit Summary (last 24h):"
jq -r 'select(.timestamp > "'$(date -d '24 hours ago' -Iseconds)'") | .result' \
  /var/log/agentops/audit.jsonl | sort | uniq -c

echo "=== Health Check Complete ==="
```

**Weekly Maintenance:**
```bash
#!/bin/bash
# weekly-maintenance.sh

echo "=== Weekly Maintenance - $(date) ==="

# Update images
echo "Updating Docker images..."
docker-compose pull

# Clean up Docker
echo "Cleaning up Docker..."
docker system prune -f

# Rotate logs
echo "Rotating logs..."
logrotate -f /etc/logrotate.d/burly-mcp

# Security scan
echo "Running security scan..."
trivy image burly-mcp:latest

# Backup
echo "Creating backup..."
./scripts/backup.sh

echo "=== Weekly Maintenance Complete ==="
```

### Update Procedures

**Security Updates:**
```bash
# 1. Check for security updates
docker scout cves burly-mcp:latest

# 2. Update base images
docker-compose build --no-cache burly-mcp

# 3. Test in staging
docker-compose --env-file .env.staging up -d
./scripts/security-test.sh

# 4. Deploy to production (if tests pass)
docker-compose --env-file .env.production up -d
```

**Application Updates:**
```bash
# 1. Review changelog
git log --oneline HEAD..origin/main

# 2. Test in development
git checkout main
docker-compose build burly-mcp
docker-compose up -d
./scripts/functional-tests.sh

# 3. Deploy to staging
git checkout staging
git merge main
docker-compose --env-file .env.staging up -d
./scripts/integration-tests.sh

# 4. Deploy to production
git checkout production
git merge staging
docker-compose --env-file .env.production up -d
./scripts/smoke-tests.sh
```

## Security Operations

### Security Monitoring

**Real-time Monitoring:**
```bash
# Monitor audit logs for security events
tail -f /var/log/agentops/audit.jsonl | \
  jq 'select(.security_context.requires_confirmation == true or .result == "failure")'

# Monitor container security
docker exec burly-mcp ps aux | grep -v "^agentops"  # Should be empty
docker exec burly-mcp id  # Should show uid=1000(agentops)
```

**Security Alerts:**
```bash
# Failed tool executions
jq 'select(.result == "failure")' /var/log/agentops/audit.jsonl | tail -10

# Privilege escalation attempts
docker logs burly-mcp 2>&1 | grep -i "privilege\|sudo\|root"

# Unusual file access
jq 'select(.tool_name | contains("blog")) | .arguments' /var/log/agentops/audit.jsonl | \
  grep -E "\.\.|/etc|/root|/home"
```

### Incident Response

**Security Incident Procedure:**

1. **Immediate Response:**
   ```bash
   # Stop the service
   docker-compose stop burly-mcp
   
   # Preserve evidence
   docker-compose logs burly-mcp > incident-logs-$(date +%Y%m%d_%H%M%S).log
   cp /var/log/agentops/audit.jsonl incident-audit-$(date +%Y%m%d_%H%M%S).jsonl
   ```

2. **Investigation:**
   ```bash
   # Analyze logs
   grep -i "suspicious\|error\|failure" incident-logs-*.log
   
   # Check for unauthorized access
   jq 'select(.result == "failure" or .security_context.requires_confirmation == true)' \
     incident-audit-*.jsonl
   
   # Verify container integrity
   docker diff $(docker-compose ps -q burly-mcp)
   ```

3. **Recovery:**
   ```bash
   # Rebuild from clean state
   docker-compose down
   docker rmi burly-mcp:latest
   docker-compose build --no-cache burly-mcp
   
   # Restore from backup if needed
   ./scripts/restore.sh /backups/latest
   
   # Restart with enhanced monitoring
   LOG_LEVEL=DEBUG docker-compose up -d
   ```

### Compliance and Auditing

**Audit Log Analysis:**
```bash
# Generate compliance report
./scripts/compliance-report.sh > compliance-$(date +%Y%m%d).txt

# Tool usage by user
jq -r '"\(.timestamp) \(.user_id) \(.tool_name)"' /var/log/agentops/audit.jsonl | \
  sort | uniq -c | sort -nr

# Privileged operations
jq 'select(.security_context.mutates_system == true)' /var/log/agentops/audit.jsonl

# Failed operations analysis
jq 'select(.result == "failure") | {timestamp, tool_name, error, user_id}' \
  /var/log/agentops/audit.jsonl
```

## Performance Optimization

### Performance Monitoring

**Key Performance Indicators:**
- Tool execution time (target: <5s for 95th percentile)
- Memory usage (target: <512MB steady state)
- CPU usage (target: <50% average)
- Disk I/O (target: <100MB/s sustained)

**Performance Testing:**
```bash
# Load testing
./scripts/load-test.sh 100 60  # 100 concurrent requests for 60 seconds

# Memory profiling
docker exec burly-mcp python -m memory_profiler burly_mcp/server/main.py

# CPU profiling
docker exec burly-mcp python -m cProfile -o profile.stats burly_mcp/server/main.py
```

### Optimization Strategies

**Container Optimization:**
```yaml
# docker-compose.yml optimizations
services:
  burly-mcp:
    deploy:
      resources:
        limits:
          memory: 512M
          cpus: '0.5'
        reservations:
          memory: 128M
          cpus: '0.1'
    environment:
      - PYTHONUNBUFFERED=1
      - PYTHONDONTWRITEBYTECODE=1
    ulimits:
      nofile:
        soft: 65536
        hard: 65536
```

**Application Optimization:**
```bash
# Optimize Python performance
PYTHONOPTIMIZE=2 docker-compose up -d

# Enable connection pooling
MAX_CONCURRENT_TOOLS=10

# Optimize logging
LOG_LEVEL=WARNING  # Reduce log verbosity in production
```

## Disaster Recovery

### Backup Strategy

**Automated Backups:**
```bash
# Add to crontab
0 2 * * * /opt/burly-mcp/scripts/backup.sh
0 6 * * 0 /opt/burly-mcp/scripts/weekly-backup.sh
```

**Backup Verification:**
```bash
# Test backup integrity
./scripts/verify-backup.sh /backups/latest

# Test restoration procedure
./scripts/test-restore.sh /backups/latest
```

### Recovery Procedures

**Service Recovery:**
```bash
# 1. Stop failed service
docker-compose down

# 2. Restore from backup
./scripts/restore.sh /backups/latest

# 3. Verify configuration
docker-compose config

# 4. Start service
docker-compose up -d

# 5. Verify functionality
./scripts/smoke-test.sh
```

**Data Recovery:**
```bash
# Restore specific components
./scripts/restore-config.sh /backups/latest
./scripts/restore-logs.sh /backups/latest
./scripts/restore-blog-data.sh /backups/latest
```

This operations guide provides comprehensive procedures for managing Burly MCP in production environments, covering all aspects from deployment to incident response.