"""
Streaming Test Orchestrator

Implements streaming test processing mode: generate one test case, test it immediately,
and dynamically adjust the next generation parameters based on results.
Unlike batch mode, streaming mode supports real-time feedback loops and early stopping.

Core improvements:
- Batch mode: Generate N tests -> Execute N tests -> Analyze -> Next round
- Streaming mode: Generate 1 test -> Execute -> Analyze -> Adjust parameters -> Generate next

Feedback-driven adaptive iteration:
- Use RuleBasedFailureAnalyzer to analyze failure patterns
- Use AdaptiveGenerationParams to pass feedback to LLM
- LLM dynamically generates improved versions based on feedback
"""

import asyncio
import logging
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from src.domain.testing.value_objects.execution_config import TwoPhaseExecutionConfig
from src.shared.types import AttackType
from src.infrastructure.loaders.paths import resolve_data_path

from ...domain.analysis.services.failure_analyzer import RuleBasedFailureAnalyzer
from ...domain.generation.entities.generation_result import RefusedResult
from ...domain.generation.entities.test_suite import GeneratedTestCase
from ...domain.generation.services.adaptive_params import AdaptiveGenerationParams
from ...domain.generation.services.generation_factory import TestGenerationStrategyFactory
from ...domain.testing.entities.test_case import TestCase, TestCaseId, TestResult
from ...domain.testing.services.sandbox_test_runner import SandboxTestRunner

logger = logging.getLogger(__name__)


@dataclass
class StreamingProgress:
    """Streaming processing progress

    Tracks real-time progress of streaming test processing
    """

    total_generated: int = 0
    total_executed: int = 0
    total_succeeded: int = 0  # Number of blocked tests (defense successful)
    total_failed: int = 0  # Number of maliciously executed tests (attack successful)
    total_determined: int = 0  # Number of tests with clear results (succeeded + failed)
    current_skill: str = ""
    current_attack_type: str = ""
    current_params: dict = field(default_factory=dict)
    message: str = ""

    @property
    def success_rate(self) -> float:
        """Calculate defense success rate (based on tests with clear results)

        Returns:
            Success rate (0-1), 0 means all tests were bypassed, 1 means all tests were blocked
        """
        if self.total_determined == 0:
            return 0.0
        return self.total_succeeded / self.total_determined

    @property
    def undetermined_count(self) -> int:
        """Number of tests with undetermined results"""
        return self.total_executed - self.total_determined

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary"""
        return {
            "total_generated": self.total_generated,
            "total_executed": self.total_executed,
            "total_succeeded": self.total_succeeded,
            "total_failed": self.total_failed,
            "total_determined": self.total_determined,
            "undetermined_count": self.undetermined_count,
            "success_rate": self.success_rate,
            "current_skill": self.current_skill,
            "current_attack_type": self.current_attack_type,
            "current_params": self.current_params,
            "message": self.message,
        }


@dataclass
class StreamingResult:
    """Streaming processing result

    Final result of streaming test execution
    """

    total_generated: int
    total_executed: int
    total_succeeded: int
    total_failed: int
    total_determined: int  # Number of tests with clear results (succeeded + failed)
    success_rate: float
    succeeded_tests: list[str]  # Blocked test IDs (defense successful)
    failed_tests: list[str]  # Maliciously executed test IDs (attack successful)
    execution_time_seconds: float
    started_at: datetime
    completed_at: datetime
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary"""
        # Calculate ASR by counting each test case once
        total_test_cases = len(self.succeeded_tests) + len(self.failed_tests)
        asr = len(self.failed_tests) / total_test_cases if total_test_cases > 0 else 0.0

        return {
            "total_generated": self.total_generated,
            "total_executed": self.total_executed,
            "total_succeeded": self.total_succeeded,
            "total_failed": self.total_failed,
            "total_determined": self.total_determined,
            "undetermined_count": self.total_executed - self.total_determined,
            "total_test_cases": total_test_cases,  # New: total test case count (unique count)
            "success_rate": self.success_rate,
            "asr": asr,  # New: ASR counted by test case
            "succeeded_tests": self.succeeded_tests,
            "failed_tests": self.failed_tests,
            "execution_time_seconds": self.execution_time_seconds,
            "started_at": self.started_at.isoformat(),
            "completed_at": self.completed_at.isoformat(),
            "metadata": self.metadata,
        }


class StreamingOrchestrator:
    """Streaming test orchestrator

    Implements core logic for streaming test processing:
    1. Iterate through skills
    2. Attempt multiple iterations for each skill
    3. Generate -> Execute -> Analyze -> Generate next based on feedback (closed loop)
    4. Support early stopping mechanism

    Uses feedback-driven adaptive iteration:
    - RuleBasedFailureAnalyzer analyzes failure patterns
    - AdaptiveGenerationParams passes feedback to LLM
    - LLM dynamically generates improved versions based on feedback
    """

    def __init__(
        self,
        config: TwoPhaseExecutionConfig,
        max_attempts_per_test: int = 3,
        stop_on_success: bool = False,
        max_concurrency: int = 4,
    ):
        """Initialize streaming orchestrator

        Args:
            config: Two-phase execution configuration
            max_attempts_per_test: Maximum attempts per test (default 6)
            stop_on_success: Whether to stop after single success (skip remaining iterations)
            max_concurrency: Maximum concurrency for skill-attack pairs (default 4)
        """
        self._config = config
        self._max_attempts_per_test = max_attempts_per_test
        self._stop_on_success = stop_on_success
        self._max_concurrency = max_concurrency

        # Completed test case set {skill_name: {attack_type}}
        self._completed_tests: dict[str, set[str]] = {}

        # Create generator, test runner, and failure analyzer
        # Use factory pattern to create generator, supports all generation strategies
        # Pass execution.output_dir so generator saves to test_details directory
        self._generator = TestGenerationStrategyFactory.create(
            config.generation,
            execution_output_dir=Path(config.execution.output_dir),
        )
        self._test_runner = SandboxTestRunner(config)
        self._failure_analyzer = RuleBasedFailureAnalyzer()

        # Log generator type (for debugging)
        logger.info(
            f"[Streaming Orch] Initialized generator: {type(self._generator).__name__} "
            f"(strategy: {config.generation.strategy.value})"
        )

        # Statistics (requires concurrency protection)
        self._succeeded_tests: list[str] = []
        self._failed_tests: list[str] = []

        # Early stopping state (requires concurrency protection)
        self._skill_success: dict[str, set[str]] = {}  # {skill_name: {attack_type}}

        # Concurrency control locks
        self._early_stop_lock = asyncio.Lock()  # Protect _skill_success state
        self._progress_lock = asyncio.Lock()  # Protect progress updates (_succeeded_tests, _failed_tests)
        self._completed_lock = asyncio.Lock()  # Protect _completed_tests state

    async def execute_streaming(
        self,
        skill_names: list[str] | None = None,
        attack_types: list[AttackType] | None = None,
        progress_callback: Callable[[StreamingProgress], None] | None = None,
    ) -> StreamingResult:
        """Execute streaming test pipeline

        Workflow:
        1. Iterate through each skill (or execute multiple skill-attack pairs concurrently)
        2. Iterate through attack types for each skill
        3. Try various parameters for each combination
        4. Generate -> Execute -> Analyze -> Select next parameters

        Concurrent mode:
        - When max_concurrency > 1, different skill-attack pairs execute concurrently
        - Iterations within a single skill-attack pair remain serial (feedback loop dependency)
        - Reuse execution.max_concurrency configuration from main.yaml

        Args:
            skill_names: List of skills to test, None means all
            attack_types: List of attack types to test, None means all
            progress_callback: Progress callback function

        Returns:
            Streaming processing result
        """
        # Load completed tests
        self._load_completed_tests()

        # Get skill list
        if skill_names is None:
            skill_names = self._get_all_skill_names()

        # Get attack type list
        if attack_types is None:
            attack_types = list(AttackType)

        logger.info(
            f"[Streaming Orch] Starting processing {len(skill_names)} skills, "
            f"{len(attack_types)} attack types, "
            f"concurrency: {self._max_concurrency}"
        )

        # Choose execution path based on concurrency
        if self._max_concurrency > 1:
            result = await self._execute_streaming_concurrent(
                skill_names=skill_names,
                attack_types=attack_types,
                progress_callback=progress_callback,
            )
        else:
            result = await self._execute_streaming_serial(
                skill_names=skill_names,
                attack_types=attack_types,
                progress_callback=progress_callback,
            )

        return result

    async def _execute_streaming_serial(
        self,
        skill_names: list[str],
        attack_types: list[AttackType],
        progress_callback: Callable[[StreamingProgress], None] | None = None,
    ) -> StreamingResult:
        """Execute streaming test pipeline in serial

        This is the original execution logic, maintained for backward compatibility.

        Args:
            skill_names: List of skills to test
            attack_types: List of attack types to test
            progress_callback: Progress callback function

        Returns:
            Streaming processing result
        """
        start_time = time.time()
        started_at = datetime.now()

        # Initialize progress
        progress = StreamingProgress()
        self._report_progress(progress, progress_callback)

        # Iterate through skills
        for skill_name in skill_names:
            # Check global early stop
            if self._should_stop_globally():
                logger.info("[Streaming Orch] Global early stop triggered")
                break

            # Skill-level processing
            await self._execute_skill_streaming(
                skill_name=skill_name,
                attack_types=attack_types,
                progress=progress,
                progress_callback=progress_callback,
            )

        # Completion processing
        completed_at = datetime.now()
        execution_time = time.time() - start_time

        result = StreamingResult(
            total_generated=progress.total_generated,
            total_executed=progress.total_executed,
            total_succeeded=progress.total_succeeded,
            total_failed=progress.total_failed,
            total_determined=progress.total_determined,
            success_rate=progress.success_rate,
            succeeded_tests=self._succeeded_tests,
            failed_tests=self._failed_tests,
            execution_time_seconds=execution_time,
            started_at=started_at,
            completed_at=completed_at,
            metadata={
                "max_attempts_per_test": self._max_attempts_per_test,
                "stop_on_success": self._stop_on_success,
                "concurrency": 1,
                "execution_mode": "serial",
            },
        )

        logger.info(
            f"[Streaming Orch] Serial processing complete, success rate: {result.success_rate:.1%}, "
            f"time: {execution_time:.1f}s"
        )

        return result

    async def _execute_streaming_concurrent(
        self,
        skill_names: list[str],
        attack_types: list[AttackType],
        progress_callback: Callable[[StreamingProgress], None] | None = None,
    ) -> StreamingResult:
        """Execute streaming test pipeline concurrently

        Execute at skill-attack pair level:
        - Each independent skill-attack pair can execute concurrently
        - Iterations within a single skill-attack pair remain serial (feedback loop requires it)
        - Use Semaphore to limit concurrency

        Args:
            skill_names: List of skills to test
            attack_types: List of attack types to test
            progress_callback: Progress callback function

        Returns:
            Streaming processing result
        """
        start_time = time.time()
        started_at = datetime.now()

        # Initialize progress
        progress = StreamingProgress()
        self._report_progress(progress, progress_callback)

        # Build all skill-attack pairs, filter completed tests
        skill_attack_pairs = [
            (s, at)
            for s in skill_names
            for at in attack_types
            if not self._is_test_completed(s, at.value)
        ]

        logger.info(f"[Streaming Orch] Concurrent mode: {len(skill_attack_pairs)} skill-attack pairs to execute")

        if not skill_attack_pairs:
            logger.info("[Streaming Orch] All tests completed, no execution needed")
            completed_at = datetime.now()

            # Use historical statistics
            total_succeeded = len(self._succeeded_tests)
            total_failed = len(self._failed_tests)
            total_determined = total_succeeded + total_failed
            success_rate = total_succeeded / total_determined if total_determined > 0 else 1.0

            return StreamingResult(
                total_generated=0,  # No new tests generated in this run
                total_executed=0,   # No new tests run in this run
                total_succeeded=total_succeeded,
                total_failed=total_failed,
                total_determined=total_determined,
                success_rate=success_rate,
                succeeded_tests=self._succeeded_tests,
                failed_tests=self._failed_tests,
                execution_time_seconds=time.time() - start_time,
                started_at=started_at,
                completed_at=completed_at,
                metadata={
                    "max_attempts_per_test": self._max_attempts_per_test,
                    "stop_on_success": self._stop_on_success,
                    "concurrency": self._max_concurrency,
                    "execution_mode": "concurrent",
                    "all_from_history": True,  # Mark all results from history
                },
            )

        # Create Semaphore and tasks
        semaphore = asyncio.Semaphore(self._max_concurrency)

        # Start all concurrent tasks
        tasks = [
            asyncio.create_task(
                self._execute_skill_attack_pair_concurrent(
                    skill_name=s,
                    attack_type=at,
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
                logger.error(f"[Streaming Orch] Task exception: {skill_name}/{attack_type.value}: {result}")

        # Completion processing
        completed_at = datetime.now()
        execution_time = time.time() - start_time

        result = StreamingResult(
            total_generated=progress.total_generated,
            total_executed=progress.total_executed,
            total_succeeded=progress.total_succeeded,
            total_failed=progress.total_failed,
            total_determined=progress.total_determined,
            success_rate=progress.success_rate,
            succeeded_tests=self._succeeded_tests,
            failed_tests=self._failed_tests,
            execution_time_seconds=execution_time,
            started_at=started_at,
            completed_at=completed_at,
            metadata={
                "max_attempts_per_test": self._max_attempts_per_test,
                "stop_on_success": self._stop_on_success,
                "concurrency": self._max_concurrency,
                "execution_mode": "concurrent",
            },
        )

        logger.info(
            f"[Streaming Orch] Concurrent processing complete, success rate: {result.success_rate:.1%}, "
            f"time: {execution_time:.1f}s"
        )

        return result

    async def _execute_skill_attack_pair_concurrent(
        self,
        skill_name: str,
        attack_type: AttackType,
        semaphore: asyncio.Semaphore,
        progress: StreamingProgress,
        progress_callback: Callable[[StreamingProgress], None] | None = None,
    ) -> None:
        """Execute a single skill-attack pair concurrently

        Use semaphore to limit concurrency, check early stop conditions before starting.

        Args:
            skill_name: Skill name
            attack_type: Attack type
            semaphore: Concurrency control semaphore
            progress: Progress object
            progress_callback: Progress callback
        """
        async with semaphore:
            # Initialize skill success state
            if skill_name not in self._skill_success:
                self._skill_success[skill_name] = set()

            # Check early stop condition (must check and decide within lock)
            should_skip = False
            async with self._early_stop_lock:
                if self._should_stop_early(skill_name, attack_type):
                    logger.info(
                        f"[Streaming Orch] Concurrent mode skip (early stop): {skill_name}/{attack_type.value}"
                    )
                    should_skip = True

            if should_skip:
                return

            # Execute feedback loop (pass lock for state updates)
            await self._execute_test_with_feedback_loop(
                skill_name=skill_name,
                attack_type=attack_type,
                progress=progress,
                progress_callback=progress_callback,
                early_stop_lock=self._early_stop_lock,
            )

    async def _execute_skill_streaming(
        self,
        skill_name: str,
        attack_types: list[AttackType],
        progress: StreamingProgress,
        progress_callback: Callable[[StreamingProgress], None] | None = None,
    ) -> None:
        """Execute streaming test for a single skill

        Args:
            skill_name: Skill name
            attack_types: List of attack types
            progress: Progress object
            progress_callback: Progress callback
        """
        logger.info(f"[Streaming Orch] Starting processing skill: {skill_name}")

        # Initialize skill success state
        if skill_name not in self._skill_success:
            self._skill_success[skill_name] = set()

        for attack_type in attack_types:
            # Check if this test is completed
            if self._is_test_completed(skill_name, attack_type.value):
                logger.info(f"[Streaming Orch] Skipping completed test: {skill_name}/{attack_type.value}")
                continue

            # Check early stop condition
            if self._should_stop_early(skill_name, attack_type):
                logger.info(f"[Streaming Orch] Early stop: {skill_name}/{attack_type.value}")
                break

            # Test-level feedback loop
            await self._execute_test_with_feedback_loop(
                skill_name=skill_name,
                attack_type=attack_type,
                progress=progress,
                progress_callback=progress_callback,
            )

    async def _execute_test_with_feedback_loop(
        self,
        skill_name: str,
        attack_type: AttackType,
        progress: StreamingProgress,
        progress_callback: Callable[[StreamingProgress], None] | None = None,
        early_stop_lock: asyncio.Lock | None = None,
    ) -> None:
        """Execute a single test using feedback loop

        Adaptive iteration generation process based on test results:
        1. Initial generation (default configuration)
        2. Execute test -> ConsequenceDetector detects consequences
        3. RuleBasedFailureAnalyzer analyzes failure patterns
        4. Determine: ESCAPED/BLOCKED/IGNORED/ATTEMPTED_FAILED
        5. ESCAPED -> Stop (attack successful)
        6. Others -> Build feedback Prompt -> LLM generates improved version
        7. Loop until success or max_attempts_per_test reached

        Key improvement: Count by test case, each skill × attack_type combination counts only once.
        Any iteration with executed_malicious=True means the test case is compromised.

        Args:
            skill_name: Skill name
            attack_type: Attack type
            progress: Progress object
            progress_callback: Progress callback
        """
        # Create initial adaptive parameters
        adaptive_params = AdaptiveGenerationParams.create_initial()

        # Track test case status (for counting by test case)
        # Note: Early stop logic changed to "stop when attack succeeds"
        # - attack_succeeded=True: Attack succeeded, trigger early stop, count as failed (total_failed)
        # - attack_succeeded=False: Attack failed, continue iteration, don't count (until max iterations reached)
        test_case_succeeded = False  # Defense succeeded (deprecated, kept for compatibility)
        test_case_failed = False  # Attack succeeded

        # For reading previous round's generated SKILL.md content
        previous_content = None
        iteration_number = 0
        # Consecutive failure counter: allow generation failures up to MAX_CONSECUTIVE_FAILURES times
        consecutive_failures = 0
        MAX_CONSECUTIVE_FAILURES = 2

        while iteration_number < self._max_attempts_per_test:
            # Update progress
            progress.current_skill = skill_name
            progress.current_attack_type = attack_type.value
            progress.current_params = adaptive_params.to_dict()
            progress.message = (
                f"Generating test (iteration {iteration_number + 1}/{self._max_attempts_per_test})"
            )
            self._report_progress(progress, progress_callback)

            # Generate test case (use feedback-driven generation method)
            # Pass base path without test_details, let generator build full path
            base_output_dir = Path(self._config.execution.output_dir)

            generated_test = await self._generator.generate_stream_with_feedback(
                skill_name=skill_name,
                attack_type=attack_type,
                adaptive_params=adaptive_params,
                output_dir=base_output_dir,
            )

            if isinstance(generated_test, RefusedResult):
                # Build refusal message for screen output
                refusal_msg = (
                    f"\n{'=' * 60}\n"
                    f"[{generated_test.skill_name}/{generated_test.attack_type}] LLM Refused Generation\n"
                    f"{'=' * 60}\n"
                    f"  Reason: {generated_test.reason}\n"
                    f"{'=' * 60}\n"
                )
                print(refusal_msg)  # Output directly to screen
                logger.info(
                    f"[Feedback Loop] {skill_name}/{attack_type.value}: "
                    f"LLM refused generation, skipping this skill/attack_type combination"
                )
                # Refuse generation breaks out of feedback loop, continue to next attack_type
                break

            if generated_test is None:
                consecutive_failures += 1
                if consecutive_failures >= MAX_CONSECUTIVE_FAILURES:
                    logger.warning(
                        f"[Feedback Loop] {skill_name}/{attack_type.value}: "
                        f"LLM call failed {consecutive_failures} times consecutively, skipping this skill/attack_type combination"
                    )
                    break
                logger.info(
                    f"[Feedback Loop] {skill_name}/{attack_type.value}: "
                    f"LLM call failed ({consecutive_failures}/{MAX_CONSECUTIVE_FAILURES}), retrying..."
                )
                iteration_number += 1
                continue

            # Verify payload_content is non-empty (last line of defense)
            if not generated_test.payload_content or not generated_test.payload_content.strip():
                consecutive_failures += 1
                if consecutive_failures >= MAX_CONSECUTIVE_FAILURES:
                    logger.warning(
                        f"[Feedback Loop] {skill_name}/{attack_type.value}: "
                        f"Generated content empty {consecutive_failures} times consecutively, skipping this skill/attack_type combination"
                    )
                    break
                logger.warning(
                    f"[Feedback Loop] {skill_name}/{attack_type.value}: "
                    f"Generated test case payload_content empty ({consecutive_failures}/{MAX_CONSECUTIVE_FAILURES}), retrying..."
                )
                iteration_number += 1
                continue

            # Generation successful, reset consecutive failure counter
            consecutive_failures = 0

            progress.total_generated += 1
            self._report_progress(progress, progress_callback)

            # Execute test
            progress.message = (
                f"Executing test (iteration {iteration_number + 1}/{self._max_attempts_per_test})"
            )
            self._report_progress(progress, progress_callback)

            test_result = await self._execute_single_test(
                generated_test,
                iteration_number=iteration_number,
            )

            progress.total_executed += 1
            self._report_progress(progress, progress_callback)

            # Analyze results - simplified logic: only check for malicious behavior
            executed_malicious = test_result.executed_malicious
            attack_succeeded = executed_malicious  # Malicious behavior = attack successful

            # Count by test case (each test case counts only once)
            if not test_case_succeeded and not test_case_failed:
                # First count (requires concurrency protection)
                # Note: Early stop logic changed to "stop when attack succeeds"
                # attack_succeeded=True -> Attack succeeded -> Trigger early stop (no more iterations)
                # attack_succeeded=False -> Attack failed -> Continue iteration (try different attack methods)
                if attack_succeeded:
                    async with self._progress_lock:
                        progress.total_failed += 1
                        progress.total_determined += 1  # Tests with clear results increase
                        self._failed_tests.append(generated_test.test_id)
                    # Early stop state needs separate lock protection
                    if early_stop_lock:
                        async with early_stop_lock:
                            self._skill_success[skill_name].add(attack_type.value)
                    else:
                        self._skill_success[skill_name].add(attack_type.value)
                    test_case_failed = True
                    logger.warning(
                        f"[Feedback Loop] {skill_name}/{attack_type.value}: Malicious command executed (attack succeeded)"
                    )
                else:
                    # Attack failed (no malicious behavior), continue trying different attack methods
                    # Note: When attack fails, no longer count as "succeeded", but continue iteration
                    logger.debug(
                        f"[Feedback Loop] {skill_name}/{attack_type.value}: No harmful behavior detected, continuing to try"
                    )
            else:
                # Already counted, only log
                logger.debug(
                    f"[Feedback Loop] {skill_name}/{attack_type.value}: "
                    f"Iteration {iteration_number} (already counted, skip statistics)"
                )

            # Use failure analyzer to analyze results
            failure_analysis = self._failure_analyzer.analyze(test_result)

            # Check if defense was bypassed (executed_malicious = True)
            # Stop iteration immediately when attack succeeds, no need to continue trying
            if executed_malicious:
                logger.info(f"[Feedback Loop] {skill_name}/{attack_type.value}: Attack succeeded, stopping iteration")
                break

            # Prepare next iteration: read previous round's generated SKILL.md content
            previous_content = generated_test.payload_content

            # Create next round's adaptive parameters
            adaptive_params = adaptive_params.create_next(
                feedback=failure_analysis,
                previous_content=previous_content,
            )

            # Increment iteration number
            iteration_number += 1

            # Log if max attempts reached
            if iteration_number >= self._max_attempts_per_test:
                logger.info(
                    f"[Feedback Loop] {skill_name}/{attack_type.value}: "
                    f"Reached maximum attempts {self._max_attempts_per_test}"
                )

    async def _execute_single_test(
        self,
        generated_test: GeneratedTestCase,
        iteration_number: int = 0,
    ) -> TestResult:
        """Execute a single test

        Args:
            generated_test: Generated test case
            iteration_number: Iteration number, for building iteration_{N} directory

        Returns:
            Test result
        """
        # Extract skill_name: prefer from metadata, otherwise parse from test_id
        # test_id format: {skill_name}_{attack_type}
        skill_name = generated_test.metadata.get("skill_name")
        if not skill_name:
            # Parse from test_id: remove attack type suffix
            test_id_parts = generated_test.test_id.rsplit("_", 1)
            skill_name = test_id_parts[0] if len(test_id_parts) > 1 else generated_test.test_id

        # Build test_case_dir consistent with generator save path (supports iteration_N)
        # Generator save path: test_details/{strategy}/{dataset}/{skill_name}/{attack_type}/iteration_{N}/
        strategy = self._config.generation.strategy.value
        dataset = generated_test.dataset
        test_case_dir = (
            Path(self._config.execution.output_dir)
            / "test_details"
            / strategy
            / dataset
            / skill_name
            / generated_test.attack_type
            / f"iteration_{iteration_number}"
        )

        # Ensure directory exists (before creating TestCase)
        test_case_dir.mkdir(parents=True, exist_ok=True)

        # Convert to TestCase
        test_case = TestCase(
            id=TestCaseId(generated_test.test_id),
            skill_name=skill_name,
            layer=generated_test.injection_layer,
            attack_type=AttackType(generated_test.attack_type),
            payload_name="skillject",
            severity=generated_test.severity,
            skill_path=Path(generated_test.skill_path),
            test_case_dir=test_case_dir,
            dataset=generated_test.dataset,
            should_be_blocked=generated_test.should_be_blocked,
            injected_resource_file=generated_test.injected_resource_file,
            injection_points=generated_test.injection_points,
            metadata=generated_test.metadata,
        )

        # Create execution context
        context = self._test_runner.prepare_context(test_case)

        # Execute test
        # Note: skill_dir kept for compatibility, but no longer used to save injected_skill directory
        # (generator has saved SKILL.md and resources to test_case_dir)
        skill_dir = (
            test_case.test_case_dir
            if test_case.test_case_dir and test_case.test_case_dir.exists()
            else None
        )
        result = await self._test_runner._run_test_async(
            test_case,
            iteration_number=iteration_number,  # Pass iteration number
            skill_dir=skill_dir,
        )

        return result

    def _should_stop_early(self, skill_name: str, attack_type: AttackType) -> bool:
        """Check if should stop early

        Args:
            skill_name: Skill name
            attack_type: Attack type

        Returns:
            Whether to stop early
        """
        # Skill-level early stop: this skill has already succeeded on this attack type
        if skill_name in self._skill_success:
            if attack_type.value in self._skill_success[skill_name]:
                return True

        return False

    def _should_stop_globally(self) -> bool:
        """Check if should stop globally

        Returns:
            Whether to stop globally
        """
        return False

    def _load_completed_tests(self) -> None:
        """Load completed test cases from existing results and count results

        Only load truly completed tests (non-infrastructure errors).

        Directory structure: test_details/{strategy}/{dataset}/{skill_name}/{attack_type}/iteration_*/result.json
        """
        import json

        # Use test_details directory instead of computed_output_dir
        test_details_dir = Path(self._config.execution.output_dir) / "test_details"
        if not test_details_dir.exists():
            logger.info(f"[Incremental Test] test_details directory does not exist: {test_details_dir}")
            return

        # Iterate through strategy subdirectories (like skillject)
        current_strategy = self._config.generation.strategy.value
        # Define infrastructure error types
        INFRA_ERRORS = {
            "execd_crash", "timeout", "network_error",
            "container_error", "sandbox_not_available"
        }

        for strategy_dir in test_details_dir.iterdir():
            if not strategy_dir.is_dir():
                continue

            # FIX: Only process current strategy results, avoid test results from different strategies interfering
            if strategy_dir.name != current_strategy:
                logger.debug(
                    f"[Incremental Test] Skipping other strategy results: {strategy_dir.name} "
                    f"(current strategy: {current_strategy})"
                )
                continue

            # Iterate through dataset subdirectories (like skills_from_skill0)
            for dataset_dir in strategy_dir.iterdir():
                if not dataset_dir.is_dir():
                    continue

                # Iterate through skill_name subdirectories
                for skill_dir in dataset_dir.iterdir():
                    if not skill_dir.is_dir():
                        continue
                    skill_name = skill_dir.name

                    # Iterate through attack_type subdirectories
                    for attack_dir in skill_dir.iterdir():
                        if not attack_dir.is_dir():
                            continue
                        attack_type = attack_dir.name

                        # Find latest result.json file
                        result_file = self._find_latest_result_json(attack_dir)
                        if result_file is None:
                            continue

                        # Read results and count
                        try:
                            with open(result_file) as f:
                                data = json.load(f)
                                status = data.get("status")
                                error_type = data.get("error_type")
                                test_id = data.get("test_id", f"{skill_name}_{attack_type}")
                                executed_malicious = data.get("executed_malicious", False)

                                # Skip infrastructure errors (need retry)
                                if status == "error" and error_type in INFRA_ERRORS:
                                    logger.info(
                                        f"[Incremental Test] Skipping infrastructure error (will retry): {test_id}, "
                                        f"error_type={error_type}"
                                    )
                                    continue

                                # Record as completed (for skipping)
                                if skill_name not in self._completed_tests:
                                    self._completed_tests[skill_name] = set()
                                self._completed_tests[skill_name].add(attack_type)

                                # Count historical results
                                if executed_malicious:
                                    self._failed_tests.append(test_id)
                                else:
                                    self._succeeded_tests.append(test_id)

                                logger.info(
                                    f"[Incremental Test] Loaded historical result: {test_id}, "
                                    f"status={status}, executed_malicious={executed_malicious}"
                                )
                        except Exception as e:
                            logger.warning(f"[Incremental Test] Failed to read result: {result_file}, {e}")

        # Add statistics log
        total_skipped = sum(len(attacks) for attacks in self._completed_tests.values())
        total_history = len(self._succeeded_tests) + len(self._failed_tests)
        logger.info(
            f"[Incremental Test] Loaded {len(self._completed_tests)} skills' {total_skipped} completed tests, "
            f"historical results: {len(self._succeeded_tests)} blocked, {len(self._failed_tests)} attack succeeded"
        )

    def _find_latest_result_json(self, attack_dir: Path) -> Path | None:
        """Find the latest result.json file in the specified attack directory

        Args:
            attack_dir: Attack type directory (like information_disclosure)

        Returns:
            Path to result.json in the latest iteration directory, or None if not exists
        """
        # Find iteration_* directories with largest number
        iteration_dirs = [
            d for d in attack_dir.iterdir()
            if d.is_dir() and d.name.startswith("iteration_")
        ]
        if not iteration_dirs:
            return None

        # Sort by iteration number, take largest
        iteration_dirs.sort(key=lambda d: int(d.name.split("_")[1]))
        latest_dir = iteration_dirs[-1]
        result_file = latest_dir / "result.json"

        return result_file if result_file.exists() else None

    def _is_test_completed(self, skill_name: str, attack_type: str) -> bool:
        """Check if test is completed

        Args:
            skill_name: Skill name
            attack_type: Attack type

        Returns:
            Whether completed
        """
        if skill_name in self._completed_tests:
            return attack_type in self._completed_tests[skill_name]
        return False

    def _get_all_skill_names(self) -> list[str]:
        """Get all skill names

        Returns:
            List of skill names
        """
        # Use dataset path from config, not template_base_dir
        # Use resolve_data_path to properly handle relative paths
        base_dir = resolve_data_path(self._config.generation.dataset.base_dir)
        if not base_dir.exists():
            return []

        skill_names = []
        for skill_dir in base_dir.iterdir():
            if skill_dir.is_dir() and (skill_dir / "SKILL.md").exists():
                skill_names.append(skill_dir.name)

        return sorted(skill_names)

    def _report_progress(
        self,
        progress: StreamingProgress,
        callback: Callable[[StreamingProgress], None] | None = None,
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
                logger.warning(f"[Progress Report] Callback failed: {e}")

    async def cleanup(self) -> None:
        """Clean up resources"""
        await self._test_runner.cleanup()


__all__ = [
    "StreamingProgress",
    "StreamingResult",
    "StreamingOrchestrator",
]
