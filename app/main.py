"""Application factory and ASGI entrypoint (`uvicorn app.main:app`)."""

from contextlib import asynccontextmanager

from fastapi import FastAPI

from app import models  # noqa: F401  (registers tables on Base.metadata)
from app.api import router
from app.clock import Clock, utc_now
from app.config import Settings
from app.db import Base, make_engine, make_session_factory
from app.errors import register_error_handlers


def create_app(settings: Settings | None = None, clock: Clock = utc_now) -> FastAPI:
    settings = settings or Settings.from_env()
    engine = make_engine(settings.database_url)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        Base.metadata.create_all(engine)
        yield
        engine.dispose()

    app = FastAPI(
        title="URL Shortener",
        version="1.0.0",
        description="Create short links, redirect, expire them and count clicks.",
        lifespan=lifespan,
    )
    app.state.settings = settings
    app.state.clock = clock
    app.state.session_factory = make_session_factory(engine)

    register_error_handlers(app)
    app.include_router(router)
    return app


app = create_app()
