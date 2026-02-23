"""
Anthropic Claude LLM Client Implementation

Provides LLM client implementation for Anthropic Claude API
"""

import asyncio
import os

try:
    import anthropic
    from anthropic import AsyncAnthropic

    ANTHROPIC_AVAILABLE = True
except ImportError:
    ANTHROPIC_AVAILABLE = False

from src.domain.generation.services.llm_injection_service import (
    LLMInjectionBatchRequest,
    LLMInjectionBatchResult,
    LLMInjectionRequest,
    LLMInjectionResult,
)
from src.domain.generation.value_objects.injection_strategy import InjectionStrategy
from src.infrastructure.llm.base_llm_client import LLMClient, LLMClientConfig
from src.infrastructure.llm.prompt_templates import PromptTemplates


class AnthropicClient(LLMClient):
    """Anthropic Claude LLM Client

    Uses Anthropic Claude API to execute intelligent injection
    """

    DEFAULT_MODEL = "claude-3-5-sonnet-20241022"

    def __init__(self, config: LLMClientConfig | None = None):
        """Initialize Anthropic client

        Args:
            config: Client configuration

        Raises:
            ImportError: If anthropic package is not installed
            ValueError: If API Key is not set
        """
        if not ANTHROPIC_AVAILABLE:
            raise ImportError(
                "The 'anthropic' package is required for AnthropicClient. "
                "Install it with: pip install anthropic"
            )

        super().__init__(config)

        # Get API Key
        api_key = self._config.api_key or os.getenv("ANTHROPIC_API_KEY")
        if not api_key:
            raise ValueError(
                "ANTHROPIC_API_KEY is required. Set it via environment variable "
                "or pass it in the config."
            )

        # Create async client
        self._client = AsyncAnthropic(api_key=api_key)
        self._api_key = api_key

    async def inject_intelligent(self, request: LLMInjectionRequest) -> LLMInjectionResult:
        """Execute intelligent injection

        Args:
            request: Injection request

        Returns:
            Injection result
        """
        try:
            # Check if using payload directly as prompt (for Resource-First generation)
            if request.use_raw_prompt:
                prompt = request.payload
            else:
                # Build prompt (standard flow)
                prompt = self._build_prompt(request, request.strategy)

            # Call Claude API
            response = await self._call_claude(prompt)

            # Clean response
            injected_content = self._clean_response(response)

            # Parse injection points
            injection_points = self._parse_injection_points(injected_content, request.skill_content)

            # Extract explanation
            explanation = self._extract_explanation(response)

            # Calculate confidence
            confidence = self._calculate_confidence(response, request.strategy)

            return LLMInjectionResult(
                injected_content=injected_content,
                injection_points=injection_points,
                explanation=explanation,
                confidence=confidence,
                metadata={
                    "provider": "anthropic",
                    "model": self._config.model,
                    "strategy": request.strategy.strategy_type.value,
                },
                success=True,
            )

        except Exception as e:
            return LLMInjectionResult(
                injected_content=request.skill_content,
                injection_points=[],
                explanation="",
                confidence=0.0,
                success=False,
                error_message=str(e),
            )

    async def inject_intelligent_batch(
        self, batch_request: LLMInjectionBatchRequest
    ) -> LLMInjectionBatchResult:
        """Execute intelligent injection in batch

        Args:
            batch_request: Batch injection request

        Returns:
            Batch injection result
        """
        # Create async tasks
        semaphore = asyncio.Semaphore(batch_request.max_concurrency)

        async def bounded_inject(request: LLMInjectionRequest) -> LLMInjectionResult:
            async with semaphore:
                return await self.inject_intelligent(request)

        # Concurrent execution
        results = await asyncio.gather(
            *[bounded_inject(req) for req in batch_request.requests],
            return_exceptions=True,
        )

        # Process exception results
        processed_results = []
        for r in results:
            if isinstance(r, Exception):
                processed_results.append(
                    LLMInjectionResult(
                        injected_content="",
                        injection_points=[],
                        explanation="",
                        confidence=0.0,
                        success=False,
                        error_message=str(r),
                    )
                )
            else:
                processed_results.append(r)

        return LLMInjectionBatchResult.from_results(processed_results)

    def get_provider_name(self) -> str:
        """Get provider name"""
        return "anthropic"

    def _build_prompt(self, request: LLMInjectionRequest, strategy: InjectionStrategy) -> str:
        """Build LLM prompt

        Args:
            request: Injection request
            strategy: Injection strategy

        Returns:
            Prompt string
        """
        return PromptTemplates.get_prompt(
            strategy=strategy,
            skill_content=request.skill_content,
            skill_frontmatter=request.skill_frontmatter,
            payload=request.payload,
            attack_type=request.attack_type.value,
        )

    async def _call_claude(self, prompt: str) -> str:
        """Call Claude API

        Args:
            prompt: Prompt

        Returns:
            Response text

        Raises:
            anthropic.APIError: API call failed
        """
        try:
            response = await self._client.messages.create(
                model=self._config.model,
                max_tokens=self._config.max_tokens,
                temperature=self._config.temperature,
                messages=[
                    {
                        "role": "user",
                        "content": prompt,
                    }
                ],
            )

            # Extract text content
            content = ""
            for block in response.content:
                if block.type == "text":
                    content += block.text

            return content

        except anthropic.APITimeoutError as e:
            raise TimeoutError(f"Claude API timeout: {e}")
        except anthropic.APIError as e:
            raise RuntimeError(f"Claude API error: {e}")

    def supports_batch(self) -> bool:
        """Check if batch processing is supported"""
        return True


def create_anthropic_client(
    api_key: str = "",
    model: str = "",
    max_tokens: int = 8192,
    temperature: float = 0.7,
) -> AnthropicClient:
    """Convenience function to create Anthropic client

    Args:
        api_key: API key (reads from environment variable if empty)
        model: Model name
        max_tokens: Maximum tokens
        temperature: Temperature parameter

    Returns:
        Anthropic client instance
    """
    config = LLMClientConfig(
        api_key=api_key,
        model=model or AnthropicClient.DEFAULT_MODEL,
        max_tokens=max_tokens,
        temperature=temperature,
    )
    return AnthropicClient(config)
