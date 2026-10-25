import pytest

from tests.conftest import create_link


def test_creates_link_with_generated_code(client):
    response = create_link(client, url="https://example.com/a/very/long/path")

    assert response.status_code == 201
    body = response.json()
    assert len(body["code"]) == 7
    assert body["short_url"] == f"http://short.test/{body['code']}"
    assert body["original_url"] == "https://example.com/a/very/long/path"
    assert body["expires_at"] is None


def test_generated_codes_are_unique(client):
    codes = {create_link(client).json()["code"] for _ in range(25)}
    assert len(codes) == 25


def test_custom_alias_is_used_as_code(client):
    response = create_link(client, alias="spring-sale")

    assert response.status_code == 201
    assert response.json()["code"] == "spring-sale"
    assert response.json()["short_url"] == "http://short.test/spring-sale"


def test_duplicate_alias_is_rejected_with_helpful_error(client):
    create_link(client, alias="promo")

    response = create_link(client, url="https://other.example.org", alias="promo")

    assert response.status_code == 409
    error = response.json()["error"]
    assert error["code"] == "alias_taken"
    assert "'promo' is already in use" in error["message"]


def test_duplicate_alias_does_not_overwrite_existing_link(client):
    create_link(client, url="https://first.example.com", alias="promo")
    create_link(client, url="https://second.example.com", alias="promo")

    response = client.get("/promo")

    assert response.headers["location"] == "https://first.example.com"


def test_aliases_are_case_sensitive(client):
    assert create_link(client, alias="Promo").status_code == 201
    assert create_link(client, alias="promo").status_code == 201


@pytest.mark.parametrize(
    "alias, expected_fragment",
    [
        ("ab", "3-32 characters"),
        ("x" * 33, "3-32 characters"),
        ("has space", "letters, digits"),
        ("bad/slash", "letters, digits"),
        ("emoji-😀", "letters, digits"),
        ("", "3-32 characters"),
        ("links", "reserved"),
        ("DOCS", "reserved"),
    ],
)
def test_invalid_alias_is_rejected(client, alias, expected_fragment):
    response = create_link(client, alias=alias)

    assert response.status_code == 422
    error = response.json()["error"]
    assert error["code"] == "validation_error"
    assert error["details"][0]["field"] == "alias"
    assert expected_fragment in error["details"][0]["message"]


@pytest.mark.parametrize(
    "url",
    [
        "not a url",
        "example.com",  # missing scheme
        "ftp://example.com/file",
        "javascript:alert(1)",
        "http://",
        "http://nodots",
        "https://exa mple.com",
        "https://example.com:99999",
        "",
    ],
)
def test_invalid_url_is_rejected(client, url):
    response = create_link(client, url=url)

    assert response.status_code == 422
    error = response.json()["error"]
    assert error["code"] == "validation_error"
    assert error["details"][0]["field"] == "url"


def test_missing_url_is_rejected(client):
    response = client.post("/links", json={})

    assert response.status_code == 422
    assert response.json()["error"]["details"][0]["field"] == "url"


@pytest.mark.parametrize(
    "url", ["http://localhost:8000/path", "http://127.0.0.1/x", "https://example.com"]
)
def test_valid_urls_are_accepted(client, url):
    assert create_link(client, url=url).status_code == 201


def test_expiry_in_the_past_is_rejected(client, clock):
    past = (clock.now.replace(year=2025)).isoformat()

    response = create_link(client, expires_at=past)

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "invalid_expiry"


def test_expiry_equal_to_now_is_rejected(client, clock):
    response = create_link(client, expires_at=clock.now.isoformat())

    assert response.status_code == 422


def test_expiry_without_timezone_is_treated_as_utc(client):
    response = create_link(client, expires_at="2026-06-01T00:00:00")

    assert response.status_code == 201
    assert response.json()["expires_at"] == "2026-06-01T00:00:00Z"


def test_random_code_collision_is_retried(client, monkeypatch):
    create_link(client, alias="taken01")
    candidates = iter(["taken01", "fresh01"])
    monkeypatch.setattr("app.services.generate_code", lambda: next(candidates))

    response = create_link(client)

    assert response.status_code == 201
    assert response.json()["code"] == "fresh01"
