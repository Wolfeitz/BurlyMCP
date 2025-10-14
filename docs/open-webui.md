# Open WebUI Integration Guide

## Overview

This guide shows you how to integrate Burly MCP with Open WebUI, enabling your AI assistant to safely execute system operations through natural language commands. Open WebUI is a popular web interface for AI models that supports the Model Context Protocol (MCP).

## Prerequisites

Before starting, ensure you have:
- Burly MCP deployed and running (see `docs/runbook.md`)
- Open WebUI installed and configured
- Basic understanding of MCP concepts (see `docs/mcp-explained.md`)

## Integration Methods

### Method 1: Docker Container Integration (Recommended)

This method connects Open WebUI to the Burly MCP container directly.

#### 1. Configure MCP in Open WebUI

Add Burly MCP to your Open WebUI MCP configuration:

```json
{
  "mcpServers": {
    "burly-mcp": {
      "command": "docker",
      "args": [
        "exec", "-i", "burly-mcp", 
        "python", "-m", "server.main"
      ],
      "env": {},
      "disabled": false,
      "autoApprove": []
    }
  }
}
```

#### 2. Verify Container Access

Ensure Open WebUI can access the Burly MCP container:

```bash
# Test container connectivity
docker exec -i burly-mcp python -m server.main <<< '{"method": "list_tools"}'

# Expected response should show available tools
```

#### 3. Configure Auto-Approval (Optional)

For frequently used read-only tools, you can enable auto-approval:

```json
{
  "mcpServers": {
    "burly-mcp": {
      "command": "docker",
      "args": ["exec", "-i", "burly-mcp", "python", "-m", "server.main"],
      "env": {},
      "disabled": false,
      "autoApprove": [
        "docker_ps",
        "disk_space"
      ]
    }
  }
}
```

### Method 2: Direct Execution (Advanced)

For advanced users who want to run Burly MCP directly:

```json
{
  "mcpServers": {
    "burly-mcp": {
      "command": "python",
      "args": ["-m", "server.main"],
      "env": {
        "BLOG_STAGE_ROOT": "/path/to/blog/staging",
        "BLOG_PUBLISH_ROOT": "/path/to/blog/publish",
        "GOTIFY_URL": "https://your-gotify-server.com",
        "GOTIFY_TOKEN": "your-token-here"
      },
      "disabled": false,
      "cwd": "/path/to/burly-mcp"
    }
  }
}
```

## Testing the Integration

### 1. Verify Tool Discovery

In Open WebUI, ask:
```
"What tools do you have available?"
```

Expected response should list:
- docker_ps: List Docker containers
- disk_space: Show filesystem usage
- blog_stage_markdown: Validate blog content
- blog_publish_static: Publish blog content
- gotify_ping: Send test notifications

### 2. Test Read-Only Operations

Try these commands:

```
"Show me my running Docker containers"
"Check my disk space"
"What's the status of my system?"
```

### 3. Test Validation Operations

```
"Validate the blog post at staging/my-post.md"
"Check if my blog content is ready to publish"
```

### 4. Test Mutating Operations (with Confirmation)

```
"Publish my blog post from staging/my-post"
"Send a test notification to Gotify"
```

These should prompt for confirmation before executing.

## Example Workflows

### System Monitoring Workflow

**User**: "Give me a system status report"

**AI Response**: "I'll check your Docker containers and disk usage."

**Behind the scenes**:
1. AI calls `docker_ps` tool
2. AI calls `disk_space` tool
3. AI formats results into readable report

**Sample Output**:
```
System Status Report:

Docker Containers:
- burly-mcp: Up 2 hours
- nginx: Up 5 days
- postgres: Up 5 days

Disk Usage:
- /: 45% used (12GB/27GB)
- /var: 23% used (2.3GB/10GB)
- /home: 67% used (67GB/100GB)

All systems appear healthy!
```

### Blog Publishing Workflow

**User**: "I want to publish my latest blog post"

**AI Response**: "I'll help you publish your blog post. Let me first validate the content."

**Step 1 - Validation**:
```
AI: "Which blog post would you like to publish?"
User: "The one in staging/new-feature-announcement"
AI: [Calls blog_stage_markdown tool]
AI: "✅ Blog post validation successful! Front-matter is valid and all required fields are present."
```

**Step 2 - Confirmation**:
```
AI: "Ready to publish 'New Feature Announcement' to your live blog. This will copy files to the publish directory. Should I proceed?"
User: "Yes, go ahead"
AI: [Calls blog_publish_static with _confirm: true]
AI: "✅ Successfully published 3 files to your blog!"
```

### Notification Testing Workflow

**User**: "Test my notification system"

**AI Response**: "I'll send a test notification to your Gotify server."

**Behind the scenes**:
1. AI calls `gotify_ping` tool (requires confirmation)
2. User confirms the action
3. Test notification sent
4. AI reports success/failure

## Advanced Configuration

### Custom Tool Prompts

You can create custom prompts that leverage MCP tools effectively:

#### System Health Check Prompt
```
You are a system administrator assistant. When asked about system health:
1. Always check Docker containers with docker_ps
2. Always check disk space with disk_space
3. Format the results in a clear, actionable report
4. Highlight any concerning metrics (>80% disk usage, stopped containers)
5. Suggest actions if problems are found
```

#### Blog Management Prompt
```
You are a blog publishing assistant. For blog operations:
1. Always validate content with blog_stage_markdown before publishing
2. Explain what will happen before requesting confirmation
3. Provide clear success/failure feedback
4. Suggest next steps after publishing
```

### Environment-Specific Configuration

#### Development Environment
```json
{
  "mcpServers": {
    "burly-mcp-dev": {
      "command": "docker",
      "args": ["exec", "-i", "burly-mcp-dev", "python", "-m", "server.main"],
      "env": {},
      "disabled": false,
      "autoApprove": ["docker_ps", "disk_space", "blog_stage_markdown"]
    }
  }
}
```

#### Production Environment
```json
{
  "mcpServers": {
    "burly-mcp-prod": {
      "command": "docker",
      "args": ["exec", "-i", "burly-mcp-prod", "python", "-m", "server.main"],
      "env": {},
      "disabled": false,
      "autoApprove": []  // No auto-approval in production
    }
  }
}
```

## Security Considerations

### 1. Auto-Approval Settings

**Safe for auto-approval**:
- `docker_ps` (read-only)
- `disk_space` (read-only)
- `blog_stage_markdown` (validation only)

**Never auto-approve**:
- `blog_publish_static` (modifies files)
- `gotify_ping` (sends external notifications)

### 2. User Education

Educate users about:
- **Confirmation prompts**: Always review what will happen
- **Audit trails**: Operations are logged for security
- **Safe operations**: Read-only vs. mutating operations
- **Error handling**: What to do when operations fail

### 3. Access Control

Consider implementing:
- **User-specific MCP configurations**: Different tools for different users
- **Time-based restrictions**: Limit when certain operations can be performed
- **Approval workflows**: Multi-step approval for sensitive operations

## Troubleshooting

### Common Issues

#### "MCP server not found" or "Connection failed"

**Symptoms**: Open WebUI can't connect to Burly MCP

**Solutions**:
1. Verify Burly MCP container is running:
   ```bash
   docker ps | grep burly-mcp
   ```

2. Test direct connection:
   ```bash
   docker exec -i burly-mcp python -m server.main <<< '{"method": "list_tools"}'
   ```

3. Check Open WebUI logs for connection errors

4. Verify MCP configuration syntax in Open WebUI

#### "Tool not found" errors

**Symptoms**: AI says tools aren't available

**Solutions**:
1. Check tool availability:
   ```bash
   docker exec -i burly-mcp python -m server.main <<< '{"method": "list_tools"}'
   ```

2. Verify policy configuration in `policy/tools.yaml`

3. Check container logs for policy loading errors:
   ```bash
   docker logs burly-mcp
   ```

#### "Permission denied" or "Path not found" errors

**Symptoms**: File operations fail with permission errors

**Solutions**:
1. Verify directory mounts in `docker-compose.yml`
2. Check directory permissions:
   ```bash
   ls -la /path/to/blog/directories
   ```
3. Ensure directories exist and are accessible

#### Confirmation workflows not working

**Symptoms**: Mutating operations execute without confirmation

**Solutions**:
1. Check `requires_confirm: true` in policy configuration
2. Verify `_confirm` parameter handling in tool implementation
3. Review Open WebUI MCP configuration for auto-approval settings

### Debug Mode

Enable debug logging for troubleshooting:

```yaml
# In docker-compose.yml
environment:
  - LOG_LEVEL=DEBUG
```

Then check logs:
```bash
docker logs -f burly-mcp
```

### Testing MCP Protocol Directly

For advanced debugging, test the MCP protocol directly:

```bash
# Test tool discovery
echo '{"method": "list_tools"}' | docker exec -i burly-mcp python -m server.main

# Test tool execution
echo '{"method": "call_tool", "params": {"name": "disk_space", "arguments": {}}}' | \
  docker exec -i burly-mcp python -m server.main
```

## Best Practices

### 1. Start Simple
- Begin with read-only operations
- Test each tool individually
- Gradually introduce mutating operations

### 2. User Training
- Explain confirmation workflows
- Show users how to interpret results
- Teach troubleshooting basics

### 3. Monitoring
- Regularly check audit logs
- Monitor system resource usage
- Review notification patterns

### 4. Maintenance
- Keep Burly MCP updated
- Review and update tool policies
- Test integrations after updates

## Example Agent Prompts

### System Administrator Agent
```
You are a helpful system administrator assistant with access to system monitoring tools. 

When users ask about system status:
- Use docker_ps to check container health
- Use disk_space to check storage usage
- Provide clear, actionable summaries
- Highlight any issues that need attention

When users ask about blog publishing:
- Always validate content first with blog_stage_markdown
- Explain what publishing will do
- Request confirmation for publishing operations
- Provide clear success/failure feedback

Always be helpful but cautious with system operations.
```

### Blog Management Agent
```
You are a blog publishing assistant that helps users manage their static site content.

For blog operations:
1. Validate content before publishing using blog_stage_markdown
2. Explain what files will be published and where
3. Always request confirmation before publishing
4. Provide clear feedback on success or failure
5. Suggest next steps after publishing

Be encouraging but thorough in your validation process.
```

This integration guide should help you successfully connect Open WebUI with Burly MCP, enabling powerful AI-assisted system operations through natural language commands.