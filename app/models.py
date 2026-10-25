"""ORM models."""

from datetime import datetime, timezone

from sqlalchemy import DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import TypeDecorator

from app.db import Base


class UTCDateTime(TypeDecorator):
    """Stores timezone-aware datetimes as naive UTC and returns them as aware.

    SQLite (and plain Postgres TIMESTAMP) drop tzinfo, which would otherwise
    make comparisons with aware datetimes blow up.
    """

    impl = DateTime
    cache_ok = True

    def process_bind_param(self, value, dialect):
        if value is None:
            return None
        if value.tzinfo is None:
            raise ValueError("Naive datetimes are not allowed; use UTC-aware values.")
        return value.astimezone(timezone.utc).replace(tzinfo=None)

    def process_result_value(self, value, dialect):
        if value is None:
            return None
        return value.replace(tzinfo=timezone.utc)


class Link(Base):
    __tablename__ = "links"

    id: Mapped[int] = mapped_column(primary_key=True)
    # Unique constraint is the source of truth for "alias already taken",
    # so duplicate detection is race-free.
    code: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    original_url: Mapped[str] = mapped_column(String(2048))
    created_at: Mapped[datetime] = mapped_column(UTCDateTime)
    expires_at: Mapped[datetime | None] = mapped_column(UTCDateTime, nullable=True)
    click_count: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    last_clicked_at: Mapped[datetime | None] = mapped_column(UTCDateTime, nullable=True)

    def is_expired(self, now: datetime) -> bool:
        return self.expires_at is not None and now >= self.expires_at
