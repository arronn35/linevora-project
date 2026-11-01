"""Belirteç üretimi ve doğrulama."""

from linevora.auth.tokens import issue_token
from linevora.config import get_settings


def test_token_issue_and_me(client):
    response = client.post(
        "/v1/auth/token", json={"username": "uzman", "password": "uzman123"}
    )
    assert response.status_code == 200
    token = response.json()["access_token"]
    me = client.get("/v1/me", headers={"Authorization": f"Bearer {token}"})
    assert me.status_code == 200
    assert me.json() == {"username": "uzman", "roles": ["specialist"]}


def test_token_wrong_password(client):
    response = client.post(
        "/v1/auth/token", json={"username": "uzman", "password": "yanlis"}
    )
    assert response.status_code == 401


def test_token_unknown_user(client):
    response = client.post(
        "/v1/auth/token", json={"username": "kimse", "password": "ne"}
    )
    assert response.status_code == 401


def test_me_without_token(client):
    assert client.get("/v1/me").status_code == 401


def test_me_tampered_token(client, viewer_token):
    bad = viewer_token[:-1] + ("a" if viewer_token[-1] != "a" else "b")
    response = client.get("/v1/me", headers={"Authorization": f"Bearer {bad}"})
    assert response.status_code == 401


def test_me_expired_token(client):
    secret = get_settings().secret_key
    token = issue_token(secret, "admin", ["admin"], ttl_seconds=-1)
    response = client.get("/v1/me", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 401
