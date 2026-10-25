"""FastAPI dependencies. Shared state lives on `app.state` (see app.main)."""

from collections.abc import Iterator

from fastapi import Depends, Request
from sqlalchemy.orm import Session

from app.services import LinkService


def get_db(request: Request) -> Iterator[Session]:
    with request.app.state.session_factory() as session:
        yield session


def get_link_service(request: Request, db: Session = Depends(get_db)) -> LinkService:
    return LinkService(db, request.app.state.clock)
