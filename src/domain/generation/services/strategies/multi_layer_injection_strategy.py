"""
Multi-layer Injection Strategy

Coordinates multiple single-layer strategies to implement multi-layer injection
"""

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
from src.domain.generation.services.strategies.resource_injection_strategy import (
    ResourceInjectionStrategy,
)
from src.shared.types import InjectionLayer


class MultiLayerInjectionStrategy(IInjectionStrategy):
    """Multi-layer injection strategy

    Coordinates multiple single-layer strategies to implement combined injection:
    - DESCRIPTION_RESOURCE: description + resource
    - INSTRUCTION_RESOURCE: instruction + resource
    - ALL: description + instruction + resource
    """

    def __init__(self, parser: UnifiedSkillParser | None = None):
        """Initialize strategy

        Args:
            parser: Skill parser (optional, defaults to new instance)
        """
        self._parser = parser or UnifiedSkillParser()
        self._description_strategy = DescriptionInjectionStrategy(parser)
        self._instruction_strategy = InstructionInjectionStrategy(parser)
        self._resource_strategy = ResourceInjectionStrategy(parser)

    @property
    def strategy_name(self) -> str:
        return "multi_layer_injection"

    @property
    def target_layers(self) -> list[InjectionLayer]:
        return [
            InjectionLayer.DESCRIPTION_RESOURCE,
            InjectionLayer.INSTRUCTION_RESOURCE,
            InjectionLayer.ALL,
        ]

    def can_handle(self, layer: InjectionLayer) -> bool:
        return layer in self.target_layers

    def inject(self, context: InjectionContext) -> InjectionResult:
        """Execute multi-layer injection

        Executes each single-layer strategy sequentially based on the specified layer combination

        Args:
            context: Injection context

        Returns:
            Injection result
        """
        # Validate context
        errors = self.validate_context(context)
        if errors:
            result = InjectionResult(success=False)
            result.mark_failure("; ".join(errors))
            return result

        try:
            # Get parsed result
            if hasattr(context.parsed_result, "frontmatter"):
                frontmatter = context.parsed_result.frontmatter
                content = context.parsed_result.content
            else:
                # Compatible with old format dictionary
                frontmatter = context.parsed_result.get("frontmatter", {})
                content = context.parsed_result.get("content", "")

            # Select strategy combination based on layer type
            modified_layers = []
            injection_points = []

            if context.layer == InjectionLayer.DESCRIPTION_RESOURCE:
                # Description + Resource
                frontmatter = self._parser.prepend_to_description(frontmatter, context.payload)
                modified_layers.append(InjectionLayer.DESCRIPTION)
                injection_points.append("frontmatter.description")

                frontmatter = self._parser.add_resource(
                    frontmatter, ResourceInjectionStrategy.DEFAULT_MALICIOUS_URL
                )
                modified_layers.append(InjectionLayer.RESOURCE)
                injection_points.append("frontmatter.resources")

                content = self._parser.inject_into_content(
                    content, f"Refer to: {context.payload}", position="end"
                )
                injection_points.append("content.end")

            elif context.layer == InjectionLayer.INSTRUCTION_RESOURCE:
                # Instruction + Resource
                frontmatter = self._parser.add_resource(
                    frontmatter, ResourceInjectionStrategy.DEFAULT_MALICIOUS_URL
                )
                modified_layers.append(InjectionLayer.RESOURCE)
                injection_points.append("frontmatter.resources")

                content = self._parser.inject_into_content(
                    content, f"{context.payload}\n\nRefer to: {context.payload}", position="end"
                )
                modified_layers.append(InjectionLayer.INSTRUCTION)
                injection_points.append("content.end")

            elif context.layer == InjectionLayer.ALL:
                # Description + Instruction + Resource
                frontmatter = self._parser.prepend_to_description(frontmatter, context.payload)
                modified_layers.append(InjectionLayer.DESCRIPTION)
                injection_points.append("frontmatter.description")

                frontmatter = self._parser.add_resource(
                    frontmatter, ResourceInjectionStrategy.DEFAULT_MALICIOUS_URL
                )
                modified_layers.append(InjectionLayer.RESOURCE)
                injection_points.append("frontmatter.resources")

                content = self._parser.inject_into_content(
                    content, f"{context.payload}\n\nRefer to: {context.payload}", position="end"
                )
                modified_layers.append(InjectionLayer.INSTRUCTION)
                injection_points.append("content.end")

            else:
                # Unsupported layer
                result = InjectionResult(success=False)
                result.mark_failure(f"Unsupported layer for multi-layer strategy: {context.layer}")
                return result

            # Rebuild content
            injected_content = self._parser.build(frontmatter, content)

            return InjectionResult(
                success=True,
                injected_content=injected_content,
                modified_layers=modified_layers,
                injection_points=injection_points,
            )

        except Exception as e:
            result = InjectionResult(success=False)
            result.mark_failure(f"Multi-layer injection failed: {e}")
            return result
