#!/usr/bin/env python3
"""
Security Validation Script for Burly MCP

This script validates the security configuration of the restructured Burly MCP project
according to the requirements and best practices outlined in the security documentation.

Usage:
    python scripts/security-validation.py [--fix] [--report-format json|text]
"""

import argparse
import json
import os
import stat
import sys
import yaml
from pathlib import Path
from typing import Dict, List, Any, Optional
import subprocess
import re

class SecurityValidator:
    """Validates security configuration for Burly MCP"""
    
    def __init__(self, project_root: Path):
        self.project_root = project_root
        self.issues: List[Dict[str, Any]] = []
        self.warnings: List[Dict[str, Any]] = []
        self.passed: List[Dict[str, Any]] = []
    
    def add_issue(self, category: str, severity: str, message: str, file_path: Optional[str] = None, fix_suggestion: Optional[str] = None):
        """Add a security issue"""
        issue = {
            'category': category,
            'severity': severity,
            'message': message,
            'file_path': file_path,
            'fix_suggestion': fix_suggestion
        }
        
        if severity in ['CRITICAL', 'HIGH']:
            self.issues.append(issue)
        elif severity == 'MEDIUM':
            self.warnings.append(issue)
        else:
            self.passed.append(issue)
    
    def validate_file_permissions(self) -> None:
        """Validate file permissions for security-sensitive files"""
        print("Validating file permissions...")
        
        # Check .env files
        env_files = ['.env', '.env.local', '.env.production']
        for env_file in env_files:
            env_path = self.project_root / env_file
            if env_path.exists():
                file_stat = env_path.stat()
                perms = stat.filemode(file_stat.st_mode)
                octal_perms = oct(file_stat.st_mode)[-3:]
                
                if octal_perms != '600':
                    self.add_issue(
                        'file_permissions',
                        'HIGH',
                        f'Environment file {env_file} has insecure permissions: {perms}',
                        str(env_path),
                        f'chmod 600 {env_path}'
                    )
                else:
                    self.add_issue(
                        'file_permissions',
                        'LOW',
                        f'Environment file {env_file} has secure permissions: {perms}',
                        str(env_path)
                    )
        
        # Check config directory permissions
        config_dir = self.project_root / 'config'
        if config_dir.exists():
            for config_file in config_dir.rglob('*'):
                if config_file.is_file():
                    file_stat = config_file.stat()
                    octal_perms = oct(file_stat.st_mode)[-3:]
                    
                    if int(octal_perms) > 644:
                        self.add_issue(
                            'file_permissions',
                            'MEDIUM',
                            f'Config file has overly permissive permissions: {config_file}',
                            str(config_file),
                            f'chmod 644 {config_file}'
                        )
    
    def validate_docker_configuration(self) -> None:
        """Validate Docker security configuration"""
        print("Validating Docker configuration...")
        
        # Check example docker-compose files
        compose_files = ['examples/compose/docker-compose.yml', 'examples/compose/docker-compose.override.yml', 'docker/docker-compose.yml']
        
        for compose_file in compose_files:
            compose_path = self.project_root / compose_file
            if compose_path.exists():
                try:
                    with open(compose_path, 'r') as f:
                        compose_config = yaml.safe_load(f)
                    
                    self._validate_compose_security(compose_config, str(compose_path))
                    
                except yaml.YAMLError as e:
                    self.add_issue(
                        'docker_config',
                        'MEDIUM',
                        f'Invalid YAML in {compose_file}: {e}',
                        str(compose_path)
                    )
    
    def _validate_compose_security(self, config: Dict[str, Any], file_path: str) -> None:
        """Validate Docker Compose security settings"""
        services = config.get('services', {})
        
        for service_name, service_config in services.items():
            if 'burly' in service_name.lower() or 'mcp' in service_name.lower():
                # Check user configuration
                user = service_config.get('user')
                if not user or user in ['root', '0', '0:0']:
                    self.add_issue(
                        'docker_security',
                        'CRITICAL',
                        f'Service {service_name} running as root user',
                        file_path,
                        'Add "user: 1000:1000" to service configuration'
                    )
                
                # Check privileged mode
                if service_config.get('privileged'):
                    self.add_issue(
                        'docker_security',
                        'CRITICAL',
                        f'Service {service_name} running in privileged mode',
                        file_path,
                        'Remove "privileged: true" from service configuration'
                    )
                
                # Check capability dropping
                cap_drop = service_config.get('cap_drop', [])
                if 'ALL' not in cap_drop:
                    self.add_issue(
                        'docker_security',
                        'HIGH',
                        f'Service {service_name} not dropping all capabilities',
                        file_path,
                        'Add "cap_drop: [ALL]" to service configuration'
                    )
                
                # Check read-only filesystem
                if not service_config.get('read_only'):
                    self.add_issue(
                        'docker_security',
                        'MEDIUM',
                        f'Service {service_name} not using read-only filesystem',
                        file_path,
                        'Add "read_only: true" to service configuration'
                    )
                
                # Check security options
                security_opt = service_config.get('security_opt', [])
                if 'no-new-privileges:true' not in security_opt:
                    self.add_issue(
                        'docker_security',
                        'HIGH',
                        f'Service {service_name} allows new privileges',
                        file_path,
                        'Add "no-new-privileges:true" to security_opt'
                    )
                
                # Check for exposed ports
                ports = service_config.get('ports', [])
                if ports:
                    self.add_issue(
                        'docker_security',
                        'MEDIUM',
                        f'Service {service_name} exposes ports: {ports}',
                        file_path,
                        'Remove port mappings for MCP over stdio'
                    )
    
    def validate_environment_configuration(self) -> None:
        """Validate environment variable security"""
        print("Validating environment configuration...")
        
        # Check .env.example for security warnings
        env_example = self.project_root / '.env.example'
        if env_example.exists():
            with open(env_example, 'r') as f:
                content = f.read()
            
            # Check for security warnings
            if 'WARNING:' not in content:
                self.add_issue(
                    'env_config',
                    'MEDIUM',
                    'No security warnings found in .env.example',
                    str(env_example),
                    'Add security warnings for sensitive variables'
                )
            
            # Check for hardcoded secrets
            secret_patterns = [
                r'TOKEN=\w+',
                r'PASSWORD=\w+',
                r'SECRET=\w+',
                r'KEY=\w+'
            ]
            
            for pattern in secret_patterns:
                if re.search(pattern, content):
                    self.add_issue(
                        'env_config',
                        'HIGH',
                        f'Potential hardcoded secret in .env.example: {pattern}',
                        str(env_example),
                        'Use placeholder values and _FILE suffixes for secrets'
                    )
        
        # Check for actual .env files with secrets
        env_files = ['.env', '.env.local', '.env.production']
        for env_file in env_files:
            env_path = self.project_root / env_file
            if env_path.exists():
                with open(env_path, 'r') as f:
                    content = f.read()
                
                # Check for direct secret assignment (should use _FILE)
                direct_secret_patterns = [
                    r'GOTIFY_TOKEN=\w+',
                    r'MCP_AUTH_TOKEN=\w+',
                    r'WEBHOOK_TOKEN=\w+'
                ]
                
                for pattern in direct_secret_patterns:
                    if re.search(pattern, content):
                        self.add_issue(
                            'env_config',
                            'CRITICAL',
                            f'Direct secret assignment in {env_file}: {pattern}',
                            str(env_path),
                            'Use _FILE suffix and Docker secrets instead'
                        )
    
    def validate_policy_configuration(self) -> None:
        """Validate security policy configuration"""
        print("Validating policy configuration...")
        
        policy_files = list((self.project_root / 'config' / 'policy').glob('*.yaml'))
        policy_files.extend(list((self.project_root / 'config' / 'policy').glob('*.yml')))
        
        for policy_file in policy_files:
            try:
                with open(policy_file, 'r') as f:
                    policy_config = yaml.safe_load(f)
                
                self._validate_policy_security(policy_config, str(policy_file))
                
            except yaml.YAMLError as e:
                self.add_issue(
                    'policy_config',
                    'HIGH',
                    f'Invalid YAML in policy file {policy_file}: {e}',
                    str(policy_file)
                )
    
    def _validate_policy_security(self, config: Dict[str, Any], file_path: str) -> None:
        """Validate policy security settings"""
        tools = config.get('tools', {})
        
        # Check for dangerous tools
        dangerous_tools = ['docker_exec', 'system_exec', 'shell_exec']
        for tool_name, tool_config in tools.items():
            if any(dangerous in tool_name.lower() for dangerous in dangerous_tools):
                if tool_config.get('enabled', False):
                    confirmation_required = tool_config.get('confirmation_required', False)
                    if not confirmation_required:
                        self.add_issue(
                            'policy_security',
                            'CRITICAL',
                            f'Dangerous tool {tool_name} enabled without confirmation',
                            file_path,
                            'Set "confirmation_required: true" for dangerous tools'
                        )
        
        # Check global settings
        global_settings = config.get('global_settings', {})
        
        # Check audit logging
        if not global_settings.get('audit_all_operations', False):
            self.add_issue(
                'policy_security',
                'HIGH',
                'Audit logging not enabled for all operations',
                file_path,
                'Set "audit_all_operations: true" in global_settings'
            )
        
        # Check fail secure setting
        if not global_settings.get('fail_secure', True):
            self.add_issue(
                'policy_security',
                'HIGH',
                'Fail secure not enabled',
                file_path,
                'Set "fail_secure: true" in global_settings'
            )
    
    def validate_package_structure(self) -> None:
        """Validate Python package security structure"""
        print("Validating package structure...")
        
        # Check for proper package structure
        src_dir = self.project_root / 'src' / 'burly_mcp'
        if not src_dir.exists():
            self.add_issue(
                'package_structure',
                'CRITICAL',
                'Source package directory not found: src/burly_mcp/',
                None,
                'Ensure proper package structure with src/burly_mcp/'
            )
            return
        
        # Check for __init__.py files
        required_init_files = [
            'src/burly_mcp/__init__.py',
            'src/burly_mcp/server/__init__.py',
            'src/burly_mcp/tools/__init__.py',
            'src/burly_mcp/policy/__init__.py',
            'src/burly_mcp/notifications/__init__.py'
        ]
        
        for init_file in required_init_files:
            init_path = self.project_root / init_file
            if not init_path.exists():
                self.add_issue(
                    'package_structure',
                    'HIGH',
                    f'Missing __init__.py file: {init_file}',
                    str(init_path),
                    f'Create {init_file} with proper exports'
                )
        
        # Check for security module
        security_module = src_dir / 'security.py'
        if not security_module.exists():
            self.add_issue(
                'package_structure',
                'MEDIUM',
                'Security module not found: src/burly_mcp/security.py',
                str(security_module),
                'Create security module with input validation and path checking'
            )
    
    def validate_ci_security(self) -> None:
        """Validate CI/CD security configuration"""
        print("Validating CI/CD security...")
        
        # Check GitHub Actions workflows
        workflows_dir = self.project_root / '.github' / 'workflows'
        if workflows_dir.exists():
            for workflow_file in workflows_dir.glob('*.yml'):
                with open(workflow_file, 'r') as f:
                    workflow_config = yaml.safe_load(f)
                
                self._validate_workflow_security(workflow_config, str(workflow_file))
    
    def _validate_workflow_security(self, config: Dict[str, Any], file_path: str) -> None:
        """Validate GitHub Actions workflow security"""
        jobs = config.get('jobs', {})
        
        security_tools_found = False
        
        for job_name, job_config in jobs.items():
            steps = job_config.get('steps', [])
            
            for step in steps:
                step_name = step.get('name', '').lower()
                step_run = step.get('run', '').lower()
                
                # Check for security scanning tools
                if any(tool in step_name or tool in step_run for tool in ['bandit', 'trivy', 'pip-audit', 'safety']):
                    security_tools_found = True
                    break
        
        if not security_tools_found:
            self.add_issue(
                'ci_security',
                'HIGH',
                f'No security scanning tools found in workflow: {file_path}',
                file_path,
                'Add security scanning steps (bandit, trivy, pip-audit)'
            )
    
    def validate_dependency_security(self) -> None:
        """Validate dependency security"""
        print("Validating dependency security...")
        
        # Check if pip-audit is available and run it
        try:
            result = subprocess.run(
                ['pip-audit', '--desc', '--format=json'],
                capture_output=True,
                text=True,
                cwd=self.project_root
            )
            
            if result.returncode == 0:
                # No vulnerabilities found
                self.add_issue(
                    'dependency_security',
                    'LOW',
                    'No known vulnerabilities found in dependencies',
                    None
                )
            else:
                # Parse vulnerabilities
                try:
                    audit_data = json.loads(result.stdout)
                    vuln_count = len(audit_data.get('vulnerabilities', []))
                    
                    if vuln_count > 0:
                        self.add_issue(
                            'dependency_security',
                            'HIGH',
                            f'Found {vuln_count} known vulnerabilities in dependencies',
                            None,
                            'Run "pip-audit --fix" to update vulnerable packages'
                        )
                except json.JSONDecodeError:
                    self.add_issue(
                        'dependency_security',
                        'MEDIUM',
                        'Could not parse pip-audit output',
                        None
                    )
        
        except FileNotFoundError:
            self.add_issue(
                'dependency_security',
                'MEDIUM',
                'pip-audit not available for dependency scanning',
                None,
                'Install pip-audit: pip install pip-audit'
            )
    
    def run_all_validations(self) -> None:
        """Run all security validations"""
        print("Running comprehensive security validation...")
        print("=" * 50)
        
        self.validate_file_permissions()
        self.validate_docker_configuration()
        self.validate_environment_configuration()
        self.validate_policy_configuration()
        self.validate_package_structure()
        self.validate_ci_security()
        self.validate_dependency_security()
        
        print("=" * 50)
        print("Security validation complete!")
    
    def generate_report(self, format_type: str = 'text') -> str:
        """Generate security validation report"""
        if format_type == 'json':
            return json.dumps({
                'issues': self.issues,
                'warnings': self.warnings,
                'passed': self.passed,
                'summary': {
                    'critical_issues': len([i for i in self.issues if i['severity'] == 'CRITICAL']),
                    'high_issues': len([i for i in self.issues if i['severity'] == 'HIGH']),
                    'medium_issues': len([i for i in self.warnings if i['severity'] == 'MEDIUM']),
                    'total_issues': len(self.issues) + len(self.warnings)
                }
            }, indent=2)
        
        # Text format
        report = []
        report.append("BURLY MCP SECURITY VALIDATION REPORT")
        report.append("=" * 50)
        
        # Summary
        critical_count = len([i for i in self.issues if i['severity'] == 'CRITICAL'])
        high_count = len([i for i in self.issues if i['severity'] == 'HIGH'])
        medium_count = len([i for i in self.warnings if i['severity'] == 'MEDIUM'])
        
        report.append(f"SUMMARY:")
        report.append(f"  Critical Issues: {critical_count}")
        report.append(f"  High Issues: {high_count}")
        report.append(f"  Medium Issues: {medium_count}")
        report.append(f"  Total Issues: {len(self.issues) + len(self.warnings)}")
        report.append("")
        
        # Critical and High Issues
        if self.issues:
            report.append("CRITICAL AND HIGH SEVERITY ISSUES:")
            report.append("-" * 40)
            for issue in self.issues:
                report.append(f"[{issue['severity']}] {issue['category']}: {issue['message']}")
                if issue['file_path']:
                    report.append(f"  File: {issue['file_path']}")
                if issue['fix_suggestion']:
                    report.append(f"  Fix: {issue['fix_suggestion']}")
                report.append("")
        
        # Medium Issues (Warnings)
        if self.warnings:
            report.append("MEDIUM SEVERITY ISSUES (WARNINGS):")
            report.append("-" * 40)
            for warning in self.warnings:
                report.append(f"[{warning['severity']}] {warning['category']}: {warning['message']}")
                if warning['file_path']:
                    report.append(f"  File: {warning['file_path']}")
                if warning['fix_suggestion']:
                    report.append(f"  Fix: {warning['fix_suggestion']}")
                report.append("")
        
        # Passed Checks
        if self.passed:
            report.append("PASSED SECURITY CHECKS:")
            report.append("-" * 40)
            for passed in self.passed:
                report.append(f"[PASS] {passed['category']}: {passed['message']}")
            report.append("")
        
        return "\n".join(report)

def main():
    parser = argparse.ArgumentParser(description='Validate Burly MCP security configuration')
    parser.add_argument('--project-root', type=Path, default=Path.cwd(),
                        help='Project root directory (default: current directory)')
    parser.add_argument('--report-format', choices=['text', 'json'], default='text',
                        help='Report format (default: text)')
    parser.add_argument('--output', type=Path,
                        help='Output file for report (default: stdout)')
    
    args = parser.parse_args()
    
    # Validate project root
    if not args.project_root.exists():
        print(f"Error: Project root directory not found: {args.project_root}")
        sys.exit(1)
    
    # Run validation
    validator = SecurityValidator(args.project_root)
    validator.run_all_validations()
    
    # Generate report
    report = validator.generate_report(args.report_format)
    
    # Output report
    if args.output:
        with open(args.output, 'w') as f:
            f.write(report)
        print(f"Security report written to: {args.output}")
    else:
        print(report)
    
    # Exit with error code if critical or high issues found
    critical_count = len([i for i in validator.issues if i['severity'] == 'CRITICAL'])
    high_count = len([i for i in validator.issues if i['severity'] == 'HIGH'])
    
    if critical_count > 0:
        print(f"\nERROR: {critical_count} critical security issues found!")
        sys.exit(2)
    elif high_count > 0:
        print(f"\nWARNING: {high_count} high severity security issues found!")
        sys.exit(1)
    else:
        print("\nSecurity validation passed!")
        sys.exit(0)

if __name__ == '__main__':
    main()