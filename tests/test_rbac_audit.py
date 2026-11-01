"""Rol kapıları ve denetim kaydı (Adım 2 kabulü)."""

import dataclasses

import pytest

from linevora.audit.store import InMemoryAuditStore


def test_audit_requires_admin(client, viewer_token):
    response = client.get("/v1/audit", headers={"Authorization": f"Bearer {viewer_token}"})
    assert response.status_code == 403


def test_audit_allows_admin_and_records(client, admin_token):
    response = client.get("/v1/audit", headers={"Authorization": f"Bearer {admin_token}"})
    assert response.status_code == 200
    actions = [entry["action"] for entry in response.json()["entries"]]
    assert "auth.token_issue" in actions
    assert "audit.read" in actions


def test_failed_login_is_audited(client, admin_token):
    client.post("/v1/auth/token", json={"username": "admin", "password": "yanlis"})
    response = client.get("/v1/audit", headers={"Authorization": f"Bearer {admin_token}"})
    failures = [
        entry
        for entry in response.json()["entries"]
        if entry["action"] == "auth.token_issue" and entry["detail"] == "hatalı kimlik"
    ]
    assert len(failures) == 1


def test_audit_entries_are_append_only():
    store = InMemoryAuditStore()
    entry = store.append(actor="admin", action="test", target="x")
    with pytest.raises(dataclasses.FrozenInstanceError):
        entry.action = "değişti"  # type: ignore[misc]
    assert store.list()[0].action == "test"
