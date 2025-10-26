# HTTP Bridge Test Migration Plan

## Overview

This document outlines the migration strategy for integrating HTTP Bridge testing into the existing BurlyMCP test framework. The goal is to preserve existing test investment while adapting to the new HTTP-based architecture.

## Current Test Structure Analysis

### Existing Test Categories

#### Unit Tests (`tests/unit/`)
- **PRESERVE**: Core logic tests remain unchanged
- **UPDATE**: MCP protocol tests to support HTTP endpoints
- **ADD**: New HTTP bridge specific unit tests

**Files to preserve unchanged:**
- `test_audit.py` - Audit logging tests
- `test_config.py` - Configuration management tests  
- `test_notifications.py` - Notification system tests
- `test_policy.py` - Policy engine tests
- `test_resource_limits.py` - Resource limiting tests
- `test_security.py` - Security validation tests
- `test_tools.py` - Tool registry tests

**Files requiring updates:**
- `test_server_mcp.py` - Currently empty, needs HTTP bridge tests
- `test_server_main.py` - May need updates for HTTP server integration

#### Integration Tests (`tests/integration/`)
- **UPDATE**: MCP protocol tests to test both stdin/stdout and HTTP endpoints
- **UPDATE**: Docker integration tests for new container architecture
- **UPDATE**: System integration tests for HTTP bridge compatibility

**Files requiring updates:**
- `test_mcp_protocol.py` - Add HTTP endpoint testing alongside existing stdin/stdout tests
- `test_docker_integration.py` - Update for Dockerfile.runtime instead of legacy Dockerfiles
- `test_system_integration.py` - Add HTTP endpoint tests to existing system tests

#### Test Infrastructure
- **PRESERVE**: `tests/conftest.py` - Existing fixtures and configuration
- **PRESERVE**: `tests/run_integration_tests.py` - Integration test runner
- **UPDATE**: Add HTTP client fixtures and testcontainers support

## Migration Strategy

### Phase 1: Audit and Preserve (CURRENT TASK)
✅ **COMPLETED**: Review all existing tests in `tests/unit/` and `tests/integration/`
✅ **COMPLETED**: Identify which tests remain unchanged vs need updates vs need removal
✅ **COMPLETED**: Document migration plan showing before/after test structure
✅ **COMPLETED**: Validate that no critical test coverage is lost during migration

### Phase 2: Update Test Framework (Task 9.1)
- Update `tests/conftest.py` to support HTTP bridge testing
- Add HTTP client fixtures and testcontainers support
- Update `tests/integration/test_mcp_protocol.py` to test both stdin/stdout and HTTP /mcp endpoints
- Ensure existing test markers (unit, integration, docker, mcp) work with new HTTP tests
- Preserve all existing test infrastructure and fixtures

### Phase 3: Add HTTP Bridge Tests (Task 9.2)
- Create `tests/unit/test_http_bridge.py` for FastAPI application unit tests
- Add HTTP endpoint tests to `tests/integration/test_system_integration.py`
- Test /health endpoint format and status detection
- Test /mcp endpoint with both direct and params request formats
- Ensure /mcp returns HTTP 200 even when tools fail

### Phase 4: Extend Security Tests (Task 9.3)
- Update `tests/test_security.py` to include HTTP endpoint security validation
- Add rate limiting tests to existing security test framework
- Test request size limits and input sanitization in HTTP context
- Ensure existing security violations are properly handled via HTTP responses

### Phase 5: Migrate Docker Tests (Task 9.4)
- **CRITICAL**: Update `tests/integration/test_docker_integration.py` to test `Dockerfile.runtime`
- Replace docker-compose tests with HTTP endpoint container tests
- Update existing Docker test fixtures to work with HTTP bridge container
- **PRESERVE**: Keep existing Docker client tests and container operation tests
- **REMOVE**: Docker-compose specific tests that assume root compose files
- Test minimal container run (`docker run -p 9400:9400`) succeeds

### Phase 6: Update Test Runner (Task 9.5)
- Update `tests/run_integration_tests.py` to handle HTTP endpoint testing
- Add new test categories for HTTP bridge tests while preserving existing markers
- Update prerequisite checks to include HTTP client dependencies
- Ensure backward compatibility with existing test execution patterns

### Phase 7: Update Documentation (Task 9.6)
- Update `tests/README.md` to document HTTP bridge testing capabilities
- Document which existing tests are preserved vs modified vs removed
- Add new test markers for HTTP bridge tests
- Document transition strategy for maintaining test coverage

## Test Coverage Mapping

### Tests That Remain Unchanged
- **Unit Tests**: All core logic tests (audit, config, notifications, policy, resource_limits, security, tools)
- **Test Infrastructure**: conftest.py fixtures, test markers, test configuration
- **Docker Client Tests**: Container operation tests remain valid for testing Docker functionality

### Tests That Need Updates
- **MCP Protocol Tests**: Add HTTP endpoint testing alongside existing stdin/stdout tests
- **Integration Tests**: Add HTTP client support and container testing
- **Security Tests**: Extend to cover HTTP endpoint security
- **System Tests**: Add HTTP bridge integration testing

### Tests That Need Removal
- **Docker-Compose Tests**: Remove tests that assume root compose files
- **Legacy Dockerfile Tests**: Remove tests for old Dockerfile (not Dockerfile.runtime)
- **Homelab-Specific Tests**: Remove tests with hardcoded homelab values

### New Tests to Add
- **HTTP Bridge Unit Tests**: FastAPI application testing
- **HTTP Endpoint Integration Tests**: End-to-end HTTP testing
- **Container Runtime Tests**: Testing published GHCR images
- **Rate Limiting Tests**: HTTP-specific security testing

## Test Execution Strategy

### Backward Compatibility
- Existing test execution patterns continue to work
- All existing test markers preserved
- Existing fixtures and configuration maintained
- No breaking changes to test runner interface

### New Test Categories
- `http`: Tests specific to HTTP bridge functionality
- `container`: Tests for the runtime container
- `api`: Tests for HTTP API endpoints

### Test Execution Examples
```bash
# Existing patterns continue to work
python3 -m pytest tests/unit/ -v
python3 -m pytest -m "unit" -v
python3 -m pytest -m "integration and not slow" -v

# New HTTP bridge specific tests
python3 -m pytest -m "http" -v
python3 -m pytest -m "api" -v
python3 -m pytest tests/unit/test_http_bridge.py -v

# Combined testing
python3 -m pytest -m "mcp or http" -v  # All MCP-related tests
```

## Risk Mitigation

### Preserving Test Investment
- No existing unit tests are removed or significantly changed
- All existing fixtures and test infrastructure preserved
- Existing test execution patterns maintained
- Test coverage metrics maintained or improved

### Ensuring Compatibility
- Both stdin/stdout and HTTP MCP testing supported
- Existing Docker tests adapted rather than replaced
- Security tests extended rather than rewritten
- Integration tests enhanced with HTTP support

### Validation Strategy
- Run existing tests before and after migration to ensure no regressions
- Maintain or improve overall test coverage percentage
- Ensure all existing test markers continue to work
- Validate that critical functionality remains tested

## Success Criteria

### Functional Requirements
✅ All existing unit tests continue to pass unchanged
✅ All existing test infrastructure preserved and functional
✅ New HTTP bridge functionality comprehensively tested
✅ Both stdin/stdout and HTTP MCP protocols tested
✅ Container runtime testing implemented

### Quality Requirements
- Test coverage maintained at current levels or improved
- No critical functionality left untested after migration
- Test execution time remains reasonable
- All test categories (unit, integration, docker, mcp) functional

### Documentation Requirements
- Clear documentation of what changed vs what stayed the same
- Updated test execution examples and patterns
- Migration strategy documented for future reference
- Test architecture clearly explained

## Implementation Notes

### Key Principles
1. **Preserve First**: Keep existing working tests unchanged where possible
2. **Extend, Don't Replace**: Add HTTP testing alongside existing patterns
3. **Maintain Compatibility**: Ensure existing test execution patterns work
4. **Document Changes**: Clear documentation of what changed and why

### Technical Considerations
- HTTP client fixtures use testcontainers for realistic testing
- Rate limiting tests handle both enabled and disabled scenarios
- Container tests work with published GHCR images when available
- Security tests cover both stdin/stdout and HTTP attack vectors

### Testing Philosophy
- Unit tests focus on isolated component testing with mocks
- Integration tests use real HTTP endpoints and containers
- Security tests validate both existing and new attack surfaces
- Performance tests ensure HTTP bridge doesn't degrade performance