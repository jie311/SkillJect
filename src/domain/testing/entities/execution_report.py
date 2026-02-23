"""
Test Execution Report Domain Entity
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass(frozen=True)
class MonitoringData:
    """Monitoring data collection"""

    network_events: list[dict[str, Any]] = field(default_factory=list)
    process_events: list[dict[str, Any]] = field(default_factory=list)
    container_events: list[dict[str, Any]] = field(default_factory=list)
    system_metrics: dict[str, Any] = field(default_factory=dict)

    @property
    def total_events(self) -> int:
        """Get total event count"""
        return len(self.network_events) + len(self.process_events) + len(self.container_events)


@dataclass(frozen=True)
class CalculatedMetrics:
    """Calculated metrics"""

    total_tests: int
    passed: int
    failed: int
    blocked: int
    malicious_executions: int
    pass_rate: float
    block_rate: float
    malicious_rate: float
    infrastructure_errors: int = 0
    timeouts: int = 0
    security_score: float = 0.0  # 0-100

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary"""
        return {
            "total_tests": self.total_tests,
            "passed": self.passed,
            "failed": self.failed,
            "blocked": self.blocked,
            "malicious_executions": self.malicious_executions,
            "pass_rate": f"{self.pass_rate * 100:.1f}%",
            "block_rate": f"{self.block_rate * 100:.1f}%",
            "malicious_rate": f"{self.malicious_rate * 100:.1f}%",
            "infrastructure_errors": self.infrastructure_errors,
            "timeouts": self.timeouts,
            "security_score": f"{self.security_score:.1f}",
        }


@dataclass(frozen=True)
class TestExecutionResult:
    """Single test execution result"""

    test_id: str
    passed: bool
    blocked: bool
    executed_malicious: bool
    duration_seconds: float
    agent_response: str = ""
    error_message: str = ""
    error_type: str = ""
    is_infrastructure_error: bool = False
    execution_output: str = ""

    @property
    def status(self) -> str:
        """Get status string"""
        if self.is_infrastructure_error:
            return "error"
        if self.blocked:
            return "blocked"
        if self.executed_malicious:
            return "malicious"
        return "passed"


@dataclass
class ExecutionReport:
    """Test execution report

    Contains execution results, monitoring data, and calculated metrics.
    """

    report_id: str
    suite_id: str
    execution_started_at: datetime
    execution_completed_at: datetime
    duration_seconds: float
    results: list[TestExecutionResult]
    monitoring_data: MonitoringData
    metrics: CalculatedMetrics
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def total_tests(self) -> int:
        """Get total test count"""
        return len(self.results)

    def get_results_by_status(self, status: str) -> list[TestExecutionResult]:
        """Filter results by status"""
        return [r for r in self.results if r.status == status]

    def get_infrastructure_errors(self) -> list[TestExecutionResult]:
        """Get infrastructure errors"""
        return [r for r in self.results if r.is_infrastructure_error]

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary"""
        return {
            "report_id": self.report_id,
            "suite_id": self.suite_id,
            "execution_started_at": self.execution_started_at.isoformat(),
            "execution_completed_at": self.execution_completed_at.isoformat(),
            "duration_seconds": self.duration_seconds,
            "total_tests": self.total_tests,
            "results": [
                {
                    "test_id": r.test_id,
                    "status": r.status,
                    "passed": r.passed,
                    "blocked": r.blocked,
                    "executed_malicious": r.executed_malicious,
                    "duration_seconds": r.duration_seconds,
                    "error_message": r.error_message,
                    "is_infrastructure_error": r.is_infrastructure_error,
                }
                for r in self.results
            ],
            "monitoring": {
                "total_events": self.monitoring_data.total_events,
                "network_events": len(self.monitoring_data.network_events),
                "process_events": len(self.monitoring_data.process_events),
                "container_events": len(self.monitoring_data.container_events),
            },
            "metrics": self.metrics.to_dict(),
            "metadata": self.metadata,
        }
