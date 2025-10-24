# Burly MCP Documentation

This directory contains comprehensive documentation for the Burly MCP server.

## Documentation Structure

- [`api/`](api/) - API documentation and specifications
- [`contributing/`](contributing/) - Contributor guidelines and development docs
- [`security/`](security/) - Security documentation and threat model

## Quick Start

For quick setup instructions, see the main [README.md](../README.md) in the project root.

## Documentation Categories

### API Documentation
- MCP Protocol implementation details
- Tool schemas and specifications
- Response format documentation

### Contributing
- Development environment setup
- Code style guidelines
- Testing procedures
- Pull request process

### Security
- Security architecture overview
- Threat model and mitigations
- Security best practices
- Vulnerability reporting

### Deployment and Operations
- [`operations.md`](operations.md) - **Complete operations guide** - Central reference for production operations
- [`deployment.md`](deployment.md) - Comprehensive deployment guide for all environments
- [`config.md`](config.md) - Complete configuration reference and examples
- [`runbook.md`](runbook.md) - Operational runbook and quick start guide
- [`troubleshooting.md`](troubleshooting.md) - Systematic troubleshooting guide
- [`monitoring.md`](monitoring.md) - Monitoring, logging, and observability setup

## Building Documentation

Documentation can be built using Sphinx (when configured):

```bash
# Install documentation dependencies
pip install -e ".[dev]"

# Build documentation
sphinx-build -b html docs/ docs/_build/
```