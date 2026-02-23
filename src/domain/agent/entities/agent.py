"""
Agent Entity

Domain core entity representing an AI Agent
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from src.shared.types import AgentType


class AgentStatus(Enum):
    """Agent status"""

    UNINITIALIZED = "uninitialized"
    SETTING_UP = "setting_up"
    READY = "ready"
    RUNNING = "running"
    ERROR = "error"
    CLEANED_UP = "cleaned_up"


class ExecutionResult:
    """Execution result protocol

    Defines the standard structure for Agent execution results
    """

    exit_code: int
    stdout: list[str]
    stderr: list[str]
    error: dict[str, str] | None
    metadata: dict[str, Any]


@dataclass
class AgentConfig:
    """Agent configuration (value object)

    Contains all configuration required for creating and running an Agent
    """

    agent_type: AgentType
    name: str
    display_name: str

    # Installation configuration
    npm_package: str = ""
    install_command: str = ""
    install_timeout: int = 300

    # Execution configuration
    base_command: str = ""
    command_timeout: int = 300
    use_otel_logging: bool = False

    # Environment variables
    env_prefix: str = ""
    env_vars: dict[str, str] = field(default_factory=dict)
    additional_env: dict[str, str] = field(default_factory=dict)

    # Post-install commands
    post_install_commands: list[str] = field(default_factory=list)

    def get_env(self, env_dict: dict[str, str] | None = None) -> dict[str, str]:
        """Get complete environment variable configuration

        Args:
            env_dict: External environment variable dictionary

        Returns:
            Merged environment variable dictionary
        """
        import os

        env = {}

        # Get from system environment variables
        if env_dict:
            env.update(env_dict)
        else:
            # Get from os.environ
            for var_name, env_name in self.env_vars.items():
                value = os.getenv(f"{self.env_prefix}_{env_name}")
                if value:
                    env[var_name] = value

        # Add additional environment variables
        env.update(self.additional_env)

        return env

    def validate(self) -> list[str]:
        """Validate configuration

        Returns:
            Error list (empty list indicates valid)
        """
        errors = []

        if not self.name:
            errors.append("name cannot be empty")

        if self.install_timeout < 0:
            errors.append("install_timeout cannot be negative")

        if self.command_timeout < 0:
            errors.append("command_timeout cannot be negative")

        return errors


@dataclass
class AgentExecutionContext:
    """Agent execution context

    Contains context information during execution
    """

    sandbox_id: str = ""
    workdir: str = ""
    environment: dict[str, str] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)

    def is_ready(self) -> bool:
        """Check if context is ready"""
        return bool(self.sandbox_id and self.workdir)


@dataclass
class AgentExecutionResult:
    """Agent execution result

    Represents the result of a single Agent execution
    """

    exit_code: int
    stdout: list[str] = field(default_factory=list)
    stderr: list[str] = field(default_factory=list)
    error: dict[str, str] | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def is_success(self) -> bool:
        """Check if execution was successful"""
        return self.exit_code == 0 and self.error is None

    def has_output(self) -> bool:
        """Check if there is any output"""
        return bool(self.stdout or self.stderr)

    def get_combined_output(self) -> str:
        """Get combined output"""
        return "\n".join(self.stdout + self.stderr)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary"""
        return {
            "exit_code": self.exit_code,
            "stdout": self.stdout,
            "stderr": self.stderr,
            "error": self.error,
            "metadata": self.metadata,
        }


class Agent(ABC):
    """Agent abstract interface

    Defines interfaces that all Agents must implement
    """

    def __init__(self, config: AgentConfig):
        self._config = config
        self._status = AgentStatus.UNINITIALIZED

    @property
    def config(self) -> AgentConfig:
        """Get configuration"""
        return self._config

    @property
    def status(self) -> AgentStatus:
        """Get status"""
        return self._status

    @abstractmethod
    async def setup(self, context: AgentExecutionContext) -> None:
        """Set up Agent environment

        Args:
            context: Execution context

        Raises:
            Exception: Setup failure
        """
        pass

    @abstractmethod
    async def execute(
        self,
        prompt: str,
        context: AgentExecutionContext | None = None,
    ) -> AgentExecutionResult:
        """Execute prompt

        Args:
            prompt: User prompt
            context: Execution context

        Returns:
            Execution result
        """
        pass

    @abstractmethod
    async def cleanup(self, context: AgentExecutionContext) -> None:
        """Clean up Agent resources

        Args:
            context: Execution context
        """
        pass


class CLIAgent(Agent):
    """CLI Agent base class

    Provides common implementation for command-line based Agents
    """

    async def execute(
        self,
        prompt: str,
        context: AgentExecutionContext | None = None,
    ) -> AgentExecutionResult:
        """Execute CLI command

        Subclasses need to implement specific command building and execution logic
        """
        raise NotImplementedError("Subclasses must implement execute method")


class SDKAgent(Agent):
    """SDK Agent base class

    Provides common implementation for SDK-based Agents
    """

    async def execute(
        self,
        prompt: str,
        context: AgentExecutionContext | None = None,
    ) -> AgentExecutionResult:
        """Execute SDK call

        Subclasses need to implement specific SDK call logic
        """
        raise NotImplementedError("Subclasses must implement execute method")


class AgentFactory(ABC):
    """Agent factory abstract interface

    Defines interfaces that Agent factories must implement
    """

    @abstractmethod
    def create(self, config: AgentConfig) -> Agent:
        """Create Agent instance

        Args:
            config: Agent configuration

        Returns:
            Agent instance
        """
        pass

    @abstractmethod
    def create_config(self, agent_type: AgentType) -> AgentConfig:
        """Create Agent configuration

        Args:
            agent_type: Agent type

        Returns:
            Agent configuration
        """
        pass
