# Makefile for Burly MCP Development
# Provides unified local testing commands that match CI exactly

.PHONY: help venv install test test-all lint typecheck security clean docs version-current version-bump version-set version-suggest version-validate version-notes prepare-release build-clean build-package build-test build-docker build-validate prepare-distribution
.DEFAULT_GOAL := help

# Variables
PYTHON := python3
VENV_DIR := .venv
PIP := $(VENV_DIR)/bin/pip
PYTEST := $(VENV_DIR)/bin/pytest
PYTHON_VENV := $(VENV_DIR)/bin/python

# Colors for output
GREEN := \033[0;32m
YELLOW := \033[1;33m
RED := \033[0;31m
NC := \033[0m # No Color

help: ## Show this help message
	@echo "$(GREEN)Burly MCP Development Commands$(NC)"
	@echo ""
	@echo "$(YELLOW)Setup:$(NC)"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | grep -E '^(venv|install)' | awk 'BEGIN {FS = ":.*?## "}; {printf "  $(GREEN)%-12s$(NC) %s\n", $$1, $$2}'
	@echo ""
	@echo "$(YELLOW)Testing:$(NC)"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | grep -E '^(test|test-all)' | awk 'BEGIN {FS = ":.*?## "}; {printf "  $(GREEN)%-12s$(NC) %s\n", $$1, $$2}'
	@echo ""
	@echo "$(YELLOW)Code Quality:$(NC)"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | grep -E '^(lint|typecheck|security)' | awk 'BEGIN {FS = ":.*?## "}; {printf "  $(GREEN)%-12s$(NC) %s\n", $$1, $$2}'
	@echo ""
	@echo "$(YELLOW)Utilities:$(NC)"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | grep -E '^(docs|clean)' | awk 'BEGIN {FS = ":.*?## "}; {printf "  $(GREEN)%-12s$(NC) %s\n", $$1, $$2}'

venv: ## Create virtual environment
	@echo "$(YELLOW)Creating virtual environment...$(NC)"
	$(PYTHON) -m venv $(VENV_DIR)
	@echo "$(GREEN)Virtual environment created at $(VENV_DIR)$(NC)"
	@echo "$(YELLOW)Activate with: source $(VENV_DIR)/bin/activate$(NC)"

install: venv ## Install development dependencies
	@echo "$(YELLOW)Installing development dependencies...$(NC)"
	$(PIP) install --upgrade pip setuptools wheel
	$(PIP) install -e .[dev]
	@echo "$(GREEN)Development dependencies installed$(NC)"

test: ## Run unit tests (matches CI exactly)
	@echo "$(YELLOW)Running unit tests (excluding integration tests)...$(NC)"
	@if [ ! -f $(PYTEST) ]; then \
		echo "$(RED)Error: pytest not found. Run 'make install' first.$(NC)"; \
		exit 1; \
	fi
	$(PYTEST) -m "not integration" --cov=burly_mcp --cov-report=xml --cov-branch --cov-report=term-missing -v

test-integration: ## Run integration tests separately
	@echo "$(YELLOW)Running integration tests...$(NC)"
	@if [ ! -f $(PYTEST) ]; then \
		echo "$(RED)Error: pytest not found. Run 'make install' first.$(NC)"; \
		exit 1; \
	fi
	$(PYTEST) -m integration -v --tb=short

test-all: test test-integration ## Run all tests (unit + integration)
	@echo "$(GREEN)All tests completed$(NC)"

lint: ## Run code linting with ruff
	@echo "$(YELLOW)Running code linting...$(NC)"
	@if [ ! -f $(VENV_DIR)/bin/ruff ]; then \
		echo "$(RED)Error: ruff not found. Run 'make install' first.$(NC)"; \
		exit 1; \
	fi
	$(VENV_DIR)/bin/ruff check src/ tests/ --fix
	$(VENV_DIR)/bin/black --check src/ tests/
	@echo "$(GREEN)Linting completed$(NC)"

typecheck: ## Run type checking with mypy
	@echo "$(YELLOW)Running type checking...$(NC)"
	@if [ ! -f $(VENV_DIR)/bin/mypy ]; then \
		echo "$(RED)Error: mypy not found. Run 'make install' first.$(NC)"; \
		exit 1; \
	fi
	$(VENV_DIR)/bin/mypy src/burly_mcp/
	@echo "$(GREEN)Type checking completed$(NC)"

security: ## Run security scans
	@echo "$(YELLOW)Running security scans...$(NC)"
	@if [ ! -f $(VENV_DIR)/bin/bandit ]; then \
		echo "$(RED)Error: security tools not found. Run 'make install' first.$(NC)"; \
		exit 1; \
	fi
	@echo "$(YELLOW)Running Bandit security scan...$(NC)"
	$(VENV_DIR)/bin/bandit -r src/ -f json -o bandit-report.json || true
	$(VENV_DIR)/bin/bandit -r src/ --severity-level medium
	@echo "$(YELLOW)Running pip-audit for dependency vulnerabilities...$(NC)"
	$(VENV_DIR)/bin/pip-audit --desc --format=json --output=pip-audit-report.json || true
	$(VENV_DIR)/bin/pip-audit --desc
	@echo "$(YELLOW)Running safety check...$(NC)"
	$(VENV_DIR)/bin/safety check --json --output=safety-report.json || true
	$(VENV_DIR)/bin/safety check
	@echo "$(GREEN)Security scans completed$(NC)"

docs: ## Generate documentation
	@echo "$(YELLOW)Generating documentation...$(NC)"
	@if [ ! -f $(VENV_DIR)/bin/sphinx-build ]; then \
		echo "$(RED)Error: sphinx not found. Run 'make install' first.$(NC)"; \
		exit 1; \
	fi
	$(VENV_DIR)/bin/sphinx-build -b html docs/ docs/_build/html
	@echo "$(GREEN)Documentation generated in docs/_build/html$(NC)"

clean: ## Clean build artifacts and cache files
	@echo "$(YELLOW)Cleaning build artifacts...$(NC)"
	rm -rf build/
	rm -rf dist/
	rm -rf *.egg-info/
	rm -rf .pytest_cache/
	rm -rf .mypy_cache/
	rm -rf .coverage
	rm -rf htmlcov/
	rm -rf coverage.xml
	rm -rf coverage.json
	rm -rf bandit-report.json
	rm -rf pip-audit-report.json
	rm -rf safety-report.json
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete
	@echo "$(GREEN)Cleanup completed$(NC)"

# Development workflow targets
dev-setup: install ## Complete development setup
	@echo "$(YELLOW)Setting up development environment...$(NC)"
	@if [ -f $(VENV_DIR)/bin/pre-commit ]; then \
		$(VENV_DIR)/bin/pre-commit install; \
		echo "$(GREEN)Pre-commit hooks installed$(NC)"; \
	fi
	@echo "$(GREEN)Development setup completed$(NC)"
	@echo "$(YELLOW)Run 'make test' to verify everything works$(NC)"

ci-test: ## Run the exact same tests as CI (unit tests only)
	@echo "$(YELLOW)Running CI-equivalent unit tests...$(NC)"
	@if [ ! -f $(PYTEST) ]; then \
		echo "$(RED)Error: pytest not found. Run 'make install' first.$(NC)"; \
		exit 1; \
	fi
	$(PYTEST) -m "not integration" --cov=burly_mcp --cov-report=xml --cov-branch --cov-report=term-missing -v

validate: lint typecheck security test ## Run all validation checks
	@echo "$(GREEN)All validation checks passed$(NC)"

# Check if virtual environment exists
check-venv:
	@if [ ! -d $(VENV_DIR) ]; then \
		echo "$(RED)Virtual environment not found. Run 'make venv' first.$(NC)"; \
		exit 1; \
	fi
# Ve
rsion Management targets
VERSION_SCRIPT := $(PYTHON_VENV) scripts/version_manager.py

version-current: ## Show current version
	@echo "$(YELLOW)Current version:$(NC)"
	@$(VERSION_SCRIPT) current

version-bump: ## Bump version (usage: make version-bump TYPE=patch|minor|major)
	@if [ -z "$(TYPE)" ]; then \
		echo "$(RED)Error: TYPE parameter required. Usage: make version-bump TYPE=patch|minor|major$(NC)"; \
		exit 1; \
	fi
	@echo "$(YELLOW)Bumping $(TYPE) version...$(NC)"
	@$(VERSION_SCRIPT) bump $(TYPE)

version-set: ## Set specific version (usage: make version-set VERSION=1.2.3)
	@if [ -z "$(VERSION)" ]; then \
		echo "$(RED)Error: VERSION parameter required. Usage: make version-set VERSION=1.2.3$(NC)"; \
		exit 1; \
	fi
	@echo "$(YELLOW)Setting version to $(VERSION)...$(NC)"
	@$(VERSION_SCRIPT) set $(VERSION)

version-suggest: ## Suggest version bump based on git history
	@echo "$(YELLOW)Analyzing git history for version suggestion...$(NC)"
	@$(VERSION_SCRIPT) suggest

version-validate: ## Validate release readiness
	@echo "$(YELLOW)Validating release readiness...$(NC)"
	@$(VERSION_SCRIPT) validate

version-notes: ## Generate release notes from git history
	@echo "$(YELLOW)Generating release notes...$(NC)"
	@$(VERSION_SCRIPT) notes

# Release preparation workflow
prepare-release: version-validate lint typecheck security test ## Prepare for release (validate everything)
	@echo "$(GREEN)Release preparation completed successfully!$(NC)"
	@echo "$(YELLOW)Next steps:$(NC)"
	@echo "  1. Review changes: git log --oneline"
	@echo "  2. Bump version: make version-bump TYPE=patch|minor|major"
	@echo "  3. Push to main branch to trigger release pipeline"

# Release validation and monitoring targets
RELEASE_MONITOR := $(PYTHON_VENV) scripts/release_monitor.py
RELEASE_ROLLBACK := $(PYTHON_VENV) scripts/release_rollback.py
POST_RELEASE_VERIFY := $(PYTHON_VENV) scripts/post_release_verification.py

release-monitor: ## Monitor release health (usage: make release-monitor VERSION=1.2.3)
	@if [ -z "$(VERSION)" ]; then \
		echo "$(RED)Error: VERSION parameter required. Usage: make release-monitor VERSION=1.2.3$(NC)"; \
		exit 1; \
	fi
	@echo "$(YELLOW)Monitoring release v$(VERSION)...$(NC)"
	@$(RELEASE_MONITOR) monitor $(VERSION)

release-check: ## Check release health once (usage: make release-check VERSION=1.2.3)
	@if [ -z "$(VERSION)" ]; then \
		echo "$(RED)Error: VERSION parameter required. Usage: make release-check VERSION=1.2.3$(NC)"; \
		exit 1; \
	fi
	@echo "$(YELLOW)Checking release v$(VERSION)...$(NC)"
	@$(RELEASE_MONITOR) check $(VERSION)

release-verify: ## Verify released artifacts (usage: make release-verify VERSION=1.2.3)
	@if [ -z "$(VERSION)" ]; then \
		echo "$(RED)Error: VERSION parameter required. Usage: make release-verify VERSION=1.2.3$(NC)"; \
		exit 1; \
	fi
	@echo "$(YELLOW)Verifying release v$(VERSION)...$(NC)"
	@$(POST_RELEASE_VERIFY) verify $(VERSION)

release-rollback-plan: ## Create rollback plan (usage: make release-rollback-plan VERSION=1.2.3)
	@if [ -z "$(VERSION)" ]; then \
		echo "$(RED)Error: VERSION parameter required. Usage: make release-rollback-plan VERSION=1.2.3$(NC)"; \
		exit 1; \
	fi
	@echo "$(YELLOW)Creating rollback plan for v$(VERSION)...$(NC)"
	@$(RELEASE_ROLLBACK) plan $(VERSION)

release-rollback: ## Execute rollback (usage: make release-rollback VERSION=1.2.3)
	@if [ -z "$(VERSION)" ]; then \
		echo "$(RED)Error: VERSION parameter required. Usage: make release-rollback VERSION=1.2.3$(NC)"; \
		exit 1; \
	fi
	@echo "$(YELLOW)Rolling back v$(VERSION)...$(NC)"
	@$(RELEASE_ROLLBACK) execute $(VERSION)#
 Build validation targets
BUILD_VALIDATOR := $(PYTHON_VENV) scripts/build_validator.py

build-clean: ## Clean build artifacts
	@echo "$(YELLOW)Cleaning build artifacts...$(NC)"
	@$(BUILD_VALIDATOR) clean

build-package: ## Build and validate Python package
	@echo "$(YELLOW)Building and validating package...$(NC)"
	@$(BUILD_VALIDATOR) build

build-test: ## Test package installation in clean environment
	@echo "$(YELLOW)Testing package installation...$(NC)"
	@$(BUILD_VALIDATOR) test-install

build-docker: ## Test Docker build process
	@echo "$(YELLOW)Testing Docker build...$(NC)"
	@$(BUILD_VALIDATOR) test-docker

build-validate: ## Run complete build validation pipeline
	@echo "$(YELLOW)Running complete build validation...$(NC)"
	@$(BUILD_VALIDATOR) full

# Distribution preparation workflow
prepare-distribution: build-validate version-validate ## Prepare for distribution (validate everything)
	@echo "$(GREEN)Distribution preparation completed successfully!$(NC)"
	@echo "$(YELLOW)Next steps:$(NC)"
	@echo "  1. Review build validation report: cat build_validation_report.md"
	@echo "  2. Test package: make build-test"
	@echo "  3. Bump version: make version-bump TYPE=patch|minor|major"
	@echo "  4. Push to main branch to trigger release pipeline"