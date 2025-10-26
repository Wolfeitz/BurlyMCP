# Requirements Document

## Introduction

BurlyMCP needs to be transformed into a standalone service container that can be consumed by other systems. The current implementation assumes docker-compose orchestration and lacks HTTP API endpoints. This transformation will create a self-contained Docker image that exposes HTTP endpoints (/health and /mcp) and can be deployed independently by downstream infrastructure systems.

BurlyMCP is an open, public project. The Runtime_Container must run on arbitrary Linux hosts, not just our homelab. All host-specific values (paths, group IDs, network names, notification endpoints, etc.) must be configurable at runtime via environment variables or optional mounts. No container behavior may depend on hardcoded values from any single operator's environment.

## Glossary

- **BurlyMCP**: The Model Context Protocol server application
- **HTTP_Bridge**: FastAPI application that provides HTTP endpoints for MCP communication
- **Runtime_Container**: The canonical Docker image that contains the complete BurlyMCP service
- **Downstream_System**: External systems that will consume the BurlyMCP container (e.g., system-tools stack)
- **Canonical_Dockerfile**: The official Dockerfile.runtime that produces the deployable container image

## Requirements

### Requirement 1

**User Story:** As a downstream system operator, I want to deploy BurlyMCP as a standalone container, so that I can integrate it into my infrastructure without managing docker-compose files.

#### Acceptance Criteria

1. WHEN I run `docker build -f Dockerfile.runtime -t burlymcp:dev .` from the repo root, THEN the build SHALL complete successfully without external dependencies
2. WHEN the container starts, THEN it SHALL expose port 9400 with HTTP endpoints without requiring external configuration files
3. WHEN I deploy the container, THEN it SHALL NOT require docker-compose.yml or external volume mounts to function
4. IF the container needs elevated privileges, THEN those SHALL be optional and configurable via environment variables
5. WHEN the container runs, THEN it SHALL be self-contained with all required dependencies and configuration embedded
6. WHEN I run `docker run -p 9400:9400 burlymcp:dev` with no extra environment variables, THEN the container SHALL start and respond successfully to GET /health

### Requirement 2

**User Story:** As an API consumer, I want to interact with BurlyMCP through HTTP endpoints, so that I can integrate it with web-based systems and monitoring tools.

#### Acceptance Criteria

1. WHEN I send GET /health, THEN the HTTP_Bridge SHALL return 200 status with JSON body containing at least {"status":"ok"}
2. WHEN I send POST /mcp with MCP request JSON, THEN the HTTP_Bridge SHALL forward the request to the MCP engine and return the response
3. WHEN I call POST /mcp with {"id":"test","method":"list_tools","params":{}}, THEN the system SHALL return available tools in MCP format
4. WHEN I call POST /mcp with {"id":"test","method":"call_tool","name":"disk_space","args":{}}, THEN the system SHALL execute the tool and return results
5. WHEN the HTTP_Bridge communicates with MCP engine, THEN it SHALL maintain the same behavior as direct stdio communication
6. WHEN I call POST /mcp with body {"id":"X","method":"call_tool","name":"disk_space","args":{}}, THEN the system SHALL return a JSON response with fields ok, summary, and (if successful) data, matching the MCP engine's response structure
7. WHEN I call POST /mcp with body {"id":"X","method":"call_tool","params":{"name":"disk_space","args":{}}}, THEN the system SHOULD also work, or respond with a structured error that describes the required schema

### Requirement 3

**User Story:** As a container registry consumer, I want to pull official BurlyMCP images from a registry, so that I can deploy consistent versions without building from source.

#### Acceptance Criteria

1. WHEN code is pushed to main branch, THEN GitHub Actions SHALL build and publish ghcr.io/<org>/burlymcp:main automatically
2. WHEN a commit is made, THEN the system SHALL also tag and publish ghcr.io/<org>/burlymcp:${{ github.sha }}
3. WHEN I pull the published image, THEN it SHALL contain the complete BurlyMCP service ready to run
4. IF I need a specific version, THEN I SHALL be able to pull by commit SHA or main tag
5. WHEN images are published, THEN they SHALL be available to downstream systems without authentication for public repositories
6. WHEN the GitHub Actions workflow builds images, THEN it SHALL build using Dockerfile.runtime at the repo root as the canonical source, and NOT any legacy Dockerfile(s)

### Requirement 4

**User Story:** As a system administrator, I want clear documentation of the container interface, so that I can deploy and configure BurlyMCP correctly in my environment.

#### Acceptance Criteria

1. WHEN I read the README, THEN it SHALL document the container interface including port 9400, /health, and /mcp endpoints
2. WHEN I need to run with Docker socket access, THEN the documentation SHALL provide the exact docker run command with proper security options
3. WHEN I want to persist data, THEN the documentation SHALL specify internal paths for logs, audit files, and configuration
4. IF I need to configure the service, THEN the documentation SHALL list all environment variables and their purposes
5. WHEN I deploy in production, THEN the documentation SHALL explain security considerations and optional elevated privileges
6. WHEN I read the README, THEN it SHALL document shutdown expectations (SIGTERM leads to graceful shutdown within 10 seconds) and clearly state that the process inside the container is PID 1 and is the main MCP/HTTP runtime
7. WHEN I read the README, THEN all documented paths, group IDs, URLs, and env values SHALL be generic or parameterized (for example <host_docker_group_gid>, <your_gotify_url>), and SHALL NOT include operator-specific values from a private environment

### Requirement 5

**User Story:** As a developer, I want docker-compose configurations moved to examples, so that the repository clearly separates the official container interface from deployment examples.

#### Acceptance Criteria

1. WHEN I examine the repo root, THEN docker-compose.yml SHALL NOT be present as an authoritative deployment method
2. WHEN I look in examples/compose/, THEN I SHALL find reference docker-compose configurations with clear documentation
3. WHEN I read example compose files, THEN they SHALL include comments explaining that these are environment-specific examples
4. IF example compose files include special mounts or configurations, THEN they SHALL be clearly marked as optional operator decisions
5. WHEN the repository is examined, THEN it SHALL be clear that the official contract is the container image, not compose files

### Requirement 6

**User Story:** As a BurlyMCP core developer, I want the Python code to be independent of docker-compose assumptions, so that the service can run in any container orchestration system.

#### Acceptance Criteria

1. WHEN the Python code references file paths, THEN they SHALL be configurable via environment variables with sensible defaults
2. WHEN the service needs external resources, THEN it SHALL NOT assume specific network names or container hostnames
3. WHEN configuration files are required, THEN they SHALL be embedded in the container image or have fallback defaults
4. IF the service needs Docker socket access, THEN it SHALL gracefully handle cases where the socket is not available
5. WHEN the service starts, THEN it SHALL validate its environment and provide clear error messages for missing requirements
6. WHEN the container is built, THEN it SHALL include a default policy file (e.g. policy/tools.yaml) baked into the image, and the runtime SHALL load that by default if no override is provided via env or volume
7. WHEN the Python code initializes, THEN it SHALL NOT assume web-tools network, BASE_HOST, homepage.* labels, or any other downstream stack concerns. Those MAY appear in example compose files, but SHALL NOT appear in runtime logic inside the image

### Requirement 7

**User Story:** As a CI/CD engineer, I want automated container publishing, so that new versions are available immediately after code changes.

#### Acceptance Criteria

1. WHEN code is pushed to main, THEN GitHub Actions SHALL build Dockerfile.runtime and push to GitHub Container Registry
2. WHEN the build completes, THEN both :main and :${{ github.sha }} tags SHALL be available for pulling
3. WHEN the workflow runs, THEN it SHALL assume GITHUB_TOKEN has packages:write permission for GHCR publishing
4. IF the build fails, THEN the workflow SHALL fail and prevent publishing of broken images
5. WHEN images are published, THEN they SHALL be immediately available for downstream systems to consume

### Requirement 8

**User Story:** As a security-conscious operator, I want the runtime container to follow security best practices, so that I can deploy it safely in production environments.

#### Acceptance Criteria

1. WHEN the container runs, THEN it SHALL use a non-root user with minimal privileges
2. WHEN the container is built, THEN it SHALL use debian:trixie-slim as the base image for security and size optimization
3. WHEN the container needs elevated access, THEN it SHALL be configurable and documented with security warnings
4. IF Docker socket access is mounted, THEN the documentation SHALL explain the security implications
5. WHEN the container starts, THEN it SHALL validate security configurations and warn about insecure setups
6. WHEN the container is built, THEN it SHALL create a dedicated runtime user (e.g. mcp UID 1000:GID 1000 or similar), and that user SHALL own the runtime process
7. WHEN the container is started with --group-add <host_docker_group_gid> and /var/run/docker.sock mounted, THEN docker-related tools SHALL function under that user without requiring the container to run as root
8. WHEN the container runs in "minimal mode" (no docker.sock mount, no extra groups, no notification tokens), THEN it SHALL still be functional, SHALL expose /mcp for read-only / diagnostic tools (e.g. disk usage), and SHALL not escalate privileges automatically

### Requirement 9

**User Story:** As a testing engineer, I want the container to be testable independently, so that I can validate functionality without complex setup.

#### Acceptance Criteria

1. WHEN I run the container with `docker run -p 9400:9400 ghcr.io/<org>/burlymcp:main`, THEN it SHALL start successfully and respond to health checks
2. WHEN I test the /health endpoint, THEN it SHALL return 200 OK without requiring external dependencies
3. WHEN I test basic MCP functionality, THEN list_tools SHALL work without Docker socket or special mounts
4. IF I mount Docker socket, THEN Docker-related tools SHALL become available and functional
5. WHEN I run integration tests, THEN they SHALL be able to test the container as a black box via HTTP endpoints

### Requirement 10

**User Story:** As a downstream infrastructure engineer, I want predictable container behavior, so that I can integrate BurlyMCP into automated deployment pipelines.

#### Acceptance Criteria

1. WHEN the container starts, THEN it SHALL listen on port 9400 within 30 seconds of startup
2. WHEN the container receives SIGTERM, THEN it SHALL gracefully shutdown within 10 seconds
3. WHEN environment variables are provided, THEN the container SHALL validate them at startup and fail fast on invalid configuration
4. IF required files are missing, THEN the container SHALL log clear error messages and exit with non-zero status
5. WHEN the container is healthy, THEN /health endpoint SHALL consistently return 200 status with valid JSON
6. WHEN the container is running, THEN it SHALL write audit and operation logs to a known internal path (for example /var/log/agentops/audit.jsonl) and SHALL NOT crash if that path is not mounted to the host
7. WHEN the container starts, THEN it SHALL log a single structured startup summary (tool count, policy loaded, notifications enabled/disabled) to stdout, so downstream logging systems can detect readiness

### Requirement 11

**User Story:** As an integrator, I want the HTTP bridge to remain stable even if the internal MCP implementation changes, so that downstream systems do not break when BurlyMCP refactors.

#### Acceptance Criteria

1. WHEN the MCP engine implementation changes (e.g. module paths, internal class names, moving from subprocess to in-process call), THEN the HTTP_Bridge /mcp endpoint SHALL continue to accept the same request format and return the same response format defined in Requirement 2
2. WHEN I upgrade BurlyMCP from one published image tag to a newer tag, THEN my downstream integrations SHALL NOT have to change how they call /mcp
3. WHEN I parse the response from /mcp, THEN I SHALL continue to receive top-level fields ok, summary, and (when relevant) data, so my LLM agent logic still works

### Requirement 12

**User Story:** As an external user (not running the original homelab), I want to run BurlyMCP without modifying source code or guessing at internal assumptions, so that I can adopt it in my environment.

#### Acceptance Criteria

1. WHEN I run the published container with only `docker run -p 9400:9400 ghcr.io/<org>/burlymcp:main`, THEN it SHALL start successfully, expose /health, and respond to /mcp list_tools, without requiring local bind mounts, docker.sock, or any environment variables
2. WHEN optional features require external integration (for example, docker_ps which inspects host Docker, or Gotify notifications), THEN those features SHALL gracefully degrade if not configured, and the container SHALL NOT crash or exit non-zero because they're missing
3. IF /var/run/docker.sock is not mounted, WHEN calling docker_ps, THEN it SHOULD return a structured error like {"ok": false, "summary": "Docker unavailable", "error": "Docker socket not accessible in this container"} instead of a stack trace or 500
4. WHEN configuration is needed (e.g. BLOG_STAGE_ROOT, BLOG_PUBLISH_ROOT, GOTIFY_URL, GOTIFY_TOKEN, audit log path), THEN each SHALL have a documented default baked into the image, and MAY be overridden by environment variables at runtime
5. WHEN the container uses default paths, THEN there SHALL NOT be required absolute paths like /home/rob/.... Defaults must be container-internal paths like /app/data/... or /var/log/agentops/... that exist in the image
6. WHEN the container starts, THEN it SHALL log (to stdout) a single structured startup block that includes the resolved values of key runtime dirs (blog stage dir, publish dir, audit log path), whether notifications are enabled, and how many tools are registered
7. WHEN startup logging occurs, THEN it SHALL NOT print secrets (like GOTIFY_TOKEN), but SHALL make it obvious to any operator on any host "what mode it's in"
8. WHEN I read the README, THEN it SHALL document the default internal paths for everything (audit log dir, policy file location, blog staging dir), the env vars that can override each path, and examples for "secure minimal run" (no privileges) vs "privileged ops run" (with --group-add <gid> and -v /var/run/docker.sock:/var/run/docker.sock)
9. WHEN I look at any example docker-compose in examples/compose/, THEN it SHALL NOT include homelab-specific network names, labels, or dashboards (like homepage.labels, web-tools, BASE_HOST, etc.), and SHALL NOT assume the docker group is GID 984
10. WHEN example compose files reference host-specific values, THEN they SHALL include comments like "# OPTIONAL: to allow container to inspect host Docker, # replace <host_docker_group_gid> with the numeric GID of your docker group: # getent group docker"