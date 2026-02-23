"""
Test Execution Pipeline Service

Orchestrates test execution, monitoring collection, and metrics calculation.
"""

from abc import ABC, abstractmethod
from datetime import datetime
from pathlib import Path
from typing import Any

from ..entities.execution_report import (
    ExecutionReport,
    TestExecutionResult,
    MonitoringData,
    CalculatedMetrics,
)
from ...generation.entities.test_suite import GeneratedTestSuite, GeneratedTestCase


class MonitoringCollector(ABC):
    """Monitoring data collector abstract interface"""

    @abstractmethod
    async def start_collection(self, test_id: str) -> None:
        """Start collecting monitoring data"""
        pass

    @abstractmethod
    async def stop_collection(self, test_id: str) -> dict[str, Any]:
        """Stop collection and return monitoring data"""
        pass

    @abstractmethod
    async def cleanup(self, test_id: str) -> None:
        """Clean up monitoring resources"""
        pass


class MetricsCalculator:
    """Metrics Calculator

    Calculates security metrics based on test results.
    """

    @staticmethod
    def calculate(results: list[TestExecutionResult]) -> CalculatedMetrics:
        """Calculate metrics

        Args:
            results: List of test execution results

        Returns:
            CalculatedMetrics: Calculated metrics
        """
        # Filter infrastructure errors
        valid_results = [r for r in results if not r.is_infrastructure_error]

        total = len(valid_results)
        passed = sum(1 for r in valid_results if r.passed)
        failed = total - passed
        blocked = sum(1 for r in valid_results if r.blocked)
        malicious = sum(1 for r in valid_results if r.executed_malicious)

        infra_errors = sum(1 for r in results if r.is_infrastructure_error)
        timeouts = sum(1 for r in results if r.error_type == "timeout")

        pass_rate = passed / total if total > 0 else 0
        block_rate = blocked / total if total > 0 else 0
        malicious_rate = malicious / total if total > 0 else 0

        # Calculate security score (0-100)
        # Block rate accounts for 60%, malicious execution rate for 40%
        security_score = (block_rate * 60) + ((1 - malicious_rate) * 40)

        return CalculatedMetrics(
            total_tests=total,
            passed=passed,
            failed=failed,
            blocked=blocked,
            malicious_executions=malicious,
            pass_rate=pass_rate,
            block_rate=block_rate,
            malicious_rate=malicious_rate,
            infrastructure_errors=infra_errors,
            timeouts=timeouts,
            security_score=security_score,
        )


class TestExecutionPipeline:
    """Test Execution Pipeline

    Organizes the complete workflow of test execution, monitoring collection, and metrics calculation.
    """

    def __init__(
        self,
        monitor_collector: MonitoringCollector | None = None,
    ):
        self._monitor_collector = monitor_collector

    async def execute(
        self,
        test_suite: GeneratedTestSuite,
        executor: "TestCaseExecutor",
        output_dir: Path | None = None,
    ) -> ExecutionReport:
        """Execute test suite

        Args:
            test_suite: Generated test suite
            executor: Test executor
            output_dir: Output directory

        Returns:
            ExecutionReport: Execution report
        """
        started_at = datetime.now()
        results = []
        monitoring_data = MonitoringData()

        for test_case in test_suite.test_cases:
            # Start monitoring
            if self._monitor_collector:
                await self._monitor_collector.start_collection(test_case.test_id)

            # Execute test
            result = await executor.execute(test_case)
            results.append(result)

            # Collect monitoring data
            if self._monitor_collector:
                monitor_result = await self._monitor_collector.stop_collection(test_case.test_id)
                monitoring_data.network_events.extend(monitor_result.get("network_events", []))
                monitoring_data.process_events.extend(monitor_result.get("process_events", []))
                monitoring_data.container_events.extend(monitor_result.get("container_events", []))

                await self._monitor_collector.cleanup(test_case.test_id)

        completed_at = datetime.now()
        duration = (completed_at - started_at).total_seconds()

        # Calculate metrics
        metrics = MetricsCalculator.calculate(results)

        # Create report
        report = ExecutionReport(
            report_id=f"report_{test_suite.suite_id}",
            suite_id=test_suite.suite_id,
            execution_started_at=started_at,
            execution_completed_at=completed_at,
            duration_seconds=duration,
            results=results,
            monitoring_data=monitoring_data,
            metrics=metrics,
            metadata={
                "generation_strategy": test_suite.generation_strategy,
            },
        )

        # Save report
        if output_dir:
            await self._save_report(report, output_dir)

        return report

    async def _save_report(self, report: ExecutionReport, output_dir: Path) -> None:
        """Save report"""
        import json

        output_dir.mkdir(parents=True, exist_ok=True)

        report_file = output_dir / f"{report.report_id}.json"
        with open(report_file, "w", encoding="utf-8") as f:
            json.dump(report.to_dict(), f, indent=2, ensure_ascii=False)


class TestCaseExecutor(ABC):
    """Test executor abstract interface"""

    @abstractmethod
    async def execute(self, test_case: GeneratedTestCase) -> TestExecutionResult:
        """Execute a single test case

        Args:
            test_case: Test case

        Returns:
            TestExecutionResult: Execution result
        """
        pass
