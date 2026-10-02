"""
app/models/metric.py
--------------------
ORM model for a single numeric measurement captured during a PipelineRun.

Metrics are intentionally simple key-value pairs so they can be used for
both operational metrics (throughput, latency) and ML metrics (loss, AUC).
"""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base


class Metric(Base):
    """
    A single named numeric metric recorded at a point in time.

    Inherits ``id``, ``created_at``, and ``updated_at`` from :class:`Base`.
    """

    __tablename__ = "metrics"

    # ── Parent reference ───────────────────────────────────────────────────────
    pipeline_run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("pipeline_runs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="FK to the PipelineRun that produced this metric.",
    )

    # ── Measurement ────────────────────────────────────────────────────────────
    name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        comment="Metric identifier, e.g. 'throughput_rows_per_sec'.",
    )

    value: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        comment="Numeric value of the metric.",
    )

    unit: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
        comment="Optional SI unit string, e.g. 'rows/s', 'ms', 'bytes'.",
    )

    recorded_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="Exact timestamp of the measurement (defaults to created_at if null).",
    )

    step: Mapped[int | None] = mapped_column(
        nullable=True,
        comment="Training step or batch index for iterative metrics.",
    )

    # ── Relationships ──────────────────────────────────────────────────────────
    pipeline_run: Mapped["PipelineRun"] = relationship(  # noqa: F821
        "PipelineRun",
        back_populates="metrics",
    )

    def __repr__(self) -> str:
        return f"<Metric id={self.id} name={self.name!r} value={self.value}>"
