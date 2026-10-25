from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app


class FakeClock:
    """A controllable "now" so expiry and last-clicked can be tested exactly."""

    def __init__(self):
        self.now = datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc)

    def __call__(self) -> datetime:
        return self.now

    def advance(self, **kwargs) -> None:
        self.now += timedelta(**kwargs)


@pytest.fixture
def clock() -> FakeClock:
    return FakeClock()


@pytest.fixture
def client(tmp_path, clock):
    settings = Settings(
        database_url=f"sqlite:///{tmp_path / 'test.db'}",
        base_url="http://short.test",
    )
    app = create_app(settings, clock=clock)
    # follow_redirects=False so tests can assert on the 307 itself.
    with TestClient(app, follow_redirects=False) as test_client:
        yield test_client


def create_link(client: TestClient, **body):
    """Helper: POST /links with `url` defaulting to a valid value."""
    body.setdefault("url", "https://example.com/some/long/path?x=1")
    return client.post("/links", json=body)
