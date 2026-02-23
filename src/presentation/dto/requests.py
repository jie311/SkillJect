"""
Presentation layer DTOs (Data Transfer Objects).

Defines data transfer objects between command line interface and business layer.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from src.shared.types import AttackType, InjectionLayer, Severity


class OutputFormat(Enum):
    """Output format enumeration."""

    TEXT = "text"
    JSON = "json"
    TABLE = "table"


@dataclass
class ExperimentRequestDTO:
    """Experiment request data transfer object."""

    name: str = "security_experiment"
    description: str = ""

    # Target selection
    skill_names: list[str] = field(default_factory=list)
    attack_types: list[str] = field(default_factory=list)
    injection_layers: list[str] = field(default_factory=list)
    severities: list[str] = field(default_factory=list)

    # Execution parameters
    max_concurrency: int = 4
    timeout_seconds: int = 120
    max_tests: int | None = None

    # Output configuration
    output_dir: str = "experiment_results"
    output_format: OutputFormat = OutputFormat.TEXT
    save_reports: bool = True
    verbose: bool = False

    def to_domain_types(self) -> dict[str, Any]:
        """Convert to domain types.

        Returns:
            Dictionary containing domain types
        """
        return {
            "attack_types": [AttackType(at) for at in self.attack_types]
            if self.attack_types
            else None,
            "injection_layers": [InjectionLayer(il) for il in self.injection_layers]
            if self.injection_layers
            else None,
            "severities": [Severity(s) for s in self.severities] if self.severities else None,
        }

    def validate(self) -> list[str]:
        """Validate request.

        Returns:
            List of errors (empty list means valid)
        """
        errors = []

        if not self.name:
            errors.append("name cannot be empty")

        if self.max_concurrency < 1:
            errors.append("max_concurrency must be greater than 0")

        if self.timeout_seconds < 1:
            errors.append("timeout_seconds must be greater than 0")

        if self.attack_types:
            invalid_types = [
                at for at in self.attack_types if at not in [a.value for a in AttackType]
            ]
            if invalid_types:
                errors.append(f"Invalid attack types: {invalid_types}")

        if self.injection_layers:
            invalid_layers = [
                il for il in self.injection_layers if il not in [i.value for i in InjectionLayer]
            ]
            if invalid_layers:
                errors.append(f"Invalid injection layers: {invalid_layers}")

        return errors


@dataclass
class TestGenerationRequestDTO:
    """Test generation request data transfer object."""

    attack_types: list[str] = field(default_factory=list)
    injection_layers: list[str] = field(default_factory=list)
    severities: list[str] = field(default_factory=list)
    skill_names: list[str] = field(default_factory=list)

    # Output configuration
    output_dir: str = "generated_tests"
    format: str = "directory"  # "directory" or "single_file"

    def to_domain_types(self) -> dict[str, Any]:
        """Convert to domain types."""
        return {
            "attack_types": [AttackType(at) for at in self.attack_types]
            if self.attack_types
            else None,
            "injection_layers": [InjectionLayer(il) for il in self.injection_layers]
            if self.injection_layers
            else None,
            "severities": [Severity(s) for s in self.severities] if self.severities else None,
        }


@dataclass
class ExperimentResultDTO:
    """Experiment result data transfer object."""

    experiment_id: str
    status: str
    total_tests: int = 0
    completed_tests: int = 0
    passed_tests: int = 0
    failed_tests: int = 0
    blocked_tests: int = 0
    malicious_executions: int = 0
    pass_rate: float = 0.0
    block_rate: float = 0.0
    execution_time_seconds: float = 0.0
    output_dir: str = ""
    errors: list[str] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ExperimentResultDTO":
        """Create from dictionary.

        Args:
            data: Data dictionary

        Returns:
            Result DTO
        """
        return cls(
            experiment_id=data.get("experiment_id", ""),
            status=data.get("status", "unknown"),
            total_tests=data.get("total_tests", 0),
            completed_tests=data.get("completed_tests", 0),
            passed_tests=data.get("passed_tests", 0),
            failed_tests=data.get("failed_tests", 0),
            blocked_tests=data.get("blocked_tests", 0),
            malicious_executions=data.get("malicious_executions", 0),
            pass_rate=data.get("pass_rate", 0.0),
            block_rate=data.get("block_rate", 0.0),
            execution_time_seconds=data.get("execution_time_seconds", 0.0),
            output_dir=data.get("output_dir", ""),
            errors=data.get("errors", []),
        )


@dataclass
class TestInfoDTO:
    """Test info data transfer object."""

    test_id: str
    skill_name: str
    layer: str
    attack_type: str
    severity: str
    should_be_blocked: bool
    path: str

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "TestInfoDTO":
        """Create from dictionary.

        Args:
            data: Data dictionary

        Returns:
            Test info DTO
        """
        return cls(
            test_id=data.get("test_id", ""),
            skill_name=data.get("skill_name", ""),
            layer=data.get("layer", ""),
            attack_type=data.get("attack_type", ""),
            severity=data.get("severity", ""),
            should_be_blocked=data.get("should_be_blocked", True),
            path=data.get("path", ""),
        )


@dataclass
class IntelligentTestGenerationRequestDTO:
    """Intelligent test generation request data transfer object."""

    skill_name: str = ""
    strategy: str = "comprehensive"
    attack_types: list[str] = field(default_factory=list)
    payload: str = ""
    output_dir: str = "intelligent_tests"
    llm_provider: str = "openai"
    max_concurrency: int = 4

    # Available strategy types
    STRATEGY_CHOICES = [
        "semantic_fusion",
        "stealth_injection",
        "intent_understanding",
        "comprehensive",
    ]

    # Available LLM providers
    PROVIDER_CHOICES = ["anthropic", "openai"]

    def validate(self) -> list[str]:
        """Validate request.

        Returns:
            List of errors (empty list means valid)
        """
        errors = []

        if self.strategy not in self.STRATEGY_CHOICES:
            errors.append(f"Invalid strategy: {self.strategy}. Available: {', '.join(self.STRATEGY_CHOICES)}")

        if self.llm_provider not in self.PROVIDER_CHOICES:
            errors.append(
                f"Invalid provider: {self.llm_provider}. Available: {', '.join(self.PROVIDER_CHOICES)}"
            )

        if self.max_concurrency < 1:
            errors.append("max_concurrency must be greater than 0")

        if self.attack_types:
            valid_types = [at.value for at in AttackType]
            invalid = [at for at in self.attack_types if at not in valid_types]
            if invalid:
                errors.append(f"Invalid attack types: {invalid}")

        return errors
