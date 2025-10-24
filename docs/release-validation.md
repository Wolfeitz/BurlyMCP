# Release Validation System

This document describes the comprehensive release validation system for Burly MCP, which ensures that all releases are thoroughly tested, validated, and monitored before and after deployment.

## Overview

The release validation system consists of four main components:

1. **Release Validation Pipeline** - Automated testing of release artifacts
2. **Release Rollback Procedures** - Automated rollback capabilities for failed releases
3. **Release Monitoring** - Real-time monitoring of release health and deployment status
4. **Post-Release Verification** - Comprehensive verification of deployed artifacts

## Components

### 1. Release Validation Pipeline

**File**: `.github/workflows/release-validation.yml`

The release validation pipeline runs automatically as part of the release process and performs comprehensive testing of all release artifacts.

#### Validation Checks

- **PyPI Package Validation**
  - Cross-platform installation testing (Ubuntu, Windows, macOS)
  - Multi-Python version testing (3.11, 3.12)
  - Package functionality verification
  - Console script testing
  - Import validation

- **Docker Image Validation**
  - Multi-platform image testing (linux/amd64, linux/arm64)
  - Container functionality verification
  - Security configuration validation
  - Performance benchmarking

- **Release Artifacts Validation**
  - Checksum verification
  - Package metadata validation
  - Asset completeness checking

- **Security Validation**
  - Dependency vulnerability scanning
  - Docker image security scanning
  - SBOM generation and validation

- **End-to-End Functionality Testing**
  - Core module import testing
  - Configuration loading validation
  - Tool registry functionality

#### Usage

The validation pipeline runs automatically during releases but can also be triggered manually:

```bash
# Trigger via GitHub CLI
gh workflow run release-validation.yml -f version=1.2.3 -f release_tag=v1.2.3
```

### 2. Release Rollback Procedures

**File**: `scripts/release_rollback.py`

Provides automated rollback capabilities for failed releases, including reverting version changes, removing tags, and cleaning up artifacts.

#### Features

- **Rollback Planning**: Analyze release state and create rollback execution plan
- **Git Operations**: Remove tags, revert commits, reset to previous versions
- **Artifact Cleanup**: Remove GitHub releases, warn about PyPI/Docker artifacts
- **Safety Checks**: Validate repository state before rollback
- **Dry Run Mode**: Preview rollback actions without executing them

#### Usage

```bash
# Create rollback plan
python scripts/release_rollback.py plan 1.2.3
make release-rollback-plan VERSION=1.2.3

# Execute rollback (with confirmation)
python scripts/release_rollback.py execute 1.2.3
make release-rollback VERSION=1.2.3

# Dry run (preview actions)
python scripts/release_rollback.py execute 1.2.3 --dry-run

# Force rollback (skip safety checks)
python scripts/release_rollback.py execute 1.2.3 --force
```

#### Rollback Capabilities

| Component | Automatic | Manual Required |
|-----------|-----------|-----------------|
| Git tags | ✅ Yes | - |
| Version files | ✅ Yes | - |
| GitHub releases | ✅ Yes | - |
| Git commits | ✅ Yes | - |
| PyPI packages | ❌ No | ⚠️ Manual |
| Docker images | ❌ No | ⚠️ Manual |

### 3. Release Monitoring

**File**: `scripts/release_monitor.py`

Provides real-time monitoring of release health and deployment status with automated health scoring.

#### Features

- **Multi-Component Monitoring**: GitHub releases, PyPI packages, Docker images, CI pipelines
- **Health Scoring**: 0-100 health score based on component availability and functionality
- **Continuous Monitoring**: Monitor releases over time with configurable intervals
- **Issue Detection**: Identify and report specific issues with releases
- **Progress Tracking**: Track deployment progress and completion

#### Usage

```bash
# Single health check
python scripts/release_monitor.py check 1.2.3
make release-check VERSION=1.2.3

# Continuous monitoring (30 minutes, 60-second intervals)
python scripts/release_monitor.py monitor 1.2.3
make release-monitor VERSION=1.2.3

# Custom monitoring duration and interval
python scripts/release_monitor.py monitor 1.2.3 --duration 60 --interval 30

# Save monitoring data
python scripts/release_monitor.py monitor 1.2.3 --output monitoring_report.json
```

#### Health Scoring

The health score is calculated based on:

- **GitHub Release** (25 points): Release exists and is published
- **PyPI Package** (25 points): Package is available and installable
- **Docker Image** (25 points): Image exists and is functional (+5 for multi-platform)
- **CI Pipeline** (25 points): Latest pipeline run was successful

#### Health Status Levels

- **🟢 100% - Fully Healthy**: All components working perfectly
- **🟡 80-99% - Mostly Healthy**: Minor issues, likely to resolve automatically
- **🟠 50-79% - Partially Healthy**: Significant issues, manual intervention may be needed
- **🔴 <50% - Unhealthy**: Critical issues, immediate attention required

### 4. Post-Release Verification

**File**: `scripts/post_release_verification.py`

Performs comprehensive verification of released artifacts to ensure they work correctly in real-world scenarios.

#### Verification Checks

- **PyPI Installation Verification**
  - Clean environment installation testing
  - Cross-platform compatibility (Windows, macOS, Linux)
  - Multi-Python version support
  - Console script functionality
  - Package import validation

- **Docker Functionality Verification**
  - Image pull and execution testing
  - Multi-platform support validation
  - Performance benchmarking
  - Security configuration verification

- **GitHub Release Verification**
  - Release completeness checking
  - Asset availability and integrity
  - Checksum validation
  - Release notes quality

- **Documentation Verification**
  - Version reference updates
  - Installation guide accuracy
  - API documentation completeness

- **Security Compliance Verification**
  - Vulnerability scanning
  - Dependency security analysis
  - Container security validation

#### Usage

```bash
# Full verification
python scripts/post_release_verification.py verify 1.2.3
make release-verify VERSION=1.2.3

# Component-specific verification
python scripts/post_release_verification.py pypi 1.2.3
python scripts/post_release_verification.py docker 1.2.3
python scripts/post_release_verification.py security 1.2.3
```

#### Verification Report

The verification generates a comprehensive report including:

- Executive summary with overall success rate
- Detailed results for each verification check
- Performance metrics and security findings
- Recommendations based on results
- Pass/fail status for each component

## Integration with Release Process

### Automated Integration

The validation system is fully integrated into the release pipeline:

1. **Pre-Release**: Version validation and build testing
2. **Release Creation**: Automated tagging and artifact generation
3. **Artifact Publishing**: PyPI and Docker registry publishing
4. **Release Validation**: Comprehensive artifact testing
5. **Post-Release Verification**: End-to-end functionality validation
6. **Monitoring**: Continuous health monitoring

### Manual Operations

Some operations require manual intervention:

- **Rollback Execution**: Requires explicit confirmation
- **PyPI Package Removal**: Cannot be automated (PyPI policy)
- **Docker Image Cleanup**: Manual removal from registries
- **Security Issue Response**: Manual assessment and patching

## Configuration

### Environment Variables

The validation system uses several environment variables:

```bash
# GitHub CLI authentication
GITHUB_TOKEN=<github_token>

# Docker registry access
DOCKER_USERNAME=<username>
DOCKER_PASSWORD=<password>

# Monitoring intervals
RELEASE_MONITOR_DURATION=30  # minutes
RELEASE_MONITOR_INTERVAL=60  # seconds
```

### Dependencies

Required tools and libraries:

- **Python 3.11+**: Core runtime
- **GitHub CLI**: Release and repository operations
- **Docker**: Container testing and validation
- **Python packages**: `requests`, `packaging`, `safety`, `pip-audit`

### Makefile Integration

All validation tools are integrated into the project Makefile:

```bash
# Release preparation
make prepare-release

# Version management
make version-bump TYPE=patch
make version-validate

# Release monitoring
make release-check VERSION=1.2.3
make release-monitor VERSION=1.2.3

# Release verification
make release-verify VERSION=1.2.3

# Rollback operations
make release-rollback-plan VERSION=1.2.3
make release-rollback VERSION=1.2.3
```

## Best Practices

### Release Validation

1. **Always run validation**: Never skip the validation pipeline
2. **Monitor actively**: Watch releases for the first 30 minutes
3. **Verify manually**: Run post-release verification for critical releases
4. **Document issues**: Record any validation failures for future improvement

### Rollback Procedures

1. **Plan first**: Always create a rollback plan before executing
2. **Use dry-run**: Preview rollback actions before execution
3. **Act quickly**: Execute rollbacks within 1 hour of detection
4. **Communicate**: Notify stakeholders of rollback actions

### Monitoring

1. **Set alerts**: Configure notifications for health score drops
2. **Track trends**: Monitor health scores over time
3. **Investigate issues**: Follow up on any validation failures
4. **Update thresholds**: Adjust health scoring based on experience

## Troubleshooting

### Common Issues

#### Validation Pipeline Failures

**PyPI Installation Failures**
- Check PyPI package availability and propagation
- Verify package metadata and dependencies
- Test in clean environments

**Docker Image Issues**
- Verify image registry accessibility
- Check multi-platform build success
- Validate container security settings

**Security Scan Failures**
- Review vulnerability reports
- Update dependencies if needed
- Consider security exceptions for false positives

#### Rollback Issues

**Git Operation Failures**
- Ensure clean working directory
- Verify branch permissions
- Check remote repository access

**Artifact Cleanup Issues**
- Manual PyPI package handling required
- Docker registry cleanup may need manual intervention
- GitHub release removal requires proper permissions

#### Monitoring Issues

**Health Score Anomalies**
- Check component availability
- Verify network connectivity
- Review API rate limits

**False Positives**
- Adjust health scoring thresholds
- Update component check logic
- Consider temporary service outages

### Support

For issues with the release validation system:

1. Check the GitHub Actions logs for detailed error information
2. Review the generated reports for specific failure details
3. Use the dry-run modes to test operations safely
4. Consult the troubleshooting section above
5. Create an issue in the repository with detailed logs

## Future Enhancements

Planned improvements to the validation system:

- **Automated Rollback Triggers**: Automatic rollback on critical failures
- **Enhanced Monitoring**: Integration with external monitoring systems
- **Performance Baselines**: Automated performance regression detection
- **User Acceptance Testing**: Automated end-user scenario testing
- **Notification Integration**: Slack/email notifications for validation events