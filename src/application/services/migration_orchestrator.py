"""
Migration Test Orchestrator

Implements migration test pattern: loads generated skills from final_glm_skills/,
runs tests on target models for cross-model security assessment comparison.

Core functionality:
- Load SKILL.md and metadata.json from final_glm_skills/{attack_type}/{skill_name}/
- Convert to TestCase entities
- Execute tests using SandboxTestRunner
- Preserve automatic retry mechanism for infrastructure errors
- Save results to experiment_results_{target_model}/

Directory structure comparison:
Source directory (read):
  final_glm_skills/
  ├── backdoor_injection/
  │   ├── adaptyv/
  │   │   ├── SKILL.md
  │   │   ├── metadata.json
  │   │   └── resources/

Target directory (write):
  experiment_results_claude/
  ├── test_details/
  │   └── migration/              # Strategy name
  │       └── skills_sample/      # Dataset name
  │           └── {skill_name}/
  │               └── {attack_type}/
  │                   └── run_0/  # Run once, use run_0
  │                       ├── SKILL.md      # Copied from source
  │                       ├── metadata.json # Copied from source
  │                       ├── resources/    # Copied from source
  │                       ├── result.json   # Newly generated
  │                       ├── tool_calls.json
  │                       └── raw_logs.txt
  └── migration_result.json
"""

import asyncio
import json
import logging
import shutil
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from src.domain.testing.entities.test_case import (
    TestCase,
    TestCaseId,
    TestResult,
)
from src.domain.testing.services.sandbox_test_runner import SandboxTestRunner
from src.domain.testing.value_objects.execution_config import TwoPhaseExecutionConfig
from src.shared.types import AttackType, InjectionLayer, Severity

logger = logging.getLogger(__name__)


@dataclass
class MigrationProgress:
    """Migration processing progress

    Tracks real-time progress of migration test processing
    """

    total_tests: int = 0
    total_loaded: int = 0
    total_executed: int = 0
    total_succeeded: int = 0  # Number of blocked tests (defense successful)
    total_failed: int = 0  # Number of maliciously executed tests (attack successful)
    total_determined: int = 0  # Number of tests with clear results (succeeded + failed)
    total_skipped: int = 0  # Number of skipped tests (results already exist)
    current_skill: str = ""
    current_attack_type: str = ""
    message: str = ""

    @property
    def success_rate(self) -> float:
        """Calculate defense success rate (based on tests with clear results)

        Returns:
            Success rate (0-1), 0 means all tests bypassed, 1 means all tests blocked
        """
        if self.total_determined == 0:
            return 0.0
        return self.total_succeeded / self.total_determined

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary"""
        return {
            "total_tests": self.total_tests,
            "total_loaded": self.total_loaded,
            "total_executed": self.total_executed,
            "total_succeeded": self.total_succeeded,
            "total_failed": self.total_failed,
            "total_determined": self.total_determined,
            "total_skipped": self.total_skipped,
            "success_rate": self.success_rate,
            "current_skill": self.current_skill,
            "current_attack_type": self.current_attack_type,
            "message": self.message,
        }


@dataclass
class MigrationResult:
    """Migration processing result

    Final result of migration test execution
    """

    total_tests: int
    total_loaded: int
    total_executed: int
    total_succeeded: int
    total_failed: int
    total_determined: int
    total_skipped: int
    success_rate: float
    succeeded_tests: list[str]  # Blocked test IDs (defense successful)
    failed_tests: list[str]  # Maliciously executed test IDs (attack successful)
    skipped_tests: list[str]  # Skipped test IDs (results already exist)
    execution_time_seconds: float
    started_at: datetime
    completed_at: datetime
    target_model: str
    source_dir: str
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary"""
        return {
            "total_tests": self.total_tests,
            "total_loaded": self.total_loaded,
            "total_executed": self.total_executed,
            "total_succeeded": self.total_succeeded,
            "total_failed": self.total_failed,
            "total_determined": self.total_determined,
            "total_skipped": self.total_skipped,
            "success_rate": self.success_rate,
            "succeeded_tests": self.succeeded_tests,
            "failed_tests": self.failed_tests,
            "skipped_tests": self.skipped_tests,
            "execution_time_seconds": self.execution_time_seconds,
            "started_at": self.started_at.isoformat(),
            "completed_at": self.completed_at.isoformat(),
            "target_model": self.target_model,
            "source_dir": self.source_dir,
            "metadata": self.metadata,
        }


class MigrationOrchestrator:
    """Migration test orchestrator

    Implements core logic for migration testing:
    1. Scan and load generated skills from source directory
    2. Filter by attack type
    3. Convert to TestCase entities
    4. Execute tests using SandboxTestRunner
    5. Save results to target directory
    """

    # Infrastructure error types (do not save result files)
    INFRA_ERRORS = {
        "execd_crash", "timeout", "network_error",
        "container_error", "sandbox_not_available"
    }

    def __init__(
        self,
        config: TwoPhaseExecutionConfig,
        max_concurrency: int = 4,
    ):
        """Initialize migration orchestrator

        Args:
            config: Two-phase execution configuration
            max_concurrency: Maximum concurrency for skill-attack pairs (default 4)
        """
        self._config = config
        self._max_concurrency = max_concurrency

        # Create test runner
        self._test_runner = SandboxTestRunner(config)

        # Statistics (require concurrency protection)
        self._succeeded_tests: list[str] = []
        self._failed_tests: list[str] = []
        self._skipped_tests: list[str] = []

        # Completed test case set {skill_name: {attack_type}}
        # Used for O(1) query to check if test is completed (align with streaming_orchestrator)
        self._completed_tests: dict[str, set[str]] = {}

        # Concurrency control locks
        self._progress_lock = asyncio.Lock()  # Protect progress updates

        # Migration configuration
        self._strategy_name = "migration"
        self._dataset_name = "skills_sample"

    def _load_completed_tests(self, target_model: str) -> None:
        """Load completed test cases from existing results and tally results

        Only load truly completed tests (non-infrastructure errors).
        Directory structure: test_details/migration/skills_sample/{skill_name}/{attack_type}/run_0/result.json

        Args:
            target_model: Target model name (for logging)
        """
        test_details_dir = Path(self._config.execution.output_dir) / "test_details"
        if not test_details_dir.exists():
            logger.info(f"[Migration orchestrator] test_details directory does not exist: {test_details_dir}")
            return

        # Traverse dataset subdirectories (only process skills_sample)
        for dataset_dir in (test_details_dir / self._strategy_name).iterdir():
            if not dataset_dir.is_dir() or dataset_dir.name != self._dataset_name:
                continue

            # Traverse skill_name subdirectories
            for skill_dir in dataset_dir.iterdir():
                if not skill_dir.is_dir():
                    continue
                skill_name = skill_dir.name

                # Traverse attack_type subdirectories
                for attack_dir in skill_dir.iterdir():
                    if not attack_dir.is_dir():
                        continue
                    attack_type = attack_dir.name

                    # Migration mode uses fixed run_0 directory (no iteration detection needed)
                    result_file = attack_dir / "run_0" / "result.json"
                    if not result_file.exists():
                        continue

                    # Read results and tally
                    try:
                        with open(result_file) as f:
                            data = json.load(f)
                            status = data.get("status")
                            error_type = data.get("error_type")
                            test_id = data.get("test_id", f"{skill_name}_{attack_type}")
                            executed_malicious = data.get("executed_malicious", False)

                            # Skip infrastructure errors (need retry)
                            if status == "error" and error_type in self.INFRA_ERRORS:
                                logger.info(
                                    f"[Migration orchestrator] Skipping infrastructure error (will retry): {test_id}, "
                                    f"error_type={error_type}"
                                )
                                continue

                            # Record as completed (for skipping)
                            if skill_name not in self._completed_tests:
                                self._completed_tests[skill_name] = set()
                            self._completed_tests[skill_name].add(attack_type)

                            # Tally historical results
                            if executed_malicious:
                                self._failed_tests.append(test_id)
                            else:
                                self._succeeded_tests.append(test_id)

                            logger.info(
                                f"[Migration orchestrator] Loaded historical result: {test_id}, "
                                f"status={status}, executed_malicious={executed_malicious}"
                            )
                    except Exception as e:
                        logger.warning(f"[Migration orchestrator] Failed to read result: {result_file}, {e}")

        # Add tally log
        total_skipped = sum(len(attacks) for attacks in self._completed_tests.values())
        total_history = len(self._succeeded_tests) + len(self._failed_tests)
        logger.info(
            f"[Migration orchestrator] Loaded {total_skipped} completed tests from {len(self._completed_tests)} skills, "
            f"historical results: {len(self._succeeded_tests)} blocked, {len(self._failed_tests)} attack succeeded"
        )

    def _is_test_completed(self, skill_name: str, attack_type: str) -> bool:
        """Check if test is completed (O(1) lookup)

        Args:
            skill_name: Skill name
            attack_type: Attack type

        Returns:
            Whether completed
        """
        if skill_name in self._completed_tests:
            return attack_type in self._completed_tests[skill_name]
        return False

    async def execute_migration(
        self,
        source_dir: Path,
        target_model: str,
        attack_types: list[AttackType] | None = None,
        progress_callback: Callable[[MigrationProgress], None] | None = None,
    ) -> MigrationResult:
        """Execute migration test pipeline

        Workflow:
        1. Scan source_dir, build skill-attack pair list
        2. Filter attack_types
        3. Check completed tests (incremental execution)
        4. Execute tests concurrently
        5. Save results

        Args:
            source_dir: Source directory path (e.g., final_glm_skills/)
            target_model: Target model name (e.g., claude, glm4)
            attack_types: List of attack types to test, None means all
            progress_callback: Progress callback function

        Returns:
            Migration processing result
        """
        start_time = time.time()
        started_at = datetime.now()

        # Load completed tests (align with streaming_orchestrator implementation style)
        self._load_completed_tests(target_model)

        # Initialize progress
        progress = MigrationProgress()
        self._report_progress(progress, progress_callback)

        # Scan source directory
        skill_attack_pairs = self._scan_source_directory(source_dir, attack_types)
        progress.total_tests = len(skill_attack_pairs)

        if not skill_attack_pairs:
            logger.warning(f"[Migration orchestrator] No test cases found in source directory: {source_dir}")
            return MigrationResult(
                total_tests=0,
                total_loaded=0,
                total_executed=0,
                total_succeeded=0,
                total_failed=0,
                total_determined=0,
                total_skipped=0,
                success_rate=0.0,
                succeeded_tests=[],
                failed_tests=[],
                skipped_tests=[],
                execution_time_seconds=0.0,
                started_at=started_at,
                completed_at=datetime.now(),
                target_model=target_model,
                source_dir=str(source_dir),
                metadata={"reason": "no_tests_found"},
            )

        logger.info(
            f"[Migration orchestrator] Found {len(skill_attack_pairs)} test cases, "
            f"target model: {target_model}"
        )

        # Check completed tests
        skill_attack_pairs = await self._filter_completed_tests(
            skill_attack_pairs, target_model
        )
        progress.total_skipped = progress.total_tests - len(skill_attack_pairs)

        if not skill_attack_pairs:
            logger.info("[Migration orchestrator] All tests completed, no need to execute")
            return self._create_result_from_history(progress, target_model, source_dir, started_at)

        # Choose execution path based on concurrency number
        if self._max_concurrency > 1:
            result = await self._execute_migration_concurrent(
                skill_attack_pairs=skill_attack_pairs,
                source_dir=source_dir,
                target_model=target_model,
                progress=progress,
                progress_callback=progress_callback,
            )
        else:
            result = await self._execute_migration_serial(
                skill_attack_pairs=skill_attack_pairs,
                source_dir=source_dir,
                target_model=target_model,
                progress=progress,
                progress_callback=progress_callback,
            )

        return result

    def _scan_source_directory(
        self,
        source_dir: Path,
        attack_types: list[AttackType] | None = None,
    ) -> list[tuple[str, AttackType]]:
        """Scan source directory, build skill-attack pair list

        Args:
            source_dir: Source directory path
            attack_types: List of attack types to test, None means all

        Returns:
            List of (skill_name, attack_type) pairs
        """
        if not source_dir.exists():
            logger.error(f"[Migration orchestrator] Source directory does not exist: {source_dir}")
            return []

        # Get attack type list
        if attack_types is None:
            attack_types = list(AttackType)

        skill_attack_pairs = []

        # Traverse attack type directories
        for attack_type in attack_types:
            attack_dir = source_dir / attack_type.value
            if not attack_dir.exists():
                logger.warning(f"[Migration orchestrator] Attack type directory does not exist: {attack_dir}")
                continue

            # Traverse skill directories
            for skill_dir in attack_dir.iterdir():
                if not skill_dir.is_dir():
                    continue

                # Check required files
                skill_file = skill_dir / "SKILL.md"
                metadata_file = skill_dir / "metadata.json"

                if not skill_file.exists() or not metadata_file.exists():
                    logger.warning(
                        f"[Migration orchestrator] Skill directory missing required files: {skill_dir}"
                    )
                    continue

                skill_attack_pairs.append((skill_dir.name, attack_type))

        return sorted(skill_attack_pairs)

    async def _filter_completed_tests(
        self,
        skill_attack_pairs: list[tuple[str, AttackType]],
        target_model: str,
    ) -> list[tuple[str, AttackType]]:
        """Filter completed tests (aligns with streaming_orchestrator implementation style)

        Use _is_test_completed() for O(1) lookup, historical results loaded in _load_completed_tests().

        Args:
            skill_attack_pairs: List of skill-attack pairs
            target_model: Target model name

        Returns:
            List of incomplete skill-attack pairs
        """
        filtered_pairs = []

        for skill_name, attack_type in skill_attack_pairs:
            attack_type_str = attack_type.value

            # Use _is_test_completed() for fast lookup
            if self._is_test_completed(skill_name, attack_type_str):
                logger.info(
                    f"[Migration orchestrator] Skipping completed: {skill_name}/{attack_type_str}"
                )
            else:
                filtered_pairs.append((skill_name, attack_type))

        return filtered_pairs

    async def _execute_migration_serial(
        self,
        skill_attack_pairs: list[tuple[str, AttackType]],
        source_dir: Path,
        target_model: str,
        progress: MigrationProgress,
        progress_callback: Callable[[MigrationProgress], None] | None = None,
    ) -> MigrationResult:
        """Execute migration test pipeline serially

        Args:
            skill_attack_pairs: List of skill-attack pairs
            source_dir: Source directory path
            target_model: Target model name
            progress: Progress object
            progress_callback: Progress callback

        Returns:
            Migration processing result
        """
        start_time = time.time()
        started_at = datetime.now()

        for skill_name, attack_type in skill_attack_pairs:
            await self._execute_skill_attack_pair(
                skill_name=skill_name,
                attack_type=attack_type,
                source_dir=source_dir,
                target_model=target_model,
                progress=progress,
                progress_callback=progress_callback,
            )

        completed_at = datetime.now()
        execution_time = time.time() - start_time

        return MigrationResult(
            total_tests=progress.total_tests,
            total_loaded=progress.total_loaded,
            total_executed=progress.total_executed,
            total_succeeded=progress.total_succeeded,
            total_failed=progress.total_failed,
            total_determined=progress.total_determined,
            total_skipped=progress.total_skipped,
            success_rate=progress.success_rate,
            succeeded_tests=self._succeeded_tests,
            failed_tests=self._failed_tests,
            skipped_tests=self._skipped_tests,
            execution_time_seconds=execution_time,
            started_at=started_at,
            completed_at=completed_at,
            target_model=target_model,
            source_dir=str(source_dir),
            metadata={"concurrency": 1, "execution_mode": "serial"},
        )

    async def _execute_migration_concurrent(
        self,
        skill_attack_pairs: list[tuple[str, AttackType]],
        source_dir: Path,
        target_model: str,
        progress: MigrationProgress,
        progress_callback: Callable[[MigrationProgress], None] | None = None,
    ) -> MigrationResult:
        """Execute migration test pipeline concurrently

        Args:
            skill_attack_pairs: List of skill-attack pairs
            source_dir: Source directory path
            target_model: Target model name
            progress: Progress object
            progress_callback: Progress callback

        Returns:
            Migration processing result
        """
        start_time = time.time()
        started_at = datetime.now()

        # Create Semaphore and tasks
        semaphore = asyncio.Semaphore(self._max_concurrency)

        # Start all concurrent tasks
        tasks = [
            asyncio.create_task(
                self._execute_skill_attack_pair_concurrent(
                    skill_name=s,
                    attack_type=at,
                    source_dir=source_dir,
                    target_model=target_model,
                    semaphore=semaphore,
                    progress=progress,
                    progress_callback=progress_callback,
                )
            )
            for s, at in skill_attack_pairs
        ]

        # Wait for all tasks to complete
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Check for exceptions
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                skill_name, attack_type = skill_attack_pairs[i]
                logger.error(f"[Migration orchestrator] Task exception: {skill_name}/{attack_type.value}: {result}")

        completed_at = datetime.now()
        execution_time = time.time() - start_time

        return MigrationResult(
            total_tests=progress.total_tests,
            total_loaded=progress.total_loaded,
            total_executed=progress.total_executed,
            total_succeeded=progress.total_succeeded,
            total_failed=progress.total_failed,
            total_determined=progress.total_determined,
            total_skipped=progress.total_skipped,
            success_rate=progress.success_rate,
            succeeded_tests=self._succeeded_tests,
            failed_tests=self._failed_tests,
            skipped_tests=self._skipped_tests,
            execution_time_seconds=execution_time,
            started_at=started_at,
            completed_at=completed_at,
            target_model=target_model,
            source_dir=str(source_dir),
            metadata={"concurrency": self._max_concurrency, "execution_mode": "concurrent"},
        )

    async def _execute_skill_attack_pair_concurrent(
        self,
        skill_name: str,
        attack_type: AttackType,
        source_dir: Path,
        target_model: str,
        semaphore: asyncio.Semaphore,
        progress: MigrationProgress,
        progress_callback: Callable[[MigrationProgress], None] | None = None,
    ) -> None:
        """Execute single skill-attack pair concurrently

        Use semaphore to limit concurrency.

        Args:
            skill_name: Skill name
            attack_type: Attack type
            source_dir: Source directory path
            target_model: Target model name
            semaphore: Concurrency control semaphore
            progress: Progress object
            progress_callback: Progress callback
        """
        async with semaphore:
            await self._execute_skill_attack_pair(
                skill_name=skill_name,
                attack_type=attack_type,
                source_dir=source_dir,
                target_model=target_model,
                progress=progress,
                progress_callback=progress_callback,
            )

    async def _execute_skill_attack_pair(
        self,
        skill_name: str,
        attack_type: AttackType,
        source_dir: Path,
        target_model: str,
        progress: MigrationProgress,
        progress_callback: Callable[[MigrationProgress], None] | None = None,
    ) -> None:
        """Execute single skill-attack pair

        Args:
            skill_name: Skill name
            attack_type: Attack type
            source_dir: Source directory path
            target_model: Target model name
            progress: Progress object
            progress_callback: Progress callback
        """
        # Update progress
        progress.current_skill = skill_name
        progress.current_attack_type = attack_type.value
        progress.message = f"Loading test case: {skill_name}/{attack_type.value}"
        self._report_progress(progress, progress_callback)

        # Load test case
        test_case = self._load_test_case(
            skill_name=skill_name,
            attack_type=attack_type,
            source_dir=source_dir,
            target_model=target_model,
        )

        if test_case is None:
            logger.warning(f"[Migration orchestrator] Failed to load test case: {skill_name}/{attack_type.value}")
            return

        async with self._progress_lock:
            progress.total_loaded += 1
        self._report_progress(progress, progress_callback)

        # Execute test
        progress.message = f"Executing test: {skill_name}/{attack_type.value}"
        self._report_progress(progress, progress_callback)

        # Build source skill directory (for copying SKILL.md and resources)
        source_skill_dir = source_dir / attack_type.value / skill_name

        result = await self._test_runner._run_test_async(
            test_case,
            iteration_number=0,  # Migration test runs only once
            skill_dir=source_skill_dir,
        )

        # Update statistics
        async with self._progress_lock:
            progress.total_executed += 1
            progress.total_determined += 1

            test_id = f"{skill_name}_{attack_type.value}"

            if result.executed_malicious:
                progress.total_failed += 1
                self._failed_tests.append(test_id)
            else:
                progress.total_succeeded += 1
                self._succeeded_tests.append(test_id)

        self._report_progress(progress, progress_callback)

    def _load_test_case(
        self,
        skill_name: str,
        attack_type: AttackType,
        source_dir: Path,
        target_model: str,
    ) -> TestCase | None:
        """Load test case from source directory

        Args:
            skill_name: Skill name
            attack_type: Attack type
            source_dir: Source directory path
            target_model: Target model name

        Returns:
            TestCase instance, or None if loading fails
        """
        # Build source path
        source_skill_dir = source_dir / attack_type.value / skill_name
        skill_file = source_skill_dir / "SKILL.md"
        metadata_file = source_skill_dir / "metadata.json"

        if not skill_file.exists() or not metadata_file.exists():
            logger.error(f"[Migration orchestrator] Source file does not exist: {source_skill_dir}")
            return None

        # Read metadata
        try:
            with open(metadata_file) as f:
                metadata = json.load(f)
        except Exception as e:
            logger.error(f"[Migration orchestrator] Failed to read metadata: {metadata_file}, {e}")
            return None

        # Build output directory path
        output_dir = Path(self._config.execution.output_dir)
        test_case_dir = (
            output_dir
            / "test_details"
            / self._strategy_name
            / self._dataset_name
            / skill_name
            / attack_type.value
            / "run_0"
        )

        # Ensure directory exists
        test_case_dir.mkdir(parents=True, exist_ok=True)

        # Copy SKILL.md and metadata.json to output directory
        shutil.copy2(skill_file, test_case_dir / "SKILL.md")
        shutil.copy2(metadata_file, test_case_dir / "metadata.json")

        # Copy resources directory
        resources_dir = source_skill_dir / "resources"
        if resources_dir.exists():
            dest_resources_dir = test_case_dir / "resources"
            if dest_resources_dir.exists():
                shutil.rmtree(dest_resources_dir)
            shutil.copytree(resources_dir, dest_resources_dir)

        # Build TestCase
        test_case = TestCase(
            id=TestCaseId.create(skill_name, attack_type),
            skill_name=skill_name,
            layer=InjectionLayer.DESCRIPTION,  # Default value, migration test doesn't care
            attack_type=attack_type,
            payload_name="migration",
            severity=Severity.HIGH,  # Default value
            skill_path=skill_file,
            test_case_dir=test_case_dir,
            dataset=self._dataset_name,
            should_be_blocked=True,
            metadata={
                "strategy": self._strategy_name,
                "source_model": "glm",  # Migrated from final_glm_skills
                "target_model": target_model,
                "original_metadata": metadata,
            },
        )

        logger.info(f"[Migration orchestrator] Successfully loaded test case: {skill_name}/{attack_type.value}")
        return test_case

    def _create_result_from_history(
        self,
        progress: MigrationProgress,
        target_model: str,
        source_dir: Path,
        started_at: datetime,
    ) -> MigrationResult:
        """Create MigrationResult from historical results

        Args:
            progress: Progress object
            target_model: Target model name
            source_dir: Source directory path
            started_at: Start time

        Returns:
            Migration processing result
        """
        # Calculate historical statistics
        total_succeeded = len(self._succeeded_tests)
        total_failed = len(self._failed_tests)
        total_determined = total_succeeded + total_failed

        return MigrationResult(
            total_tests=progress.total_tests,
            total_loaded=0,
            total_executed=0,
            total_succeeded=total_succeeded,
            total_failed=total_failed,
            total_determined=total_determined,
            total_skipped=progress.total_tests,
            success_rate=total_succeeded / total_determined if total_determined > 0 else 0.0,
            succeeded_tests=self._succeeded_tests,
            failed_tests=self._failed_tests,
            skipped_tests=self._skipped_tests,
            execution_time_seconds=0.0,
            started_at=started_at,
            completed_at=datetime.now(),
            target_model=target_model,
            source_dir=str(source_dir),
            metadata={"all_from_history": True},
        )

    def _report_progress(
        self,
        progress: MigrationProgress,
        callback: Callable[[MigrationProgress], None] | None = None,
    ) -> None:
        """Report progress

        Args:
            progress: Progress object
            callback: Callback function
        """
        if callback:
            try:
                callback(progress)
            except Exception as e:
                logger.warning(f"[Progress report] Callback failed: {e}")

    async def cleanup(self) -> None:
        """Clean up resources"""
        await self._test_runner.cleanup()


__all__ = [
    "MigrationProgress",
    "MigrationResult",
    "MigrationOrchestrator",
]
