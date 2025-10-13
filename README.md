# Burly MCP Server

A secure, policy-driven Model Context Protocol (MCP) server that enables AI assistants to safely execute system operations through a standardized interface.

## What is MCP and Why Should You Care?

The **Model Context Protocol (MCP)** is a standardized way for AI assistants to interact with external tools and services. Think of it as a secure bridge between AI systems and your infrastructure.

### The Problem MCP Solves

Traditional AI assistants are limited to text generation and can't interact with your systems directly. When you ask an AI to "check my Docker containers" or "publish my blog post," it can only give you the commands to run manually.

### The MCP Solution

MCP enables AI assistants to:
- ✅ Execute real system operations safely
- ✅ Follow strict security policies
- ✅ Provide immediate, actionable results
- ✅ Maintain comprehensive audit trails

### Why "Burly" MCP?

This implementation is "burly" because it's built with security and robustness as primary concerns:
- **Policy-driven**: Only whitelisted operations are allowed
- **Containerized**: Runs with minimal privileges in isolation
- **Audited**: Every operation is logged for compliance
- **Confirmed**: Dangerous operations require explicit approval

## Quick Start

### Prerequisites

**System Requirements:**
- Docker and Docker Compose
- Python 3.12+ (for development)
- Basic understanding of containerization

**System Dependencies:**
- Docker daemon (for container operations)
- Access to `/var/run/docker.sock` (for Docker API)
- Sufficient disk space for audit logs
- Network access for Gotify notifications (optional)

### Security Tools (Recommended)

For comprehensive security analysis during development:

```bash
# Install security scanning tools
sudo apt install gitleaks          # Secret detection
sudo snap install trivy           # Vulnerability scanning

# Or using alternative package managers:
# brew install gitleaks trivy      # macOS with Homebrew
# choco install gitleaks trivy     # Windows with Chocolatey
```

These tools are used for:
- **gitleaks**: Scanning for exposed secrets and credentials in code
- **trivy**: Filesystem vulnerability scanning for known security issues
- **npm audit**: Dependency vulnerability checking (built into npm)

### 1. Clone and Setup

```bash
git clone https://github.com/your-org/burly-mcp.git
cd burly-mcp

# Copy environment template
cp .env.example .env

# Edit configuration (optional)
nano .env
```

### 2. Run with Docker Compose

```bash
# Start the MCP server
docker-compose up -d

# View logs
docker-compose logs -f burly-mcp

# Test the server
echo '{"method": "list_tools"}' | docker-compose exec -T burly-mcp python -m server.main
```

### 3. Integration with Open WebUI

See [docs/open-webui.md](docs/open-webui.md) for detailed integration instructions.

## Alternative: Manual Installation

If you prefer to run without Docker:

```bash
# Install Python dependencies
pip install -e .

# Create required directories
sudo mkdir -p /var/log/agentops
sudo chown $USER:$USER /var/log/agentops

# Run the MCP server
python -m server.main
```

**Note:** Manual installation requires:
- Python 3.12+
- All system dependencies listed above
- Proper permissions for log directories
- Docker daemon running (for Docker tools)

## Available Tools

Burly MCP provides these system operation tools:

### 📦 Docker Operations
- **`docker_ps`**: List running containers with status information
- Safe read-only access to Docker daemon

### 💾 System Monitoring  
- **`disk_space`**: Check filesystem usage across mounted volumes
- Helps monitor storage capacity and usage patterns

### 📝 Blog Management
- **`blog_stage_markdown`**: Validate blog posts with YAML front-matter
- **`blog_publish_static`**: Publish validated content (requires confirmation)
- Secure file operations with path traversal protection

### 🔔 Notifications
- **`gotify_ping`**: Send test notifications via Gotify
- Optional integration for operation alerts

## Security Model

Burly MCP implements defense-in-depth security:

### 🛡️ Container Security
- Runs as non-root user (`agentops:1000`)
- Read-only filesystem with minimal writable areas
- No network ports exposed (stdin/stdout only)
- Resource limits prevent resource exhaustion

### 📋 Policy Enforcement
- All tools must be explicitly whitelisted in `policy/tools.yaml`
- JSON Schema validation for all tool arguments
- Path traversal protection for file operations
- Timeout enforcement prevents hanging operations

### 🔍 Audit and Monitoring
- Every operation logged in JSON Lines format
- Argument hashing preserves privacy while enabling audit
- Optional Gotify notifications for real-time monitoring
- Comprehensive execution metrics and error tracking

### ⚠️ Confirmation Workflow
- Mutating operations require explicit confirmation
- Two-step process prevents accidental destructive actions
- Clear indication of what will be modified

## Configuration

### Environment Variables

```bash
# Gotify Notifications (Optional)
GOTIFY_ENABLED=false
GOTIFY_URL=https://gotify.example.com
GOTIFY_TOKEN=your_app_token

# Security Settings
BLOG_STAGE_ROOT=/app/data/blog/stage
BLOG_PUBLISH_ROOT=/app/data/blog/public
OUTPUT_TRUNCATE_LIMIT=10240

# Logging
LOG_LEVEL=INFO
AUDIT_LOG_PATH=/var/log/agentops/audit.jsonl
```

### Policy Configuration

Edit `policy/tools.yaml` to customize available tools and their security constraints:

```yaml
tools:
  docker_ps:
    description: "List Docker containers"
    timeout_sec: 30
    notify: ["failure"]
  
  custom_tool:
    description: "Your custom tool"
    args_schema:
      type: "object"
      properties:
        param: {"type": "string"}
    command: ["your-command", "{param}"]
    mutates: false
    requires_confirm: false
```

## Development

### Local Development Setup

```bash
# Install Python dependencies
pip install -e ".[dev]"

# Run tests
pytest

# Run with coverage
pytest --cov=server

# Format code
black server/ tests/
isort server/ tests/

# Type checking
mypy server/
```

### Core Dependencies

The Burly MCP server requires these Python packages:

**Runtime Dependencies:**
- `pydantic>=2.5.0` - Data validation and settings management
- `pyyaml>=6.0.1` - YAML parsing for policy configuration
- `jsonschema>=4.20.0` - JSON Schema validation for tool arguments
- `requests>=2.31.0` - HTTP client for Gotify notifications
- `docker>=7.0.0` - Docker API client for container operations

**Development Dependencies:**
- `pytest>=7.4.0` - Testing framework
- `pytest-cov>=4.1.0` - Test coverage reporting
- `pytest-asyncio>=0.21.0` - Async testing support
- `black>=23.0.0` - Code formatting
- `isort>=5.12.0` - Import sorting
- `flake8>=6.0.0` - Linting
- `mypy>=1.7.0` - Static type checking
- `pre-commit>=3.5.0` - Git hooks for code quality

All dependencies are automatically installed with `pip install -e ".[dev]"`

### Security Validation

Run security checks before committing code:

```bash
# Check for secrets and credentials
gitleaks detect --source . --verbose

# Scan for vulnerabilities
trivy filesystem .

# Check Python dependencies (if using npm for tooling)
npm audit --production-only

# Validate Python syntax and imports
python -m py_compile server/*.py
```

These security checks help ensure:
- No secrets are accidentally committed
- Dependencies don't have known vulnerabilities  
- Code follows security best practices
- All imports and syntax are valid

### Adding New Tools

1. Define the tool in `policy/tools.yaml`
2. Implement the tool function in `server/tools.py`
3. Add tests in `tests/test_tools.py`
4. Update documentation

See [docs/config.md](docs/config.md) for detailed configuration options.

## Architecture

```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│   Open WebUI    │    │   Burly MCP      │    │  System Tools   │
│                 │◄──►│     Server       │◄──►│                 │
│  AI Assistant   │    │                  │    │ Docker, Files,  │
│                 │    │  Policy Engine   │    │ Notifications   │
└─────────────────┘    └──────────────────┘    └─────────────────┘
                              │
                              ▼
                       ┌──────────────┐
                       │ Audit Logs   │
                       │ (JSON Lines) │
                       └──────────────┘
```

## Documentation

- [📖 Complete Configuration Guide](docs/config.md)
- [🔒 Security Model and Threat Analysis](docs/security.md)
- [🚀 Deployment and Operations](docs/runbook.md)
- [🤖 Open WebUI Integration](docs/open-webui.md)
- [📚 Understanding MCP Protocol](docs/mcp-explained.md)

## Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Make your changes with tests
4. Run the test suite (`pytest`)
5. Commit your changes (`git commit -m 'Add amazing feature'`)
6. Push to the branch (`git push origin feature/amazing-feature`)
7. Open a Pull Request

### Development Guidelines

- All new tools must include comprehensive tests
- Security implications must be documented
- Follow the existing code style (Black + isort)
- Update documentation for user-facing changes
- Run security validation before submitting PRs:
  ```bash
  # Required security checks
  gitleaks detect --source .
  trivy filesystem .
  python -m py_compile server/*.py
  ```

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Troubleshooting

### Security Tools Not Found

If you encounter "command not found" errors for security tools:

```bash
# Ubuntu/Debian
sudo apt update
sudo apt install gitleaks
sudo snap install trivy

# macOS
brew install gitleaks trivy

# Windows (with Chocolatey)
choco install gitleaks trivy

# Alternative: Use Docker versions
docker run --rm -v $(pwd):/src zricethezav/gitleaks:latest detect --source /src
docker run --rm -v $(pwd):/src aquasec/trivy:latest filesystem /src
```

### Python Environment Issues

```bash
# If pip install fails, try:
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"

# For permission issues:
python -m pip install --user -e ".[dev]"
```

## Support and Community

- 🐛 **Issues**: [GitHub Issues](https://github.com/your-org/burly-mcp/issues)
- 💬 **Discussions**: [GitHub Discussions](https://github.com/your-org/burly-mcp/discussions)
- 📧 **Security**: Report security issues privately to security@example.com

## Acknowledgments

- Built on the [Model Context Protocol](https://modelcontextprotocol.io/) specification
- Inspired by the need for secure AI-system integration
- Thanks to the open source community for tools and libraries

---

**⚡ Ready to give your AI assistant superpowers? Get started with Burly MCP today!**