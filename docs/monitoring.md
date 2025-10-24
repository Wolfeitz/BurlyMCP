# Monitoring and Logging Configuration

## Overview

This guide provides comprehensive monitoring and logging configurations for Burly MCP, including metrics collection, alerting, log aggregation, and observability best practices for production deployments.

## Logging Configuration

### Application Logging

**Log Levels and Configuration:**
```bash
# .env configuration for logging
LOG_LEVEL=INFO                    # DEBUG, INFO, WARNING, ERROR, CRITICAL
BURLY_LOG_DIR=/var/log/agentops  # Log directory
AUDIT_ENABLED=true               # Enable audit logging
AUDIT_LOG_PATH=/var/log/agentops/audit.jsonl
```

**Structured Logging Format:**
```python
# Example log entry structure
{
  "timestamp": "2024-01-15T10:30:45.123Z",
  "level": "INFO",
  "logger": "burly_mcp.server.main",
  "message": "Tool execution completed",
  "tool_name": "docker_ps",
  "execution_time": 0.245,
  "user_id": "user123",
  "request_id": "req-abc123",
  "success": true
}
```

**Audit Logging Format:**
```json
{
  "timestamp": "2024-01-15T10:30:45.123Z",
  "event_type": "tool_execution",
  "tool_name": "blog_publish_static",
  "user_id": "user123",
  "request_id": "req-abc123",
  "arguments": {
    "source_dir": "2024-01-15-post",
    "_confirm": true
  },
  "result": "success",
  "execution_time": 2.456,
  "output_size": 1024,
  "security_context": {
    "requires_confirmation": true,
    "mutates_system": true
  }
}
```

### Docker Logging Configuration

**Docker Compose Logging:**
```yaml
# docker-compose.yml
services:
  burly-mcp:
    logging:
      driver: "json-file"
      options:
        max-size: "10m"
        max-file: "5"
        labels: "service,environment,version"
    labels:
      - "service=burly-mcp"
      - "environment=production"
      - "version=1.0.0"
```

**Centralized Logging with Fluentd:**
```yaml
# docker-compose.logging.yml
version: '3.8'

services:
  burly-mcp:
    logging:
      driver: fluentd
      options:
        fluentd-address: localhost:24224
        tag: burly-mcp.{{.Name}}

  fluentd:
    image: fluent/fluentd:v1.16-debian-1
    ports:
      - "24224:24224"
      - "24224:24224/udp"
    volumes:
      - ./fluentd/conf:/fluentd/etc
      - ./logs:/var/log/fluentd
    environment:
      - FLUENTD_CONF=fluent.conf

  elasticsearch:
    image: docker.elastic.co/elasticsearch/elasticsearch:8.11.0
    environment:
      - discovery.type=single-node
      - "ES_JAVA_OPTS=-Xms512m -Xmx512m"
      - xpack.security.enabled=false
    ports:
      - "9200:9200"
    volumes:
      - elasticsearch-data:/usr/share/elasticsearch/data

  kibana:
    image: docker.elastic.co/kibana/kibana:8.11.0
    ports:
      - "5601:5601"
    environment:
      - ELASTICSEARCH_HOSTS=http://elasticsearch:9200
    depends_on:
      - elasticsearch

volumes:
  elasticsearch-data:
```

**Fluentd Configuration:**
```ruby
# fluentd/conf/fluent.conf
<source>
  @type forward
  port 24224
  bind 0.0.0.0
</source>

<filter burly-mcp.**>
  @type parser
  key_name log
  reserve_data true
  <parse>
    @type json
    time_key timestamp
    time_format %Y-%m-%dT%H:%M:%S.%LZ
  </parse>
</filter>

<filter burly-mcp.**>
  @type record_transformer
  <record>
    service ${tag_parts[0]}
    container_name ${tag_parts[1]}
    environment "#{ENV['ENVIRONMENT'] || 'production'}"
  </record>
</filter>

<match burly-mcp.**>
  @type elasticsearch
  host elasticsearch
  port 9200
  index_name burly-mcp-logs
  type_name _doc
  <buffer>
    @type file
    path /var/log/fluentd/burly-mcp
    flush_mode interval
    flush_interval 10s
    chunk_limit_size 10m
    queue_limit_length 32
    retry_max_interval 30
    retry_forever true
  </buffer>
</match>
```

### Log Rotation and Retention

**Logrotate Configuration:**
```bash
# /etc/logrotate.d/burly-mcp
/var/log/agentops/*.log /var/log/agentops/*.jsonl {
    daily
    rotate 30
    compress
    delaycompress
    missingok
    notifempty
    copytruncate
    postrotate
        docker-compose exec burly-mcp kill -USR1 1 2>/dev/null || true
    endscript
}
```

**Docker Log Rotation:**
```json
# /etc/docker/daemon.json
{
  "log-driver": "json-file",
  "log-opts": {
    "max-size": "10m",
    "max-file": "5"
  }
}
```

## Metrics and Monitoring

### Prometheus Integration

**Prometheus Configuration:**
```yaml
# prometheus/prometheus.yml
global:
  scrape_interval: 15s
  evaluation_interval: 15s

rule_files:
  - "rules/*.yml"

alerting:
  alertmanagers:
    - static_configs:
        - targets:
          - alertmanager:9093

scrape_configs:
  - job_name: 'burly-mcp'
    static_configs:
      - targets: ['burly-mcp:8080']
    metrics_path: /metrics
    scrape_interval: 30s

  - job_name: 'node-exporter'
    static_configs:
      - targets: ['node-exporter:9100']

  - job_name: 'docker'
    static_configs:
      - targets: ['docker-exporter:9323']

  - job_name: 'cadvisor'
    static_configs:
      - targets: ['cadvisor:8080']
```

**Application Metrics Endpoint:**
```python
# src/burly_mcp/metrics.py
from prometheus_client import Counter, Histogram, Gauge, generate_latest
import time

# Metrics definitions
TOOL_EXECUTIONS = Counter(
    'burly_mcp_tool_executions_total',
    'Total number of tool executions',
    ['tool_name', 'status']
)

TOOL_EXECUTION_TIME = Histogram(
    'burly_mcp_tool_execution_seconds',
    'Time spent executing tools',
    ['tool_name']
)

ACTIVE_CONNECTIONS = Gauge(
    'burly_mcp_active_connections',
    'Number of active MCP connections'
)

AUDIT_LOG_SIZE = Gauge(
    'burly_mcp_audit_log_size_bytes',
    'Size of audit log file in bytes'
)

def metrics_endpoint():
    """Prometheus metrics endpoint"""
    return generate_latest()

def record_tool_execution(tool_name: str, execution_time: float, success: bool):
    """Record tool execution metrics"""
    status = 'success' if success else 'failure'
    TOOL_EXECUTIONS.labels(tool_name=tool_name, status=status).inc()
    TOOL_EXECUTION_TIME.labels(tool_name=tool_name).observe(execution_time)
```

**Docker Compose Monitoring Stack:**
```yaml
# monitoring/docker-compose.yml
version: '3.8'

services:
  prometheus:
    image: prom/prometheus:v2.45.0
    ports:
      - "9090:9090"
    volumes:
      - ./prometheus:/etc/prometheus
      - prometheus-data:/prometheus
    command:
      - '--config.file=/etc/prometheus/prometheus.yml'
      - '--storage.tsdb.path=/prometheus'
      - '--web.console.libraries=/etc/prometheus/console_libraries'
      - '--web.console.templates=/etc/prometheus/consoles'
      - '--storage.tsdb.retention.time=30d'
      - '--web.enable-lifecycle'

  grafana:
    image: grafana/grafana:10.2.0
    ports:
      - "3000:3000"
    volumes:
      - grafana-data:/var/lib/grafana
      - ./grafana/dashboards:/etc/grafana/provisioning/dashboards
      - ./grafana/datasources:/etc/grafana/provisioning/datasources
    environment:
      - GF_SECURITY_ADMIN_PASSWORD=${GRAFANA_ADMIN_PASSWORD:-admin}
      - GF_USERS_ALLOW_SIGN_UP=false
      - GF_INSTALL_PLUGINS=grafana-piechart-panel

  alertmanager:
    image: prom/alertmanager:v0.26.0
    ports:
      - "9093:9093"
    volumes:
      - ./alertmanager:/etc/alertmanager
      - alertmanager-data:/alertmanager
    command:
      - '--config.file=/etc/alertmanager/alertmanager.yml'
      - '--storage.path=/alertmanager'
      - '--web.external-url=http://localhost:9093'

  node-exporter:
    image: prom/node-exporter:v1.6.1
    ports:
      - "9100:9100"
    volumes:
      - /proc:/host/proc:ro
      - /sys:/host/sys:ro
      - /:/rootfs:ro
    command:
      - '--path.procfs=/host/proc'
      - '--path.sysfs=/host/sys'
      - '--collector.filesystem.ignored-mount-points=^/(sys|proc|dev|host|etc)($$|/)'

  cadvisor:
    image: gcr.io/cadvisor/cadvisor:v0.47.2
    ports:
      - "8081:8080"
    volumes:
      - /:/rootfs:ro
      - /var/run:/var/run:ro
      - /sys:/sys:ro
      - /var/lib/docker/:/var/lib/docker:ro
      - /dev/disk/:/dev/disk:ro
    privileged: true
    devices:
      - /dev/kmsg

volumes:
  prometheus-data:
  grafana-data:
  alertmanager-data:
```

### Grafana Dashboards

**Burly MCP Dashboard Configuration:**
```json
{
  "dashboard": {
    "id": null,
    "title": "Burly MCP Monitoring",
    "tags": ["burly-mcp"],
    "timezone": "browser",
    "panels": [
      {
        "id": 1,
        "title": "Tool Executions per Minute",
        "type": "graph",
        "targets": [
          {
            "expr": "rate(burly_mcp_tool_executions_total[5m]) * 60",
            "legendFormat": "{{tool_name}} - {{status}}"
          }
        ],
        "yAxes": [
          {
            "label": "Executions/min",
            "min": 0
          }
        ]
      },
      {
        "id": 2,
        "title": "Tool Execution Time",
        "type": "graph",
        "targets": [
          {
            "expr": "histogram_quantile(0.95, rate(burly_mcp_tool_execution_seconds_bucket[5m]))",
            "legendFormat": "95th percentile"
          },
          {
            "expr": "histogram_quantile(0.50, rate(burly_mcp_tool_execution_seconds_bucket[5m]))",
            "legendFormat": "50th percentile"
          }
        ]
      },
      {
        "id": 3,
        "title": "Active Connections",
        "type": "singlestat",
        "targets": [
          {
            "expr": "burly_mcp_active_connections",
            "legendFormat": "Connections"
          }
        ]
      },
      {
        "id": 4,
        "title": "Container Resources",
        "type": "graph",
        "targets": [
          {
            "expr": "rate(container_cpu_usage_seconds_total{name=\"burly-mcp\"}[5m]) * 100",
            "legendFormat": "CPU %"
          },
          {
            "expr": "container_memory_usage_bytes{name=\"burly-mcp\"} / 1024 / 1024",
            "legendFormat": "Memory MB"
          }
        ]
      }
    ],
    "time": {
      "from": "now-1h",
      "to": "now"
    },
    "refresh": "30s"
  }
}
```

**System Dashboard:**
```json
{
  "dashboard": {
    "title": "System Metrics",
    "panels": [
      {
        "title": "CPU Usage",
        "type": "graph",
        "targets": [
          {
            "expr": "100 - (avg by (instance) (rate(node_cpu_seconds_total{mode=\"idle\"}[5m])) * 100)",
            "legendFormat": "CPU Usage %"
          }
        ]
      },
      {
        "title": "Memory Usage",
        "type": "graph",
        "targets": [
          {
            "expr": "(node_memory_MemTotal_bytes - node_memory_MemAvailable_bytes) / node_memory_MemTotal_bytes * 100",
            "legendFormat": "Memory Usage %"
          }
        ]
      },
      {
        "title": "Disk Usage",
        "type": "graph",
        "targets": [
          {
            "expr": "100 - (node_filesystem_avail_bytes{mountpoint=\"/\"} / node_filesystem_size_bytes{mountpoint=\"/\"} * 100)",
            "legendFormat": "Disk Usage %"
          }
        ]
      }
    ]
  }
}
```

## Alerting Configuration

### Prometheus Alert Rules

```yaml
# prometheus/rules/burly-mcp.yml
groups:
  - name: burly-mcp
    rules:
      - alert: BurlyMCPDown
        expr: up{job="burly-mcp"} == 0
        for: 1m
        labels:
          severity: critical
        annotations:
          summary: "Burly MCP is down"
          description: "Burly MCP has been down for more than 1 minute"

      - alert: HighToolFailureRate
        expr: rate(burly_mcp_tool_executions_total{status="failure"}[5m]) > 0.1
        for: 2m
        labels:
          severity: warning
        annotations:
          summary: "High tool failure rate"
          description: "Tool failure rate is {{ $value }} failures per second"

      - alert: SlowToolExecution
        expr: histogram_quantile(0.95, rate(burly_mcp_tool_execution_seconds_bucket[5m])) > 30
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "Slow tool execution"
          description: "95th percentile tool execution time is {{ $value }} seconds"

      - alert: HighMemoryUsage
        expr: container_memory_usage_bytes{name="burly-mcp"} / container_spec_memory_limit_bytes{name="burly-mcp"} > 0.8
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "High memory usage"
          description: "Memory usage is {{ $value | humanizePercentage }}"

      - alert: AuditLogGrowth
        expr: increase(burly_mcp_audit_log_size_bytes[1h]) > 100000000  # 100MB per hour
        for: 0m
        labels:
          severity: info
        annotations:
          summary: "Rapid audit log growth"
          description: "Audit log grew by {{ $value | humanizeBytes }} in the last hour"

  - name: system
    rules:
      - alert: HighCPUUsage
        expr: 100 - (avg by (instance) (rate(node_cpu_seconds_total{mode="idle"}[5m])) * 100) > 80
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "High CPU usage"
          description: "CPU usage is {{ $value }}%"

      - alert: HighMemoryUsage
        expr: (node_memory_MemTotal_bytes - node_memory_MemAvailable_bytes) / node_memory_MemTotal_bytes * 100 > 85
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "High memory usage"
          description: "Memory usage is {{ $value }}%"

      - alert: LowDiskSpace
        expr: 100 - (node_filesystem_avail_bytes{mountpoint="/"} / node_filesystem_size_bytes{mountpoint="/"} * 100) > 90
        for: 5m
        labels:
          severity: critical
        annotations:
          summary: "Low disk space"
          description: "Disk usage is {{ $value }}%"
```

### Alertmanager Configuration

```yaml
# alertmanager/alertmanager.yml
global:
  smtp_smarthost: 'smtp.company.com:587'
  smtp_from: 'alerts@company.com'
  smtp_auth_username: 'alerts@company.com'
  smtp_auth_password: 'password'

route:
  group_by: ['alertname']
  group_wait: 10s
  group_interval: 10s
  repeat_interval: 1h
  receiver: 'web.hook'
  routes:
    - match:
        severity: critical
      receiver: 'critical-alerts'
    - match:
        severity: warning
      receiver: 'warning-alerts'

receivers:
  - name: 'web.hook'
    webhook_configs:
      - url: 'http://webhook-service:5000/alerts'

  - name: 'critical-alerts'
    email_configs:
      - to: 'oncall@company.com'
        subject: 'CRITICAL: {{ .GroupLabels.alertname }}'
        body: |
          {{ range .Alerts }}
          Alert: {{ .Annotations.summary }}
          Description: {{ .Annotations.description }}
          {{ end }}
    slack_configs:
      - api_url: 'https://hooks.slack.com/services/YOUR/SLACK/WEBHOOK'
        channel: '#alerts'
        title: 'CRITICAL Alert'
        text: '{{ range .Alerts }}{{ .Annotations.summary }}{{ end }}'

  - name: 'warning-alerts'
    email_configs:
      - to: 'team@company.com'
        subject: 'WARNING: {{ .GroupLabels.alertname }}'
        body: |
          {{ range .Alerts }}
          Alert: {{ .Annotations.summary }}
          Description: {{ .Annotations.description }}
          {{ end }}

inhibit_rules:
  - source_match:
      severity: 'critical'
    target_match:
      severity: 'warning'
    equal: ['alertname', 'instance']
```

## Health Checks and Monitoring

### Application Health Checks

```python
# src/burly_mcp/health.py
import json
import time
from pathlib import Path
from typing import Dict, Any

class HealthChecker:
    def __init__(self, config):
        self.config = config
        
    def check_health(self) -> Dict[str, Any]:
        """Comprehensive health check"""
        checks = {
            'timestamp': time.time(),
            'status': 'healthy',
            'checks': {}
        }
        
        # Configuration check
        checks['checks']['config'] = self._check_config()
        
        # File system check
        checks['checks']['filesystem'] = self._check_filesystem()
        
        # Docker connectivity check
        checks['checks']['docker'] = self._check_docker()
        
        # Notification service check
        checks['checks']['notifications'] = self._check_notifications()
        
        # Overall status
        failed_checks = [name for name, check in checks['checks'].items() 
                        if check['status'] != 'healthy']
        
        if failed_checks:
            checks['status'] = 'unhealthy'
            checks['failed_checks'] = failed_checks
            
        return checks
    
    def _check_config(self) -> Dict[str, Any]:
        """Check configuration validity"""
        try:
            errors = self.config.validate()
            return {
                'status': 'healthy' if not errors else 'unhealthy',
                'errors': errors,
                'timestamp': time.time()
            }
        except Exception as e:
            return {
                'status': 'unhealthy',
                'error': str(e),
                'timestamp': time.time()
            }
    
    def _check_filesystem(self) -> Dict[str, Any]:
        """Check filesystem access"""
        try:
            # Check required directories
            directories = [
                self.config.config_dir,
                self.config.log_dir,
                self.config.blog_stage_root,
                self.config.blog_publish_root
            ]
            
            for directory in directories:
                if not Path(directory).exists():
                    return {
                        'status': 'unhealthy',
                        'error': f'Directory not found: {directory}',
                        'timestamp': time.time()
                    }
                    
            return {
                'status': 'healthy',
                'directories_checked': len(directories),
                'timestamp': time.time()
            }
        except Exception as e:
            return {
                'status': 'unhealthy',
                'error': str(e),
                'timestamp': time.time()
            }
    
    def _check_docker(self) -> Dict[str, Any]:
        """Check Docker connectivity"""
        try:
            import docker
            client = docker.from_env()
            client.ping()
            return {
                'status': 'healthy',
                'docker_version': client.version()['Version'],
                'timestamp': time.time()
            }
        except Exception as e:
            return {
                'status': 'unhealthy',
                'error': str(e),
                'timestamp': time.time()
            }
    
    def _check_notifications(self) -> Dict[str, Any]:
        """Check notification service connectivity"""
        try:
            if not self.config.gotify_url:
                return {
                    'status': 'disabled',
                    'message': 'Notifications not configured',
                    'timestamp': time.time()
                }
                
            # Test connectivity (without sending notification)
            import requests
            response = requests.get(
                f"{self.config.gotify_url}/health",
                timeout=5
            )
            
            return {
                'status': 'healthy' if response.status_code == 200 else 'unhealthy',
                'response_code': response.status_code,
                'timestamp': time.time()
            }
        except Exception as e:
            return {
                'status': 'unhealthy',
                'error': str(e),
                'timestamp': time.time()
            }
```

### Docker Health Check

```dockerfile
# Dockerfile health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
  CMD python -c "
from burly_mcp.health import HealthChecker
from burly_mcp.config import Config
import sys
health = HealthChecker(Config()).check_health()
sys.exit(0 if health['status'] == 'healthy' else 1)
"
```

### Kubernetes Probes

```yaml
# k8s/deployment.yaml
livenessProbe:
  httpGet:
    path: /health
    port: 8080
  initialDelaySeconds: 30
  periodSeconds: 30
  timeoutSeconds: 10
  failureThreshold: 3

readinessProbe:
  httpGet:
    path: /ready
    port: 8080
  initialDelaySeconds: 5
  periodSeconds: 10
  timeoutSeconds: 5
  failureThreshold: 3

startupProbe:
  httpGet:
    path: /health
    port: 8080
  initialDelaySeconds: 10
  periodSeconds: 10
  timeoutSeconds: 5
  failureThreshold: 30
```

## Log Analysis and Observability

### Log Parsing and Analysis

```bash
#!/bin/bash
# log-analysis.sh - Automated log analysis script

LOG_FILE="/var/log/agentops/audit.jsonl"
REPORT_FILE="/tmp/burly-mcp-report-$(date +%Y%m%d).txt"

echo "Burly MCP Log Analysis Report - $(date)" > "$REPORT_FILE"
echo "=========================================" >> "$REPORT_FILE"

# Tool usage statistics
echo -e "\nTool Usage Statistics:" >> "$REPORT_FILE"
jq -r '.tool_name' "$LOG_FILE" | sort | uniq -c | sort -nr >> "$REPORT_FILE"

# Success/failure rates
echo -e "\nSuccess/Failure Rates:" >> "$REPORT_FILE"
jq -r '.result' "$LOG_FILE" | sort | uniq -c >> "$REPORT_FILE"

# Average execution times
echo -e "\nAverage Execution Times by Tool:" >> "$REPORT_FILE"
jq -r 'select(.execution_time) | "\(.tool_name) \(.execution_time)"' "$LOG_FILE" | \
  awk '{sum[$1]+=$2; count[$1]++} END {for(tool in sum) printf "%s: %.3fs\n", tool, sum[tool]/count[tool]}' | \
  sort >> "$REPORT_FILE"

# Error analysis
echo -e "\nRecent Errors:" >> "$REPORT_FILE"
jq -r 'select(.result == "failure") | "\(.timestamp) \(.tool_name) \(.error // "Unknown error")"' "$LOG_FILE" | \
  tail -10 >> "$REPORT_FILE"

# Security events
echo -e "\nSecurity Events:" >> "$REPORT_FILE"
jq -r 'select(.security_context.requires_confirmation == true) | "\(.timestamp) \(.tool_name) \(.user_id)"' "$LOG_FILE" | \
  tail -10 >> "$REPORT_FILE"

echo "Report generated: $REPORT_FILE"
```

### Custom Metrics Collection

```python
# scripts/collect-metrics.py
#!/usr/bin/env python3
"""Custom metrics collection script"""

import json
import time
import subprocess
from pathlib import Path
from datetime import datetime, timedelta

def collect_audit_metrics():
    """Collect metrics from audit logs"""
    audit_file = Path("/var/log/agentops/audit.jsonl")
    if not audit_file.exists():
        return {}
    
    metrics = {
        'total_executions': 0,
        'successful_executions': 0,
        'failed_executions': 0,
        'tools_used': set(),
        'avg_execution_time': 0,
        'last_24h_executions': 0
    }
    
    total_time = 0
    now = datetime.now()
    yesterday = now - timedelta(days=1)
    
    with open(audit_file, 'r') as f:
        for line in f:
            try:
                entry = json.loads(line.strip())
                metrics['total_executions'] += 1
                
                if entry.get('result') == 'success':
                    metrics['successful_executions'] += 1
                else:
                    metrics['failed_executions'] += 1
                
                metrics['tools_used'].add(entry.get('tool_name', 'unknown'))
                
                if 'execution_time' in entry:
                    total_time += entry['execution_time']
                
                # Check if within last 24 hours
                entry_time = datetime.fromisoformat(entry['timestamp'].replace('Z', '+00:00'))
                if entry_time > yesterday:
                    metrics['last_24h_executions'] += 1
                    
            except (json.JSONDecodeError, KeyError, ValueError):
                continue
    
    if metrics['total_executions'] > 0:
        metrics['avg_execution_time'] = total_time / metrics['total_executions']
        metrics['success_rate'] = metrics['successful_executions'] / metrics['total_executions']
    
    metrics['tools_used'] = list(metrics['tools_used'])
    return metrics

def collect_system_metrics():
    """Collect system metrics"""
    try:
        # Docker stats
        docker_stats = subprocess.run(
            ['docker', 'stats', '--no-stream', '--format', 'table {{.Container}}\t{{.CPUPerc}}\t{{.MemUsage}}'],
            capture_output=True, text=True
        )
        
        # Disk usage
        disk_usage = subprocess.run(
            ['df', '-h', '/var/log/agentops'],
            capture_output=True, text=True
        )
        
        return {
            'docker_stats': docker_stats.stdout,
            'disk_usage': disk_usage.stdout,
            'timestamp': datetime.now().isoformat()
        }
    except Exception as e:
        return {'error': str(e)}

def main():
    """Main metrics collection function"""
    metrics = {
        'timestamp': datetime.now().isoformat(),
        'audit_metrics': collect_audit_metrics(),
        'system_metrics': collect_system_metrics()
    }
    
    # Output metrics in JSON format for consumption by monitoring systems
    print(json.dumps(metrics, indent=2, default=str))

if __name__ == '__main__':
    main()
```

This comprehensive monitoring and logging configuration provides full observability for Burly MCP deployments, including metrics collection, alerting, log aggregation, and health monitoring suitable for production environments.