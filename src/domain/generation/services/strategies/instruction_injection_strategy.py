"""
Instruction Injection Strategy

Injects payload into the end of body content
"""

from src.domain.generation.interfaces import (
    IInjectionStrategy,
    InjectionContext,
    InjectionResult,
)
from src.domain.generation.services.parsers.skill_parser import UnifiedSkillParser
from src.shared.types import InjectionLayer


class InstructionInjectionStrategy(IInjectionStrategy):
    """Instruction injection strategy

    Injects payload into the end of the skill file's body content
    """

    def __init__(self, parser: UnifiedSkillParser | None = None):
        """Initialize strategy

        Args:
            parser: Skill parser (optional, defaults to new instance)
        """
        self._parser = parser or UnifiedSkillParser()

    @property
    def strategy_name(self) -> str:
        return "instruction_injection"

    @property
    def target_layers(self) -> list[InjectionLayer]:
        return [InjectionLayer.INSTRUCTION]

    def can_handle(self, layer: InjectionLayer) -> bool:
        return layer in (InjectionLayer.INSTRUCTION, InjectionLayer.ALL)

    def inject(self, context: InjectionContext) -> InjectionResult:
        """Execute injection

        Adds payload to the end of body content

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

            # Add payload to body end
            injected_content_body = self._parser.inject_into_content(
                content, context.payload, position="end"
            )

            # Rebuild content
            injected_content = self._parser.build(frontmatter, injected_content_body)

            return InjectionResult(
                success=True,
                injected_content=injected_content,
                modified_layers=[InjectionLayer.INSTRUCTION],
                injection_points=["content.end"],
            )

        except Exception as e:
            result = InjectionResult(success=False)
            result.mark_failure(f"Instruction injection failed: {e}")
            return result
