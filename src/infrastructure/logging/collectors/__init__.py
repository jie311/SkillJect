"""
Log Collector Module Exports

Exports public interfaces for log collector related modules.

Available log collectors:
- StderrLogCollector: General log collection for CLI agents
- ClaudeOtelLogCollector: Claude Code specific OpenTelemetry log collection
- NetworkLogCollector: Network activity log collection
- PassiveNetworkCollector: Passive network log collection
"""

from .base_collector import LogCollector, StdoutCollector, OtelCollector
from .stderr_log_collector import StderrLogCollector
from .claude_otel_log_collector import ClaudeOtelLogCollector
from .network_log_collector import NetworkLogCollector, PassiveNetworkCollector

__all__ = [
    "LogCollector",
    "StdoutCollector",
    "OtelCollector",
    "StderrLogCollector",
    "ClaudeOtelLogCollector",
    "NetworkLogCollector",
    "PassiveNetworkCollector",
]
