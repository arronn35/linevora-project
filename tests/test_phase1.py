"""Faz 1 kabul testleri: P1.1 grounding, P1.3, P1.4, P1.5."""

import json

import pytest

from linevora.ingest.extract import Page
from linevora.matching.extractor import extract_requirements, quote_in_page
from linevora.matching.store import InMemoryRequirementStore
from linevora.model import FakeModelClient
from linevora.model.schemas import SchemaValidationError


def test_quote_grounding_rejects_fabricated_quote():
    pages = (Page(number=1, text="DN50 santrifüj pompa, 10 adet"),)
    prompt = "Sayfa 1:\nDN50 santrifüj pompa, 10 adet"
    bad = {
        "requirements": [
            {
                "product_type": "santrifüj pompa",
                "quantity": 10,
                "unit": "adet",
                "source": {"page": 1, "quote": "bu metin belgede yok"},
            }
        ]
    }
    client = FakeModelClient({prompt: json.dumps(bad, ensure_ascii=False)})
    with pytest.raises(SchemaValidationError):
        extract_requirements(client, pages)
    assert quote_in_page("DN50 santrifüj pompa", pages[0].text)
    assert not quote_in_page("yok", pages[0].text)


def test_requirement_store_requires_source():
    store = InMemoryRequirementStore()
    with pytest.raises(ValueError):
        store.add(version_id="v1", product_type="pompa", quote="")
    with pytest.raises(ValueError):
        store.add(version_id="v1", product_type="pompa", page=0, quote="alıntı")
    ok = store.add(version_id="v1", product_type="pompa", page=1, quote="alıntı")
    assert ok.quote == "alıntı"


def test_fabricated_quote_produces_no_suggestions(client, app, admin_token, inquiry_id):
    content = "DN50 santrifüj pompa, 10 adet"
    bad = {
        "requirements": [
            {
                "product_type": "santrifüj pompa",
                "quantity": 10,
                "unit": "adet",
                "source": {"page": 1, "quote": "uydurma alıntı"},
            }
        ]
    }
    app.state.model_client = FakeModelClient(
        {f"Sayfa 1:\n{content}": json.dumps(bad, ensure_ascii=False)}
    )
    headers = {"Authorization": f"Bearer {admin_token}"}
    up = client.post(
        f"/v1/inquiries/{inquiry_id}/versions",
        files={"file": ("t.txt", content.encode())},
        headers=headers,
    )
    assert up.status_code == 201
    job = client.post(
        f"/v1/inquiries/{inquiry_id}/versions/1/process", headers=headers
    )
    status = client.get(f"/v1/jobs/{job.json()['job_id']}", headers=headers)
    assert status.json()["status"] == "failed"
    suggestions = client.get(
        f"/v1/inquiries/{inquiry_id}/versions/1/suggestions", headers=headers
    )
    assert suggestions.json()["requirements"] == []


def test_pdf_magic_byte_required(client, admin_token, inquiry_id):
    headers = {"Authorization": f"Bearer {admin_token}"}
    response = client.post(
        f"/v1/inquiries/{inquiry_id}/versions",
        files={"file": ("sahte.pdf", b"aslinda metin")},
        headers=headers,
    )
    assert response.status_code == 415


def test_prod_app_requires_persistence_and_hashed_passwords(monkeypatch, tmp_path):
    from linevora.config import get_settings
    from linevora.main import create_app

    monkeypatch.setenv("LINEVORA_ENV", "prod")
    monkeypatch.setenv("LINEVORA_SECRET_KEY", "guclu-anahtar")
    monkeypatch.setenv("LINEVORA_USERS", "patron:düzparola:admin")
    get_settings.cache_clear()
    try:
        with pytest.raises(RuntimeError):
            create_app()
        monkeypatch.setenv("LINEVORA_DB_PATH", str(tmp_path / "x.db"))
        get_settings.cache_clear()
        with pytest.raises(RuntimeError):
            create_app()
    finally:
        monkeypatch.undo()
        get_settings.cache_clear()


def test_invalid_matcher_fails_fast(monkeypatch):
    from linevora.config import get_settings
    from linevora.main import create_app

    monkeypatch.setenv("LINEVORA_MATCHER", "bilinmeyen")
    get_settings.cache_clear()
    try:
        with pytest.raises(ValueError):
            create_app()
    finally:
        monkeypatch.undo()
        get_settings.cache_clear()
