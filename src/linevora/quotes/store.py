"""Quote stores. The MVP implementation is in-memory; the persistent
implementation moves behind these interfaces with a managed database.
"""

from __future__ import annotations

import copy

import threading
import time
import uuid
from dataclasses import asdict
from typing import Protocol

from ..catalog.models import Product
from .models import PriceVersion, Quote, QuoteLine, TermsVersion


class PriceStore(Protocol):
    def create(self, product_id: str, price: float, currency: str) -> PriceVersion:
        ...

    def get(self, version_id: str) -> PriceVersion:
        ...

    def list_for_product(self, product_id: str) -> list[PriceVersion]:
        ...

    def effective_for_product(self, product_id: str) -> PriceVersion | None:
        ...

    def activate(self, version_id: str) -> PriceVersion:
        """Activates the draft; archives the previously active version."""
        ...


class TermsStore(Protocol):
    def create(self, name: str, text: str) -> TermsVersion:
        ...

    def get(self, version_id: str) -> TermsVersion:
        ...

    def list(self) -> list[TermsVersion]:
        ...

    def effective(self) -> TermsVersion | None:
        ...

    def activate(self, version_id: str) -> TermsVersion:
        ...


class QuoteStore(Protocol):
    def create(
        self, inquiry_id: str, version_id: str, terms_version_id: str, created_by: str
    ) -> Quote:
        ...

    def get(self, quote_id: str) -> Quote:
        ...

    def list(self) -> list[Quote]:
        ...

    def update(self, quote: Quote) -> Quote:
        ...

    def list_for_inquiry(self, inquiry_id: str) -> list[Quote]:
        ...


class QuoteLineStore(Protocol):
    def add(
        self,
        quote_id: str,
        requirement_id: str,
        product_id: str,
        quantity: float,
        unit: str,
        price_version_id: str,
        unit_price: float,
        currency: str,
        amount: float,
    ) -> QuoteLine:
        ...

    def list_for_quote(self, quote_id: str) -> list[QuoteLine]:
        ...

    def delete_for_quote(self, quote_id: str) -> None:
        ...


class InMemoryPriceStore:
    def __init__(self) -> None:
        self._items: dict[str, PriceVersion] = {}
        self._lock = threading.Lock()

    def create(self, product_id: str, price: float, currency: str) -> PriceVersion:
        with self._lock:
            version = PriceVersion(
                id=uuid.uuid4().hex,
                product_id=product_id,
                price=price,
                currency=currency,
            )
            self._items[version.id] = version
            return version

    def get(self, version_id: str) -> PriceVersion:
        with self._lock:
            try:
                return self._items[version_id]
            except KeyError:
                raise KeyError(version_id)

    def list_for_product(self, product_id: str) -> list[PriceVersion]:
        with self._lock:
            return [item for item in self._items.values() if item.product_id == product_id]

    def effective_for_product(self, product_id: str) -> PriceVersion | None:
        with self._lock:
            for item in self._items.values():
                if item.product_id == product_id and item.status == "active":
                    return item
            return None

    def activate(self, version_id: str) -> PriceVersion:
        with self._lock:
            try:
                version = self._items[version_id]
            except KeyError:
                raise KeyError(version_id)
            if version.status != "draft":
                raise ValueError("only a draft can be activated")
            for key, item in self._items.items():
                if item.product_id == version.product_id and item.status == "active":
                    self._items[key] = PriceVersion(
                        id=item.id,
                        product_id=item.product_id,
                        price=item.price,
                        currency=item.currency,
                        status="archived",
                        created_at=item.created_at,
                    )
            activated = PriceVersion(
                id=version.id,
                product_id=version.product_id,
                price=version.price,
                currency=version.currency,
                status="active",
                created_at=version.created_at,
            )
            self._items[version.id] = activated
            return activated

    def to_snapshot(self) -> dict:
        with self._lock:
            return {"items": [asdict(item) for item in self._items.values()]}

    def load_snapshot(self, data: dict) -> None:
        with self._lock:
            self._items = {
                item["id"]: PriceVersion(**item) for item in data.get("items", [])
            }


class InMemoryTermsStore:
    def __init__(self) -> None:
        self._items: dict[str, TermsVersion] = {}
        self._lock = threading.Lock()

    def create(self, name: str, text: str) -> TermsVersion:
        with self._lock:
            version = TermsVersion(id=uuid.uuid4().hex, name=name, text=text)
            self._items[version.id] = version
            return version

    def get(self, version_id: str) -> TermsVersion:
        with self._lock:
            try:
                return self._items[version_id]
            except KeyError:
                raise KeyError(version_id)

    def list(self) -> list[TermsVersion]:
        with self._lock:
            return list(self._items.values())

    def effective(self) -> TermsVersion | None:
        with self._lock:
            for item in self._items.values():
                if item.status == "active":
                    return item
            return None

    def activate(self, version_id: str) -> TermsVersion:
        with self._lock:
            try:
                version = self._items[version_id]
            except KeyError:
                raise KeyError(version_id)
            if version.status != "draft":
                raise ValueError("only a draft can be activated")
            for key, item in self._items.items():
                if item.status == "active":
                    self._items[key] = TermsVersion(
                        id=item.id,
                        name=item.name,
                        text=item.text,
                        status="archived",
                        created_at=item.created_at,
                    )
            activated = TermsVersion(
                id=version.id,
                name=version.name,
                text=version.text,
                status="active",
                created_at=version.created_at,
            )
            self._items[version.id] = activated
            return activated

    def to_snapshot(self) -> dict:
        with self._lock:
            return {"items": [asdict(item) for item in self._items.values()]}

    def load_snapshot(self, data: dict) -> None:
        with self._lock:
            self._items = {
                item["id"]: TermsVersion(**item) for item in data.get("items", [])
            }


class InMemoryQuoteStore:
    def __init__(self) -> None:
        self._items: dict[str, Quote] = {}
        self._lock = threading.Lock()

    def create(
        self, inquiry_id: str, version_id: str, terms_version_id: str, created_by: str
    ) -> Quote:
        with self._lock:
            quote = Quote(
                id=uuid.uuid4().hex,
                inquiry_id=inquiry_id,
                version_id=version_id,
                terms_version_id=terms_version_id,
                created_by=created_by,
            )
            self._items[quote.id] = quote
            return quote

    def get(self, quote_id: str) -> Quote:
        with self._lock:
            try:
                return copy.deepcopy(self._items[quote_id])
            except KeyError:
                raise KeyError(quote_id)

    def update(self, quote: Quote) -> Quote:
        with self._lock:
            quote.updated_at = time.time()
            self._items[quote.id] = quote
            return quote

    def list_for_inquiry(self, inquiry_id: str) -> list[Quote]:
        with self._lock:
            return copy.deepcopy([item for item in self._items.values() if item.inquiry_id == inquiry_id])

    def list(self) -> list[Quote]:
        with self._lock:
            return copy.deepcopy(list(self._items.values()))

    def to_snapshot(self) -> dict:
        with self._lock:
            return {"items": [asdict(item) for item in self._items.values()]}

    def load_snapshot(self, data: dict) -> None:
        with self._lock:
            self._items = {item["id"]: Quote(**item) for item in data.get("items", [])}


class InMemoryQuoteLineStore:
    def __init__(self) -> None:
        self._items: dict[str, QuoteLine] = {}
        self._lock = threading.Lock()

    def add(
        self,
        quote_id: str,
        requirement_id: str,
        product_id: str,
        quantity: float,
        unit: str,
        price_version_id: str,
        unit_price: float,
        currency: str,
        amount: float,
    ) -> QuoteLine:
        with self._lock:
            line = QuoteLine(
                id=uuid.uuid4().hex,
                quote_id=quote_id,
                requirement_id=requirement_id,
                product_id=product_id,
                quantity=quantity,
                unit=unit,
                price_version_id=price_version_id,
                unit_price=unit_price,
                currency=currency,
                amount=amount,
            )
            self._items[line.id] = line
            return line

    def list_for_quote(self, quote_id: str) -> list[QuoteLine]:
        with self._lock:
            return [item for item in self._items.values() if item.quote_id == quote_id]

    def delete_for_quote(self, quote_id: str) -> None:
        with self._lock:
            for key in [
                key for key, item in self._items.items() if item.quote_id == quote_id
            ]:
                del self._items[key]

    def to_snapshot(self) -> dict:
        with self._lock:
            return {"items": [asdict(item) for item in self._items.values()]}

    def load_snapshot(self, data: dict) -> None:
        with self._lock:
            self._items = {item["id"]: QuoteLine(**item) for item in data.get("items", [])}


_DEMO_PRICES = {
    "P-001": 85000.0,
    "P-002": 120000.0,
    "V-001": 18500.0,
    "V-002": 12750.0,
    "V-003": 6400.0,
}


def seed_demo_prices(store: PriceStore, products: list[Product]) -> None:
    for product in products:
        version = store.create(
            product_id=product.id,
            price=_DEMO_PRICES.get(product.code, 1000.0),
            currency="TRY",
        )
        store.activate(version.id)


def seed_demo_terms(store: TermsStore) -> None:
    version = store.create(
        name="Standard Sales Terms",
        text="Payment: 50% with order, 50% on delivery. Delivery: EXW. Quote validity: 30 days.",
    )
    store.activate(version.id)
