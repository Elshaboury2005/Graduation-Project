"""
app/models/audit_log.py
-----------------------
ORM model for immutable audit trail entries.

Every significant state change (pipeline created, run triggered, user
updated) should produce an AuditLog entry.  Rows must never be deleted
or updated — only inserted.
"""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, JSON, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base


class AuditLog(Base):
    """
    An immutable record of a significant platform event.

    Inherits ``id``, ``created_at``, and ``updated_at`` from :class:`Base`.

    .. note::
        Application-level enforcement is required to prevent updates/deletes.
        A database-level trigger or row-level security policy is recommended
        for production deployments.
    """

    __tablename__ = "audit_logs"

    # ── Who ────────────────────────────────────────────────────────────────────
    actor_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        nullable=True,
        index=True,
        comment="UUID of the user or service account that triggered the event.",
    )

    actor_type: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
        comment="'user' | 'service' | 'system'.",
    )

    # ── What ───────────────────────────────────────────────────────────────────
    action: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        index=True,
        comment="Verb describing the action, e.g. 'pipeline.create', 'run.trigger'.",
    )

    resource_type: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
        comment="The entity type affected, e.g. 'Pipeline', 'PipelineRun'.",
    )

    resource_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        nullable=True,
        index=True,
        comment="UUID of the specific resource affected.",
    )

    # ── Context ────────────────────────────────────────────────────────────────
    detail: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Human-readable summary of the change.",
    )

    diff: Mapped[dict | None] = mapped_column(
        JSON,
        nullable=True,
        comment="Optional before/after diff of the changed fields.",
    )

    ip_address: Mapped[str | None] = mapped_column(
        String(45),
        nullable=True,
        comment="Client IP address (IPv4 or IPv6) that initiated the request.",
    )

    occurred_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="Exact timestamp of the event (may differ from created_at under clock skew).",
    )

    def __repr__(self) -> str:
        return f"<AuditLog id={self.id} action={self.action!r}>"
