# Design Document

## Overview

This design addresses the Docker container image publishing failure by implementing a lowercase naming convention for container images. The solution focuses on modifying the GitHub Actions workflow to use Docker registry-compliant naming while maintaining functionality and fixing the security scanning issues.

## Architecture

The fix involves three main components:
1. **GitHub Actions Workflow Modification**: Update environment variables and image naming logic
2. **Image Name Transformation**: Convert repository names to lowercase format
3. **Security Scanning Integration**: Ensure Trivy security scanning works with the corrected image names

## Components and Interfaces

### GitHub Actions Environment Variables

**Current State:**
```yaml
env:
  REGISTRY: ghcr.io
  IMAGE_NAME: Wolfeitz/BurlyMCP  # Contains uppercase - causes failure
```

**Proposed State:**
```yaml
env:
  REGISTRY: ghcr.io
  IMAGE_NAME: wolfeitz/burlymcp  # Lowercase compliant
```

### Image Naming Strategy

**Selected Approach**: Repository-based naming with lowercase conversion
- **Rationale**: Maintains clear ownership (wolfeitz/) while fixing the technical issue
- **Format**: `ghcr.io/wolfeitz/burlymcp:tag`
- **Benefits**: 
  - Minimal disruption to existing references
  - Clear ownership indication
  - Docker registry compliant

### Workflow Steps Affected

1. **Build and Push Container Step**
   - Update IMAGE_NAME environment variable
   - Ensure all docker commands use lowercase image references

2. **Image Validation Step**
   - Update hardcoded image references in validation scripts
   - Fix the MAIN_TAG variable construction

3. **Security Scanning Step**
   - Ensure Trivy scan targets the correct lowercase image name
   - Fix SARIF file generation and upload path issues

## Data Models

### Image Reference Structure
```
Registry: ghcr.io
Namespace: wolfeitz
Repository: burlymcp
Tag: main|latest|v1.0.0|etc.
Full Reference: ghcr.io/wolfeitz/burlymcp:tag
```

### Environment Variable Schema
```yaml
REGISTRY: string          # Container registry URL
IMAGE_NAME: string        # Lowercase repository path (namespace/repo)
MAIN_TAG: string         # Computed full image reference
```

## Error Handling

### Docker Pull/Push Failures
- **Issue**: Invalid reference format errors
- **Solution**: Validate image name format before Docker operations
- **Fallback**: Provide clear error messages with correct naming examples

### Security Scan Failures
- **Issue**: Missing trivy-results.sarif file
- **Solution**: Ensure Trivy scan completes successfully and generates output file
- **Fallback**: Continue workflow with warning if security scan fails (non-blocking for development)

### Image Validation Failures
- **Issue**: Health endpoint tests failing due to incorrect image references
- **Solution**: Update all hardcoded image references in test scripts
- **Fallback**: Provide detailed container logs on validation failure

## Testing Strategy

### Unit Testing
- Validate image name transformation logic
- Test environment variable substitution
- Verify Docker command construction

### Integration Testing
- Test complete workflow execution with new naming
- Validate image publishing to registry
- Confirm image pull and validation steps work

### Security Testing
- Ensure Trivy security scanning works with new image names
- Validate SARIF file generation and upload
- Test security scan integration with GitHub Security tab

### Deployment Testing
- Test image deployment in various environments
- Validate backward compatibility with existing deployment scripts
- Confirm image accessibility from different contexts

## Implementation Considerations

### Backward Compatibility
- Document the image name change in release notes
- Provide migration guide for existing deployments
- Consider creating image aliases if needed

### Documentation Updates
- Update README.md with new image references
- Update deployment documentation
- Update any hardcoded references in example files

### Monitoring and Observability
- Ensure logging captures the correct image names
- Update any monitoring that references the old image names
- Verify container registry metrics track the new image names correctly