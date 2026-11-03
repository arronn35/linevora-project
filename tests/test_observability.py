"""Observability and security headers."""

import pytest

from linevora.config import get_settings


def test_metrics_reflects_traffic(client, admin_token):
    client.get("/v1/health")
    client.get("/v1/health")
    response = client.get(
        "/v1/metrics", headers={"Authorization": f"Bearer {admin_token}"}
    )
    assert response.status_code == 200
    body = response.json()
    assert body["http"]["total"] >= 3
    assert body["http"]["by_class"]["2xx"] >= 3
    assert set(body) == {"http", "jobs", "model", "quotes"}
    assert body["quotes"]["avg_approval_seconds"] is None


def test_metrics_requires_admin(client, viewer_token):
    assert (
        client.get("/v1/metrics", headers={"Authorization": f"Bearer {viewer_token}"}).status_code
        == 403
    )
    assert client.get("/v1/metrics").status_code == 401


def test_request_id_header(client):
    plain = client.get("/v1/health")
    assert plain.headers["X-Request-ID"]
    echo = client.get("/v1/health", headers={"X-Request-ID": "trace-123"})
    assert echo.headers["X-Request-ID"] == "trace-123"


def test_security_headers(client):
    response = client.get("/v1/health")
    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert response.headers["X-Frame-Options"] == "DENY"
    assert response.headers["Referrer-Policy"] == "no-referrer"


def test_prod_requires_secrets(monkeypatch):
    monkeypatch.setenv("LINEVORA_ENV", "prod")
    get_settings.cache_clear()
    try:
        with pytest.raises(RuntimeError):
            get_settings()
    finally:
        monkeypatch.undo()
        get_settings.cache_clear()
    assert get_settings().env == "dev"


def test_prod_accepts_custom_secrets(monkeypatch):
    monkeypatch.setenv("LINEVORA_ENV", "prod")
    monkeypatch.setenv("LINEVORA_SECRET_KEY", "strong-key")
    monkeypatch.setenv("LINEVORA_USERS", "boss:s3cret:admin")
    get_settings.cache_clear()
    try:
        assert get_settings().env == "prod"
    finally:
        monkeypatch.undo()
        get_settings.cache_clear()
    assert get_settings().env == "dev"
