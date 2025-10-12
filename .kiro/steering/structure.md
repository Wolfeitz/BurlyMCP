# Project Structure

## Directory Organization

```
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

## File Naming Conventions

- **API Files**: Use descriptive names like `*route*.js`, `*handler*.js`, `*api*.js`
- **Configuration**: Keep config files in root (`vite.config.*`, `svelte.config.*`)
- **Environment**: Use `.env.example` for template, `.env` for local values
- **Ports**: Centralize port assignments in `ports.json`

## Key Files

- `package.json` - Dependencies and scripts
- `index.html` - Application entry point
- `.env.example` - Environment variable template
- `ports.json` - Port allocation registry
- `.devlock` - Development server lock file (auto-generated)

## Security-First Organization

- All API changes require corresponding documentation in `docs/api/`
- Environment variables must be templated in `.env.example`
- Port assignments tracked in `ports.json` to prevent conflicts
- Infrastructure code isolated in `infra/` directory
- Security scanning covers `server/`, `api/`, `infra/`, and `scripts/` directories