"""Test fixtures: an isolated app, stores and file area for every test."""

import pytest
from fastapi.testclient import TestClient

from linevora.audit.store import InMemoryAuditStore
from linevora.files.store import LocalBlobStore
from linevora.inquiries.store import InMemoryInquiryStore
from linevora.main import create_app
from linevora.model import FakeModelClient


@pytest.fixture
def app(tmp_path):
    return create_app(
        audit_store=InMemoryAuditStore(),
        inquiry_store=InMemoryInquiryStore(),
        blob_store=LocalBlobStore(str(tmp_path / "blobs")),
        model_client=FakeModelClient({}),
        inline_jobs=True,
    )


@pytest.fixture
def client(app):
    return TestClient(app)


@pytest.fixture
def admin_token(client):
    response = client.post(
        "/v1/auth/token", json={"username": "admin", "password": "admin123"}
    )
    assert response.status_code == 200
    return response.json()["access_token"]


@pytest.fixture
def viewer_token(client):
    response = client.post(
        "/v1/auth/token", json={"username": "viewer", "password": "viewer123"}
    )
    assert response.status_code == 200
    return response.json()["access_token"]


@pytest.fixture
def inquiry_id(client, admin_token):
    response = client.post(
        "/v1/inquiries",
        json={"customer": "Acme", "title": "Pump quote"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert response.status_code == 201
    return response.json()["id"]
