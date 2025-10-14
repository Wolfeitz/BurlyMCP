# Building a Secure MCP Server with Kiro: How Hooks and Steering Transformed Our Development Experience

*A deep dive into using Kiro's automation features to build production-ready software with AI assistance*

## The Challenge: Building Production Software with AI

When I set out to build Burly MCP—a secure Model Context Protocol server for AI assistants—I knew I wanted to leverage AI development tools. But I also knew the typical pitfalls: inconsistent code quality, security oversights, missing documentation, and the constant context switching between writing code and maintaining development hygiene.

What I discovered was that Kiro's hooks and steering system could transform this experience entirely. Instead of just getting help writing code, I could create an intelligent development environment that enforced best practices, caught security issues early, and maintained consistency across the entire project lifecycle.

## What We Built: Burly MCP Server

Before diving into the tooling, let me briefly describe what we built together. Burly MCP is a containerized Python server that implements the Model Context Protocol, allowing AI assistants like Open WebUI to safely execute system operations. It includes:

- **Docker container management** with read-only socket access
- **Blog publishing workflow** with YAML front-matter validation
- **System monitoring tools** for disk usage and health checks
- **Gotify notification integration** for operation alerts
- **Comprehensive audit logging** in JSON Lines format
- **Policy-driven security** with JSON Schema validation

The entire project follows security-first principles, runs in a hardened container, and includes extensive documentation for newcomers to MCP.

## The Game Changer: Kiro's Hooks and Steering

What made this project special wasn't just the AI assistance—it was the intelligent automation layer we built around the development process. Kiro's hooks and steering system allowed us to create a development environment that was both powerful and safe.

### Steering: Establishing the Ground Rules

Steering files in Kiro act like persistent context that guides every interaction. Think of them as the "team standards" that get automatically included in conversations. We created three key steering files:

#### 1. Product Vision (`product.md`)
```markdown
# Product Overview

This is a web application project with a focus on API development and security-first practices. The project emphasizes:

- **API-Centric Architecture**: Built around well-documented REST APIs
- **Security by Design**: Automated security validation, secret detection, and vulnerability scanning
- **Development Quality**: Automated documentation sync, port management, and environment validation
- **Modern Web Stack**: Uses contemporary JavaScript/TypeScript tooling with Vite for development
```

This steering file ensured that every code suggestion, architectural decision, and implementation detail aligned with our security-first philosophy. When Kiro suggested solutions, they automatically incorporated these principles.

#### 2. Project Structure (`structure.md`)
```markdown
## Directory Organization

├── src/                    # Main application source code
│   ├── api/               # API routes and handlers
│   ├── server/            # Server-side logic and middleware
│   ├── components/        # Reusable UI components
│   ├── lib/               # Shared utilities and libraries
│   └── routes/            # Application routes (if using file-based routing)
├── public/                # Static assets served directly
├── infra/                 # Infrastructure as code (Terraform, etc.)
├── scripts/               # Build and deployment scripts
├── docs/                  # Project documentation
│   └── api/               # API documentation and specs
├── tests/                 # Test files and test utilities
└── .kiro/                 # Kiro configuration and hooks
    ├── hooks/             # Automated workflow hooks
    └── steering/          # AI assistant guidance rules
```

This steering file meant that every time we created new files or refactored code, the suggestions automatically followed our established patterns. No more "where should this file go?" decisions—the AI knew our conventions.

#### 3. Technology Stack (`tech.md`)
```markdown
## Core Technologies

- **Frontend**: Modern JavaScript/TypeScript with Vite build system
- **Framework**: Likely Svelte (based on svelte.config.* patterns)
- **Development Server**: Vite dev server on port 5173
- **Package Manager**: npm

## Security Tools

- **ESLint**: Security-focused rules (`eslint-plugin-security`, `@typescript-eslint/recommended-requiring-type-checking`)
- **Audit**: npm audit for dependency vulnerabilities
- **Secret Detection**: gitleaks for exposed credentials
- **Vulnerability Scanning**: trivy for known security issues
```

This ensured that all tooling suggestions, build configurations, and security recommendations were consistent with our chosen stack.

### Hooks: Automation That Actually Helps

The real magic happened with hooks—automated workflows that trigger based on file changes. We created six hooks that transformed our development experience:

#### 1. Start-Task Guard: Keeping Work Off Main
```json
{
  "name": "Start-Task Guard",
  "when": {
    "type": "fileEdited",
    "patterns": ["specs/**", "docs/**"]
  },
  "then": {
    "type": "askAgent",
    "prompt": "You are the Start-Task Guard. A file has been saved in the specs or docs directory. Your job is to:\n\n1. Run `git rev-parse --abbrev-ref HEAD` to detect the current branch\n2. If the current branch is \"main\" or \"master\":\n   - Ask the user: \"You're on main. Create a feature branch and switch to it?\"\n   - If they say yes, create a feature branch named `feature/<YYYYMMDD>-<slug-of-latest-edited-file>`\n   - Use `git switch -c <branch-name>` to create and switch to the new branch\n3. If already on a non-main branch, just log \"Start-Task Guard: OK\" and do nothing"
  }
}
```

This hook prevented the common mistake of working directly on main. Every time I started editing specs or docs, it would automatically offer to create a properly named feature branch. Simple, but incredibly effective for maintaining clean git history.

#### 2. Environment Security Validator: Preventing Secrets in Code
```json
{
  "name": "Environment Security Validator",
  "when": {
    "type": "fileEdited",
    "patterns": [".env", ".env.example", "**/*.js", "**/*.ts", "**/*.json", "**/*.yml", "**/*.yaml"]
  },
  "then": {
    "type": "askAgent",
    "prompt": "Analyze the changed files and perform the following validations:\n\n1. **Environment Sync**: Compare .env.example with any .env files and ensure .env.example contains all required keys (without values).\n\n2. **Secret Detection**: Scan all tracked files for potential secrets (API keys, passwords, tokens, private keys).\n\n3. **Port Validation**: If ports.json exists, validate that all host ports are unique across services.\n\n4. **CORS Validation**: Check for CORS origin configurations in code and ensure they match the domains configured in environment/config files.\n\nFor any violations found, REFUSE to proceed and provide specific corrected diffs showing exactly what needs to be fixed."
  }
}
```

This hook was a game-changer for security. It automatically caught when I accidentally included real API keys in code, ensured my `.env.example` stayed in sync with actual environment needs, and validated port configurations. It literally prevented security incidents before they happened.

#### 3. Security Quick Pass: Comprehensive Security Analysis
```json
{
  "name": "Security Quick Pass",
  "when": {
    "type": "fileEdited",
    "patterns": ["server/**/*", "infra/**/*", "api/**/*", "docker/**/*", "scripts/**/*"]
  },
  "then": {
    "type": "askAgent",
    "prompt": "Run a comprehensive security analysis on the changed server/infrastructure files. Execute the following security checks in order:\n\n1. ESLint with security-focused rules\n2. npm audit --production-only to check for vulnerabilities in production dependencies\n3. gitleaks to scan for exposed secrets and credentials\n4. trivy filesystem scan for known vulnerabilities\n\nFor each tool, capture and analyze the output. If ANY high or critical severity issues are found:\n- FAIL the hook immediately\n- Generate a concise, actionable summary of security issues found\n- Propose minimal code diffs to fix issues\n- Clearly state that the merge must be blocked until these security issues are resolved"
  }
}
```

This hook ran comprehensive security analysis every time I touched server or infrastructure code. It caught dependency vulnerabilities, exposed secrets, and security anti-patterns before they made it into commits. The AI would not only identify issues but propose specific fixes.

#### 4. API Documentation Sync: Keeping Docs Current
```json
{
  "name": "API Documentation Sync",
  "when": {
    "type": "fileEdited",
    "patterns": ["**/*route*.js", "**/*api*.js", "**/routes/**", "**/api/**"]
  },
  "then": {
    "type": "askAgent",
    "prompt": "New API routes or handlers have been detected. Please analyze the changes and:\n\n1. Check if a Feature Spec document exists for this API\n2. If missing, create one from the project template including:\n   - Endpoint definitions\n   - Request/response JSON schemas\n   - Authentication requirements\n   - Rate limiting specifications\n   - CSP (Content Security Policy) impact analysis\n3. If existing, update it with the new endpoints and their specifications\n4. Verify that corresponding test stubs are present"
  }
}
```

This hook ensured that API documentation never fell behind code changes. Every time I added or modified an API endpoint, it would automatically update the documentation with proper schemas, authentication requirements, and security considerations.

#### 5. Dev Server Port Manager: Handling Development Conflicts
```json
{
  "name": "Dev Server Port Manager",
  "when": {
    "type": "fileEdited",
    "patterns": ["src/**/*", "package.json", "vite.config.*", "*.html"]
  },
  "then": {
    "type": "askAgent",
    "prompt": "Before starting the dev server, ensure port 5173 is available by: 1) Check if anything is listening on port 5173, 2) If occupied, terminate any Node/Vite processes using port 5173, 3) Wait up to 5 seconds and re-check port availability, 4) If still busy after 5s, fail with clear error message instead of using alternate port, 5) Create a .devlock file to prevent concurrent restarts within 15 seconds"
  }
}
```

This hook solved the annoying problem of port conflicts during development. Instead of getting random port assignments or cryptic error messages, it would intelligently manage port 5173, terminate conflicting processes, and prevent concurrent server restarts.

#### 6. Finish-Task Guard: Complete Git Workflow Automation
```json
{
  "name": "Finish-Task Guard",
  "when": {
    "type": "fileEdited",
    "patterns": ["specs/requirements.md", "docs/design.md", "**/*[finish-task]*"]
  },
  "then": {
    "type": "askAgent",
    "prompt": "Execute the finish-task workflow:\n\n1. **Preflight checks**: Verify we're in a git repository with origin remote\n2. **Stage and commit changes**: Run `git add -A` and create a Conventional Commit message\n3. **Push changes**: Run `git push -u origin <branch>` to set upstream\n4. **PR readiness assessment**: Compute diff vs origin/main, run tests, check for secrets\n5. **Sync from main for next work**: Switch to main, pull latest, rebase feature branch\n6. **Output brief report**: Branch name, commit status, PR recommendation"
  }
}
```

This hook automated the entire "task completion" workflow. When I finished a feature, it would handle staging, committing with proper conventional commit messages, pushing, running tests, checking PR readiness, and even syncing with main for the next task. It turned a 10-step manual process into a single trigger.

## How It Worked in Practice

### The Development Flow

Here's what a typical development session looked like:

1. **Starting Work**: I'd open a spec file to plan a feature. The Start-Task Guard would immediately offer to create a feature branch with a proper name like `feature/20241014-mcp-security-policy`.

2. **Writing Code**: As I implemented features, the steering files ensured all suggestions followed our security-first, well-documented approach. The AI knew our project structure, technology choices, and quality standards.

3. **Security Validation**: Every time I touched server code, the Security Quick Pass would run comprehensive checks. If I accidentally included a real API key or introduced a vulnerability, it would catch it immediately and suggest fixes.

4. **Documentation Sync**: When I added new API endpoints, the API Documentation Sync would automatically update our specs with proper schemas, authentication requirements, and security considerations.

5. **Environment Management**: The Environment Security Validator ensured my `.env.example` stayed current and prevented secrets from being committed.

6. **Finishing Tasks**: When ready to commit, the Finish-Task Guard would handle the entire git workflow—staging, committing with proper messages, pushing, running tests, and preparing for PR creation.

### The Compound Effect

What made this system powerful wasn't any single hook—it was how they worked together to create a development environment that was both productive and safe. The steering files provided consistent context, while the hooks automated all the tedious-but-important tasks that usually get skipped under deadline pressure.

## What Worked Exceptionally Well

### 1. Security by Default
The combination of security-focused steering and automated security hooks meant that security wasn't an afterthought—it was built into every interaction. The AI suggestions automatically included security considerations, and the hooks caught issues before they became problems.

### 2. Consistent Quality
The steering files ensured that every piece of code, documentation, and configuration followed our established patterns. There was no "style drift" or inconsistent approaches across different parts of the project.

### 3. Reduced Cognitive Load
The hooks automated all the "process overhead" that usually distracts from actual development. I could focus on solving problems while the system handled git workflows, security checks, documentation updates, and environment management.

### 4. Learning Amplification
Because the steering files encoded best practices and the hooks enforced them, I was constantly learning better approaches. The AI wasn't just helping me write code—it was teaching me better development practices.

### 5. Audit Trail and Compliance
Every security check, every documentation update, every git operation was logged and traceable. This created a natural audit trail that would be valuable for compliance or security reviews.

## Areas for Improvement

### 1. Hook Complexity Management
Some hooks became quite complex, trying to handle too many scenarios. The Finish-Task Guard, in particular, tried to be a complete git workflow manager. Breaking this into smaller, more focused hooks might be more maintainable.

**Recommendation**: Create smaller, composable hooks that can be chained together rather than monolithic workflows.

### 2. Error Handling and Recovery
When hooks failed (e.g., network issues during security scans), the error messages weren't always clear about how to recover. Better error handling and recovery suggestions would improve the experience.

**Recommendation**: Add explicit error handling patterns and recovery instructions to hook prompts.

### 3. Performance Impact
Running comprehensive security scans on every file change could be slow, especially for large projects. Some hooks might benefit from smarter triggering or incremental analysis.

**Recommendation**: Implement file change analysis to only run relevant checks, or add debouncing for rapid file changes.

### 4. Customization Complexity
While the hooks were powerful, customizing them for different project types required understanding the JSON structure and prompt engineering. A more user-friendly configuration interface could help adoption.

**Recommendation**: Create hook templates for common scenarios and a visual hook builder.

### 5. Cross-Hook Coordination
Sometimes hooks would conflict or duplicate work. Better coordination between hooks could prevent redundant operations.

**Recommendation**: Add hook dependency management and shared state between hooks.

## Recreating This Setup: A Step-by-Step Guide

Want to implement a similar system for your projects? Here's how to recreate the magic:

### Step 1: Create Your Steering Foundation

Start by creating `.kiro/steering/` directory with three core files:

**`.kiro/steering/product.md`** - Define your project's core principles:
```markdown
# Product Overview

[Your project description and core principles]

## Key Principles

- [Principle 1: e.g., Security by design]
- [Principle 2: e.g., Comprehensive documentation]
- [Principle 3: e.g., Test-driven development]
```

**`.kiro/steering/structure.md`** - Document your project structure:
```markdown
# Project Structure

## Directory Organization

[Your directory structure with explanations]

## File Naming Conventions

[Your naming conventions and patterns]

## Security-First Organization

[Security-related organizational principles]
```

**`.kiro/steering/tech.md`** - Define your technology stack:
```markdown
# Technology Stack

## Core Technologies

[Your chosen technologies and why]

## Common Commands

[Standard commands for your stack]

## Security Tools

[Security tools and their usage]
```

### Step 2: Implement Core Hooks

Create these hooks in `.kiro/hooks/` directory:

**1. Branch Management Hook** (`start-task-guard.kiro.hook`):
```json
{
  "enabled": true,
  "name": "Start-Task Guard",
  "description": "Prompts to create feature branch when working on main",
  "version": "1",
  "when": {
    "type": "fileEdited",
    "patterns": ["specs/**", "docs/**", "src/**"]
  },
  "then": {
    "type": "askAgent",
    "prompt": "Check current git branch. If on main/master, offer to create a feature branch named feature/<YYYYMMDD>-<descriptive-slug>. Use git switch -c to create and switch."
  }
}
```

**2. Security Validation Hook** (`security-validator.kiro.hook`):
```json
{
  "enabled": true,
  "name": "Security Validator",
  "description": "Runs security checks on code changes",
  "version": "1",
  "when": {
    "type": "fileEdited",
    "patterns": ["src/**/*", "server/**/*", "api/**/*", ".env*", "**/*.js", "**/*.ts"]
  },
  "then": {
    "type": "askAgent",
    "prompt": "Run security analysis: 1) Scan for secrets in changed files, 2) Check .env.example sync, 3) Validate no hardcoded credentials, 4) Run dependency audit if package files changed. REFUSE to proceed if security issues found."
  }
}
```

**3. Documentation Sync Hook** (`doc-sync.kiro.hook`):
```json
{
  "enabled": true,
  "name": "Documentation Sync",
  "description": "Updates documentation when code changes",
  "version": "1",
  "when": {
    "type": "fileEdited",
    "patterns": ["src/api/**/*", "src/routes/**/*", "**/*api*.js", "**/*route*.js"]
  },
  "then": {
    "type": "askAgent",
    "prompt": "API code changed. Check if documentation exists for these endpoints. If missing, create API documentation with: endpoint definitions, request/response schemas, authentication requirements, rate limiting specs. Update existing docs if endpoints changed."
  }
}
```

**4. Task Completion Hook** (`finish-task.kiro.hook`):
```json
{
  "enabled": true,
  "name": "Finish Task",
  "description": "Automates git workflow when task is complete",
  "version": "1",
  "when": {
    "type": "fileEdited",
    "patterns": ["**/*[finish-task]*", "**/*[complete]*"]
  },
  "then": {
    "type": "askAgent",
    "prompt": "Execute task completion workflow: 1) git add -A, 2) Create conventional commit message, 3) git commit, 4) git push with upstream, 5) Run tests if available, 6) Report PR readiness status."
  }
}
```

### Step 3: Customize for Your Stack

Adapt the hooks and steering files for your specific technology stack:

**For Python Projects**:
- Add `pytest`, `black`, `mypy` to security checks
- Include `requirements.txt` and `pyproject.toml` in dependency monitoring
- Add Python-specific security tools like `bandit` or `safety`

**For Node.js Projects**:
- Include `npm audit`, `eslint` with security plugins
- Monitor `package.json` and `package-lock.json`
- Add `gitleaks` and `trivy` for comprehensive scanning

**For Go Projects**:
- Include `go mod tidy`, `golangci-lint`, `gosec`
- Monitor `go.mod` and `go.sum` files
- Add Go-specific security scanning

### Step 4: Test and Iterate

Start with basic hooks and gradually add complexity:

1. **Test Each Hook Individually**: Make sure each hook triggers correctly and provides useful output
2. **Monitor Performance**: Ensure hooks don't slow down your development workflow
3. **Gather Feedback**: If working with a team, collect feedback on hook usefulness and accuracy
4. **Iterate and Improve**: Refine prompts based on real-world usage

### Step 5: Advanced Patterns

Once basic hooks are working, consider these advanced patterns:

**Conditional Hooks**: Use file patterns and conditions to make hooks more targeted:
```json
{
  "when": {
    "type": "fileEdited",
    "patterns": ["src/**/*.ts"],
    "conditions": ["file_size > 100", "contains_export_default"]
  }
}
```

**Hook Chaining**: Create hooks that trigger other hooks for complex workflows:
```json
{
  "then": {
    "type": "askAgent",
    "prompt": "After completing this task, trigger the documentation-sync hook if API files were changed."
  }
}
```

**Context-Aware Hooks**: Use git status, file contents, or project metadata to make smarter decisions:
```json
{
  "then": {
    "type": "askAgent",
    "prompt": "Check git status. If there are staged changes, suggest commit message based on changed files. If working directory is clean, suggest next development task."
  }
}
```

## The Future of AI-Assisted Development

Our experience with Kiro's hooks and steering system points to a future where AI assistance goes far beyond code generation. The most powerful applications combine:

1. **Persistent Context** (steering files) that encode team knowledge and standards
2. **Intelligent Automation** (hooks) that handle process overhead
3. **Security by Default** that prevents issues rather than fixing them later
4. **Learning Amplification** that teaches better practices through consistent application

This isn't just about writing code faster—it's about creating development environments that are inherently more secure, consistent, and maintainable.

## Key Takeaways

### What Made This Successful

1. **Start with Principles**: The steering files that encoded our security-first, documentation-heavy approach were crucial for consistency.

2. **Automate the Boring Stuff**: The most valuable hooks automated tedious-but-important tasks like git workflows, security checks, and documentation updates.

3. **Fail Fast and Loud**: Hooks that caught problems early (like the security validator) were more valuable than those that fixed problems later.

4. **Compound Effects**: The real power came from hooks working together to create a comprehensive development environment.

5. **Iterative Improvement**: We started simple and gradually added complexity based on real needs.

### Recommendations for Your Implementation

1. **Start Small**: Begin with 2-3 simple hooks and expand based on what you actually need.

2. **Focus on Pain Points**: Identify the manual tasks you skip under pressure and automate those first.

3. **Make Security Automatic**: Security hooks that prevent problems are worth their weight in gold.

4. **Document Everything**: Your steering files should be comprehensive enough that a new team member could understand your standards.

5. **Test Thoroughly**: Hooks that fail or give false positives will quickly be disabled. Make sure they work reliably.

6. **Keep It Maintainable**: Complex hooks are harder to debug and modify. Prefer simple, focused hooks over monolithic ones.

## Conclusion

Building Burly MCP with Kiro's hooks and steering system was a revelation. We didn't just build a secure MCP server—we created a development environment that enforced security best practices, maintained consistent quality, and automated away the tedious parts of software development.

The combination of persistent context (steering) and intelligent automation (hooks) created a development experience that was both more productive and more secure than traditional approaches. The AI wasn't just helping write code—it was actively preventing security issues, maintaining documentation, and enforcing best practices.

For teams looking to leverage AI in their development workflow, I can't recommend this approach highly enough. The initial setup investment pays dividends in code quality, security posture, and developer productivity. More importantly, it creates a development environment that teaches better practices and prevents the kinds of issues that usually only get caught in code review or production.

The future of software development isn't just AI that writes code—it's AI that creates intelligent development environments that make good practices automatic and security issues impossible. Kiro's hooks and steering system is a glimpse of that future, and it's available today.

---

*Want to try this approach yourself? Start with the step-by-step guide above, or check out the [Burly MCP repository](https://github.com/your-org/burly-mcp) to see the complete implementation in action.*