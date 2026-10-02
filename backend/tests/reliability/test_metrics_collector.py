"""
tests/reliability/test_metrics_collector.py
---------------------------------------------
Unit tests for MetricsCollector.

Tests focus on:
- measure_recovery_time returning elapsed seconds when service recovers
- measure_recovery_time returning None when max_wait exceeded
- compute_throughput arithmetic
- capture_baseline extracts records_processed correctly
"""

from __future__ import annotations

import time
from unittest.mock import MagicMock, patch

import pytest

from app.reliability.metrics_collector import MetricsCollector


class TestMeasureRecoveryTime:
    """measure_recovery_time tests."""

    def test_returns_elapsed_seconds_when_recovered(self) -> None:
        """
        Returns elapsed time (float) when container becomes healthy
        after N polls.
        """
        collector = MetricsCollector()
        mock_docker = MagicMock()

        # Container is down for first 2 polls, then up
        mock_docker.is_container_running.side_effect = [False, False, True]

        elapsed = collector.measure_recovery_time(
            target_service="kafka",
            docker_controller=mock_docker,
            poll_interval=0.01,
            max_wait=5.0,
        )

        assert elapsed is not None
        assert elapsed >= 0.0
        assert elapsed < 5.0

    def test_returns_none_when_max_wait_exceeded(self) -> None:
        """Returns None when the service never recovers within max_wait."""
        collector = MetricsCollector()
        mock_docker = MagicMock()
        mock_docker.is_container_running.return_value = False

        elapsed = collector.measure_recovery_time(
            target_service="kafka",
            docker_controller=mock_docker,
            poll_interval=0.01,
            max_wait=0.05,  # very short timeout
        )

        assert elapsed is None

    def test_health_check_fn_must_also_pass(self) -> None:
        """
        If health_check_fn is provided, both container running AND
        health_check_fn returning connected=True must be true.
        """
        collector = MetricsCollector()
        mock_docker = MagicMock()
        mock_docker.is_container_running.return_value = True

        # health_check returns unhealthy first, then healthy
        health_fn = MagicMock(side_effect=[
            {"connected": False},
            {"connected": True},
        ])

        elapsed = collector.measure_recovery_time(
            target_service="kafka",
            docker_controller=mock_docker,
            poll_interval=0.01,
            max_wait=5.0,
            health_check_fn=health_fn,
        )

        assert elapsed is not None
        assert health_fn.call_count == 2

    def test_health_check_exception_treated_as_not_recovered(self) -> None:
        """An exception from health_check_fn is treated as unhealthy (not recovered)."""
        collector = MetricsCollector()
        mock_docker = MagicMock()
        mock_docker.is_container_running.return_value = True

        def failing_health():
            raise ConnectionError("broker unreachable")

        elapsed = collector.measure_recovery_time(
            target_service="kafka",
            docker_controller=mock_docker,
            poll_interval=0.01,
            max_wait=0.05,
            health_check_fn=failing_health,
        )

        assert elapsed is None


class TestComputeThroughput:
    """compute_throughput tests."""

    def test_basic_throughput(self) -> None:
        """1000 records in 10 seconds = 100 records/s."""
        collector = MetricsCollector()
        assert collector.compute_throughput(1000, 10.0) == 100.0

    def test_zero_duration_returns_zero(self) -> None:
        """Zero duration must return 0.0 (avoid ZeroDivisionError)."""
        collector = MetricsCollector()
        assert collector.compute_throughput(1000, 0.0) == 0.0

    def test_zero_records(self) -> None:
        """Zero records processed returns 0.0."""
        collector = MetricsCollector()
        assert collector.compute_throughput(0, 60.0) == 0.0


class TestCaptureBaseline:
    """capture_baseline tests."""

    def test_extracts_records_processed(self) -> None:
        """Baseline must correctly extract records_processed from context."""
        collector = MetricsCollector()
        context = {"records_processed": 5000}
        baseline = collector.capture_baseline(context)
        assert baseline["expected_record_count"] == 5000

    def test_falls_back_to_rows_written(self) -> None:
        """Falls back to rows_written if records_processed is absent."""
        collector = MetricsCollector()
        context = {"rows_written": 3000}
        baseline = collector.capture_baseline(context)
        assert baseline["expected_record_count"] == 3000

    def test_returns_zero_when_no_records(self) -> None:
        """Returns 0 if neither key is in context."""
        collector = MetricsCollector()
        baseline = collector.capture_baseline({})
        assert baseline["expected_record_count"] == 0

    def test_baseline_contains_timestamp(self) -> None:
        """Baseline dict must include a timestamp."""
        collector = MetricsCollector()
        baseline = collector.capture_baseline({})
        assert "baseline_captured_at" in baseline
        assert "T" in baseline["baseline_captured_at"]  # ISO format check
