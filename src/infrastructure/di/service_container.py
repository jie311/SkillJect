"""
Simple Dependency Injection Container

Provides service registration and dependency resolution functionality.
"""

from typing import Any, Callable, Type, TypeVar

T = TypeVar("T")


class ServiceContainer:
    """Simple dependency injection container.

    Supports singleton and factory patterns.
    """

    def __init__(self) -> None:
        """Initialize container."""
        self._services: dict[str, Any] = {}
        self._factories: dict[str, Callable[[], Any]] = {}
        self._singletons: dict[str, Any] = {}

    def register_instance(self, name: str, instance: Any) -> None:
        """Register an instance.

        Args:
            name: Service name
            instance: Service instance
        """
        self._services[name] = instance

    def register_singleton(self, name: str, factory: Callable[[], Any]) -> None:
        """Register a singleton factory.

        Args:
            name: Service name
            factory: Factory function
        """
        self._factories[name] = factory

    def register_transient(self, name: str, factory: Callable[[], Any]) -> None:
        """Register a transient factory (creates new instance each call).

        Args:
            name: Service name
            factory: Factory function
        """
        self._factories[name] = factory
        # Mark as non-singleton
        self._services[name] = None  # None means transient

    def get(self, name: str) -> Any:
        """Get service.

        Args:
            name: Service name

        Returns:
            Service instance

        Raises:
            KeyError: Service not registered
        """
        # First check directly registered instances
        if name in self._services and self._services[name] is not None:
            return self._services[name]

        # Check singletons
        if name in self._singletons:
            return self._singletons[name]

        # Check factories
        if name in self._factories:
            instance = self._factories[name]()
            # If singleton (not transient), cache instance
            if name not in self._services or self._services[name] is not None:
                self._singletons[name] = instance
            return instance

        raise KeyError(f"Service not registered: {name}")

    def has(self, name: str) -> bool:
        """Check if service is registered.

        Args:
            name: Service name

        Returns:
            Whether service is registered
        """
        return name in self._services or name in self._factories or name in self._singletons

    def resolve(self, cls: Type[T]) -> T:
        """Resolve service by type.

        Args:
            cls: Service type

        Returns:
            Service instance

        Raises:
            KeyError: Service not registered
        """
        name = cls.__name__
        return self.get(name)

    def clear(self) -> None:
        """Clear container (mainly for testing)."""
        self._services.clear()
        self._factories.clear()
        self._singletons.clear()


# Global container instance
container = ServiceContainer()


def configure_services() -> ServiceContainer:
    """Configure default services.

    Returns:
        Configured container
    """
    from domain.generation.services.parsers.skill_parser import UnifiedSkillParser
    from domain.generation.services.strategies.description_injection_strategy import (
        DescriptionInjectionStrategy,
    )
    from domain.generation.services.strategies.instruction_injection_strategy import (
        InstructionInjectionStrategy,
    )
    from domain.generation.services.strategies.multi_layer_injection_strategy import (
        MultiLayerInjectionStrategy,
    )
    from domain.generation.services.strategies.resource_injection_strategy import (
        ResourceInjectionStrategy,
    )

    # Register parser as singleton
    container.register_singleton("skill_parser", lambda: UnifiedSkillParser())

    # Register strategies
    container.register_singleton(
        "description_strategy", lambda: DescriptionInjectionStrategy(container.get("skill_parser"))
    )
    container.register_singleton(
        "instruction_strategy", lambda: InstructionInjectionStrategy(container.get("skill_parser"))
    )
    container.register_singleton(
        "resource_strategy", lambda: ResourceInjectionStrategy(container.get("skill_parser"))
    )
    container.register_singleton(
        "multi_layer_strategy", lambda: MultiLayerInjectionStrategy(container.get("skill_parser"))
    )

    return container


# Auto configuration
configure_services()
