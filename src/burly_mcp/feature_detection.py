"""
Feature Detection Framework

This module implements comprehensive feature detection for BurlyMCP,
allowing the system to gracefully degrade when optional features
are not available or properly configured.

Key Features:
- Docker socket availability detection
- Gotify notification configuration validation
- Blog directory accessibility checks
- Policy file and configuration validation
- Feature status reporting for /health endpoint

The framework provides a unified interface for checking feature
availability and generating appropriate error responses when
features are unavailable.
"""

import json
import logging
import os
import socket
import subprocess  # nosec B404 - Used for safe Docker version detection only
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml

logger = logging.getLogger(__name__)


@dataclass
class FeatureStatus:
    """
    Status information for a system feature.
    
    Provides detailed information about feature availability,
    configuration status, and any issues preventing use.
    """
    name: str
    available: bool
    configured: bool
    error: Optional[str] = None
    details: Optional[Dict[str, Any]] = None
    suggestion: Optional[str] = None


class FeatureDetector:
    """
    Comprehensive feature detection system.
    
    Detects availability of optional system features and provides
    structured information about their status for health reporting
    and graceful degradation.
    """
    
    def __init__(self):
        """Initialize the feature detector."""
        self._cache: Dict[str, FeatureStatus] = {}
        self._cache_ttl = 30  # Cache results for 30 seconds
        self._cache_time: Dict[str, float] = {}
    
    def get_all_features(self) -> Dict[str, FeatureStatus]:
        """
        Get status of all system features.
        
        Returns:
            Dictionary mapping feature names to their status
        """
        features = {}
        
        # Core system features
        features["docker"] = self.check_docker_availability()
        features["notifications"] = self.check_notifications_configured()
        features["blog_directories"] = self.check_blog_directories_accessible()
        features["policy"] = self.check_policy_loaded()
        
        return features
    
    def check_docker_availability(self) -> FeatureStatus:
        """
        Check if Docker operations are available.
        
        Performs comprehensive Docker availability detection including:
        - Docker socket accessibility
        - Docker CLI availability
        - Docker daemon connectivity
        
        Returns:
            FeatureStatus with Docker availability information
        """
        feature_name = "docker"
        
        # Check cache first
        if self._is_cached(feature_name):
            return self._cache[feature_name]
        
        try:
            # Check if Docker socket exists and is accessible
            docker_socket = Path("/var/run/docker.sock")
            
            if not docker_socket.exists():
                status = FeatureStatus(
                    name=feature_name,
                    available=False,
                    configured=False,
                    error="Docker socket not found",
                    details={"socket_path": "/var/run/docker.sock"},
                    suggestion="Mount /var/run/docker.sock to enable Docker operations"
                )
                self._cache_result(feature_name, status)
                return status
            
            if not docker_socket.is_socket():
                status = FeatureStatus(
                    name=feature_name,
                    available=False,
                    configured=False,
                    error="Docker socket path exists but is not a socket",
                    details={"socket_path": "/var/run/docker.sock"},
                    suggestion="Ensure /var/run/docker.sock is properly mounted"
                )
                self._cache_result(feature_name, status)
                return status
            
            # Check if socket is accessible (readable)
            if not os.access(docker_socket, os.R_OK):
                status = FeatureStatus(
                    name=feature_name,
                    available=False,
                    configured=False,
                    error="Docker socket not accessible - permission denied",
                    details={"socket_path": "/var/run/docker.sock"},
                    suggestion="Add the docker group to this container with --group-add <docker_gid>"
                )
                self._cache_result(feature_name, status)
                return status
            
            # Check if Docker CLI is available
            try:
                result = subprocess.run([  # nosec
                    "docker", "--version"],
                    capture_output=True,
                    text=True,
                    timeout=5
                )
                
                if result.returncode != 0:
                    status = FeatureStatus(
                        name=feature_name,
                        available=False,
                        configured=False,
                        error="Docker CLI not working properly",
                        details={"cli_error": result.stderr.strip()},
                        suggestion="Ensure Docker CLI is properly installed"
                    )
                    self._cache_result(feature_name, status)
                    return status
                
                docker_version = result.stdout.strip()
                
            except FileNotFoundError:
                status = FeatureStatus(
                    name=feature_name,
                    available=False,
                    configured=False,
                    error="Docker CLI not found",
                    details={"command": "docker"},
                    suggestion="Install Docker CLI in the container"
                )
                self._cache_result(feature_name, status)
                return status
            
            except subprocess.TimeoutExpired:
                status = FeatureStatus(
                    name=feature_name,
                    available=False,
                    configured=False,
                    error="Docker CLI command timed out",
                    details={"timeout": 5},
                    suggestion="Check Docker daemon connectivity"
                )
                self._cache_result(feature_name, status)
                return status
            
            # Test Docker daemon connectivity with a quick ping
            try:
                result = subprocess.run([  # nosec
                    "docker", "info", "--format", "{{.ServerVersion}}"],
                    capture_output=True,
                    text=True,
                    timeout=10
                )
                
                if result.returncode == 0:
                    server_version = result.stdout.strip()
                    status = FeatureStatus(
                        name=feature_name,
                        available=True,
                        configured=True,
                        details={
                            "client_version": docker_version,
                            "server_version": server_version,
                            "socket_path": "/var/run/docker.sock"
                        }
                    )
                else:
                    # Docker CLI works but daemon not accessible
                    error_msg = result.stderr.strip() or "Docker daemon not accessible"
                    status = FeatureStatus(
                        name=feature_name,
                        available=False,
                        configured=False,
                        error=error_msg,
                        details={"daemon_error": error_msg},
                        suggestion="Ensure Docker daemon is running and socket is properly mounted"
                    )
                
            except subprocess.TimeoutExpired:
                status = FeatureStatus(
                    name=feature_name,
                    available=False,
                    configured=False,
                    error="Docker daemon connection timed out",
                    details={"timeout": 10},
                    suggestion="Check Docker daemon status and network connectivity"
                )
            
            self._cache_result(feature_name, status)
            return status
            
        except Exception as e:
            logger.warning(f"Unexpected error checking Docker availability: {e}")
            status = FeatureStatus(
                name=feature_name,
                available=False,
                configured=False,
                error=f"Unexpected error: {str(e)}",
                suggestion="Check Docker installation and configuration"
            )
            self._cache_result(feature_name, status)
            return status
    
    def check_notifications_configured(self) -> FeatureStatus:
        """
        Check if Gotify notification system is properly configured.
        
        Validates Gotify URL and token configuration without
        actually sending test notifications.
        
        Returns:
            FeatureStatus with notification configuration information
        """
        feature_name = "notifications"
        
        # Check cache first
        if self._is_cached(feature_name):
            return self._cache[feature_name]
        
        try:
            gotify_url = os.environ.get("GOTIFY_URL", "").strip()
            gotify_token = os.environ.get("GOTIFY_TOKEN", "").strip()
            
            if not gotify_url and not gotify_token:
                status = FeatureStatus(
                    name=feature_name,
                    available=False,
                    configured=False,
                    error="Gotify not configured",
                    details={"missing": ["GOTIFY_URL", "GOTIFY_TOKEN"]},
                    suggestion="Set GOTIFY_URL and GOTIFY_TOKEN environment variables to enable notifications"
                )
                self._cache_result(feature_name, status)
                return status
            
            if not gotify_url:
                status = FeatureStatus(
                    name=feature_name,
                    available=False,
                    configured=False,
                    error="Gotify URL not configured",
                    details={"missing": ["GOTIFY_URL"]},
                    suggestion="Set GOTIFY_URL environment variable"
                )
                self._cache_result(feature_name, status)
                return status
            
            if not gotify_token:
                status = FeatureStatus(
                    name=feature_name,
                    available=False,
                    configured=False,
                    error="Gotify token not configured",
                    details={"missing": ["GOTIFY_TOKEN"]},
                    suggestion="Set GOTIFY_TOKEN environment variable"
                )
                self._cache_result(feature_name, status)
                return status
            
            # Validate URL format
            if not (gotify_url.startswith("http://") or gotify_url.startswith("https://")):
                status = FeatureStatus(
                    name=feature_name,
                    available=False,
                    configured=False,
                    error="Invalid Gotify URL format",
                    details={"url": gotify_url},
                    suggestion="GOTIFY_URL must start with http:// or https://"
                )
                self._cache_result(feature_name, status)
                return status
            
            # Basic token validation (should be non-empty and reasonable length)
            if len(gotify_token) < 10:
                status = FeatureStatus(
                    name=feature_name,
                    available=False,
                    configured=False,
                    error="Gotify token appears invalid (too short)",
                    details={"token_length": len(gotify_token)},
                    suggestion="Verify GOTIFY_TOKEN is a valid Gotify application token"
                )
                self._cache_result(feature_name, status)
                return status
            
            # Configuration looks valid
            status = FeatureStatus(
                name=feature_name,
                available=True,
                configured=True,
                details={
                    "url": gotify_url,
                    "token_configured": True,
                    "token_length": len(gotify_token)
                }
            )
            self._cache_result(feature_name, status)
            return status
            
        except Exception as e:
            logger.warning(f"Unexpected error checking notification configuration: {e}")
            status = FeatureStatus(
                name=feature_name,
                available=False,
                configured=False,
                error=f"Unexpected error: {str(e)}",
                suggestion="Check notification environment variables"
            )
            self._cache_result(feature_name, status)
            return status
    
    def check_blog_directories_accessible(self) -> FeatureStatus:
        """
        Check if blog directories are accessible for staging and publishing.
        
        Validates that blog stage and publish directories exist
        and have appropriate permissions.
        
        Returns:
            FeatureStatus with blog directory accessibility information
        """
        feature_name = "blog_directories"
        
        # Check cache first
        if self._is_cached(feature_name):
            return self._cache[feature_name]
        
        try:
            blog_stage_root = os.environ.get("BLOG_STAGE_ROOT", "/app/data/blog/stage")
            blog_publish_root = os.environ.get("BLOG_PUBLISH_ROOT", "/app/data/blog/publish")
            
            issues = []
            details = {
                "stage_root": blog_stage_root,
                "publish_root": blog_publish_root
            }
            
            # Check stage directory
            stage_path = Path(blog_stage_root)
            if not stage_path.exists():
                issues.append(f"Stage directory does not exist: {blog_stage_root}")
                details["stage_exists"] = False
            elif not stage_path.is_dir():
                issues.append(f"Stage path is not a directory: {blog_stage_root}")
                details["stage_exists"] = False
            else:
                details["stage_exists"] = True
                if not os.access(stage_path, os.R_OK):
                    issues.append(f"Stage directory not readable: {blog_stage_root}")
                    details["stage_readable"] = False
                else:
                    details["stage_readable"] = True
            
            # Check publish directory
            publish_path = Path(blog_publish_root)
            if not publish_path.exists():
                # Try to create it
                try:
                    publish_path.mkdir(parents=True, exist_ok=True)
                    details["publish_exists"] = True
                    details["publish_created"] = True
                except OSError as e:
                    issues.append(f"Cannot create publish directory {blog_publish_root}: {e}")
                    details["publish_exists"] = False
                    details["publish_created"] = False
            elif not publish_path.is_dir():
                issues.append(f"Publish path is not a directory: {blog_publish_root}")
                details["publish_exists"] = False
            else:
                details["publish_exists"] = True
                details["publish_created"] = False
            
            # Check publish directory permissions
            if details.get("publish_exists", False):
                if not os.access(publish_path, os.W_OK):
                    issues.append(f"Publish directory not writable: {blog_publish_root}")
                    details["publish_writable"] = False
                else:
                    details["publish_writable"] = True
            
            if issues:
                status = FeatureStatus(
                    name=feature_name,
                    available=False,
                    configured=True,  # Configured but not accessible
                    error=f"Blog directory issues: {'; '.join(issues)}",
                    details=details,
                    suggestion="Mount blog directories with proper permissions or check BLOG_STAGE_ROOT and BLOG_PUBLISH_ROOT settings"
                )
            else:
                status = FeatureStatus(
                    name=feature_name,
                    available=True,
                    configured=True,
                    details=details
                )
            
            self._cache_result(feature_name, status)
            return status
            
        except Exception as e:
            logger.warning(f"Unexpected error checking blog directories: {e}")
            status = FeatureStatus(
                name=feature_name,
                available=False,
                configured=False,
                error=f"Unexpected error: {str(e)}",
                suggestion="Check blog directory configuration and permissions"
            )
            self._cache_result(feature_name, status)
            return status
    
    def check_policy_loaded(self) -> FeatureStatus:
        """
        Check if policy file is accessible and valid.
        
        Validates that the policy file exists, is readable,
        and contains valid YAML configuration.
        
        Returns:
            FeatureStatus with policy file validation information
        """
        feature_name = "policy"
        
        # Check cache first
        if self._is_cached(feature_name):
            return self._cache[feature_name]
        
        try:
            policy_file = os.environ.get("POLICY_FILE", "/app/BurlyMCP/config/policy/tools.yaml")
            policy_path = Path(policy_file)
            
            details = {"policy_file": policy_file}
            
            if not policy_path.exists():
                status = FeatureStatus(
                    name=feature_name,
                    available=False,
                    configured=False,
                    error=f"Policy file not found: {policy_file}",
                    details=details,
                    suggestion="Ensure policy file exists or set POLICY_FILE environment variable"
                )
                self._cache_result(feature_name, status)
                return status
            
            if not policy_path.is_file():
                status = FeatureStatus(
                    name=feature_name,
                    available=False,
                    configured=False,
                    error=f"Policy path is not a file: {policy_file}",
                    details=details,
                    suggestion="Ensure POLICY_FILE points to a valid file"
                )
                self._cache_result(feature_name, status)
                return status
            
            if not os.access(policy_path, os.R_OK):
                status = FeatureStatus(
                    name=feature_name,
                    available=False,
                    configured=False,
                    error=f"Policy file not readable: {policy_file}",
                    details=details,
                    suggestion="Check file permissions for policy file"
                )
                self._cache_result(feature_name, status)
                return status
            
            # Try to parse the YAML file
            try:
                with open(policy_path, 'r', encoding='utf-8') as f:
                    policy_data = yaml.safe_load(f)
                
                if not isinstance(policy_data, dict):
                    status = FeatureStatus(
                        name=feature_name,
                        available=False,
                        configured=False,
                        error="Policy file does not contain valid YAML dictionary",
                        details=details,
                        suggestion="Ensure policy file contains valid YAML configuration"
                    )
                    self._cache_result(feature_name, status)
                    return status
                
                # Basic validation - check for tools section
                tools_count = 0
                if "tools" in policy_data and isinstance(policy_data["tools"], dict):
                    tools_count = len(policy_data["tools"])
                
                details.update({
                    "file_size": policy_path.stat().st_size,
                    "tools_count": tools_count,
                    "has_tools_section": "tools" in policy_data
                })
                
                status = FeatureStatus(
                    name=feature_name,
                    available=True,
                    configured=True,
                    details=details
                )
                
            except yaml.YAMLError as e:
                status = FeatureStatus(
                    name=feature_name,
                    available=False,
                    configured=False,
                    error=f"Policy file contains invalid YAML: {str(e)}",
                    details=details,
                    suggestion="Fix YAML syntax errors in policy file"
                )
            
            except UnicodeDecodeError as e:
                status = FeatureStatus(
                    name=feature_name,
                    available=False,
                    configured=False,
                    error=f"Policy file encoding error: {str(e)}",
                    details=details,
                    suggestion="Ensure policy file is UTF-8 encoded"
                )
            
            self._cache_result(feature_name, status)
            return status
            
        except Exception as e:
            logger.warning(f"Unexpected error checking policy file: {e}")
            status = FeatureStatus(
                name=feature_name,
                available=False,
                configured=False,
                error=f"Unexpected error: {str(e)}",
                suggestion="Check policy file configuration"
            )
            self._cache_result(feature_name, status)
            return status
    
    def _is_cached(self, feature_name: str) -> bool:
        """
        Check if feature status is cached and still valid.
        
        Args:
            feature_name: Name of the feature to check
            
        Returns:
            True if cached result is still valid
        """
        if feature_name not in self._cache:
            return False
        
        import time
        cache_time = self._cache_time.get(feature_name, 0)
        return (time.time() - cache_time) < self._cache_ttl
    
    def _cache_result(self, feature_name: str, status: FeatureStatus) -> None:
        """
        Cache feature status result.
        
        Args:
            feature_name: Name of the feature
            status: Feature status to cache
        """
        import time
        self._cache[feature_name] = status
        self._cache_time[feature_name] = time.time()
    
    def clear_cache(self) -> None:
        """Clear all cached feature status results."""
        self._cache.clear()
        self._cache_time.clear()


# Global feature detector instance
_feature_detector: Optional[FeatureDetector] = None


def get_feature_detector() -> FeatureDetector:
    """
    Get the global feature detector instance.
    
    Returns:
        Global FeatureDetector instance
    """
    global _feature_detector
    if _feature_detector is None:
        _feature_detector = FeatureDetector()
    return _feature_detector


def get_degraded_tool_response(tool_name: str, feature_name: str, feature_status: FeatureStatus) -> Dict[str, Any]:
    """
    Generate consistent degraded response for unavailable tools.
    
    Creates a standardized MCP response envelope for tools that
    cannot function due to missing or misconfigured features.
    
    Args:
        tool_name: Name of the tool that cannot function
        feature_name: Name of the feature that is unavailable
        feature_status: Status information for the unavailable feature
        
    Returns:
        MCP response dictionary with structured error information
    """
    return {
        "ok": False,
        "summary": f"{tool_name} unavailable - {feature_status.error or 'feature not available'}",
        "error": f"Feature '{feature_name}' not available: {feature_status.error}",
        "data": {
            "tool": tool_name,
            "feature": feature_name,
            "feature_available": feature_status.available,
            "feature_configured": feature_status.configured,
            "suggestion": feature_status.suggestion or f"Enable {feature_name} to use {tool_name}",
            "details": feature_status.details
        },
        "metrics": {"elapsed_ms": 0, "exit_code": 1}
    }


def get_feature_suggestion(tool_name: str) -> str:
    """
    Provide helpful suggestions for enabling features required by tools.
    
    Args:
        tool_name: Name of the tool needing feature enablement
        
    Returns:
        Helpful suggestion string for enabling the required feature
    """
    suggestions = {
        "docker_ps": "Mount /var/run/docker.sock and add docker group to enable Docker operations",
        "blog_publish_static": "Mount blog directories with proper permissions",
        "blog_stage_markdown": "Ensure blog staging directory is accessible",
        "gotify_ping": "Set GOTIFY_URL and GOTIFY_TOKEN environment variables"
    }
    return suggestions.get(tool_name, "Check container configuration and feature requirements")