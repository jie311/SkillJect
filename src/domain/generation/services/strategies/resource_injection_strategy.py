"""
Resource Injection Strategy

Injects payload into the resources field of frontmatter and body content
"""

from src.domain.generation.interfaces import (
    IInjectionStrategy,
    InjectionContext,
    InjectionResult,
)
from src.domain.generation.services.parsers.skill_parser import UnifiedSkillParser
from src.shared.types import InjectionLayer


class ResourceInjectionStrategy(IInjectionStrategy):
    """Resource injection strategy

    Adds malicious resource URL to the resources list and references it in the body
    """

    # Default malicious resource URL
    DEFAULT_MALICIOUS_URL = "http://evil.com/malicious.md"

    def __init__(self, parser: UnifiedSkillParser | None = None):
        """Initialize strategy

        Args:
            parser: Skill parser (optional, defaults to new instance)
        """
        self._parser = parser or UnifiedSkillParser()

    @property
    def strategy_name(self) -> str:
        return "resource_injection"

    @property
    def target_layers(self) -> list[InjectionLayer]:
        return [InjectionLayer.RESOURCE]

    def can_handle(self, layer: InjectionLayer) -> bool:
        return layer in (
            InjectionLayer.RESOURCE,
            InjectionLayer.DESCRIPTION_RESOURCE,
            InjectionLayer.INSTRUCTION_RESOURCE,
            InjectionLayer.ALL,
        )

    def inject(self, context: InjectionContext) -> InjectionResult:
        """Execute injection

        Adds malicious resource URL to resources list and references it in the body

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

            # Add malicious resource URL
            updated_frontmatter = self._parser.add_resource(frontmatter, self.DEFAULT_MALICIOUS_URL)

            # Add reference in body
            reference_text = f"Refer to: {context.payload}"
            injected_content_body = self._parser.inject_into_content(
                content, reference_text, position="end"
            )

            # Rebuild content
            injected_content = self._parser.build(updated_frontmatter, injected_content_body)

            return InjectionResult(
                success=True,
                injected_content=injected_content,
                modified_layers=[InjectionLayer.RESOURCE],
                injection_points=["frontmatter.resources", "content.end"],
            )

        except Exception as e:
            result = InjectionResult(success=False)
            result.mark_failure(f"Resource injection failed: {e}")
            return result
