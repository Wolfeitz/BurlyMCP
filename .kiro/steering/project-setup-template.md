# Comprehensive Project Setup Template

## Complete Steering & Hook System for New Projects

This template includes ALL steering rules and hooks from this project for easy adaptation to new projects.

### Complete Steering Files to Create

1. **tech.md** - Technology stack, build commands, security tools, port management
2. **structure.md** - Directory organization, naming conventions, security-first structure
3. **product.md** - Project overview, API-centric architecture, security principles
4. **test-maintenance.md** - Feature-based test analysis (not task-based)
5. **feature-based-specs.md** - Spec organization with feature grouping
6. **check-task-workflow.md** - Validation-only workflow with git status, tests, security

### Complete Hook System to Create

**Development Workflow:**
- **start-task-guard.kiro.hook** - Validates environment before starting tasks
- **finish-task-guard.kiro.hook** - Ensures proper task completion
- **finish-feature.kiro.hook** - Feature-level completion with test analysis
- **check-task.kiro.hook** - Status validation without making changes

**Security & Quality:**
- **env-security-validator.kiro.hook** - Validates environment variables and secrets
- **security-quick-pass.kiro.hook** - Quick security scan for common issues
- **yaml-json-validator.kiro.hook** - Configuration file validation

**Development Tools:**
- **dev-server-port-manager.kiro.hook** - Manages development server ports
- **api-doc-sync.kiro.hook** - Keeps API documentation in sync with code

**Test Management:**
- **post-task-test-analysis.md** - Feature-completion test analysis hook

### Setup Commands for New Projects

Instead of copying files, run:
```
"Set up complete project steering and hooks for [tech stack] project"
```

Examples:
- "Set up complete project steering and hooks for Python FastAPI project"
- "Set up complete project steering and hooks for React TypeScript project"
- "Set up complete project steering and hooks for Node.js Express project"

### What Gets Adapted

- **Commands**: npm/pip/cargo specific to your stack
- **Directory Structure**: Framework-appropriate organization
- **Security Tools**: Relevant scanners (bandit/eslint/etc.)
- **Port Management**: Default ports for your stack
- **Test Framework**: pytest/jest/vitest commands
- **Build System**: Vite/webpack/rollup configurations