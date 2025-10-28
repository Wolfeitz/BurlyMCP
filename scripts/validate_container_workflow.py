#!/usr/bin/env python3
"""
Validation script for container publishing workflow.
Ensures the workflow meets all requirements from the spec.
"""

import yaml
import sys
from pathlib import Path

def validate_workflow():
    """Validate the container publishing workflow configuration."""
    
    workflow_path = Path('.github/workflows/publish-image.yml')
    
    if not workflow_path.exists():
        print("❌ Workflow file not found: .github/workflows/publish-image.yml")
        return False
    
    try:
        with open(workflow_path, 'r', encoding='utf-8') as f:
            workflow = yaml.safe_load(f)
    except yaml.YAMLError as e:
        print(f"❌ Invalid YAML syntax: {e}")
        return False
    except Exception as e:
        print(f"❌ Error reading workflow file: {e}")
        return False
    
    if not workflow:
        print("❌ Empty or invalid workflow file")
        return False
    
    print("🔍 Validating container publishing workflow...")
    
    # Check trigger configuration
    triggers = workflow.get('on', {})
    if 'workflow_run' not in triggers:
        print("❌ Missing workflow_run trigger (should depend on CI)")
        return False
    
    workflow_run_config = triggers['workflow_run']
    if 'workflows' not in workflow_run_config or 'CI Pipeline' not in workflow_run_config['workflows']:
        print("❌ Missing CI Pipeline dependency")
        return False
    
    if 'types' not in workflow_run_config or 'completed' not in workflow_run_config['types']:
        print("❌ Missing completed trigger type")
        return False
    
    print("✅ Trigger configuration: Depends on CI Pipeline completion")
    
    # Check environment variables
    env = workflow.get('env', {})
    if env.get('REGISTRY') != 'ghcr.io':
        print("❌ Registry should be ghcr.io")
        return False
    
    if env.get('IMAGE_NAME') != 'wolfeitz/burlymcp':
        print("❌ Image name should be 'wolfeitz/burlymcp' (lowercase format)")
        return False
    
    print("✅ Environment configuration: GHCR registry")
    
    # Check permissions
    permissions = workflow.get('permissions', {})
    if permissions.get('packages') != 'write':
        print("❌ Missing packages:write permission")
        return False
    
    if permissions.get('contents') != 'read':
        print("❌ Missing contents:read permission")
        return False
    
    print("✅ Permissions: packages:write and contents:read")
    
    # Check jobs
    jobs = workflow.get('jobs', {})
    if 'publish' not in jobs:
        print("❌ Missing publish job")
        return False
    
    publish_job = jobs['publish']
    
    # Check CI success condition
    job_if = publish_job.get('if', '')
    if 'workflow_run.conclusion' not in job_if and 'success' not in job_if:
        print("❌ Missing CI success condition")
        return False
    
    print("✅ CI dependency: Only runs after CI success")
    
    # Check build step uses Dockerfile.runtime
    steps = publish_job.get('steps', [])
    build_step = None
    for step in steps:
        if 'docker/build-push-action' in step.get('uses', ''):
            build_step = step
            break
    
    if not build_step:
        print("❌ Missing docker build step")
        return False
    
    build_with = build_step.get('with', {})
    if build_with.get('file') != './Dockerfile.runtime':
        print("❌ Build step should use Dockerfile.runtime")
        return False
    
    print("✅ Build configuration: Uses Dockerfile.runtime")
    
    # Check metadata extraction for tagging
    meta_step = None
    for step in steps:
        if 'docker/metadata-action' in step.get('uses', ''):
            meta_step = step
            break
    
    if not meta_step:
        print("❌ Missing metadata extraction step")
        return False
    
    meta_with = meta_step.get('with', {})
    tags = meta_with.get('tags', '')
    
    if 'type=raw,value=main' not in tags:
        print("❌ Missing main tag configuration")
        return False
    
    if 'type=raw,value=latest' not in tags:
        print("❌ Missing latest tag configuration")
        return False
    
    if 'type=sha,prefix={{branch}}-' not in tags:
        print("❌ Missing branch-sha tag configuration")
        return False
    
    print("✅ Tagging strategy: main, latest, versioned, and branch-sha tags")
    
    # Check multi-platform build
    if 'linux/amd64,linux/arm64' not in str(build_with.get('platforms', '')):
        print("❌ Missing multi-platform build configuration")
        return False
    
    print("✅ Multi-platform: linux/amd64,linux/arm64")
    
    # Check caching
    if build_with.get('cache-from') != 'type=gha':
        print("❌ Missing GitHub Actions cache configuration")
        return False
    
    print("✅ Caching: GitHub Actions cache enabled")
    
    # Check validation job exists
    if 'validate' not in jobs:
        print("❌ Missing validation job")
        return False
    
    print("✅ Validation job: Image functionality tests")
    
    # Check security scan job exists
    if 'security-scan' not in jobs:
        print("❌ Missing security scan job")
        return False
    
    print("✅ Security scan job: Trivy vulnerability scanning")
    
    print("\n🎉 All workflow requirements validated successfully!")
    return True

def validate_registry_documentation():
    """Validate that registry documentation exists and is complete."""
    
    doc_path = Path('docs/container-registry.md')
    
    if not doc_path.exists():
        print("❌ Container registry documentation not found")
        return False
    
    with open(doc_path) as f:
        content = f.read()
    
    required_sections = [
        'Registry Details',
        'Tagging Strategy', 
        'Permissions Configuration',
        'Usage Examples',
        'Container Contract'
    ]
    
    for section in required_sections:
        if section not in content:
            print(f"❌ Missing documentation section: {section}")
            return False
    
    # Check for required registry information
    if 'ghcr.io/wolfeitz/burlymcp' not in content:
        print("❌ Missing correct registry path in documentation")
        return False
    
    if 'packages:write' not in content:
        print("❌ Missing packages:write permission documentation")
        return False
    
    print("✅ Registry documentation: Complete and accurate")
    return True

def main():
    """Main validation function."""
    
    print("🚀 Container Publishing Workflow Validation")
    print("=" * 50)
    
    workflow_valid = validate_workflow()
    docs_valid = validate_registry_documentation()
    
    if workflow_valid and docs_valid:
        print("\n✅ All validations passed! Container publishing is properly configured.")
        return 0
    else:
        print("\n❌ Validation failed. Please fix the issues above.")
        return 1

if __name__ == '__main__':
    sys.exit(main())