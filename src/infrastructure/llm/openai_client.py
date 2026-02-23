"""
OpenAI LLM Client Implementation

Provides LLM client implementation for OpenAI API, supports proxy/relay
"""

import asyncio
import os

try:
    from openai import AsyncOpenAI

    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False

from src.domain.generation.services.llm_injection_service import (
    LLMInjectionBatchRequest,
    LLMInjectionBatchResult,
    LLMInjectionRequest,
    LLMInjectionResult,
)
from src.domain.generation.value_objects.injection_strategy import InjectionStrategy
from src.infrastructure.llm.base_llm_client import LLMClient, LLMClientConfig
from src.infrastructure.llm.prompt_templates import PromptTemplates


class OpenAIClient(LLMClient):
    """OpenAI LLM Client

    Uses OpenAI API to execute intelligent injection, supports proxy/relay
    """

    DEFAULT_MODEL = "gpt-4o"
    DEFAULT_BASE_URL = "https://api.openai.com/v1"

    def __init__(self, config: LLMClientConfig | None = None, base_url: str = ""):
        """Initialize OpenAI client

        Args:
            config: Client configuration
            base_url: API base URL (for proxy/relay)

        Raises:
            ImportError: If openai package is not installed
            ValueError: If API Key is not set
        """
        if not OPENAI_AVAILABLE:
            raise ImportError(
                "The 'openai' package is required for OpenAIClient. "
                "Install it with: pip install openai"
            )

        super().__init__(config)

        # Get API Key
        api_key = self._config.api_key or os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ValueError(
                "OPENAI_API_KEY is required. Set it via environment variable "
                "or pass it in the config."
            )

        # Get Base URL (supports proxy/relay)
        base_url = base_url or os.getenv("OPENAI_BASE_URL", self.DEFAULT_BASE_URL)

        # Create async client
        self._client = AsyncOpenAI(
            api_key=api_key,
            base_url=base_url,
        )
        self._api_key = api_key
        self._base_url = base_url

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

            # Call OpenAI API
            response = await self._call_openai(prompt)

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
                    "provider": "openai",
                    "model": self._config.model,
                    "strategy": request.strategy.strategy_type.value,
                    "base_url": self._base_url,
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
        return "openai"

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

    async def _call_openai(self, prompt: str) -> str:
        """Call OpenAI API

        Args:
            prompt: Prompt

        Returns:
            Response text

        Raises:
            Exception: API call failed
        """
        try:
            response = await self._client.chat.completions.create(
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
            return response.choices[0].message.content or ""

        except Exception as e:
            raise RuntimeError(f"OpenAI API error: {e}")

    async def generate_code(self, prompt: str, language: str = "python") -> str:
        """Generate code

        Args:
            prompt: Prompt for code generation
            language: Programming language

        Returns:
            Generated code content
        """
        try:
            system_prompt = f"You are a code generator. Generate {language} code based on the user's request. Only output the code, no explanations."

            response = await self._client.chat.completions.create(
                model=self._config.model,
                max_tokens=4096,
                temperature=0.7,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": prompt},
                ],
            )

            return response.choices[0].message.content or ""

        except Exception as e:
            raise RuntimeError(f"OpenAI code generation error: {e}")

    def supports_batch(self) -> bool:
        """Check if batch processing is supported"""
        return True


def create_openai_client(
    api_key: str = "",
    model: str = "",
    base_url: str = "",
    max_tokens: int = 8192,
    temperature: float = 0.7,
) -> OpenAIClient:
    """Convenience function to create OpenAI client

    Args:
        api_key: API key (reads from environment variable if empty)
        model: Model name
        base_url: API base URL (reads from environment variable if empty)
        max_tokens: Maximum tokens
        temperature: Temperature parameter

    Returns:
        OpenAI client instance
    """
    config = LLMClientConfig(
        api_key=api_key or os.getenv("OPENAI_API_KEY", ""),
        model=model or OpenAIClient.DEFAULT_MODEL,
        max_tokens=max_tokens,
        temperature=temperature,
    )
    return OpenAIClient(config, base_url=base_url)
