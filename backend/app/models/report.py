"""
app/models/report.py
--------------------
ORM model for generated analytical reports.

A Report is a rendered output document (HTML, PDF, JSON) produced from
one or more PipelineRuns or Experiments.  Storage details (e.g. S3 URI)
are deferred to a later phase.
"""

from sqlalchemy import JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base


class Report(Base):
    """
    A generated report artifact produced by the platform.

    Inherits ``id``, ``created_at``, and ``updated_at`` from :class:`Base`.
    """

    __tablename__ = "reports"

    title: Mapped[str] = mapped_column(
        String(512),
        nullable=False,
        comment="Human-readable title for the report.",
    )

    report_type: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        comment="Classifier for the report kind, e.g. 'pipeline_summary', 'experiment_comparison'.",
    )

    content: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Inline report body (HTML or Markdown).  Null when stored externally.",
    )

    storage_uri: Mapped[str | None] = mapped_column(
        String(1024),
        nullable=True,
        comment="External storage URI (e.g. s3://bucket/key) for large reports.",
    )

    metadata_: Mapped[dict | None] = mapped_column(
        "metadata",
        JSON,
        nullable=True,
        comment="Arbitrary key-value metadata (e.g. run IDs that contributed to this report).",
    )

    def __repr__(self) -> str:
        return f"<Report id={self.id} title={self.title!r}>"
