"""
Google Gemini CLI Agent Configuration

Configures all required parameters and options for Google Gemini CLI.

Configuration Details:
- name: "gemini-cli" - Unique agent identifier
- display_name: "Google Gemini CLI" - Human-readable name
- npm_package: "@google/gemini-cli@latest" - NPM package name and version
- command: "gemini" - Base command
- env_prefix: "GEMINI" - Environment variable prefix
- env_vars: Environment variable name mapping
- install_command: Installation command
- use_otel_logging: False - Does not use OpenTelemetry logging (CLI agent)

Backward Compatibility:
- Environment variables: GEMINI_API_KEY, GEMINI_BASE_URL, GEMINI_MODEL
- Consistent with other examples (examples/gemini-cli)

Integration with agent-security-eval:
- Will be registered by AgentRegistry
- Agent instances created through AgentFactory
- Used in MultiAgentSecurityTester
"""

import os
from typing import Dict

from src.domain.agent.interfaces.agent_interface import BaseAgentConfig
from src.infrastructure.logging.collectors.stderr_log_collector import StderrLogCollector


class GeminiCliAgentConfig(BaseAgentConfig):
    """
    Google Gemini CLI Agent Configuration

    Defines all configuration parameters for Google Gemini CLI.
    Google Gemini CLI executes via shell commands, output to stdout/stderr.
    """

    def __init__(self):
        """
        Initialize Google Gemini CLI configuration

        Sets agent-specific default values and environment variable mappings.
        """
        # Common configuration (from BaseAgentConfig)
        self.name = "gemini-cli"
        self.display_name = "Google Gemini CLI"
        self.npm_package = "@google/gemini-cli@latest"
        self.command = "gemini"
        self.env_prefix = "GEMINI"

        # Environment variable mapping
        self.env_vars = {
            "API_KEY": "GEMINI_API_KEY",
            "BASE_URL": "GEMINI_BASE_URL",
            "MODEL": "GEMINI_MODEL",
        }

        # Installation command
        self.install_command = "npm install -g @google/gemini-cli@latest"

        # Log collector: Not using OTel, using StderrLogCollector
        self.log_collector = StderrLogCollector
        self.use_otel_logging = False

        # Installation timeout (default value)
        self.install_timeout = 300  # 5 minutes

        # Command execution timeout (default value)
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
            ValueError: If GEMINI_API_KEY is not set
        """
        env = {}

        # GEMINI_API_KEY is required
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            raise ValueError(
                "Google Gemini CLI: Required environment variable "
                "'GEMINI_API_KEY' is not set. "
                "Please set it with: export GEMINI_API_KEY='your-api-key'"
            )
        env["GEMINI_API_KEY"] = api_key

        # GEMINI_BASE_URL is optional (has default value)
        base_url = os.getenv("GEMINI_BASE_URL", "https://generativelanguage.googleapis.com/")
        if base_url:
            env["GEMINI_BASE_URL"] = base_url

        # GEMINI_MODEL is optional (has default value)
        model = os.getenv("GEMINI_MODEL", "gemini-2.5-flash-exp")
        if model:
            env["GEMINI_MODEL"] = model

        return env

    def _load_from_env(self) -> "GeminiCliAgentConfig":
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
        Get complete environment variables (including additional environment variables)

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
        return f"GeminiCliAgentConfig(name='{self.name}', display_name='{self.display_name}')"
