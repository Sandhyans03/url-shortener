"""Runtime configuration, read from environment variables."""

import os
from dataclasses import dataclass

DEFAULT_DATABASE_URL = "sqlite:///./shortener.db"


@dataclass(frozen=True)
class Settings:
    # Any SQLAlchemy URL works, e.g. postgresql+psycopg://user:pass@host/db
    database_url: str = DEFAULT_DATABASE_URL
    # Public origin used to build `short_url`. When unset, the origin of the
    # incoming request is used instead.
    base_url: str | None = None

    @classmethod
    def from_env(cls) -> "Settings":
        return cls(
            database_url=os.getenv("DATABASE_URL", DEFAULT_DATABASE_URL),
            base_url=os.getenv("BASE_URL") or None,
        )
