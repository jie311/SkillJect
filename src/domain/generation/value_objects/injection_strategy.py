"""
Injection Strategy Value Object

Defines strategy types and configuration parameters for intelligent injection
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class InjectionStrategyType(Enum):
    """Injection strategy type enum

    Defines different intelligent injection strategy types
    """

    SEMANTIC_FUSION = "semantic_fusion"  # Semantic fusion: integrate payload semantics into original content
    STEALTH_INJECTION = "stealth_injection"  # Stealth injection: hide payload to make it hard to detect
    INTENT_UNDERSTANDING = "intent_understanding"  # Intent understanding: understand and reconstruct intent expression
    COMPREHENSIVE = "comprehensive"  # Comprehensive intelligence: combine all above strategies


@dataclass(frozen=True)
class InjectionStrategy:
    """Injection strategy configuration value object

    Defines behavioral configuration parameters for intelligent injection

    Attributes:
        strategy_type: Strategy type
        preserve_original_context: Whether to preserve original context
        natural_language_level: Natural language level (low/medium/high)
        stealth_level: Stealth level (low/medium/high)
        max_variants: Maximum number of generated variants
        custom_instructions: Custom instruction prompts
        extra_params: Additional parameters
    """

    strategy_type: InjectionStrategyType
    preserve_original_context: bool = True
    natural_language_level: str = "high"
    stealth_level: str = "medium"
    max_variants: int = 1
    custom_instructions: str = ""
    extra_params: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        """Validate parameter validity"""
        # Validate natural_language_level
        if self.natural_language_level not in ("low", "medium", "high"):
            raise ValueError(
                f"natural_language_level must be one of: low, medium, high, "
                f"got: {self.natural_language_level}"
            )

        # Validate stealth_level
        if self.stealth_level not in ("low", "medium", "high"):
            raise ValueError(
                f"stealth_level must be one of: low, medium, high, got: {self.stealth_level}"
            )

        # Validate max_variants
        if self.max_variants < 1:
            raise ValueError(f"max_variants must be at least 1, got: {self.max_variants}")

    def with_custom_instructions(self, instructions: str) -> "InjectionStrategy":
        """Return a new strategy with custom instructions

        Args:
            instructions: Custom instruction text

        Returns:
            New strategy object
        """
        return InjectionStrategy(
            strategy_type=self.strategy_type,
            preserve_original_context=self.preserve_original_context,
            natural_language_level=self.natural_language_level,
            stealth_level=self.stealth_level,
            max_variants=self.max_variants,
            custom_instructions=instructions,
            extra_params=self.extra_params.copy(),
        )

    def get_prompt_context(self) -> dict[str, Any]:
        """Get context parameters for LLM prompts

        Returns:
            Context dictionary
        """
        return {
            "strategy_type": self.strategy_type.value,
            "preserve_context": self.preserve_original_context,
            "language_level": self.natural_language_level,
            "stealth_level": self.stealth_level,
            "max_variants": self.max_variants,
            **self.extra_params,
        }


class InjectionStrategyFactory:
    """Injection strategy factory

    Provides predefined strategy configurations
    """

    @classmethod
    def semantic_fusion(
        cls,
        preserve_context: bool = True,
        language_level: str = "high",
    ) -> InjectionStrategy:
        """Create semantic fusion strategy

        Args:
            preserve_context: Whether to preserve original context
            language_level: Natural language level

        Returns:
            Semantic fusion strategy
        """
        return InjectionStrategy(
            strategy_type=InjectionStrategyType.SEMANTIC_FUSION,
            preserve_original_context=preserve_context,
            natural_language_level=language_level,
            stealth_level="low",  # Semantic fusion focuses on naturalness
            max_variants=1,
        )

    @classmethod
    def stealth_injection(
        cls,
        stealth_level: str = "high",
        preserve_context: bool = True,
    ) -> InjectionStrategy:
        """Create stealth injection strategy

        Args:
            stealth_level: Stealth level
            preserve_context: Whether to preserve original context

        Returns:
            Stealth injection strategy
        """
        return InjectionStrategy(
            strategy_type=InjectionStrategyType.STEALTH_INJECTION,
            preserve_original_context=preserve_context,
            natural_language_level="high",
            stealth_level=stealth_level,
            max_variants=1,
        )

    @classmethod
    def intent_understanding(
        cls,
        language_level: str = "high",
    ) -> InjectionStrategy:
        """Create intent understanding strategy

        Args:
            language_level: Natural language level

        Returns:
            Intent understanding strategy
        """
        return InjectionStrategy(
            strategy_type=InjectionStrategyType.INTENT_UNDERSTANDING,
            preserve_original_context=True,
            natural_language_level=language_level,
            stealth_level="medium",
            max_variants=1,
        )

    @classmethod
    def comprehensive(
        cls,
        stealth_level: str = "medium",
        language_level: str = "high",
        max_variants: int = 1,
    ) -> InjectionStrategy:
        """Create comprehensive intelligence strategy

        Args:
            stealth_level: Stealth level
            language_level: Natural language level
            max_variants: Maximum number of variants

        Returns:
            Comprehensive intelligence strategy
        """
        return InjectionStrategy(
            strategy_type=InjectionStrategyType.COMPREHENSIVE,
            preserve_original_context=True,
            natural_language_level=language_level,
            stealth_level=stealth_level,
            max_variants=max_variants,
        )

    @classmethod
    def from_string(cls, strategy_name: str) -> InjectionStrategy:
        """Create strategy from string

        Args:
            strategy_name: Strategy name

        Returns:
            Corresponding strategy object

        Raises:
            ValueError: Unknown strategy name
        """
        mapping = {
            "semantic_fusion": cls.semantic_fusion(),
            "stealth_injection": cls.stealth_injection(),
            "intent_understanding": cls.intent_understanding(),
            "comprehensive": cls.comprehensive(),
        }

        if strategy_name not in mapping:
            raise ValueError(
                f"Unknown strategy: {strategy_name}. Available: {list(mapping.keys())}"
            )

        return mapping[strategy_name]
