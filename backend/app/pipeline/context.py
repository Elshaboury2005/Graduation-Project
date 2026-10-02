"""
app/pipeline/context.py
------------------------
Per-run execution context that accumulates metrics and logs as a pipeline
progresses through its stages.

A fresh :class:`PipelineExecutionContext` is created at the start of every
``PipelineExecutor.execute()`` call.  No state is shared between runs.

Log entry format
----------------
Every entry appended to ``logs`` is a plain dict with at minimum::

    {
        "timestamp": "<ISO-8601 UTC string>",
        "level":     "INFO" | "WARNING" | "ERROR",
        "step":      "<step name, e.g. 'processor:filter:2'>",
        "message":   "<human-readable description>",
    }

This matches the structured JSON logging style established in Phase 1
(:class:`app.main._JsonFormatter`), so logs can be aggregated into the same
pipeline without extra transformation.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone


def _utc_now_iso() -> str:
    """Return the current UTC time as an ISO-8601 string."""
    return datetime.now(tz=timezone.utc).isoformat()


@dataclass
class PipelineExecutionContext:
    """
    Mutable context object created for a single pipeline run.

    Attributes
    ----------
    run_id : str
        UUID4 string that uniquely identifies this execution.  Used to
        correlate log entries and metrics across services.
    status : str
        Current run status — ``"running"``, ``"success"``, or ``"failed"``.
    metrics : dict
        Stage-level performance and volume data.  Keys are step names
        (e.g. ``"source:csv"``, ``"processor:filter:2"``); values are dicts
        with at least ``"rows_out"`` and ``"duration_ms"``.
    logs : list[dict]
        Ordered list of structured log entries appended during execution.
    """

    run_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    status: str = "running"
    metrics: dict = field(default_factory=dict)
    logs: list[dict] = field(default_factory=list)

    # ── Helpers ────────────────────────────────────────────────────────────────

    def log_info(self, step: str, message: str) -> None:
        """Append an INFO-level log entry."""
        self.logs.append(
            {
                "timestamp": _utc_now_iso(),
                "level": "INFO",
                "step": step,
                "message": message,
            }
        )

    def log_warning(self, step: str, message: str) -> None:
        """Append a WARNING-level log entry."""
        self.logs.append(
            {
                "timestamp": _utc_now_iso(),
                "level": "WARNING",
                "step": step,
                "message": message,
            }
        )

    def log_error(self, step: str, message: str) -> None:
        """Append an ERROR-level log entry."""
        self.logs.append(
            {
                "timestamp": _utc_now_iso(),
                "level": "ERROR",
                "step": step,
                "message": message,
            }
        )

    def record_stage(self, step: str, metadata: dict) -> None:
        """
        Record performance/volume data for a completed stage.

        Parameters
        ----------
        step : str
            Step identifier used as the metrics dict key.
        metadata : dict
            Arbitrary metadata — must contain at least ``"rows_out"`` and
            ``"duration_ms"``.
        """
        self.metrics[step] = metadata

    def to_summary(self) -> dict:
        """Return a JSON-serialisable summary of this context."""
        return {
            "run_id": self.run_id,
            "status": self.status,
            "metrics": self.metrics,
            "logs": self.logs,
        }
