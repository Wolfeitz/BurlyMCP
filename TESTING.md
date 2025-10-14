# Burly MCP Testing Guide

## Quick Start

1. **Set up development environment:**
   ```bash
   source .env.development
   ```

2. **Run comprehensive tests:**
   ```bash
   ./scripts/run_tests.sh demo
   ```

3. **Validate all tools:**
   ```bash
   ./scripts/run_tests.sh validate-all
   ```

## Test Results

✅ **100% Success Rate Achieved!**

All 11 test scenarios are now passing:
- ✅ list_tools_basic - MCP protocol functionality
- ✅ docker_ps_success - Docker container monitoring  
- ✅ disk_space_success - Filesystem monitoring
- ✅ blog_validate_success - Markdown validation
- ✅ blog_validate_path_traversal - Security (path traversal prevention)
- ✅ blog_publish_no_confirm - Confirmation workflow
- ✅ blog_publish_with_confirm - Publishing functionality
- ✅ gotify_ping_success - Notification system (config validation)
- ✅ invalid_tool_name - Error handling
- ✅ invalid_method - Protocol error handling  
- ✅ malformed_json - Input validation

## Interactive Testing

```bash
./scripts/run_tests.sh interactive
```

Example commands:
```
mcp> {"method": "list_tools"}
mcp> {"method": "call_tool", "name": "docker_ps", "args": {}}
mcp> help
mcp> quit
```

## Individual Tool Testing

```bash
./scripts/run_tests.sh validate-tool docker_ps
```

## What's Working

- **MCP Protocol**: Full request/response cycle
- **Security**: Path traversal prevention, input validation
- **Tools**: All 5 tools (docker_ps, disk_space, blog_stage_markdown, blog_publish_static, gotify_ping)
- **Error Handling**: Graceful handling of invalid requests
- **Confirmation Workflow**: Proper confirmation for mutating operations
- **JSON Validation**: Strict schema validation for all responses

The test harness successfully validates the complete MCP implementation!