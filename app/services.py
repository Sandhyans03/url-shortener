"""Business rules for creating, resolving and inspecting short links."""

import secrets
import string
from datetime import datetime

from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.clock import Clock
from app.errors import (
    AliasTaken,
    CodeGenerationFailed,
    InvalidExpiry,
    LinkExpired,
    LinkNotFound,
)
from app.models import Link

CODE_ALPHABET = string.ascii_letters + string.digits
CODE_LENGTH = 7
MAX_GENERATION_ATTEMPTS = 5


def generate_code() -> str:
    return "".join(secrets.choice(CODE_ALPHABET) for _ in range(CODE_LENGTH))


class _CodeAlreadyExists(Exception):
    """Internal signal: the unique constraint on `links.code` was violated."""


class LinkService:
    def __init__(self, db: Session, clock: Clock):
        self._db = db
        self._clock = clock

    def create(
        self,
        url: str,
        alias: str | None = None,
        expires_at: datetime | None = None,
    ) -> Link:
        now = self._clock()
        if expires_at is not None and expires_at <= now:
            raise InvalidExpiry()

        if alias is not None:
            try:
                return self._insert(alias, url, now, expires_at)
            except _CodeAlreadyExists:
                raise AliasTaken(alias) from None

        # Random codes can (rarely) collide with an existing code or a custom
        # alias; the unique constraint catches that and we simply retry.
        for _ in range(MAX_GENERATION_ATTEMPTS):
            try:
                return self._insert(generate_code(), url, now, expires_at)
            except _CodeAlreadyExists:
                continue
        raise CodeGenerationFailed()

    def register_click(self, code: str) -> str:
        """Return the destination for `code` and record the visit.

        Raises LinkNotFound / LinkExpired; neither counts as a click.
        """
        link = self._get(code)
        now = self._clock()
        if link.is_expired(now):
            raise LinkExpired(code, link.expires_at)

        destination = link.original_url
        # Increment in SQL (not read-modify-write) so concurrent clicks
        # are never lost.
        self._db.execute(
            update(Link)
            .where(Link.id == link.id)
            .values(click_count=Link.click_count + 1, last_clicked_at=now)
        )
        self._db.commit()
        return destination

    def get_stats(self, code: str) -> Link:
        return self._get(code)

    def is_expired(self, link: Link) -> bool:
        return link.is_expired(self._clock())

    def _get(self, code: str) -> Link:
        link = self._db.scalar(select(Link).where(Link.code == code))
        if link is None:
            raise LinkNotFound(code)
        return link

    def _insert(
        self, code: str, url: str, now: datetime, expires_at: datetime | None
    ) -> Link:
        link = Link(code=code, original_url=url, created_at=now, expires_at=expires_at)
        self._db.add(link)
        try:
            self._db.commit()
        except IntegrityError:
            self._db.rollback()
            raise _CodeAlreadyExists() from None
        return link
