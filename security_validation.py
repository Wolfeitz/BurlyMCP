#!/usr/bin/env python3
"""
Container Security Validation Script

This script performs security validation checks on container startup
to ensure the container is running with appropriate security posture.
"""

import os
import pwd
import grp
import stat
import sys
import logging
from pathlib import Path
from typing import List, Dict, Any

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)


class SecurityValidationError(Exception):
    """Raised when security validation fails."""
    pass


class ContainerSecurityValidator:
    """Validates container security configuration on startup."""
    
    def __init__(self):
        self.warnings: List[str] = []
        self.errors: List[str] = []
    
    def validate_user_privileges(self) -> bool:
        """
        Validate that container is running as non-root user.
        
        Returns:
            True if running as non-root, False otherwise
        """
        try:
            uid = os.getuid()
            gid = os.getgid()
            user = pwd.getpwuid(uid)
            group = grp.getgrgid(gid)
            
            logger.info(f"Running as user: {user.pw_name} (UID: {uid})")
            logger.info(f"Running as group: {group.gr_name} (GID: {gid})")
            
            if uid == 0:
                self.errors.append("Container is running as root user (UID 0)")
                return False
            
            if user.pw_name != "mcp":
                self.warnings.append(f"Expected to run as 'mcp' user, but running as '{user.pw_name}'")
            
            return True
            
        except Exception as e:
            self.errors.append(f"Failed to validate user privileges: {e}")
            return False
    
    def validate_file_permissions(self) -> bool:
        """
        Validate file and directory permissions for security.
        
        Returns:
            True if permissions are secure, False otherwise
        """
        try:
            # Check critical directories
            critical_paths = [
                ("/app", 0o755, "Application directory"),
                ("/var/log/agentops", 0o750, "Audit log directory"),
                ("/app/data/blog/stage", 0o755, "Blog staging directory"),
                ("/app/data/blog/publish", 0o755, "Blog publish directory"),
            ]
            
            for path_str, expected_mode, description in critical_paths:
                path = Path(path_str)
                if not path.exists():
                    self.warnings.append(f"{description} does not exist: {path_str}")
                    continue
                
                actual_mode = stat.S_IMODE(path.stat().st_mode)
                if actual_mode != expected_mode:
                    self.warnings.append(
                        f"{description} has unexpected permissions: "
                        f"got {oct(actual_mode)}, expected {oct(expected_mode)}"
                    )
            
            # Check policy file accessibility
            policy_file = Path(os.environ.get("POLICY_FILE", "/config/policy/tools.yaml"))
            if not policy_file.exists():
                self.errors.append(f"Policy file not found: {policy_file}")
                return False
            
            if not os.access(policy_file, os.R_OK):
                self.errors.append(f"Policy file not readable: {policy_file}")
                return False
            
            logger.info(f"Policy file accessible: {policy_file}")
            
            return True
            
        except Exception as e:
            self.errors.append(f"Failed to validate file permissions: {e}")
            return False
    
    def validate_docker_socket_access(self) -> Dict[str, Any]:
        """
        Validate Docker socket access configuration.
        
        Returns:
            Dictionary with Docker access status and recommendations
        """
        docker_socket = Path("/var/run/docker.sock")
        docker_status = {
            "socket_exists": docker_socket.exists(),
            "socket_accessible": False,
            "user_in_docker_group": False,
            "recommendations": []
        }
        
        if docker_socket.exists():
            # Check if socket is accessible
            docker_status["socket_accessible"] = os.access(docker_socket, os.R_OK | os.W_OK)
            
            # Check if user is in docker group
            try:
                user_groups = [grp.getgrgid(gid).gr_name for gid in os.getgroups()]
                docker_status["user_in_docker_group"] = "docker" in user_groups
                logger.info(f"User groups: {user_groups}")
            except Exception:
                pass
            
            if not docker_status["socket_accessible"]:
                docker_status["recommendations"].append(
                    "To enable Docker operations: mount /var/run/docker.sock and add --group-add <docker_gid>"
                )
            else:
                logger.info("Docker socket is accessible - Docker operations enabled")
        else:
            docker_status["recommendations"].append(
                "Docker socket not mounted - Docker operations will be unavailable"
            )
            logger.info("Docker socket not found - running in minimal mode")
        
        return docker_status
    
    def validate_environment_security(self) -> bool:
        """
        Validate environment variables for security issues.
        
        Returns:
            True if environment is secure, False otherwise
        """
        try:
            # Check for sensitive environment variables that shouldn't be exposed
            sensitive_vars = ["GOTIFY_TOKEN", "SECRET_KEY", "API_KEY", "PASSWORD"]
            exposed_secrets = []
            
            for var in sensitive_vars:
                if var in os.environ:
                    value = os.environ[var]
                    if value and len(value) > 0:
                        # Don't log the actual value
                        logger.info(f"Sensitive environment variable configured: {var}")
                    else:
                        exposed_secrets.append(var)
            
            # Check for required security settings
            strict_security = os.environ.get("STRICT_SECURITY_MODE", "true").lower()
            if strict_security not in ["true", "1", "yes"]:
                self.warnings.append("STRICT_SECURITY_MODE is disabled")
            else:
                logger.info("Strict security mode enabled")
            
            # Check rate limiting configuration
            rate_limit_disabled = os.environ.get("RATE_LIMIT_DISABLED", "false").lower()
            if rate_limit_disabled in ["true", "1", "yes"]:
                self.warnings.append("Rate limiting is disabled - only use in lab environments")
            else:
                logger.info("Rate limiting enabled")
            
            return True
            
        except Exception as e:
            self.errors.append(f"Failed to validate environment security: {e}")
            return False
    
    def validate_network_security(self) -> bool:
        """
        Validate network security configuration.
        
        Returns:
            True if network configuration is secure, False otherwise
        """
        try:
            # Check listening configuration
            host = os.environ.get("HOST", "0.0.0.0")
            port = os.environ.get("PORT", "9400")
            
            logger.info(f"HTTP server will listen on {host}:{port}")
            
            if host == "0.0.0.0":
                logger.info("Listening on all interfaces - ensure proper firewall configuration")
            elif host == "127.0.0.1":
                self.warnings.append("Listening only on localhost - may not be accessible from outside container")
            
            return True
            
        except Exception as e:
            self.errors.append(f"Failed to validate network security: {e}")
            return False
    
    def generate_security_report(self) -> Dict[str, Any]:
        """
        Generate comprehensive security validation report.
        
        Returns:
            Dictionary containing security status and recommendations
        """
        report = {
            "timestamp": os.environ.get("STARTUP_TIME", "unknown"),
            "user_validation": self.validate_user_privileges(),
            "file_permissions": self.validate_file_permissions(),
            "docker_access": self.validate_docker_socket_access(),
            "environment_security": self.validate_environment_security(),
            "network_security": self.validate_network_security(),
            "warnings": self.warnings,
            "errors": self.errors,
            "overall_status": "secure" if not self.errors else "insecure"
        }
        
        return report
    
    def log_security_summary(self, report: Dict[str, Any]) -> None:
        """
        Log security validation summary.
        
        Args:
            report: Security validation report
        """
        logger.info("=== Container Security Validation Summary ===")
        logger.info(f"Overall Status: {report['overall_status'].upper()}")
        
        if report['errors']:
            logger.error("Security Errors:")
            for error in report['errors']:
                logger.error(f"  - {error}")
        
        if report['warnings']:
            logger.warning("Security Warnings:")
            for warning in report['warnings']:
                logger.warning(f"  - {warning}")
        
        # Log Docker access status
        docker_status = report['docker_access']
        if docker_status['socket_accessible']:
            logger.info("Docker operations: ENABLED")
        else:
            logger.info("Docker operations: DISABLED (minimal mode)")
            for rec in docker_status['recommendations']:
                logger.info(f"  Recommendation: {rec}")
        
        logger.info("=== Security Validation Complete ===")


def main():
    """Main security validation entry point."""
    try:
        validator = ContainerSecurityValidator()
        report = validator.generate_security_report()
        validator.log_security_summary(report)
        
        # Exit with error code if security validation fails
        if report['errors']:
            logger.error("Security validation failed - container startup aborted")
            sys.exit(1)
        
        if report['warnings']:
            logger.warning("Security validation completed with warnings")
        else:
            logger.info("Security validation passed")
        
        return 0
        
    except Exception as e:
        logger.error(f"Security validation crashed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    sys.exit(main())