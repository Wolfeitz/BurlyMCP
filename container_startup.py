#!/usr/bin/env python3
"""
Container Startup Script

This script handles container initialization, security validation,
and startup of the HTTP bridge service.
"""

import os
import sys
import time
import signal
import subprocess
import logging
from pathlib import Path

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Global process handle for graceful shutdown
http_bridge_process = None


def signal_handler(signum, frame):
    """Handle shutdown signals gracefully."""
    logger.info(f"Received signal {signum}, initiating graceful shutdown...")
    
    global http_bridge_process
    if http_bridge_process:
        logger.info("Terminating HTTP bridge process...")
        http_bridge_process.terminate()
        
        # Wait up to 8 seconds for graceful shutdown
        try:
            http_bridge_process.wait(timeout=8)
            logger.info("HTTP bridge shut down gracefully")
        except subprocess.TimeoutExpired:
            logger.warning("HTTP bridge did not shut down gracefully, sending SIGKILL")
            http_bridge_process.kill()
            try:
                http_bridge_process.wait(timeout=2)
                logger.info("HTTP bridge terminated with SIGKILL")
            except subprocess.TimeoutExpired:
                logger.error("HTTP bridge did not respond to SIGKILL")
    
    logger.info("Container shutdown complete")
    sys.exit(0)


def run_security_validation():
    """
    Run container security validation.
    
    Returns:
        True if validation passes, False otherwise
    """
    logger.info("Running container security validation...")
    
    try:
        # Run security validation script
        result = subprocess.run([
            sys.executable, "/app/security_validation.py"
        ], capture_output=True, text=True, timeout=30)
        
        # Log validation output
        if result.stdout:
            for line in result.stdout.strip().split('\n'):
                logger.info(f"Security: {line}")
        
        if result.stderr:
            for line in result.stderr.strip().split('\n'):
                logger.error(f"Security: {line}")
        
        if result.returncode != 0:
            logger.error("Security validation failed")
            return False
        
        logger.info("Security validation passed")
        return True
        
    except subprocess.TimeoutExpired:
        logger.error("Security validation timed out")
        return False
    except Exception as e:
        logger.error(f"Security validation error: {e}")
        return False


def log_startup_summary():
    """Log structured startup summary for downstream logging systems."""
    try:
        # Load configuration for summary
        config = {
            "server_name": os.environ.get("SERVER_NAME", "burlymcp"),
            "server_version": os.environ.get("SERVER_VERSION", "1.0.0"),
            "policy_file": os.environ.get("POLICY_FILE", "/app/BurlyMCP/config/policy/tools.yaml"),
            "audit_enabled": os.environ.get("AUDIT_ENABLED", "true").lower() in ["true", "1", "yes"],
            "notifications_enabled": bool(os.environ.get("GOTIFY_URL") and os.environ.get("GOTIFY_TOKEN")),
            "docker_socket": os.environ.get("DOCKER_SOCKET", "/var/run/docker.sock"),
            "blog_stage_root": os.environ.get("BLOG_STAGE_ROOT", "/app/data/blog/stage"),
            "blog_publish_root": os.environ.get("BLOG_PUBLISH_ROOT", "/app/data/blog/publish"),
            "audit_log_path": os.environ.get("AUDIT_LOG_PATH", "/var/log/agentops/audit.jsonl"),
            "strict_security_mode": os.environ.get("STRICT_SECURITY_MODE", "true").lower() in ["true", "1", "yes"],
            "rate_limit_disabled": os.environ.get("RATE_LIMIT_DISABLED", "false").lower() in ["true", "1", "yes"],
        }
        
        # Check Docker socket availability
        docker_available = Path(config["docker_socket"]).exists()
        
        # Count tools (simplified check)
        tools_count = "unknown"
        try:
            policy_file = Path(config["policy_file"])
            if policy_file.exists():
                # Simple heuristic - count tool definitions in policy file
                content = policy_file.read_text()
                tools_count = content.count("name:") if "name:" in content else "unknown"
        except Exception:
            pass
        
        # Log structured startup summary
        logger.info("=== BurlyMCP Container Startup Summary ===")
        logger.info(f"Server: {config['server_name']} v{config['server_version']}")
        logger.info(f"Policy file: {config['policy_file']}")
        logger.info(f"Tools registered: {tools_count}")
        logger.info(f"Audit logging: {'enabled' if config['audit_enabled'] else 'disabled'}")
        logger.info(f"Notifications: {'enabled' if config['notifications_enabled'] else 'disabled'}")
        logger.info(f"Docker operations: {'enabled' if docker_available else 'disabled'}")
        logger.info(f"Security mode: {'strict' if config['strict_security_mode'] else 'permissive'}")
        logger.info(f"Rate limiting: {'disabled' if config['rate_limit_disabled'] else 'enabled'}")
        logger.info(f"Blog staging: {config['blog_stage_root']}")
        logger.info(f"Blog publish: {config['blog_publish_root']}")
        logger.info(f"Audit logs: {config['audit_log_path']}")
        logger.info("=== Startup Summary Complete ===")
        
    except Exception as e:
        logger.error(f"Failed to generate startup summary: {e}")


def start_http_bridge():
    """
    Start the HTTP bridge service.
    
    Returns:
        subprocess.Popen object for the HTTP bridge process
    """
    logger.info("Starting BurlyMCP HTTP Bridge...")
    
    # Get configuration
    host = os.environ.get("HOST", "0.0.0.0")
    port = os.environ.get("PORT", "9400")
    log_level = os.environ.get("LOG_LEVEL", "info").lower()
    
    # Start uvicorn HTTP bridge
    cmd = [
        "uvicorn", "http_bridge:app",
        "--host", host,
        "--port", port,
        "--log-level", log_level,
        "--access-log"
    ]
    
    logger.info(f"Starting HTTP bridge: {' '.join(cmd)}")
    
    try:
        process = subprocess.Popen(
            cmd,
            cwd="/app",
            stdout=sys.stdout,
            stderr=sys.stderr,
            preexec_fn=os.setsid  # Create new process group for signal handling
        )
        
        logger.info(f"HTTP bridge started with PID {process.pid}")
        
        # Wait a moment for the HTTP bridge to start up
        time.sleep(2)
        
        # Verify the process is still running
        if process.poll() is not None:
            raise RuntimeError(f"HTTP bridge process exited immediately with code {process.returncode}")
        
        return process
        
    except Exception as e:
        logger.error(f"Failed to start HTTP bridge: {e}")
        raise


def main():
    """Main container startup entry point."""
    global http_bridge_process
    
    # Set up signal handlers for graceful shutdown
    signal.signal(signal.SIGTERM, signal_handler)
    signal.signal(signal.SIGINT, signal_handler)
    
    logger.info("=== BurlyMCP Container Starting ===")
    
    # Set startup time for security validation
    os.environ["STARTUP_TIME"] = str(int(time.time()))
    
    try:
        # Step 1: Run security validation
        if not run_security_validation():
            logger.error("Container startup aborted due to security validation failure")
            sys.exit(1)
        
        # Step 2: Log startup summary
        log_startup_summary()
        
        # Step 3: Start HTTP bridge
        http_bridge_process = start_http_bridge()
        
        logger.info("Container startup complete - HTTP bridge running")
        
        # Step 4: Wait for HTTP bridge process
        try:
            http_bridge_process.wait()
        except KeyboardInterrupt:
            logger.info("Received keyboard interrupt")
        
        logger.info("HTTP bridge process terminated")
        
    except Exception as e:
        logger.error(f"Container startup failed: {e}")
        sys.exit(1)
    
    finally:
        # Ensure cleanup
        if http_bridge_process and http_bridge_process.poll() is None:
            logger.info("Cleaning up HTTP bridge process...")
            http_bridge_process.terminate()
            try:
                http_bridge_process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                http_bridge_process.kill()


if __name__ == "__main__":
    main()