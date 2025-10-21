# Test Triage Implementation Tasks

## PHASE 1: Fix Security Tests (CURRENT)
- [x] Start security test rewrite
- [ ] **TASK 1A**: Complete test_security.py rewrite with proper interface matching
- [ ] **TASK 1B**: Fix the broken symlink test that's currently failing
- [ ] **TASK 1C**: Add missing audit_security_event test with correct signature

## PHASE 2: Rewrite Config Tests  
- [ ] **TASK 2A**: Completely rewrite test_config.py for new Config class interface
- [ ] **TASK 2B**: Test Config.__getattr__ behavior
- [ ] **TASK 2C**: Test Config environment variable loading
- [ ] **TASK 2D**: Test Config validation methods

## PHASE 3: Rewrite Audit Tests
- [ ] **TASK 3A**: Rewrite test_audit.py for AuditLogger class
- [ ] **TASK 3B**: Test log_tool_execution with correct signature
- [ ] **TASK 3C**: Test log_security_violation method
- [ ] **TASK 3D**: Test global audit functions

## PHASE 4: Rewrite Remaining Core Tests
- [ ] **TASK 4A**: Rewrite test_notifications.py for provider-based system
- [ ] **TASK 4B**: Rewrite test_policy.py for security-aware PolicyLoader
- [ ] **TASK 4C**: Rewrite test_resource_limits.py for current ResourceLimiter
- [ ] **TASK 4D**: Rewrite test_tools.py for current ToolRegistry

## PHASE 5: Add Missing Tests
- [ ] **TASK 5A**: Create test_mcp_protocol.py for MCPProtocolHandler
- [ ] **TASK 5B**: Create test_server_main.py for main application functions
- [ ] **TASK 5C**: Remove obsolete test_server.py

## CURRENT STATUS: Working on TASK 1A