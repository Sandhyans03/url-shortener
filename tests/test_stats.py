from datetime import timedelta

from tests.conftest import create_link


def test_new_link_has_zero_clicks(client):
    code = create_link(client).json()["code"]

    response = client.get(f"/links/{code}/stats")

    assert response.status_code == 200
    body = response.json()
    assert body["code"] == code
    assert body["total_clicks"] == 0
    assert body["last_clicked_at"] is None
    assert body["is_expired"] is False


def test_each_redirect_counts_as_a_click(client):
    code = create_link(client).json()["code"]

    for _ in range(3):
        client.get(f"/{code}")

    assert client.get(f"/links/{code}/stats").json()["total_clicks"] == 3


def test_last_clicked_time_is_recorded(client, clock):
    code = create_link(client).json()["code"]

    client.get(f"/{code}")
    clock.advance(minutes=10)
    client.get(f"/{code}")

    stats = client.get(f"/links/{code}/stats").json()
    assert stats["last_clicked_at"] == "2026-01-01T12:10:00Z"


def test_clicks_are_counted_per_link(client):
    first = create_link(client, alias="first").json()["code"]
    second = create_link(client, alias="second").json()["code"]

    client.get(f"/{first}")
    client.get(f"/{first}")
    client.get(f"/{second}")

    assert client.get(f"/links/{first}/stats").json()["total_clicks"] == 2
    assert client.get(f"/links/{second}/stats").json()["total_clicks"] == 1


def test_viewing_stats_does_not_count_as_a_click(client):
    code = create_link(client).json()["code"]

    client.get(f"/links/{code}/stats")
    client.get(f"/links/{code}/stats")

    assert client.get(f"/links/{code}/stats").json()["total_clicks"] == 0


def test_failed_visits_are_not_counted(client, clock):
    code = create_link(
        client, expires_at=(clock.now + timedelta(minutes=1)).isoformat()
    ).json()["code"]
    client.get(f"/{code}")  # valid click
    clock.advance(minutes=2)

    assert client.get(f"/{code}").status_code == 410
    assert client.get("/nope").status_code == 404

    stats = client.get(f"/links/{code}/stats").json()
    assert stats["total_clicks"] == 1
    assert stats["last_clicked_at"] == "2026-01-01T12:00:00Z"


def test_stats_remain_available_for_expired_links(client, clock):
    code = create_link(
        client, expires_at=(clock.now + timedelta(minutes=1)).isoformat()
    ).json()["code"]
    clock.advance(minutes=5)

    response = client.get(f"/links/{code}/stats")

    assert response.status_code == 200
    assert response.json()["is_expired"] is True


def test_stats_for_unknown_code_returns_404(client):
    response = client.get("/links/missing/stats")

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "link_not_found"


def test_health_endpoint(client):
    assert client.get("/health").json() == {"status": "ok"}
