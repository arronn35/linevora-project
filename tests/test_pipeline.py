"""End to end: version processing → job → suggestions."""

import json

from linevora.model import FakeModelClient

CONTENT = "DN50 centrifugal pump, 10 pcs"
EXPECTED = {
    "requirements": [
        {
            "product_type": "centrifugal pump",
            "features": {"DN": "50"},
            "quantity": 10,
            "unit": "pcs",
            "source": {"page": 1, "quote": CONTENT},
        }
    ]
}


def _auth(token):
    return {"Authorization": f"Bearer {token}"}


def _script(app):
    app.state.model_client = FakeModelClient(
        responses={f"Page 1:\n{CONTENT}": json.dumps(EXPECTED, ensure_ascii=False)}
    )


def _upload(client, token, inquiry_id):
    return client.post(
        f"/v1/inquiries/{inquiry_id}/versions",
        files={"file": ("inquiry.txt", CONTENT.encode("utf-8"))},
        headers=_auth(token),
    )


def test_process_version_to_suggestions(client, app, admin_token, inquiry_id):
    _script(app)
    assert _upload(client, admin_token, inquiry_id).status_code == 201
    process = client.post(
        f"/v1/inquiries/{inquiry_id}/versions/1/process", headers=_auth(admin_token)
    )
    assert process.status_code == 202
    assert process.json()["status"] == "done"
    job = client.get(f"/v1/jobs/{process.json()['job_id']}", headers=_auth(admin_token))
    assert job.status_code == 200
    assert job.json()["result"] == {
        "requirements": 1,
        "suggestions": 2,
        "gaps": 0,
        "alternatives": 0,
    }
    suggestions = client.get(
        f"/v1/inquiries/{inquiry_id}/versions/1/suggestions",
        headers=_auth(admin_token),
    )
    assert suggestions.status_code == 200
    body = suggestions.json()
    assert len(body["requirements"]) == 1
    assert body["requirements"][0]["source"] == {"page": 1, "quote": CONTENT}
    top = body["suggestions"][0]
    assert top["product"]["code"] == "P-001"
    assert top["score"] > 0.7
    assert top["status"] == "pending"


def test_reprocess_replaces_not_duplicates(client, app, admin_token, inquiry_id):
    _script(app)
    assert _upload(client, admin_token, inquiry_id).status_code == 201
    url = f"/v1/inquiries/{inquiry_id}/versions/1/process"
    assert client.post(url, headers=_auth(admin_token)).status_code == 202
    assert client.post(url, headers=_auth(admin_token)).status_code == 202
    suggestions = client.get(
        f"/v1/inquiries/{inquiry_id}/versions/1/suggestions",
        headers=_auth(admin_token),
    )
    assert len(suggestions.json()["requirements"]) == 1


def test_process_unknown_version_404(client, admin_token, inquiry_id):
    response = client.post(
        f"/v1/inquiries/{inquiry_id}/versions/9/process", headers=_auth(admin_token)
    )
    assert response.status_code == 404


def test_job_unknown_404(client, admin_token):
    assert client.get("/v1/jobs/missing", headers=_auth(admin_token)).status_code == 404


def test_viewer_cannot_process_but_can_read(
    client, app, admin_token, viewer_token, inquiry_id
):
    _script(app)
    assert _upload(client, admin_token, inquiry_id).status_code == 201
    process = client.post(
        f"/v1/inquiries/{inquiry_id}/versions/1/process", headers=_auth(viewer_token)
    )
    assert process.status_code == 403
    suggestions = client.get(
        f"/v1/inquiries/{inquiry_id}/versions/1/suggestions",
        headers=_auth(viewer_token),
    )
    assert suggestions.status_code == 200
    assert suggestions.json() == {"requirements": [], "suggestions": []}


def test_unconfigured_model_fails_job(client, app, admin_token, inquiry_id):
    _ = app
    assert _upload(client, admin_token, inquiry_id).status_code == 201
    process = client.post(
        f"/v1/inquiries/{inquiry_id}/versions/1/process", headers=_auth(admin_token)
    )
    assert process.json()["status"] == "failed"
    job = client.get(f"/v1/jobs/{process.json()['job_id']}", headers=_auth(admin_token))
    assert job.json()["attempts"] == 3
    assert "unscripted" in (job.json()["error"] or "")
