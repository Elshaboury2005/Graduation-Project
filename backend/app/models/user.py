"""
app/models/user.py
------------------
ORM model for platform users.

Columns are intentionally minimal for Phase 1; authentication and
role-based access control columns will be added in a later phase.
"""

from sqlalchemy import Boolean, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base


class User(Base):
    """
    Represents a human operator or service account on the platform.

    Inherits ``id``, ``created_at``, and ``updated_at`` from :class:`Base`.
    """

    __tablename__ = "users"

    email: Mapped[str] = mapped_column(
        String(255),
        unique=True,
        nullable=False,
        index=True,
        comment="Unique email address used as the login identifier.",
    )

    hashed_password: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        comment="bcrypt hash of the user's password — never the plain-text value.",
    )

    full_name: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
        comment="Optional display name for the user.",
    )

    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        server_default="true",
        nullable=False,
        comment="False when the account has been deactivated.",
    )

    is_superuser: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        server_default="false",
        nullable=False,
        comment="True grants unrestricted access to all platform resources.",
    )

    # ── Relationships (back-references populated by child models) ──────────────
    pipelines: Mapped[list["Pipeline"]] = relationship(  # noqa: F821
        "Pipeline",
        back_populates="owner",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return f"<User id={self.id} email={self.email!r}>"
