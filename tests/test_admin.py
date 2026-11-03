"""Demo model scripting (dev only)."""

import json

from linevora.config import get_settings

CONTENT = "DN50 centrifugal pump, 2 pcs"
EXPECTED = {
    "requirements": [
        {
            "product_type": "centrifugal pump",
            "features": {"DN": "50"},
            "quantity": 2,
            "unit": "pcs",
            "source": {"page": 1, "quote": CONTENT},
        }
    ]
}


def _auth(token):
    return {"Authorization": f"Bearer {token}"}


def test_demo_model_enables_processing(client, admin_token, inquiry_id):
    scripts = {f"Page 1:\n{CONTENT}": json.dumps(EXPECTED, ensure_ascii=False)}
    response = client.post(
        "/v1/admin/demo-model", json={"scripts": scripts}, headers=_auth(admin_token)
    )
    assert response.json() == {"scripted": 1}
    upload = client.post(
        f"/v1/inquiries/{inquiry_id}/versions",
        files={"file": ("t.txt", CONTENT.encode("utf-8"))},
        headers=_auth(admin_token),
    )
    assert upload.status_code == 201
    process = client.post(
        f"/v1/inquiries/{inquiry_id}/versions/1/process", headers=_auth(admin_token)
    )
    assert process.json()["status"] == "done"
    suggestions = client.get(
        f"/v1/inquiries/{inquiry_id}/versions/1/suggestions",
        headers=_auth(admin_token),
    ).json()
    assert suggestions["suggestions"][0]["product"]["code"] == "P-001"


def test_demo_model_admin_only(client, viewer_token):
    response = client.post(
        "/v1/admin/demo-model",
        json={"scripts": {}},
        headers=_auth(viewer_token),
    )
    assert response.status_code == 403


def test_demo_model_blocked_in_prod(client, monkeypatch):
    monkeypatch.setenv("LINEVORA_ENV", "prod")
    monkeypatch.setenv("LINEVORA_SECRET_KEY", "x-key")
    monkeypatch.setenv("LINEVORA_USERS", "boss:s3cret:admin")
    get_settings.cache_clear()
    try:
        login = client.post(
            "/v1/auth/token", json={"username": "boss", "password": "s3cret"}
        )
        token = login.json()["access_token"]
        response = client.post(
            "/v1/admin/demo-model",
            json={"scripts": {}},
            headers=_auth(token),
        )
        assert response.status_code == 403
    finally:
        monkeypatch.undo()
        get_settings.cache_clear()
