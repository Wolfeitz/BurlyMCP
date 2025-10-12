# Requirements Document

## Introduction

Burly MCP is a containerized Model Context Protocol (MCP) server that provides a secure, policy-driven interface for system operations. It serves as the first component of the broader "AgentOps" initiative, enabling AI assistants like Open WebUI to safely execute whitelisted system tasks including Docker container management, disk monitoring, blog publishing, and notification services.

## Requirements

### Requirement 1

**User Story:** As an AI assistant user, I want to query system status through a secure MCP interface, so that I can monitor Docker containers and disk usage without direct system access.

#### Acceptance Criteria

1. WHEN the MCP server receives a list_tools request THEN it SHALL return available tools (docker_ps, disk_space) with their descriptions and schemas
2. WHEN docker_ps is called THEN the system SHALL execute Docker CLI commands and return container status in table format
3. WHEN disk_space is called THEN the system SHALL return filesystem usage summary using df -hT
4. IF any read-only tool fails THEN the system SHALL return error details without exposing sensitive system information

### Requirement 2

**User Story:** As a blog author, I want to validate and publish Markdown content through MCP, so that I can safely manage my static site content with AI assistance.

#### Acceptance Criteria

1. WHEN blog_stage_markdown is called with a file path THEN the system SHALL validate YAML front-matter and return validation results
2. WHEN blog_publish_static is called without confirmation THEN the system SHALL return need_confirm response
3. WHEN blog_publish_static is called with _confirm:true THEN the system SHALL copy staged files to publish directory
4. IF source files are outside BLOG_STAGE_ROOT THEN the system SHALL reject the request with path traversal error
5. IF publish operation succeeds THEN the system SHALL return summary with files_written count

### Requirement 3

**User Story:** As a system administrator, I want all MCP operations to be audited and optionally reported via Gotify, so that I can track AI assistant actions and receive notifications.

#### Acceptance Criteria

1. WHEN any tool is executed THEN the system SHALL write an audit record with timestamp, tool name, status, and execution metrics
2. WHEN a tool is configured with Gotify notifications THEN the system SHALL send appropriate priority messages (success=3, need_confirm=5, failure=8)
3. IF Gotify delivery fails THEN the system SHALL log a warning but continue tool execution
4. WHEN audit logs are written THEN sensitive environment variables SHALL be redacted from args_hash

### Requirement 4

**User Story:** As a security-conscious operator, I want the MCP server to enforce strict policy controls and run with minimal privileges, so that AI assistants cannot perform unauthorized system operations.

#### Acceptance Criteria

1. WHEN the server starts THEN it SHALL load tool policies from policy/tools.yaml and validate against JSON schemas
2. WHEN any tool is called THEN the system SHALL validate arguments against the tool's defined schema
3. WHEN a mutating tool is called without confirmation THEN the system SHALL refuse execution and request confirmation
4. IF any tool exceeds its configured timeout THEN the system SHALL terminate execution and return timeout error
5. WHEN tool output exceeds OUTPUT_TRUNCATE_LIMIT THEN the system SHALL truncate and indicate truncation
6. IF any command attempts to execute outside the allowlist THEN the system SHALL reject with policy violation error

### Requirement 5

**User Story:** As a DevOps engineer, I want the MCP server to run in a secure container with proper isolation, so that it can safely interface with system resources without compromising security.

#### Acceptance Criteria

1. WHEN the container starts THEN it SHALL run as non-root user (agentops, uid 1000) with no sudo access
2. WHEN Docker operations are needed THEN the system SHALL access Docker socket through read-only mount
3. WHEN blog operations are performed THEN staging directory SHALL be read-only and publish directory SHALL be write-only
4. IF any operation attempts path traversal THEN the system SHALL reject with security violation
5. WHEN the server communicates THEN it SHALL use only stdin/stdout (no network ports exposed)

### Requirement 6

**User Story:** As an Open WebUI user, I want to interact with system tools through natural language, so that I can perform operations without learning command-line syntax.

#### Acceptance Criteria

1. WHEN I ask "List my Docker containers" THEN the system SHALL execute docker_ps and return formatted results
2. WHEN I ask "Check disk space" THEN the system SHALL execute disk_space and return usage summary
3. WHEN I request to publish blog content THEN the system SHALL require explicit confirmation before executing
4. WHEN any operation completes THEN the system SHALL provide a clear summary of what was accomplished
5. IF I attempt to use non-existent tools THEN the system SHALL inform me of available tools only