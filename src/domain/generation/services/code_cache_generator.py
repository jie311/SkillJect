"""
Code Cache Generator

Pre-generates malicious code files for all attack types using LLM and caches them
"""

from pathlib import Path
from typing import Any

from src.domain.generation.services.code_cache_manager import CodeCacheManager
from src.infrastructure.llm.base_llm_client import LLMClient
from src.infrastructure.llm.code_generation_prompts import CodeGenerationPrompts
from src.shared.types import AttackType


class CodeCacheGenerator:
    """Code cache generator

    Pre-generates malicious code files for all attack types and caches them
    """

    def __init__(
        self,
        llm_client: LLMClient,
        cache_dir: Path | None = None,
    ):
        """Initialize the generator

        Args:
            llm_client: LLM client
            cache_dir: Cache directory
        """
        self._llm_client = llm_client
        self._cache_manager = CodeCacheManager(cache_dir)
        self._prompts = CodeGenerationPrompts()

    async def generate_all_caches(self) -> dict[str, Any]:
        """Generate code caches for all attack types

        Returns:
            Generation result statistics
        """
        results = {
            "total": 0,
            "successful": [],
            "failed": [],
            "errors": [],
        }

        for attack_type in AttackType:
            try:
                await self.generate_for_attack_type(attack_type)
                results["successful"].append(attack_type.value)
            except Exception as e:
                results["failed"].append(attack_type.value)
                results["errors"].append(f"{attack_type.value}: {str(e)}")

            results["total"] += 1

        return results

    async def generate_for_attack_type(self, attack_type: AttackType) -> None:
        """Generate code cache for a specific attack type

        Args:
            attack_type: Attack type
        """
        # Generate Python code
        python_prompt = self._prompts.get_python_prompt(attack_type)
        python_code = await self._llm_client.generate_code(
            prompt=python_prompt,
            language="python",
        )

        # Generate Shell code
        shell_prompt = self._prompts.get_shell_prompt(attack_type)
        shell_code = await self._llm_client.generate_code(
            prompt=shell_prompt,
            language="shell",
        )

        # Save to cache
        self._cache_manager.save_code_files(
            attack_type=attack_type,
            python_content=python_code,
            shell_content=shell_code,
        )

    def get_cached_code(self, attack_type: AttackType) -> dict[str, Path]:
        """Get cached code file paths

        Args:
            attack_type: Attack type

        Returns:
            Mapping from filename to path
        """
        return self._cache_manager.get_cached_code_paths(attack_type)

    def has_cache(self, attack_type: AttackType) -> bool:
        """Check if cache exists

        Args:
            attack_type: Attack type

        Returns:
            Whether cache exists
        """
        return self._cache_manager.has_cache(attack_type)

    def list_cached_attack_types(self) -> list[AttackType]:
        """List all cached attack types

        Returns:
            List of attack types
        """
        return self._cache_manager.get_all_cached_attack_types()
