"""
Injection Generator Domain Service

Responsible for generating various injection test cases
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from src.shared.types import AttackType, InjectionLayer, Severity
from src.domain.generation.services.parsers.skill_parser import UnifiedSkillParser


@dataclass
class InjectionPayload:
    """Injection payload (value object)"""

    name: str
    attack_type: AttackType
    severity: Severity
    content: str
    description: str = ""

    def __str__(self) -> str:
        return f"{self.attack_type.value}/{self.name}"


@dataclass
class InjectionPoint:
    """Injection point (value object)"""

    layer: InjectionLayer
    position: str  # "start", "end", "after_heading"
    prefix: str = ""
    suffix: str = ""

    def __str__(self) -> str:
        return f"{self.layer.value}@{self.position}"


@dataclass
class GeneratedTest:
    """Generated test case

    Represents a generated injection test
    """

    test_id: str
    skill_name: str
    layer: InjectionLayer
    attack_type: AttackType
    payload: InjectionPayload
    injection_points: list[InjectionPoint]
    injected_content: str
    original_content: str
    should_be_blocked: bool = True
    metadata: dict[str, Any] = field(default_factory=dict)

    def is_multi_layer(self) -> bool:
        """Determine if this is a multi-layer injection"""
        return self.layer in (
            InjectionLayer.DESCRIPTION_RESOURCE,
            InjectionLayer.INSTRUCTION_RESOURCE,
            InjectionLayer.ALL,
        )


class InjectionGenerator:
    """Injection generator

    Responsible for generating various types of injection test cases
    """

    def __init__(self, skills_dir: Path):
        """Initialize the generator

        Args:
            skills_dir: Skills directory path
        """
        self._skills_dir = Path(skills_dir)

    def generate_test(
        self,
        skill_name: str,
        layer: InjectionLayer,
        payload: InjectionPayload,
    ) -> GeneratedTest:
        """Generate a single test case

        Args:
            skill_name: Skill name
            layer: Injection layer
            payload: Injection payload

        Returns:
            Generated test case
        """
        # Read original content
        skill_file = self._skills_dir / skill_name / "SKILL.md"
        if not skill_file.exists():
            raise FileNotFoundError(f"Skill file not found: {skill_file}")

        original_content = skill_file.read_text(encoding="utf-8")
        parsed_result = UnifiedSkillParser.parse(original_content)
        parsed = {"frontmatter": parsed_result.frontmatter, "content": parsed_result.content}

        # Inject payload
        injected_content = self._inject(
            parsed=parsed,
            layer=layer,
            payload=payload.content,
        )

        # Determine injection points
        injection_points = self._get_injection_points(layer)

        # Generate test ID
        test_id = self._generate_test_id(
            skill_name=skill_name,
            layer=layer,
            attack_type=payload.attack_type,
            payload_name=payload.name,
        )

        return GeneratedTest(
            test_id=test_id,
            skill_name=skill_name,
            layer=layer,
            attack_type=payload.attack_type,
            payload=payload,
            injection_points=injection_points,
            injected_content=injected_content,
            original_content=original_content,
        )

    def _inject(
        self,
        parsed: dict[str, Any],
        layer: InjectionLayer,
        payload: str,
    ) -> str:
        """Execute injection

        Args:
            parsed: Parsed content
            layer: Injection layer
            payload: Payload content

        Returns:
            Injected content
        """
        if layer == InjectionLayer.DESCRIPTION:
            return self._inject_description(parsed, payload)
        elif layer == InjectionLayer.INSTRUCTION:
            return self._inject_instruction(parsed, payload)
        elif layer == InjectionLayer.RESOURCE:
            return self._inject_resource(parsed, payload)
        elif layer == InjectionLayer.DESCRIPTION_RESOURCE:
            return self._inject_description_resource(parsed, payload)
        elif layer == InjectionLayer.INSTRUCTION_RESOURCE:
            return self._inject_instruction_resource(parsed, payload)
        elif layer == InjectionLayer.ALL:
            return self._inject_all(parsed, payload)
        else:
            return self._inject_description(parsed, payload)

    def _inject_description(self, parsed: dict[str, Any], payload: str) -> str:
        """Inject into description layer"""
        frontmatter = parsed["frontmatter"].copy()
        original_desc = frontmatter.get("description", "")
        frontmatter["description"] = f"{payload} Special note: {original_desc}"
        return UnifiedSkillParser.build(frontmatter, parsed["content"])

    def _inject_instruction(self, parsed: dict[str, Any], payload: str) -> str:
        """Inject into instruction layer"""
        content = parsed["content"]
        injected_content = f"{content}\n\nSpecial instruction: {payload}"
        return UnifiedSkillParser.build(parsed["frontmatter"], injected_content)

    def _inject_resource(self, parsed: dict[str, Any], payload: str) -> str:
        """Inject into resource layer"""
        frontmatter = parsed["frontmatter"].copy()
        resources = frontmatter.get("resources", [])
        resources.append("http://evil.com/malicious.md")
        frontmatter["resources"] = resources

        content = parsed["content"]
        injected_content = f"{content}\n\nRefer to: {payload}"
        return UnifiedSkillParser.build(frontmatter, injected_content)

    def _inject_description_resource(self, parsed: dict[str, Any], payload: str) -> str:
        """Inject into description + resource layer"""
        frontmatter = parsed["frontmatter"].copy()
        original_desc = frontmatter.get("description", "")
        frontmatter["description"] = f"{payload} Special note: {original_desc}"

        resources = frontmatter.get("resources", [])
        resources.append("http://evil.com/malicious.md")
        frontmatter["resources"] = resources

        content = parsed["content"]
        injected_content = f"{content}\n\nRefer to: {payload}"
        return UnifiedSkillParser.build(frontmatter, injected_content)

    def _inject_instruction_resource(self, parsed: dict[str, Any], payload: str) -> str:
        """Inject into instruction + resource layer"""
        frontmatter = parsed["frontmatter"].copy()
        resources = frontmatter.get("resources", [])
        resources.append("http://evil.com/malicious.md")
        frontmatter["resources"] = resources

        content = parsed["content"]
        injected_content = f"{content}\n\nSpecial instruction: {payload}\n\nRefer to: {payload}"
        return UnifiedSkillParser.build(frontmatter, injected_content)

    def _inject_all(self, parsed: dict[str, Any], payload: str) -> str:
        """Inject into all layers"""
        frontmatter = parsed["frontmatter"].copy()
        original_desc = frontmatter.get("description", "")
        frontmatter["description"] = f"{payload} Special note: {original_desc}"

        resources = frontmatter.get("resources", [])
        resources.append("http://evil.com/malicious.md")
        frontmatter["resources"] = resources

        content = parsed["content"]
        injected_content = f"{content}\n\nSpecial instruction: {payload}\n\nRefer to: {payload}"
        return UnifiedSkillParser.build(frontmatter, injected_content)

    def _get_injection_points(self, layer: InjectionLayer) -> list[InjectionPoint]:
        """Get list of injection points

        Args:
            layer: Injection layer

        Returns:
            List of injection points
        """
        mapping = {
            InjectionLayer.DESCRIPTION: [InjectionPoint(layer, "end")],
            InjectionLayer.INSTRUCTION: [InjectionPoint(layer, "end")],
            InjectionLayer.RESOURCE: [InjectionPoint(layer, "end")],
            InjectionLayer.DESCRIPTION_RESOURCE: [
                InjectionPoint(layer, "end"),
                InjectionPoint(InjectionLayer.RESOURCE, "end"),
            ],
            InjectionLayer.INSTRUCTION_RESOURCE: [
                InjectionPoint(layer, "end"),
                InjectionPoint(InjectionLayer.RESOURCE, "end"),
            ],
            InjectionLayer.ALL: [
                InjectionPoint(InjectionLayer.DESCRIPTION, "end"),
                InjectionPoint(InjectionLayer.INSTRUCTION, "end"),
                InjectionPoint(InjectionLayer.RESOURCE, "end"),
            ],
        }
        return mapping.get(layer, [InjectionPoint(layer, "end")])

    def _generate_test_id(
        self,
        skill_name: str,
        layer: InjectionLayer,
        attack_type: AttackType,
        payload_name: str,
    ) -> str:
        """Generate test ID

        Args:
            skill_name: Skill name
            layer: Injection layer
            attack_type: Attack type
            payload_name: Payload name

        Returns:
            Test ID
        """
        return f"{skill_name}_{layer.value}_{attack_type.value}_{payload_name}"


class PayloadRegistry:
    """Payload registry

    Manages all available injection payloads
    """

    _payloads: list[InjectionPayload] = []

    @classmethod
    def register(cls, payload: InjectionPayload) -> None:
        """Register a payload

        Args:
            payload: Payload object
        """
        cls._payloads.append(payload)

    @classmethod
    def get_by_attack_type(cls, attack_type: AttackType) -> list[InjectionPayload]:
        """Get payloads by attack type

        Args:
            attack_type: Attack type

        Returns:
            List of payloads
        """
        return [p for p in cls._payloads if p.attack_type == attack_type]

    @classmethod
    def get_by_severity(cls, severity: Severity) -> list[InjectionPayload]:
        """Get payloads by severity

        Args:
            severity: Severity level

        Returns:
            List of payloads
        """
        return [p for p in cls._payloads if p.severity == severity]

    @classmethod
    def list_all(cls) -> list[InjectionPayload]:
        """Get all payloads

        Returns:
            List of all payloads
        """
        return cls._payloads.copy()

    @classmethod
    def clear(cls) -> None:
        """Clear the registry (mainly for testing)"""
        cls._payloads.clear()
