"""
Unified Configuration Manager

Integrates all configuration management logic, providing a unified configuration access interface.
Supports multi-source configuration: environment variables, configuration files, default values.
"""

import os
import threading
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any

from src.shared.exceptions import ConfigurationError


class ConfigSource(Enum):
    """Configuration source."""

    DEFAULT = "default"
    ENV = "environment"
    FILE = "file"
    CODE = "code"  # Set in code


@dataclass(frozen=True)
class ConfigValue:
    """Configuration value with source tracking."""

    value: Any
    source: ConfigSource
    path: str  # Configuration path, e.g., "sandbox.domain"


class ConfigManager:
    """Unified Configuration Manager

    Provides hierarchical configuration management:
    1. Environment variables (highest priority)
    2. Configuration files
    3. Default values

    Supports configuration change listening, validation, import/export.
    """

    # Singleton instance
    _instance: "ConfigManager | None" = None
    _lock = threading.Lock()

    def __new__(cls) -> "ConfigManager":
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if hasattr(self, "_initialized"):
            return

        self._initialized = True
        self._config: dict[str, Any] = {}
        self._config_sources: dict[str, ConfigSource] = {}
        self._change_listeners: list[callable] = []
        self._base_dir = Path(__file__).parent.parent.parent.parent.parent

        # Load default configuration
        self._load_defaults()

    def _load_defaults(self) -> None:
        """Load default configuration."""
        self._set_default("sandbox.domain", "localhost:8080")
        self._set_default("sandbox.api_key", None)
        self._set_default("sandbox.request_timeout", 120)
        self._set_default("sandbox.image", "claude_code:v4")
        self._set_default("sandbox.user_config", "claude_code")
        self._set_default("sandbox.bypass_mode", True)
        self._set_default("sandbox.default_workdir", "/home/claude_code/project")

        self._set_default("test.command_timeout", 300)
        self._set_default("test.max_concurrency", 4)
        self._set_default("test.retry_failed", True)
        self._set_default("test.max_retries", 2)
        self._set_default("test.max_tests", None)

        self._set_default("log.output_dir", "experiment_results")
        self._set_default("log.save_individual_logs", True)
        self._set_default("log.generate_html_report", False)
        self._set_default("log.generate_json_report", True)
        self._set_default("log.generate_statistics", True)
        self._set_default("log.desensitize_logs", True)
        self._set_default("log.show_sensitive_chars", 4)

        self._set_default("claude.auth_token", None)
        self._set_default("claude.base_url", None)
        self._set_default("claude.model", None)

        # Path configuration
        self._set_default("paths.base_dir", str(self._base_dir))
        self._set_default("paths.test_dir", str(self._base_dir / "generated_tests"))
        self._set_default("paths.output_dir", str(self._base_dir / "experiment_results"))
        self._set_default("paths.skills_dir", str(self._base_dir / "data" / "skills_from_skill0"))
        self._set_default(
            "paths.instructions_dir", str(self._base_dir / "data" / "skills_instructions")
        )

        # Experiment configuration
        self._set_default("experiment.name", "security_experiment")
        self._set_default("experiment.mode", "category")
        self._set_default("experiment.max_concurrency", 4)
        self._set_default("experiment.timeout_seconds", 120)

        # Load environment variables
        self._load_env_vars()

    def _set_default(self, key: str, value: Any) -> None:
        """Set default value."""
        self._config[key] = value
        self._config_sources[key] = ConfigSource.DEFAULT

    def _load_env_vars(self) -> None:
        """Load environment variables."""
        env_mappings = {
            "SANDBOX_DOMAIN": "sandbox.domain",
            "SANDBOX_API_KEY": "sandbox.api_key",
            "SANDBOX_IMAGE": "sandbox.image",
            "SANDBOX_USER": "sandbox.user_config",
            "BYPASS_MODE": "sandbox.bypass_mode",
            "MAX_CONCURRENCY": "test.max_concurrency",
            "COMMAND_TIMEOUT": "test.command_timeout",
            "MAX_TESTS": "test.max_tests",
            "OUTPUT_DIR": "log.output_dir",
            "ANTHROPIC_AUTH_TOKEN": "claude.auth_token",
            "ANTHROPIC_BASE_URL": "claude.base_url",
            "ANTHROPIC_MODEL": "claude.model",
            "SECURITY_TEST_DIR": "paths.test_dir",
            "EXPERIMENT_OUTPUT_DIR": "paths.output_dir",
            "SKILLS_FROM_SKILL0_DIR": "paths.skills_dir",
            "SKILLS_INSTRUCTIONS_DIR": "paths.instructions_dir",
        }

        for env_var, config_key in env_mappings.items():
            value = os.getenv(env_var)
            if value is not None:
                # Type conversion
                if value.lower() in ("true", "false"):
                    value = value.lower() == "true"
                elif value.isdigit():
                    value = int(value)

                self._config[config_key] = value
                self._config_sources[config_key] = ConfigSource.ENV

    def get(self, key: str, default: Any = None) -> Any:
        """Get configuration value.

        Args:
            key: Configuration key (supports dot-separated paths, e.g., "sandbox.domain")
            default: Default value

        Returns:
            Configuration value

        Examples:
            >>> cm = ConfigManager()
            >>> cm.get("sandbox.domain")
            'localhost:8080'
            >>> cm.get("sandbox.nonexistent", "default")
            'default'
        """
        # Configuration stored as flat keys (e.g., "sandbox.domain"), direct lookup
        return self._config.get(key, default)

    def set(self, key: str, value: Any, source: ConfigSource = ConfigSource.CODE) -> None:
        """Set configuration value.

        Args:
            key: Configuration key
            value: Configuration value
            source: Configuration source
        """
        old_value = self._config.get(key)
        self._config[key] = value
        self._config_sources[key] = source

        # Trigger change listeners
        if old_value != value:
            self._notify_listeners(key, old_value, value)

    def get_with_source(self, key: str) -> ConfigValue:
        """Get configuration value with source.

        Args:
            key: Configuration key

        Returns:
            ConfigValue object

        Raises:
            ConfigurationError: Configuration does not exist
        """
        if key not in self._config:
            raise ConfigurationError(f"Configuration does not exist: {key}")

        return ConfigValue(
            value=self._config[key],
            source=self._config_sources[key],
            path=key,
        )

    def get_source(self, key: str) -> ConfigSource:
        """Get configuration source.

        Args:
            key: Configuration key

        Returns:
            Configuration source

        Raises:
            ConfigurationError: Configuration does not exist
        """
        if key not in self._config_sources:
            raise ConfigurationError(f"Configuration does not exist: {key}")

        return self._config_sources[key]

    def load_from_file(self, path: str | Path) -> None:
        """Load configuration from file.

        Supports YAML and JSON formats.

        Args:
            path: Configuration file path

        Raises:
            ConfigurationError: File does not exist or has invalid format
        """
        path = Path(path)

        if not path.exists():
            raise ConfigurationError(f"Configuration file does not exist: {path}")

        try:
            if path.suffix in (".yaml", ".yml"):
                import yaml

                with open(path, encoding="utf-8") as f:
                    data = yaml.safe_load(f) or {}
            elif path.suffix == ".json":
                import json

                with open(path, encoding="utf-8") as f:
                    data = json.load(f)
            else:
                raise ConfigurationError(f"Unsupported configuration file format: {path.suffix}")

            # Flatten nested dictionary
            self._apply_dict_config(data, ConfigSource.FILE)

        except Exception as e:
            raise ConfigurationError(f"Failed to load configuration file: {e}") from e

    def _apply_dict_config(self, data: dict[str, Any], source: ConfigSource) -> None:
        """Apply dictionary configuration (recursive flattening)."""
        for key, value in data.items():
            full_key = key
            if isinstance(value, dict):
                # Recursively process nested dictionary
                for sub_key, sub_value in self._flatten_dict(value, key).items():
                    self._config[sub_key] = sub_value
                    self._config_sources[sub_key] = source
            else:
                self._config[full_key] = value
                self._config_sources[full_key] = source

    def _flatten_dict(self, data: dict[str, Any], prefix: str = "") -> dict[str, Any]:
        """Flatten nested dictionary."""
        result = {}
        for key, value in data.items():
            full_key = f"{prefix}.{key}" if prefix else key
            if isinstance(value, dict):
                result.update(self._flatten_dict(value, full_key))
            else:
                result[full_key] = value
        return result

    def save_to_file(self, path: str | Path, format: str = "yaml") -> None:
        """Save configuration to file.

        Args:
            path: Output path
            format: Format ("yaml" or "json")

        Raises:
            ConfigurationError: Save failed
        """
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)

        # Unflatten to nested structure
        nested = self._unflatten_dict(self._config)

        try:
            if format == "yaml":
                import yaml

                with open(path, "w", encoding="utf-8") as f:
                    yaml.dump(nested, f, allow_unicode=True, default_flow_style=False)
            elif format == "json":
                import json

                with open(path, "w", encoding="utf-8") as f:
                    json.dump(nested, f, indent=2, ensure_ascii=False)
            else:
                raise ConfigurationError(f"Unsupported format: {format}")
        except Exception as e:
            raise ConfigurationError(f"Failed to save configuration: {e}") from e

    def _unflatten_dict(self, data: dict[str, Any]) -> dict[str, Any]:
        """Unflatten dictionary (rebuild nested structure)."""
        result: dict[str, Any] = {}

        for key, value in data.items():
            if "." in key:
                parts = key.split(".")
                current = result
                for part in parts[:-1]:
                    if part not in current:
                        current[part] = {}
                    current = current[part]
                current[parts[-1]] = value
            else:
                result[key] = value

        return result

    def add_change_listener(self, listener: callable) -> None:
        """Add configuration change listener.

        Args:
            listener: Listener function with signature (key, old_value, new_value) -> None
        """
        self._change_listeners.append(listener)

    def remove_change_listener(self, listener: callable) -> None:
        """Remove configuration change listener."""
        if listener in self._change_listeners:
            self._change_listeners.remove(listener)

    def _notify_listeners(self, key: str, old_value: Any, new_value: Any) -> None:
        """Notify listeners."""
        for listener in self._change_listeners:
            try:
                listener(key, old_value, new_value)
            except Exception:
                pass  # Listener exception does not affect configuration management

    def validate(self) -> list[str]:
        """Validate configuration.

        Returns:
            List of errors (empty list means no errors)
        """
        errors = []

        # Validate numeric ranges
        if self.get("test.max_concurrency", 0) < 1:
            errors.append("test.max_concurrency must be greater than 0")

        if self.get("test.command_timeout", 0) < 1:
            errors.append("test.command_timeout must be greater than 0")

        if self.get("test.max_retries", 0) < 0:
            errors.append("test.max_retries cannot be negative")

        if self.get("experiment.timeout_seconds", 0) < 1:
            errors.append("experiment.timeout_seconds must be greater than 0")

        # Validate paths
        for path_key in ["paths.test_dir", "paths.output_dir", "paths.skills_dir"]:
            path_value = self.get(path_key)
            if path_value:
                path = Path(path_value)
                if not path.exists():
                    # Path doesn't exist but not necessarily an error (may need to be created)
                    pass

        return errors

    def reset(self) -> None:
        """Reset to default configuration."""
        self._config.clear()
        self._config_sources.clear()
        self._load_defaults()

    def to_dict(self) -> dict[str, Any]:
        """Export as dictionary (flattened)."""
        return self._config.copy()

    def to_nested_dict(self) -> dict[str, Any]:
        """Export as nested dictionary."""
        return self._unflatten_dict(self._config)

    # ========== Convenient access methods ==========

    @property
    def sandbox_domain(self) -> str:
        """Get Sandbox domain."""
        return self.get("sandbox.domain", "localhost:8080")

    @property
    def sandbox_api_key(self) -> str | None:
        """Get Sandbox API key."""
        return self.get("sandbox.api_key")

    @property
    def sandbox_image(self) -> str:
        """Get Sandbox image."""
        return self.get("sandbox.image", "claude_code:v4")

    @property
    def max_concurrency(self) -> int:
        """Get maximum concurrency."""
        return self.get("test.max_concurrency", 4)

    @property
    def command_timeout(self) -> int:
        """Get command timeout."""
        return self.get("test.command_timeout", 300)

    @property
    def output_dir(self) -> Path:
        """Get output directory."""
        return Path(self.get("paths.output_dir", "experiment_results"))

    @property
    def test_dir(self) -> Path:
        """Get test directory."""
        return Path(self.get("paths.test_dir", "generated_tests"))

    @property
    def skills_dir(self) -> Path:
        """Get skills directory."""
        return Path(self.get("paths.skills_dir", "data/skills_from_skill0"))

    # ========== Static factory methods ==========

    @staticmethod
    def get_instance() -> "ConfigManager":
        """Get singleton instance."""
        return ConfigManager()

    @staticmethod
    def reset_instance() -> None:
        """Reset singleton instance (mainly for testing)."""
        ConfigManager._instance = None


# Global configuration instance
_global_config: ConfigManager | None = None


def get_config() -> ConfigManager:
    """Get global configuration instance.

    Returns:
        ConfigManager singleton
    """
    global _global_config

    if _global_config is None:
        _global_config = ConfigManager()

    return _global_config


def reset_config() -> None:
    """Reset global configuration (mainly for testing)."""
    global _global_config
    _global_config = None
    ConfigManager.reset_instance()
