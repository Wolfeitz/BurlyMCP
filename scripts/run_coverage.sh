#!/bin/bash
"""
Coverage test runner script for Burly MCP project.

This script provides convenient commands for running tests with coverage
in different configurations and environments.
"""

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Project root directory
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_ROOT"

# Default values
MIN_COVERAGE=80
VERBOSE=false
CLEAN=false

# Function to print colored output
print_status() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Function to show usage
show_usage() {
    cat << EOF
Usage: $0 [OPTIONS] [COMMAND]

COMMANDS:
    unit                Run unit tests with coverage
    integration         Run integration tests with coverage  
    all                 Run all tests with coverage (default)
    validate            Validate existing coverage without running tests
    clean               Clean coverage artifacts
    report              Generate and show coverage report

OPTIONS:
    --min-coverage N    Set minimum coverage threshold (default: 80)
    --verbose           Enable verbose output
    --clean             Clean coverage artifacts before running
    --help              Show this help message

EXAMPLES:
    $0                          # Run all tests with coverage
    $0 unit                     # Run unit tests only
    $0 --min-coverage 85 all    # Run all tests with 85% threshold
    $0 --verbose integration    # Run integration tests with verbose output
    $0 validate                 # Just validate existing coverage
    $0 clean                    # Clean coverage artifacts

EOF
}

# Function to clean coverage artifacts
clean_coverage() {
    print_status "Cleaning coverage artifacts..."
    
    # Remove coverage files
    rm -f coverage.xml coverage.json .coverage
    rm -rf htmlcov/
    rm -rf .pytest_cache/
    
    print_success "Coverage artifacts cleaned"
}

# Function to check prerequisites
check_prerequisites() {
    print_status "Checking prerequisites..."
    
    # Check if we're in a virtual environment
    if [[ -z "$VIRTUAL_ENV" ]]; then
        print_warning "Not in a virtual environment. Consider activating one."
    fi
    
    # Check if pytest is installed
    if ! python -c "import pytest" 2>/dev/null; then
        print_error "pytest not found. Install with: pip install -e .[test]"
        exit 1
    fi
    
    # Check if pytest-cov is installed
    if ! python -c "import pytest_cov" 2>/dev/null; then
        print_error "pytest-cov not found. Install with: pip install -e .[test]"
        exit 1
    fi
    
    print_success "Prerequisites check passed"
}

# Function to run coverage check
run_coverage() {
    local test_type="$1"
    local args=()
    
    args+=("--min-coverage" "$MIN_COVERAGE")
    
    if [[ "$VERBOSE" == "true" ]]; then
        args+=("--verbose")
    fi
    
    case "$test_type" in
        "unit")
            args+=("--unit-only")
            ;;
        "integration")
            args+=("--integration-only")
            ;;
        "validate")
            args+=("--validate-only")
            ;;
        "all"|"")
            # Default - run all tests
            ;;
        *)
            print_error "Unknown test type: $test_type"
            exit 1
            ;;
    esac
    
    print_status "Running coverage check: python scripts/check_coverage.py ${args[*]}"
    
    if python scripts/check_coverage.py "${args[@]}"; then
        print_success "Coverage check passed!"
        return 0
    else
        print_error "Coverage check failed!"
        return 1
    fi
}

# Function to generate coverage report
generate_report() {
    print_status "Generating coverage reports..."
    
    # Run pytest to generate fresh coverage data
    python -m pytest tests/ \
        --cov=burly_mcp \
        --cov-report=html \
        --cov-report=xml \
        --cov-report=json \
        --cov-report=term-missing \
        --quiet
    
    print_success "Coverage reports generated:"
    echo "  - HTML report: htmlcov/index.html"
    echo "  - XML report: coverage.xml"
    echo "  - JSON report: coverage.json"
    
    # Show summary
    if [[ -f "coverage.json" ]]; then
        python -c "
import json
with open('coverage.json') as f:
    data = json.load(f)
    total = data['totals']['percent_covered']
    print(f'\\nOverall Coverage: {total:.2f}%')
"
    fi
}

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --min-coverage)
            MIN_COVERAGE="$2"
            shift 2
            ;;
        --verbose)
            VERBOSE=true
            shift
            ;;
        --clean)
            CLEAN=true
            shift
            ;;
        --help|-h)
            show_usage
            exit 0
            ;;
        unit|integration|all|validate|clean|report)
            COMMAND="$1"
            shift
            ;;
        *)
            print_error "Unknown option: $1"
            show_usage
            exit 1
            ;;
    esac
done

# Set default command if none provided
COMMAND="${COMMAND:-all}"

# Main execution
main() {
    print_status "Burly MCP Coverage Runner"
    print_status "Project root: $PROJECT_ROOT"
    print_status "Command: $COMMAND"
    print_status "Min coverage: $MIN_COVERAGE%"
    
    # Clean if requested
    if [[ "$CLEAN" == "true" ]]; then
        clean_coverage
    fi
    
    # Handle commands
    case "$COMMAND" in
        "clean")
            clean_coverage
            ;;
        "report")
            check_prerequisites
            generate_report
            ;;
        "validate"|"unit"|"integration"|"all")
            check_prerequisites
            run_coverage "$COMMAND"
            ;;
        *)
            print_error "Unknown command: $COMMAND"
            show_usage
            exit 1
            ;;
    esac
}

# Run main function
main