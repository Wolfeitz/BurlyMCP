# Release and Distribution Process

This document describes the automated release and distribution process for Burly MCP, including versioning, building, testing, and publishing to PyPI and Docker registries.

## Overview

The Burly MCP project uses a fully automated release pipeline that:

1. **Automatically determines version bumps** based on conventional commit messages
2. **Validates release readiness** through comprehensive testing
3. **Builds and validates packages** for both Python and Docker
4. **Publishes to multiple registries** with security scanning
5. **Generates release notes** and documentation automatically

## Release Workflow

### Automatic Releases (Recommended)

Releases are automatically triggered when code is pushed to the `main` branch, based on conventional commit messages:

```bash
# Patch release (1.0.0 → 1.0.1)
git commit -m "fix: resolve Docker socket permission issue"

# Minor release (1.0.0 → 1.1.0)  
git commit -m "feat: add new blog management tools"

# Major release (1.0.0 → 2.0.0)
git commit -m "feat!: redesign MCP protocol interface"
# or
git commit -m "feat: add breaking change

BREAKING CHANGE: The MCP interface has been redesigned"
```

### Manual Releases

You can also trigger releases manually using the GitHub Actions workflow:

1. Go to **Actions** → **Release Pipeline** in the GitHub repository
2. Click **Run workflow**
3. Select the version bump type (`patch`, `minor`, `major`)
4. Choose whether to create a prerelease
5. Click **Run workflow**

### Local Release Preparation

Before pushing changes that will trigger a release:

```bash
# 1. Prepare and validate everything locally
make prepare-distribution

# 2. Check current version and suggest bump
make version-current
make version-suggest

# 3. Optionally bump version locally (will be done automatically in CI)
make version-bump TYPE=patch  # or minor, major

# 4. Push to main branch to trigger release
git push origin main
```

## Version Management

### Semantic Versioning

The project follows [Semantic Versioning](https://semver.org/):

- **MAJOR** version for incompatible API changes
- **MINOR** version for backwards-compatible functionality additions  
- **PATCH** version for backwards-compatible bug fixes

### Version Management Commands

```bash
# Show current version
make version-current

# Suggest version bump based on git history
make version-suggest

# Manually bump version
make version-bump TYPE=patch|minor|major

# Set specific version
make version-set VERSION=1.2.3

# Validate release readiness
make version-validate

# Generate release notes
make version-notes
```

### Version Synchronization

The version is managed in a single source of truth (`src/burly_mcp/__init__.py`) and automatically synchronized across:

- Python package metadata
- Docker image labels
- Git tags
- Release documentation

## Build and Distribution

### Package Building

The build process creates multiple distribution formats:

```bash
# Clean build artifacts
make build-clean

# Build and validate Python package
make build-package

# Test package installation
make build-test

# Test Docker build
make build-docker

# Run complete validation
make build-validate
```

### Distribution Targets

#### PyPI (Python Package Index)

- **Production**: [pypi.org/project/burly-mingo-mcp](https://pypi.org/project/burly-mingo-mcp)
- **Test**: [test.pypi.org/project/burly-mingo-mcp](https://test.pypi.org/project/burly-mingo-mcp)

```bash
# Install from PyPI
pip install burly-mingo-mcp

# Install specific version
pip install burly-mingo-mcp==1.2.3

# Install from Test PyPI (prereleases)
pip install -i https://test.pypi.org/simple/ burly-mingo-mcp
```

#### GitHub Container Registry

- **Registry**: `ghcr.io/wolfeitz/burlymcp`
- **Platforms**: `linux/amd64`, `linux/arm64`

```bash
# Pull latest release
docker pull ghcr.io/wolfeitz/burlymcp:latest

# Pull specific version
docker pull ghcr.io/wolfeitz/burlymcp:1.2.3

# Run container
docker run ghcr.io/wolfeitz/burlymcp:latest
```

## Release Pipeline Details

### 1. Version Determination

The pipeline automatically determines the appropriate version bump by analyzing commit messages since the last tag:

- Commits with `feat!:` or `BREAKING CHANGE:` → **major** bump
- Commits with `feat:` → **minor** bump  
- Commits with `fix:` → **patch** bump
- No conventional commits → no release

### 2. Pre-Release Validation

Before creating a release, the pipeline runs the complete CI suite:

- ✅ Unit tests with coverage validation
- ✅ Integration tests with Docker
- ✅ Security scanning (Bandit, pip-audit, Trivy)
- ✅ Code quality checks (linting, type checking)

### 3. Release Creation

If validation passes:

1. **Version bump**: Updates `__init__.py` with new version
2. **Git tag**: Creates annotated tag (e.g., `v1.2.3`)
3. **Release notes**: Generates changelog from commit history
4. **GitHub release**: Creates release with generated notes

### 4. Package Publishing

#### Python Package (PyPI)

1. **Build**: Creates wheel and source distribution
2. **Validate**: Runs `twine check` and installation tests
3. **Test**: Validates package in clean environments (Python 3.11, 3.12)
4. **Publish**: Uploads to PyPI (or Test PyPI for prereleases)
5. **Verify**: Tests installation from published package

#### Docker Images

1. **Multi-platform build**: Builds for `linux/amd64` and `linux/arm64`
2. **Security scan**: Scans with Trivy for vulnerabilities
3. **SBOM generation**: Creates Software Bill of Materials
4. **Registry push**: Publishes to GitHub Container Registry
5. **Validation**: Tests image functionality across platforms

### 5. Post-Release Validation

After publishing:

1. **Artifact validation**: Verifies all packages are accessible
2. **Installation testing**: Tests installation from public registries
3. **Release updates**: Updates GitHub release with artifact links
4. **Documentation**: Updates package registry descriptions

## Security and Compliance

### Security Scanning

All releases undergo comprehensive security scanning:

- **Code analysis**: Bandit for Python security issues
- **Dependency scanning**: pip-audit and Safety for known vulnerabilities
- **Container scanning**: Trivy for Docker image vulnerabilities
- **Supply chain**: SBOM generation and provenance attestations

### Secrets Management

The release pipeline uses secure secret management:

- **PyPI tokens**: Stored as GitHub repository secrets
- **Docker registry**: Uses GitHub token with appropriate permissions
- **Trusted publishing**: Uses OIDC for PyPI authentication (when available)

### Compliance Features

- **Reproducible builds**: Deterministic build process with locked dependencies
- **Audit trail**: Complete history of all releases and changes
- **Vulnerability tracking**: Automated scanning and reporting
- **License compliance**: Proper license headers and attribution

## Troubleshooting

### Common Issues

#### Release Not Triggered

**Problem**: Pushed to main but no release was created

**Solutions**:
1. Check commit messages follow conventional format
2. Verify no CI failures in the pipeline
3. Check if changes are in ignored paths (docs, README, etc.)

#### Build Failures

**Problem**: Package build or validation fails

**Solutions**:
1. Run local validation: `make build-validate`
2. Check build logs for specific errors
3. Verify all dependencies are properly specified
4. Test in clean environment: `make build-test`

#### Security Scan Failures

**Problem**: Security scans block the release

**Solutions**:
1. Review security scan results in GitHub Security tab
2. Update vulnerable dependencies: `pip-audit --fix`
3. Address code security issues identified by Bandit
4. Update base Docker images if container scan fails

#### Version Conflicts

**Problem**: Version mismatch between different components

**Solutions**:
1. Verify version in `__init__.py` is correct
2. Check that version bump was applied properly
3. Ensure no manual version changes conflict with automation

### Getting Help

1. **Check the logs**: Review GitHub Actions workflow logs
2. **Validate locally**: Use `make prepare-distribution` to catch issues early
3. **Review documentation**: Check this guide and inline comments
4. **Open an issue**: Create a GitHub issue with detailed error information

## Configuration

### Required Secrets

Configure these secrets in your GitHub repository:

```bash
# PyPI publishing
PYPI_API_TOKEN          # Production PyPI token
TEST_PYPI_API_TOKEN     # Test PyPI token (optional)

# Docker Hub (optional, for README updates)
DOCKERHUB_USERNAME      # Docker Hub username
DOCKERHUB_TOKEN         # Docker Hub access token
```

### Environment Variables

The release process can be customized with these environment variables:

```bash
# Version management
VERSION_PATTERN="v*"           # Git tag pattern for version detection
MIN_COVERAGE=80               # Minimum test coverage threshold

# Build configuration  
PYTHON_VERSION="3.12"         # Python version for builds
DOCKER_PLATFORMS="linux/amd64,linux/arm64"  # Target platforms

# Security settings
SECURITY_SCAN_LEVEL="HIGH"    # Minimum severity level for scan failures
VULNERABILITY_DB_UPDATE=true  # Update vulnerability database before scanning
```

## Best Practices

### Commit Messages

Use conventional commit format for automatic version determination:

```bash
# Good examples
git commit -m "feat: add Docker health check endpoint"
git commit -m "fix: resolve memory leak in policy engine"  
git commit -m "docs: update API documentation"
git commit -m "chore: update dependencies"

# Breaking changes
git commit -m "feat!: redesign configuration API"
git commit -m "fix: correct behavior

BREAKING CHANGE: The configuration format has changed"
```

### Release Timing

- **Regular releases**: Aim for regular, small releases rather than large batches
- **Security updates**: Release security fixes as patch versions immediately
- **Feature releases**: Group related features into minor version releases
- **Breaking changes**: Plan major version releases carefully with migration guides

### Testing Strategy

- **Local validation**: Always run `make prepare-distribution` before pushing
- **Prerelease testing**: Use prerelease versions for testing in staging environments
- **Rollback plan**: Keep previous versions available for quick rollback if needed

### Documentation

- **Changelog**: Rely on automated changelog generation from commit messages
- **Migration guides**: Write manual migration guides for breaking changes
- **API documentation**: Keep API docs updated with code changes
- **Release notes**: Review and enhance generated release notes when needed