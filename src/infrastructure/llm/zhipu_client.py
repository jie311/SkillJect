"""
Zhipu AI LLM Client Implementation

Provides LLM client implementation for Zhipu AI (GLM) API
"""

import asyncio
import os
import re

try:
    from zai import ZhipuAiClient as SyncZhipuAiClient

    ZHIPU_AVAILABLE = True
except ImportError:
    ZHIPU_AVAILABLE = False
    SyncZhipuAiClient = None

from src.domain.generation.services.llm_injection_service import (
    InjectionPoint,
    LLMInjectionBatchRequest,
    LLMInjectionBatchResult,
    LLMInjectionRequest,
    LLMInjectionResult,
)
from src.domain.generation.value_objects.injection_strategy import InjectionStrategy
from src.infrastructure.llm.base_llm_client import LLMClient, LLMClientConfig
from src.infrastructure.llm.prompt_templates import PromptTemplates


class ZhipuAIClient(LLMClient):
    """Zhipu AI LLM Client

    Uses Zhipu AI (GLM) API to execute intelligent injection
    """

    DEFAULT_MODEL = "glm-4.7"
    DEFAULT_BASE_URL = "https://open.bigmodel.cn/api/paas/v4"

    def __init__(self, config: LLMClientConfig | None = None, base_url: str = ""):
        """Initialize Zhipu AI client

        Args:
            config: Client configuration
            base_url: API base URL

        Raises:
            ImportError: If zai-sdk package is not installed
            ValueError: If API Key is not set
        """
        if not ZHIPU_AVAILABLE:
            raise ImportError(
                "The 'zai-sdk' package is required for ZhipuAIClient. "
                "Install it with: pip install zai-sdk"
            )

        super().__init__(config)

        # Get API Key
        api_key = self._config.api_key or os.getenv("ZHIPU_API_KEY", "")
        if not api_key:
            raise ValueError(
                "ZHIPU_API_KEY is required. Set it via environment variable "
                "or pass it in the config."
            )

        # Create sync client (zai-sdk is synchronous)
        self._client = SyncZhipuAiClient(api_key=api_key)
        self._api_key = api_key

    async def inject_intelligent(self, request: LLMInjectionRequest) -> LLMInjectionResult:
        """Execute intelligent injection

        Args:
            request: Injection request

        Returns:
            Injection result
        """
        # Check if using payload directly as prompt (for Resource-First generation)
        if request.use_raw_prompt:
            prompt = request.payload
        else:
            # Build prompt (standard flow)
            prompt = self._build_prompt(request, request.strategy)

        # Execute sync call in thread pool
        response = await asyncio.to_thread(self._sync_chat, prompt)

        # Clean response
        injected_content = self._clean_response(response)

        # Parse injection points
        injection_points = self._parse_injection_points(injected_content, request.skill_content)

        # Calculate confidence
        confidence = self._calculate_confidence(injected_content, request.strategy)

        # Extract explanation
        explanation = self._extract_explanation(response)

        return LLMInjectionResult(
            injected_content=injected_content,
            injection_points=injection_points,
            explanation=explanation,
            confidence=confidence,
            metadata={
                "provider": "zhipu",
                "model": self._config.model,
                "strategy": request.strategy.strategy_type.value,
            },
            success=True,
        )

    def _sync_chat(self, prompt: str) -> str:
        """Execute chat request synchronously

        Args:
            prompt: Prompt

        Returns:
            Response text
        """
        response = self._client.chat.completions.create(
            model=self._config.model,
            messages=[{"role": "user", "content": prompt}],
            temperature=self._config.temperature,
            max_tokens=self._config.max_tokens,
        )

        return response.choices[0].message.content

    async def inject_intelligent_batch(
        self, batch_request: LLMInjectionBatchRequest
    ) -> LLMInjectionBatchResult:
        """Execute intelligent injection in batch

        Args:
            batch_request: Batch injection request

        Returns:
            Batch injection result
        """
        # Use semaphore to limit concurrency
        semaphore = asyncio.Semaphore(batch_request.max_concurrency)

        async def process_one(request: LLMInjectionRequest) -> LLMInjectionResult:
            async with semaphore:
                return await self.inject_intelligent(request)

        # Process all requests concurrently
        tasks = [process_one(req) for req in batch_request.requests]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Process exception results
        final_results = []
        errors = []

        for i, result in enumerate(results):
            if isinstance(result, Exception):
                errors.append(f"Request {i}: {str(result)}")
                final_results.append(
                    LLMInjectionResult(
                        injected_content="",
                        injection_points=[],
                        explanation="",
                        confidence=0.0,
                        success=False,
                        error_message=str(result),
                    )
                )
            else:
                final_results.append(result)

        return LLMInjectionBatchResult.from_results(final_results)

    def get_provider_name(self) -> str:
        """Get provider name

        Returns:
            Provider name
        """
        return "zhipu"

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
            injection_layer=request.injection_layer,
        )

    async def generate_code(self, prompt: str, language: str = "python") -> str:
        """Generate code

        Args:
            prompt: Prompt for code generation
            language: Programming language

        Returns:
            Generated code content
        """
        code_prompt = f"""Please generate {language} code for the following task:

{prompt}

Return only the code, no explanations."""

        response = await asyncio.to_thread(self._sync_chat, code_prompt)

        return response

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
                original_text=original_content[:200]
                if len(original_content) > 200
                else original_content,
                injected_text=response_text[:200] if len(response_text) > 200 else response_text,
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
