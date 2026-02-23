"""
LLM Client Abstract Base Class

Defines unified LLM client interface, supporting multiple LLM providers
"""

import json
import re
from abc import ABC, abstractmethod
from dataclasses import dataclass

from src.domain.generation.services.llm_injection_service import (
    InjectionPoint,
    LLMInjectionBatchRequest,
    LLMInjectionBatchResult,
    LLMInjectionRequest,
    LLMInjectionResult,
)
from src.domain.generation.value_objects.injection_strategy import InjectionStrategy


@dataclass
class LLMClientConfig:
    """LLM Client Configuration

    Attributes:
        api_key: API key
        model: Model name
        max_tokens: Maximum tokens
        temperature: Temperature parameter
        timeout: Request timeout (seconds)
    """

    api_key: str = ""
    model: str = "claude-3-5-sonnet-20241022"
    max_tokens: int = 8192
    temperature: float = 0.7
    timeout: int = 120


class LLMClient(ABC):
    """LLM Client Abstract Base Class

    Defines interfaces that all LLM clients must implement
    """

    def __init__(self, config: LLMClientConfig | None = None):
        """Initialize client

        Args:
            config: Client configuration
        """
        self._config = config or LLMClientConfig()

    @abstractmethod
    async def inject_intelligent(self, request: LLMInjectionRequest) -> LLMInjectionResult:
        """Execute intelligent injection

        Args:
            request: Injection request

        Returns:
            Injection result
        """
        raise NotImplementedError

    @abstractmethod
    async def inject_intelligent_batch(
        self, batch_request: LLMInjectionBatchRequest
    ) -> LLMInjectionBatchResult:
        """Execute intelligent injection in batch

        Args:
            batch_request: Batch injection request

        Returns:
            Batch injection result
        """
        raise NotImplementedError

    @abstractmethod
    def get_provider_name(self) -> str:
        """Get provider name

        Returns:
            Provider name
        """
        raise NotImplementedError

    @abstractmethod
    def _build_prompt(self, request: LLMInjectionRequest, strategy: InjectionStrategy) -> str:
        """Build LLM prompt

        Args:
            request: Injection request
            strategy: Injection strategy

        Returns:
            Prompt string
        """
        raise NotImplementedError

    @abstractmethod
    async def generate_code(self, prompt: str, language: str = "python") -> str:
        """Generate code

        Args:
            prompt: Prompt for code generation
            language: Programming language (python/shell)

        Returns:
            Generated code content
        """
        raise NotImplementedError

    def supports_batch(self) -> bool:
        """Check if batch processing is supported

        Default implementation returns True

        Returns:
            Whether batch processing is supported
        """
        return True

    def _parse_injection_points(
        self, response_text: str, original_content: str
    ) -> list[InjectionPoint]:
        """Parse injection point information from LLM response

        Args:
            response_text: LLM response text
            original_content: Original content

        Returns:
            List of injection points
        """
        # Default implementation: assume entire content was modified
        return [
            InjectionPoint(
                location="full_content",
                method="modify",
                original_text=original_content[:200],
                injected_text=response_text[:200],
            )
        ]

    def _calculate_confidence(self, response_text: str, strategy: InjectionStrategy) -> float:
        """Calculate injection confidence

        Args:
            response_text: Response text
            strategy: Injection strategy

        Returns:
            Confidence (0.0 - 1.0)
        """
        # Default implementation: return fixed confidence based on strategy type
        confidence_map = {
            "semantic_fusion": 0.85,
            "stealth_injection": 0.75,
            "intent_understanding": 0.80,
            "comprehensive": 0.90,
        }
        base_confidence = confidence_map.get(strategy.strategy_type.value, 0.70)

        # Adjust based on stealth level
        stealth_modifier = {
            "low": 0.0,
            "medium": -0.05,
            "high": -0.10,
        }
        modifier = stealth_modifier.get(strategy.stealth_level, 0.0)

        return max(0.0, min(1.0, base_confidence + modifier))

    def _extract_explanation(self, response_text: str) -> str:
        """Extract explanation from response

        Args:
            response_text: Response text

        Returns:
            Explanation text
        """
        # Try to extract JSON format explanation
        # Look for JSON format reasoning
        json_pattern = r'\s*"reasoning":\s*"(.*?)",?\s*\n'
        match = re.search(json_pattern, response_text, re.DOTALL)
        if match:
            return match.group(1).strip()

        # Look for XML tag format explanation
        xml_pattern = r"<explanation>(.*?)</explanation>"
        match = re.search(xml_pattern, response_text, re.DOTALL)
        if match:
            return match.group(1).strip()

        # Default explanation
        return "Payload injected using intelligent strategy"

    def _clean_response(self, response_text: str) -> str:
        """Clean LLM response, remove extra markers

        Args:
            response_text: Original response text

        Returns:
            Cleaned content
        """
        content = response_text

        # Remove JSON wrapper - use JSON parsing instead of regex
        if content.strip().startswith("{"):
            try:
                # Use JSON parsing to handle escape characters
                data = json.loads(content)
                # Prefer using skill_md field (Resource-First response)
                if "skill_md" in data:
                    content = data["skill_md"]
                # Secondly use content field (standard response)
                elif "content" in data:
                    content = data["content"]
            except (json.JSONDecodeError, UnicodeDecodeError):
                # JSON parsing failed, keep original content
                pass

        # Remove XML tags
        content = re.sub(r"<explanation>.*?</explanation>", "", content, flags=re.DOTALL)
        content = re.sub(r"<reasoning>.*?</reasoning>", "", content, flags=re.DOTALL)
        content = re.sub(r"<injection_points>.*?</injection_points>", "", content, flags=re.DOTALL)

        # Remove markdown code block markers
        content = self._strip_markdown_code_blocks(content)

        return content.strip()

    def _strip_markdown_code_blocks(self, content: str) -> str:
        """Remove markdown code block markers, keep content

        Supports removing the following code block markers:
        - ```markdown
        - ```yaml
        - ```text
        - ```json
        - ``` (no language identifier)

        Args:
            content: Content that may contain code block markers

        Returns:
            Content with code block markers removed
        """
        pattern = r"^```(?:\w+)?\s*\n(.*?)\n?```\s*$"
        match = re.search(pattern, content.strip(), re.DOTALL)
        if match:
            return match.group(1).strip()
        return content
