"""
tests/reliability/test_fault_injectors.py
-------------------------------------------
Unit tests for all fault injectors.

All tests use a mocked DockerController — no real Docker socket needed.
Tests verify that each injector calls the correct controller methods with
the correct parameters, and that rollback() is always safely callable.
"""

from __future__ import annotations

from unittest.mock import MagicMock, call

import pytest

from app.reliability.fault_injectors.base_fault import FAULT_INJECTOR_REGISTRY
from app.reliability.fault_injectors.container_stop_fault import ContainerStopFault
from app.reliability.fault_injectors.container_restart_fault import ContainerRestartFault
from app.reliability.fault_injectors.network_disruption_fault import NetworkDisruptionFault
from app.reliability.fault_injectors.cpu_stress_fault import CpuStressFault
from app.reliability.fault_injectors.memory_stress_fault import MemoryStressFault
from app.reliability.fault_injectors.disk_pressure_fault import DiskPressureFault


# ── Fixtures ───────────────────────────────────────────────────────────────────


@pytest.fixture
def mock_docker():
    """Return a mocked DockerController with sensible defaults."""
    ctrl = MagicMock()
    ctrl.stop_container.return_value = {
        "container_id": "abc123",
        "container_name": "platform-kafka",
        "stopped_at": "2024-01-01T00:00:00+00:00",
    }
    ctrl.start_container.return_value = {"started_at": "2024-01-01T00:00:20+00:00"}
    ctrl.restart_container.return_value = {
        "container_id": "abc123",
        "container_name": "platform-kafka",
        "restarted_at": "2024-01-01T00:00:00+00:00",
    }
    ctrl.apply_network_disruption.return_value = {
        "action": "network_disruption_applied",
        "rule": "loss 100%",
        "applied_at": "2024-01-01T00:00:00+00:00",
        "duration_hint_seconds": 15,
    }
    ctrl.exec_in_container.return_value = (0, "")
    ctrl.exec_in_container_detached.return_value = {
        "container_name": "platform-kafka",
        "command": [],
        "started_at": "2024-01-01T00:00:00+00:00",
    }
    ctrl.is_container_running.return_value = False
    return ctrl


# ── Registry tests ─────────────────────────────────────────────────────────────


class TestFaultRegistry:
    """All 6 fault types must be registered."""

    def test_all_fault_types_registered(self) -> None:
        """Import triggers registration — all 6 types must be in the registry."""
        import app.reliability.fault_injectors  # noqa: F401 — triggers registration

        expected = {
            "container_stop",
            "container_restart",
            "network_disruption",
            "cpu_stress",
            "memory_stress",
            "disk_pressure",
        }
        assert expected.issubset(set(FAULT_INJECTOR_REGISTRY.keys()))

    def test_registry_classes_are_injector_subclasses(self) -> None:
        """All registry entries must be BaseFaultInjector subclasses."""
        from app.reliability.fault_injectors.base_fault import BaseFaultInjector

        import app.reliability.fault_injectors  # noqa: F401
        for fault_type, cls in FAULT_INJECTOR_REGISTRY.items():
            assert issubclass(cls, BaseFaultInjector), (
                f"'{fault_type}' → {cls.__name__} is not a BaseFaultInjector subclass"
            )


# ── ContainerStopFault ─────────────────────────────────────────────────────────


class TestContainerStopFault:
    def test_inject_calls_stop_container(self, mock_docker) -> None:
        """inject() must call DockerController.stop_container."""
        injector = ContainerStopFault(mock_docker)
        result = injector.inject("kafka", {})
        mock_docker.stop_container.assert_called_once_with("kafka")
        assert result["fault_type"] == "container_stop"

    def test_rollback_starts_container_when_not_running(self, mock_docker) -> None:
        """rollback() must call start_container when container is stopped."""
        mock_docker.is_container_running.return_value = False
        injector = ContainerStopFault(mock_docker)
        injector.rollback("kafka", {"container_id": "abc"})
        mock_docker.start_container.assert_called_once_with("kafka")

    def test_rollback_skips_start_when_already_running(self, mock_docker) -> None:
        """rollback() must not call start_container if already running."""
        mock_docker.is_container_running.return_value = True
        injector = ContainerStopFault(mock_docker)
        injector.rollback("kafka", {})
        mock_docker.start_container.assert_not_called()

    def test_rollback_is_safe_without_prior_inject(self, mock_docker) -> None:
        """rollback({}) must not raise even if inject was never called."""
        injector = ContainerStopFault(mock_docker)
        injector.rollback("kafka", {})  # Must not raise


# ── ContainerRestartFault ──────────────────────────────────────────────────────


class TestContainerRestartFault:
    def test_inject_calls_restart_container(self, mock_docker) -> None:
        """inject() must call DockerController.restart_container."""
        injector = ContainerRestartFault(mock_docker)
        result = injector.inject("kafka", {})
        mock_docker.restart_container.assert_called_once_with("kafka")
        assert result["fault_type"] == "container_restart"

    def test_rollback_is_noop(self, mock_docker) -> None:
        """rollback() must be a no-op (restart is instantaneous)."""
        injector = ContainerRestartFault(mock_docker)
        injector.rollback("kafka", {})
        mock_docker.restart_container.assert_not_called()
        mock_docker.start_container.assert_not_called()


# ── NetworkDisruptionFault ─────────────────────────────────────────────────────


class TestNetworkDisruptionFault:
    def test_inject_calls_apply_network_disruption(self, mock_docker) -> None:
        """inject() must call apply_network_disruption with correct duration."""
        injector = NetworkDisruptionFault(mock_docker)
        result = injector.inject("kafka", {"duration": 15})
        mock_docker.apply_network_disruption.assert_called_once_with("kafka", 15)
        assert result["fault_type"] == "network_disruption"

    def test_rollback_calls_remove_network_disruption(self, mock_docker) -> None:
        """rollback() must call remove_network_disruption."""
        injector = NetworkDisruptionFault(mock_docker)
        injector.rollback("kafka", {})
        mock_docker.remove_network_disruption.assert_called_once_with("kafka")

    def test_rollback_safe_even_if_inject_never_ran(self, mock_docker) -> None:
        """rollback({}) without inject must not raise."""
        injector = NetworkDisruptionFault(mock_docker)
        injector.rollback("kafka", {})  # Must not raise


# ── CpuStressFault ─────────────────────────────────────────────────────────────


class TestCpuStressFault:
    def test_inject_calls_exec_detached_with_stress_ng(self, mock_docker) -> None:
        """inject() must call exec_in_container_detached with stress-ng --cpu."""
        injector = CpuStressFault(mock_docker)
        result = injector.inject("spark-worker", {"cores": 2, "duration": 20})
        args = mock_docker.exec_in_container_detached.call_args
        command = args[0][1]  # second positional arg is command list
        assert "stress-ng" in command
        assert "--cpu" in command
        assert "2" in command
        assert result["fault_type"] == "cpu_stress"
        assert result["cores"] == 2

    def test_rollback_sends_pkill(self, mock_docker) -> None:
        """rollback() must call exec_in_container with pkill stress-ng."""
        injector = CpuStressFault(mock_docker)
        injector.rollback("spark-worker", {})
        args = mock_docker.exec_in_container.call_args[0]
        assert "pkill" in args[1]
        assert "stress-ng" in args[1]

    def test_rollback_safe_when_pkill_returns_nonzero(self, mock_docker) -> None:
        """rollback must not raise when pkill returns 1 (no process found)."""
        mock_docker.exec_in_container.return_value = (1, "no process found")
        injector = CpuStressFault(mock_docker)
        injector.rollback("spark-worker", {})  # Must not raise


# ── MemoryStressFault ──────────────────────────────────────────────────────────


class TestMemoryStressFault:
    def test_inject_calls_exec_detached_with_vm(self, mock_docker) -> None:
        """inject() must use stress-ng --vm with correct workers and bytes."""
        injector = MemoryStressFault(mock_docker)
        result = injector.inject(
            "spark-worker",
            {"vm_workers": 2, "memory_bytes": "256M", "duration": 20},
        )
        args = mock_docker.exec_in_container_detached.call_args[0][1]
        assert "--vm" in args
        assert "--vm-bytes" in args
        assert "256M" in args
        assert result["fault_type"] == "memory_stress"

    def test_rollback_kills_stress_ng(self, mock_docker) -> None:
        """rollback() must pkill stress-ng."""
        injector = MemoryStressFault(mock_docker)
        injector.rollback("spark-worker", {})
        args = mock_docker.exec_in_container.call_args[0]
        assert "pkill" in args[1]


# ── DiskPressureFault ──────────────────────────────────────────────────────────


class TestDiskPressureFault:
    def test_inject_calls_exec_detached_with_dd(self, mock_docker) -> None:
        """inject() must use dd to write a scratch file."""
        injector = DiskPressureFault(mock_docker)
        result = injector.inject("kafka", {"disk_size_mb": 100})
        args = mock_docker.exec_in_container_detached.call_args[0][1]
        assert "dd" in args
        assert "/tmp/chaoslab_disk_scratch" in str(args)
        assert result["fault_type"] == "disk_pressure"
        assert result["size_mb"] == 100

    def test_inject_caps_size_at_500mb(self, mock_docker) -> None:
        """Disk pressure must be capped at 500MB regardless of configured value."""
        injector = DiskPressureFault(mock_docker)
        result = injector.inject("kafka", {"disk_size_mb": 999})
        assert result["size_mb"] == 500

    def test_rollback_removes_scratch_file(self, mock_docker) -> None:
        """rollback() must rm -f the scratch file."""
        injector = DiskPressureFault(mock_docker)
        injector.rollback("kafka", {"scratch_path": "/tmp/chaoslab_disk_scratch"})
        args = mock_docker.exec_in_container.call_args[0][1]
        assert "rm" in args
        assert "/tmp/chaoslab_disk_scratch" in str(args)

    def test_rollback_safe_without_prior_inject(self, mock_docker) -> None:
        """rollback({}) must not raise even if inject never ran."""
        injector = DiskPressureFault(mock_docker)
        injector.rollback("kafka", {})  # Must not raise
