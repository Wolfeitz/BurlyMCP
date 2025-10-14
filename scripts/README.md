# Burly MCP Test Harness

A comprehensive command-line tool for testing and validating MCP operations against the Burly MCP server. This test harness provides JSON input/output validation, demo scenarios, and interactive testing capabilities.

## Features

- **Comprehensive Testing**: Full MCP protocol validation with request/response checking
- **Demo Scenarios**: Pre-built test scenarios covering all tools and edge cases
- **Interactive Mode**: Real-time testing with immediate feedback
- **Security Testing**: Path traversal, input validation, and DoS prevention tests
- **JSON Validation**: Strict schema validation for all MCP responses
- **Docker Support**: Test against containerized server instances
- **Batch Testing**: Run multiple scenarios with detailed reporting

## Quick Start

### Run Demo Scenarios
```bash
# Run all demo scenarios
./scripts/run_tests.sh demo

# Or use Python directly
python scripts/test_harness.py --demo
```

### Interactive Testing
```bash
# Start interactive mode
./scripts/run_tests.sh interactive

# Example commands in interactive mode:
mcp> {"method": "list_tools"}
mcp> {"method": "call_tool", "name": "docker_ps", "args": {}}
mcp> help
mcp> quit
```

### Validate Specific Tools
```bash
# Validate a specific tool
./scripts/run_tests.sh validate-tool docker_ps

# Validate all tools
./scripts/run_tests.sh validate-all
```

### Health Check
```bash
# Quick server health check
./scripts/run_tests.sh health
```

## Test Scenarios

The test harness includes comprehensive scenarios covering:

### Basic Operations
- `list_tools_basic` - Basic tool listing functionality
- `docker_ps_success` - Docker container listing
- `disk_space_success` - Filesystem monitoring

### Security Tests
- `blog_validate_path_traversal` - Path traversal prevention
- `blog_validate_security_test_1` - Directory traversal with `../`
- `blog_validate_security_test_2` - Invalid file extension rejection
- `gotify_ping_invalid_message` - Input sanitization testing

### Confirmation Workflow
- `blog_publish_no_confirm` - Publishing without confirmation
- `blog_publish_with_confirm` - Publishing with explicit confirmation
- `blog_publish_confirmation_workflow` - Complete workflow testing

### Error Handling
- `invalid_tool_name` - Non-existent tool handling
- `invalid_method` - Unsupported MCP method handling
- `malformed_json` - Invalid JSON request handling

### Stress Testing
- `stress_test_rapid_requests` - Rate limiting validation
- `blog_publish_too_many_files` - DoS prevention testing

## Usage Examples

### Basic Demo
```bash
# Run comprehensive demo
python scripts/test_harness.py --demo
```

### Custom Server Command
```bash
# Test against Docker container
python scripts/test_harness.py --demo --server-cmd "docker run --rm -i burly-mcp"

# Test with custom timeout
python scripts/test_harness.py --demo --timeout 60
```

### Interactive Testing
```bash
python scripts/test_harness.py --interactive
```

Example interactive session:
```
mcp> {"method": "list_tools"}
✅ Response received:
{
  "ok": true,
  "summary": "Available tools: 5 tools found",
  "data": {
    "tools": [...]
  }
}

mcp> {"method": "call_tool", "name": "docker_ps", "args": {}}
✅ Docker containers listed successfully

mcp> help
Available commands:
  help     - Show this help message
  demo     - Run a quick demo
  quit     - Exit interactive mode
```

### Tool Validation
```bash
# Validate specific tool
python scripts/test_harness.py --validate-tool docker_ps

# Expected output:
# Validating tool: docker_ps
# ✅ Tool 'docker_ps' found in tool list
# ✅ Tool 'docker_ps' executed successfully
```

## Test Configuration

### Environment Variables
```bash
export BURLY_MCP_TIMEOUT=60        # Default timeout
export BURLY_MCP_PYTHON=python3.12 # Python command
```

### Custom Test Scenarios
Create custom test scenarios in JSON format:

```json
{
  "scenarios": [
    {
      "name": "custom_test",
      "description": "Custom test scenario",
      "request": {
        "method": "call_tool",
        "name": "docker_ps",
        "args": {}
      },
      "expected_response": {
        "ok": true,
        "summary": "Success"
      },
      "should_succeed": true,
      "timeout": 30
    }
  ]
}
```

## Response Validation

The test harness validates all responses against a strict JSON schema:

```json
{
  "type": "object",
  "properties": {
    "ok": {"type": "boolean"},
    "summary": {"type": "string"},
    "need_confirm": {"type": "boolean"},
    "data": {"type": ["object", "null"]},
    "stdout": {"type": "string"},
    "stderr": {"type": "string"},
    "error": {"type": ["string", "null"]},
    "metrics": {
      "type": "object",
      "properties": {
        "elapsed_ms": {"type": "number"},
        "exit_code": {"type": "number"}
      },
      "required": ["elapsed_ms", "exit_code"]
    }
  },
  "required": ["ok", "summary", "metrics"]
}
```

## Security Testing

The harness includes comprehensive security tests:

### Path Traversal Prevention
```bash
# Tests directory traversal attempts
{"method": "call_tool", "name": "blog_stage_markdown", "args": {"file_path": "../../../etc/passwd"}}
```

### Input Validation
```bash
# Tests invalid file extensions
{"method": "call_tool", "name": "blog_stage_markdown", "args": {"file_path": "malicious.exe"}}
```

### DoS Prevention
```bash
# Tests file count limits
{"method": "call_tool", "name": "blog_publish_static", "args": {"source_files": ["file1.md", "file2.md", ...]}}
```

### Rate Limiting
```bash
# Tests rapid request handling
# Multiple rapid requests to test rate limiting
```

## Docker Testing

Test against containerized server:

```bash
# Build and test with Docker
./scripts/run_tests.sh docker

# Or manually
docker build -t burly-mcp .
python scripts/test_harness.py --demo --server-cmd "docker run --rm -i burly-mcp"
```

## Troubleshooting

### Common Issues

**Server not responding:**
```bash
# Check server startup
python -m server.main
# Should wait for input on stdin
```

**Permission errors:**
```bash
# Ensure script is executable
chmod +x scripts/run_tests.sh

# Check Python path
which python3
```

**Timeout errors:**
```bash
# Increase timeout
./scripts/run_tests.sh demo --timeout 60
```

### Debug Mode

Enable verbose logging:
```bash
export LOG_LEVEL=DEBUG
python scripts/test_harness.py --demo
```

### Test Failures

When tests fail, check:
1. Server configuration and policy files
2. Environment variables and permissions
3. Docker socket access (for Docker tests)
4. Network connectivity (for Gotify tests)

## Integration with CI/CD

Example GitHub Actions workflow:

```yaml
name: MCP Tests
on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - uses: actions/setup-python@v4
        with:
          python-version: '3.12'
      - run: pip install -e .
      - run: ./scripts/run_tests.sh demo
      - run: ./scripts/run_tests.sh validate-all
```

## Contributing

When adding new tools or features:

1. Add test scenarios to `test_scenarios.json`
2. Update the demo scenarios in `test_harness.py`
3. Add validation rules for new response formats
4. Test security implications with path traversal and input validation
5. Update this README with new examples

## Requirements

- Python 3.12+
- jsonschema library
- Access to MCP server (local or Docker)
- Optional: Docker for container testing

## Files

- `test_harness.py` - Main test harness implementation
- `test_scenarios.json` - Extended test scenario definitions
- `run_tests.sh` - Convenience shell script
- `README.md` - This documentation

## License

Same as Burly MCP project (MIT License).