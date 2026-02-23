"""
Code Cache Manager

Manages cache of pre-generated malicious code files
"""

import shutil
from dataclasses import dataclass
from pathlib import Path

from src.shared.types import AttackType


@dataclass
class CachedCodeInfo:
    """Cached code information"""

    attack_type: AttackType
    python_file: str  # Python filename
    shell_file: str  # Shell filename
    cache_dir: Path


class CodeCacheManager:
    """Code cache manager

    Manages cache of pre-generated malicious code files, provides copy and query functions
    """

    DEFAULT_CACHE_DIR = Path("data/malicious_code_cache")

    # Filename mapping for each attack type
    FILENAME_MAPPING = {
        AttackType.INFORMATION_DISCLOSURE: ("env_stealer.py", "exfil_env.sh"),
        AttackType.PRIVILEGE_ESCALATION: ("bashrc_injector.py", "inject_bashrc.sh"),
        AttackType.UNAUTHORIZED_WRITE: ("file_writer.py", "write_main.sh"),
        AttackType.BACKDOOR_INJECTION: ("url_injector.py", "inject_url.sh"),
    }

    def __init__(self, cache_dir: Path | None = None):
        """Initialize the cache manager

        Args:
            cache_dir: Cache directory path
        """
        self._cache_dir = Path(cache_dir) if cache_dir else self.DEFAULT_CACHE_DIR

    def get_cache_dir(self, attack_type: AttackType) -> Path:
        """Get cache directory for a specific attack type

        Args:
            attack_type: Attack type

        Returns:
            Cache directory path
        """
        return self._cache_dir / attack_type.value

    def list_cached_files(self, attack_type: AttackType) -> list[str]:
        """List cached files for a specific attack type

        Args:
            attack_type: Attack type

        Returns:
            List of filenames
        """
        cache_dir = self.get_cache_dir(attack_type)
        if not cache_dir.exists():
            return []

        return [
            f.name
            for f in cache_dir.iterdir()
            if f.is_file() and (f.suffix == ".py" or f.suffix == ".sh")
        ]

    def get_cached_code_paths(self, attack_type: AttackType) -> dict[str, Path]:
        """Get cached code file paths

        Args:
            attack_type: Attack type

        Returns:
            Mapping from filename to path
        """
        cache_dir = self.get_cache_dir(attack_type)
        result = {}

        if cache_dir.exists():
            for f in cache_dir.iterdir():
                if f.is_file():
                    result[f.name] = f

        return result

    def copy_to_resources(
        self,
        attack_type: AttackType,
        dest_dir: Path,
    ) -> list[str]:
        """Copy cached code to target resources/ directory

        Args:
            attack_type: Attack type
            dest_dir: Target directory (usually resources/)

        Returns:
            List of copied filenames
        """
        cache_dir = self.get_cache_dir(attack_type)
        dest_dir = Path(dest_dir)

        # Ensure target directory exists
        dest_dir.mkdir(parents=True, exist_ok=True)

        copied_files = []

        if cache_dir.exists():
            for src_file in cache_dir.iterdir():
                if src_file.is_file() and (src_file.suffix == ".py" or src_file.suffix == ".sh"):
                    dest_file = dest_dir / src_file.name
                    shutil.copy2(src_file, dest_file)
                    copied_files.append(src_file.name)

        return copied_files

    def has_cache(self, attack_type: AttackType) -> bool:
        """Check if cache exists for a specific attack type

        Args:
            attack_type: Attack type

        Returns:
            Whether cache exists
        """
        cache_dir = self.get_cache_dir(attack_type)
        return cache_dir.exists() and any(cache_dir.iterdir())

    def get_all_cached_attack_types(self) -> list[AttackType]:
        """Get all cached attack types

        Returns:
            List of attack types
        """
        cached = []

        if self._cache_dir.exists():
            for attack_type in AttackType:
                if self.has_cache(attack_type):
                    cached.append(attack_type)

        return cached

    def get_cache_info(self, attack_type: AttackType) -> CachedCodeInfo | None:
        """Get cache information

        Args:
            attack_type: Attack type

        Returns:
            Cache information, or None if not exists
        """
        if not self.has_cache(attack_type):
            return None

        python_file, shell_file = self.FILENAME_MAPPING.get(
            attack_type, ("exploit.py", "exploit.sh")
        )

        return CachedCodeInfo(
            attack_type=attack_type,
            python_file=python_file,
            shell_file=shell_file,
            cache_dir=self.get_cache_dir(attack_type),
        )

    def ensure_cache_dir(self, attack_type: AttackType) -> Path:
        """Ensure cache directory exists

        Args:
            attack_type: Attack type

        Returns:
            Cache directory path
        """
        cache_dir = self.get_cache_dir(attack_type)
        cache_dir.mkdir(parents=True, exist_ok=True)
        return cache_dir

    def save_code_files(
        self,
        attack_type: AttackType,
        python_content: str | None = None,
        shell_content: str | None = None,
    ) -> None:
        """Save code files to cache

        Args:
            attack_type: Attack type
            python_content: Python code content
            shell_content: Shell code content
        """
        cache_dir = self.ensure_cache_dir(attack_type)
        python_file, shell_file = self.FILENAME_MAPPING.get(
            attack_type, ("exploit.py", "exploit.sh")
        )

        if python_content:
            (cache_dir / python_file).write_text(python_content, encoding="utf-8")

        if shell_content:
            (cache_dir / shell_file).write_text(shell_content, encoding="utf-8")
