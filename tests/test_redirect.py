from datetime import timedelta

from tests.conftest import create_link


def test_redirects_to_original_url(client):
    code = create_link(client, url="https://example.com/a?b=1&c=two#frag").json()["code"]

    response = client.get(f"/{code}")

    assert response.status_code == 307
    # The stored URL is returned exactly as submitted (no normalisation).
    assert response.headers["location"] == "https://example.com/a?b=1&c=two#frag"


def test_unknown_code_returns_404_with_clear_message(client):
    response = client.get("/doesnotexist")

    assert response.status_code == 404
    error = response.json()["error"]
    assert error["code"] == "link_not_found"
    assert "doesnotexist" in error["message"]


def test_link_works_before_expiry_and_gone_after(client, clock):
    expires_at = clock.now + timedelta(hours=1)
    code = create_link(client, expires_at=expires_at.isoformat()).json()["code"]

    clock.advance(minutes=59)
    assert client.get(f"/{code}").status_code == 307

    clock.advance(minutes=2)
    response = client.get(f"/{code}")

    assert response.status_code == 410
    error = response.json()["error"]
    assert error["code"] == "link_expired"
    assert "expired" in error["message"]
    assert "2026-01-01 13:00:00 UTC" in error["message"]


def test_link_is_expired_exactly_at_expiry_time(client, clock):
    expires_at = clock.now + timedelta(minutes=5)
    code = create_link(client, expires_at=expires_at.isoformat()).json()["code"]

    clock.advance(minutes=5)

    assert client.get(f"/{code}").status_code == 410


def test_link_without_expiry_never_expires(client, clock):
    code = create_link(client).json()["code"]

    clock.advance(days=3650)

    assert client.get(f"/{code}").status_code == 307


def test_unknown_route_uses_same_error_shape(client):
    response = client.get("/a/b/c")

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "not_found"
