"""
Test Case Validator

Provides validation functionality for test case directories, including:
- Directory existence checks
- Metadata file validation
- Test case completeness checks
- Statistics reporting
"""

import json
from pathlib import Path
from dataclasses import dataclass, field
from typing import Any

from .paths import get_test_dir, get_test_metadata_path
from src.shared.types import InjectionLayer


@dataclass
class ValidationResult:
    """Validation result."""

    is_valid: bool
    test_dir: str
    exists: bool = False
    has_metadata: bool = False
    metadata_valid: bool = False
    missing_layers: list[str] = field(default_factory=list)
    missing_metadata_fields: list[str] = field(default_factory=list)
    total_tests: int = 0
    tests_by_layer: dict[str, int] = field(default_factory=dict)
    tests_by_attack_type: dict[str, int] = field(default_factory=dict)
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "is_valid": self.is_valid,
            "test_dir": self.test_dir,
            "exists": self.exists,
            "has_metadata": self.has_metadata,
            "metadata_valid": self.metadata_valid,
            "missing_layers": self.missing_layers,
            "missing_metadata_fields": self.missing_metadata_fields,
            "total_tests": self.total_tests,
            "tests_by_layer": self.tests_by_layer,
            "tests_by_attack_type": self.tests_by_attack_type,
            "errors": self.errors,
            "warnings": self.warnings,
        }

    def format_report(self) -> str:
        """Format validation report."""
        lines = []
        lines.append("=" * 60)
        lines.append("Test Case Validation Report")
        lines.append("=" * 60)
        lines.append(f"Test directory: {self.test_dir}")
        lines.append(f"Validation status: {'Passed' if self.is_valid else 'Failed'}")
        lines.append("")

        if self.exists:
            lines.append("Directory structure:")
            lines.append("  - Directory exists: Yes")
            lines.append(f"  - Metadata file: {'Exists' if self.has_metadata else 'Missing'}")

            if self.has_metadata:
                lines.append(f"  - Metadata format: {'Valid' if self.metadata_valid else 'Invalid'}")
            lines.append("")

            if self.total_tests > 0:
                lines.append(f"Total test cases: {self.total_tests}")
                lines.append("")
                lines.append("Distribution by injection layer:")
                for layer, count in self.tests_by_layer.items():
                    lines.append(f"  - {layer}: {count}")
                lines.append("")

                if self.tests_by_attack_type:
                    lines.append("Distribution by attack type:")
                    for attack_type, count in self.tests_by_attack_type.items():
                        lines.append(f"  - {attack_type}: {count}")
                    lines.append("")

            if self.missing_layers:
                lines.append("Missing injection layers:")
                for layer in self.missing_layers:
                    lines.append(f"  - {layer}")
                lines.append("")

            if self.warnings:
                lines.append("Warnings:")
                for warning in self.warnings:
                    lines.append(f"  - {warning}")
                lines.append("")

            if self.errors:
                lines.append("Errors:")
                for error in self.errors:
                    lines.append(f"  - {error}")
                lines.append("")
        else:
            lines.append("Error: Test directory does not exist")
            lines.append("")
            lines.append("Hint: Please generate test cases first:")
            lines.append("  python generate_tests.py")
            lines.append("  or:")
            lines.append("  python generate_tests.py --output tests/v1")

        lines.append("=" * 60)
        return "\n".join(lines)


class TestValidator:
    """Test case validator."""

    def __init__(self, test_dir: str | None = None, version: str | None = None):
        """
        Initialize validator.

        Args:
            test_dir: Custom test directory path
            version: Version suffix (e.g., "v1")
        """
        self.test_dir_path = get_test_dir(test_dir, version)
        self.metadata_path = get_test_metadata_path(test_dir, version)

    def validate(self) -> ValidationResult:
        """
        Validate test case directory.

        Returns:
            ValidationResult validation result
        """
        result = ValidationResult(
            is_valid=False,
            test_dir=str(self.test_dir_path),
        )

        # Check if directory exists
        if not self.test_dir_path.exists():
            result.errors.append(f"Test directory does not exist: {self.test_dir_path}")
            return result

        result.exists = True

        # Check metadata file
        if not self.metadata_path.exists():
            result.warnings.append(f"Metadata file does not exist: {self.metadata_path}")
            # Continue checking directory structure
            self._scan_directory_structure(result)
        else:
            result.has_metadata = True
            metadata_valid, metadata, errors = self._validate_metadata()
            result.metadata_valid = metadata_valid
            result.errors.extend(errors)

            if metadata_valid:
                result.total_tests = metadata.get("total_tests", 0)
                result.tests_by_layer = metadata.get("by_layer", {})
                result.tests_by_attack_type = metadata.get("by_attack_type", {})

                # Check for missing layers
                expected_layers = {layer.value for layer in InjectionLayer}
                actual_layers = set(result.tests_by_layer.keys())
                result.missing_layers = list(expected_layers - actual_layers)

        # Check directory structure
        self._scan_directory_structure(result)

        # Determine overall validity
        result.is_valid = result.exists and (not result.errors or result.metadata_valid)

        return result

    def _validate_metadata(self) -> tuple[bool, dict, list[str]]:
        """
        Validate metadata file.

        Returns:
            (is_valid, metadata_dict, errors)
        """
        errors = []

        try:
            with open(self.metadata_path, "r", encoding="utf-8") as f:
                metadata = json.load(f)

            # Check required fields
            required_fields = ["total_tests", "by_layer", "by_attack_type", "tests"]
            missing_fields = [f for f in required_fields if f not in metadata]

            if missing_fields:
                errors.append(f"Metadata missing fields: {', '.join(missing_fields)}")
                return False, {}, errors

            # Validate total_tests matches tests list length
            if metadata["total_tests"] != len(metadata.get("tests", [])):
                errors.append(
                    f"total_tests ({metadata['total_tests']}) "
                    f"does not match tests list length ({len(metadata.get('tests', []))})"
                )

            return len(errors) == 0, metadata, errors

        except json.JSONDecodeError as e:
            errors.append(f"Metadata JSON format error: {e}")
            return False, {}, errors
        except Exception as e:
            errors.append(f"Failed to read metadata file: {e}")
            return False, {}, errors

    def _scan_directory_structure(self, result: ValidationResult) -> None:
        """
        Scan directory structure, count actual test cases.

        Args:
            result: Validation result object (modified in place)
        """
        actual_count = 0
        actual_by_layer = {layer.value: 0 for layer in InjectionLayer}

        for layer in InjectionLayer:
            layer_dir = self.test_dir_path / layer.value
            if layer_dir.exists():
                # Count SKILL.md files
                skill_files = list(layer_dir.glob("*/SKILL.md"))
                actual_count += len(skill_files)
                actual_by_layer[layer.value] = len(skill_files)

        # If metadata doesn't exist or is invalid, use actual scan results
        if not result.metadata_valid:
            result.total_tests = actual_count
            result.tests_by_layer = actual_by_layer

        # Check consistency between metadata and actual directory
        if result.metadata_valid and result.total_tests != actual_count:
            result.warnings.append(
                f"Metadata records {result.total_tests} tests, actually found {actual_count} test files"
            )

    def print_report(self) -> None:
        """Print validation report."""
        result = self.validate()
        print(result.format_report())


def validate_test_dir(test_dir: str | None = None, version: str | None = None) -> bool:
    """
    Shortcut function to validate test case directory.

    Args:
        test_dir: Custom test directory
        version: Version suffix

    Returns:
        bool Whether validation passed
    """
    validator = TestValidator(test_dir, version)
    result = validator.validate()
    validator.print_report()
    return result.is_valid


def find_test_dirs() -> list[Path]:
    """
    Find all available test case directories.

    Returns:
        List of test directories (only those actually containing security test cases)
    """
    base_dir = Path(__file__).parent.parent

    def is_valid_test_dir(d: Path) -> bool:
        """Check if directory is a valid security test case directory."""
        # Must exist
        if not d.is_dir():
            return False
        # Exclude pytest test directories (containing .py test files)
        if any(d.glob("test_*.py")):
            return False
        # Check if has test_metadata.json or test subdirectories
        if (d / "test_metadata.json").exists():
            return True
        # Check if has test subdirectories
        for layer in ("description", "instruction", "resource"):
            if (d / layer).is_dir():
                return True
        return False

    # Possible test directory locations
    possible_dirs = [
        base_dir / "generated_tests",
        base_dir / "data" / "generated_tests",
    ]

    # Check if there are versioned directories under tests/ (exclude tests/ itself, it's a pytest directory)
    tests_root = base_dir / "tests"
    if tests_root.exists():
        for subdir in tests_root.iterdir():
            if subdir.is_dir() and not subdir.name.startswith("_") and subdir.name != "__pycache__":
                possible_dirs.append(subdir)

    # Only return valid test directories
    return [d for d in possible_dirs if is_valid_test_dir(d)]


def print_available_test_dirs() -> None:
    """Print all available test case directories."""
    test_dirs = find_test_dirs()

    print("Available test case directories:")
    if not test_dirs:
        print("  (none)")
        print("")
        print("Hint: Please generate test cases first:")
        print("  python generate_tests.py")
        return

    for d in test_dirs:
        # Try to get relative path
        try:
            rel_path = d.relative_to(Path.cwd())
        except ValueError:
            rel_path = d

        # Check if has metadata
        metadata_file = d / "test_metadata.json"
        has_metadata = metadata_file.exists()

        if has_metadata:
            try:
                with open(metadata_file) as f:
                    metadata = json.load(f)
                count = metadata.get("total_tests", "?")
                print(f"  - {rel_path} ({count} tests)")
            except Exception:
                print(f"  - {rel_path} (metadata corrupted)")
        else:
            print(f"  - {rel_path} (no metadata)")
