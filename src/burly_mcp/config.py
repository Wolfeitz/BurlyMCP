"""Configuration management for BurlyMCP."""

import os
from pathlib import Path
from typing import Any


class Config:
    """Configuration manager for BurlyMCP."""

    def __init__(self, config_dir: str | None = None):
        """Initialize configuration.
        
        Args:
            config_dir: Optional configuration directory path
        """
        self.config_dir = Path(config_dir) if config_dir else Path.home() / ".burly_mcp"
        self.policy_file = self.config_dir / "policy.json"

        # Default configuration values
        self._defaults = {
            "gotify_url": "",
            "gotify_token": "",
            "gotify_enabled": False,
            "blog_enabled": False,
            "blog_url": "",
            "blog_token": "",
            "security_enabled": True,
            "audit_enabled": True,
            "resource_limits_enabled": True,
            "max_memory_mb": 512,
            "max_cpu_percent": 80,
            "max_execution_time": 300,
        }

        # Load from environment
        self._load_from_environment()

    def _load_from_environment(self):
        """Load configuration from environment variables."""
        env_mapping = {
            "GOTIFY_URL": "gotify_url",
            "GOTIFY_TOKEN": "gotify_token",
            "GOTIFY_ENABLED": "gotify_enabled",
            "BLOG_ENABLED": "blog_enabled",
            "BLOG_URL": "blog_url",
            "BLOG_TOKEN": "blog_token",
            "SECURITY_ENABLED": "security_enabled",
            "AUDIT_ENABLED": "audit_enabled",
            "RESOURCE_LIMITS_ENABLED": "resource_limits_enabled",
            "MAX_MEMORY_MB": "max_memory_mb",
            "MAX_CPU_PERCENT": "max_cpu_percent",
            "MAX_EXECUTION_TIME": "max_execution_time",
        }

        for env_var, config_key in env_mapping.items():
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
                # Convert numeric strings
                elif config_key in ("max_memory_mb", "max_cpu_percent", "max_execution_time"):
                    try:
                        self._defaults[config_key] = int(value)
                    except ValueError:
                        raise ValueError(f"Invalid integer value for {env_var}: {value}")
                else:
                    # Handle empty strings
                    self._defaults[config_key] = value if value.strip() else ""

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

    def validate(self) -> bool:
        """Validate configuration."""
        # Check if config directory exists
        if not self.config_dir.exists():
            return False

        # Check if policy file exists when security is enabled
        if self.security_enabled and not self.policy_file.exists():
            return False

        # Check Gotify configuration when enabled
        if self.gotify_enabled and not self.gotify_token:
            return False

        return True

    def to_dict(self) -> dict[str, Any]:
        """Convert configuration to dictionary."""
        return self._defaults.copy()

    def __str__(self) -> str:
        """String representation of configuration."""
        return f"Config(config_dir={self.config_dir})"

    def __repr__(self) -> str:
        """Detailed string representation."""
        return f"Config(config_dir={self.config_dir}, policy_file={self.policy_file})"
