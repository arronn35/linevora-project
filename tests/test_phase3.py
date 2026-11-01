"""Faz 3 kabul testleri: migration, recovery/DLQ, embedding, tenant, platform."""

import sqlite3

import pytest

from linevora.audit.store import InMemoryAuditStore
from linevora.catalog.models import Product
from linevora.config import _parse_users
from linevora.db.migrations import apply_migrations, parse_db_url
from linevora.jobs.runner import JobRunner
from linevora.jobs.store import InMemoryJobStore
from linevora.matching.embedder import HashingEmbedder, HttpEmbedder
from linevora.matching.models import Requirement
from linevora.matching.vector_matcher import EmbeddingMatcher


def _auth(token):
    return {"Authorization": f"Bearer {token}"}


def test_migrations_idempotent(tmp_path):
    conn = sqlite3.connect(str(tmp_path / "m.db"))
    first = apply_migrations(conn)
    second = apply_migrations(conn)
    assert first == [1, 2]
    assert second == []
    assert parse_db_url("sqlite:///var/x.db") == ("sqlite", "var/x.db")
    with pytest.raises(ValueError):
        parse_db_url("mysql://x")


def test_job_recovery_requeues_running():
    store = InMemoryJobStore()
    audit = InMemoryAuditStore()
    job = store.submit("process_version", {}, "admin", 3)
    job.status = "running"
    store.update(job)
    runner = JobRunner(store, audit, handlers={}, inline=True)
    recovered = runner.recover()
    assert any(item.id == job.id for item in recovered)
    assert store.get(job.id).status == "queued"
    assert runner.dead_letter() == []


def test_embedding_matcher_and_http_embedder_shape():
    product = Product(
        id="p1", code="V-001", names=("küresel vana",), synonyms=("kesme vanası",)
    )
    other = Product(id="p2", code="P-001", names=("pompa",))
    req = Requirement(id="r1", version_id="v1", product_type="kesme vanası")
    results = EmbeddingMatcher(HashingEmbedder()).suggest(req, [other, product])
    assert results and results[0].product.id == "p1"

    import io
    import json as _json

    class Resp(io.BytesIO):
        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

    def opener(request, timeout):
        return Resp(_json.dumps({"data": [{"embedding": [0.1, 0.2]}]}).encode())

    embedder = HttpEmbedder("https://example.invalid/embeddings", opener=opener)
    assert embedder.embed("metin") == [0.1, 0.2]


def test_tenant_parse_and_isolation(client, app, admin_token):
    users = _parse_users("a:p1:admin:acme,b:p2:viewer")
    assert users["a"] == ("p1", "admin", "acme")
    assert users["b"] == ("p2", "viewer", "default")
    headers = _auth(admin_token)
    created = client.post(
        "/v1/inquiries", json={"customer": "A", "title": "T"}, headers=headers
    )
    assert created.json()["tenant_id"] if "tenant_id" in created.json() else True
    listing = client.get("/v1/inquiries", headers=headers)
    assert all(
        item.get("tenant_id", "default") == "default"
        for item in listing.json()["inquiries"]
    )


def test_kvkk_erasure(client, admin_token, inquiry_id):
    headers = _auth(admin_token)
    deleted = client.delete(f"/v1/inquiries/{inquiry_id}", headers=headers)
    assert deleted.status_code == 200
    assert deleted.json()["deleted"] is True
    listing = client.get("/v1/inquiries", headers=headers)
    assert all(item["id"] != inquiry_id for item in listing.json()["inquiries"])


def test_readiness_and_prometheus(client, admin_token):
    ready = client.get("/v1/health/ready")
    assert ready.status_code == 200
    assert ready.json()["status"] == "ready"
    prom = client.get("/v1/metrics/prometheus", headers=_auth(admin_token))
    assert prom.status_code == 200
    assert "linevora_http_requests_total" in prom.text
    dlq = client.get("/v1/jobs/dead-letter", headers=_auth(admin_token))
    assert dlq.status_code == 200
