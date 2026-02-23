"""
iFlow CLI Agent Configuration

Configures all required parameters and options for iFlow CLI.

Configuration Details:
- name: "iflow-cli" - Unique agent identifier
- display_name: "iFlow CLI" - Human-readable name
- npm_package: "@iflow-ai/iflow-cli@latest" - NPM package name and version
- command: "iflow" - Base command
- env_prefix: "IFLOW" - Environment variable prefix
- env_vars: Environment variable name mapping
- install_command: Installation command
- use_otel_logging: False - Does not use OpenTelemetry logging (CLI agent)

Backward Compatibility:
- Environment variables: IFLOW_API_KEY, IFLOW_BASE_URL, IFLOW_MODEL_NAME
- Consistent with iflow-cli examples

Integration with agent-security-eval:
- Will be registered by AgentRegistry
- Agent instances created through AgentFactory
- Used in MultiAgentSecurityTester
"""

import os
from typing import Dict

from src.domain.agent.interfaces.agent_interface import BaseAgentConfig
from src.infrastructure.logging.collectors.stderr_log_collector import StderrLogCollector


class IfLowCliAgentConfig(BaseAgentConfig):
    """
    iFlow CLI Agent Configuration

    Defines all configuration parameters for iFlow CLI.
    iFlow CLI executes via shell commands, output to stdout/stderr.
    """

    def __init__(self):
        """
        Initialize iFlow CLI configuration

        Sets agent-specific default values and environment variable mappings.
        """
        # Common configuration (from BaseAgentConfig)
        self.name = "iflow-cli"
        self.display_name = "iFlow CLI"
        self.npm_package = "@iflow-ai/iflow-cli@latest"
        self.command = "iflow"
        self.env_prefix = "IFLOW"

        # Environment variable mapping (note: IFLOW uses MODEL_NAME, other agents use MODEL)
        self.env_vars = {
            "API_KEY": "IFLOW_API_KEY",
            "BASE_URL": "IFLOW_BASE_URL",
            "MODEL_NAME": "IFLOW_MODEL_NAME",
        }

        # Installation command
        self.install_command = "npm install -g @iflow-ai/iflow-cli@latest"

        # Log collector: Not using OTel, using StderrLogCollector
        self.log_collector = StderrLogCollector
        self.use_otel_logging = False

        # Installation timeout (default value, can be overridden)
        self.install_timeout = 300  # 5 minutes

        # Command execution timeout (default value, can be overridden)
        self.command_timeout = 300  # 5 minutes

        # Additional environment variables (optional)
        self.additional_env = {}

        # Additional commands after installation (optional)
        self.post_install_commands = []

        # Working directory (default value)
        self.default_workdir = "/home/claude_code/project"

    def get_required_env_vars(self) -> Dict[str, str]:
        """
        Get required environment variables

        Returns:
            Mapping of environment variable names to values

        Raises:
            ValueError: If IFLOW_API_KEY is not set
        """
        env = {}

        # IFLOW_API_KEY is required
        api_key = os.getenv("IFLOW_API_KEY")
        if not api_key:
            raise ValueError(
                "iFlow CLI: Required environment variable "
                "'IFLOW_API_KEY' is not set. "
                "Please set it with: export IFLOW_API_KEY=<your-api-key>"
            )
        env["IFLOW_API_KEY"] = api_key

        # IFLOW_BASE_URL is optional (has default value)
        base_url = os.getenv("IFLOW_BASE_URL", "https://apis.iflow.cn/v1")
        if base_url:
            env["IFLOW_BASE_URL"] = base_url

        # IFLOW_MODEL_NAME is optional (has default value)
        model_name = os.getenv("IFLOW_MODEL_NAME", "qwen3-coder-plus")
        if model_name:
            env["IFLOW_MODEL_NAME"] = model_name

        return env

    def _load_from_env(self) -> "IfLowCliAgentConfig":
        """
        Load configuration from environment variables

        Supports overriding default configuration values via environment variables.

        Returns:
            Loaded configuration object
        """
        # Load optional working directory override
        if "CLAUDE_WORKDIR" in os.environ:
            self.default_workdir = os.environ["CLAUDE_WORKDIR"]

        return self

    def get_full_env(self) -> Dict[str, str]:
        """
        Get complete environment variables (including configuration override values)

        Returns:
            Mapping of environment variable names to values
        """
        env = self.get_required_env_vars()

        # Add additional environment variables
        env.update(self.additional_env)

        return env

    def get_install_env(self) -> Dict[str, str]:
        """
        Get environment variables required for installation

        Returns:
            Mapping of environment variable names to values
        """
        return self.get_required_env_vars()

    def get_install_commands(self) -> list[str]:
        """
        Get list of installation commands

        Returns:
            List of commands
        """
        commands = [self.install_command]

        # Add additional commands after installation
        commands.extend(self.post_install_commands)

        return commands

    def __repr__(self) -> str:
        """
        Return string representation of configuration

        Used for debugging and logging.
        """
        return f"IfLowCliAgentConfig(name='{self.name}', display_name='{self.display_name}')"
