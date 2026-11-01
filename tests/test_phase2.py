"""Faz 2 kabul testleri: P2.1 karar akışı, P2.2 önizleme, P2.4 sayfalama, P2.5."""

import json

import pytest

from linevora.model import FakeModelClient

CONTENT = "DN50 santrifüj pompa, 10 adet"


def _auth(token):
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def processed(client, app, admin_token, inquiry_id):
    expected = {
        "requirements": [
            {
                "product_type": "santrifüj pompa",
                "features": {"DN": "50"},
                "quantity": 10,
                "unit": "adet",
                "source": {"page": 1, "quote": CONTENT},
            }
        ]
    }
    app.state.model_client = FakeModelClient(
        {f"Sayfa 1:\n{CONTENT}": json.dumps(expected, ensure_ascii=False)}
    )
    headers = _auth(admin_token)
    client.post(
        f"/v1/inquiries/{inquiry_id}/versions",
        files={"file": ("t.txt", CONTENT.encode())},
        headers=headers,
    )
    client.post(f"/v1/inquiries/{inquiry_id}/versions/1/process", headers=headers)
    data = client.get(
        f"/v1/inquiries/{inquiry_id}/versions/1/suggestions", headers=headers
    ).json()
    products = client.get("/v1/products", headers=headers).json()["products"]
    return {
        "inquiry_id": inquiry_id,
        "requirement_id": data["requirements"][0]["id"],
        "suggestion_id": data["suggestions"][0]["id"],
        "product_id": {p["code"]: p["id"] for p in products}["P-001"],
        "headers": headers,
    }


def test_suggestion_decision_and_requirement_update(client, processed):
    headers = processed["headers"]
    decided = client.patch(
        f"/v1/suggestions/{processed['suggestion_id']}",
        json={"status": "onaylandı", "note": "uygun"},
        headers=headers,
    )
    assert decided.status_code == 200
    assert decided.json()["status"] == "onaylandı"
    assert decided.json()["source"]["quote"] == CONTENT
    bad = client.patch(
        f"/v1/suggestions/{processed['suggestion_id']}",
        json={"status": "belki"},
        headers=headers,
    )
    assert bad.status_code == 422
    updated = client.patch(
        f"/v1/requirements/{processed['requirement_id']}",
        json={"quantity": 12},
        headers=headers,
    )
    assert updated.status_code == 200
    assert updated.json()["quantity"] == 12


def test_gap_answer_and_mandatory_block(client, app, processed):
    headers = processed["headers"]
    # Zorunlu eksik elle eklenir, teklif bloklanır, yanıtlanınca açılır.
    version_id = app.state.inquiry_store.list_versions(processed["inquiry_id"])[0].id
    gap = app.state.gap_store.add(
        version_id=version_id,
        requirement_id=processed["requirement_id"],
        field="teslim",
        question="Teslim süresi?",
        severity="zorunlu",
    )
    blocked = client.post(
        f"/v1/inquiries/{processed['inquiry_id']}/versions/1/quotes",
        json={
            "lines": [
                {
                    "requirement_id": processed["requirement_id"],
                    "product_id": processed["product_id"],
                }
            ]
        },
        headers=headers,
    )
    assert blocked.status_code == 400
    answered = client.post(
        f"/v1/gaps/{gap.id}/answer",
        json={"status": "yanıtlandı", "answer": "4 hafta"},
        headers=headers,
    )
    assert answered.status_code == 200
    assert answered.json()["answer"] == "4 hafta"
    built = client.post(
        f"/v1/inquiries/{processed['inquiry_id']}/versions/1/quotes",
        json={
            "lines": [
                {
                    "requirement_id": processed["requirement_id"],
                    "product_id": processed["product_id"],
                }
            ]
        },
        headers=headers,
    )
    assert built.status_code == 201


def test_preview_does_not_change_status(client, processed):
    headers = processed["headers"]
    quote = client.post(
        f"/v1/inquiries/{processed['inquiry_id']}/versions/1/quotes",
        json={
            "lines": [
                {
                    "requirement_id": processed["requirement_id"],
                    "product_id": processed["product_id"],
                }
            ]
        },
        headers=headers,
    ).json()
    client.post(f"/v1/quotes/{quote['id']}/submit", headers=headers)
    client.post(f"/v1/quotes/{quote['id']}/approve", headers=headers)
    preview = client.get(f"/v1/quotes/{quote['id']}/preview", headers=headers)
    assert preview.status_code == 200
    assert preview.json()["status"] == "onaylandı"
    after = client.get(f"/v1/quotes/{quote['id']}", headers=headers)
    assert after.json()["status"] == "onaylandı"


def test_pagination_params(client, admin_token, inquiry_id):
    headers = _auth(admin_token)
    page = client.get("/v1/inquiries?limit=1&offset=0", headers=headers)
    assert page.status_code == 200
    assert page.json()["total"] >= 1
    assert len(page.json()["inquiries"]) == 1
    audit = client.get("/v1/audit?limit=2", headers=headers)
    assert audit.json()["total"] >= len(audit.json()["entries"])


def test_unit_normalization_and_token_estimate():
    from linevora.ingest.extract import Page
    from linevora.matching.extractor import extract_requirements
    from linevora.model.client import CallRecord

    pages = (Page(number=1, text="100 metre boru"),)
    payload = {
        "requirements": [
            {
                "product_type": "boru",
                "quantity": 100.0,
                "unit": "m",
                "source": {"page": 1, "quote": "100 metre boru"},
            }
        ]
    }
    client = FakeModelClient(
        {"Sayfa 1:\n100 metre boru": json.dumps(payload, ensure_ascii=False)}
    )
    result = extract_requirements(client, pages)
    assert result[0]["unit"] == "metre"
    assert result[0]["quantity"] == 100
    record = CallRecord("m", prompt_chars=400, response_chars=400, latency_ms=1, ok=True)
    assert record.estimated_tokens == 200
