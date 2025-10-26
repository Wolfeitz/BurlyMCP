# File Validation System

## Overview

This project includes a comprehensive validation system to prevent YAML and JSON syntax errors from breaking CI/CD pipelines. The system includes automated hooks, manual validation scripts, and CI integration.

## Components

### 1. Kiro Hook (Automatic)

**File**: `.kiro/hooks/yaml-json-validator.kiro.hook`

Automatically triggers whenever YAML or JSON files are edited, providing immediate feedback in the IDE.

**Triggers on**:
- `**/*.yml`, `**/*.yaml` - All YAML files
- `**/*.json` - All JSON files  
- `.github/workflows/*` - GitHub Actions workflows
- `docker-compose*.yml` - Docker Compose files
- `pyproject.toml`, `package.json`, `tsconfig.json` - Config files

### 2. Manual Validation Script

**File**: `scripts/validate_yaml_json.py`

Comprehensive validation script that can be run manually or in CI.

```bash
# Validate all YAML/JSON files
python3 scripts/validate_yaml_json.py

# Validate specific files
python3 scripts/validate_yaml_json.py .github/workflows/ci.yml package.json

# Strict mode (warnings as errors)
python3 scripts/validate_yaml_json.py --strict

# Only YAML files
python3 scripts/validate_yaml_json.py --yaml-only
```

### 3. Pre-commit Hooks

**File**: `.pre-commit-config.yaml`

Prevents committing invalid files using the pre-commit framework.

```bash
# Install pre-commit
pip install pre-commit

# Install hooks
pre-commit install

# Run manually
pre-commit run --all-files
```

### 4. CI Validation

**File**: `.github/workflows/validate-files.yml`

Runs validation on all PRs and pushes to main/develop branches.

## Validation Features

### YAML Validation
- **Syntax checking**: Indentation, invalid characters, malformed structures
- **GitHub Actions workflows**: Required fields, valid triggers, job structure
- **Docker Compose**: Service definitions, volume syntax, environment variables

### JSON Validation  
- **Syntax checking**: Missing commas, brackets, quotes
- **Package.json**: NPM package structure validation
- **Config files**: General JSON configuration validation

### TOML Validation
- **Syntax checking**: For files like `pyproject.toml`

## Common YAML Issues Fixed

### 1. Reserved Keywords
```yaml
# ❌ Problem: 'on' is interpreted as boolean True
on:
  push: ...

# ✅ Solution: Quote reserved keywords  
"on":
  push: ...
```

### 2. Indentation Errors
```yaml
# ❌ Problem: Inconsistent indentation
jobs:
  test:
    runs-on: ubuntu-latest
     steps:  # Wrong indentation
      - name: Test

# ✅ Solution: Consistent 2-space indentation
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - name: Test
```

### 3. Missing Quotes
```yaml
# ❌ Problem: Special characters without quotes
name: My App: Version 2.0

# ✅ Solution: Quote strings with special characters
name: "My App: Version 2.0"
```

## Error Examples

### YAML Syntax Error
```
❌ Invalid Files:
- .github/workflows/publish-image.yml:12 - Line 12, Column 5: found character '\t' that cannot start any token
```

### JSON Syntax Error  
```
❌ Invalid Files:
- package.json:15 - Line 15, Column 10: Expecting ',' delimiter
```

### GitHub Actions Warning
```
⚠️ Warnings:
- .github/workflows/test.yml: Job 'build' missing 'runs-on' field
```

## Integration with Development Workflow

### IDE Integration (Kiro Hook)
1. Edit any YAML/JSON file
2. Hook automatically validates on save
3. Immediate feedback prevents syntax errors

### Pre-commit Integration
1. Attempt to commit changes
2. Pre-commit hooks validate files
3. Commit blocked if validation fails

### CI Integration
1. Push changes or create PR
2. GitHub Actions runs validation
3. Build fails if files are invalid

## Best Practices

### YAML Files
- Use 2-space indentation consistently
- Quote reserved keywords (`"on"`, `"true"`, `"false"`, `"null"`)
- Quote strings with special characters
- Use `|` for multi-line strings, `>` for folded strings

### JSON Files
- Use 2-space indentation for readability
- Always use double quotes for strings
- No trailing commas (invalid in JSON)
- Validate with `jq` for complex files

### GitHub Actions
- Always include `name` field for workflows and jobs
- Specify `runs-on` for all jobs
- Use proper action references (`uses: actions/checkout@v4`)
- Quote version numbers in action references

## Troubleshooting

### Hook Not Triggering
1. Check `.kiro/hooks/yaml-json-validator.kiro.hook` is enabled
2. Verify file patterns match your edited files
3. Restart Kiro if hooks aren't loading

### Pre-commit Issues
```bash
# Reinstall hooks
pre-commit uninstall
pre-commit install

# Update hook versions
pre-commit autoupdate

# Skip hooks temporarily (not recommended)
git commit --no-verify
```

### CI Validation Failures
1. Run validation locally: `python3 scripts/validate_yaml_json.py`
2. Fix reported syntax errors
3. Test with strict mode: `python3 scripts/validate_yaml_json.py --strict`
4. Commit and push fixes

## Extending Validation

### Adding New File Types
Edit `.kiro/hooks/yaml-json-validator.kiro.hook`:
```json
"patterns": [
  "**/*.yml",
  "**/*.yaml", 
  "**/*.json",
  "**/*.toml",
  "**/*.xml"  // Add new pattern
]
```

### Custom Validation Rules
Extend `scripts/validate_yaml_json.py`:
```python
def validate_custom_config(file_path: Path, content: Dict[str, Any]) -> List[str]:
    """Add custom validation logic."""
    warnings = []
    # Your validation logic here
    return warnings
```

### Additional CI Checks
Add to `.github/workflows/validate-files.yml`:
```yaml
- name: Custom validation
  run: |
    # Your custom validation commands
    ./scripts/validate_custom_configs.sh
```