"""Anlık görüntü: kaydetme, yükleme, kuşak rotasyonu, geri yükleme."""

import json
import os
import shutil

from fastapi.testclient import TestClient

from linevora.audit.store import InMemoryAuditStore
from linevora.files.store import LocalBlobStore
from linevora.inquiries.store import InMemoryInquiryStore
from linevora.main import create_app
from linevora.model import FakeModelClient
from linevora.observability import SnapshotManager
from linevora.reports.store import InMemoryGapStore

CONTENT = "DN50 santrifüj pompa, 10 adet"


def _login(client):
    response = client.post(
        "/v1/auth/token", json={"username": "admin", "password": "admin123"}
    )
    return response.json()["access_token"]


def _scripted_client():
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
    return FakeModelClient(
        responses={f"Sayfa 1:\n{CONTENT}": json.dumps(expected, ensure_ascii=False)}
    )


def _full_flow(client, token):
    headers = {"Authorization": f"Bearer {token}"}
    inquiry = client.post(
        "/v1/inquiries",
        json={"customer": "Acme", "title": "Pompa"},
        headers=headers,
    ).json()["id"]
    client.post(
        f"/v1/inquiries/{inquiry}/versions",
        files={"file": ("t.txt", CONTENT.encode("utf-8"))},
        headers=headers,
    )
    process = client.post(
        f"/v1/inquiries/{inquiry}/versions/1/process", headers=headers
    ).json()
    assert process["status"] == "done"
    requirement = client.get(
        f"/v1/inquiries/{inquiry}/versions/1/suggestions", headers=headers
    ).json()["requirements"][0]["id"]
    products = {
        product["code"]: product["id"]
        for product in client.get("/v1/products", headers=headers).json()["products"]
    }
    quote = client.post(
        f"/v1/inquiries/{inquiry}/versions/1/quotes",
        json={
            "lines": [{"requirement_id": requirement, "product_id": products["P-001"]}]
        },
        headers=headers,
    ).json()
    client.post(f"/v1/quotes/{quote['id']}/submit", headers=headers)
    client.post(f"/v1/quotes/{quote['id']}/approve", headers=headers)
    export = client.get(f"/v1/quotes/{quote['id']}/export", headers=headers).json()
    return inquiry, quote["id"], export


def test_snapshot_roundtrip_preserves_state(tmp_path):
    snap = str(tmp_path / "snap.json")
    app1 = create_app(
        audit_store=InMemoryAuditStore(),
        inquiry_store=InMemoryInquiryStore(),
        blob_store=LocalBlobStore(str(tmp_path / "b1")),
        model_client=_scripted_client(),
        inline_jobs=True,
        snapshot_path=snap,
    )
    first = TestClient(app1)
    token = _login(first)
    headers = {"Authorization": f"Bearer {token}"}
    inquiry_id, quote_id, export1 = _full_flow(first, token)
    model_calls = first.get("/v1/metrics", headers=headers).json()["model"]
    assert model_calls == {"calls": 1, "ok": 1, "failed": 0}
    saved = first.post("/v1/admin/snapshot", headers=headers)
    assert saved.json() == {"saved": True, "path": snap}
    # Yeni süreç, boş dosya dizini: durum yalnızca anlık görüntüden gelir.
    app2 = create_app(
        audit_store=InMemoryAuditStore(),
        inquiry_store=InMemoryInquiryStore(),
        blob_store=LocalBlobStore(str(tmp_path / "b2")),
        inline_jobs=True,
        snapshot_path=snap,
    )
    second = TestClient(app2)
    suggestions = second.get(
        f"/v1/inquiries/{inquiry_id}/versions/1/suggestions", headers=headers
    ).json()
    assert len(suggestions["requirements"]) == 1
    assert len(suggestions["suggestions"]) == 2
    quote = second.get(f"/v1/quotes/{quote_id}", headers=headers).json()
    assert quote["status"] == "dışa aktarıldı"
    assert quote["totals"] == export1["totals"]
    metrics = second.get("/v1/metrics", headers=headers).json()
    assert metrics["jobs"]["by_status"] == {"done": 1}
    assert metrics["quotes"]["exported"] == 1
    assert metrics["quotes"]["avg_approval_seconds"] is not None
    actions = [
        entry["action"]
        for entry in second.get("/v1/audit", headers=headers).json()["entries"]
    ]
    assert "quote.export" in actions
    products = second.get("/v1/products", headers=headers).json()["products"]
    assert len(products) == 5


def test_snapshot_requires_configuration(client, admin_token):
    response = client.post(
        "/v1/admin/snapshot", headers={"Authorization": f"Bearer {admin_token}"}
    )
    assert response.status_code == 400


def test_rotation_keeps_five_generations(tmp_path):
    live = str(tmp_path / "s.json")
    state = {"n": 0}
    manager = SnapshotManager(
        live, {"sayac": (lambda: dict(state), lambda data: state.update(data))}
    )
    for index in range(7):
        state["n"] = index
        manager.save()
    with open(live, encoding="utf-8") as handle:
        assert json.load(handle) == {"sayac": {"n": 6}}
    for index in (1, 2, 3, 4, 5):
        assert os.path.exists(f"{live}.{index}")
    assert not os.path.exists(f"{live}.6")
    with open(f"{live}.1", encoding="utf-8") as handle:
        assert json.load(handle) == {"sayac": {"n": 5}}


def test_restore_procedure(tmp_path):
    live = str(tmp_path / "s.json")
    store = InMemoryGapStore()
    manager = SnapshotManager(live, {"gaps": (store.to_snapshot, store.load_snapshot)})
    store.add(
        version_id="v", requirement_id="r", field="quantity",
        question="?", severity="zorunlu",
    )
    manager.save()
    shutil.copy(live, str(tmp_path / "backup.json"))
    store.add(
        version_id="v", requirement_id="r", field="unit",
        question="?", severity="zorunlu",
    )
    manager.save()
    assert len(store.list_for_version("v")) == 2
    shutil.copy(str(tmp_path / "backup.json"), live)
    fresh = InMemoryGapStore()
    SnapshotManager(live, {"gaps": (fresh.to_snapshot, fresh.load_snapshot)}).load()
    assert [gap.field for gap in fresh.list_for_version("v")] == ["quantity"]
