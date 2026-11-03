"""Trust + speed additions: dashboard, company summary, listing trust, sorting."""

import pytest
from fastapi.testclient import TestClient

from linevora.audit.store import InMemoryAuditStore
from linevora.config import get_settings
from linevora.files.store import LocalBlobStore
from linevora.inquiries.store import InMemoryInquiryStore
from linevora.main import create_app
from linevora.model import FakeModelClient

USERS = (
    "buyer:buyer123:admin,"
    "supplier-a:supplier-a123:specialist,"
    "supplier-b:supplier-b123:specialist,"
    "outsider:outsider123:viewer"
)
PASSWORDS = {
    "buyer": "buyer123",
    "supplier-a": "supplier-a123",
    "supplier-b": "supplier-b123",
    "outsider": "outsider123",
}
DEMAND_TEXT = "Looking for 300 pcs galvanized pipe. Delivery to Istanbul, within two weeks."


@pytest.fixture
def client(monkeypatch, tmp_path):
    monkeypatch.setenv("LINEVORA_USERS", USERS)
    get_settings.cache_clear()
    app = create_app(
        audit_store=InMemoryAuditStore(),
        inquiry_store=InMemoryInquiryStore(),
        blob_store=LocalBlobStore(str(tmp_path / "blobs")),
        model_client=FakeModelClient({}),
        inline_jobs=True,
    )
    try:
        yield TestClient(app)
    finally:
        monkeypatch.undo()
        get_settings.cache_clear()


def _token(client, username):
    r = client.post("/v1/auth/token", json={"username": username, "password": PASSWORDS[username]})
    assert r.status_code == 200, r.text
    return r.json()["access_token"]


@pytest.fixture
def headers(client):
    return {n: {"Authorization": f"Bearer {_token(client, n)}"} for n in PASSWORDS}


def _publish(client, headers, text=DEMAND_TEXT, kind="demand", extra=None):
    body = {"kind": kind, "raw_text": text}
    if extra:
        body.update(extra)
    c = client.post("/v1/marketplace/listings", json=body, headers=headers)
    assert c.status_code == 201, c.text
    lid = c.json()["id"]
    p = client.post(f"/v1/marketplace/listings/{lid}/publish", json={"confirmed": True}, headers=headers)
    assert p.status_code == 200, p.text
    return p.json()


def _offer(client, headers, lid, price="100"):
    r = client.post(f"/v1/marketplace/listings/{lid}/offers", json={
        "lines": [{"quantity": "300", "unit": "pcs", "unit_price": price, "currency": "TRY"}],
        "tax_included": True, "shipping_included": True,
    }, headers=headers)
    assert r.status_code == 201, r.text
    return r.json()


def test_dashboard_counts_and_activity(client, headers):
    empty = client.get("/v1/marketplace/dashboard", headers=headers["buyer"])
    assert empty.status_code == 200, empty.text
    b = empty.json()
    assert b["my_listings"] == {"draft": 0, "published": 0, "awarded": 0, "closed": 0, "total": 0}
    assert b["offers_received_open"] == 0 and b["offers_sent_open"] == 0
    assert b["revision_requested"] == 0 and b["recent_activity"] == []

    listing = _publish(client, headers["buyer"])
    offer = _offer(client, headers["supplier-a"], listing["id"])

    buyer = client.get("/v1/marketplace/dashboard", headers=headers["buyer"]).json()
    assert buyer["my_listings"]["published"] == 1 and buyer["my_listings"]["total"] == 1
    assert buyer["offers_received_open"] == 1
    assert buyer["offers_sent_open"] == 0
    assert buyer["unread_notifications"] >= 1
    assert any(a["type"] in ("offer_received", "listing") for a in buyer["recent_activity"])
    assert all("timestamp" in a and ("text" in a or "description" in a) for a in buyer["recent_activity"])

    seller = client.get("/v1/marketplace/dashboard", headers=headers["supplier-a"]).json()
    assert seller["offers_sent_open"] == 1
    assert seller["offers_received_open"] == 0

    # revision flow
    client.post(f"/v1/marketplace/offers/{offer['id']}/request-revision",
                json={"note": "revision"}, headers=headers["buyer"])
    seller2 = client.get("/v1/marketplace/dashboard", headers=headers["supplier-a"]).json()
    assert seller2["revision_requested"] == 1
    assert seller2["offers_sent_open"] == 0


def test_dashboard_anonymous_401(client):
    assert client.get("/v1/marketplace/dashboard").status_code == 401
    assert client.get("/v1/marketplace/company/me").status_code == 401


def test_company_me_derived_no_fabrication(client, headers):
    r = client.get("/v1/marketplace/company/me", headers=headers["outsider"])
    assert r.status_code == 200, r.text
    b = r.json()
    assert b["company_id"] == "default"
    assert b["display_name"] == "outsider"  # tenant default -> username
    assert "tax" not in str(b).lower()
    assert b["stats"] == {"published_listings": 0, "agreements_completed": 0, "offers_sent": 0}
    assert b["trust"] == {"has_published": False, "has_agreement": False, "level": "new"}
    assert b["member_since"] is None or isinstance(b["member_since"], (int, float))

    _publish(client, headers["buyer"])
    b2 = client.get("/v1/marketplace/company/me", headers=headers["buyer"]).json()
    assert b2["trust"]["level"] == "active" and b2["trust"]["has_published"] is True
    assert b2["stats"]["published_listings"] == 1


def test_company_me_verified_after_agreement(client, headers):
    listing = _publish(client, headers["buyer"])
    offer = _offer(client, headers["supplier-a"], listing["id"])
    sel = client.post(f"/v1/marketplace/offers/{offer['id']}/select",
                      json={"confirmed": True}, headers=headers["buyer"])
    assert sel.status_code == 200, sel.text
    for who in ("buyer", "supplier-a"):
        b = client.get("/v1/marketplace/company/me", headers=headers[who]).json()
        assert b["trust"]["level"] == "verified", (who, b)
        assert b["trust"]["has_agreement"] is True
        assert b["stats"]["agreements_completed"] == 1
    dash = client.get("/v1/marketplace/dashboard", headers=headers["buyer"]).json()
    assert dash["my_listings"]["awarded"] == 1
    assert any(a["type"] == "agreement" for a in dash["recent_activity"])


def test_listing_detail_trust_signals_no_price_leak(client, headers):
    listing = _publish(client, headers["buyer"])
    offer = _offer(client, headers["supplier-a"], listing["id"], price="777")
    detail = client.get(f"/v1/marketplace/listings/{listing['id']}", headers=headers["supplier-b"])
    assert detail.status_code == 200, detail.text
    b = detail.json()
    comp = b.get("company") or b.get("owner_company") or {}
    assert comp.get("company_id") == b["company_id"]
    assert comp.get("level") in ("new", "active", "verified")
    assert comp.get("agreements_completed") == 0
    assert b.get("trust", {}).get("level") == comp.get("level")
    # a competing offer price does not leak into the detail
    assert "777" not in detail.text


def test_listings_sort_newest_delivery_and_open_only(client, headers):
    a = _publish(client, headers["buyer"], extra={"delivery_days": 30, "title": "old"})
    b_ = _publish(client, headers["buyer"], extra={"delivery_days": 5, "title": "fast"})
    c = _publish(client, headers["buyer"], extra={"delivery_days": 14, "title": "medium"})

    newest = client.get("/v1/marketplace/listings?sort=newest", headers=headers["supplier-a"]).json()["listings"]
    ids_new = [x["id"] for x in newest]
    assert ids_new.index(c["id"]) < ids_new.index(a["id"])  # last created first (time-resolution tolerance below as well)
    times = [x["created_at"] for x in newest]
    assert times == sorted(times, reverse=True)

    by_delivery = client.get("/v1/marketplace/listings?sort=delivery", headers=headers["supplier-a"]).json()["listings"]
    days = [x["delivery_days"] for x in by_delivery]
    assert days == sorted(days, key=lambda d: (d is None, d or 0))

    opened = client.get("/v1/marketplace/listings?open_only=true", headers=headers["supplier-a"]).json()["listings"]
    assert opened and all(x["status"] == "published" for x in opened)
    opened2 = client.get("/v1/marketplace/listings?only_open=true", headers=headers["supplier-a"]).json()["listings"]
    assert {x["id"] for x in opened2} == {x["id"] for x in opened}

    # the existing filters are not broken
    filtered = client.get("/v1/marketplace/listings?max_delivery_days=10", headers=headers["supplier-a"]).json()["listings"]
    assert [x["id"] for x in filtered] == [b_["id"]]
    plain = client.get("/v1/marketplace/listings", headers=headers["supplier-a"])
    assert plain.status_code == 200 and len(plain.json()["listings"]) == 3
