"""
app/reliability/__init__.py
-----------------------------
ChaosLab — Reliability Engine (Phase 7).

This package implements the complete chaos engineering lifecycle:

    CREATE → VALIDATE → PREPARE → BASELINE → INJECT FAILURE →
    MONITOR → WAIT FOR RECOVERY → VALIDATE DATA → COLLECT METRICS →
    ANALYZE → CLEANUP → GENERATE REPORT

Key architectural rules
-----------------------
1. All Docker operations go through ``DockerController`` ONLY.
2. ``DockerController`` MUST call ``SafetyValidator`` before every action.
3. Fault injectors MUST NOT import or use ``docker`` directly.
4. ``safety.py`` is the single authority — every fault path goes through it.

See each sub-module for detailed documentation.
"""

from app.reliability.experiment_models import ExperimentModel
from app.reliability.exceptions import (
    ReliabilityError,
    UnsafeTargetError,
    TooManyConcurrentExperimentsError,
    ExperimentValidationError,
    FaultInjectionError,
    RollbackError,
)

__all__ = [
    "ExperimentModel",
    "ReliabilityError",
    "UnsafeTargetError",
    "TooManyConcurrentExperimentsError",
    "ExperimentValidationError",
    "FaultInjectionError",
    "RollbackError",
]
