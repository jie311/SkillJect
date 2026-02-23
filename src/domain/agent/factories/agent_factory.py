"""
Agent Factory

Responsible for creating Agent instances
"""

from typing import Type

from src.shared.exceptions import AgentNotFoundError
from src.shared.types import AgentType
from src.domain.agent.entities.agent import (
    Agent,
    AgentConfig,
    AgentFactory as AgentFactoryInterface,
)


class DefaultAgentFactory(AgentFactoryInterface):
    """Default Agent factory

    Creates corresponding Agent instances based on configuration
    """

    # Mapping from Agent type to implementation class
    _agent_classes: dict[AgentType, Type[Agent]] = {}

    # Mapping from Agent type to configuration class
    _config_classes: dict[AgentType, Type[AgentConfig]] = {}

    @classmethod
    def register_agent_class(
        cls,
        agent_type: AgentType,
        agent_class: Type[Agent],
    ) -> None:
        """Register Agent class

        Args:
            agent_type: Agent type
            agent_class: Agent implementation class
        """
        cls._agent_classes[agent_type] = agent_class

    @classmethod
    def register_config_class(
        cls,
        agent_type: AgentType,
        config_class: Type[AgentConfig],
    ) -> None:
        """Register configuration class

        Args:
            agent_type: Agent type
            config_class: Configuration class
        """
        cls._config_classes[agent_type] = config_class

    def create(self, config: AgentConfig) -> Agent:
        """Create Agent instance

        Args:
            config: Agent configuration

        Returns:
            Agent instance

        Raises:
            AgentNotFoundError: Agent type not registered
        """
        agent_class = self._agent_classes.get(config.agent_type)

        if agent_class is None:
            raise AgentNotFoundError(config.agent_type.value)

        return agent_class(config)

    def create_config(self, agent_type: AgentType) -> AgentConfig:
        """Create Agent configuration

        Args:
            agent_type: Agent type

        Returns:
            Agent configuration

        Raises:
            AgentNotFoundError: Agent type not registered
        """
        config_class = self._config_classes.get(agent_type)

        if config_class is None:
            raise AgentNotFoundError(agent_type.value)

        return config_class(agent_type=agent_type)

    @classmethod
    def list_registered_agents(cls) -> list[AgentType]:
        """List registered Agent types

        Returns:
            Agent type list
        """
        return list(cls._agent_classes.keys())


class CLIAgentFactory(DefaultAgentFactory):
    """CLI Agent factory

    Specializes in creating CLI-type Agents
    """

    def __init__(self):
        # Register default CLI Agents
        self._register_default_agents()

    def _register_default_agents(self) -> None:
        """Register default CLI Agents"""
        # Import from existing agents module
        try:
            from ....src.agents.cli_command_agent import CLICommandAgent

            self.register_agent_class(AgentType.CLAUDE_CODE, CLICommandAgent)
        except ImportError:
            pass


# Global factory instance
_default_factory: DefaultAgentFactory | None = None


def get_agent_factory() -> DefaultAgentFactory:
    """Get global Agent factory instance

    Returns:
        Agent factory instance
    """
    global _default_factory

    if _default_factory is None:
        _default_factory = DefaultAgentFactory()

    return _default_factory


def create_agent(config: AgentConfig) -> Agent:
    """Convenience function for creating Agent instance

    Args:
        config: Agent configuration

    Returns:
        Agent instance
    """
    return get_agent_factory().create(config)


def create_agent_config(agent_type: AgentType) -> AgentConfig:
    """Convenience function for creating Agent configuration

    Args:
        agent_type: Agent type

    Returns:
        Agent configuration
    """
    return get_agent_factory().create_config(agent_type)
