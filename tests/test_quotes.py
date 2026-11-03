"""Quote engine and approval flow."""

import json

import pytest

from linevora.model import FakeModelClient

CONTENT = "DN50 centrifugal pump, 10 pcs"


def _auth(token):
    return {"Authorization": f"Bearer {token}"}


def _specialist_token(client):
    response = client.post(
        "/v1/auth/token", json={"username": "specialist", "password": "specialist123"}
    )
    assert response.status_code == 200
    return response.json()["access_token"]


@pytest.fixture
def prepared(client, app, admin_token, inquiry_id):
    expected = {
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
    app.state.model_client = FakeModelClient(
        responses={f"Page 1:\n{CONTENT}": json.dumps(expected, ensure_ascii=False)}
    )
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
    )
    products = client.get("/v1/products", headers=_auth(admin_token)).json()["products"]
    return {
        "inquiry_id": inquiry_id,
        "requirement_id": suggestions.json()["requirements"][0]["id"],
        "products": {product["code"]: product["id"] for product in products},
    }


def _build(client, token, prepared, **overrides):
    line = {
        "requirement_id": prepared["requirement_id"],
        "product_id": prepared["products"]["P-001"],
    }
    line.update(overrides)
    return client.post(
        f"/v1/inquiries/{prepared['inquiry_id']}/versions/1/quotes",
        json={"lines": [line]},
        headers=_auth(token),
    )


def test_quote_happy_path(client, admin_token, prepared):
    build = _build(client, admin_token, prepared)
    assert build.status_code == 201
    quote = build.json()
    assert quote["status"] == "draft"
    assert quote["lines"][0]["unit_price"] == 85000.0
    assert quote["lines"][0]["amount"] == 850000.0
    assert quote["totals"] == [{"currency": "TRY", "amount": 850000.0}]
    quote_id = quote["id"]
    submit = client.post(f"/v1/quotes/{quote_id}/submit", headers=_auth(admin_token))
    assert submit.json()["status"] == "in_review"
    approve = client.post(f"/v1/quotes/{quote_id}/approve", headers=_auth(admin_token))
    assert approve.json()["status"] == "approved"
    assert approve.json()["approved_by"] == "admin"
    export = client.get(f"/v1/quotes/{quote_id}/export", headers=_auth(admin_token))
    assert export.status_code == 200
    document = export.json()
    assert document["status"] == "exported"
    assert document["customer"] == "Acme"
    assert document["lines"][0]["product_code"] == "P-001"
    assert document["totals"] == [{"currency": "TRY", "amount": 850000.0}]
    assert "30 days" in document["terms"]["text"]
    assert document["prepared_by"] == "admin"
    assert document["approved_by"] == "admin"
    re_export = client.get(f"/v1/quotes/{quote_id}/export", headers=_auth(admin_token))
    assert re_export.json()["lines"] == document["lines"]


def test_export_requires_approval(client, admin_token, prepared):
    quote_id = _build(client, admin_token, prepared).json()["id"]
    assert (
        client.get(f"/v1/quotes/{quote_id}/export", headers=_auth(admin_token)).status_code
        == 400
    )
    client.post(f"/v1/quotes/{quote_id}/submit", headers=_auth(admin_token))
    assert (
        client.get(f"/v1/quotes/{quote_id}/export", headers=_auth(admin_token)).status_code
        == 400
    )
    client.post(f"/v1/quotes/{quote_id}/approve", headers=_auth(admin_token))
    assert (
        client.get(f"/v1/quotes/{quote_id}/export", headers=_auth(admin_token)).status_code
        == 200
    )


def test_approve_requires_admin_and_return_reopens(client, admin_token, prepared):
    specialist = _specialist_token(client)
    quote_id = _build(client, specialist, prepared).json()["id"]
    client.post(f"/v1/quotes/{quote_id}/submit", headers=_auth(specialist))
    assert (
        client.post(f"/v1/quotes/{quote_id}/approve", headers=_auth(specialist)).status_code
        == 403
    )
    returned = client.post(f"/v1/quotes/{quote_id}/return", headers=_auth(admin_token))
    assert returned.json()["status"] == "draft"
    edited = client.put(
        f"/v1/quotes/{quote_id}/lines",
        json={
            "lines": [
                {
                    "requirement_id": prepared["requirement_id"],
                    "product_id": prepared["products"]["P-001"],
                    "quantity": 5,
                }
            ]
        },
        headers=_auth(specialist),
    )
    assert edited.json()["lines"][0]["amount"] == 425000.0
    client.post(f"/v1/quotes/{quote_id}/submit", headers=_auth(specialist))
    approved = client.post(f"/v1/quotes/{quote_id}/approve", headers=_auth(admin_token))
    assert approved.json()["status"] == "approved"


def test_invalid_transitions_rejected(client, admin_token, prepared):
    quote_id = _build(client, admin_token, prepared).json()["id"]
    headers = _auth(admin_token)
    assert client.post(f"/v1/quotes/{quote_id}/approve", headers=headers).status_code == 400
    assert client.post(f"/v1/quotes/{quote_id}/return", headers=headers).status_code == 400
    client.post(f"/v1/quotes/{quote_id}/submit", headers=headers)
    assert client.post(f"/v1/quotes/{quote_id}/submit", headers=headers).status_code == 400
    edit = client.put(
        f"/v1/quotes/{quote_id}/lines",
        json={
            "lines": [
                {
                    "requirement_id": prepared["requirement_id"],
                    "product_id": prepared["products"]["P-001"],
                }
            ]
        },
        headers=headers,
    )
    assert edit.status_code == 400


def test_price_pinning_across_versions(client, admin_token, prepared):
    headers = _auth(admin_token)
    first_id = _build(client, admin_token, prepared).json()["id"]
    client.post(f"/v1/quotes/{first_id}/submit", headers=headers)
    client.post(f"/v1/quotes/{first_id}/approve", headers=headers)
    before = client.get(f"/v1/quotes/{first_id}/export", headers=headers).json()
    assert before["lines"][0]["unit_price"] == 85000.0
    created = client.post(
        "/v1/prices",
        json={"product_id": prepared["products"]["P-001"], "price": 90000.0, "currency": "TRY"},
        headers=headers,
    )
    assert created.status_code == 201
    activated = client.post(f"/v1/prices/{created.json()['id']}/activate", headers=headers)
    assert activated.json()["status"] == "active"
    after = client.get(f"/v1/quotes/{first_id}/export", headers=headers).json()
    assert after["lines"][0]["unit_price"] == 85000.0
    second_id = _build(client, admin_token, prepared).json()["id"]
    second = client.get(f"/v1/quotes/{second_id}", headers=headers).json()
    assert second["lines"][0]["unit_price"] == 90000.0


def test_terms_pinning_across_versions(client, admin_token, prepared):
    headers = _auth(admin_token)
    first_id = _build(client, admin_token, prepared).json()["id"]
    client.post(f"/v1/quotes/{first_id}/submit", headers=headers)
    client.post(f"/v1/quotes/{first_id}/approve", headers=headers)
    created = client.post(
        "/v1/terms", json={"name": "New Terms", "text": "Cash in advance."}, headers=headers
    )
    client.post(f"/v1/terms/{created.json()['id']}/activate", headers=headers)
    first = client.get(f"/v1/quotes/{first_id}/export", headers=headers).json()
    assert "30 days" in first["terms"]["text"]
    second_id = _build(client, admin_token, prepared).json()["id"]
    client.post(f"/v1/quotes/{second_id}/submit", headers=headers)
    client.post(f"/v1/quotes/{second_id}/approve", headers=headers)
    second = client.get(f"/v1/quotes/{second_id}/export", headers=headers).json()
    assert second["terms"]["text"] == "Cash in advance."


def test_build_requires_effective_price(client, admin_token, prepared):
    headers = _auth(admin_token)
    created = client.post(
        "/v1/products",
        json={"code": "T-001", "names": ["Test Product"]},
        headers=headers,
    )
    assert created.status_code == 201
    duplicate = client.post(
        "/v1/products", json={"code": "T-001", "names": ["Other"]}, headers=headers
    )
    assert duplicate.status_code == 400
    build = _build(client, admin_token, prepared, product_id=created.json()["id"])
    assert build.status_code == 400


def test_build_validations(client, admin_token, prepared):
    headers = _auth(admin_token)
    bogus = _build(client, admin_token, prepared, requirement_id="missing")
    assert bogus.status_code == 400
    unknown = _build(client, admin_token, prepared, product_id="missing")
    assert unknown.status_code == 404
    bad_quantity = _build(client, admin_token, prepared, quantity=0)
    assert bad_quantity.status_code == 400
    empty = client.post(
        f"/v1/inquiries/{prepared['inquiry_id']}/versions/1/quotes",
        json={"lines": []},
        headers=headers,
    )
    assert empty.status_code == 400


def test_quantity_override_wins(client, admin_token, prepared):
    build = _build(client, admin_token, prepared, quantity=3)
    assert build.json()["lines"][0]["amount"] == 255000.0


def test_roles_on_quote_surfaces(client, admin_token, viewer_token, prepared):
    quote_id = _build(client, admin_token, prepared).json()["id"]
    viewer_headers = _auth(viewer_token)
    assert (
        client.post(
            f"/v1/inquiries/{prepared['inquiry_id']}/versions/1/quotes",
            json={"lines": []},
            headers=viewer_headers,
        ).status_code
        == 403
    )
    assert client.get(f"/v1/quotes/{quote_id}", headers=viewer_headers).status_code == 200
    assert (
        client.get(f"/v1/quotes/{quote_id}/export", headers=viewer_headers).status_code
        == 403
    )
    assert (
        client.post(
            "/v1/prices",
            json={
                "product_id": prepared["products"]["P-001"],
                "price": 1.0,
                "currency": "TRY",
            },
            headers=viewer_headers,
        ).status_code
        == 403
    )


def test_list_quotes(client, admin_token, prepared):
    headers = _auth(admin_token)
    _build(client, admin_token, prepared)
    _build(client, admin_token, prepared)
    listing = client.get(
        f"/v1/inquiries/{prepared['inquiry_id']}/quotes", headers=headers
    )
    assert len(listing.json()["quotes"]) == 2
