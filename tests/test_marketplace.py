"""Marketplace acceptance tests: listing -> offer -> comparison -> selection.

The acceptance flow is verified in both the buying (demand) and selling
(supply) directions. The system never invents an unspecified price,
technical detail or payment term; publishing/sending happens only after
user approval; competing offers never see each other.
"""

from decimal import Decimal

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
    # Extra users with the existing pattern (LINEVORA_USERS + cache clearing).
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
    response = client.post(
        "/v1/auth/token",
        json={"username": username, "password": PASSWORDS[username]},
    )
    assert response.status_code == 200, response.text
    return response.json()["access_token"]


@pytest.fixture
def headers(client):
    return {
        name: {"Authorization": f"Bearer {_token(client, name)}"}
        for name in PASSWORDS
    }


def _publish_listing(client, headers, text=DEMAND_TEXT, kind="demand"):
    created = client.post(
        "/v1/marketplace/listings",
        json={"kind": kind, "raw_text": text},
        headers=headers,
    )
    assert created.status_code == 201, created.text
    listing = created.json()
    published = client.post(
        f"/v1/marketplace/listings/{listing['id']}/publish",
        json={"confirmed": True},
        headers=headers,
    )
    assert published.status_code == 200, published.text
    assert published.json()["status"] == "published"
    return published.json()


def _offer(client, headers, listing_id, body):
    response = client.post(
        f"/v1/marketplace/listings/{listing_id}/offers",
        json=body,
        headers=headers,
    )
    assert response.status_code == 201, response.text
    return response.json()


def _demand_with_two_offers(client, headers):
    """A published demand listing + offers in different currencies from two suppliers."""
    listing = _publish_listing(client, headers["buyer"])
    offer_a = _offer(client, headers["supplier-a"], listing["id"], {
        "lines": [{"quantity": "300", "unit": "pcs",
                   "unit_price": "100", "currency": "TRY"}],
        "tax_included": False,
    })
    offer_b = _offer(client, headers["supplier-b"], listing["id"], {
        "lines": [{"quantity": "300", "unit": "pcs",
                   "unit_price": "2.5", "currency": "USD"}],
        "tax_included": True, "shipping_included": True,
        "delivery_days": 10, "payment_terms": "upfront",
    })
    return listing, offer_a, offer_b


# (1) Parsing: only what is written in the text is extracted; no price is invented.
def test_parse_galvanized_pipe_no_fabricated_price(client, headers):
    response = client.post(
        "/v1/marketplace/parse-listing",
        json={"kind": "demand", "text": DEMAND_TEXT},
        headers=headers["buyer"],
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert Decimal(body["quantity"]) == Decimal("300")
    assert body["unit"] == "pcs"
    assert body["delivery_place"] == "Istanbul"
    assert body["delivery_days"] == 14
    assert body["product"] == "galvanized pipe"
    missing = set(body["missing_fields"])
    assert {"diameter", "length", "wall_thickness"} <= missing
    asked = {q["field"] for q in body["missing_questions"]}
    assert {"diameter", "length", "wall_thickness"} <= asked
    # An unspecified price is never invented.
    assert body.get("unit_price") is None
    assert body.get("price") is None
    assert "Information to be clarified" in body["document"]


# (2) The fileless publish flow works with two users.
def test_fileless_publish_flow_two_users(client, headers):
    created = client.post(
        "/v1/marketplace/listings",
        json={"kind": "demand", "raw_text": DEMAND_TEXT},
        headers=headers["buyer"],
    )
    assert created.status_code == 201, created.text
    listing = created.json()
    assert listing["status"] == "draft"
    # A draft is invisible in discovery and closed to others.
    discovered = client.get("/v1/marketplace/listings", headers=headers["supplier-a"])
    assert discovered.status_code == 200
    assert all(i["id"] != listing["id"] for i in discovered.json()["listings"])
    hidden = client.get(
        f"/v1/marketplace/listings/{listing['id']}", headers=headers["supplier-a"]
    )
    assert hidden.status_code == 404
    # After a confirmed publish, the second user sees the listing.
    published = client.post(
        f"/v1/marketplace/listings/{listing['id']}/publish",
        json={"confirmed": True},
        headers=headers["buyer"],
    )
    assert published.status_code == 200, published.text
    assert published.json()["status"] == "published"
    discovered = client.get("/v1/marketplace/listings", headers=headers["supplier-a"])
    assert any(i["id"] == listing["id"] for i in discovered.json()["listings"])


# (3) Two suppliers offer with their own prices; the catalog is not mandatory.
def test_two_suppliers_own_prices_catalog_optional(client, headers):
    listing, offer_a, offer_b = _demand_with_two_offers(client, headers)
    assert offer_a["offerer_user"] == "supplier-a"
    assert offer_b["offerer_user"] == "supplier-b"
    assert Decimal(offer_a["lines"][0]["unit_price"]) == Decimal("100")
    assert Decimal(offer_b["lines"][0]["unit_price"]) == Decimal("2.5")
    assert offer_a["status"] == "submitted"
    assert offer_b["status"] == "submitted"
    # A catalog price is only an optional pre-fill.
    other = _publish_listing(client, headers["buyer"])
    prefilled = _offer(client, headers["supplier-a"], other["id"], {
        "catalog_price": "120", "catalog_currency": "TRY",
    })
    assert Decimal(prefilled["lines"][0]["unit_price"]) == Decimal("120")
    assert Decimal(prefilled["total"]) == Decimal("36000")


# (4) Comparison: Decimal totals, missing shipping, comparable, no "best".
def test_comparison_totals_missing_costs_and_no_best(client, headers):
    listing, offer_a, offer_b = _demand_with_two_offers(client, headers)
    response = client.get(
        f"/v1/marketplace/listings/{listing['id']}/comparison",
        headers=headers["buyer"],
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert "best" not in body
    entries = {e["offer_id"]: e for e in body["offers"]}
    assert set(entries) == {offer_a["id"], offer_b["id"]}
    entry_a, entry_b = entries[offer_a["id"]], entries[offer_b["id"]]
    assert Decimal(entry_a["total"]) == Decimal("300") * Decimal("100")
    assert Decimal(entry_b["total"]) == Decimal("300") * Decimal("2.5")
    assert any("shipping" in cost for cost in entry_a["missing_costs"])
    assert entry_b["comparable"] is False
    assert any("currency" in reason for reason in entry_b["comparable_reasons"])
    assert all("best" not in entry for entry in entries.values())


# (5) Competitor isolation and anonymous access.
def test_competitor_isolation_and_anonymous_401(client, headers):
    listing, offer_a, offer_b = _demand_with_two_offers(client, headers)
    mine = client.get(
        f"/v1/marketplace/listings/{listing['id']}/offers",
        headers=headers["supplier-a"],
    )
    assert mine.status_code == 200
    visible = [o["id"] for o in mine.json()["offers"]]
    assert visible == [offer_a["id"]]
    assert offer_b["id"] not in visible
    third = client.get(
        f"/v1/marketplace/listings/{listing['id']}/offers",
        headers=headers["outsider"],
    )
    assert third.json()["offers"] == []
    owner = client.get(
        f"/v1/marketplace/listings/{listing['id']}/offers",
        headers=headers["buyer"],
    )
    assert {o["id"] for o in owner.json()["offers"]} == {offer_a["id"], offer_b["id"]}
    assert client.get("/v1/marketplace/listings").status_code == 401
    assert client.get(
        f"/v1/marketplace/listings/{listing['id']}/offers"
    ).status_code == 401


# (6) Revision request -> supplier revision -> revision_no increases.
def test_revision_flow_increments_revision_no(client, headers):
    listing, offer_a, _offer_b = _demand_with_two_offers(client, headers)
    requested = client.post(
        f"/v1/marketplace/offers/{offer_a['id']}/request-revision",
        json={"note": "Could you review the price?"},
        headers=headers["buyer"],
    )
    assert requested.status_code == 200, requested.text
    assert requested.json()["status"] == "revision_requested"
    revised = client.post(
        f"/v1/marketplace/offers/{offer_a['id']}/revise",
        json={
            "lines": [{"quantity": "300", "unit": "pcs",
                       "unit_price": "90", "currency": "TRY"}],
            "tax_included": False,
        },
        headers=headers["supplier-a"],
    )
    assert revised.status_code == 201, revised.text
    body = revised.json()
    assert body["revision_no"] == offer_a["revision_no"] + 1
    assert body["parent_offer_id"] == offer_a["id"]
    assert Decimal(body["total"]) == Decimal("27000")
    owner_view = client.get(
        f"/v1/marketplace/listings/{listing['id']}/offers",
        headers=headers["buyer"],
    )
    statuses = {o["id"]: o["status"] for o in owner_view.json()["offers"]}
    assert statuses[offer_a["id"]] == "withdrawn"
    assert statuses[body["id"]] == "submitted"


# (7) Selection: an agreement is created, the listing is awarded, the other offer is rejected.
def test_select_creates_agreement_awards_and_rejects_other(client, headers):
    listing, offer_a, offer_b = _demand_with_two_offers(client, headers)
    client.post(
        f"/v1/marketplace/offers/{offer_a['id']}/request-revision",
        json={"note": "Could you give your final price?"},
        headers=headers["buyer"],
    )
    revised = client.post(
        f"/v1/marketplace/offers/{offer_a['id']}/revise",
        json={
            "lines": [{"quantity": "300", "unit": "pcs",
                       "unit_price": "90", "currency": "TRY"}],
            "tax_included": False,
        },
        headers=headers["supplier-a"],
    ).json()
    selected = client.post(
        f"/v1/marketplace/offers/{revised['id']}/select",
        json={"confirmed": True},
        headers=headers["buyer"],
    )
    assert selected.status_code == 200, selected.text
    body = selected.json()
    agreement = body["agreement"]
    assert agreement["offer_id"] == revised["id"]
    assert agreement["listing_id"] == listing["id"]
    assert Decimal(agreement["total"]) == Decimal("27000")
    assert agreement["currency"] == "TRY"
    assert agreement["buyer_user"] == "buyer"
    assert agreement["seller_user"] == "supplier-a"
    assert body["listing"]["status"] == "awarded"
    assert body["offer"]["status"] == "selected"
    owner_view = client.get(
        f"/v1/marketplace/listings/{listing['id']}/offers",
        headers=headers["buyer"],
    )
    statuses = {o["id"]: o["status"] for o in owner_view.json()["offers"]}
    assert statuses[offer_b["id"]] == "rejected"


# (8) Sales-listing direction: a buyer offers on a supply listing; the same flow applies.
def test_supply_listing_reverse_flow(client, headers):
    listing = _publish_listing(
        client, headers["supplier-b"],
        text="I have 500 pcs galvanized pipe for sale. Delivery to Ankara, within 10 days.",
        kind="supply",
    )
    assert listing["kind"] == "supply"
    offer = _offer(client, headers["buyer"], listing["id"], {
        "lines": [{"quantity": "500", "unit": "pcs",
                   "unit_price": "80", "currency": "TRY"}],
        "tax_included": True, "shipping_included": True,
    })
    assert Decimal(offer["total"]) == Decimal("40000")
    selected = client.post(
        f"/v1/marketplace/offers/{offer['id']}/select",
        json={"confirmed": True},
        headers=headers["supplier-b"],
    )
    assert selected.status_code == 200, selected.text
    body = selected.json()
    assert body["listing"]["status"] == "awarded"
    assert body["agreement"]["buyer_user"] == "buyer"
    assert body["agreement"]["seller_user"] == "supplier-b"
    assert Decimal(body["agreement"]["total"]) == Decimal("40000")


# (9) A listing published with "I don't know" carries the label; the offer is conditional.
def test_needs_clarification_listing_and_conditional_offer(client, headers):
    listing = _publish_listing(
        client, headers["buyer"],
        text="Looking for galvanized pipe, I don't know the diameter, supplier suggestion please.",
    )
    assert listing["needs_clarification"] is True
    offer = _offer(client, headers["supplier-a"], listing["id"], {
        "text": "300 pcs, unit price 100 USD, VAT excluded, conditional offer",
    })
    assert offer["conditional"] is True
    assert offer["status"] == "submitted"


# (10) You cannot make an offer on your own listing.
def test_cannot_offer_on_own_listing(client, headers):
    listing = _publish_listing(client, headers["buyer"])
    response = client.post(
        f"/v1/marketplace/listings/{listing['id']}/offers",
        json={"lines": [{"quantity": "300", "unit": "pcs",
                         "unit_price": "1", "currency": "TRY"}]},
        headers=headers["buyer"],
    )
    assert response.status_code == 400, response.text
