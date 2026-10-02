"""
app/models/pipeline.py
----------------------
ORM model representing a data pipeline definition.

A Pipeline is the top-level entity that owns PipelineVersions and
PipelineRuns.  Configuration and DAG details live on PipelineVersion,
keeping the pipeline record itself stable across version changes.
"""

import uuid

from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base


class Pipeline(Base):
    """
    A named, reusable data pipeline definition owned by a user.

    Inherits ``id``, ``created_at``, and ``updated_at`` from :class:`Base`.
    """

    __tablename__ = "pipelines"

    # ── Core identity ──────────────────────────────────────────────────────────
    name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        comment="Human-readable name for the pipeline.",
    )

    description: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Optional longer description of what this pipeline does.",
    )

    # ── Ownership ──────────────────────────────────────────────────────────────
    owner_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
        comment="FK to the user who created or owns this pipeline.",
    )

    # ── Relationships ──────────────────────────────────────────────────────────
    owner: Mapped["User"] = relationship(  # noqa: F821
        "User",
        back_populates="pipelines",
    )

    versions: Mapped[list["PipelineVersion"]] = relationship(  # noqa: F821
        "PipelineVersion",
        back_populates="pipeline",
        cascade="all, delete-orphan",
        order_by="PipelineVersion.created_at",
    )

    runs: Mapped[list["PipelineRun"]] = relationship(  # noqa: F821
        "PipelineRun",
        back_populates="pipeline",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return f"<Pipeline id={self.id} name={self.name!r}>"
