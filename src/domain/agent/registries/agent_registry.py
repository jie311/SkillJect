"""
Agent Registry

Manages all available Agent types
"""

from typing import Type, dict

from src.shared.types import AgentType
from src.domain.agent.entities.agent import Agent, AgentConfig


class AgentRegistry:
    """Agent registry

    Manages all available Agent types and configurations
    """

    # Registered Agent classes
    _agent_classes: dict[AgentType, Type[Agent]] = {}

    # Registered configuration classes
    _config_classes: dict[AgentType, Type[AgentConfig]] = {}

    # Display name mapping
    _display_names: dict[AgentType, str] = {
        AgentType.CLAUDE_CODE: "Claude Code",
        AgentType.GEMINI_CLI: "Gemini CLI",
        AgentType.CODEX_CLI: "Codex CLI",
        AgentType.IFLOW_CLI: "iFlow CLI",
    }

    @classmethod
    def register(
        cls,
        agent_type: AgentType,
        agent_class: Type[Agent] | None = None,
        config_class: Type[AgentConfig] | None = None,
    ) -> None:
        """Register Agent

        Args:
            agent_type: Agent type
            agent_class: Agent implementation class (optional)
            config_class: Configuration class (optional)
        """
        if agent_class is not None:
            cls._agent_classes[agent_type] = agent_class

        if config_class is not None:
            cls._config_classes[agent_type] = config_class

    @classmethod
    def unregister(cls, agent_type: AgentType) -> None:
        """Unregister Agent

        Args:
            agent_type: Agent type
        """
        cls._agent_classes.pop(agent_type, None)
        cls._config_classes.pop(agent_type, None)

    @classmethod
    def get_agent_class(cls, agent_type: AgentType) -> Type[Agent] | None:
        """Get Agent class

        Args:
            agent_type: Agent type

        Returns:
            Agent class or None
        """
        return cls._agent_classes.get(agent_type)

    @classmethod
    def get_config_class(cls, agent_type: AgentType) -> Type[AgentConfig] | None:
        """Get configuration class

        Args:
            agent_type: Agent type

        Returns:
            Configuration class or None
        """
        return cls._config_classes.get(agent_type)

    @classmethod
    def list_agents(cls) -> list[AgentType]:
        """List all registered Agent types

        Returns:
            Agent type list
        """
        return list(cls._agent_classes.keys())

    @classmethod
    def get_display_name(cls, agent_type: AgentType) -> str:
        """Get display name

        Args:
            agent_type: Agent type

        Returns:
            Display name
        """
        return cls._display_names.get(agent_type, agent_type.value)

    @classmethod
    def set_display_name(cls, agent_type: AgentType, display_name: str) -> None:
        """Set display name

        Args:
            agent_type: Agent type
            display_name: Display name
        """
        cls._display_names[agent_type] = display_name

    @classmethod
    def list_available_agents(cls) -> dict[str, str]:
        """List all available Agents

        Returns:
            Agent name to display name mapping
        """
        return {
            agent_type.value: cls.get_display_name(agent_type) for agent_type in cls.list_agents()
        }

    @classmethod
    def is_registered(cls, agent_type: AgentType) -> bool:
        """Check if Agent is registered

        Args:
            agent_type: Agent type

        Returns:
            Whether registered
        """
        return agent_type in cls._agent_classes

    @classmethod
    def clear(cls) -> None:
        """Clear all registrations (mainly for testing)"""
        cls._agent_classes.clear()
        cls._config_classes.clear()


def register_agent(
    agent_type: AgentType,
    agent_class: Type[Agent] | None = None,
    config_class: Type[AgentConfig] | None = None,
) -> None:
    """Convenience function for registering Agent

    Args:
        agent_type: Agent type
        agent_class: Agent implementation class (optional)
        config_class: Configuration class (optional)
    """
    AgentRegistry.register(agent_type, agent_class, config_class)


def list_available_agents() -> dict[str, str]:
    """Convenience function for listing all available Agents

    Returns:
        Agent name to display name mapping
    """
    return AgentRegistry.list_available_agents()
