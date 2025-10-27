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
├── HTTP_BRIDGE_TEST_MIGRATION_PLAN.md  # Migration plan documentation
├── unit/                          # Unit tests
│   ├── test_audit.py              # Audit logging tests
│   ├── test_config.py             # Configuration management tests
│   ├── test_framework_verification.py  # Framework verification tests
│   ├── test_http_bridge.py        # HTTP bridge FastAPI tests (NEW)
│   ├── test_notifications.py      # Notification system tests
│   ├── test_policy.py             # Policy engine tests
│   ├── test_resource_limits.py    # Resource limiting tests
│   ├── test_security.py           # Security validation tests (EXTENDED)
│   ├── test_server.py             # Server component tests
│   └── test_tools.py              # Tool registry tests
├── integration/                   # Integration tests
│   ├── conftest.py                # Integration test configuration
│   ├── test_docker_integration.py # Docker integration tests (UPDATED)
│   ├── test_mcp_protocol.py       # MCP protocol tests (EXTENDED)
│   └── test_system_integration.py # System-wide integration tests (EXTENDED)
└── test_security.py               # Root-level security tests (EXTENDED)
```

## Test Categories

### Unit Tests (`tests/unit/`)

Unit tests focus on individual components in isolation:

- **Fast execution** (< 1 second per test)
- **Comprehensive mocking** of external dependencies
- **High code coverage** targeting 80%+ coverage
- **No external dependencies** (Docker, network, filesystem)

**Markers**: `@pytest.mark.unit`

**New HTTP Bridge Tests**: `test_http_bridge.py` provides comprehensive unit testing for the FastAPI HTTP bridge, including request/response models, endpoint logic, and MCP engine integration (mocked).

### Integration Tests (`tests/integration/`)

Integration tests verify component interactions:

- **Real dependencies** (Docker containers, test services)
- **End-to-end workflows** (MCP protocol, tool execution, HTTP endpoints)
- **System behavior** under realistic conditions
- **Performance validation** and resource usage

**Markers**: `@pytest.mark.integration`, `@pytest.mark.docker`, `@pytest.mark.mcp`, `@pytest.mark.slow`

**Extended for HTTP Bridge**: Integration tests now include HTTP endpoint testing alongside existing stdin/stdout MCP protocol tests, ensuring compatibility during the transition to HTTP-based architecture.

### HTTP Bridge Tests (New Category)

HTTP bridge tests focus on the new HTTP API endpoints:

- **HTTP endpoint functionality** (/health and /mcp endpoints)
- **Request format compatibility** (direct and params formats)
- **API contract validation** (always HTTP 200 for /mcp)
- **Security measures** (rate limiting, input validation)

**Markers**: `@pytest.mark.http`, `@pytest.mark.api`

### Container Runtime Tests (New Category)

Container runtime tests validate the new standalone container:

- **Container build and startup** (Dockerfile.runtime)
- **Minimal configuration** (docker run -p 9400:9400)
- **Graceful degradation** (missing optional features)
- **Security posture** (non-root execution)

**Markers**: `@pytest.mark.container`

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

# Run MCP protocol tests (both stdin/stdout and HTTP)
python3 -m pytest -m "mcp" -v

# Run HTTP bridge tests
python3 -m pytest -m "http" -v

# Run API endpoint tests
python3 -m pytest -m "api" -v

# Run container runtime tests
python3 -m pytest -m "container" -v

# Run security tests (including HTTP bridge security)
python3 -m pytest -m "security" -v

# Combined testing patterns
python3 -m pytest -m "mcp or http" -v  # All MCP-related tests
python3 -m pytest -m "http and not slow" -v  # Fast HTTP tests only
python3 -m pytest -m "integration and http" -v  # HTTP integration tests
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

# Run only HTTP bridge tests
python3 tests/run_integration_tests.py --only-http

# Include container runtime tests
python3 tests/run_integration_tests.py --include-container

# Run with coverage
python3 tests/run_integration_tests.py --coverage

# Run in parallel
python3 tests/run_integration_tests.py --parallel 4
```

## HTTP Bridge Testing Migration

### What Changed

The BurlyMCP project has migrated from a docker-compose orchestrated application to a standalone service container with HTTP endpoints. This migration preserves all existing test investment while adding comprehensive HTTP bridge testing.

**Preserved Tests:**
- All unit tests remain unchanged (audit, config, notifications, policy, resource_limits, security, tools)
- All existing test infrastructure and fixtures maintained
- All existing test markers and execution patterns continue to work
- Docker client tests and container operation tests remain valid

**Extended Tests:**
- `test_mcp_protocol.py`: Added HTTP endpoint testing alongside existing stdin/stdout tests
- `test_security.py`: Extended with HTTP endpoint security validation
- `test_system_integration.py`: Added HTTP bridge integration testing
- `test_docker_integration.py`: Updated for Dockerfile.runtime instead of legacy Dockerfiles

**New Tests:**
- `test_http_bridge.py`: Comprehensive FastAPI application unit tests
- Container runtime tests for the new standalone container architecture
- HTTP-specific security tests (rate limiting, input validation, etc.)

**Removed Tests:**
- Docker-compose specific tests that assumed root compose files
- Legacy Dockerfile tests (replaced with Dockerfile.runtime tests)
- Homelab-specific tests with hardcoded values

### Migration Benefits

1. **Backward Compatibility**: All existing test execution patterns continue to work
2. **Enhanced Coverage**: Both stdin/stdout and HTTP MCP protocols are tested
3. **Security Focus**: Comprehensive HTTP endpoint security validation
4. **Container Testing**: Validation of the new runtime container architecture
5. **API Stability**: Tests ensure HTTP API contract stability across internal refactors

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
    "http: Tests for HTTP bridge functionality",  # NEW
    "api: Tests for HTTP API endpoints",          # NEW
    "container: Tests for runtime container",     # NEW
]
```

### Global Fixtures (`tests/conftest.py`)

Key fixtures available to all tests:

**Existing Fixtures (Preserved):**
- `temp_dir`: Temporary directory for test files
- `mock_config`: Mock configuration with environment variables
- `mock_docker_client`: Mock Docker client for unit tests
- `sample_blog_post`: Sample blog post content
- `sample_mcp_request`: Sample MCP request data
- `policy_config_dir`: Temporary policy configuration directory

**New HTTP Bridge Fixtures:**
- `http_client`: HTTP client session for testing HTTP endpoints
- `http_bridge_container`: Running HTTP bridge container for integration testing
- `sample_mcp_http_request`: Sample MCP HTTP request data
- `sample_mcp_call_tool_request`: Sample call_tool HTTP request (direct format)
- `sample_mcp_call_tool_params_request`: Sample call_tool HTTP request (params format)
- `mock_http_bridge_config`: Mock configuration for HTTP bridge testing
- `mock_mcp_engine_response`: Mock MCP engine response for testing
- `mock_mcp_engine_error_response`: Mock MCP engine error response for testing

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

# HTTP bridge testing (NEW)
pip install fastapi uvicorn requests

# Optional: Parallel execution
pip install pytest-xdist

# Optional: Async testing
pip install pytest-asyncio

# Install all test dependencies
pip install -e .[test]
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