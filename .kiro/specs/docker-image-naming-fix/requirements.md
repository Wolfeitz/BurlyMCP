# Requirements Document

## Introduction

This feature addresses the Docker container image publishing failure caused by uppercase characters in the repository name. Docker registries require lowercase repository names, but the current GitHub Actions workflow uses "Wolfeitz/BurlyMCP" which contains uppercase letters, causing the publishing step to fail with "invalid reference format" errors.

## Glossary

- **GitHub_Actions_Workflow**: The automated CI/CD pipeline that builds, tests, and publishes container images
- **Docker_Registry**: The container image storage service (GitHub Container Registry - ghcr.io)
- **Repository_Name**: The identifier used for the container image in the registry (e.g., "burly-mcp" or "wolfeitz/burlymcp")
- **Image_Naming_Strategy**: The approach for converting repository names to Docker-compliant lowercase format
- **Image_Tag**: The version identifier appended to the repository name
- **Container_Publishing_Step**: The specific workflow step that pushes built images to the registry

## Requirements

### Requirement 1

**User Story:** As a developer, I want the container image publishing to succeed, so that the CI/CD pipeline completes successfully and images are available for deployment.

#### Acceptance Criteria

1. WHEN the GitHub_Actions_Workflow builds a container image, THE GitHub_Actions_Workflow SHALL use a lowercase repository name format
2. WHEN the Container_Publishing_Step executes, THE Container_Publishing_Step SHALL successfully push images to the Docker_Registry without format errors
3. WHEN the image validation step runs, THE GitHub_Actions_Workflow SHALL successfully pull and test the published image
4. WHERE the repository name contains uppercase characters, THE GitHub_Actions_Workflow SHALL convert them to lowercase before publishing
5. WHEN the publishing completes, THE Docker_Registry SHALL contain images with consistent lowercase naming

### Requirement 2

**User Story:** As a DevOps engineer, I want a clear and consistent image naming strategy, so that the container images are easily identifiable and follow Docker registry standards.

#### Acceptance Criteria

1. THE GitHub_Actions_Workflow SHALL choose between two Image_Naming_Strategy options: descriptive naming (e.g., "burly-mcp") or repository-based naming (e.g., "wolfeitz/burlymcp")
2. WHERE a descriptive naming strategy is chosen, THE Repository_Name SHALL reflect the application purpose (e.g., "burly-mcp", "burly-mingo-mcp-server")
3. WHERE a repository-based naming strategy is chosen, THE Repository_Name SHALL convert the GitHub repository name to lowercase format
4. THE Container_Publishing_Step SHALL generate image names that follow Docker registry naming standards (lowercase, hyphens allowed, no underscores in registry path)
5. WHEN the workflow publishes multiple tags, THE GitHub_Actions_Workflow SHALL apply the chosen naming convention consistently to all tag variations

### Requirement 3

**User Story:** As a system administrator, I want the security scanning to work properly, so that vulnerability reports are generated and uploaded correctly.

#### Acceptance Criteria

1. WHEN the security scan completes, THE GitHub_Actions_Workflow SHALL generate the trivy-results.sarif file
2. WHEN uploading security results, THE GitHub_Actions_Workflow SHALL successfully upload the SARIF file to GitHub Security tab
3. IF the trivy scan fails to generate results, THEN THE GitHub_Actions_Workflow SHALL provide clear error messaging
4. THE GitHub_Actions_Workflow SHALL ensure security scanning runs against the correctly named container image
5. WHEN security vulnerabilities are found, THE GitHub_Actions_Workflow SHALL block the publishing process for critical issues