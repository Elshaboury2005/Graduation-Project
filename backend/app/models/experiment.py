"""
app/models/experiment.py
------------------------
ORM model for an ML/data experiment that may run across multiple
configurations (ExperimentRuns).

Experiments are independent of Pipelines at the data-model level so they
can be linked to external compute frameworks in later phases.
"""

from sqlalchemy import String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base


class Experiment(Base):
    """
    A named group of ExperimentRuns sharing a common hypothesis or goal.

    Inherits ``id``, ``created_at``, and ``updated_at`` from :class:`Base`.
    """

    __tablename__ = "experiments"

    name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        comment="Human-readable experiment name.",
    )

    description: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Optional description of the experiment's goal.",
    )

    # ── Relationships ──────────────────────────────────────────────────────────
    runs: Mapped[list["ExperimentRun"]] = relationship(  # noqa: F821
        "ExperimentRun",
        back_populates="experiment",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return f"<Experiment id={self.id} name={self.name!r}>"
