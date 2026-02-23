"""
Injection Strategy Module

Provides various injection layer strategy implementations
"""

from src.domain.generation.services.strategies.description_injection_strategy import (
    DescriptionInjectionStrategy,
)
from src.domain.generation.services.strategies.instruction_injection_strategy import (
    InstructionInjectionStrategy,
)
from src.domain.generation.services.strategies.multi_layer_injection_strategy import (
    MultiLayerInjectionStrategy,
)
from src.domain.generation.services.strategies.resource_injection_strategy import (
    ResourceInjectionStrategy,
)

__all__ = [
    "DescriptionInjectionStrategy",
    "InstructionInjectionStrategy",
    "ResourceInjectionStrategy",
    "MultiLayerInjectionStrategy",
]


def get_strategies() -> dict[str, type]:
    """Get all available strategy classes

    Returns:
        Mapping of strategy name to strategy class
    """
    return {
        "description": DescriptionInjectionStrategy,
        "instruction": InstructionInjectionStrategy,
        "resource": ResourceInjectionStrategy,
        "multi_layer": MultiLayerInjectionStrategy,
    }
