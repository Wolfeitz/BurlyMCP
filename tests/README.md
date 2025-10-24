# Burly MCP Testing Framework

This document describes the comprehensive testing framework implemented for the Burly MCP project.

## Overview

The testing framework provides:
- **Unit Tests**: Fast, isolated tests with comprehensive mocking
- **Integration Tests**: End-to-end tests with Docker containers and real services
- **Test Configuration**: Centralized configuration with pytest
- **Test Fixtures**: Reusable test data and mock objects
- **Test Markers**: Organized test categorization and selective execution

## Directory Structure

```
tests/
├── conftest.py                     # Global test configuration and fixtures
├── README.md                       # This documentation
├── run_integration_tests.py        # Integration test runner script
├── unit/                          # Unit tests
│   ├── test_audit.py              # Audit logging tests
│   ├── test_config.py             # Configuration management tests
│   ├── test_framework_verification.py  # Framework verification tests
│   ├── test_notifications.py      # Notification system tests
│   ├── test_policy.py             # Policy engine tests
│   ├── test_resource_limits.py    # Resource limiting tests
│   ├── test_security.py           # Security validation tests
│   ├── test_server.py             # Server component tests
│   └── test_tools.py              # Tool registry tests
└── integration/                   # Integration tests
    ├── conftest.py                # Integration test configuration
    ├── test_docker_integration.py # Docker integration tests
    ├── test_mcp_protocol.py       # MCP protocol tests
    └── test_system_integration.py # System-wide integration tests
```

## Test Categories

### Unit Tests (`tests/unit/`)

Unit tests focus on individual components in isolation:

- **Fast execution** (< 1 second per test)
- **Comprehensive mocking** of external dependencies
- **High code coverage** targeting 80%+ coverage
- **No external dependencies** (Docker, network, filesystem)

**Markers**: `@pytest.mark.unit`

### Integration Tests (`tests/integration/`)

Integration tests verify component interactions:

- **Real dependencies** (Docker containers, test services)
- **End-to-end workflows** (MCP protocol, tool execution)
- **System behavior** under realistic conditions
- **Performance validation** and resource usage

**Markers**: `@pytest.mark.integration`, `@pytest.mark.docker`, `@pytest.mark.mcp`, `@pytest.mark.slow`

## Running Tests

### Basic Usage

```bash
# Run all unit tests
python3 -m pytest tests/unit/ -v

# Run all tests with coverage
python3 -m pytest --cov=burly_mcp --cov-report=html

# Run specific test file
python3 -m pytest tests/unit/test_config.py -v

# Run specific test function
python3 -m pytest tests/unit/test_config.py::TestConfig::test_config_defaults -v
```

### Using Test Markers

```bash
# Run only unit tests
python3 -m pytest -m "unit" -v

# Run integration tests (excluding slow ones)
python3 -m pytest -m "integration and not slow" -v

# Run Docker-related tests
python3 -m pytest -m "docker" -v

# Run MCP protocol tests
python3 -m pytest -m "mcp" -v
```

### Integration Test Runner

Use the dedicated integration test runner for advanced options:

```bash
# Run all integration tests
python3 tests/run_integration_tests.py

# Skip Docker tests
python3 tests/run_integration_tests.py --no-docker

# Skip slow tests
python3 tests/run_integration_tests.py --no-slow

# Run only MCP protocol tests
python3 tests/run_integration_tests.py --only-mcp

# Run with coverage
python3 tests/run_integration_tests.py --coverage

# Run in parallel
python3 tests/run_integration_tests.py --parallel 4
```

## Test Configuration

### pytest Configuration (`pyproject.toml`)

```toml
[tool.pytest.ini_options]
testpaths = ["tests"]
python_files = ["test_*.py"]
python_classes = ["Test*"]
python_functions = ["test_*"]
addopts = [
    "--strict-markers",
    "--strict-config",
    "-ra",
]
markers = [
    "unit: Unit tests that don't require external dependencies",
    "integration: Integration tests that may require Docker or external services",
    "docker: Tests that require Docker to be available",
    "slow: Tests that take longer than usual to run",
    "security: Security-focused tests",
    "mcp: Tests related to MCP protocol functionality",
]
```

### Global Fixtures (`tests/conftest.py`)

Key fixtures available to all tests:

- `temp_dir`: Temporary directory for test files
- `mock_config`: Mock configuration with environment variables
- `mock_docker_client`: Mock Docker client for unit tests
- `sample_blog_post`: Sample blog post content
- `sample_mcp_request`: Sample MCP request data
- `policy_config_dir`: Temporary policy configuration directory

### Integration Test Fixtures (`tests/integration/conftest.py`)

Additional fixtures for integration tests:

- `docker_client`: Real Docker client (requires Docker)
- `integration_test_config`: Complete test configuration
- `clean_docker_environment`: Ensures clean Docker state
- `performance_monitor`: Monitors test performance metrics

## Test Data and Mocking

### Mock Objects

The framework provides comprehensive mocking for:

- **Docker Client**: Mock container operations, image management
- **Configuration**: Mock environment variables and settings
- **Audit Logging**: Mock audit events and logging
- **Notifications**: Mock notification delivery
- **External Services**: Mock HTTP services and APIs

### Test Data

Predefined test data includes:

- Sample blog posts (valid and invalid)
- MCP request/response examples
- Policy configuration templates
- Docker container configurations
- Security test scenarios

## Prerequisites

### Required Dependencies

```bash
# Core testing
pip install pytest pytest-cov pytest-mock

# Integration testing
pip install testcontainers docker

# Optional: Parallel execution
pip install pytest-xdist

# Optional: Async testing
pip install pytest-asyncio
```

### System Requirements

- **Python 3.12+**
- **Docker** (for integration tests)
- **Git** (for repository operations)

### Environment Setup

```bash
# Install in development mode
pip install -e .[dev,test]

# Verify installation
python3 tests/run_integration_tests.py --check-only
```

## Coverage Reporting

### Generate Coverage Reports

```bash
# HTML report
python3 -m pytest --cov=burly_mcp --cov-report=html

# XML report (for CI/CD)
python3 -m pytest --cov=burly_mcp --cov-report=xml

# Terminal report
python3 -m pytest --cov=burly_mcp --cov-report=term-missing
```

### Coverage Targets

- **Unit Tests**: 80%+ line coverage
- **Integration Tests**: Focus on critical paths
- **Combined**: 85%+ overall coverage

## Continuous Integration

### GitHub Actions Integration

The testing framework integrates with CI/CD pipelines:

```yaml
- name: Run Unit Tests
  run: python3 -m pytest tests/unit/ --cov=burly_mcp --cov-report=xml

- name: Run Integration Tests
  run: python3 tests/run_integration_tests.py --no-slow

- name: Upload Coverage
  uses: codecov/codecov-action@v4
  with:
    file: ./coverage.xml
```

### Test Isolation

Tests are isolated through:

- **Temporary directories** for file operations
- **Mock objects** for external dependencies
- **Environment variable** isolation
- **Docker container** cleanup
- **Process management** for server tests

## Best Practices

### Writing Unit Tests

1. **Test one thing** per test function
2. **Use descriptive names** that explain the scenario
3. **Mock external dependencies** completely
4. **Test both success and failure** cases
5. **Use fixtures** for common test data

### Writing Integration Tests

1. **Test realistic scenarios** end-to-end
2. **Use test containers** for external services
3. **Clean up resources** after tests
4. **Handle timeouts** appropriately
5. **Test error conditions** and recovery

### Test Organization

1. **Group related tests** in classes
2. **Use consistent naming** conventions
3. **Add appropriate markers** for categorization
4. **Document complex test** scenarios
5. **Keep tests independent** and isolated

## Troubleshooting

### Common Issues

**Docker not available:**
```bash
# Check Docker status
docker version

# Start Docker service
sudo systemctl start docker
```

**Module import errors:**
```bash
# Install in development mode
pip install -e .

# Set PYTHONPATH
export PYTHONPATH=src:$PYTHONPATH
```

**Permission errors:**
```bash
# Fix test directory permissions
chmod -R 755 tests/

# Use temporary directories
pytest --basetemp=/tmp/pytest
```

### Debug Mode

```bash
# Verbose output
python3 -m pytest -v -s

# Debug specific test
python3 -m pytest tests/unit/test_config.py::TestConfig::test_config_defaults -v -s --pdb

# Show local variables on failure
python3 -m pytest --tb=long -v
```

## Contributing

When adding new tests:

1. **Follow naming conventions** (`test_*.py`, `Test*`, `test_*`)
2. **Add appropriate markers** for categorization
3. **Update documentation** for new test categories
4. **Ensure tests are isolated** and repeatable
5. **Add fixtures** for reusable test data

For more information, see the [Contributing Guide](../docs/contributing.md).