# Contributing to Burly MCP

Thank you for your interest in contributing to Burly MCP! This document provides guidelines and instructions for contributing to the project.

## Table of Contents

- [Development Setup](#development-setup)
- [Code Style Guidelines](#code-style-guidelines)
- [Testing Requirements](#testing-requirements)
- [Security Guidelines](#security-guidelines)
- [Pull Request Process](#pull-request-process)
- [Issue Reporting](#issue-reporting)

## Development Setup

### Prerequisites

- Python 3.12 or higher
- Docker and Docker Compose
- Git

### Local Development Environment

1. **Clone the repository:**
   ```bash
   git clone https://github.com/Wolfeitz/BurlyMCP.git
   cd BurlyMCP
   ```

2. **Create and activate a virtual environment:**
   ```bash
   python -m venv .venv
   source .venv/bin/activate  # On Windows: .venv\Scripts\activate
   ```

3. **Install development dependencies:**
   ```bash
   pip install -e .[dev,test,docs]
   ```

4. **Set up pre-commit hooks:**
   ```bash
   pre-commit install
   ```

5. **Copy environment configuration:**
   ```bash
   cp .env.example .env
   # Edit .env with your local configuration
   ```

6. **Run tests to verify setup:**
   ```bash
   pytest tests/unit/ -v
   ```

### Docker Development

1. **Build the development image:**
   ```bash
   docker-compose build
   ```

2. **Run the development environment:**
   ```bash
   docker-compose up -d
   ```

3. **Run tests in Docker:**
   ```bash
   docker-compose exec burly-mcp pytest tests/ -v
   ```

## Code Style Guidelines

### Python Code Style

- **Formatter**: Use `black` with line length 88
- **Linter**: Use `flake8` with project configuration
- **Type Hints**: All public functions must have type hints
- **Docstrings**: Use Google-style docstrings for all public functions and classes

### Code Formatting

Run formatting tools before committing:

```bash
# Format code
black src/ tests/

# Check linting
flake8 src/ tests/

# Type checking
mypy src/
```

### Import Organization

- Standard library imports first
- Third-party imports second
- Local imports last
- Use absolute imports for internal modules

Example:
```python
import os
import sys
from pathlib import Path

import docker
import yaml
from pydantic import BaseModel

from burly_mcp.security import SecurityValidator
from burly_mcp.audit import log_tool_execution
```

### Security Code Guidelines

- **Input Validation**: All external inputs must be validated
- **Path Operations**: Use `validate_path_within_root()` for all file operations
- **Command Execution**: Use `sanitize_command_args()` before shell execution
- **Secrets**: Never log or expose sensitive information
- **Error Handling**: Fail securely and log security events

## Testing Requirements

### Test Coverage

- Minimum 80% code coverage required
- All new features must include comprehensive tests
- Security-critical code requires 100% coverage

### Test Types

1. **Unit Tests** (`tests/unit/`):
   - Test individual functions and classes
   - Use mocking for external dependencies
   - Fast execution (< 1 second per test)

2. **Integration Tests** (`tests/integration/`):
   - Test component interactions
   - Use test containers for external services
   - Moderate execution time (< 30 seconds per test)

3. **Security Tests**:
   - Test security boundaries and validation
   - Include negative test cases for attacks
   - Test error handling and fail-safe behavior

### Running Tests

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=burly_mcp --cov-report=html

# Run specific test categories
pytest tests/unit/ -m "not integration"
pytest tests/integration/ -m integration

# Run security tests
pytest tests/ -m security
```

### Test Markers

Use pytest markers to categorize tests:

```python
@pytest.mark.unit
def test_security_validator():
    pass

@pytest.mark.integration
def test_docker_integration():
    pass

@pytest.mark.security
def test_path_traversal_protection():
    pass
```

## Security Guidelines

### Security Review Process

All code changes undergo security review:

1. **Automated Security Scanning**: 
   - Bandit for Python security issues
   - pip-audit for dependency vulnerabilities
   - Trivy for Docker image scanning

2. **Manual Security Review**:
   - Path traversal protection
   - Input validation completeness
   - Secret handling
   - Error message information disclosure

### Security Testing

- Include attack scenarios in tests
- Test boundary conditions and edge cases
- Verify fail-safe behavior
- Test with malicious inputs

### Vulnerability Reporting

Report security vulnerabilities privately to: security@burly-mcp.dev

Do not create public issues for security vulnerabilities.

## Pull Request Process

### Before Submitting

1. **Create a feature branch:**
   ```bash
   git checkout -b feature/your-feature-name
   ```

2. **Make your changes with tests:**
   - Write code following style guidelines
   - Add comprehensive tests
   - Update documentation if needed

3. **Run the full test suite:**
   ```bash
   pytest tests/ --cov=burly_mcp
   black src/ tests/
   flake8 src/ tests/
   mypy src/
   ```

4. **Run security scans:**
   ```bash
   bandit -r src/
   pip-audit
   ```

### Pull Request Requirements

- **Title**: Clear, descriptive title
- **Description**: Explain what changes were made and why
- **Tests**: Include tests for new functionality
- **Documentation**: Update docs for user-facing changes
- **Security**: Address any security implications

### Pull Request Template

```markdown
## Description
Brief description of changes

## Type of Change
- [ ] Bug fix
- [ ] New feature
- [ ] Breaking change
- [ ] Documentation update
- [ ] Security fix

## Testing
- [ ] Unit tests pass
- [ ] Integration tests pass
- [ ] Security tests pass
- [ ] Manual testing completed

## Security Checklist
- [ ] Input validation added/updated
- [ ] Path operations use security functions
- [ ] No secrets in code or logs
- [ ] Error handling is secure

## Documentation
- [ ] Code comments updated
- [ ] API documentation updated
- [ ] User documentation updated
```

### Review Process

1. **Automated Checks**: CI/CD pipeline runs all tests and security scans
2. **Code Review**: At least one maintainer reviews the code
3. **Security Review**: Security-sensitive changes get additional review
4. **Testing**: Reviewers may test changes locally
5. **Approval**: Changes are approved and merged

## Issue Reporting

### Bug Reports

Use the bug report template and include:

- **Environment**: OS, Python version, Docker version
- **Steps to Reproduce**: Clear, minimal reproduction steps
- **Expected Behavior**: What should happen
- **Actual Behavior**: What actually happens
- **Logs**: Relevant log output (redact sensitive information)

### Feature Requests

Use the feature request template and include:

- **Use Case**: Why is this feature needed?
- **Proposed Solution**: How should it work?
- **Alternatives**: Other approaches considered
- **Security Implications**: Any security considerations

### Security Issues

For security vulnerabilities:

1. **Do not create public issues**
2. **Email security@burly-mcp.dev**
3. **Include detailed reproduction steps**
4. **Allow time for coordinated disclosure**

## Development Workflow

### Branch Naming

- `feature/description` - New features
- `bugfix/description` - Bug fixes
- `security/description` - Security fixes
- `docs/description` - Documentation updates

### Commit Messages

Use conventional commit format:

```
type(scope): description

[optional body]

[optional footer]
```

Types:
- `feat`: New feature
- `fix`: Bug fix
- `docs`: Documentation
- `style`: Code style changes
- `refactor`: Code refactoring
- `test`: Test changes
- `security`: Security fixes

Examples:
```
feat(tools): add Docker container monitoring tool
fix(security): prevent path traversal in file operations
docs(api): update security configuration examples
```

### Release Process

1. **Version Bumping**: Use semantic versioning (MAJOR.MINOR.PATCH)
2. **Changelog**: Update CHANGELOG.md with changes
3. **Testing**: Full test suite including security scans
4. **Documentation**: Update version-specific documentation
5. **Release**: Create GitHub release with artifacts

## Getting Help

- **Documentation**: Check the [docs](docs/) directory
- **Discussions**: Use GitHub Discussions for questions
- **Issues**: Create issues for bugs and feature requests
- **Chat**: Join our community chat (link in README)

## Code of Conduct

This project follows the [Contributor Covenant Code of Conduct](CODE_OF_CONDUCT.md). By participating, you agree to uphold this code.

## License

By contributing to Burly MCP, you agree that your contributions will be licensed under the MIT License.