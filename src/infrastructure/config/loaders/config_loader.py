"""
Configuration Loader

Responsible for loading and parsing the evaluation framework's configuration files.
"""

from pathlib import Path
from typing import Any

from src.domain.testing.value_objects.execution_config import (
    AdaptiveIterationConfig,
    AdvancedConfig,
    GenerationConfig,
    GlobalConfig,
    Phase2ExecutionConfig,
    TwoPhaseExecutionConfig,
)
from src.shared.exceptions import ConfigurationError
from src.infrastructure.config.loaders.file_loader import FileConfigLoader


class ConfigLoader:
    """Configuration Loader

    Loads evaluation framework configuration from YAML files.
    """

    DEFAULT_CONFIG_PATH = Path("evaluation/config/two_phase_config.yaml")

    @classmethod
    def load(
        cls,
        config_path: str | Path | None = None,
    ) -> TwoPhaseExecutionConfig:
        """Load evaluation configuration.

        Args:
            config_path: Configuration file path (uses default path if None)

        Returns:
            Execution configuration

        Raises:
            ConfigurationError: Configuration file does not exist or has invalid format
        """
        if config_path is None:
            config_path = cls.DEFAULT_CONFIG_PATH

        # Use file loader to load YAML
        try:
            data = FileConfigLoader.load_yaml(config_path)
        except Exception as e:
            raise ConfigurationError(f"Failed to load configuration file: {e}") from e

        # Parse configuration (pass config_path for resolving relative paths)
        try:
            return cls._parse_config(data, config_path)
        except ValueError as e:
            raise ConfigurationError(f"Failed to parse configuration: {e}") from e

    @classmethod
    def _parse_config(
        cls,
        data: dict[str, Any],
        config_file_path: str | Path | None = None,
    ) -> TwoPhaseExecutionConfig:
        """Parse configuration data.

        Args:
            data: Configuration data dictionary
            config_file_path: Main configuration file path (for resolving relative paths)

        Returns:
            Execution configuration

        Raises:
            ValueError: Invalid configuration format
        """
        # Parse each configuration section
        generation_data = data.get("generation", {})
        execution_data = data.get("execution", {})
        global_data = data.get("global", {})
        advanced_data = data.get("advanced")
        adaptive_iteration_data = data.get("adaptive_iteration")
        dataset_data = data.get("dataset")

        # Check if config_file reference is used
        if "config_file" in generation_data:
            # Before loading sub-config, save override fields from main config
            # These fields allow users to fine-tune test scope in main config
            override_fields = ["attack_types", "injection_layers", "severities", "skill_names"]
            saved_overrides = {
                field: generation_data[field]
                for field in override_fields
                if field in generation_data
            }

            # Load generation config from sub-config file
            config_file = generation_data["config_file"]
            generation_data = cls._load_generation_config(
                config_file,
                config_file_path,
            )

            # Merge saved override fields back into generation_data
            # Main config values take priority over sub-config
            generation_data.update(saved_overrides)

        # If main config has dataset config, merge into generation_data
        # Prefer main config's dataset (this is usually what users want to override)
        if dataset_data is not None:
            # Ensure dataset_data is dict type (keep as-is if already DatasetConfig object)
            if isinstance(dataset_data, dict):
                # Pre-convert to DatasetConfig object to ensure correct subsequent processing
                from src.domain.testing.value_objects.execution_config import DatasetConfig
                generation_data["dataset"] = DatasetConfig.from_dict(dataset_data)
            else:
                generation_data["dataset"] = dataset_data

        # Validate generation config (ensure required fields are present)
        # If sub-config file was loaded, it should contain method field
        if "config_file" in data.get("generation", {}):
            # Sub-config file must contain method field
            if "method" not in generation_data:
                original_config_file = data["generation"]["config_file"]
                raise ConfigurationError(
                    f"Sub-config file format error: Missing 'method' field. "
                    f"Please check if {original_config_file} is a valid generation config file."
                )

        # Create configuration objects
        # Note: GenerationConfig.from_dict handles dataset conversion
        generation = GenerationConfig.from_dict(generation_data)
        execution = Phase2ExecutionConfig.from_dict(execution_data)
        global_config = GlobalConfig.from_dict(global_data)
        advanced = AdvancedConfig.from_dict(advanced_data if advanced_data else {})
        adaptive_iteration = AdaptiveIterationConfig.from_dict(adaptive_iteration_data if adaptive_iteration_data else {})

        # Combine complete configuration
        return TwoPhaseExecutionConfig(
            generation=generation,
            execution=execution,
            global_config=global_config,
            advanced=advanced,
            adaptive_iteration=adaptive_iteration,
        )

    @classmethod
    def _load_generation_config(
        cls,
        config_file: str | Path,
        main_config_path: str | Path | None = None,
    ) -> dict[str, Any]:
        """Load generation configuration file.

        Args:
            config_file: Configuration file path
                - Absolute path: use directly
                - Relative path: relative to main config file directory or its parent
            main_config_path: Main configuration file path (for resolving relative paths)

        Returns:
            Configuration data dictionary

        Raises:
            ConfigurationError: Configuration file does not exist or has invalid format
        """
        config_path = Path(config_file)

        if not config_path.is_absolute():
            # If main config path is provided, try multiple possible paths
            if main_config_path is not None:
                main_config_file = Path(main_config_path)
                main_config_dir = main_config_file.parent

                # Try multiple paths (in priority order):
                possible_paths = [
                    # 1. Relative to main config file directory
                    main_config_dir / config_file,
                    # 2. Relative to parent of main config file (evaluation directory)
                    main_config_dir.parent / config_file,
                    # 3. Relative to current working directory
                    Path.cwd() / config_file,
                ]

                for possible_path in possible_paths:
                    if possible_path.exists():
                        config_path = possible_path
                        break
                else:
                    # All paths don't exist, use last one (for error reporting)
                    config_path = possible_paths[-1]
            else:
                # No main config path, try current working directory first
                if not config_path.exists():
                    # Then try relative to evaluation/config directory
                    if (Path("evaluation/config") / config_file).exists():
                        config_path = Path("evaluation/config") / config_file
                    # Finally try as config/ subdirectory
                    elif (Path("config") / config_file.name).exists():
                        config_path = Path("config") / config_file.name
                    else:
                        # Use original path, let subsequent code report error
                        config_path = Path.cwd() / config_file

        if not config_path.exists():
            raise ConfigurationError(f"Generation config file does not exist: {config_path}")

        try:
            return FileConfigLoader.load_yaml(config_path)
        except Exception as e:
            raise ConfigurationError(f"Failed to load generation config file: {e}") from e

    @classmethod
    def load_with_overrides(
        cls,
        config_path: str | Path | None = None,
        **overrides,
    ) -> TwoPhaseExecutionConfig:
        """Load configuration and apply overrides.

        Args:
            config_path: Configuration file path
            **overrides: Configuration items to override (use dot notation for nested paths)
                e.g., generation.llm_provider="anthropic"

        Returns:
            Execution configuration
        """
        # Load base configuration
        if config_path is None:
            config_path = cls.DEFAULT_CONFIG_PATH

        try:
            data = FileConfigLoader.load_yaml(config_path)
        except Exception as e:
            raise ConfigurationError(f"Failed to load configuration file: {e}") from e

        # Apply overrides
        for key_path, value in overrides.items():
            cls._apply_override(data, key_path, value)

        # Parse configuration
        try:
            return cls._parse_config(data)
        except ValueError as e:
            raise ConfigurationError(f"Failed to parse configuration: {e}") from e

    @classmethod
    def _apply_override(cls, data: dict[str, Any], key_path: str, value: Any) -> None:
        """Apply configuration override.

        Args:
            data: Configuration data dictionary
            key_path: Configuration path (dot-separated)
            value: Override value
        """
        parts = key_path.split(".")
        current = data

        for part in parts[:-1]:
            if part not in current:
                current[part] = {}
            current = current[part]

        current[parts[-1]] = value

    @classmethod
    def save_default_config(cls, output_path: str | Path) -> None:
        """Save default configuration to file.

        Args:
            output_path: Output file path
        """
        default_config = cls._get_default_config_dict()
        FileConfigLoader.save_yaml(default_config, output_path)

    @classmethod
    def _get_default_config_dict(cls) -> dict[str, Any]:
        """Get default configuration dictionary.

        Returns:
            Default configuration dictionary
        """
        return {
            "generation": {
                "strategy": "template_injection",
                "template_base_dir": "data/skills_from_skill0",
                "template_output_dir": "generated_tests",
                "llm_provider": "openai",
                "llm_model": "gpt-4",
                "llm_max_concurrency": 4,
                "attack_types": [
                    "prompt_injection",
                    "jailbreak",
                    "data_exfiltration",
                ],
                "injection_layers": ["description", "instruction", "resource"],
                "severities": ["high", "critical"],
                "skill_names": [],
                "max_tests": None,
                "save_metadata": True,
            },
            "execution": {
                "max_concurrency": 4,
                "test_timeout": 120,
                "command_timeout": 300,
                "retry_failed": True,
                "max_retries": 2,
                "enable_monitoring": {
                    "network": True,
                    "process": False,
                    "container": False,
                },
                "output_dir": "experiment_results",
                "save_detailed_logs": True,
                "agent_type": "claude-code",
            },
            "global": {
                "verbose": False,
                "log_level": "INFO",
                "timestamp_format": "%Y-%m-%d %H:%M:%S",
            },
            "advanced": {
                "enable_cache": True,
                "cache_dir": ".cache/two_phase",
                "batch_size": 10,
                "prefetch_tests": True,
                "max_memory_mb": 4096,
                "max_execution_time_minutes": 60,
            },
        }

    @classmethod
    def validate_config_file(cls, config_path: str | Path) -> list[str]:
        """Validate configuration file.

        Args:
            config_path: Configuration file path

        Returns:
            List of errors (empty list means valid)
        """
        errors = []

        # Check file existence
        config_path = Path(config_path)
        if not config_path.exists():
            errors.append(f"Configuration file does not exist: {config_path}")
            return errors

        # Try loading configuration
        try:
            config = cls.load(config_path)
            validation_errors = config.validate()
            errors.extend(validation_errors)
        except ConfigurationError as e:
            errors.append(str(e))
        except Exception as e:
            errors.append(f"Unknown error: {e}")

        return errors

    @classmethod
    def create_example_config(cls, output_path: str | Path) -> None:
        """Create example configuration file.

        Args:
            output_path: Output file path
        """
        example_config = {
            "generation": {
                "strategy": "llm_intelligent",
                "template_base_dir": "data/skills",
                "template_output_dir": "generated_tests",
                "llm_provider": "anthropic",
                "llm_model": "claude-3-opus-20240229",
                "llm_max_concurrency": 8,
                "attack_types": [
                    "information_disclosure",
                    "privilege_escalation",
                    "unauthorized_write",
                    "backdoor_injection",
                ],
                "injection_layers": ["description", "instruction"],
                "severities": ["critical"],
                "skill_names": ["file-browser", "web-search"],
                "max_tests": 100,
                "save_metadata": True,
            },
            "execution": {
                "max_concurrency": 8,
                "test_timeout": 180,
                "command_timeout": 600,
                "retry_failed": True,
                "max_retries": 3,
                "enable_monitoring": {
                    "network": True,
                    "process": True,
                    "container": False,
                },
                "output_dir": "experiment_results/example_run",
                "save_detailed_logs": True,
                "agent_type": "claude-code",
            },
            "global": {
                "verbose": True,
                "log_level": "DEBUG",
                "timestamp_format": "%Y-%m-%d %H:%M:%S",
            },
            "advanced": {
                "enable_cache": True,
                "cache_dir": ".cache/example",
                "batch_size": 20,
                "prefetch_tests": True,
                "max_memory_mb": 8192,
                "max_execution_time_minutes": 120,
            },
        }

        FileConfigLoader.save_yaml(example_config, output_path)
