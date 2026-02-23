"""
Monitoring data collector implementation.
"""

import asyncio
from typing import Any

from src.domain.testing.services.execution_pipeline import MonitoringCollector
from .network_monitor import NetworkMonitor, MonitorConfig, MonitorMode


class NetworkMonitoringCollector(MonitoringCollector):
    """Network monitoring collector.

    Collects network security events during test execution.
    """

    def __init__(self):
        self._active_monitors: dict[str, NetworkMonitor] = {}
        self._monitor_tasks: dict[str, asyncio.Task] = {}

    async def start_collection(self, test_id: str) -> None:
        """Start collecting monitoring data."""
        config = MonitorConfig(mode=MonitorMode.PASSIVE)
        monitor = NetworkMonitor(config=config)
        await monitor.start_monitoring()

        self._active_monitors[test_id] = monitor

        # Start monitoring task - keep monitoring active
        self._monitor_tasks[test_id] = asyncio.create_task(self._monitor_loop(test_id, monitor))

    async def _monitor_loop(self, test_id: str, monitor: NetworkMonitor) -> None:
        """Monitoring loop."""
        try:
            while test_id in self._active_monitors:
                await asyncio.sleep(0.5)
        except asyncio.CancelledError:
            pass

    async def stop_collection(self, test_id: str) -> dict[str, Any]:
        """Stop collection and return monitoring data."""
        # Cancel monitoring task
        task = self._monitor_tasks.pop(test_id, None)
        if task:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass

        # Get monitor
        monitor = self._active_monitors.pop(test_id, None)
        if not monitor:
            return {"network_events": [], "process_events": [], "container_events": []}

        # Stop monitoring and get events
        await monitor.stop_monitoring()
        activity_log = await monitor.get_network_activity()

        # Convert NetworkActivityLog to dictionary format
        events = [event.to_dict() for event in activity_log.events]

        return {
            "network_events": events,
            "process_events": [],
            "container_events": [],
        }

    async def cleanup(self, test_id: str) -> None:
        """Clean up monitoring resources."""
        # Resources already cleaned up in stop_collection
        pass


class CompositeMonitoringCollector(MonitoringCollector):
    """Composite monitoring collector.

    Integrates multiple monitoring data sources.
    """

    def __init__(self):
        self._collectors: list[MonitoringCollector] = []

    def add_collector(self, collector: MonitoringCollector) -> None:
        """Add collector."""
        self._collectors.append(collector)

    async def start_collection(self, test_id: str) -> None:
        """Start collecting monitoring data."""
        for collector in self._collectors:
            try:
                await collector.start_collection(test_id)
            except Exception as e:
                print(f"Warning: Failed to start collector: {e}")

    async def stop_collection(self, test_id: str) -> dict[str, Any]:
        """Stop collection and return monitoring data."""
        all_events = {
            "network_events": [],
            "process_events": [],
            "container_events": [],
        }

        for collector in self._collectors:
            try:
                data = await collector.stop_collection(test_id)
                for key in all_events:
                    all_events[key].extend(data.get(key, []))
            except Exception as e:
                print(f"Warning: Failed to stop collector: {e}")

        return all_events

    async def cleanup(self, test_id: str) -> None:
        """Clean up monitoring resources."""
        for collector in self._collectors:
            try:
                await collector.cleanup(test_id)
            except Exception as e:
                print(f"Warning: Failed to clean up collector: {e}")
