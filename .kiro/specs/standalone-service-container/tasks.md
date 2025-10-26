# Implementation Plan

## Non-negotiable Contract

The Runtime Container MUST boot and serve /health and /mcp with a plain `docker run -p 9400:9400 ghcr.io/<org>/burlymcp:<tag>` and zero extra flags.

/mcp MUST always return 200 OK with a JSON envelope (ok, summary, error, etc.) even on failure or validation problems.

The HTTP contract MUST remain stable even if the internal MCP engine moves from a subprocess to in-process calls. Downstream systems (e.g. Open WebUI) MUST NOT have to change how they talk to /mcp.

Mutating tools MUST require _confirm: true and MUST NOT execute without it.

- [x] 1. Create HTTP Bridge and Core Infrastructure
- [x] 1.1 Create FastAPI HTTP bridge (http_bridge.py)
  - Implement FastAPI application with /health and /mcp endpoints
  - Add Pydantic models for MCPRequest, MCPResponse, and HealthResponse
  - Implement request format normalization (direct args vs params wrapper)
  - Ensure /mcp always returns HTTP 200 with structured JSON envelope
  - Add comprehensive error handling with structured responses
  - /mcp MUST respond with HTTP 200 in all cases. Errors/failures MUST be expressed in the response body (never via HTTP 4xx/5xx), so LLM clients do not need HTTP branching
  - The response body MUST include metrics.elapsed_ms and metrics.exit_code for every call, even failures, to support downstream audit/telemetry
  - _Requirements: 2.1, 2.2, 2.6, 2.7, 11.1_

- [x] 1.2 Implement MCP engine communication
  - Create subprocess communication with burly_mcp.server.main
  - Implement JSON request/response handling over stdin/stdout
  - Add timeout handling and process management
  - Implement graceful error handling for MCP engine failures
  - The bridge MUST isolate the MCP engine behind a single call boundary (forward_to_mcp_engine(normalized_request))
  - The bridge MUST treat the MCP engine as an interchangeable backend (today = subprocess that runs python -m ..., future = direct import). The HTTP schema MUST NOT depend on whether the engine runs as a subprocess
  - When spawning a subprocess, the bridge MUST sanitize the child environment. Sensitive env like GOTIFY_TOKEN MUST NOT be inherited. Non-sensitive env like HOME and USER MAY remain so libraries don't break
  - _Requirements: 2.4, 2.5, 11.1, 11.2_

- [x] 1.3 Create comprehensive health check endpoint
  - Implement health status detection (ok/degraded/error)
  - Add system feature detection (Docker, notifications, blog directories)
  - Include server metadata (name, version, policy_loaded, strict_security_mode)
  - Add uptime tracking and tool count reporting
  - Implement quick MCP engine health test
  - /health MUST include: server_name, version (aka server_version), policy_loaded, strict_security_mode, docker_available, notifications_enabled, and tools_available
  - /health MUST return status: "ok" only if MCP engine is callable AND policy loaded; otherwise MUST return "degraded". It MUST NOT return "error" unless the service is effectively unusable
  - _Requirements: 2.1, 4.1, 10.5, 12.6, 12.7_

- [x] 1.4 Define stable API schema contract
  - Document the exact request/response schema for /mcp and /health in the repo under docs/api-contract.md
  - Include examples for: list_tools, call_tool (direct form), call_tool (params form), mutating tool requiring _confirm, degraded docker tool response
  - This document MUST be treated as the external compatibility contract
  - _Requirements: 2.2, 2.6, 4.1, 11.1_

- [x] 2. Create Canonical Runtime Container (Dockerfile.runtime)
- [x] 2.1 Create base container structure
  - Use debian:trixie-slim as base image
  - Install system dependencies (python3, python3-venv, python3-pip, curl, ca-certificates)
  - Install Docker CLI only (not dockerd daemon) for optional Docker operations
  - Create virtual environment at /opt/venv with proper PATH configuration
  - The Runtime Container MUST NOT include or run a Docker daemon (dockerd). Only optional client capability is allowed. If the distro package pulls in dockerd, this is a failure
  - If there's no clean package name for "just docker client," then the tool SHOULD shell out to docker only if /var/run/docker.sock is mounted AND /usr/bin/docker exists; otherwise it must degrade
  - _Requirements: 1.1, 1.2, 8.1, 8.2_

- [x] 2.2 Set up application installation and configuration
  - Copy complete BurlyMCP source tree to /app/BurlyMCP
  - Install BurlyMCP package with pip install -e .
  - Copy http_bridge.py to /app/ and install FastAPI + uvicorn==0.30.6
  - Embed default policy file and configuration in container image
  - Create all required directories (/var/log/agentops, /app/data/blog/stage, /app/data/blog/publish)
  - The image MUST bake in a working default policy file at a known path (e.g. /app/BurlyMCP/config/policy/tools.yaml). Container startup MUST succeed if the operator does not mount a policy
  - The image MUST create /var/log/agentops and /app/data/blog/{stage,publish} at build time so startup doesn't die on missing dirs
  - _Requirements: 1.1, 1.6, 6.6, 12.4, 12.5_

- [x] 2.3 Configure security and runtime user
  - Create dedicated mcp user (UID 1000, GID 1000)
  - Set proper ownership and permissions for all application directories
  - Configure container to run as non-root user
  - Set up secure environment variables with container-internal defaults
  - Configure uvicorn to listen on 0.0.0.0:9400
  - The container entrypoint MUST run as the non-root mcp user. Running as root MUST NOT be required for normal (non-docker) operation
  - If the operator wants Docker inspection, they MAY: mount /var/run/docker.sock read-only, and run the container with --group-add <docker_group_gid>. This escalation MUST be treated as "operator choice," never default
  - _Requirements: 8.1, 8.6, 8.7, 10.1, 12.1_

- [x] 2.4 Validate zero-config container startup
  - Test container builds successfully from repo root with docker build -f Dockerfile.runtime
  - Verify container starts with docker run -p 9400:9400 and no additional flags
  - Confirm /health endpoint returns 200 OK without external dependencies
  - Test basic MCP functionality (list_tools) works without Docker socket
  - Validate all embedded defaults are functional
  - /health MUST NOT expose stack-specific/homelab values (no BASE_HOST, no tail...ts.net, etc)
  - /health MUST NOT crash if Docker, Gotify, or blog dirs aren't mounted
  - _Requirements: 1.6, 2.1, 9.1, 12.1_

- [x] 3. Implement Graceful Degradation System
- [x] 3.1 Create feature detection framework
  - Implement Docker socket availability detection
  - Add Gotify notification configuration validation
  - Create blog directory accessibility checks
  - Add policy file and configuration validation
  - Implement feature status reporting for /health endpoint
  - _Requirements: 12.2, 12.3, 4.3, 6.4_

- [x] 3.2 Implement graceful tool degradation
  - Modify Docker tools to fail gracefully when socket unavailable
  - Return structured error responses with helpful suggestions
  - Implement notification system fallback when Gotify not configured
  - Add blog tool degradation when directories not mounted
  - Ensure no tools crash the container when optional features missing
  - If a tool is unavailable (e.g. docker_ps without socket), the response MUST still follow the normal MCP envelope and MUST include a "suggestion" field in data describing how to enable that capability (e.g. "Mount /var/run/docker.sock and add the docker group to this container")
  - _Requirements: 12.2, 12.3, 6.4, 6.5_

- [x] 3.3 Add mutating operation confirmation system
  - Implement _confirm requirement validation for mutating tools
  - Create structured "confirmation required" responses (need_confirm: true)
  - Ensure mutating operations never execute without explicit confirmation
  - Add helpful error messages explaining confirmation requirement
  - Test confirmation workflow with blog_publish_static
  - When _confirm is not true, the call MUST return: {"ok": false, "need_confirm": true, "summary": "Confirmation required", "error": "This is a mutating operation and requires _confirm: true", ...} and MUST NOT perform side effects
  - _Requirements: 2.6, 4.4, 6.1_

- [x] 4. Set Up Container Publishing Pipeline
- [x] 4.1 Create GitHub Actions workflow (.github/workflows/publish-image.yml)
  - Configure workflow to trigger on push to main branch
  - Set up Docker Buildx and GitHub Container Registry authentication
  - Build container using Dockerfile.runtime as canonical source
  - Publish both main and <branch>-<shortsha> tags to GHCR
  - Add proper caching and metadata extraction
  - The workflow MUST build from Dockerfile.runtime (and ONLY Dockerfile.runtime) as the canonical source of the Runtime Container image
  - _Requirements: 3.1, 3.2, 3.6, 7.1, 7.2_

- [x] 4.2 Configure container registry and permissions
  - Ensure GITHUB_TOKEN has packages:write permission
  - Set up proper image tagging strategy (main + commit SHA)
  - Configure image metadata and labels
  - Test automated publishing on push to main
  - Validate published images are immediately available for pull
  - The workflow MUST publish at least: ghcr.io/<org>/burlymcp:main (rolling main), ghcr.io/<org>/burlymcp:<branch>-<shortsha> for traceability. This gives downstream stacks both "latest stable" and "forensic snapshot"
  - _Requirements: 3.3, 3.4, 3.5, 7.3_

- [x] 5. Migrate Docker Compose to Examples
- [x] 5.1 Create examples directory structure
  - Create examples/compose/ directory
  - Move existing docker-compose.yml and docker-compose.override.yml to examples/compose/
  - Remove any homelab-specific configuration (BASE_HOST, homepage labels, specific GIDs)
  - Add clear "EXAMPLE ONLY" header comments explaining these are reference deployments
  - _Requirements: 5.1, 5.2, 5.3, 12.9_

- [x] 5.2 Create generic example configurations
  - Parameterize all host-specific values (use <host_docker_group_gid> placeholders)
  - Add commented examples for optional Docker socket mounting
  - Include minimal run example (docker run -p 9400:9400)
  - Document optional volume mounts and environment variables
  - Remove assumptions about specific docker group GID (984)
  - Each compose example MUST start with a header comment block that says: "REFERENCE ONLY. The authoritative interface is the container (port 9400, /health, /mcp)." and "Security note: mounting /var/run/docker.sock effectively gives BurlyMCP root-equivalent power on the host. Do not expose that mode on untrusted networks."
  - _Requirements: 5.4, 5.5, 12.8, 12.10_

- [x] 5.3 Update repository root to remove compose authority
  - Remove docker-compose.yml from repository root
  - Ensure no documentation refers to compose as authoritative deployment method
  - Update any scripts or documentation that assume compose-based deployment
  - Make it clear the official contract is the container image, not compose files
  - _Requirements: 5.1, 5.2_

- [x] 6. Decouple Core Code from Docker Compose Assumptions
- [x] 6.1 Update configuration management
  - Remove hardcoded paths that assume specific compose volume mounts
  - Make all file paths configurable via environment variables
  - Implement container-internal default paths that work without external mounts
  - Remove assumptions about specific network names or container hostnames
  - Add configuration validation with clear error messages for missing requirements
  - _Requirements: 6.1, 6.2, 6.3, 6.6, 6.7_

- [x] 6.2 Update Python code to remove stack-specific assumptions
  - Remove references to web-tools network, BASE_HOST, homepage.* labels
  - Ensure no runtime logic depends on downstream stack concerns
  - Make Docker socket access optional and configurable
  - Update notification system to work without hardcoded Gotify assumptions
  - Test that core functionality works in isolation
  - Remove any implicit dependency on Docker network names, service DNS names, or other compose-era assumptions. All service-to-service communication MUST be via HTTP hostnames/IPs explicitly provided by the operator
  - _Requirements: 6.7, 8.8, 12.2_

- [x] 7. Create Comprehensive Documentation
- [x] 7.1 Add Runtime Contract section to README
  - Document container interface (port 9400, /health GET, /mcp POST)
  - Provide exact docker run commands for minimal and privileged usage
  - Document all environment variables and their purposes
  - Explain security considerations and optional elevated privileges
  - Include shutdown behavior and PID 1 expectations
  - README MUST include a "Quickstart (no privileges)" block showing: docker run --rm -p 9400:9400 ghcr.io/<org>/burlymcp:main; curl http://127.0.0.1:9400/health; curl -X POST http://127.0.0.1:9400/mcp -H 'content-type: application/json' -d '{"id":"1","method":"list_tools","params":{}}'. This sequence MUST work on any clean Linux box with only Docker installed
  - _Requirements: 4.1, 4.2, 4.3, 4.4, 4.6_

- [x] 7.2 Document configuration and deployment options
  - List all default internal paths (audit logs, policy file, blog directories)
  - Explain environment variable overrides for all settings
  - Document optional volume mounts for data persistence
  - Provide security warnings for Docker socket mounting
  - Include examples for different deployment scenarios
  - _Requirements: 4.5, 4.7, 12.8_

- [x] 7.3 Create portable documentation with generic examples
  - Ensure all documented paths, group IDs, URLs are parameterized
  - Remove any operator-specific values from public documentation
  - Include getent group docker examples for Docker socket access
  - Document graceful degradation behavior for missing optional features
  - Add troubleshooting guide for common deployment issues
  - _Requirements: 4.7, 12.9, 12.10_

- [x] 8. Implement Security and Rate Limiting
- [x] 8.1 Add HTTP API security measures
  - Implement rate limiting for /mcp endpoint (60/minute default)
  - Add RATE_LIMIT_DISABLED environment variable for lab use
  - Implement request size limits and complexity validation
  - Add input sanitization for tool names and arguments
  - Implement proper error handling without information disclosure
  - Rate limiting MUST be enabled by default for /mcp (example: 60/min/IP). An env var like RATE_LIMIT_DISABLED=true MAY fully disable rate limiting for air-gapped / lab deployments
  - Max request body size MUST be enforced (e.g. 10KB). Oversize requests MUST return an MCP-style JSON error envelope, not crash uvicorn
  - _Requirements: 8.3, 8.8, 10.3_

- [x] 8.2 Enhance container security posture
  - Ensure container runs with minimal privileges and non-root user
  - Implement proper group membership for Docker socket access
  - Add security validation on container startup
  - Document security implications of optional mounts and privileges
  - Test container security in minimal mode (no elevated privileges)
  - _Requirements: 8.1, 8.6, 8.7, 8.8_

- [x] 9. Audit Existing Tests and Integrate HTTP Bridge Testing
- [x] 9.0 Audit existing tests and plan migration strategy
  - **AUDIT**: Review all existing tests in tests/unit/ and tests/integration/ directories
  - **IDENTIFY**: Which tests remain unchanged (unit tests, security tests, tool logic tests)
  - **IDENTIFY**: Which tests need updates (MCP protocol tests to support HTTP endpoints)
  - **IDENTIFY**: Which tests need removal (docker-compose specific tests, legacy Dockerfile tests)
  - **PRESERVE**: Existing test fixtures, markers, and configuration in tests/conftest.py
  - **DOCUMENT**: Create migration plan showing before/after test structure
  - **VALIDATE**: Ensure no critical test coverage is lost during migration
  - _Requirements: Preserve existing test investment while adapting to new architecture_

- [x] 9. Integrate with Existing Testing Framework and Add HTTP Bridge Tests
- [x] 9.1 Update existing test framework for HTTP bridge compatibility
  - Review and update tests/conftest.py to support HTTP bridge testing
  - Add HTTP client fixtures and testcontainers support to existing framework
  - Update tests/integration/test_mcp_protocol.py to test both stdin/stdout and HTTP /mcp endpoints
  - Ensure existing test markers (unit, integration, docker, mcp) work with new HTTP tests
  - Preserve all existing test infrastructure and fixtures
  - _Requirements: 9.1, 9.2, 9.3, 9.4_

- [x] 9.2 Add HTTP bridge specific tests to existing structure
  - Create tests/unit/test_http_bridge.py for FastAPI application unit tests
  - Add HTTP endpoint tests to tests/integration/test_system_integration.py
  - Test /health endpoint format and status detection in existing integration framework
  - Test /mcp endpoint with both direct and params request formats using existing MCP test data
  - Integration tests MUST assert that /mcp returns HTTP 200 even when the tool fails (e.g. calling docker_ps with no socket). Non-200 here is considered a bug
  - _Requirements: 9.1, 9.2, 9.3, 9.4_

- [x] 9.3 Extend existing security tests for HTTP bridge
  - Update tests/test_security.py to include HTTP endpoint security validation
  - Add rate limiting tests to existing security test framework
  - Test request size limits and input sanitization in HTTP context
  - Ensure existing path traversal and timeout tests work with HTTP bridge
  - Validate that existing security violations are properly handled via HTTP responses
  - _Requirements: 8.1, 8.3, 10.3_

- [x] 9.4 Migrate existing Docker integration tests for new container architecture
  - **CRITICAL**: Update tests/integration/test_docker_integration.py to test Dockerfile.runtime instead of legacy Dockerfiles
  - Replace docker-compose tests with HTTP endpoint container tests
  - Migrate existing container lifecycle tests to use published GHCR images when available
  - Update existing Docker test fixtures to work with HTTP bridge container
  - **PRESERVE**: Keep existing Docker client tests and container operation tests (these remain valid)
  - **REMOVE**: Docker-compose specific tests that assume root compose files
  - Test minimal container run (docker run -p 9400:9400) succeeds using existing Docker test infrastructure
  - _Requirements: 10.1, 10.2, 10.3, 12.1_

- [x] 9.5 Update integration test runner for new architecture
  - Update tests/run_integration_tests.py to handle HTTP endpoint testing
  - Add new test categories for HTTP bridge tests while preserving existing markers
  - Update prerequisite checks to include HTTP client dependencies
  - Modify test execution to support both stdin/stdout (legacy) and HTTP (new) MCP testing
  - Ensure backward compatibility with existing test execution patterns
  - _Requirements: 9.5, 11.1, 11.2, 11.3_

- [x] 9.6 Update test documentation for new architecture
  - Update tests/README.md to document HTTP bridge testing capabilities and migration from compose-based tests
  - Document which existing tests are preserved vs modified vs removed
  - Add new test markers for HTTP bridge tests while preserving existing markers
  - Update test execution examples to show both legacy and new testing approaches
  - Document the transition strategy for maintaining test coverage during migration
  - _Requirements: 9.5, 11.1, 11.2, 11.3_

- [x] 10. Final Integration and Validation
- [x] 10.1 Validate complete standalone operation
  - Test container starts and responds to health checks within 30 seconds
  - Verify graceful shutdown on SIGTERM within 10 seconds
  - Confirm all tools fail gracefully when optional features unavailable
  - Test environment variable validation and startup error handling
  - Validate audit logging and startup summary output
  - _Requirements: 10.1, 10.2, 10.6, 10.7_

- [x] 10.2 Verify API stability and backward compatibility
  - Test HTTP bridge maintains consistent response format
  - Verify both MCP request formats continue to work
  - Confirm error responses include helpful suggestions
  - Test that internal refactors don't break /mcp contract
  - Validate downstream integration compatibility
  - After we refactor the MCP engine from subprocess → in-process (future work), the same black-box tests MUST continue to pass unchanged
  - _Requirements: 11.1, 11.2, 11.3_

- [x] 10.3 Complete public deployment readiness validation
  - Test container works on arbitrary Linux hosts without customization
  - Verify no hardcoded homelab-specific values in published image
  - Confirm all documentation uses generic, parameterized examples
  - Test minimal privilege mode provides useful functionality
  - Validate container can be consumed by downstream infrastructure systems
  - _Requirements: 12.1, 12.8, 12.9, 12.10_