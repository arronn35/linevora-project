"""Health endpoint."""

from linevora import __version__


def test_health_ok(client):
    response = client.get("/v1/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "version": __version__}
