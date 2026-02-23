"""
Test Generation Strategy Factory
"""

from pathlib import Path
from typing import Any

from src.domain.testing.value_objects.execution_config import (
    GenerationConfig,
    GenerationStrategy,
)
from .generation_strategy import TestGenerationStrategy
from .template_injection_generator import TemplateInjectionGenerator
from .llm_intelligent_generator import LLMIntelligentGenerator
from .skillject_generator import SkilljectGenerator

# SECURITY_TEST_INPUTS strategy is not created through the factory for now, uses a separate generator


class TestGenerationStrategyFactory:
    """Test generation strategy factory

    Creates corresponding generator instances based on configuration
    """

    _strategies = {
        GenerationStrategy.TEMPLATE_INJECTION: TemplateInjectionGenerator,
        GenerationStrategy.LLM_INTELLIGENT: LLMIntelligentGenerator,
        GenerationStrategy.SKILLJECT: SkilljectGenerator,
    }

    @classmethod
    def create(
        cls,
        config: GenerationConfig,
        execution_output_dir: Path | None = None,
    ) -> TestGenerationStrategy:
        """Create a generator instance

        Args:
            config: Generation configuration
            execution_output_dir: Optional execution output directory (for saving to test_details)

        Returns:
            TestGenerationStrategy generator instance

        Raises:
            ValueError: Unsupported generation strategy
        """
        strategy_class = cls._strategies.get(config.strategy)

        if strategy_class is None:
            raise ValueError(f"Unsupported generation strategy: {config.strategy}")

        # Check if the generator supports execution_output_dir parameter
        import inspect
        sig = inspect.signature(strategy_class.__init__)
        if 'execution_output_dir' in sig.parameters:
            return strategy_class(config, execution_output_dir)
        else:
            return strategy_class(config)

    @classmethod
    def register_strategy(
        cls,
        strategy: GenerationStrategy,
        strategy_class: type[TestGenerationStrategy],
    ) -> None:
        """Register a custom strategy

        Args:
            strategy: Strategy enum
            strategy_class: Strategy class
        """
        cls._strategies[strategy] = strategy_class


def get_generator(
    config: GenerationConfig,
    execution_output_dir: Path | None = None,
) -> TestGenerationStrategy:
    """Convenience function to get a generator

    Args:
        config: Generation configuration
        execution_output_dir: Optional execution output directory (for saving to test_details)

    Returns:
        TestGenerationStrategy generator instance
    """
    return TestGenerationStrategyFactory.create(config, execution_output_dir)
