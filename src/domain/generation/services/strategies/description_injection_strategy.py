"""
Description Injection Strategy

Injects payload into the description field of frontmatter
"""

from src.domain.generation.interfaces import (
    IInjectionStrategy,
    InjectionContext,
    InjectionResult,
)
from src.domain.generation.services.parsers.skill_parser import UnifiedSkillParser
from src.shared.types import InjectionLayer


class DescriptionInjectionStrategy(IInjectionStrategy):
    """Description injection strategy

    Injects payload into the description field of the skill file's frontmatter
    """

    def __init__(self, parser: UnifiedSkillParser | None = None):
        """Initialize strategy

        Args:
            parser: Skill parser (optional, defaults to new instance)
        """
        self._parser = parser or UnifiedSkillParser()

    @property
    def strategy_name(self) -> str:
        return "description_injection"

    @property
    def target_layers(self) -> list[InjectionLayer]:
        return [InjectionLayer.DESCRIPTION]

    def can_handle(self, layer: InjectionLayer) -> bool:
        return layer in (InjectionLayer.DESCRIPTION, InjectionLayer.ALL)

    def inject(self, context: InjectionContext) -> InjectionResult:
        """Execute injection

        Adds payload to the start of description

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

            # Add payload to description start
            updated_frontmatter = self._parser.prepend_to_description(frontmatter, context.payload)

            # Rebuild content
            injected_content = self._parser.build(updated_frontmatter, content)

            return InjectionResult(
                success=True,
                injected_content=injected_content,
                modified_layers=[InjectionLayer.DESCRIPTION],
                injection_points=["frontmatter.description"],
            )

        except Exception as e:
            result = InjectionResult(success=False)
            result.mark_failure(f"Description injection failed: {e}")
            return result
