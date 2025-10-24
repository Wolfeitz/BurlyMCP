# Deployment Guide

## Overview

This guide provides comprehensive deployment instructions for Burly MCP across different environments, from development to production. Burly MCP is designed to be deployed as a containerized application with strong security defaults and flexible configuration options.

## Deployment Environments

### Development Environment

**Prerequisites:**
- Docker and Docker Compose
- Git
- Text editor
- Basic understanding of environment variables

**Quick Setup:**
```bash
# Clone repository
git clone <repository-url>
cd burly-mcp

# Create development environment
cp .env.example .env.development
mkdir -p ./logs ./test_data/blog/stage ./test_data/blog/publish

# Configure for development
cat >> .env.development << EOF
BURLY_CONFIG_DIR=./config
BURLY_LOG_DIR=./logs
LOG_LEVEL=DEBUG
BLOG_STAGE_ROOT=./test_data/blog/stage
BLOG_PUBLISH_ROOT=./test_data/blog/publish
DEVELOPMENT_MODE=true
NOTIFICATIONS_ENABLED=false
EOF

# Start development container
docker-compose --env-file .env.development up -d

# Verify deployment
docker-compose ps
docker-compose logs burly-mcp
```

**Development Features:**
- Debug logging enabled
- Local file system mounts
- Hot reload capabilities
- Relaxed security for testing
- Console-only notifications

### Staging Environment

**Prerequisites:**
- Docker Swarm or Kubernetes cluster
- Persistent storage volumes
- SSL certificates
- Monitoring infrastructure

**Configuration:**
```bash
# Create staging environment file
cp .env.example .env.staging

# Configure staging-specific settings
cat >> .env.staging << EOF
BURLY_CONFIG_DIR=/app/config
BURLY_LOG_DIR=/var/log/agentops
LOG_LEVEL=INFO
AUDIT_ENABLED=true
BLOG_STAGE_ROOT=/data/blog/stage
BLOG_PUBLISH_ROOT=/data/blog/publish
GOTIFY_URL=https://notifications-staging.company.com
GOTIFY_TOKEN=${STAGING_GOTIFY_TOKEN}
NOTIFICATIONS_ENABLED=true
NOTIFICATION_PROVIDERS=gotify,console
MAX_CONCURRENT_TOOLS=3
EOF

# Deploy with staging configuration
docker-compose --env-file .env.staging up -d
```

**Staging Features:**
- Production-like configuration
- External notification integration
- Audit logging enabled
- Resource limits enforced
- SSL/TLS encryption

### Production Environment

**Prerequisites:**
- Production-grade container orchestration (Kubernetes, Docker Swarm)
- High-availability storage
- Load balancer with SSL termination
- Centralized logging system
- Monitoring and alerting
- Backup and disaster recovery procedures

**Security Hardening:**
```bash
# Create production environment
cp .env.example .env.production

# Production configuration
cat >> .env.production << EOF
BURLY_CONFIG_DIR=/app/config
BURLY_LOG_DIR=/var/log/agentops
LOG_LEVEL=WARNING
AUDIT_ENABLED=true
BLOG_STAGE_ROOT=/data/blog/stage
BLOG_PUBLISH_ROOT=/data/blog/publish
GOTIFY_URL=https://notifications.company.com
GOTIFY_TOKEN=${PRODUCTION_GOTIFY_TOKEN}
NOTIFICATIONS_ENABLED=true
NOTIFICATION_PROVIDERS=gotify
MAX_CONCURRENT_TOOLS=5
DOCKER_TIMEOUT=60
DEFAULT_TIMEOUT_SEC=45
MAX_OUTPUT_SIZE=2097152
PUID=1000
PGID=1000
PYTHONUNBUFFERED=1
EOF
```

**Production Docker Compose:**
```yaml
# docker-compose.production.yml
version: '3.8'

services:
  burly-mcp:
    image: burly-mcp:${VERSION:-latest}
    restart: unless-stopped
    user: "1000:1000"
    read_only: true
    security_opt:
      - no-new-privileges:true
    cap_drop:
      - ALL
    cap_add:
      - CHOWN
      - SETUID
      - SETGID
    environment:
      - BURLY_CONFIG_DIR=/app/config
      - BURLY_LOG_DIR=/var/log/agentops
      - PYTHONUNBUFFERED=1
    env_file:
      - .env.production
    volumes:
      - ./config:/app/config:ro
      - blog-stage:/data/blog/stage:ro
      - blog-publish:/data/blog/publish:rw
      - audit-logs:/var/log/agentops:rw
      - /var/run/docker.sock:/var/run/docker.sock:ro
    tmpfs:
      - /tmp:noexec,nosuid,size=100m
    deploy:
      resources:
        limits:
          memory: 512M
          cpus: '0.5'
        reservations:
          memory: 128M
          cpus: '0.1'
      restart_policy:
        condition: on-failure
        delay: 5s
        max_attempts: 3
        window: 120s
    healthcheck:
      test: ["CMD", "python", "-c", "import burly_mcp; print('healthy')"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 40s
    logging:
      driver: "json-file"
      options:
        max-size: "10m"
        max-file: "3"

volumes:
  blog-stage:
    driver: local
    driver_opts:
      type: none
      o: bind
      device: /data/blog/stage
  blog-publish:
    driver: local
    driver_opts:
      type: none
      o: bind
      device: /data/blog/publish
  audit-logs:
    driver: local
    driver_opts:
      type: none
      o: bind
      device: /var/log/agentops

networks:
  default:
    driver: bridge
    ipam:
      config:
        - subnet: 172.20.0.0/16
```

## Kubernetes Deployment

### Namespace and RBAC

```yaml
# k8s/namespace.yaml
apiVersion: v1
kind: Namespace
metadata:
  name: burly-mcp
  labels:
    name: burly-mcp
    security.policy: restricted

---
apiVersion: v1
kind: ServiceAccount
metadata:
  name: burly-mcp
  namespace: burly-mcp

---
apiVersion: rbac.authorization.k8s.io/v1
kind: Role
metadata:
  namespace: burly-mcp
  name: burly-mcp-role
rules:
- apiGroups: [""]
  resources: ["pods"]
  verbs: ["get", "list"]

---
apiVersion: rbac.authorization.k8s.io/v1
kind: RoleBinding
metadata:
  name: burly-mcp-binding
  namespace: burly-mcp
subjects:
- kind: ServiceAccount
  name: burly-mcp
  namespace: burly-mcp
roleRef:
  kind: Role
  name: burly-mcp-role
  apiGroup: rbac.authorization.k8s.io
```

### ConfigMap and Secrets

```yaml
# k8s/configmap.yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: burly-mcp-config
  namespace: burly-mcp
data:
  BURLY_CONFIG_DIR: "/app/config"
  BURLY_LOG_DIR: "/var/log/agentops"
  LOG_LEVEL: "WARNING"
  AUDIT_ENABLED: "true"
  NOTIFICATIONS_ENABLED: "true"
  NOTIFICATION_PROVIDERS: "gotify"
  MAX_CONCURRENT_TOOLS: "5"
  DEFAULT_TIMEOUT_SEC: "45"
  MAX_OUTPUT_SIZE: "2097152"

---
apiVersion: v1
kind: Secret
metadata:
  name: burly-mcp-secrets
  namespace: burly-mcp
type: Opaque
data:
  GOTIFY_TOKEN: <base64-encoded-token>
  GOTIFY_URL: <base64-encoded-url>
```

### Deployment

```yaml
# k8s/deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: burly-mcp
  namespace: burly-mcp
  labels:
    app: burly-mcp
spec:
  replicas: 2
  selector:
    matchLabels:
      app: burly-mcp
  template:
    metadata:
      labels:
        app: burly-mcp
    spec:
      serviceAccountName: burly-mcp
      securityContext:
        runAsNonRoot: true
        runAsUser: 1000
        runAsGroup: 1000
        fsGroup: 1000
      containers:
      - name: burly-mcp
        image: burly-mcp:v1.0.0
        imagePullPolicy: Always
        securityContext:
          allowPrivilegeEscalation: false
          readOnlyRootFilesystem: true
          capabilities:
            drop:
            - ALL
            add:
            - CHOWN
            - SETUID
            - SETGID
        envFrom:
        - configMapRef:
            name: burly-mcp-config
        - secretRef:
            name: burly-mcp-secrets
        resources:
          limits:
            memory: "512Mi"
            cpu: "500m"
          requests:
            memory: "128Mi"
            cpu: "100m"
        volumeMounts:
        - name: config
          mountPath: /app/config
          readOnly: true
        - name: blog-stage
          mountPath: /data/blog/stage
          readOnly: true
        - name: blog-publish
          mountPath: /data/blog/publish
        - name: audit-logs
          mountPath: /var/log/agentops
        - name: tmp
          mountPath: /tmp
        livenessProbe:
          exec:
            command:
            - python
            - -c
            - "import burly_mcp; print('healthy')"
          initialDelaySeconds: 30
          periodSeconds: 30
          timeoutSeconds: 10
          failureThreshold: 3
        readinessProbe:
          exec:
            command:
            - python
            - -c
            - "import burly_mcp; print('ready')"
          initialDelaySeconds: 5
          periodSeconds: 10
          timeoutSeconds: 5
          failureThreshold: 3
      volumes:
      - name: config
        configMap:
          name: burly-mcp-policy
      - name: blog-stage
        persistentVolumeClaim:
          claimName: blog-stage-pvc
      - name: blog-publish
        persistentVolumeClaim:
          claimName: blog-publish-pvc
      - name: audit-logs
        persistentVolumeClaim:
          claimName: audit-logs-pvc
      - name: tmp
        emptyDir:
          sizeLimit: 100Mi
```

## Cloud Provider Deployments

### AWS ECS

```json
{
  "family": "burly-mcp",
  "networkMode": "awsvpc",
  "requiresCompatibilities": ["FARGATE"],
  "cpu": "512",
  "memory": "1024",
  "executionRoleArn": "arn:aws:iam::account:role/ecsTaskExecutionRole",
  "taskRoleArn": "arn:aws:iam::account:role/burly-mcp-task-role",
  "containerDefinitions": [
    {
      "name": "burly-mcp",
      "image": "your-registry/burly-mcp:v1.0.0",
      "essential": true,
      "user": "1000:1000",
      "readonlyRootFilesystem": true,
      "environment": [
        {"name": "BURLY_CONFIG_DIR", "value": "/app/config"},
        {"name": "BURLY_LOG_DIR", "value": "/var/log/agentops"},
        {"name": "LOG_LEVEL", "value": "WARNING"},
        {"name": "AUDIT_ENABLED", "value": "true"}
      ],
      "secrets": [
        {
          "name": "GOTIFY_TOKEN",
          "valueFrom": "arn:aws:secretsmanager:region:account:secret:burly-mcp/gotify-token"
        }
      ],
      "mountPoints": [
        {
          "sourceVolume": "blog-stage",
          "containerPath": "/data/blog/stage",
          "readOnly": true
        },
        {
          "sourceVolume": "blog-publish",
          "containerPath": "/data/blog/publish",
          "readOnly": false
        }
      ],
      "logConfiguration": {
        "logDriver": "awslogs",
        "options": {
          "awslogs-group": "/ecs/burly-mcp",
          "awslogs-region": "us-west-2",
          "awslogs-stream-prefix": "ecs"
        }
      },
      "healthCheck": {
        "command": ["CMD-SHELL", "python -c 'import burly_mcp; print(\"healthy\")'"],
        "interval": 30,
        "timeout": 10,
        "retries": 3,
        "startPeriod": 60
      }
    }
  ],
  "volumes": [
    {
      "name": "blog-stage",
      "efsVolumeConfiguration": {
        "fileSystemId": "fs-12345678",
        "rootDirectory": "/blog/stage",
        "transitEncryption": "ENABLED"
      }
    },
    {
      "name": "blog-publish",
      "efsVolumeConfiguration": {
        "fileSystemId": "fs-12345678",
        "rootDirectory": "/blog/publish",
        "transitEncryption": "ENABLED"
      }
    }
  ]
}
```

### Google Cloud Run

```yaml
# cloudrun.yaml
apiVersion: serving.knative.dev/v1
kind: Service
metadata:
  name: burly-mcp
  annotations:
    run.googleapis.com/ingress: private
spec:
  template:
    metadata:
      annotations:
        run.googleapis.com/execution-environment: gen2
        run.googleapis.com/cpu-throttling: "false"
    spec:
      serviceAccountName: burly-mcp@project.iam.gserviceaccount.com
      containerConcurrency: 1
      timeoutSeconds: 300
      containers:
      - image: gcr.io/project/burly-mcp:v1.0.0
        resources:
          limits:
            cpu: "1"
            memory: "512Mi"
        env:
        - name: BURLY_CONFIG_DIR
          value: "/app/config"
        - name: LOG_LEVEL
          value: "WARNING"
        - name: GOTIFY_TOKEN
          valueFrom:
            secretKeyRef:
              name: gotify-token
              key: token
        volumeMounts:
        - name: blog-storage
          mountPath: /data/blog
      volumes:
      - name: blog-storage
        csi:
          driver: gcsfuse.csi.storage.gke.io
          volumeAttributes:
            bucketName: burly-mcp-blog-storage
```

## Security Considerations

### Container Security

**Image Security:**
```bash
# Build secure image
docker build --no-cache \
  --build-arg BUILD_DATE=$(date -u +'%Y-%m-%dT%H:%M:%SZ') \
  --build-arg VCS_REF=$(git rev-parse --short HEAD) \
  -t burly-mcp:secure .

# Scan for vulnerabilities
trivy image --exit-code 1 --severity HIGH,CRITICAL burly-mcp:secure

# Sign image (optional)
cosign sign --key cosign.key burly-mcp:secure
```

**Runtime Security:**
```bash
# Run with security options
docker run -d \
  --name burly-mcp \
  --user 1000:1000 \
  --read-only \
  --tmpfs /tmp:noexec,nosuid,size=100m \
  --security-opt no-new-privileges:true \
  --cap-drop ALL \
  --cap-add CHOWN,SETUID,SETGID \
  --memory 512m \
  --cpus 0.5 \
  burly-mcp:secure
```

### Network Security

**Firewall Rules:**
```bash
# Allow only necessary traffic
iptables -A INPUT -p tcp --dport 22 -j ACCEPT  # SSH
iptables -A INPUT -p tcp --dport 443 -j ACCEPT # HTTPS
iptables -A INPUT -m state --state ESTABLISHED,RELATED -j ACCEPT
iptables -A INPUT -j DROP

# Docker network isolation
docker network create --driver bridge \
  --subnet=172.20.0.0/16 \
  --ip-range=172.20.240.0/20 \
  burly-mcp-network
```

**SSL/TLS Configuration:**
```nginx
# nginx.conf for reverse proxy
server {
    listen 443 ssl http2;
    server_name burly-mcp.company.com;
    
    ssl_certificate /etc/ssl/certs/burly-mcp.crt;
    ssl_certificate_key /etc/ssl/private/burly-mcp.key;
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers ECDHE-RSA-AES256-GCM-SHA512:DHE-RSA-AES256-GCM-SHA512;
    ssl_prefer_server_ciphers off;
    
    location / {
        proxy_pass http://burly-mcp:8080;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

## Backup and Disaster Recovery

### Backup Strategy

```bash
#!/bin/bash
# backup.sh - Comprehensive backup script

BACKUP_DIR="/backups/burly-mcp/$(date +%Y%m%d_%H%M%S)"
mkdir -p "$BACKUP_DIR"

# Configuration backup
tar -czf "$BACKUP_DIR/config.tar.gz" ./config/

# Blog content backup
tar -czf "$BACKUP_DIR/blog-stage.tar.gz" /data/blog/stage/
tar -czf "$BACKUP_DIR/blog-publish.tar.gz" /data/blog/publish/

# Audit logs backup
tar -czf "$BACKUP_DIR/audit-logs.tar.gz" /var/log/agentops/

# Database backup (if applicable)
# pg_dump burly_mcp > "$BACKUP_DIR/database.sql"

# Environment configuration
cp .env.production "$BACKUP_DIR/"

# Docker image backup
docker save burly-mcp:latest | gzip > "$BACKUP_DIR/burly-mcp-image.tar.gz"

# Cleanup old backups (keep 30 days)
find /backups/burly-mcp/ -type d -mtime +30 -exec rm -rf {} \;

echo "Backup completed: $BACKUP_DIR"
```

### Disaster Recovery

```bash
#!/bin/bash
# restore.sh - Disaster recovery script

BACKUP_DIR="$1"
if [ -z "$BACKUP_DIR" ]; then
    echo "Usage: $0 <backup_directory>"
    exit 1
fi

# Stop services
docker-compose down

# Restore configuration
tar -xzf "$BACKUP_DIR/config.tar.gz" -C ./

# Restore blog content
tar -xzf "$BACKUP_DIR/blog-stage.tar.gz" -C /
tar -xzf "$BACKUP_DIR/blog-publish.tar.gz" -C /

# Restore audit logs
tar -xzf "$BACKUP_DIR/audit-logs.tar.gz" -C /

# Restore environment
cp "$BACKUP_DIR/.env.production" ./

# Restore Docker image
docker load < "$BACKUP_DIR/burly-mcp-image.tar.gz"

# Start services
docker-compose up -d

echo "Restore completed from: $BACKUP_DIR"
```

## Performance Optimization

### Resource Tuning

```yaml
# docker-compose.performance.yml
services:
  burly-mcp:
    deploy:
      resources:
        limits:
          memory: 1G
          cpus: '1.0'
        reservations:
          memory: 256M
          cpus: '0.2'
    environment:
      - MAX_CONCURRENT_TOOLS=10
      - DEFAULT_TIMEOUT_SEC=60
      - MAX_OUTPUT_SIZE=4194304  # 4MB
    ulimits:
      nofile:
        soft: 65536
        hard: 65536
```

### Monitoring Integration

```yaml
# monitoring/docker-compose.yml
version: '3.8'

services:
  prometheus:
    image: prom/prometheus:latest
    ports:
      - "9090:9090"
    volumes:
      - ./prometheus.yml:/etc/prometheus/prometheus.yml
      - prometheus-data:/prometheus
    command:
      - '--config.file=/etc/prometheus/prometheus.yml'
      - '--storage.tsdb.path=/prometheus'
      - '--web.console.libraries=/etc/prometheus/console_libraries'
      - '--web.console.templates=/etc/prometheus/consoles'

  grafana:
    image: grafana/grafana:latest
    ports:
      - "3000:3000"
    volumes:
      - grafana-data:/var/lib/grafana
      - ./grafana/dashboards:/etc/grafana/provisioning/dashboards
      - ./grafana/datasources:/etc/grafana/provisioning/datasources
    environment:
      - GF_SECURITY_ADMIN_PASSWORD=admin

  node-exporter:
    image: prom/node-exporter:latest
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

volumes:
  prometheus-data:
  grafana-data:
```

This deployment guide provides comprehensive instructions for deploying Burly MCP across different environments with appropriate security, monitoring, and operational considerations.