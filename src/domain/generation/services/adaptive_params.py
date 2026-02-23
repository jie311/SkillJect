"""
Adaptive Generation Parameters

Replacement for GenerationParams, supports feedback-based iterative generation.
"""

from dataclasses import dataclass
from typing import Literal

from ...analysis.services.failure_analyzer import FailureAnalysis


@dataclass
class AdaptiveGenerationParams:
    """Adaptive generation parameters

    Supports iterative generation parameters based on test feedback.

    Attributes:
        feedback: Failure analysis feedback (used to guide the next round of generation)
        previous_content: SKILL.md content from the previous round (used for improvement)
        iteration_number: Current iteration number (starts from 0)
        prompt_style: Prompt style (post_install)
    """

    feedback: FailureAnalysis | None = None
    previous_content: str | None = None
    iteration_number: int = 0
    prompt_style: Literal["post_install"] = "post_install"

    def __str__(self) -> str:
        """Return string representation of the parameters"""
        feedback_mode = self.feedback.mode.value if self.feedback else "none"
        return f"iteration_{self.iteration_number}+{feedback_mode}+{self.prompt_style}"

    def to_dict(self) -> dict:
        """Convert to dictionary"""
        return {
            "feedback_mode": self.feedback.mode.value if self.feedback else "none",
            "iteration_number": self.iteration_number,
            "prompt_style": self.prompt_style,
            "has_previous_content": self.previous_content is not None,
            "improvement_strategy": self.feedback.improvement_strategy if self.feedback else "",
        }

    @classmethod
    def create_initial(cls) -> "AdaptiveGenerationParams":
        """Create initial parameters (first iteration)

        Returns:
            Initial generation parameters
        """
        return cls(
            feedback=None,
            previous_content=None,
            iteration_number=0,
            prompt_style="post_install",
        )

    def create_next(
        self, feedback: FailureAnalysis, previous_content: str
    ) -> "AdaptiveGenerationParams":
        """Create parameters for the next iteration

        Args:
            feedback: Failure analysis feedback
            previous_content: SKILL.md content from the previous round

        Returns:
            Generation parameters for the next iteration
        """
        return AdaptiveGenerationParams(
            feedback=feedback,
            previous_content=previous_content,
            iteration_number=self.iteration_number + 1,
            prompt_style=self.prompt_style,
        )


__all__ = [
    "AdaptiveGenerationParams",
]
