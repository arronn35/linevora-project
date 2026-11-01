"""Adım 9: kalıcılık, model bağdaştırıcısı, anlamsal eşleştirme, güvenlik, PDF."""

import io
import json

import pytest

from linevora.auth.passwords import hash_password, is_hashed, verify_password
from linevora.catalog.models import Product
from linevora.inquiries.store import InMemoryInquiryStore
from linevora.matching.models import Requirement
from linevora.matching.vector_matcher import HybridMatcher, VectorMatcher
from linevora.model.client import HttpModelClient, ModelError
from linevora.observability.middleware import RateLimiter
from linevora.persistence import wrap_store
from linevora.quotes.pdf import render_quote_pdf


def _auth(token):
    return {"Authorization": f"Bearer {token}"}


# --- Faz 1: kalıcılık ---


def test_sqlite_store_survives_restart(tmp_path):
    db = str(tmp_path / "linevora.db")
    first = wrap_store(InMemoryInquiryStore(), db, "inquiries")
    created = first.create_inquiry("Acme", "Pompa")
    second = wrap_store(InMemoryInquiryStore(), db, "inquiries")
    assert second.get_inquiry(created.id).customer == "Acme"
    assert [item.id for item in second.list()] == [created.id]


# --- Faz 2: gerçek model bağdaştırıcısı ---


class _FakeResponse(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def test_http_model_client_parses_chat_response():
    def opener(request, timeout):
        assert timeout == 5
        body = json.loads(request.data.decode())
        assert body["messages"][1]["content"] == "soru"
        payload = {"choices": [{"message": {"content": '{"requirements": []}'}}]}
        return _FakeResponse(json.dumps(payload).encode())

    client = HttpModelClient(
        "https://example.invalid/v1/chat/completions",
        api_key="k",
        model="m",
        timeout_seconds=5,
        opener=opener,
    )
    assert client.complete("sistem", "soru") == '{"requirements": []}'
    assert client.name == "http:m"


def test_http_model_client_raises_after_retries():
    def opener(request, timeout):
        raise OSError("ağ yok")

    client = HttpModelClient(
        "https://example.invalid/v1", max_attempts=2, opener=opener
    )
    with pytest.raises(ModelError):
        client.complete("s", "u")


# --- Faz 3: anlamsal eşleştirme ---


def test_vector_matcher_finds_related_product():
    product = Product(
        id="p1",
        code="V-001",
        names=("küresel vana",),
        synonyms=("kesme vanası", "shut-off valve"),
        features={"DN": "25"},
    )
    other = Product(id="p2", code="P-009", names=("santrifüj pompa",))
    requirement = Requirement(
        id="r1", version_id="v1", product_type="kesme vanası", features={"DN": "25"}
    )
    results = VectorMatcher().suggest(requirement, [other, product])
    assert results and results[0].product.id == "p1"
    hybrid = HybridMatcher().suggest(requirement, [other, product])
    assert hybrid and hybrid[0].product.id == "p1"


# --- Faz 4: güvenlik ---


def test_password_hash_roundtrip_and_plain_compat():
    stored = hash_password("gizli123")
    assert is_hashed(stored)
    assert verify_password(stored, "gizli123")
    assert not verify_password(stored, "yanlış")
    assert verify_password("düz-metin", "düz-metin")
    assert not verify_password("düz-metin", "başka")


def test_token_revocation_flow(client, admin_token):
    assert client.get("/v1/me", headers=_auth(admin_token)).status_code == 200
    assert (
        client.post("/v1/auth/revoke", headers=_auth(admin_token)).status_code == 200
    )
    assert client.get("/v1/me", headers=_auth(admin_token)).status_code == 401


def test_rate_limit_on_token_endpoint(client, app):
    app.state.rate_limiter = RateLimiter(per_minute=2)
    statuses = [
        client.post(
            "/v1/auth/token", json={"username": "admin", "password": "admin123"}
        ).status_code
        for _ in range(3)
    ]
    assert statuses[-1] == 429


# --- Faz 5: PDF çıktısı ---


def test_render_quote_pdf_bytes():
    pdf = render_quote_pdf(
        {
            "customer": "Acme",
            "title": "Pompa teklifi",
            "quote_id": "q1",
            "status": "onaylandı",
            "lines": [
                {"product_code": "P-001", "quantity": 10, "amount": 100, "currency": "TRY"}
            ],
            "totals": [{"currency": "TRY", "amount": 100}],
            "terms": {"name": "Standart", "text": "30 gün"},
            "prepared_by": "admin",
            "approved_by": "admin",
        }
    )
    assert pdf.startswith(b"%PDF")
    assert len(pdf) > 200


def test_pdf_export_endpoint_requires_approval_and_returns_pdf(
    client, app, admin_token, inquiry_id
):
    from linevora.model import FakeModelClient

    content = "DN50 santrifüj pompa, 10 adet"
    expected = {
        "requirements": [
            {
                "product_type": "santrifüj pompa",
                "features": {"DN": "50"},
                "quantity": 10,
                "unit": "adet",
                "source": {"page": 1, "quote": content},
            }
        ]
    }
    app.state.model_client = FakeModelClient(
        responses={f"Sayfa 1:\n{content}": json.dumps(expected, ensure_ascii=False)}
    )
    upload = client.post(
        f"/v1/inquiries/{inquiry_id}/versions",
        files={"file": ("t.txt", content.encode())},
        headers=_auth(admin_token),
    )
    assert upload.status_code == 201
    client.post(
        f"/v1/inquiries/{inquiry_id}/versions/1/process", headers=_auth(admin_token)
    )
    suggestions = client.get(
        f"/v1/inquiries/{inquiry_id}/versions/1/suggestions",
        headers=_auth(admin_token),
    )
    req_id = suggestions.json()["requirements"][0]["id"]
    products = client.get("/v1/products", headers=_auth(admin_token)).json()["products"]
    product_id = {p["code"]: p["id"] for p in products}["P-001"]
    quote = client.post(
        f"/v1/inquiries/{inquiry_id}/versions/1/quotes",
        json={"lines": [{"requirement_id": req_id, "product_id": product_id}]},
        headers=_auth(admin_token),
    ).json()
    # Onaysız PDF de engellenir.
    assert (
        client.get(
            f"/v1/quotes/{quote['id']}/export.pdf", headers=_auth(admin_token)
        ).status_code
        == 400
    )
    client.post(f"/v1/quotes/{quote['id']}/submit", headers=_auth(admin_token))
    client.post(f"/v1/quotes/{quote['id']}/approve", headers=_auth(admin_token))
    response = client.get(
        f"/v1/quotes/{quote['id']}/export.pdf", headers=_auth(admin_token)
    )
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/pdf")
    assert response.content.startswith(b"%PDF")
