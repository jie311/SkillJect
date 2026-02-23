"""
Instruction Updater

Batch updates existing instruction.md files, incorporating specific supporting filenames.
"""

import asyncio
import json
import re
import shutil
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any

try:
    from tqdm import tqdm

    TQDM_AVAILABLE = True
except ImportError:
    TQDM_AVAILABLE = False


class UpdateStatus(Enum):
    """Update status"""

    PENDING = "pending"
    SUCCESS = "success"
    FAILED = "failed"
    SKIPPED = "skipped"
    VALIDATION_FAILED = "validation_failed"


@dataclass
class UpdateResult:
    """Single instruction update result"""

    skill_name: str
    status: UpdateStatus
    old_instruction: str
    new_instruction: str
    backup_created: bool
    error: str | None = None
    validation_errors: list[str] = field(default_factory=list)
    timestamp: datetime = field(default_factory=datetime.now)


@dataclass
class BatchUpdateResult:
    """Batch update result"""

    total_processed: int
    success_count: int
    failure_count: int
    skipped_count: int
    validation_failed_count: int
    errors: list[str]
    results: list[UpdateResult]
    started_at: datetime
    completed_at: datetime
    duration_seconds: float


@dataclass
class InstructionUpdateConfig:
    """Instruction update configuration"""

    llm_provider: str = "zhipu"
    llm_model: str = "glm-4.7"
    api_key: str = ""
    base_url: str = ""  # OpenAI relay URL
    max_concurrency: int = 1
    request_delay: float = 5.0
    backup: bool = True
    dry_run: bool = False
    force_update: bool = False  # Whether to force update instructions that already contain filenames

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "InstructionUpdateConfig":
        """Create configuration from dictionary"""
        return cls(
            llm_provider=data.get("llm_provider", "zhipu"),
            llm_model=data.get("llm_model", "glm-4.7"),
            api_key=data.get("api_key", ""),
            base_url=data.get("base_url", ""),
            max_concurrency=data.get("max_concurrency", 1),
            request_delay=data.get("request_delay", 5.0),
            backup=data.get("backup", True),
            dry_run=data.get("dry_run", False),
            force_update=data.get("force_update", False),
        )


class InstructionUpdater:
    """Instruction updater

    Batch updates existing instruction.md files, incorporating specific supporting filenames.
    """

    # Generic terms list (should not appear in instructions)
    GENERIC_TERMS = [
        "attached file",
        "the file",
        "supporting file",
        "attached protein sequence file",
        "attached data",
        "provided file",
    ]

    def __init__(self, config: InstructionUpdateConfig):
        """Initialize the updater

        Args:
            config: Update configuration
        """
        self._config = config
        self._llm_client = None
        self._scanner = None

        # Lazy import to avoid circular dependency
        from .instruction_file_scanner import InstructionFileScanner

        self._scanner = InstructionFileScanner()

    async def update_single_instruction(
        self,
        skill_dir: Path,
        skill_content: str | None = None,
        frontmatter: dict[str, Any] | None = None,
    ) -> UpdateResult:
        """Update instruction for a single skill

        Args:
            skill_dir: Skill directory path
            skill_content: SKILL.md content (optional, if provided will not re-read)
            frontmatter: frontmatter data (optional)

        Returns:
            Update result
        """
        skill_name = skill_dir.name
        instruction_file = skill_dir / "instruction.md"

        # Check if instruction file exists
        if not instruction_file.exists():
            return UpdateResult(
                skill_name=skill_name,
                status=UpdateStatus.SKIPPED,
                old_instruction="",
                new_instruction="",
                backup_created=False,
                error="instruction.md does not exist",
            )

        # Read existing instruction
        try:
            old_instruction = instruction_file.read_text(encoding="utf-8").strip()
        except Exception as e:
            return UpdateResult(
                skill_name=skill_name,
                status=UpdateStatus.FAILED,
                old_instruction="",
                new_instruction="",
                backup_created=False,
                error=f"Failed to read instruction file: {e}",
            )

        # Scan supporting files
        scan_result = self._scanner.scan_skill(skill_dir)
        filenames = self._scanner.get_filenames_only(scan_result.supporting_files)

        # Skip if no supporting files
        if not filenames:
            return UpdateResult(
                skill_name=skill_name,
                status=UpdateStatus.SKIPPED,
                old_instruction=old_instruction,
                new_instruction="",
                backup_created=False,
                error="No supporting files found",
            )

        # Check if update is needed (if instruction already contains all filenames)
        if not self._config.force_update:
            valid, _ = self._scanner.validate_instruction_files(old_instruction, filenames)
            if valid and not self._contains_generic_terms(old_instruction):
                return UpdateResult(
                    skill_name=skill_name,
                    status=UpdateStatus.SKIPPED,
                    old_instruction=old_instruction,
                    new_instruction=old_instruction,
                    backup_created=False,
                    error="Instruction already contains all filenames",
                )

        # Read skill content (if not provided)
        if skill_content is None or frontmatter is None:
            skill_file = self._find_skill_file(skill_dir)
            if skill_file is None:
                return UpdateResult(
                    skill_name=skill_name,
                    status=UpdateStatus.FAILED,
                    old_instruction=old_instruction,
                    new_instruction="",
                    backup_created=False,
                    error="SKILL.md file not found",
                )
            try:
                skill_content = skill_file.read_text(encoding="utf-8")
                frontmatter = self._parse_frontmatter(skill_content)
            except Exception as e:
                return UpdateResult(
                    skill_name=skill_name,
                    status=UpdateStatus.FAILED,
                    old_instruction=old_instruction,
                    new_instruction="",
                    backup_created=False,
                    error=f"Failed to read skill file: {e}",
                )

        # Generate new instruction
        try:
            new_instruction = await self._generate_new_instruction(
                skill_content, frontmatter, filenames
            )
        except Exception as e:
            return UpdateResult(
                skill_name=skill_name,
                status=UpdateStatus.FAILED,
                old_instruction=old_instruction,
                new_instruction="",
                backup_created=False,
                error=f"Failed to generate new instruction: {e}",
            )

        # Validate new instruction
        validation_errors = self._validate_instruction(new_instruction, skill_name, filenames)
        if validation_errors:
            return UpdateResult(
                skill_name=skill_name,
                status=UpdateStatus.VALIDATION_FAILED,
                old_instruction=old_instruction,
                new_instruction=new_instruction,
                backup_created=False,
                validation_errors=validation_errors,
            )

        # Dry run mode - don't actually write files
        if self._config.dry_run:
            return UpdateResult(
                skill_name=skill_name,
                status=UpdateStatus.SUCCESS,
                old_instruction=old_instruction,
                new_instruction=new_instruction,
                backup_created=False,
            )

        # Create backup
        backup_created = False
        if self._config.backup:
            backup_created = self._create_backup(instruction_file)

        # Write new instruction
        try:
            instruction_file.write_text(new_instruction, encoding="utf-8")
        except Exception as e:
            # If write failed and backup was created, try to restore
            if backup_created:
                backup_file = instruction_file.with_suffix(".md.bak")
                if backup_file.exists():
                    shutil.copy(backup_file, instruction_file)
            return UpdateResult(
                skill_name=skill_name,
                status=UpdateStatus.FAILED,
                old_instruction=old_instruction,
                new_instruction=new_instruction,
                backup_created=backup_created,
                error=f"Failed to write new instruction: {e}",
            )

        return UpdateResult(
            skill_name=skill_name,
            status=UpdateStatus.SUCCESS,
            old_instruction=old_instruction,
            new_instruction=new_instruction,
            backup_created=backup_created,
        )

    async def batch_update_instructions(
        self,
        base_dir: Path,
        skill_names: list[str] | None = None,
    ) -> BatchUpdateResult:
        """Batch update instructions

        Args:
            base_dir: Base directory
            skill_names: List of skill names to update (None means all)

        Returns:
            Batch update result
        """
        started_at = datetime.now()
        results = []
        errors = []

        # Initialize LLM client
        from src.infrastructure.llm.factory import LLMClientFactory

        client_kwargs = {
            "provider": self._config.llm_provider,
            "model": self._config.llm_model,
            "api_key": self._config.api_key,
        }

        # If base_url is configured (for OpenAI relay), pass it
        if self._config.base_url:
            client_kwargs["base_url"] = self._config.base_url

        self._llm_client = LLMClientFactory.create_client(**client_kwargs)

        # Scan all skill directories
        all_skill_dirs = []
        for skill_dir in base_dir.iterdir():
            if not skill_dir.is_dir():
                continue

            if skill_names and skill_dir.name not in skill_names:
                continue

            instruction_file = skill_dir / "instruction.md"
            if instruction_file.exists():
                all_skill_dirs.append(skill_dir)

        # Progress bar
        pbar = None
        if TQDM_AVAILABLE:
            pbar = tqdm(total=len(all_skill_dirs), desc="Updating", unit="skill")
        else:
            print(f"Starting to update {len(all_skill_dirs)} skill instructions...")

        # Process each skill sequentially
        for i, skill_dir in enumerate(all_skill_dirs):
            result = await self.update_single_instruction(skill_dir)
            results.append(result)

            if result.status == UpdateStatus.FAILED and result.error:
                errors.append(f"{result.skill_name}: {result.error}")

            # Update progress bar
            if pbar:
                pbar.update(1)
                pbar.set_postfix(
                    {
                        "Success": sum(1 for r in results if r.status == UpdateStatus.SUCCESS),
                        "Skipped": sum(1 for r in results if r.status == UpdateStatus.SKIPPED),
                        "Failed": sum(1 for r in results if r.status == UpdateStatus.FAILED),
                    }
                )
            else:
                status_symbol = {
                    UpdateStatus.SUCCESS: "✓",
                    UpdateStatus.SKIPPED: "○",
                    UpdateStatus.FAILED: "✗",
                    UpdateStatus.VALIDATION_FAILED: "!",
                }.get(result.status, "?")
                print(f"[{i + 1}/{len(all_skill_dirs)}] {result.skill_name}: {status_symbol}")

            # Delay between requests
            if i < len(all_skill_dirs) - 1:
                await asyncio.sleep(self._config.request_delay)

        if pbar:
            pbar.close()

        completed_at = datetime.now()
        duration = (completed_at - started_at).total_seconds()

        return BatchUpdateResult(
            total_processed=len(results),
            success_count=sum(1 for r in results if r.status == UpdateStatus.SUCCESS),
            failure_count=sum(1 for r in results if r.status == UpdateStatus.FAILED),
            skipped_count=sum(1 for r in results if r.status == UpdateStatus.SKIPPED),
            validation_failed_count=sum(
                1 for r in results if r.status == UpdateStatus.VALIDATION_FAILED
            ),
            errors=errors,
            results=results,
            started_at=started_at,
            completed_at=completed_at,
            duration_seconds=duration,
        )

    def _find_skill_file(self, skill_dir: Path) -> Path | None:
        """Find SKILL.md file

        Args:
            skill_dir: Skill directory

        Returns:
            SKILL.md file path, or None if not exists
        """
        skill_name = skill_dir.name

        # Check current directory
        skill_file = skill_dir / "SKILL.md"
        if skill_file.exists():
            return skill_file

        # Check data/skills_from_skill0/ (same level as data/instruction/skills_from_skill0/)
        parent = skill_dir.parent
        if parent.name == "skills_from_skill0":
            # Find data/ directory (two levels up from data/instruction/skills_from_skill0/)
            data_dir = parent.parent.parent / "skills_from_skill0"
            skill_data_dir = data_dir / skill_name

            # Directly check skill directory
            alternative = skill_data_dir / "SKILL.md"
            if alternative.exists():
                return alternative

            # Check resources/ subdirectory (some skills have this structure)
            resources_dir = skill_data_dir / "resources" / skill_name
            if resources_dir.exists():
                alternative = resources_dir / "SKILL.md"
                if alternative.exists():
                    return alternative

        return None

    def _parse_frontmatter(self, content: str) -> dict[str, Any]:
        """Parse YAML frontmatter"""
        import yaml

        frontmatter = {}

        match = re.match(r"^---\n(.*?)\n---", content, re.DOTALL)
        if match:
            yaml_content = match.group(1)
            try:
                frontmatter = yaml.safe_load(yaml_content) or {}
            except yaml.YAMLError:
                pass

        frontmatter.setdefault("name", "Unknown Skill")
        frontmatter.setdefault("description", "")

        return frontmatter

    async def _generate_new_instruction(
        self,
        skill_content: str,
        frontmatter: dict[str, Any],
        filenames: list[str],
    ) -> str:
        """Generate new instruction

        Args:
            skill_content: Skill content
            frontmatter: frontmatter data
            filenames: List of supporting filenames

        Returns:
            New instruction text
        """
        # Build file information string
        files_info = self._format_files_info(filenames)

        # Build prompt
        prompt = self._build_prompt(skill_content, frontmatter, files_info)

        # Call LLM
        response = await self._call_llm(prompt)

        # Parse response
        data = self._parse_llm_response(response)

        return data.get("instruction", "")

    def _format_files_info(self, filenames: list[str]) -> str:
        """Format file information

        Args:
            filenames: List of filenames

        Returns:
            Formatted file information string
        """
        lines = ["**Available Supporting Files:**\n"]
        for filename in filenames:
            description = self._scanner.get_file_description(Path(filename))
            lines.append(f"- `{filename}`: {description}")
        return "\n".join(lines)

    def _build_prompt(
        self,
        skill_content: str,
        frontmatter: dict[str, Any],
        files_info: str,
    ) -> str:
        """Build LLM prompt"""
        from src.infrastructure.llm.prompt_templates import SECURITY_TEST_INPUT_PROMPT

        skill_name = frontmatter.get("name", "Unknown Skill")
        description = frontmatter.get("description", "")

        overview = self._extract_section(skill_content, "Overview")
        when_to_use = self._extract_section(skill_content, "When to Use") or frontmatter.get(
            "Use when", ""
        )
        examples = self._extract_section(skill_content, "Examples") or ""
        examples = examples[:500] if examples else "See skill documentation"

        return SECURITY_TEST_INPUT_PROMPT.format(
            skill_name=skill_name,
            description=description[:200],
            overview=overview[:300],
            when_to_use=when_to_use[:200],
            examples=examples,
            supporting_files_info=files_info,
        )

    def _extract_section(self, content: str, section_name: str) -> str:
        """Extract specific section from content"""
        content = re.sub(r"^---\n.*?\n---\n", "", content, flags=re.DOTALL)
        escaped_name = re.escape(section_name)

        pattern1 = rf"## {escaped_name}\s*\n(.*?)(?=\n##|\Z)"
        try:
            match = re.search(pattern1, content, re.DOTALL)
            if match:
                return match.group(1).strip()
        except re.error:
            pass

        pattern2 = rf"### {escaped_name}\s*\n(.*?)(?=\n##|\Z)"
        try:
            match = re.search(pattern2, content, re.DOTALL)
            if match:
                return match.group(1).strip()
        except re.error:
            pass

        return ""

    async def _call_llm(self, prompt: str) -> str:
        """Call LLM"""
        # Check client type, OpenAI uses async call
        if self._config.llm_provider == "openai":
            response = await self._llm_client._client.chat.completions.create(
                model=self._config.llm_model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.7,
                max_tokens=2048,
            )
            return response.choices[0].message.content
        else:
            # Other clients (Zhipu/Anthropic) use sync call
            response = await asyncio.to_thread(self._sync_llm_call, prompt)
            return response

    def _sync_llm_call(self, prompt: str) -> str:
        """Sync LLM call (for non-OpenAI clients)"""
        response = self._llm_client._client.chat.completions.create(
            model=self._config.llm_model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.7,
            max_tokens=2048,
        )
        return response.choices[0].message.content

    def _parse_llm_response(self, response: str) -> dict[str, Any]:
        """Parse LLM response"""
        response = response.strip()

        # Try to parse JSON in markdown code block
        code_block_pattern = r"```(?:json)?\s*\n?(.*?)\n?```"
        match = re.search(code_block_pattern, response, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(1).strip())
            except json.JSONDecodeError:
                pass

        # Try to parse directly
        try:
            return json.loads(response)
        except json.JSONDecodeError:
            pass

        # Try to find {...} format JSON
        brace_count = 0
        start_idx = -1
        for i, char in enumerate(response):
            if char == "{":
                if brace_count == 0:
                    start_idx = i
                brace_count += 1
            elif char == "}":
                brace_count -= 1
                if brace_count == 0 and start_idx >= 0:
                    json_str = response[start_idx : i + 1]
                    try:
                        return json.loads(json_str)
                    except json.JSONDecodeError:
                        pass

        raise ValueError(f"Failed to parse LLM response as JSON: {response[:200]}")

    def _validate_instruction(
        self, instruction: str, skill_name: str, filenames: list[str]
    ) -> list[str]:
        """Validate instruction format

        Args:
            instruction: Instruction text
            skill_name: Skill name
            filenames: Expected list of filenames to include

        Returns:
            List of validation errors (empty list means validation passed)
        """
        errors = []

        # Check length
        words = instruction.split()
        word_count = len(words)
        if word_count < 15 or word_count > 50:
            errors.append(f"Instruction length {word_count} words, out of range [15, 50]")

        # Check prefix format
        expected_prefix = f"Please use the {skill_name} skill to"
        if not instruction.startswith(expected_prefix):
            errors.append(f"Instruction does not start with expected prefix: '{expected_prefix}'")

        # Check if all filenames are included
        valid, missing = self._scanner.validate_instruction_files(instruction, filenames)
        if not valid:
            errors.append(f"Instruction missing filenames: {', '.join(missing)}")

        # Check if generic terms are included
        generic_terms_found = self._find_generic_terms(instruction)
        if generic_terms_found:
            errors.append(f"Instruction contains generic terms: {', '.join(generic_terms_found)}")

        return errors

    def _contains_generic_terms(self, instruction: str) -> bool:
        """Check if instruction contains generic terms"""
        return bool(self._find_generic_terms(instruction))

    def _find_generic_terms(self, instruction: str) -> list[str]:
        """Find generic terms in instruction

        Args:
            instruction: Instruction text

        Returns:
            List of generic terms found
        """
        instruction_lower = instruction.lower()
        found = []

        for term in self.GENERIC_TERMS:
            if term.lower() in instruction_lower:
                found.append(term)

        return found

    def _create_backup(self, file_path: Path) -> bool:
        """Create .bak backup file

        Args:
            file_path: Original file path

        Returns:
            Whether backup was successfully created
        """
        backup_path = file_path.with_suffix(".md.bak")

        try:
            shutil.copy(file_path, backup_path)
            return True
        except Exception:
            return False
