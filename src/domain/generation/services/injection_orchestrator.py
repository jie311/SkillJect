"""
Injection Strategy Orchestrator

Coordinates different injection strategies, selecting the appropriate strategy based on injection layer
"""

from typing import Any

from src.domain.generation.interfaces import (
    IInjectionStrategy,
    InjectionContext,
    InjectionResult,
)
from src.domain.generation.services.parsers.skill_parser import UnifiedSkillParser
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
from src.shared.types import InjectionLayer


class InjectionOrchestrator:
    """Injection strategy orchestrator

    Automatically selects the appropriate strategy based on injection layer
    """

    def __init__(self, parser: UnifiedSkillParser | None = None):
        """Initialize the orchestrator

        Args:
            parser: Skill parser (optional)
        """
        self._parser = parser or UnifiedSkillParser()
        self._strategies: dict[InjectionLayer, IInjectionStrategy] = {
            InjectionLayer.DESCRIPTION: DescriptionInjectionStrategy(self._parser),
            InjectionLayer.INSTRUCTION: InstructionInjectionStrategy(self._parser),
            InjectionLayer.RESOURCE: ResourceInjectionStrategy(self._parser),
            InjectionLayer.DESCRIPTION_RESOURCE: MultiLayerInjectionStrategy(self._parser),
            InjectionLayer.INSTRUCTION_RESOURCE: MultiLayerInjectionStrategy(self._parser),
            InjectionLayer.ALL: MultiLayerInjectionStrategy(self._parser),
        }

    def register_strategy(self, layer: InjectionLayer, strategy: IInjectionStrategy) -> None:
        """Register or replace a strategy for a specific layer

        Args:
            layer: Injection layer
            strategy: Strategy instance
        """
        self._strategies[layer] = strategy

    def get_strategy(self, layer: InjectionLayer) -> IInjectionStrategy:
        """Get strategy for a specific layer

        Args:
            layer: Injection layer

        Returns:
            Corresponding strategy instance

        Raises:
            ValueError: Unsupported injection layer
        """
        if layer not in self._strategies:
            raise ValueError(f"Unsupported injection layer: {layer}")
        return self._strategies[layer]

    def inject(
        self,
        skill_name: str,
        content: str,
        layer: InjectionLayer,
        attack_type: Any,
        payload: str,
        metadata: dict[str, Any] | None = None,
    ) -> InjectionResult:
        """Execute injection

        Automatically selects the appropriate strategy based on injection layer

        Args:
            skill_name: Skill name
            content: Original content
            layer: Injection layer
            attack_type: Attack type
            payload: Payload content
            metadata: Additional metadata

        Returns:
            Injection result
        """
        # Parse content
        parsed_result = self._parser.parse(content)

        # Create injection context
        context = InjectionContext(
            skill_name=skill_name,
            original_content=content,
            parsed_result=parsed_result,
            layer=layer,
            attack_type=attack_type,
            payload=payload,
            metadata=metadata or {},
        )

        # Get strategy and execute injection
        strategy = self.get_strategy(layer)
        return strategy.inject(context)

    def inject_with_parsed(
        self,
        skill_name: str,
        parsed_result: Any,
        layer: InjectionLayer,
        attack_type: Any,
        payload: str,
        metadata: dict[str, Any] | None = None,
    ) -> InjectionResult:
        """Execute injection using already parsed result

        Args:
            skill_name: Skill name
            parsed_result: Parsed result
            layer: Injection layer
            attack_type: Attack type
            payload: Payload content
            metadata: Additional metadata

        Returns:
            Injection result
        """
        # Create injection context
        context = InjectionContext(
            skill_name=skill_name,
            original_content=parsed_result.raw_content
            if hasattr(parsed_result, "raw_content")
            else "",
            parsed_result=parsed_result,
            layer=layer,
            attack_type=attack_type,
            payload=payload,
            metadata=metadata or {},
        )

        # Get strategy and execute injection
        strategy = self.get_strategy(layer)
        return strategy.inject(context)
