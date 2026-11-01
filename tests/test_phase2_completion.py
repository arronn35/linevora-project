"""Faz 2 tamamlama: kopya güvenliği, satır bazlı kalıcılık, model-usage, vurgu."""

import sqlite3

from linevora.catalog.store import InMemoryCatalogStore
from linevora.persistence import wrap_store
from linevora.quotes.store import InMemoryQuoteStore


def test_get_returns_copy_not_live_reference():
    store = InMemoryQuoteStore()
    quote = store.create(
        inquiry_id="i1", version_id="v1", terms_version_id="t1", created_by="admin"
    )
    fetched = store.get(quote.id)
    fetched.status = "bozuldu"
    assert store.get(quote.id).status != "bozuldu"


def test_catalog_features_copy_isolated():
    store = InMemoryCatalogStore()
    product = store.add(code="X-1", names=("ürün",), features={"DN": "50"})
    fetched = store.get(product.id)
    fetched.features["DN"] = "999"
    assert store.get(product.id).features["DN"] == "50"


def test_row_based_persistence_only_rows_table(tmp_path):
    db = str(tmp_path / "rows.db")
    first = wrap_store(InMemoryQuoteStore(), db, "quotes")
    quote = first.create(
        inquiry_id="i1", version_id="v1", terms_version_id="t1", created_by="admin"
    )
    second = wrap_store(InMemoryQuoteStore(), db, "quotes")
    assert second.get(quote.id).inquiry_id == "i1"
    with sqlite3.connect(db) as conn:
        rows = conn.execute(
            "SELECT item_key FROM store_rows WHERE namespace='quotes'"
        ).fetchall()
    assert [row[0] for row in rows] == [quote.id]


def test_model_usage_endpoint(client, admin_token):
    headers = {"Authorization": f"Bearer {admin_token}"}
    response = client.get("/v1/metrics/model-usage", headers=headers)
    assert response.status_code == 200
    body = response.json()
    assert "estimated_tokens" in body
    assert "calls" in body
