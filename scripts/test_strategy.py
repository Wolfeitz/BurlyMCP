#!/usr/bin/env python3
"""
Comprehensive Testing Strategy for MCP Tools

This module implements a proper testing strategy that handles configurable dependencies
correctly by testing different scenarios based on what's actually available.
"""

import os
import subprocess
import sys
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple


@dataclass
class DependencyCheck:
    """Represents a dependency check result."""
    name: str
    available: bool
    version: Optional[str] = None
    error: Optional[str] = None


class DependencyChecker:
    """Checks availability of external dependencies."""
    
    def check_docker(self) -> DependencyCheck:
        """Check if Docker is available and accessible."""
        try:
            result = subprocess.run(
                ["docker", "version", "--format", "{{.Server.Version}}"],
                capture_output=True,
                text=True,
                timeout=5
            )
            if result.returncode == 0:
                return DependencyCheck("docker", True, result.stdout.strip())
            else:
                return DependencyCheck("docker", False, error=result.stderr.strip())
        except (subprocess.TimeoutExpired, FileNotFoundError) as e:
            return DependencyCheck("docker", False, error=str(e))
    
    def check_gotify_config(self) -> DependencyCheck:
        """Check if Gotify is configured."""
        gotify_url = os.environ.get("GOTIFY_URL")
        gotify_token = os.environ.get("GOTIFY_TOKEN")
        
        if not gotify_url:
            return DependencyCheck("gotify", False, error="GOTIFY_URL not set")
        if not gotify_token:
            return DependencyCheck("gotify", False, error="GOTIFY_TOKEN not set")
        
        # Could add actual connectivity test here
        return DependencyCheck("gotify", True, version=gotify_url)
    
    def check_filesystem_access(self) -> DependencyCheck:
        """Check filesystem access for blog operations."""
        blog_stage = os.environ.get("BLOG_STAGE_ROOT", "./test_data/blog/stage")
        blog_publish = os.environ.get("BLOG_PUBLISH_ROOT", "./test_data/blog/publish")
        
        try:
            # Check if we can read from stage and write to publish
            if not os.path.exists(blog_stage):
                os.makedirs(blog_stage, exist_ok=True)
            if not os.path.exists(blog_publish):
                os.makedirs(blog_publish, exist_ok=True)
            
            # Test write access
            test_file = os.path.join(blog_publish, ".test_write")
            with open(test_file, "w") as f:
                f.write("test")
            os.remove(test_file)
            
            return DependencyCheck("filesystem", True)
        except Exception as e:
            return DependencyCheck("filesystem", False, error=str(e))
    
    def check_all(self) -> Dict[str, DependencyCheck]:
        """Check all dependencies."""
        return {
            "docker": self.check_docker(),
            "gotify": self.check_gotify_config(),
            "filesystem": self.check_filesystem_access()
        }


class TestScenarioGenerator:
    """Generates appropriate test scenarios based on available dependencies."""
    
    def __init__(self, dependencies: Dict[str, DependencyCheck]):
        self.dependencies = dependencies
    
    def generate_docker_tests(self) -> List[Dict]:
        """Generate Docker-related test scenarios."""
        if self.dependencies["docker"].available:
            return [
                {
                    "name": "docker_ps_real",
                    "description": "Test Docker container listing with real Docker daemon",
                    "request": {"method": "call_tool", "name": "docker_ps", "args": {}},
                    "expected": {"ok": True, "summary_contains": "Found"},
                    "category": "integration"
                }
            ]
        else:
            return [
                {
                    "name": "docker_ps_unavailable",
                    "description": "Test Docker container listing when Docker unavailable",
                    "request": {"method": "call_tool", "name": "docker_ps", "args": {}},
                    "expected": {"ok": False, "summary_contains": "Docker"},
                    "category": "error_handling"
                }
            ]
    
    def generate_gotify_tests(self) -> List[Dict]:
        """Generate Gotify-related test scenarios."""
        tests = []
        
        if self.dependencies["gotify"].available:
            tests.append({
                "name": "gotify_ping_configured",
                "description": "Test Gotify notification with real configuration",
                "request": {"method": "call_tool", "name": "gotify_ping", "args": {"message": "Test"}},
                "expected": {"ok": True, "summary_contains": "sent"},
                "category": "integration"
            })
        else:
            tests.append({
                "name": "gotify_ping_not_configured",
                "description": "Test Gotify error handling when not configured",
                "request": {"method": "call_tool", "name": "gotify_ping", "args": {"message": "Test"}},
                "expected": {"ok": False, "summary_contains": "not configured"},
                "category": "error_handling"
            })
        
        # Only test input validation if Gotify is configured
        # (Can't test validation if configuration check fails first)
        if self.dependencies["gotify"].available:
            tests.append({
                "name": "gotify_ping_invalid_message",
                "description": "Test Gotify input validation with configured service",
                "request": {"method": "call_tool", "name": "gotify_ping", "args": {"message": "x" * 300}},
                "expected": {"ok": False, "summary_contains": "validation"},
                "category": "validation"
            })
        
        return tests
    
    def generate_blog_tests(self) -> List[Dict]:
        """Generate blog-related test scenarios."""
        if not self.dependencies["filesystem"].available:
            return [
                {
                    "name": "blog_filesystem_error",
                    "description": "Test blog operations when filesystem unavailable",
                    "request": {"method": "call_tool", "name": "blog_stage_markdown", "args": {"file_path": "test.md"}},
                    "expected": {"ok": False, "summary_contains": "filesystem"},
                    "category": "error_handling"
                }
            ]
        
        return [
            {
                "name": "blog_validate_success",
                "description": "Test blog validation with real filesystem",
                "request": {"method": "call_tool", "name": "blog_stage_markdown", "args": {"file_path": "test-post.md"}},
                "expected": {"ok": True, "summary_contains": "validation passed"},
                "category": "integration"
            },
            {
                "name": "blog_validate_path_traversal",
                "description": "Test path traversal prevention",
                "request": {"method": "call_tool", "name": "blog_stage_markdown", "args": {"file_path": "../../../etc/passwd"}},
                "expected": {"ok": False, "summary_contains": "Path traversal"},
                "category": "security"
            },
            {
                "name": "blog_publish_confirmation",
                "description": "Test blog publishing confirmation workflow",
                "request": {"method": "call_tool", "name": "blog_publish_static", "args": {"source_files": ["test-post.md"]}},
                "expected": {"ok": False, "summary_contains": "confirmation"},
                "category": "security"
            }
        ]
    
    def generate_all_scenarios(self) -> Dict[str, List[Dict]]:
        """Generate all test scenarios categorized by type."""
        return {
            "docker": self.generate_docker_tests(),
            "gotify": self.generate_gotify_tests(),
            "blog": self.generate_blog_tests(),
            "protocol": [
                {
                    "name": "list_tools",
                    "description": "Test MCP list_tools operation",
                    "request": {"method": "list_tools"},
                    "expected": {"ok": True, "summary_contains": "tools found"},
                    "category": "protocol"
                },
                {
                    "name": "invalid_method",
                    "description": "Test invalid MCP method handling",
                    "request": {"method": "invalid_method"},
                    "expected": {"ok": False, "summary_contains": "parsing failed"},
                    "category": "protocol"
                }
            ]
        }


def main():
    """Demonstrate the testing strategy."""
    print("=== MCP Testing Strategy Analysis ===\n")
    
    # Check dependencies
    checker = DependencyChecker()
    deps = checker.check_all()
    
    print("Dependency Status:")
    for name, dep in deps.items():
        status = "✅ Available" if dep.available else "❌ Unavailable"
        print(f"  {name}: {status}")
        if dep.version:
            print(f"    Version/Config: {dep.version}")
        if dep.error:
            print(f"    Error: {dep.error}")
    print()
    
    # Generate test scenarios
    generator = TestScenarioGenerator(deps)
    scenarios = generator.generate_all_scenarios()
    
    print("Generated Test Scenarios:")
    for category, tests in scenarios.items():
        print(f"\n{category.upper()} Tests:")
        for test in tests:
            print(f"  - {test['name']}: {test['description']}")
            print(f"    Category: {test['category']}")
    
    print(f"\nTotal scenarios: {sum(len(tests) for tests in scenarios.values())}")
    
    # Show testing strategy summary
    print("\n=== Testing Strategy Summary ===")
    print("1. UNIT TESTS: Test tool logic with mocked dependencies")
    print("2. INTEGRATION TESTS: Test with real dependencies when available")
    print("3. ERROR HANDLING TESTS: Test graceful degradation when dependencies unavailable")
    print("4. SECURITY TESTS: Test input validation and security controls")
    print("5. PROTOCOL TESTS: Test MCP protocol compliance")


if __name__ == "__main__":
    main()