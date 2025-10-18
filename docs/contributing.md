# Contributing to Burly MCP

Thank you for your interest in contributing to Burly MCP! This guide will help you get started with development and ensure your contributions align with our security-first approach.

## Development Setup

### Prerequisites

- Python 3.12 or higher
- Docker and Docker Compose
- Git

### Local Development Environment

1. **Clone the repository**
   ```bash
   git clone <repository-url>
   cd burly-mcp
   ```

2. **Set up Python virtual environment**
   ```bash
   python -m venv .venv
   source .venv/bin/activate  # On Windows: .venv\Scripts\activate
   ```

3. **Install development dependencies**
   ```bash
   pip install -e .[dev]
   ```

4. **Install pre-commit hooks**
   ```bash
   pre-commit install
   ```

5. **Run tests to verify setup**
   ```bash
   pytest
   ```

## Code Style Guidelines

### Python Code Standards

- **PEP 8 Compliance**: All code must follow PEP 8 style guidelines
- **Type Hints**: Use type hints for all function parameters and return values
- **Docstrings**: Use Google-style docstrings for all public functions and classes
- **Black Formatting**: Code is automatically formatted with Black (line length: 88)
- **Import Organization**: Use isort for consistent import ordering

### Security Guidelines

- **Input Validation**: All user inputs must be validated against JSON schemas
- **Path Traversal Prevention**: Validate all file paths to prevent directory traversal
- **Secret Management**: Never hardcode secrets; use environment variables or Docker secrets
- **Audit Logging**: Log all security-relevant operations
- **Least Privilege**: Grant minimal necessary permissions

## Testing Requirements

### Test Coverage

- **Minimum Coverage**: 80% test coverage required for all new code
- **Unit Tests**: Test individual functions and classes in isolation
- **Integration Tests**: Test component interactions and external dependencies
- **Security Tests**: Include tests for security boundaries and validation

### Test Structure

```
tests/
├── unit/
│   ├── test_server/
│   ├── test_tools/
│   ├── test_policy/
│   └── test_notifications/
├── integration/
│   ├── test_docker_integration.py
│   └── test_mcp_protocol.py
└── conftest.py
```

### Running Tests

```bash
# Run all tests with coverage
pytest --cov=burly_mcp --cov-report=html --cov-report=term

# Run specific test categories
pytest tests/unit/          # Unit tests only
pytest tests/integration/   # Integration tests only

# Run with Docker containers
docker-compose -f docker/docker-compose.test.yml up --build --abort-on-container-exit
```

## Pull Request Process

### Before Submitting

1. **Run the full test suite**
   ```bash
   pytest --cov=burly_mcp --cov-fail-under=80
   ```

2. **Run security checks**
   ```bash
   bandit -r src/
   pip-audit --desc
   ```

3. **Run linting**
   ```bash
   flake8 src/ tests/
   pylint src/
   ```

4. **Format code**
   ```bash
   black src/ tests/
   isort src/ tests/
   ```

### Pull Request Guidelines

- **Branch Naming**: Use descriptive branch names (e.g., `feature/add-docker-tool`, `fix/security-validation`)
- **Commit Messages**: Use conventional commit format (`feat:`, `fix:`, `docs:`, `test:`, etc.)
- **Description**: Provide clear description of changes and motivation
- **Testing**: Include tests for new functionality and bug fixes
- **Documentation**: Update documentation for API changes or new features

### Review Process

1. **Automated Checks**: All CI checks must pass
2. **Security Review**: Security-related changes require additional review
3. **Code Review**: At least one maintainer approval required
4. **Testing**: Verify tests cover new functionality adequately

## Issue Tracking and Labels

### Issue Types

- **bug**: Something isn't working correctly
- **enhancement**: New feature or improvement
- **security**: Security-related issue or improvement
- **documentation**: Documentation improvements
- **testing**: Test-related improvements

### Priority Labels

- **critical**: Security vulnerabilities or system-breaking issues
- **high**: Important features or significant bugs
- **medium**: Standard features and improvements
- **low**: Nice-to-have features or minor issues

### Status Labels

- **needs-triage**: New issue requiring initial review
- **ready**: Issue is well-defined and ready for implementation
- **in-progress**: Someone is actively working on the issue
- **blocked**: Issue is blocked by external dependency

## Security Considerations

### Reporting Security Issues

- **Private Disclosure**: Report security vulnerabilities privately via email
- **No Public Issues**: Do not create public GitHub issues for security problems
- **Response Time**: We aim to respond to security reports within 24 hours

### Security Review Requirements

- **Threat Modeling**: Consider security implications of all changes
- **Input Validation**: Validate all external inputs
- **Access Controls**: Ensure proper authorization checks
- **Audit Logging**: Log security-relevant operations
- **Dependency Updates**: Keep dependencies updated for security patches

## Development Workflow

### Branching Strategy

- **main**: Production-ready code
- **develop**: Integration branch for features
- **feature/***: Individual feature branches
- **hotfix/***: Critical bug fixes
- **release/***: Release preparation branches

### Release Process

1. **Version Bumping**: Use semantic versioning (MAJOR.MINOR.PATCH)
2. **Changelog**: Update CHANGELOG.md with release notes
3. **Testing**: Full test suite including security scans
4. **Tagging**: Create Git tags for releases
5. **Distribution**: Automated publishing to PyPI and Docker Hub

## Getting Help

### Communication Channels

- **GitHub Issues**: For bug reports and feature requests
- **GitHub Discussions**: For questions and general discussion
- **Security Email**: For private security vulnerability reports

### Documentation

- **API Documentation**: Auto-generated from code annotations
- **Architecture Docs**: High-level system design and decisions
- **Security Docs**: Security architecture and threat model
- **Deployment Docs**: Production deployment and operations

## Code of Conduct

We are committed to providing a welcoming and inclusive environment for all contributors. Please be respectful and professional in all interactions.

### Expected Behavior

- Use welcoming and inclusive language
- Be respectful of differing viewpoints and experiences
- Gracefully accept constructive criticism
- Focus on what is best for the community
- Show empathy towards other community members

Thank you for contributing to Burly MCP!