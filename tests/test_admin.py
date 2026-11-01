"""Demo model betikleme (yalnızca dev)."""

import json

from linevora.config import get_settings

CONTENT = "DN50 santrifüj pompa, 2 adet"
EXPECTED = {
    "requirements": [
        {
            "product_type": "santrifüj pompa",
            "features": {"DN": "50"},
            "quantity": 2,
            "unit": "adet",
            "source": {"page": 1, "quote": CONTENT},
        }
    ]
}


def _auth(token):
    return {"Authorization": f"Bearer {token}"}


def test_demo_model_enables_processing(client, admin_token, inquiry_id):
    scripts = {f"Sayfa 1:\n{CONTENT}": json.dumps(EXPECTED, ensure_ascii=False)}
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
    monkeypatch.setenv("LINEVORA_SECRET_KEY", "x-anahtar")
    monkeypatch.setenv("LINEVORA_USERS", "patron:s3cret:admin")
    get_settings.cache_clear()
    try:
        login = client.post(
            "/v1/auth/token", json={"username": "patron", "password": "s3cret"}
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
