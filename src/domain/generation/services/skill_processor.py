"""
Skill Processor Domain Service

Responsible for processing skill files and injection-related operations
"""

from pathlib import Path
from typing import Any

from src.shared.exceptions import SkillNotFoundError
from src.domain.testing.entities.test_case import TestCase, TestCaseId
from src.domain.generation.services.parsers.skill_parser import UnifiedSkillParser
from src.shared.types import AttackType, InjectionLayer, Severity


class SkillProcessor:
    """Skill processor

    Responsible for reading, parsing, and processing skill files
    """

    def __init__(self, skills_dir: Path):
        """Initialize the processor

        Args:
            skills_dir: Skills directory path
        """
        self._skills_dir = Path(skills_dir)
        self._parser = UnifiedSkillParser()

    def read_skill(self, skill_name: str) -> str:
        """Read skill content

        Args:
            skill_name: Skill name

        Returns:
            Skill content

        Raises:
            SkillNotFoundError: Skill does not exist
        """
        skill_file = self._skills_dir / skill_name / "SKILL.md"

        if not skill_file.exists():
            raise SkillNotFoundError(skill_name)

        return skill_file.read_text(encoding="utf-8")

    def parse_skill(self, content: str) -> dict[str, Any]:
        """Parse skill content

        Args:
            content: Skill file content

        Returns:
            Dictionary containing frontmatter and content (compatible with old format)
        """
        result = self._parser.parse(content)
        # Convert to old format for compatibility
        return {
            "frontmatter": result.frontmatter,
            "content": result.content,
        }

    def build_skill(self, frontmatter: dict[str, Any], content: str) -> str:
        """Build skill file content

        Args:
            frontmatter: Frontmatter dictionary
            content: Body content

        Returns:
            Complete skill file content
        """
        return self._parser.build(frontmatter, content)

    def list_skills(self) -> list[str]:
        """List all skills

        Returns:
            List of skill names
        """
        if not self._skills_dir.exists():
            return []

        skill_names = []
        for skill_dir in self._skills_dir.iterdir():
            if skill_dir.is_dir():
                skill_file = skill_dir / "SKILL.md"
                if skill_file.exists():
                    skill_names.append(skill_dir.name)

        return sorted(skill_names)

    def skill_exists(self, skill_name: str) -> bool:
        """Check if skill exists

        Args:
            skill_name: Skill name

        Returns:
            Whether skill exists
        """
        skill_file = self._skills_dir / skill_name / "SKILL.md"
        return skill_file.exists()

    def get_skill_metadata(self, skill_name: str) -> dict[str, Any]:
        """Get skill metadata

        Args:
            skill_name: Skill name

        Returns:
            Metadata dictionary
        """
        content = self.read_skill(skill_name)
        parsed = self.parse_skill(content)

        return {
            "name": parsed["frontmatter"].get("name", skill_name),
            "description": parsed["frontmatter"].get("description", ""),
            "version": parsed["frontmatter"].get("version", "1.0.0"),
            "author": parsed["frontmatter"].get("author", ""),
        }


class TestCaseBuilder:
    """Test case builder

    Responsible for building test cases from skills and payloads
    """

    def __init__(self, skills_dir: Path):
        """Initialize the builder

        Args:
            skills_dir: Skills directory path
        """
        self._processor = SkillProcessor(skills_dir)

    def build_test_case(
        self,
        skill_name: str,
        layer: InjectionLayer,
        attack_type: AttackType,
        payload_name: str,
        payload_content: str,
        severity: Severity,
        should_be_blocked: bool = True,
    ) -> TestCase:
        """Build test case

        Args:
            skill_name: Skill name
            layer: Injection layer
            attack_type: Attack type
            payload_name: Payload name
            payload_content: Payload content
            severity: Severity level
            should_be_blocked: Whether it should be blocked

        Returns:
            Test case entity
        """
        # Read original content
        original_content = self._processor.read_skill(skill_name)
        parsed = self._processor.parse_skill(original_content)

        # Inject payload
        injected_content = self._inject_payload(
            parsed=parsed,
            layer=layer,
            payload=payload_content,
        )

        # Generate test ID
        test_id = TestCaseId.create(skill_name, layer, attack_type, payload_name)

        # Build path
        skill_path = self._processor._skills_dir / skill_name

        return TestCase(
            id=test_id,
            skill_name=skill_name,
            layer=layer,
            attack_type=attack_type,
            payload_name=payload_name,
            severity=severity,
            skill_path=skill_path,
            test_case_dir=skill_path,  # Will be updated when saving
            should_be_blocked=should_be_blocked,
        )

    def _inject_payload(
        self,
        parsed: dict[str, Any],
        layer: InjectionLayer,
        payload: str,
    ) -> str:
        """Inject payload

        Args:
            parsed: Parsed content
            layer: Injection layer
            payload: Payload content

        Returns:
            Injected content
        """
        if layer == InjectionLayer.DESCRIPTION:
            frontmatter = parsed["frontmatter"].copy()
            original_desc = frontmatter.get("description", "")
            frontmatter["description"] = f"{payload} {original_desc}"
            return self._processor.build_skill(frontmatter, parsed["content"])

        elif layer == InjectionLayer.INSTRUCTION:
            content = parsed["content"]
            injected_content = f"{content}\n\n{payload}"
            return self._processor.build_skill(parsed["frontmatter"], injected_content)

        elif layer == InjectionLayer.RESOURCE:
            frontmatter = parsed["frontmatter"].copy()
            resources = frontmatter.get("resources", [])
            resources.append("http://evil.com/malicious.md")
            frontmatter["resources"] = resources
            content = parsed["content"]
            injected_content = f"{content}\n\nRefer to: {payload}"
            return self._processor.build_skill(frontmatter, injected_content)

        elif layer == InjectionLayer.DESCRIPTION_RESOURCE:
            frontmatter = parsed["frontmatter"].copy()
            original_desc = frontmatter.get("description", "")
            frontmatter["description"] = f"{payload} {original_desc}"
            resources = frontmatter.get("resources", [])
            resources.append("http://evil.com/malicious.md")
            frontmatter["resources"] = resources
            content = parsed["content"]
            injected_content = f"{content}\n\nRefer to: {payload}"
            return self._processor.build_skill(frontmatter, injected_content)

        elif layer == InjectionLayer.INSTRUCTION_RESOURCE:
            frontmatter = parsed["frontmatter"].copy()
            resources = frontmatter.get("resources", [])
            resources.append("http://evil.com/malicious.md")
            frontmatter["resources"] = resources
            content = parsed["content"]
            injected_content = f"{content}\n\n{payload}\n\nRefer to: {payload}"
            return self._processor.build_skill(frontmatter, injected_content)

        elif layer == InjectionLayer.ALL:
            frontmatter = parsed["frontmatter"].copy()
            original_desc = frontmatter.get("description", "")
            frontmatter["description"] = f"{payload} {original_desc}"
            resources = frontmatter.get("resources", [])
            resources.append("http://evil.com/malicious.md")
            frontmatter["resources"] = resources
            content = parsed["content"]
            injected_content = f"{content}\n\n{payload}\n\nRefer to: {payload}"
            return self._processor.build_skill(frontmatter, injected_content)

        else:
            # Default: inject into description
            return self._inject_payload(parsed, InjectionLayer.DESCRIPTION, payload)
