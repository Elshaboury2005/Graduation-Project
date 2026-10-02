"""
app/reliability/exceptions.py
-------------------------------
Custom exception hierarchy for the ChaosLab Reliability Engine.

All exceptions carry enough context for callers to produce actionable
error messages without inspecting tracebacks.
"""

from __future__ import annotations


class ReliabilityError(Exception):
    """Base class for all ChaosLab exceptions."""


class UnsafeTargetError(ReliabilityError):
    """
    Raised when a requested target fails the SafetyValidator checks.

    Possible causes:
    - Service name not in ``ALLOWED_TARGET_SERVICES``.
    - Container does not exist in Docker.
    - Container exists but is not labeled as belonging to this project.
    - Resolved container name does not match project prefix rules.
    """

    def __init__(self, message: str, service_name: str = "") -> None:
        super().__init__(message)
        self.service_name = service_name


class TooManyConcurrentExperimentsError(ReliabilityError):
    """
    Raised when a new experiment is submitted while one is already running.

    Running two chaos experiments simultaneously would produce compounding
    failures, making measurement meaningless and potentially destabilising
    the entire platform stack.
    """

    def __init__(self, running_count: int = 1) -> None:
        super().__init__(
            f"Cannot start a new experiment: {running_count} experiment(s) already "
            "running. Wait for the current experiment to complete or cancel it first."
        )
        self.running_count = running_count


class ExperimentValidationError(ReliabilityError):
    """
    Raised when an experiment definition fails semantic validation.

    Distinct from Pydantic's ``ValidationError`` which covers schema errors —
    this covers business-rule violations (e.g. incompatible fault type / target
    combinations, unreachable services).
    """

    def __init__(self, message: str, field: str = "") -> None:
        super().__init__(message)
        self.field = field


class FaultInjectionError(ReliabilityError):
    """
    Raised when a fault injector's ``inject()`` call fails.

    Attributes
    ----------
    fault_type : str
        The type of fault that failed (e.g. ``"container_stop"``).
    target_service : str
        The service that was being targeted.
    """

    def __init__(
        self, message: str, fault_type: str = "", target_service: str = ""
    ) -> None:
        super().__init__(message)
        self.fault_type = fault_type
        self.target_service = target_service


class RollbackError(ReliabilityError):
    """
    Raised when a fault injector's ``rollback()`` call itself fails.

    This is a secondary failure — the original fault may still be applied.
    Callers must log this prominently and alert operators.
    """

    def __init__(
        self, message: str, fault_type: str = "", target_service: str = ""
    ) -> None:
        super().__init__(message)
        self.fault_type = fault_type
        self.target_service = target_service


class ExperimentTimeoutError(ReliabilityError):
    """
    Raised when the total experiment duration exceeds the global timeout.

    The runner catches this, forces rollback, and marks the run
    ``status: "timed_out"`` before generating the report.
    """

    def __init__(self, timeout_seconds: int) -> None:
        super().__init__(
            f"Experiment exceeded global timeout of {timeout_seconds}s. "
            "Rollback and cleanup initiated."
        )
        self.timeout_seconds = timeout_seconds
