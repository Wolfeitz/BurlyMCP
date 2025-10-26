# Check-Task Workflow

This steering file defines the standard check-task workflow for validation-only operations.

## Workflow Steps

When executing check-task workflow, follow these steps in order:

### 1. Repository Status Check
- Verify we're in a git repository
- Run `git fetch --prune origin` to get latest remote info
- Show current branch name with `git branch -vv`
- Show `git status --porcelain` (staged, unstaged, untracked files)
- Show ahead/behind status vs origin if upstream exists

### 2. Test Validation
- Run `python3 -m pytest -q --tb=short` (use python3, not python)
- If tests fail, report failures and STOP (do not continue)
- Show test results summary

### 3. Optional Security Scan
- If trufflehog/gitleaks/bandit present, run secret/security scan
- If critical security issues found, report them and STOP
- Show security scan summary

### 4. Status Report
- ✅ All checks passed OR ❌ Issues found
- Branch status (clean/dirty, ahead/behind)
- Test results
- Security scan results (if run)

## Critical Constraints

**This workflow performs ONLY validation and status reporting. It must NOT:**
- Stage files (`git add`)
- Create commits (`git commit`)
- Push changes (`git push`)
- Open PRs
- Perform any git write operations

## Python Command Override

**CRITICAL**: Always use `python3` instead of `python` for this project, as the system doesn't have a `python` symlink.

This applies to:
- Running Python scripts: `python3 script.py` (NOT `python script.py`)
- Running modules: `python3 -m module_name` (NOT `python -m module_name`)
- Shebang lines: `#!/usr/bin/env python3` (NOT `#!/usr/bin/env python`)
- Any Python execution commands

**Remember**: The system will return "Command 'python' not found" if you use `python` instead of `python3`.