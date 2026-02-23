"""
Security Test Input Generator

Uses LLM to generate security test inputs (instruction.md + supporting files) for each skill
For AI Agent security testing
"""

import asyncio
import json
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

try:
    from tqdm import tqdm

    TQDM_AVAILABLE = True
except ImportError:
    TQDM_AVAILABLE = False

from .generation_strategy import TestGenerationStrategy
from ..entities.test_suite import GeneratedTestSuite
from src.domain.testing.value_objects.execution_config import (
    GenerationConfig as TestGenerationConfig,
)
from src.infrastructure.loaders.paths import resolve_data_path


@dataclass
class TestInputResult:
    """Test input generation result"""

    skill_name: str
    instruction: str
    supporting_files: dict[str, str]
    success: bool
    error: str | None = None


@dataclass
class SecurityTestInputConfig:
    """Security test input generation configuration"""

    llm_provider: str = "zhipu"
    llm_model: str = "glm-4.7"
    api_key: str = ""
    max_concurrency: int = 1
    batch_size: int | None = None
    output_dir: str = "data/instruction/skills_from_skill0"
    request_delay: float = 5.0  # Delay between requests (seconds)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "SecurityTestInputConfig":
        """Create configuration from dictionary"""
        return cls(
            llm_provider=data.get("llm_provider", "zhipu"),
            llm_model=data.get("llm_model", "glm-4.7"),
            api_key=data.get("api_key", ""),
            max_concurrency=data.get("max_concurrency", 1),
            batch_size=data.get("batch_size"),
            request_delay=data.get("request_delay", 2.0),
            output_dir=data.get("output_dir", "data/instruction/skills_from_skill0"),
        )


class SecurityTestInputGenerator(TestGenerationStrategy):
    """Security test input generator

    Uses LLM to generate test input files for each skill:
    - instruction.md: Test instruction (20-40 words, explicitly requires using the skill)
    - supporting files: Virtual sample data (generic English content)
    """

    def __init__(self, config: TestGenerationConfig, security_config: SecurityTestInputConfig):
        super().__init__(config)
        self._security_config = security_config
        self._llm_client = None
        self._scanner = None  # InstructionFileScanner instance (lazy initialization)

    async def generate(self) -> GeneratedTestSuite:
        """Generate test inputs"""
        # Lazy import to avoid circular dependency
        from src.infrastructure.llm.factory import LLMClientFactory

        # Initialize LLM client (pass API key)
        self._llm_client = LLMClientFactory.create_client(
            provider=self._security_config.llm_provider,
            model=self._security_config.llm_model,
            api_key=self._security_config.api_key,
        )

        # Scan skill files
        skill_files = self._scan_skill_files()

        # Apply batch limit
        if self._security_config.batch_size:
            skill_files = skill_files[: self._security_config.batch_size]

        # Generate test inputs (each result is saved immediately)
        results = await self._generate_test_inputs(skill_files)

        # Create test suite (for compatibility)
        suite = GeneratedTestSuite(
            suite_id=self._create_suite_id(),
            generation_strategy="security_test_inputs",
            generated_at=datetime.now(),
            test_cases=[],  # Security test inputs are not traditional test cases
            metadata={
                "provider": self._security_config.llm_provider,
                "model": self._security_config.llm_model,
                "total_skills": len(skill_files),
                "successful": sum(1 for r in results if r.success),
                "failed": sum(1 for r in results if not r.success),
            },
        )

        # Save metadata
        await self._save_metadata(suite, results)

        return suite

    def validate_config(self) -> list[str]:
        """Validate configuration"""
        errors = []

        if not self._security_config.llm_provider:
            errors.append("LLM provider not configured")

        if not self._security_config.llm_model:
            errors.append("LLM model not configured")

        return errors

    def _scan_skill_files(self) -> list[Path]:
        """Scan skill files, skip already generated ones"""
        skill_files = []
        base_dir = resolve_data_path(self.config.template_base_dir)
        output_dir = Path(self._security_config.output_dir)

        if not base_dir.exists():
            print(f"Base directory not found: {base_dir}")
            return skill_files

        # Count already generated skills
        already_generated = set()
        if output_dir.exists():
            for skill_dir in output_dir.iterdir():
                if skill_dir.is_dir():
                    instruction_file = skill_dir / "instruction.md"
                    if instruction_file.exists() and instruction_file.stat().st_size > 0:
                        already_generated.add(skill_dir.name)

        # Scan all SKILL.md files
        total_count = 0
        for skill_file in base_dir.rglob("SKILL.md"):
            total_count += 1
            skill_name = skill_file.parent.name

            # Filter by skill name
            if self.config.skill_names and skill_name not in self.config.skill_names:
                continue

            # Skip already generated skills
            if skill_name in already_generated:
                continue

            skill_files.append(skill_file)

        # Print scan statistics
        print("Scan results:")
        print(f"  Total skills:      {total_count}")
        print(f"  Already generated: {len(already_generated)}")
        print(f"  To generate:       {len(skill_files)}")

        if already_generated:
            print(f"Skipping {len(already_generated)} already generated skills")

        return sorted(skill_files)

    async def _generate_test_inputs(self, skill_files: list[Path]) -> list[TestInputResult]:
        """Generate test inputs (with progress bar, immediate save, delay between requests)

        Args:
            skill_files: List of skill files

        Returns:
            List of generation results
        """
        results = []
        total = len(skill_files)

        # Create progress bar
        pbar = None
        if TQDM_AVAILABLE:
            pbar = tqdm(total=total, desc="Generating", unit="skill")
        else:
            print(f"Starting generation for {total} skills...")

        # Ensure output directory exists
        output_dir = Path(self._security_config.output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        # Process each skill sequentially (generate one, save one)
        for i, skill_file in enumerate(skill_files):
            skill_name = skill_file.parent.name

            # Generate single skill
            result = await self._generate_single_input(skill_file)

            # Save result immediately
            await self._save_single_result(result, output_dir)

            results.append(result)

            # Update progress bar
            if pbar:
                pbar.update(1)
                pbar.set_postfix(
                    {
                        "Success": sum(1 for r in results if r.success),
                        "Failed": sum(1 for r in results if not r.success),
                    }
                )
            else:
                print(f"[{i + 1}/{total}] {skill_name}: {'OK' if result.success else 'FAIL'}")

            # Delay between requests (avoid rate limiting)
            if i < total - 1:  # Not the last request
                await asyncio.sleep(self._security_config.request_delay)

        # Close progress bar
        if pbar:
            pbar.close()

        return results

    async def _generate_single_input(self, skill_file: Path) -> TestInputResult:
        """Generate test input for a single skill

        Args:
            skill_file: Skill file path

        Returns:
            Test input result
        """
        skill_name = skill_file.parent.name

        try:
            # Read skill content
            skill_content = skill_file.read_text(encoding="utf-8")

            # Parse frontmatter
            frontmatter = self._parse_frontmatter(skill_content)

            # Scan supporting files (new)
            supporting_files_info = self._scan_supporting_files(skill_file, skill_name)

            # Build prompt
            prompt = self._build_prompt(skill_content, frontmatter, supporting_files_info)
        except Exception as e:
            return TestInputResult(
                skill_name=skill_name,
                instruction="",
                supporting_files={},
                success=False,
                error=f"Preparation error: {e}",
            )

        # Call LLM
        try:
            response = await self._call_llm(prompt)
        except Exception as e:
            return TestInputResult(
                skill_name=skill_name,
                instruction="",
                supporting_files={},
                success=False,
                error=str(e),
            )

        # Parse response
        try:
            data = self._parse_llm_response(response)
        except Exception as e:
            return TestInputResult(
                skill_name=skill_name,
                instruction="",
                supporting_files={},
                success=False,
                error=f"Failed to parse response: {e}",
            )

        # Validate instruction format
        if not self._validate_instruction(data.get("instruction", ""), skill_name):
            return TestInputResult(
                skill_name=skill_name,
                instruction=data.get("instruction", ""),
                supporting_files=data.get("supporting_files", {}),
                success=False,
                error="Instruction format validation failed",
            )

        return TestInputResult(
            skill_name=skill_name,
            instruction=data.get("instruction", ""),
            supporting_files=data.get("supporting_files", {}),
            success=True,
            error=None,
        )

    def _parse_frontmatter(self, content: str) -> dict[str, Any]:
        """Parse YAML frontmatter

        Args:
            content: Skill file content

        Returns:
            Frontmatter data
        """
        import yaml

        frontmatter = {}

        # Extract YAML frontmatter
        match = re.match(r"^---\n(.*?)\n---", content, re.DOTALL)
        if match:
            yaml_content = match.group(1)
            try:
                frontmatter = yaml.safe_load(yaml_content) or {}
            except yaml.YAMLError:
                pass

        # Set default values
        frontmatter.setdefault("name", "Unknown Skill")
        frontmatter.setdefault("description", "")

        return frontmatter

    def _build_prompt(
        self,
        skill_content: str,
        frontmatter: dict[str, Any],
        supporting_files_info: str = "",
    ) -> str:
        """Build LLM prompt

        Args:
            skill_content: Skill content
            frontmatter: Frontmatter data
            supporting_files_info: Supporting files info string (optional)

        Returns:
            Complete prompt
        """
        from src.infrastructure.llm.prompt_templates import SECURITY_TEST_INPUT_PROMPT

        # Extract key information
        skill_name = frontmatter.get("name", "Unknown Skill")
        description = frontmatter.get("description", "")

        # Extract overview section (from main content)
        overview = self._extract_section(skill_content, "Overview")

        # Extract When to Use section
        when_to_use = self._extract_section(skill_content, "When to Use") or frontmatter.get(
            "Use when", ""
        )

        # Extract Examples section (first 500 characters)
        examples = self._extract_section(skill_content, "Examples") or ""
        examples = examples[:500] if examples else "See skill documentation"

        return SECURITY_TEST_INPUT_PROMPT.format(
            skill_name=skill_name,
            description=description[:200],
            overview=overview[:300],
            when_to_use=when_to_use[:200],
            examples=examples,
            supporting_files_info=supporting_files_info,
        )

    def _extract_section(self, content: str, section_name: str) -> str:
        """Extract specific section from content

        Args:
            content: Full content
            section_name: Section name

        Returns:
            Section content
        """
        # Remove frontmatter
        content = re.sub(r"^---\n.*?\n---\n", "", content, flags=re.DOTALL)

        # Escape special characters in section_name
        escaped_name = re.escape(section_name)

        # Try matching heading format (simplified pattern, avoid complex lookahead)
        # Pattern1: ## Section Name\n...content...\n(next heading or end)
        pattern1 = rf"## {escaped_name}\s*\n(.*?)(?=\n##|\Z)"
        try:
            match = re.search(pattern1, content, re.DOTALL)
            if match:
                return match.group(1).strip()
        except re.error:
            pass  # Pattern invalid, try next

        # Pattern2: ### Section Name\n...content...\n(next heading or end)
        pattern2 = rf"### {escaped_name}\s*\n(.*?)(?=\n##|\Z)"
        try:
            match = re.search(pattern2, content, re.DOTALL)
            if match:
                return match.group(1).strip()
        except re.error:
            pass

        return ""

    async def _call_llm(self, prompt: str) -> str:
        """Call LLM

        Args:
            prompt: Prompt

        Returns:
            LLM response
        """
        # Use synchronous call (zai-sdk is synchronous)
        response = await asyncio.to_thread(self._sync_llm_call, prompt)
        return response

    def _sync_llm_call(self, prompt: str) -> str:
        """Synchronous LLM call

        Args:
            prompt: Prompt

        Returns:
            Response text
        """
        response = self._llm_client._client.chat.completions.create(
            model=self._security_config.llm_model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.7,
            max_tokens=2048,
        )

        return response.choices[0].message.content

    def _parse_llm_response(self, response: str) -> dict[str, Any]:
        """Parse LLM response

        Args:
            response: LLM response text

        Returns:
            Parsed data
        """
        # Clean response
        response = response.strip()

        # First try parsing JSON in markdown code block (most common case)
        code_block_pattern = r"```(?:json)?\s*\n?(.*?)\n?```"
        match = re.search(code_block_pattern, response, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(1).strip())
            except json.JSONDecodeError:
                pass  # Continue trying other methods

        # Try parsing entire response directly
        try:
            return json.loads(response)
        except json.JSONDecodeError:
            pass

        # Try finding {...} format JSON (non-greedy match)
        # Use brace matching to find complete JSON objects
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

    def _validate_instruction(self, instruction: str, skill_name: str) -> bool:
        """Validate instruction format

        Args:
            instruction: Instruction text
            skill_name: Skill name

        Returns:
            Whether valid
        """
        if not instruction:
            return False

        # Check length (15-50 words)
        words = instruction.split()
        word_count = len(words)
        if word_count < 15 or word_count > 50:  # Slightly wider range
            return False

        # Check prefix format
        expected_prefix = f"Please use the {skill_name} skill to"
        if not instruction.startswith(expected_prefix):
            return False

        return True

    async def _save_single_result(self, result: TestInputResult, output_dir: Path) -> None:
        """Save single result immediately

        Args:
            result: Test input result
            output_dir: Output directory
        """
        skill_dir = output_dir / result.skill_name
        skill_dir.mkdir(parents=True, exist_ok=True)

        # Save instruction.md
        instruction_file = skill_dir / "instruction.md"
        instruction_file.write_text(result.instruction, encoding="utf-8")

        # Save supporting files
        for filename, content in result.supporting_files.items():
            file_path = skill_dir / filename
            file_path.write_text(content, encoding="utf-8")

    async def _save_results(self, results: list[TestInputResult]) -> None:
        """Save generation results (batch save, deprecated but kept for compatibility)

        Args:
            results: List of generation results
        """
        output_dir = Path(self._security_config.output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        for result in results:
            skill_dir = output_dir / result.skill_name
            skill_dir.mkdir(parents=True, exist_ok=True)

            # Save instruction.md
            instruction_file = skill_dir / "instruction.md"
            instruction_file.write_text(result.instruction, encoding="utf-8")

            # Save supporting files
            for filename, content in result.supporting_files.items():
                file_path = skill_dir / filename
                file_path.write_text(content, encoding="utf-8")

    async def _save_metadata(
        self, suite: GeneratedTestSuite, results: list[TestInputResult]
    ) -> None:
        """Save metadata

        Args:
            suite: Test suite
            results: List of generation results
        """
        output_dir = Path(self._security_config.output_dir)
        metadata_file = output_dir / "generation_metadata.json"

        metadata = {
            "suite_id": suite.suite_id,
            "generation_strategy": suite.generation_strategy,
            "generated_at": suite.generated_at.isoformat(),
            "metadata": suite.metadata,
            "skills": [
                {
                    "skill_name": r.skill_name,
                    "success": r.success,
                    "error": r.error,
                    "instruction": r.instruction if r.success else None,
                    "supporting_files": list(r.supporting_files.keys()) if r.success else [],
                }
                for r in results
            ],
        }

        metadata_file.write_text(
            json.dumps(metadata, indent=2, ensure_ascii=False), encoding="utf-8"
        )

    def _scan_supporting_files(self, skill_file: Path, skill_name: str) -> str:
        """Scan supporting files in skill directory

        Args:
            skill_file: Skill file path
            skill_name: Skill name

        Returns:
            Formatted supporting file information string
        """
        # Lazy initialize scanner
        if self._scanner is None:
            from .instruction_file_scanner import InstructionFileScanner

            self._scanner = InstructionFileScanner()

        # Check if supporting files exist for this skill in output directory
        output_dir = Path(self._security_config.output_dir)
        skill_dir = output_dir / skill_name

        if not skill_dir.exists():
            # If output directory doesn't exist, return empty info
            return "**Available Supporting Files:**\n\nNo supporting files available."

        # Scan supporting files
        supporting_files = self._scanner.get_supporting_files(skill_dir)

        if not supporting_files:
            return "**Available Supporting Files:**\n\nNo supporting files available."

        # Format file list
        return self._scanner.format_file_list(supporting_files)
