"""Pazar yeri kabul testleri: ilan -> teklif -> karşılaştırma -> seçim.

Kabul akışı hem alım (demand) hem satış (supply) yönünde doğrulanır.
Sistem belirtilmemiş fiyat/teknik/ödeme uydurmaz; yayımlama/gönderim
kullanıcı onayından sonra olur; rakip teklifler birbirini görmez.
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
    "alici:alici123:admin,"
    "tedarikci-a:tedarikci-a123:specialist,"
    "tedarikci-b:tedarikci-b123:specialist,"
    "disaridan:disaridan123:viewer"
)
PASSWORDS = {
    "alici": "alici123",
    "tedarikci-a": "tedarikci-a123",
    "tedarikci-b": "tedarikci-b123",
    "disaridan": "disaridan123",
}
DEMAND_TEXT = "300 adet galvaniz boru arıyorum. İstanbul'a teslim, iki hafta içinde."


@pytest.fixture
def client(monkeypatch, tmp_path):
    # Ek kullanıcılar mevcut desenle (LINEVORA_USERS + önbellek temizliği).
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
    """Yayında demand ilanı + iki tedarikçiden farklı para birimli teklif."""
    listing = _publish_listing(client, headers["alici"])
    offer_a = _offer(client, headers["tedarikci-a"], listing["id"], {
        "lines": [{"quantity": "300", "unit": "adet",
                   "unit_price": "100", "currency": "TRY"}],
        "tax_included": False,
    })
    offer_b = _offer(client, headers["tedarikci-b"], listing["id"], {
        "lines": [{"quantity": "300", "unit": "adet",
                   "unit_price": "2.5", "currency": "USD"}],
        "tax_included": True, "shipping_included": True,
        "delivery_days": 10, "payment_terms": "peşin",
    })
    return listing, offer_a, offer_b


# (1) Ayrıştırma: yalnızca metinde yazan çıkar, fiyat uydurulmaz.
def test_parse_galvaniz_boru_no_fabricated_price(client, headers):
    response = client.post(
        "/v1/marketplace/parse-listing",
        json={"kind": "demand", "text": DEMAND_TEXT},
        headers=headers["alici"],
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert Decimal(body["quantity"]) == Decimal("300")
    assert body["unit"] == "adet"
    assert body["delivery_place"] == "İstanbul"
    assert body["delivery_days"] == 14
    assert body["product"] == "galvaniz boru"
    missing = set(body["missing_fields"])
    assert {"cap", "boy", "et_kalinligi"} <= missing
    asked = {q["field"] for q in body["missing_questions"]}
    assert {"cap", "boy", "et_kalinligi"} <= asked
    # Belirtilmemiş fiyat uydurulmaz.
    assert body.get("unit_price") is None
    assert body.get("price") is None
    assert "Netleştirilecek bilgiler" in body["document"]


# (2) Dosyasız yayımlama akışı iki kullanıcıyla çalışır.
def test_fileless_publish_flow_two_users(client, headers):
    created = client.post(
        "/v1/marketplace/listings",
        json={"kind": "demand", "raw_text": DEMAND_TEXT},
        headers=headers["alici"],
    )
    assert created.status_code == 201, created.text
    listing = created.json()
    assert listing["status"] == "draft"
    # Taslak keşifte görünmez, başkasına kapalıdır.
    discovered = client.get("/v1/marketplace/listings", headers=headers["tedarikci-a"])
    assert discovered.status_code == 200
    assert all(i["id"] != listing["id"] for i in discovered.json()["listings"])
    hidden = client.get(
        f"/v1/marketplace/listings/{listing['id']}", headers=headers["tedarikci-a"]
    )
    assert hidden.status_code == 404
    # Onaylı yayımlama sonrası ikinci kullanıcı ilanı görür.
    published = client.post(
        f"/v1/marketplace/listings/{listing['id']}/publish",
        json={"confirmed": True},
        headers=headers["alici"],
    )
    assert published.status_code == 200, published.text
    assert published.json()["status"] == "published"
    discovered = client.get("/v1/marketplace/listings", headers=headers["tedarikci-a"])
    assert any(i["id"] == listing["id"] for i in discovered.json()["listings"])


# (3) İki tedarikçi kendi fiyatıyla teklif verir; katalog zorunlu değildir.
def test_two_suppliers_own_prices_catalog_optional(client, headers):
    listing, offer_a, offer_b = _demand_with_two_offers(client, headers)
    assert offer_a["offerer_user"] == "tedarikci-a"
    assert offer_b["offerer_user"] == "tedarikci-b"
    assert Decimal(offer_a["lines"][0]["unit_price"]) == Decimal("100")
    assert Decimal(offer_b["lines"][0]["unit_price"]) == Decimal("2.5")
    assert offer_a["status"] == "submitted"
    assert offer_b["status"] == "submitted"
    # Katalog fiyatı yalnızca isteğe bağlı ön doldurmadır.
    other = _publish_listing(client, headers["alici"])
    prefilled = _offer(client, headers["tedarikci-a"], other["id"], {
        "catalog_price": "120", "catalog_currency": "TRY",
    })
    assert Decimal(prefilled["lines"][0]["unit_price"]) == Decimal("120")
    assert Decimal(prefilled["total"]) == Decimal("36000")


# (4) Karşılaştırma: Decimal toplamlar, eksik nakliye, comparable, 'best' yok.
def test_comparison_totals_missing_costs_and_no_best(client, headers):
    listing, offer_a, offer_b = _demand_with_two_offers(client, headers)
    response = client.get(
        f"/v1/marketplace/listings/{listing['id']}/comparison",
        headers=headers["alici"],
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert "best" not in body
    entries = {e["offer_id"]: e for e in body["offers"]}
    assert set(entries) == {offer_a["id"], offer_b["id"]}
    entry_a, entry_b = entries[offer_a["id"]], entries[offer_b["id"]]
    assert Decimal(entry_a["total"]) == Decimal("300") * Decimal("100")
    assert Decimal(entry_b["total"]) == Decimal("300") * Decimal("2.5")
    assert any("nakliye" in cost for cost in entry_a["missing_costs"])
    assert entry_b["comparable"] is False
    assert any("para birimi" in reason for reason in entry_b["comparable_reasons"])
    assert all("best" not in entry for entry in entries.values())


# (5) Rakip izolasyonu ve anonim erişim.
def test_competitor_isolation_and_anonymous_401(client, headers):
    listing, offer_a, offer_b = _demand_with_two_offers(client, headers)
    mine = client.get(
        f"/v1/marketplace/listings/{listing['id']}/offers",
        headers=headers["tedarikci-a"],
    )
    assert mine.status_code == 200
    visible = [o["id"] for o in mine.json()["offers"]]
    assert visible == [offer_a["id"]]
    assert offer_b["id"] not in visible
    third = client.get(
        f"/v1/marketplace/listings/{listing['id']}/offers",
        headers=headers["disaridan"],
    )
    assert third.json()["offers"] == []
    owner = client.get(
        f"/v1/marketplace/listings/{listing['id']}/offers",
        headers=headers["alici"],
    )
    assert {o["id"] for o in owner.json()["offers"]} == {offer_a["id"], offer_b["id"]}
    assert client.get("/v1/marketplace/listings").status_code == 401
    assert client.get(
        f"/v1/marketplace/listings/{listing['id']}/offers"
    ).status_code == 401


# (6) Revize isteği -> tedarikçi revizesi -> revision_no artar.
def test_revision_flow_increments_revision_no(client, headers):
    listing, offer_a, _offer_b = _demand_with_two_offers(client, headers)
    requested = client.post(
        f"/v1/marketplace/offers/{offer_a['id']}/request-revision",
        json={"note": "Fiyatı gözden geçirebilir misiniz?"},
        headers=headers["alici"],
    )
    assert requested.status_code == 200, requested.text
    assert requested.json()["status"] == "revision_requested"
    revised = client.post(
        f"/v1/marketplace/offers/{offer_a['id']}/revise",
        json={
            "lines": [{"quantity": "300", "unit": "adet",
                       "unit_price": "90", "currency": "TRY"}],
            "tax_included": False,
        },
        headers=headers["tedarikci-a"],
    )
    assert revised.status_code == 201, revised.text
    body = revised.json()
    assert body["revision_no"] == offer_a["revision_no"] + 1
    assert body["parent_offer_id"] == offer_a["id"]
    assert Decimal(body["total"]) == Decimal("27000")
    owner_view = client.get(
        f"/v1/marketplace/listings/{listing['id']}/offers",
        headers=headers["alici"],
    )
    statuses = {o["id"]: o["status"] for o in owner_view.json()["offers"]}
    assert statuses[offer_a["id"]] == "withdrawn"
    assert statuses[body["id"]] == "submitted"


# (7) Seçim: anlaşma doğar, ilan awarded olur, diğer teklif rejected.
def test_select_creates_agreement_awards_and_rejects_other(client, headers):
    listing, offer_a, offer_b = _demand_with_two_offers(client, headers)
    client.post(
        f"/v1/marketplace/offers/{offer_a['id']}/request-revision",
        json={"note": "Son fiyatınızı verir misiniz?"},
        headers=headers["alici"],
    )
    revised = client.post(
        f"/v1/marketplace/offers/{offer_a['id']}/revise",
        json={
            "lines": [{"quantity": "300", "unit": "adet",
                       "unit_price": "90", "currency": "TRY"}],
            "tax_included": False,
        },
        headers=headers["tedarikci-a"],
    ).json()
    selected = client.post(
        f"/v1/marketplace/offers/{revised['id']}/select",
        json={"confirmed": True},
        headers=headers["alici"],
    )
    assert selected.status_code == 200, selected.text
    body = selected.json()
    agreement = body["agreement"]
    assert agreement["offer_id"] == revised["id"]
    assert agreement["listing_id"] == listing["id"]
    assert Decimal(agreement["total"]) == Decimal("27000")
    assert agreement["currency"] == "TRY"
    assert agreement["buyer_user"] == "alici"
    assert agreement["seller_user"] == "tedarikci-a"
    assert body["listing"]["status"] == "awarded"
    assert body["offer"]["status"] == "selected"
    owner_view = client.get(
        f"/v1/marketplace/listings/{listing['id']}/offers",
        headers=headers["alici"],
    )
    statuses = {o["id"]: o["status"] for o in owner_view.json()["offers"]}
    assert statuses[offer_b["id"]] == "rejected"


# (8) Satış ilanı yönü: supply ilanına alıcı teklif verir, aynı akış işler.
def test_supply_listing_reverse_flow(client, headers):
    listing = _publish_listing(
        client, headers["tedarikci-b"],
        text="500 adet galvaniz boru satıyorum. Ankara teslim, 10 gün içinde.",
        kind="supply",
    )
    assert listing["kind"] == "supply"
    offer = _offer(client, headers["alici"], listing["id"], {
        "lines": [{"quantity": "500", "unit": "adet",
                   "unit_price": "80", "currency": "TRY"}],
        "tax_included": True, "shipping_included": True,
    })
    assert Decimal(offer["total"]) == Decimal("40000")
    selected = client.post(
        f"/v1/marketplace/offers/{offer['id']}/select",
        json={"confirmed": True},
        headers=headers["tedarikci-b"],
    )
    assert selected.status_code == 200, selected.text
    body = selected.json()
    assert body["listing"]["status"] == "awarded"
    assert body["agreement"]["buyer_user"] == "alici"
    assert body["agreement"]["seller_user"] == "tedarikci-b"
    assert Decimal(body["agreement"]["total"]) == Decimal("40000")


# (9) 'Bilmiyorum' ile yayımlanan ilanda etiket var; teklif conditional.
def test_needs_clarification_listing_and_conditional_offer(client, headers):
    listing = _publish_listing(
        client, headers["alici"],
        text="Galvaniz boru arıyorum, çapı bilmiyorum, tedarikçi önerisi istiyorum.",
    )
    assert listing["needs_clarification"] is True
    offer = _offer(client, headers["tedarikci-a"], listing["id"], {
        "text": "300 adet, birim fiyat 100 TL, KDV hariç, şartlı teklif",
    })
    assert offer["conditional"] is True
    assert offer["status"] == "submitted"


# (10) Kendi ilanına teklif verilemez.
def test_cannot_offer_on_own_listing(client, headers):
    listing = _publish_listing(client, headers["alici"])
    response = client.post(
        f"/v1/marketplace/listings/{listing['id']}/offers",
        json={"lines": [{"quantity": "300", "unit": "adet",
                         "unit_price": "1", "currency": "TRY"}]},
        headers=headers["alici"],
    )
    assert response.status_code == 400, response.text
