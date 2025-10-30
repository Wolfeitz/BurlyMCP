"""Configuration management for BurlyMCP."""

import os
from pathlib import Path
from typing import Any, Dict, List


class Config:
    """Configuration manager for BurlyMCP with container-internal defaults."""

    def __init__(self, config_dir: str | None = None):
        """Initialize configuration.
        
        Args:
            config_dir: Optional configuration directory path
        """
        # Use container-internal defaults instead of user home directory
        if config_dir:
            self.config_dir = Path(config_dir)
        else:
            # Container-internal default that works without external mounts
            self.config_dir = Path("/app/BurlyMCP/config")
        
        # Policy file with container-internal default
        self.policy_file = Path(
            os.environ.get("POLICY_FILE", "/config/policy/tools.yaml")
        )

        # Default configuration values with container-internal paths
        self._defaults = {
            # Core paths (container-internal defaults)
            "policy_file": str(self.policy_file),
            "audit_log_path": os.environ.get("AUDIT_LOG_PATH", "/var/log/agentops/audit.jsonl"),
            "log_dir": os.environ.get("LOG_DIR", "/var/log/agentops"),
            
            # Blog configuration with container-internal defaults
            "blog_stage_root": os.environ.get("BLOG_STAGE_ROOT", "/app/data/blog/stage"),
            "blog_publish_root": os.environ.get("BLOG_PUBLISH_ROOT", "/app/data/blog/publish"),
            "blog_enabled": os.environ.get("BLOG_ENABLED", "true").lower() in ["true", "1", "yes"],
            "blog_url": os.environ.get("BLOG_URL", ""),
            "blog_token": os.environ.get("BLOG_TOKEN", ""),
            
            # Docker configuration
            "docker_socket": os.environ.get("DOCKER_SOCKET", "/var/run/docker.sock"),
            "docker_timeout": int(os.environ.get("DOCKER_TIMEOUT", "30")),
            
            # Notification configuration
            "gotify_url": os.environ.get("GOTIFY_URL", ""),
            "gotify_token": os.environ.get("GOTIFY_TOKEN", ""),
            "gotify_enabled": bool(os.environ.get("GOTIFY_URL") and os.environ.get("GOTIFY_TOKEN")),
            "notifications_enabled": os.environ.get("NOTIFICATIONS_ENABLED", "true").lower() in ["true", "1", "yes"],
            
            # Security configuration
            "security_enabled": os.environ.get("SECURITY_ENABLED", "true").lower() in ["true", "1", "yes"],
            "strict_security_mode": os.environ.get("STRICT_SECURITY_MODE", "true").lower() in ["true", "1", "yes"],
            "audit_enabled": os.environ.get("AUDIT_ENABLED", "true").lower() in ["true", "1", "yes"],
            
            # Resource limits
            "resource_limits_enabled": os.environ.get("RESOURCE_LIMITS_ENABLED", "true").lower() in ["true", "1", "yes"],
            "max_memory_mb": int(os.environ.get("MAX_MEMORY_MB", "512")),
            "max_cpu_percent": int(os.environ.get("MAX_CPU_PERCENT", "80")),
            "max_execution_time": int(os.environ.get("MAX_EXECUTION_TIME", "300")),
            "max_output_size": int(os.environ.get("MAX_OUTPUT_SIZE", "1048576")),  # 1MB
            
            # Server configuration
            "server_name": os.environ.get("SERVER_NAME", "burlymcp"),
            "server_version": os.environ.get("SERVER_VERSION", "0.1.0"),
            "host": os.environ.get("HOST", "0.0.0.0"),  # nosec B104 - Intentional for container deployment
            "port": int(os.environ.get("PORT", "9400")),
            "log_level": os.environ.get("LOG_LEVEL", "INFO"),
        }

        # Load from environment (for any additional overrides)
        self._load_from_environment()

    def _load_from_environment(self):
        """Load additional configuration from environment variables."""
        # Additional environment variable mappings for legacy compatibility
        legacy_env_mapping = {
            "GOTIFY_ENABLED": "gotify_enabled",
            "BLOG_ENABLED": "blog_enabled", 
            "SECURITY_ENABLED": "security_enabled",
            "AUDIT_ENABLED": "audit_enabled",
            "RESOURCE_LIMITS_ENABLED": "resource_limits_enabled",
        }

        for env_var, config_key in legacy_env_mapping.items():
            value = os.getenv(env_var)
            if value is not None:
                # Convert boolean strings
                if config_key.endswith("_enabled"):
                    if value.lower() in ("true", "1", "yes", "on"):
                        self._defaults[config_key] = True
                    elif value.lower() in ("false", "0", "no", "off"):
                        self._defaults[config_key] = False
                    else:
                        raise ValueError(f"Invalid boolean value for {env_var}: {value}")
        
        # Ensure gotify_enabled is set correctly based on URL and token availability
        if self._defaults["gotify_url"] and self._defaults["gotify_token"]:
            self._defaults["gotify_enabled"] = True
        else:
            self._defaults["gotify_enabled"] = False

    def __getattr__(self, name: str) -> Any:
        """Get configuration value."""
        if name in self._defaults:
            return self._defaults[name]
        raise AttributeError(f"'{self.__class__.__name__}' object has no attribute '{name}'")

    def __setattr__(self, name: str, value: Any) -> None:
        """Prevent modification of configuration after initialization."""
        # Use object.__getattribute__ to avoid triggering __getattr__
        try:
            defaults = object.__getattribute__(self, '_defaults')
            if name in defaults:
                raise AttributeError(f"Configuration is immutable: cannot set '{name}'")
        except AttributeError:
            # _defaults not set yet, allow setting
            pass
        super().__setattr__(name, value)

    def get(self, key: str, default: Any = None) -> Any:
        """Get configuration value with optional default."""
        return self._defaults.get(key, default)

    def validate(self) -> List[str]:
        """Validate configuration and return list of errors.
        
        Returns:
            List of validation error messages. Empty list means valid.
        """
        errors = []
        
        # Check if policy file exists when security is enabled
        if self.security_enabled and not self.policy_file.exists():
            errors.append(f"Policy file not found: {self.policy_file}")

        # Check Gotify configuration when notifications are enabled
        if self.notifications_enabled:
            if not self.gotify_url:
                errors.append("GOTIFY_URL required when notifications enabled")
            if not self.gotify_token:
                errors.append("GOTIFY_TOKEN required when notifications enabled")

        # Check directory permissions for blog operations
        if self.blog_enabled:
            stage_path = Path(self.blog_stage_root)
            publish_path = Path(self.blog_publish_root)
            
            if not stage_path.exists():
                try:
                    stage_path.mkdir(parents=True, exist_ok=True)
                except OSError as e:
                    errors.append(f"Cannot create blog stage directory {stage_path}: {e}")
            
            if not publish_path.exists():
                try:
                    publish_path.mkdir(parents=True, exist_ok=True)
                except OSError as e:
                    errors.append(f"Cannot create blog publish directory {publish_path}: {e}")
            
            # Check write permissions for publish directory
            if publish_path.exists() and not os.access(publish_path, os.W_OK):
                errors.append(f"Blog publish directory not writable: {publish_path}")

        # Check audit log directory
        if self.audit_enabled:
            audit_dir = Path(self.audit_log_path).parent
            if not audit_dir.exists():
                try:
                    audit_dir.mkdir(parents=True, exist_ok=True)
                except OSError as e:
                    errors.append(f"Cannot create audit log directory {audit_dir}: {e}")
            elif not os.access(audit_dir, os.W_OK):
                errors.append(f"Audit log directory not writable: {audit_dir}")

        return errors

    def to_dict(self) -> dict[str, Any]:
        """Convert configuration to dictionary."""
        return self._defaults.copy()

    def __str__(self) -> str:
        """String representation of configuration."""
        return f"Config(config_dir={self.config_dir})"

    def __repr__(self) -> str:
        """Detailed string representation."""
        return f"Config(config_dir={self.config_dir}, policy_file={self.policy_file})"
    
    def get_startup_summary(self) -> Dict[str, Any]:
        """Get startup configuration summary for logging (without secrets).
        
        Returns:
            Dictionary with key configuration values for startup logging
        """
        return {
            "server_name": self.server_name,
            "server_version": self.server_version,
            "policy_file": str(self.policy_file),
            "audit_enabled": self.audit_enabled,
            "audit_log_path": self.audit_log_path if self.audit_enabled else "disabled",
            "notifications_enabled": self.notifications_enabled,
            "gotify_configured": bool(self.gotify_url and self.gotify_token),
            "blog_enabled": self.blog_enabled,
            "blog_stage_root": self.blog_stage_root if self.blog_enabled else "disabled",
            "blog_publish_root": self.blog_publish_root if self.blog_enabled else "disabled",
            "docker_socket": self.docker_socket,
            "strict_security_mode": self.strict_security_mode,
            "host": self.host,
            "port": self.port,
            "log_level": self.log_level,
        }
    
    @classmethod
    def load_runtime_config(cls) -> 'Config':
        """Load runtime configuration with container-internal defaults.
        
        This is the main entry point for loading configuration in the
        standalone container environment.
        
        Returns:
            Configured Config instance
        """
        return cls()
