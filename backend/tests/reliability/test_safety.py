"""
tests/reliability/test_safety.py
----------------------------------
Unit tests for the SafetyValidator — the most critical module in ChaosLab.

All tests mock the Docker SDK so no real Docker socket is required.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch, PropertyMock

import pytest

from app.reliability.safety import SafetyValidator, ALLOWED_TARGET_SERVICES
from app.reliability.exceptions import (
    UnsafeTargetError,
    TooManyConcurrentExperimentsError,
)


# ── Fixtures ───────────────────────────────────────────────────────────────────


def _make_container(name: str = "platform-kafka", project: str = "resilient-big-data-platform"):
    """Return a mock Docker container with the correct project label."""
    container = MagicMock()
    container.name = name
    container.labels = {"com.docker.compose.project": project}
    return container


def _make_safety_with_mock_client(container=None):
    """
    Build a SafetyValidator with a fully mocked Docker client.
    """
    mock_client = MagicMock()
    if container is not None:
        mock_client.containers.get.return_value = container
    else:
        mock_client.containers.get.side_effect = Exception("Container not found")

    safety = SafetyValidator(docker_client=mock_client)
    return safety


# ── Tests: validate_target ─────────────────────────────────────────────────────


class TestValidateTarget:
    """SafetyValidator.validate_target() tests."""

    def test_accepts_valid_allowed_service(self) -> None:
        """An allowed service with the correct project label must pass."""
        container = _make_container("platform-kafka", "resilient-big-data-platform")
        safety = _make_safety_with_mock_client(container)

        with patch.object(safety, "_find_container", return_value=container):
            # Should not raise
            safety.validate_target("kafka")

    def test_rejects_service_not_in_allow_list(self) -> None:
        """A service not in ALLOWED_TARGET_SERVICES must raise UnsafeTargetError."""
        safety = _make_safety_with_mock_client()
        with pytest.raises(UnsafeTargetError) as exc_info:
            safety.validate_target("evil_service")
        assert "not in the ChaosLab allow-list" in str(exc_info.value)
        assert exc_info.value.service_name == "evil_service"

    def test_rejects_container_with_wrong_project_label(self) -> None:
        """A container with a different compose project label must be rejected."""
        container = _make_container("platform-kafka", "some-other-project")
        safety = _make_safety_with_mock_client(container)

        with patch.object(safety, "_find_container", return_value=container):
            with pytest.raises(UnsafeTargetError) as exc_info:
                safety.validate_target("kafka")
        assert "some-other-project" in str(exc_info.value)

    def test_rejects_container_with_no_project_label(self) -> None:
        """A container missing the compose project label must be rejected."""
        container = _make_container("platform-kafka")
        container.labels = {}  # no labels at all
        safety = _make_safety_with_mock_client(container)

        with patch.object(safety, "_find_container", return_value=container):
            with pytest.raises(UnsafeTargetError) as exc_info:
                safety.validate_target("kafka")
        assert "no 'com.docker.compose.project' label" in str(exc_info.value)

    def test_rejects_when_container_does_not_exist(self) -> None:
        """A service in the allow-list but with no running container must be rejected."""
        safety = _make_safety_with_mock_client(container=None)
        with pytest.raises(UnsafeTargetError) as exc_info:
            safety.validate_target("kafka")
        assert "kafka" in str(exc_info.value)

    @pytest.mark.parametrize("service", sorted(ALLOWED_TARGET_SERVICES))
    def test_all_allowed_services_pass_allow_list_check(self, service: str) -> None:
        """Every member of ALLOWED_TARGET_SERVICES clears the allow-list guard."""
        # We only test the first guard — container lookup is mocked to fail
        # so the test does NOT require Docker.
        safety = _make_safety_with_mock_client(container=None)
        # The allow-list check passes; the container-not-found error comes second
        with pytest.raises(UnsafeTargetError) as exc_info:
            safety.validate_target(service)
        # Error must be about the container not existing, not the allow-list
        assert "allow-list" not in str(exc_info.value)


# ── Tests: validate_duration ───────────────────────────────────────────────────


class TestValidateDuration:
    """SafetyValidator.validate_duration() tests."""

    def test_valid_duration_passes(self) -> None:
        """A duration within range must not raise."""
        safety = SafetyValidator()
        safety.validate_duration(30)  # Should not raise

    def test_zero_duration_rejected(self) -> None:
        """Duration of 0 must be rejected."""
        safety = SafetyValidator()
        with pytest.raises(UnsafeTargetError):
            safety.validate_duration(0)

    def test_negative_duration_rejected(self) -> None:
        """Negative duration must be rejected."""
        safety = SafetyValidator()
        with pytest.raises(UnsafeTargetError):
            safety.validate_duration(-10)

    def test_ceiling_duration_passes(self) -> None:
        """Exactly MAX_FAULT_DURATION_SECONDS must pass."""
        from app.reliability.experiment_models import MAX_FAULT_DURATION_SECONDS
        safety = SafetyValidator()
        safety.validate_duration(MAX_FAULT_DURATION_SECONDS)

    def test_above_ceiling_rejected(self) -> None:
        """Duration > MAX_FAULT_DURATION_SECONDS must raise."""
        from app.reliability.experiment_models import MAX_FAULT_DURATION_SECONDS
        safety = SafetyValidator()
        with pytest.raises(UnsafeTargetError) as exc_info:
            safety.validate_duration(MAX_FAULT_DURATION_SECONDS + 1)
        assert "ceiling" in str(exc_info.value)

    def test_large_duration_rejected(self) -> None:
        """An extreme duration (e.g. 99999s) must be rejected."""
        safety = SafetyValidator()
        with pytest.raises(UnsafeTargetError):
            safety.validate_duration(99999)


# ── Tests: enforce_max_concurrent_experiments ──────────────────────────────────


class TestEnforceMaxConcurrentExperiments:
    """SafetyValidator.enforce_max_concurrent_experiments() tests."""

    def test_raises_when_running_experiment_exists(self) -> None:
        """Must raise TooManyConcurrentExperimentsError if 1+ runs are 'running'."""
        mock_db = MagicMock()
        # Simulate scalar_one() returning 1 (one running experiment)
        mock_db.execute.return_value.scalar_one.return_value = 1

        safety = SafetyValidator()
        with pytest.raises(TooManyConcurrentExperimentsError) as exc_info:
            safety.enforce_max_concurrent_experiments(mock_db)
        assert exc_info.value.running_count == 1

    def test_passes_when_no_running_experiments(self) -> None:
        """Must not raise when no experiments are in 'running' status."""
        mock_db = MagicMock()
        mock_db.execute.return_value.scalar_one.return_value = 0

        safety = SafetyValidator()
        # Should not raise
        safety.enforce_max_concurrent_experiments(mock_db)

    def test_raises_with_multiple_running_experiments(self) -> None:
        """Must raise and report the correct count when >1 are running."""
        mock_db = MagicMock()
        mock_db.execute.return_value.scalar_one.return_value = 3

        safety = SafetyValidator()
        with pytest.raises(TooManyConcurrentExperimentsError) as exc_info:
            safety.enforce_max_concurrent_experiments(mock_db)
        assert "3" in str(exc_info.value)
