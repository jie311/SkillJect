"""
OpenAI Codex CLI Agent Configuration

Configures all required parameters and options for OpenAI Codex CLI.

Configuration Details:
- name: "codex-cli" - Unique agent identifier
- display_name: "OpenAI Codex CLI" - Human-readable name
- npm_package: "@openai/codex@latest" - NPM package name and version
- command: "codex exec" - Command (note: requires `exec` subcommand)
- env_prefix: "OPENAI" - Environment variable prefix
- env_vars: Environment variable name mapping
- install_command: Installation command
- use_otel_logging: False - Does not use OpenTelemetry logging (CLI agent)

Special Notes:
- Codex CLI command format is `codex exec <prompt>`, different from other CLI agents (requires `exec` subcommand)
- This requires special handling of command format in the configuration class

Backward Compatibility:
- Environment variables: OPENAI_API_KEY, OPENAI_BASE_URL, OPENAI_MODEL
- Consistent with Codex CLI examples

Integration with agent-security-eval:
- Will be registered by AgentRegistry
- Agent instances created through AgentFactory
- Used in MultiAgentSecurityTester
"""

import os
from typing import Dict

from src.domain.agent.interfaces.agent_interface import BaseAgentConfig
from src.infrastructure.logging.collectors.stderr_log_collector import StderrLogCollector


class CodexCliAgentConfig(BaseAgentConfig):
    """
    OpenAI Codex CLI Agent Configuration

    Defines all configuration for Codex CLI.
    Codex CLI uses `codex exec <prompt>` command format,
    which differs from other CLI agents (no `exec` required).
    """

    def __init__(self):
        """
        Initialize Codex CLI configuration

        Sets agent-specific default values and environment variable mappings.
        """
        # Common configuration (from BaseAgentConfig)
        self.name = "codex-cli"
        self.display_name = "OpenAI Codex CLI"
        self.npm_package = "@openai/codex@latest"

        # Command format: Codex CLI requires `exec` subcommand
        self.command = "codex exec"

        self.env_prefix = "OPENAI"

        # Environment variable mapping
        self.env_vars = {
            "API_KEY": "OPENAI_API_KEY",
            "BASE_URL": "OPENAI_BASE_URL",
            "MODEL": "OPENAI_MODEL",
        }

        # Installation command
        self.install_command = "npm install -g @openai/codex@latest"

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
            ValueError: If OPENAI_API_KEY is not set
        """
        env = {}

        # OPENAI_API_KEY is required
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ValueError(
                "OpenAI Codex CLI: Required environment variable "
                "'OPENAI_API_KEY' is not set. "
                "Please set it with: export OPENAI_API_KEY='sk-...'"
            )
        env["OPENAI_API_KEY"] = api_key

        # OPENAI_BASE_URL is optional (has default value)
        base_url = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")
        if base_url:
            env["OPENAI_BASE_URL"] = base_url

        # OPENAI_MODEL is optional (has default value)
        model = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
        if model:
            env["OPENAI_MODEL"] = model

        return env

    def _load_from_env(self) -> "CodexCliAgentConfig":
        """
        Load configuration from environment variables

        Supports overriding default configuration values via environment variables.
        """
        # Load optional working directory override
        if "CLAUDE_WORKDIR" in os.environ:
            self.default_workdir = os.environ["CLAUDE_WORKDIR"]

        return self

    def get_install_env(self) -> Dict[str, str]:
        """
        Get environment variables required for installation

        Returns:
            Mapping of environment variable names to values
        """
        return self.get_required_env_vars()

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
        return f"CodexCliAgentConfig(name='{self.name}', display_name='{self.display_name}')"
