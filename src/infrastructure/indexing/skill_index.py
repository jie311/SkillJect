"""
Skill Index Service

Provides efficient skill indexing and query functionality, avoiding repeated file system scans.
Uses JSON index files for persistence, combined with memory cache for fast queries.
"""

import json
import threading
from datetime import datetime
from pathlib import Path
from typing import Any

from src.shared.types import SkillIndexEntry, TestIndexEntry
from src.shared.exceptions import SkillNotFoundError
from src.infrastructure.indexing.cache.memory_cache import get_global_cache


class SkillIndex:
    """Skill Index.

    Provides efficient skill and test case indexing functionality:
    - Incremental index updates (only scans changed files)
    - Memory cache for fast queries
    - Filter by multiple conditions
    - Statistics
    """

    # Index file names
    SKILLS_INDEX_FILE = "skills_index.json"
    TESTS_INDEX_FILE = "tests_index.json"

    def __init__(
        self,
        skills_dir: Path,
        tests_dir: Path | None = None,
        cache_ttl_seconds: int = 3600,
    ):
        """Initialize skill index.

        Args:
            skills_dir: Skills directory path
            tests_dir: Test case directory path (optional)
            cache_ttl_seconds: Cache TTL (seconds)
        """
        self._skills_dir = Path(skills_dir)
        self._tests_dir = Path(tests_dir) if tests_dir else None
        self._index_dir = self._skills_dir.parent / "index"
        self._cache_ttl = cache_ttl_seconds

        # Ensure index directory exists
        self._index_dir.mkdir(parents=True, exist_ok=True)

        # Memory cache
        self._cache = get_global_cache(max_size=2000, ttl_seconds=cache_ttl_seconds)

        # Thread lock
        self._lock = threading.RLock()

        # Index data
        self._skills_index: dict[str, SkillIndexEntry] = {}
        self._tests_index: dict[str, TestIndexEntry] = {}

        # Load existing indexes
        self._load_indexes()

    def _load_indexes(self) -> None:
        """Load indexes from disk."""
        with self._lock:
            self._load_skills_index()
            if self._tests_dir:
                self._load_tests_index()

    def _load_skills_index(self) -> None:
        """Load skills index."""
        index_file = self._index_dir / self.SKILLS_INDEX_FILE

        if not index_file.exists():
            # First run, build index
            self._rebuild_skills_index()
            return

        try:
            with open(index_file, encoding="utf-8") as f:
                data = json.load(f)

            self._skills_index = {
                name: self._skill_entry_from_dict(entry_data)
                for name, entry_data in data.get("skills", {}).items()
            }

            # Check if index needs update (based on directory modification time)
            index_mtime = index_file.stat().st_mtime
            dir_mtime = self._skills_dir.stat().st_mtime

            if dir_mtime > index_mtime:
                self._update_skills_index()

        except (json.JSONDecodeError, KeyError, IOError):
            # Index corrupted, rebuild
            self._rebuild_skills_index()

    def _load_tests_index(self) -> None:
        """Load tests index."""
        if not self._tests_dir:
            return

        index_file = self._index_dir / self.TESTS_INDEX_FILE

        if not index_file.exists():
            self._rebuild_tests_index()
            return

        try:
            with open(index_file, encoding="utf-8") as f:
                data = json.load(f)

            self._tests_index = {
                test_id: self._test_entry_from_dict(entry_data)
                for test_id, entry_data in data.get("tests", {}).items()
            }

            # Check if metadata file was updated
            metadata_file = self._tests_dir / "test_metadata.json"
            if metadata_file.exists():
                metadata_mtime = metadata_file.stat().st_mtime
                index_mtime = index_file.stat().st_mtime

                if metadata_mtime > index_mtime:
                    self._update_tests_index()

        except (json.JSONDecodeError, KeyError, IOError):
            self._rebuild_tests_index()

    def _rebuild_skills_index(self) -> None:
        """Rebuild skills index (scan all skills)."""
        skills = {}

        if not self._skills_dir.exists():
            self._skills_index = {}
            self._save_skills_index()
            return

        for skill_dir in self._skills_dir.iterdir():
            if not skill_dir.is_dir():
                continue

            skill_file = skill_dir / "SKILL.md"
            if not skill_file.exists():
                continue

            stat = skill_file.stat()
            skills[skill_dir.name] = SkillIndexEntry(
                name=skill_dir.name,
                path=str(skill_dir),
                has_instruction=self._has_instruction(skill_dir.name),
                size_bytes=stat.st_size,
                last_modified_timestamp=stat.st_mtime,
                keywords=self._extract_keywords(skill_file),
            )

        self._skills_index = skills
        self._save_skills_index()

    def _rebuild_tests_index(self) -> None:
        """Rebuild tests index."""
        if not self._tests_dir:
            return

        tests = {}
        metadata_file = self._tests_dir / "test_metadata.json"

        if metadata_file.exists():
            try:
                with open(metadata_file, encoding="utf-8") as f:
                    metadata = json.load(f)

                for test_data in metadata.get("tests", []):
                    test_id = test_data.get("test_id")
                    if not test_id:
                        continue

                    layer = test_data.get("injection_layer", "description")
                    test_path = self._tests_dir / layer / test_id

                    tests[test_id] = TestIndexEntry(
                        test_id=test_id,
                        skill_name=test_data.get("skill_name", ""),
                        layer=layer,
                        attack_type=test_data.get("attack_type", ""),
                        payload_name=test_data.get("payload_name", ""),
                        severity=test_data.get("severity", ""),
                        should_be_blocked=test_data.get("should_be_blocked", True),
                        path=str(test_path),
                    )
            except (json.JSONDecodeError, IOError):
                pass

        self._tests_index = tests
        self._save_tests_index()

    def _update_skills_index(self) -> None:
        """Incrementally update skills index (only scan changed files)."""
        if not self._skills_dir.exists():
            self._skills_index = {}
            self._save_skills_index()
            return

        # Check for deleted skills
        existing_skills = set(self._skills_index.keys())
        current_dirs = {
            d.name for d in self._skills_dir.iterdir() if d.is_dir() and (d / "SKILL.md").exists()
        }

        # Delete non-existent skills
        for deleted_skill in existing_skills - current_dirs:
            del self._skills_index[deleted_skill]
            # Clear cache
            self._cache.delete(f"skill_content:{deleted_skill}")

        # Update or add skills
        for skill_dir in self._skills_dir.iterdir():
            if not skill_dir.is_dir():
                continue

            skill_file = skill_dir / "SKILL.md"
            if not skill_file.exists():
                continue

            stat = skill_file.stat()
            skill_name = skill_dir.name

            # Check if update needed
            needs_update = (
                skill_name not in self._skills_index
                or self._skills_index[skill_name].last_modified_timestamp < stat.st_mtime
            )

            if needs_update:
                self._skills_index[skill_name] = SkillIndexEntry(
                    name=skill_name,
                    path=str(skill_dir),
                    has_instruction=self._has_instruction(skill_name),
                    size_bytes=stat.st_size,
                    last_modified_timestamp=stat.st_mtime,
                    keywords=self._extract_keywords(skill_file),
                )
                # Clear cache
                self._cache.delete(f"skill_content:{skill_name}")

        self._save_skills_index()

    def _update_tests_index(self) -> None:
        """Incrementally update tests index."""
        if not self._tests_dir:
            return

        self._rebuild_tests_index()

    def _save_skills_index(self) -> None:
        """Save skills index to disk."""
        index_file = self._index_dir / self.SKILLS_INDEX_FILE

        data = {
            "version": "1.0",
            "generated_at": datetime.now().isoformat(),
            "skills_count": len(self._skills_index),
            "skills": {
                name: self._skill_entry_to_dict(entry) for name, entry in self._skills_index.items()
            },
        }

        with open(index_file, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    def _save_tests_index(self) -> None:
        """Save tests index to disk."""
        if not self._tests_dir:
            return

        index_file = self._index_dir / self.TESTS_INDEX_FILE

        data = {
            "version": "1.0",
            "generated_at": datetime.now().isoformat(),
            "tests_count": len(self._tests_index),
            "tests": {
                test_id: self._test_entry_to_dict(entry)
                for test_id, entry in self._tests_index.items()
            },
        }

        with open(index_file, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    def _has_instruction(self, skill_name: str) -> bool:
        """Check if skill has instruction file."""
        instruction_dir = self._skills_dir.parent / "skills_instructions" / skill_name
        return instruction_dir.exists() and (instruction_dir / "instruction.md").exists()

    def _extract_keywords(self, skill_file: Path) -> list[str]:
        """Extract keywords from skill file."""
        keywords = []

        try:
            content = skill_file.read_text(encoding="utf-8")[:5000]  # Limit read size
            # Simple keyword extraction (can be extended to more complex NLP)
            common_keywords = [
                "file",
                "path",
                "env",
                "environment",
                "config",
                "api",
                "http",
                "url",
                "network",
                "database",
                "sql",
                "command",
                "execute",
                "run",
                "system",
                "shell",
                "docker",
                "kubernetes",
            ]

            content_lower = content.lower()
            for keyword in common_keywords:
                if keyword in content_lower:
                    keywords.append(keyword)

        except (IOError, UnicodeDecodeError):
            pass

        return keywords

    def _skill_entry_to_dict(self, entry: SkillIndexEntry) -> dict[str, Any]:
        """Convert skill index entry to dictionary."""
        return {
            "name": entry.name,
            "path": entry.path,
            "has_instruction": entry.has_instruction,
            "size_bytes": entry.size_bytes,
            "last_modified_timestamp": entry.last_modified_timestamp,
            "keywords": entry.keywords,
        }

    def _skill_entry_from_dict(self, data: dict[str, Any]) -> SkillIndexEntry:
        """Create skill index entry from dictionary."""
        return SkillIndexEntry(
            name=data["name"],
            path=data["path"],
            has_instruction=data.get("has_instruction", False),
            size_bytes=data.get("size_bytes", 0),
            last_modified_timestamp=data.get("last_modified_timestamp", 0),
            keywords=data.get("keywords", []),
        )

    def _test_entry_to_dict(self, entry: TestIndexEntry) -> dict[str, Any]:
        """Convert test index entry to dictionary."""
        return {
            "test_id": entry.test_id,
            "skill_name": entry.skill_name,
            "layer": entry.layer,
            "attack_type": entry.attack_type,
            "payload_name": entry.payload_name,
            "severity": entry.severity,
            "should_be_blocked": entry.should_be_blocked,
            "path": entry.path,
        }

    def _test_entry_from_dict(self, data: dict[str, Any]) -> TestIndexEntry:
        """Create test index entry from dictionary."""
        return TestIndexEntry(
            test_id=data["test_id"],
            skill_name=data.get("skill_name", ""),
            layer=data.get("layer", ""),
            attack_type=data.get("attack_type", ""),
            payload_name=data.get("payload_name", ""),
            severity=data.get("severity", ""),
            should_be_blocked=data.get("should_be_blocked", True),
            path=data.get("path", ""),
        )

    # ========== Public API ==========

    def list_skills(
        self,
        has_instruction: bool | None = None,
        keyword: str | None = None,
        limit: int | None = None,
    ) -> list[SkillIndexEntry]:
        """List skills.

        Args:
            has_instruction: Filter by whether instruction exists
            keyword: Filter by keyword
            limit: Limit return count

        Returns:
            List of skill index entries
        """
        with self._lock:
            # Ensure index is up to date
            self._update_skills_index()

            results = list(self._skills_index.values())

            # Apply filters
            if has_instruction is not None:
                results = [e for e in results if e.has_instruction == has_instruction]

            if keyword:
                keyword_lower = keyword.lower()
                results = [
                    e
                    for e in results
                    if keyword_lower in e.name.lower()
                    or any(keyword_lower in kw.lower() for kw in e.keywords)
                ]

            if limit:
                results = results[:limit]

            return results

    def get_skill(self, skill_name: str) -> SkillIndexEntry | None:
        """Get skill index entry.

        Args:
            skill_name: Skill name

        Returns:
            Skill index entry, or None if not exists
        """
        with self._lock:
            self._update_skills_index()

            return self._skills_index.get(skill_name)

    def skill_exists(self, skill_name: str) -> bool:
        """Check if skill exists.

        Args:
            skill_name: Skill name

        Returns:
            Whether skill exists
        """
        return self.get_skill(skill_name) is not None

    def get_skill_content(self, skill_name: str) -> str | None:
        """Get skill content.

        Args:
            skill_name: Skill name

        Returns:
            Skill content, or None if not exists

        Raises:
            SkillNotFoundError: Skill does not exist
        """
        cache_key = f"skill_content:{skill_name}"

        # Try getting from cache first
        cached = self._cache.get(cache_key)
        if cached is not None:
            return cached

        # Get path from index
        entry = self.get_skill(skill_name)
        if not entry:
            raise SkillNotFoundError(skill_name)

        # Read file
        skill_file = Path(entry.path) / "SKILL.md"
        if not skill_file.exists():
            raise SkillNotFoundError(skill_name)

        try:
            content = skill_file.read_text(encoding="utf-8")
            # Cache content
            self._cache.set(cache_key, content, ttl_seconds=self._cache_ttl)
            return content
        except IOError:
            return None

    def list_tests(
        self,
        skill_name: str | None = None,
        layer: str | None = None,
        attack_type: str | None = None,
        severity: str | None = None,
        limit: int | None = None,
    ) -> list[TestIndexEntry]:
        """List test cases.

        Args:
            skill_name: Filter by skill name
            layer: Filter by injection layer
            attack_type: Filter by attack type
            severity: Filter by severity
            limit: Limit return count

        Returns:
            List of test index entries
        """
        with self._lock:
            if self._tests_dir:
                self._update_tests_index()

            results = list(self._tests_index.values())

            # Apply filters
            if skill_name:
                results = [e for e in results if e.skill_name == skill_name]

            if layer:
                results = [e for e in results if e.layer == layer]

            if attack_type:
                results = [e for e in results if e.attack_type == attack_type]

            if severity:
                results = [e for e in results if e.severity == severity]

            if limit:
                results = results[:limit]

            return results

    def get_test(self, test_id: str) -> TestIndexEntry | None:
        """Get test index entry.

        Args:
            test_id: Test ID

        Returns:
            Test index entry, or None if not exists
        """
        with self._lock:
            if self._tests_dir:
                self._update_tests_index()

            return self._tests_index.get(test_id)

    def test_exists(self, test_id: str) -> bool:
        """Check if test exists.

        Args:
            test_id: Test ID

        Returns:
            Whether test exists
        """
        return self.get_test(test_id) is not None

    def refresh(self) -> None:
        """Force refresh index."""
        with self._lock:
            self._update_skills_index()
            if self._tests_dir:
                self._update_tests_index()

    def stats(self) -> dict[str, Any]:
        """Get index statistics.

        Returns:
            Statistics dictionary
        """
        with self._lock:
            return {
                "skills_count": len(self._skills_index),
                "tests_count": len(self._tests_index),
                "cache_stats": self._cache.stats(),
            }

    def clear_cache(self) -> None:
        """Clear cache."""
        self._cache.clear()
