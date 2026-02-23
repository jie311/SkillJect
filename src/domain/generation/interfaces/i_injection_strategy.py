"""
Injection Strategy Interface

Defines strategy interfaces for different injection layers
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

from src.shared.types import AttackType, InjectionLayer


@dataclass
class InjectionContext:
    """Injection context

    Contains all information needed to perform injection

    Attributes:
        skill_name: Skill name
        original_content: Original content
        parsed_result: Parsed result
        layer: Injection layer
        attack_type: Attack type
        payload: Payload content
        metadata: Additional metadata
    """

    skill_name: str
    original_content: str
    parsed_result: Any
    layer: InjectionLayer
    attack_type: AttackType
    payload: str
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class InjectionResult:
    """Injection result

    Attributes:
        success: Whether successful
        injected_content: Injected content
        modified_layers: List of actually modified layers
        injection_points: List of injection points
        error_message: Error message
        metadata: Additional metadata
    """

    success: bool = True
    injected_content: str = ""
    modified_layers: list[InjectionLayer] = field(default_factory=list)
    injection_points: list[str] = field(default_factory=list)
    error_message: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def mark_failure(self, error_message: str) -> None:
        """Mark as failure

        Args:
            error_message: Error message
        """
        self.success = False
        self.error_message = error_message


class IInjectionStrategy(ABC):
    """Injection strategy interface

    Defines injection strategies for specific injection layers
    """

    @property
    @abstractmethod
    def strategy_name(self) -> str:
        """Get strategy name

        Returns:
            Strategy name
        """
        pass

    @property
    @abstractmethod
    def target_layers(self) -> list[InjectionLayer]:
        """Get injection layers supported by this strategy

        Returns:
            List of supported injection layers
        """
        pass

    @abstractmethod
    def can_handle(self, layer: InjectionLayer) -> bool:
        """Check if injection layer is supported

        Args:
            layer: Injection layer

        Returns:
            Whether supported
        """
        pass

    @abstractmethod
    def inject(self, context: InjectionContext) -> InjectionResult:
        """Execute injection

        Args:
            context: Injection context

        Returns:
            Injection result
        """
        pass

    def validate_context(self, context: InjectionContext) -> list[str]:
        """Validate context

        Args:
            context: Injection context

        Returns:
            Error list (empty list indicates valid)
        """
        errors = []

        if not context.payload:
            errors.append("Payload cannot be empty")

        if not context.skill_name:
            errors.append("Skill name cannot be empty")

        return errors
