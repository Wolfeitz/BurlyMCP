#!/usr/bin/env python3
"""
Comprehensive YAML and JSON validation script.
Can be run manually or integrated into CI/CD pipelines.
"""

import json
import yaml
import sys
import argparse
from pathlib import Path
from typing import List, Tuple, Dict, Any
import re

class ValidationResult:
    def __init__(self):
        self.valid_files: List[str] = []
        self.invalid_files: List[Tuple[str, str]] = []  # (file, error)
        self.warnings: List[Tuple[str, str]] = []  # (file, warning)
    
    def add_valid(self, file_path: str):
        self.valid_files.append(file_path)
    
    def add_invalid(self, file_path: str, error: str):
        self.invalid_files.append((file_path, error))
    
    def add_warning(self, file_path: str, warning: str):
        self.warnings.append((file_path, warning))
    
    def has_errors(self) -> bool:
        return len(self.invalid_files) > 0
    
    def print_summary(self):
        print("📋 YAML/JSON Validation Results")
        print("=" * 40)
        
        if self.valid_files:
            print(f"\n✅ Valid Files ({len(self.valid_files)}):")
            for file_path in sorted(self.valid_files):
                print(f"  - {file_path}")
        
        if self.invalid_files:
            print(f"\n❌ Invalid Files ({len(self.invalid_files)}):")
            for file_path, error in self.invalid_files:
                print(f"  - {file_path}: {error}")
            print(f"\n💡 Tip: Fix syntax errors in the files above.")
            print("   Common issues: missing quotes, incorrect indentation, trailing commas")
        
        if self.warnings:
            print(f"\n⚠️  Warnings ({len(self.warnings)}):")
            for file_path, warning in self.warnings:
                print(f"  - {file_path}: {warning}")
        
        if not self.invalid_files and not self.warnings:
            print("\n🎉 All files passed validation!")

def validate_yaml_file(file_path: Path) -> Tuple[bool, str]:
    """Validate a single YAML file."""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
            
        # Parse YAML
        yaml.safe_load(content)
        return True, ""
        
    except yaml.YAMLError as e:
        error_msg = str(e)
        if hasattr(e, 'problem_mark'):
            mark = e.problem_mark
            error_msg = f"Line {mark.line + 1}, Column {mark.column + 1}: {e.problem}"
        return False, error_msg
    except Exception as e:
        return False, f"Error reading file: {str(e)}"

def validate_json_file(file_path: Path) -> Tuple[bool, str]:
    """Validate a single JSON file."""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
            
        # Parse JSON
        json.loads(content)
        return True, ""
        
    except json.JSONDecodeError as e:
        return False, f"Line {e.lineno}, Column {e.colno}: {e.msg}"
    except Exception as e:
        return False, f"Error reading file: {str(e)}"

def validate_toml_file(file_path: Path) -> Tuple[bool, str]:
    """Validate a single TOML file."""
    try:
        import tomllib
    except ImportError:
        try:
            import tomli as tomllib
        except ImportError:
            return True, "TOML validation skipped (tomllib/tomli not available)"
    
    try:
        with open(file_path, 'rb') as f:
            tomllib.load(f)
        return True, ""
    except Exception as e:
        return False, str(e)

def validate_github_workflow(file_path: Path, content: Dict[str, Any]) -> List[str]:
    """Validate GitHub Actions workflow structure."""
    warnings = []
    
    # Check required fields
    if 'name' not in content:
        warnings.append("Missing 'name' field (recommended)")
    
    if 'on' not in content:
        warnings.append("Missing 'on' trigger configuration")
    
    if 'jobs' not in content:
        warnings.append("Missing 'jobs' section")
    elif not isinstance(content['jobs'], dict) or not content['jobs']:
        warnings.append("Jobs section is empty or invalid")
    
    # Check job structure
    if 'jobs' in content and isinstance(content['jobs'], dict):
        for job_name, job_config in content['jobs'].items():
            if not isinstance(job_config, dict):
                warnings.append(f"Job '{job_name}' has invalid configuration")
                continue
                
            if 'runs-on' not in job_config:
                warnings.append(f"Job '{job_name}' missing 'runs-on' field")
            
            if 'steps' not in job_config:
                warnings.append(f"Job '{job_name}' missing 'steps' field")
    
    return warnings

def validate_docker_compose(file_path: Path, content: Dict[str, Any]) -> List[str]:
    """Validate Docker Compose file structure."""
    warnings = []
    
    # Check version (optional in newer compose)
    if 'version' in content:
        version = content['version']
        if isinstance(version, str) and not re.match(r'^\d+(\.\d+)?$', version):
            warnings.append("Invalid version format")
    
    # Check services
    if 'services' not in content:
        warnings.append("Missing 'services' section")
    elif not isinstance(content['services'], dict) or not content['services']:
        warnings.append("Services section is empty or invalid")
    
    return warnings

def validate_package_json(file_path: Path, content: Dict[str, Any]) -> List[str]:
    """Validate package.json structure."""
    warnings = []
    
    required_fields = ['name', 'version']
    for field in required_fields:
        if field not in content:
            warnings.append(f"Missing required field: '{field}'")
    
    # Check scripts section
    if 'scripts' in content and not isinstance(content['scripts'], dict):
        warnings.append("Scripts section should be an object")
    
    return warnings

def find_files(patterns: List[str], exclude_patterns: List[str] = None) -> List[Path]:
    """Find files matching the given patterns."""
    if exclude_patterns is None:
        exclude_patterns = [
            'node_modules/**', 
            '.git/**', 
            '__pycache__/**', 
            '.venv/**',
            '.pytest_cache/**',
            '.ruff_cache/**',
            'build/**',
            'dist/**',
            '*.egg-info/**'
        ]
    
    files = []
    for pattern in patterns:
        # Use rglob for recursive search to ensure we catch everything
        if '**' in pattern:
            files.extend(Path('.').rglob(pattern.replace('**/', '')))
        else:
            files.extend(Path('.').glob(pattern))
    
    # Filter out excluded patterns
    filtered_files = []
    for file_path in files:
        excluded = False
        file_str = str(file_path)
        
        for exclude_pattern in exclude_patterns:
            # Handle both glob patterns and simple string matching
            if file_path.match(exclude_pattern) or exclude_pattern.replace('/**', '') in file_str:
                excluded = True
                break
        
        if not excluded and file_path.is_file():
            filtered_files.append(file_path)
    
    return sorted(set(filtered_files))

def main():
    parser = argparse.ArgumentParser(description='Validate YAML and JSON files')
    parser.add_argument('files', nargs='*', help='Specific files to validate')
    parser.add_argument('--yaml-only', action='store_true', help='Only validate YAML files')
    parser.add_argument('--json-only', action='store_true', help='Only validate JSON files')
    parser.add_argument('--strict', action='store_true', help='Treat warnings as errors')
    parser.add_argument('--quiet', action='store_true', help='Only show errors')
    
    args = parser.parse_args()
    
    result = ValidationResult()
    
    if args.files:
        # Validate specific files
        files_to_check = [Path(f) for f in args.files if Path(f).exists()]
    else:
        # Find all YAML/JSON files with comprehensive patterns
        patterns = []
        if not args.json_only:
            patterns.extend([
                '**/*.yml', 
                '**/*.yaml',
                '*.yml',      # Root level files
                '*.yaml'      # Root level files
            ])
        if not args.yaml_only:
            patterns.extend([
                '**/*.json',
                '*.json'      # Root level files
            ])
        
        # Always include common config files
        patterns.extend(['pyproject.toml', '*.toml', '**/*.toml'])
        
        files_to_check = find_files(patterns)
    
    if not files_to_check:
        print("No files found to validate")
        return 0
    
    for file_path in files_to_check:
        file_str = str(file_path)
        
        # Determine file type and validate
        if file_path.suffix.lower() in ['.yml', '.yaml']:
            is_valid, error = validate_yaml_file(file_path)
            
            if is_valid:
                result.add_valid(file_str)
                
                # Additional validation for specific file types
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        content = yaml.safe_load(f)
                    
                    if '.github/workflows/' in file_str:
                        warnings = validate_github_workflow(file_path, content or {})
                        for warning in warnings:
                            result.add_warning(file_str, warning)
                    
                    elif 'docker-compose' in file_path.name:
                        warnings = validate_docker_compose(file_path, content or {})
                        for warning in warnings:
                            result.add_warning(file_str, warning)
                            
                except Exception as e:
                    result.add_warning(file_str, f"Could not perform additional validation: {e}")
            else:
                result.add_invalid(file_str, error)
                
        elif file_path.suffix.lower() == '.json':
            is_valid, error = validate_json_file(file_path)
            
            if is_valid:
                result.add_valid(file_str)
                
                # Additional validation for package.json
                if file_path.name == 'package.json':
                    try:
                        with open(file_path, 'r', encoding='utf-8') as f:
                            content = json.load(f)
                        
                        warnings = validate_package_json(file_path, content)
                        for warning in warnings:
                            result.add_warning(file_str, warning)
                            
                    except Exception as e:
                        result.add_warning(file_str, f"Could not perform additional validation: {e}")
            else:
                result.add_invalid(file_str, error)
                
        elif file_path.suffix.lower() == '.toml':
            is_valid, error = validate_toml_file(file_path)
            
            if is_valid:
                result.add_valid(file_str)
            else:
                result.add_invalid(file_str, error)
    
    # Print results
    if not args.quiet:
        result.print_summary()
    
    # Determine exit code
    if result.has_errors():
        if not args.quiet:
            print(f"\n❌ Validation failed: {len(result.invalid_files)} invalid files found")
            print("Fix the above errors before proceeding.")
        return 1
    elif args.strict and result.warnings:
        if not args.quiet:
            print(f"\n❌ Validation failed due to {len(result.warnings)} warnings (strict mode)")
            print("Address the above warnings or run without --strict flag.")
        return 1
    else:
        if not args.quiet:
            print(f"\n✅ Validation successful: {len(result.valid_files)} files validated")
        return 0

if __name__ == '__main__':
    sys.exit(main())