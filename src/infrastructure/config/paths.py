"""
Unified Path Management

Provides unified management of project-related paths, supports environment variable overrides.
"""

import os
from pathlib import Path


def get_project_paths() -> dict[str, str]:
    """
    Get project-related paths.

    Prioritizes environment variables, otherwise uses default paths relative to src directory.

    Returns:
        Dictionary containing various project paths
    """
    base_dir = Path(__file__).parent.parent

    return {
        "base_dir": str(base_dir),
        "test_dir": os.getenv("SECURITY_TEST_DIR", str(base_dir / "generated_tests")),
        "output_dir": os.getenv("EXPERIMENT_OUTPUT_DIR", str(base_dir / "experiment_results")),
        "report_path": os.getenv(
            "SECURITY_CLAUDE_TEST_REPORT",
            str(base_dir / "reports" / "claude_code_test_report.json"),
        ),
        "skills_from_skill0_dir": os.getenv(
            "SKILLS_FROM_SKILL0_DIR", str(base_dir / "data" / "skills_from_skill0")
        ),
        "skills_instructions_dir": os.getenv(
            "SKILLS_INSTRUCTIONS_DIR", str(base_dir / "data" / "skills_instructions")
        ),
        # Test data file paths
        "test_data_env_file": os.getenv("TEST_DATA_ENV_FILE", str(base_dir / "data" / ".env")),
        "test_data_main_py": os.getenv("TEST_DATA_MAIN_PY", str(base_dir / "data" / "main.py")),
    }


def get_test_dir(test_dir: str | None = None, version: str | None = None) -> Path:
    """
    Get test case directory path, supports versioned paths.

    Args:
        test_dir: Custom test directory (absolute or relative path)
        version: Version suffix (e.g., "v1" creates tests/v1/)

    Returns:
        Path object for test case directory

    Examples:
        >>> get_test_dir()  # Default path
        Path(.../generated_tests)
        >>> get_test_dir(version="v1")  # Versioned path
        Path(.../tests/v1)
        >>> get_test_dir(test_dir="custom/tests")  # Custom path
        Path(.../custom/tests)
    """
    base_dir = Path(__file__).parent.parent

    if test_dir:
        test_path = Path(test_dir)
        # If relative path, relative to base_dir
        if not test_path.is_absolute():
            test_path = base_dir / test_path
        return test_path

    if version:
        # Versioned path: tests/{version}/
        return base_dir / "tests" / version

    # Default path
    return base_dir / "generated_tests"


def get_test_metadata_path(test_dir: str | None = None, version: str | None = None) -> Path:
    """
    Get test metadata file path.

    Args:
        test_dir: Custom test directory
        version: Version suffix

    Returns:
        Path object for test_metadata.json file
    """
    return get_test_dir(test_dir, version) / "test_metadata.json"
