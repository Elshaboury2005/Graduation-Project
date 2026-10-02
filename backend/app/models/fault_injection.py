"""
app/models/fault_injection.py
------------------------------
ORM model for a deliberate fault injected into a PipelineRun.

Fault injection records enable chaos-engineering analysis: which faults
were injected, when, and what the observed outcome was.
"""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, JSON, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base


class FaultInjection(Base):
    """
    A single fault-injection event attached to a PipelineRun.

    Inherits ``id``, ``created_at``, and ``updated_at`` from :class:`Base`.
    """

    __tablename__ = "fault_injections"

    # ── Parent reference ───────────────────────────────────────────────────────
    pipeline_run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("pipeline_runs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="FK to the PipelineRun in which this fault was injected.",
    )

    # ── Fault descriptor ───────────────────────────────────────────────────────
    fault_type: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        comment="Classifier for the fault (e.g. 'network_partition', 'disk_full').",
    )

    target_component: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
        comment="The component or service that was targeted by this fault.",
    )

    params: Mapped[dict | None] = mapped_column(
        JSON,
        nullable=True,
        comment="Fault-specific parameters (e.g. duration_seconds, packet_loss_pct).",
    )

    injected_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="Timestamp when the fault was actually applied.",
    )

    recovered_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="Timestamp when the system recovered from the fault.",
    )

    outcome: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
        comment="Observed outcome: 'recovered' | 'degraded' | 'failed'.",
    )

    # ── Relationships ──────────────────────────────────────────────────────────
    pipeline_run: Mapped["PipelineRun"] = relationship(  # noqa: F821
        "PipelineRun",
        back_populates="fault_injections",
    )

    def __repr__(self) -> str:
        return f"<FaultInjection id={self.id} type={self.fault_type!r}>"
