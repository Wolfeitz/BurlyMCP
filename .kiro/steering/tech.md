# Technology Stack

## Core Technologies

- **Frontend**: Modern JavaScript/TypeScript with Vite build system
- **Framework**: Likely Svelte (based on svelte.config.* patterns)
- **Development Server**: Vite dev server on port 5173
- **Package Manager**: npm

## Build System

- **Bundler**: Vite
- **Config Files**: `vite.config.*`, `svelte.config.*`
- **Entry Point**: Standard `index.html` in root

## Common Commands

```bash
# Development
npm run dev          # Start dev server on port 5173
npm run build        # Production build
npm run preview      # Preview production build

# Security & Quality
npm audit --production-only    # Check production dependencies
npx eslint . --ext .js,.ts     # Lint with security rules
npx gitleaks detect            # Scan for secrets
trivy filesystem .             # Vulnerability scan
```

## Development Environment

- **Port Management**: Port 5173 is reserved for dev server, conflicts are automatically resolved
- **Watch Exclusions**: `node_modules/.vite`, `.svelte-kit`, `build/` directories excluded from watch
- **Lock Files**: `.devlock` prevents concurrent dev server restarts (15s timeout)

## Security Tools

- **ESLint**: Security-focused rules (`eslint-plugin-security`, `@typescript-eslint/recommended-requiring-type-checking`)
- **Audit**: npm audit for dependency vulnerabilities
- **Secret Detection**: gitleaks for exposed credentials
- **Vulnerability Scanning**: trivy for known security issues