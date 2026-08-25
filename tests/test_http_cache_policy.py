from __future__ import annotations


def test_api_responses_are_not_cached_between_local_and_tunnel_clients(client) -> None:
    response = client.get("/api/v1/health")

    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store, no-cache, must-revalidate, max-age=0"
