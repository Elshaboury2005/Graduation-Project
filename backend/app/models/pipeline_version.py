"""
app/models/pipeline_version.py
-------------------------------
ORM model representing an immutable, versioned snapshot of a Pipeline's
configuration.

Creating a new PipelineVersion is the only way to change a pipeline's
behaviour; prior versions are kept for audit/rollback purposes.
"""

import uuid

from sqlalchemy import ForeignKey, Integer, JSON, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base


class PipelineVersion(Base):
    """
    An immutable snapshot of a Pipeline's DAG configuration.

    Inherits ``id``, ``created_at``, and ``updated_at`` from :class:`Base`.
    """

    __tablename__ = "pipeline_versions"

    # ── Parent reference ───────────────────────────────────────────────────────
    pipeline_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("pipelines.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="FK to the parent Pipeline.",
    )

    # ── Version metadata ───────────────────────────────────────────────────────
    version_number: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        comment="Monotonically increasing integer version within the parent pipeline.",
    )

    description: Mapped[str | None] = mapped_column(
        String(1024),
        nullable=True,
        comment="Changelog entry or summary for this version.",
    )

    config: Mapped[dict | None] = mapped_column(
        JSON,
        nullable=True,
        comment="Serialised DAG / step configuration for this version.",
    )

    # ── Relationships ──────────────────────────────────────────────────────────
    pipeline: Mapped["Pipeline"] = relationship(  # noqa: F821
        "Pipeline",
        back_populates="versions",
    )

    runs: Mapped[list["PipelineRun"]] = relationship(  # noqa: F821
        "PipelineRun",
        back_populates="pipeline_version",
    )

    def __repr__(self) -> str:
        return (
            f"<PipelineVersion id={self.id} "
            f"pipeline_id={self.pipeline_id} v={self.version_number}>"
        )
