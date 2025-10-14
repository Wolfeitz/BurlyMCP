#!/bin/bash
#
# Burly MCP Test Runner
#
# Convenience script for running the MCP test harness with common configurations.
# This script provides easy access to the most common testing scenarios.

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

# Default values
PYTHON_CMD="python3"
TEST_HARNESS="$SCRIPT_DIR/test_harness.py"
SERVER_CMD="python -m server.main"
TIMEOUT=30

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

# Function to check dependencies
check_dependencies() {
    print_status "Checking dependencies..."
    
    # Check Python
    if ! command -v "$PYTHON_CMD" &> /dev/null; then
        print_error "Python not found. Please install Python 3.12 or later."
        exit 1
    fi
    
    # Check Python version
    python_version=$($PYTHON_CMD --version 2>&1 | cut -d' ' -f2)
    print_status "Found Python $python_version"
    
    # Check if test harness exists
    if [[ ! -f "$TEST_HARNESS" ]]; then
        print_error "Test harness not found at $TEST_HARNESS"
        exit 1
    fi
    
    # Check if we're in the right directory
    if [[ ! -f "$PROJECT_ROOT/pyproject.toml" ]]; then
        print_error "Not in Burly MCP project root. Please run from project directory."
        exit 1
    fi
    
    print_success "Dependencies check passed"
}

# Function to run demo scenarios
run_demo() {
    print_status "Running demo scenarios (configuration validation only)..."
    cd "$PROJECT_ROOT"
    
    if $PYTHON_CMD "$TEST_HARNESS" --demo --timeout "$TIMEOUT"; then
        print_success "Demo scenarios completed successfully"
        return 0
    else
        print_error "Demo scenarios failed"
        return 1
    fi
}

# Function to run full functionality tests
run_full_test() {
    print_status "Running full functionality tests with mock services..."
    cd "$PROJECT_ROOT"
    
    # Source testing environment with mock services enabled
    if [[ -f ".env.testing" ]]; then
        print_status "Loading testing environment with mock services..."
        source ".env.testing" > /dev/null 2>&1
    fi
    
    if $PYTHON_CMD "$TEST_HARNESS" --full-test --timeout "$TIMEOUT"; then
        print_success "Full functionality tests completed successfully"
        return 0
    else
        print_error "Full functionality tests failed"
        return 1
    fi
}

# Function to run interactive mode
run_interactive() {
    print_status "Starting interactive mode..."
    cd "$PROJECT_ROOT"
    
    print_status "Use 'help' for commands, 'quit' to exit"
    $PYTHON_CMD "$TEST_HARNESS" --interactive --timeout "$TIMEOUT"
}

# Function to validate a specific tool
validate_tool() {
    local tool_name="$1"
    print_status "Validating tool: $tool_name"
    cd "$PROJECT_ROOT"
    
    if $PYTHON_CMD "$TEST_HARNESS" --validate-tool "$tool_name" --timeout "$TIMEOUT"; then
        print_success "Tool validation passed: $tool_name"
        return 0
    else
        print_error "Tool validation failed: $tool_name"
        return 1
    fi
}

# Function to validate all tools
validate_all_tools() {
    print_status "Validating all tools..."
    
    local tools=("docker_ps" "disk_space" "blog_stage_markdown" "blog_publish_static" "gotify_ping")
    local failed_tools=()
    
    for tool in "${tools[@]}"; do
        if ! validate_tool "$tool"; then
            failed_tools+=("$tool")
        fi
    done
    
    if [[ ${#failed_tools[@]} -eq 0 ]]; then
        print_success "All tools validated successfully"
        return 0
    else
        print_error "Failed tools: ${failed_tools[*]}"
        return 1
    fi
}

# Function to run quick health check
run_health_check() {
    print_status "Running quick health check..."
    cd "$PROJECT_ROOT"
    
    # Test basic server startup and list_tools
    local test_request='{"method": "list_tools"}'
    
    print_status "Testing server startup and basic functionality..."
    
    if echo "$test_request" | timeout 10 $PYTHON_CMD -m server.main > /dev/null 2>&1; then
        print_success "Health check passed - server is responding"
        return 0
    else
        print_error "Health check failed - server not responding"
        return 1
    fi
}

# Function to run with Docker
run_with_docker() {
    print_status "Running tests with Docker..."
    
    if ! command -v docker &> /dev/null; then
        print_error "Docker not found. Please install Docker to use this option."
        exit 1
    fi
    
    # Build Docker image if it doesn't exist
    if ! docker image inspect burly-mcp:latest &> /dev/null; then
        print_status "Building Docker image..."
        cd "$PROJECT_ROOT"
        docker build -t burly-mcp:latest -f docker/Dockerfile .
    fi
    
    # Run tests with Docker
    local docker_cmd="docker run --rm -i burly-mcp:latest"
    cd "$PROJECT_ROOT"
    
    if $PYTHON_CMD "$TEST_HARNESS" --demo --server-cmd "$docker_cmd" --timeout "$TIMEOUT"; then
        print_success "Docker tests completed successfully"
        return 0
    else
        print_error "Docker tests failed"
        return 1
    fi
}

# Function to show usage
show_usage() {
    cat << EOF
Burly MCP Test Runner

Usage: $0 [COMMAND] [OPTIONS]

Commands:
    demo                Run basic demo scenarios (config validation only)
    full-test           Run comprehensive tests with mock services (actual functionality)
    interactive         Start interactive testing mode
    health              Run quick health check
    validate-tool TOOL  Validate specific tool (docker_ps, disk_space, etc.)
    validate-all        Validate all available tools
    docker              Run tests using Docker container
    help                Show this help message

Options:
    --timeout SECONDS   Set timeout for operations (default: 30)
    --python COMMAND    Python command to use (default: python3)
    --server-cmd CMD    Custom server command (default: python -m server.main)

Examples:
    $0 demo                           # Run demo scenarios
    $0 interactive                    # Interactive mode
    $0 validate-tool docker_ps        # Test Docker tool
    $0 validate-all                   # Test all tools
    $0 docker                         # Test with Docker
    $0 demo --timeout 60              # Demo with 60s timeout

Environment Variables:
    BURLY_MCP_TIMEOUT    Default timeout (overridden by --timeout)
    BURLY_MCP_PYTHON     Python command (overridden by --python)

EOF
}

# Parse command line arguments
COMMAND=""
while [[ $# -gt 0 ]]; do
    case $1 in
        demo|interactive|health|validate-all|docker|help|full-test)
            COMMAND="$1"
            shift
            ;;
        validate-tool)
            COMMAND="validate-tool"
            shift
            if [[ $# -gt 0 ]]; then
                TOOL_NAME="$1"
                shift
            else
                print_error "validate-tool requires a tool name"
                exit 1
            fi
            ;;
        --timeout)
            shift
            if [[ $# -gt 0 ]]; then
                TIMEOUT="$1"
                shift
            else
                print_error "--timeout requires a value"
                exit 1
            fi
            ;;
        --python)
            shift
            if [[ $# -gt 0 ]]; then
                PYTHON_CMD="$1"
                shift
            else
                print_error "--python requires a command"
                exit 1
            fi
            ;;
        --server-cmd)
            shift
            if [[ $# -gt 0 ]]; then
                SERVER_CMD="$1"
                shift
            else
                print_error "--server-cmd requires a command"
                exit 1
            fi
            ;;
        *)
            print_error "Unknown option: $1"
            show_usage
            exit 1
            ;;
    esac
done

# Use environment variables if set
TIMEOUT="${BURLY_MCP_TIMEOUT:-$TIMEOUT}"
PYTHON_CMD="${BURLY_MCP_PYTHON:-$PYTHON_CMD}"

# Show header
echo "============================================================"
echo "Burly MCP Test Runner"
echo "============================================================"
echo "Project: $(basename "$PROJECT_ROOT")"
echo "Python: $PYTHON_CMD"
echo "Timeout: ${TIMEOUT}s"
echo "Server: $SERVER_CMD"
echo "============================================================"
echo

# Check dependencies first
check_dependencies

# Source development environment if available
if [[ -f "$PROJECT_ROOT/.env.development" ]]; then
    print_status "Loading development environment..."
    source "$PROJECT_ROOT/.env.development" > /dev/null 2>&1
fi

# Execute command
case "$COMMAND" in
    demo)
        run_demo
        ;;
    full-test)
        run_full_test
        ;;
    interactive)
        run_interactive
        ;;
    health)
        run_health_check
        ;;
    validate-tool)
        validate_tool "$TOOL_NAME"
        ;;
    validate-all)
        validate_all_tools
        ;;
    docker)
        run_with_docker
        ;;
    help|"")
        show_usage
        ;;
    *)
        print_error "Unknown command: $COMMAND"
        show_usage
        exit 1
        ;;
esac

exit_code=$?

echo
if [[ $exit_code -eq 0 ]]; then
    print_success "Test runner completed successfully"
else
    print_error "Test runner completed with errors"
fi

exit $exit_code