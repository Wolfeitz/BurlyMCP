# Implementation Plan

- [x] 1. Project scaffolding and structure setup
- [x] 1.1 Initialize git repository with public-friendly setup
  - Initialize git repository with proper `.gitignore` for Python projects
  - Add MIT or Apache 2.0 license for public GitHub release
  - Create initial commit with repository structure
  - _Requirements: 5.1_

- [x] 1.2 Create comprehensive project structure
  - Create directory structure: `/server`, `/policy`, `/docs`, `/docker`, `/tests`
  - Initialize Python project with `pyproject.toml` and dependencies
  - Create placeholder files for main modules with educational comments
  - _Requirements: 5.1, 5.2_

- [x] 1.3 Create comprehensive README with educational approach
  - Write detailed README explaining MCP concepts for newcomers
  - Include step-by-step setup instructions with explanations
  - Add "Why MCP?" section to help users understand the value
  - Include security considerations and best practices
  - _Requirements: 5.1, 6.5_

- [x] 2. Policy engine and validation system
- [x] 2.1 Implement YAML policy loader
  - Create `PolicyLoader` class to read and parse `policy/tools.yaml`
  - Implement validation for required policy fields
  - Add error handling for malformed YAML files
  - _Requirements: 4.1, 4.2_

- [x] 2.2 Build JSON schema validation system
  - Create `SchemaValidator` class with JSON Schema 2020-12 support
  - Implement per-tool argument validation
  - Add descriptive error messages for validation failures
  - _Requirements: 4.2, 4.6_

- [x] 2.3 Create tool registry and definition models
  - Implement `ToolDefinition` dataclass with all required fields
  - Create `ToolRegistry` to manage available tools
  - Add tool lookup and validation methods
  - _Requirements: 4.1, 4.2_

- [ ]* 2.4 Write unit tests for policy system
  - Test YAML loading with valid and invalid files
  - Test schema validation with edge cases
  - Test tool registry operations
  - _Requirements: 4.1, 4.2_

- [x] 3. MCP protocol implementation
- [x] 3.1 Create MCP message handling
  - Implement `MCPRequest` and `MCPResponse` dataclasses
  - Create JSON parser for stdin input
  - Add stdout writer for MCP responses
  - _Requirements: 1.1, 6.1_

- [x] 3.2 Implement core MCP operations
  - Create `list_tools` handler returning available tools
  - Implement `call_tool` handler with routing logic
  - Add confirmation workflow for mutating operations
  - _Requirements: 1.1, 2.2, 4.3_

- [x] 3.3 Build response envelope system
  - Create standardized response formatting
  - Implement error response handling
  - Add metrics collection (elapsed_ms, exit_code)
  - _Requirements: 1.1, 2.5, 6.4_

- [ ]* 3.4 Write unit tests for MCP protocol
  - Test request parsing and response formatting
  - Test confirmation workflow
  - Test error handling scenarios
  - _Requirements: 1.1, 2.2_

- [x] 4. Tool adapter implementations
- [x] 4.1 Implement Docker operations tool
  - Create `docker_ps` function executing Docker CLI
  - Parse Docker output into structured format
  - Handle Docker socket access errors
  - _Requirements: 1.2, 5.2, 6.1_

- [x] 4.2 Implement disk space monitoring tool
  - Create `disk_space` function using `df -hT` command
  - Parse filesystem usage into readable format
  - Handle permission and access errors
  - _Requirements: 1.3, 6.2_

- [x] 4.3 Implement blog validation tool
  - Create `blog_stage_markdown` function for YAML front-matter parsing
  - Validate required front-matter fields
  - Handle file access and parsing errors
  - _Requirements: 2.1, 5.4_

- [x] 4.4 Implement blog publishing tool
  - Create `blog_publish_static` function with confirmation gate
  - Implement safe file copying with path validation
  - Add file operation summary and metrics
  - _Requirements: 2.2, 2.3, 5.4_

- [x] 4.5 Implement Gotify notification tool
  - Create `gotify_ping` function for test message sending
  - Handle HTTP requests to Gotify API
  - Add error handling for network failures
  - _Requirements: 3.2, 6.3_

- [ ]* 4.6 Write integration tests for tools
  - Test Docker CLI integration with mock containers
  - Test file system operations with temporary directories
  - Test Gotify API integration
  - _Requirements: 1.2, 2.1, 3.2_

- [x] 5. Security and hardening implementation
- [x] 5.1 Implement path traversal protection
  - Create path validation functions for all file operations
  - Enforce BLOG_STAGE_ROOT and BLOG_PUBLISH_ROOT boundaries
  - Add security violation logging
  - _Requirements: 2.4, 4.4, 5.4_

- [x] 5.2 Add timeout and output limiting
  - Implement per-tool timeout enforcement
  - Add stdout/stderr truncation with indicators
  - Create resource limit monitoring
  - _Requirements: 4.5, 4.5_

- [x] 5.3 Build audit logging system
  - Create `AuditLogger` class writing JSON Lines format
  - Implement audit record generation with all required fields
  - Add environment variable redaction for security
  - _Requirements: 3.1, 3.4_

- [ ]* 5.4 Write security tests
  - Test path traversal prevention
  - Test timeout enforcement
  - Test output truncation
  - _Requirements: 4.4, 4.5, 5.4_

- [x] 6. Notification and monitoring integration
- [x] 6.1 Implement Gotify notification system
  - Create `GotifyNotifier` class with configurable priorities
  - Add per-tool notification configuration
  - Implement failure handling that doesn't block operations
  - _Requirements: 3.2, 3.3_

- [x] 6.2 Integrate notifications with tool execution
  - Add notification calls to tool execution pipeline
  - Implement success, failure, and confirmation notifications
  - Add notification status to audit logs
  - _Requirements: 3.1, 3.2_

- [ ]* 6.3 Write notification tests
  - Test Gotify API integration
  - Test notification failure handling
  - Test priority assignment
  - _Requirements: 3.2, 3.3_

- [x] 7. Main server application
- [x] 7.1 Create main server entry point
  - Implement `main.py` with MCP protocol loop
  - Add configuration loading from environment variables
  - Create graceful startup and shutdown handling
  - _Requirements: 5.1, 5.5_

- [x] 7.2 Integrate all components
  - Wire policy engine, tool registry, and audit system
  - Connect MCP handler with tool execution
  - Add comprehensive error handling and logging
  - _Requirements: 1.1, 4.1, 5.1_

- [ ]* 7.3 Write end-to-end tests
  - Test complete MCP request/response cycles
  - Test all tools through MCP interface
  - Test confirmation workflows
  - _Requirements: 1.1, 2.2, 6.4_

- [ ] 8. Container packaging and deployment
- [ ] 8.1 Create Dockerfile with security hardening
  - Use `python:3.12-slim` base image
  - Create non-root `agentops` user (uid 1000)
  - Install only required dependencies
  - _Requirements: 5.1, 5.2_

- [ ] 8.2 Create docker-compose configuration
  - Define volume mounts for policy, logs, and blog directories
  - Set environment variables and security constraints
  - Configure proper mount permissions
  - _Requirements: 5.2, 5.3, 5.4_

- [ ] 8.3 Create default policy and configuration files with security focus
  - Write `policy/tools.yaml` with all MVP tools and educational comments
  - Create `.env.example` template with NO secrets, only placeholders
  - Add comprehensive configuration documentation explaining each setting
  - Include security warnings and best practices in configuration files
  - _Requirements: 4.1, 5.1_

- [ ] 9. Documentation and integration guides
- [ ] 9.1 Create comprehensive operational documentation
  - Write `docs/runbook.md` with beginner-friendly deployment guide
  - Create `docs/config.md` explaining every configuration option and why it matters
  - Add `docs/security.md` with threat model and mitigation strategies
  - Include `docs/mcp-explained.md` to educate users about MCP protocol
  - _Requirements: 5.1, 4.1_

- [ ] 9.2 Create Open WebUI integration guide
  - Write `docs/open-webui.md` with setup instructions
  - Add example agent prompts and workflows
  - Include troubleshooting section
  - _Requirements: 6.1, 6.2, 6.5_

- [ ]* 9.3 Create CLI test harness for validation
  - Build command-line tool for testing MCP operations
  - Add JSON input/output validation
  - Create demo scenarios and expected outputs
  - _Requirements: 1.1, 6.4_