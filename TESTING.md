# Burly MCP Testing Guide

## Overview

This testing framework provides comprehensive validation of the Burly MCP server with **adaptive testing** that works across different environments and configurations.

## Quick Start

### 1. Basic Configuration Testing
Tests error handling and basic functionality without external dependencies:

```bash
# Set up environment (creates local directories)
source .env.development

# Run basic tests
./scripts/run_tests.sh demo
```

### 2. Adaptive Integration Testing  
Tests real functionality when dependencies are available, error handling when they're not:

```bash
# Run adaptive tests (RECOMMENDED)
./scripts/run_tests.sh full-test
```

### 3. Individual Tool Validation
```bash
# Test specific tools
./scripts/run_tests.sh validate-tool docker_ps
./scripts/run_tests.sh validate-all
```

## Testing Strategy

The test framework uses **adaptive testing** - it automatically detects what's available in your environment and tests accordingly:

### When Docker is Available
- ✅ **Integration Test**: Tests real Docker container listing
- ✅ **Validation**: Verifies Docker command execution and output parsing

### When Docker is Not Available  
- ✅ **Error Handling Test**: Verifies graceful degradation
- ✅ **User Feedback**: Tests appropriate error messages

### When Gotify is Configured
- ✅ **Integration Test**: Tests real notification sending with mock server
- ✅ **Input Validation**: Tests message length limits and character restrictions

### When Gotify is Not Configured
- ✅ **Error Handling Test**: Verifies configuration validation
- ✅ **User Guidance**: Tests helpful configuration error messages

### Always Tested (Environment Independent)
- ✅ **MCP Protocol**: list_tools, call_tool, error handling
- ✅ **Security**: Path traversal prevention, input sanitization  
- ✅ **Blog Operations**: File validation, confirmation workflows
- ✅ **JSON Validation**: Schema compliance for all responses

## Test Categories

### 1. Protocol Tests
- MCP request/response cycle
- Invalid method handling
- Malformed JSON handling

### 2. Integration Tests  
- Real Docker operations (when available)
- Real filesystem operations
- Real notification sending (with mock server)

### 3. Security Tests
- Path traversal prevention
- Input validation and sanitization
- Confirmation workflow enforcement

### 4. Error Handling Tests
- Graceful degradation when dependencies unavailable
- Helpful error messages and user guidance
- Configuration validation

## Interactive Testing

```bash
./scripts/run_tests.sh interactive
```

Example session:
```
mcp> {"method": "list_tools"}
✅ Response: {"ok": true, "summary": "Available tools: 5 tools found", ...}

mcp> {"method": "call_tool", "name": "docker_ps", "args": {}}
✅ Response: {"ok": true, "summary": "Found 0 running containers", ...}

mcp> {"method": "call_tool", "name": "blog_stage_markdown", "args": {"file_path": "../../../etc/passwd"}}
✅ Response: {"ok": false, "summary": "Path traversal detected", ...}

mcp> help
Available commands:
  help     - Show this help message
  demo     - Run a quick demo
  quit     - Exit interactive mode
```

## Environment Configuration

### Development Environment (`.env.development`)
- Uses local directories (`./logs`, `./test_data`)
- Disables external services (Gotify)
- Tests error handling and basic functionality

### Testing Environment (`.env.testing`)  
- Enables mock services for integration testing
- Tests real functionality with controlled dependencies
- Validates complete workflows

### Custom Configuration
You can create your own environment configuration:

```bash
# Custom environment
export LOG_DIR="./my_test_logs"
export BLOG_STAGE_ROOT="./my_test_blog"
export GOTIFY_URL="http://my-gotify-server:8080"
export GOTIFY_TOKEN="my-token"

# Run tests
./scripts/run_tests.sh full-test
```

## Expected Results

The test framework adapts to your environment:

### Minimal Environment (No Docker, No Gotify)
```
Total Tests: 7
✅ Protocol tests (2/2)
✅ Blog tests (3/3) 
✅ Error handling tests (2/2)
Success Rate: 100%
```

### Full Environment (Docker + Mock Gotify)
```
Total Tests: 10
✅ Protocol tests (2/2)
✅ Integration tests (3/3)
✅ Security tests (3/3)
✅ Error handling tests (2/2)
Success Rate: 100%
```

## Troubleshooting

### "Permission denied" errors
```bash
# Ensure directories are writable
chmod -R 755 logs test_data
```

### "Docker not available" 
This is expected if Docker isn't installed. The tests will automatically switch to error handling validation.

### "Mock server failed to start"
```bash
# Check if port is available
netstat -ln | grep :8080

# Or let the system choose a port automatically (default behavior)
```

### Test failures
1. Check that you're in the project root directory
2. Ensure `policy/tools.yaml` exists
3. Run with verbose logging: `LOG_LEVEL=DEBUG ./scripts/run_tests.sh full-test`

## For Developers

### Adding New Tests
1. Add scenarios to `scripts/test_strategy.py`
2. Update expected responses in `scripts/test_config.py`
3. Test both "available" and "unavailable" dependency scenarios

### Mock Services
- `scripts/mock_gotify_server.py` - Mock Gotify API server
- Automatically finds free ports
- Provides realistic API responses for testing

### Portable Configuration
- All paths are relative to project root
- No hardcoded local environment details
- Works across different operating systems and setups

The testing framework ensures the MCP server works correctly across different environments while providing meaningful feedback about what's being tested and why.