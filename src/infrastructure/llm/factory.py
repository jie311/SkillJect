"""
LLM Client Factory

Provides factory class for creating corresponding LLM clients based on configuration
"""

import os

from src.infrastructure.llm.anthropic_client import AnthropicClient, create_anthropic_client
from src.infrastructure.llm.base_llm_client import LLMClient, LLMClientConfig
from src.infrastructure.llm.openai_client import OpenAIClient
from src.infrastructure.llm.zhipu_client import ZhipuAIClient

# Supported client type mapping
_CLIENT_REGISTRY: dict[str, type[LLMClient]] = {
    "anthropic": AnthropicClient,
    "openai": OpenAIClient,
    "zhipu": ZhipuAIClient,
    "glm": ZhipuAIClient,  # alias
}


class LLMClientFactory:
    """LLM Client Factory Class

    Creates corresponding LLM client instances based on configuration
    """

    # Default configuration
    DEFAULT_PROVIDER = "zhipu"
    DEFAULT_MODEL = "glm-4.7"

    @classmethod
    def create_client(
        cls,
        provider: str = "",
        config: LLMClientConfig | None = None,
        **kwargs,
    ) -> LLMClient:
        """Create LLM client

        Args:
            provider: Provider name (anthropic, openai, zhipu, glm)
            config: Client configuration
            **kwargs: Additional configuration parameters

        Returns:
            LLM client instance

        Raises:
            ValueError: Unknown provider type
        """
        # Determine provider
        provider = provider or os.getenv("LLM_PROVIDER", cls.DEFAULT_PROVIDER)
        provider = provider.lower()

        # Get client class
        client_class = _CLIENT_REGISTRY.get(provider)
        if not client_class:
            available = ", ".join(_CLIENT_REGISTRY.keys())
            raise ValueError(f"Unknown LLM provider: {provider}. Available providers: {available}")

        # Create configuration
        if config is None:
            config = cls._create_config(provider, **kwargs)

        # Create and return client
        try:
            # OpenAI client requires additional base_url parameter
            if provider == "openai":
                base_url = kwargs.get("base_url", os.getenv("OPENAI_BASE_URL", ""))
                return client_class(config, base_url=base_url)
            return client_class(config)
        except ImportError as e:
            raise ImportError(f"Failed to import dependencies for {provider}: {e}")
        except Exception as e:
            raise RuntimeError(f"Failed to create {provider} client: {e}")

    @classmethod
    def create_client_from_env(cls) -> LLMClient:
        """Create client from environment variables

        Reads the following environment variables:
        - LLM_PROVIDER: Provider type (default: zhipu)
        - ANTHROPIC_API_KEY: Anthropic API Key
        - OPENAI_API_KEY: OpenAI API Key
        - ZHIPU_API_KEY: Zhipu AI API Key
        - OPENAI_BASE_URL: OpenAI API base URL (proxy/relay)

        Returns:
            LLM client instance
        """
        provider = os.getenv("LLM_PROVIDER", cls.DEFAULT_PROVIDER)
        return cls.create_client(provider)

    @classmethod
    def _create_config(cls, provider: str, **kwargs) -> LLMClientConfig:
        """Create configuration for specific provider

        Args:
            provider: Provider name
            **kwargs: Configuration parameters

        Returns:
            Client configuration
        """
        # API Key priority: parameter > environment variable
        api_key = kwargs.get("api_key", "")

        if provider == "anthropic" and not api_key:
            api_key = os.getenv("ANTHROPIC_API_KEY", "")
        elif provider == "openai" and not api_key:
            api_key = os.getenv("OPENAI_API_KEY", "")
        elif provider in ("zhipu", "glm") and not api_key:
            api_key = os.getenv("ZHIPU_API_KEY", "")

        return LLMClientConfig(
            api_key=api_key,
            model=kwargs.get("model", cls.DEFAULT_MODEL),
            max_tokens=kwargs.get("max_tokens", 8192),
            temperature=kwargs.get("temperature", 0.7),
            timeout=kwargs.get("timeout", 120),
        )

    @classmethod
    def register_client(cls, name: str, client_class: type[LLMClient]) -> None:
        """Register new client type

        Args:
            name: Client name
            client_class: Client class
        """
        _CLIENT_REGISTRY[name.lower()] = client_class

    @classmethod
    def list_providers(cls) -> list[str]:
        """Get all supported providers

        Returns:
            List of provider names
        """
        return list(_CLIENT_REGISTRY.keys())


# Convenience functions
def create_client(provider: str = "", **kwargs) -> LLMClient:
    """Convenience function to create LLM client

    Args:
        provider: Provider name
        **kwargs: Configuration parameters

    Returns:
        LLM client instance
    """
    return LLMClientFactory.create_client(provider, **kwargs)


def create_anthropic_client(api_key: str = "", model: str = "", **kwargs) -> AnthropicClient:
    """Convenience function to create Anthropic client

    Args:
        api_key: API key
        model: Model name
        **kwargs: Additional parameters

    Returns:
        Anthropic client instance
    """
    from infrastructure.llm.anthropic_client import create_anthropic_client as _create

    return _create(
        api_key=api_key or os.getenv("ANTHROPIC_API_KEY", ""),
        model=model or LLMClientFactory.DEFAULT_MODEL,
        **kwargs,
    )
