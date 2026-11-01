"""Pazar yeri depoları.

Desen mevcut store'larla aynıdır: bellek içi + ``threading.Lock`` +
``deepcopy`` + ``to_snapshot``/``load_snapshot``; böylece
``persistence.wrap_store`` ile (namespace verilerek) sarılabilir.
Yayımlama ve teklif gönderimi kullanıcı onayı (``confirmed=True``)
olmadan yapılamaz. Rakip teklifler birbirini görmez: sahip olmayan
izleyici yalnızca kendi tekliflerini listeler.
"""

from __future__ import annotations

import copy
import threading
import time
import uuid
from dataclasses import asdict
from decimal import Decimal
from typing import Any, Protocol

from .models import (
    Agreement,
    Listing,
    ListingItem,
    Message,
    Notification,
    Offer,
    OfferLine,
    to_decimal,
)


def _listing_from_snapshot(item: dict) -> Listing:
    data = dict(item)
    if data.get("quantity") is not None:
        data["quantity"] = Decimal(str(data["quantity"]))
    data["items"] = [
        ListingItem(
            product=it.get("product"),
            quantity=Decimal(str(it["quantity"])) if it.get("quantity") is not None else None,
            unit=it.get("unit"), category=it.get("category"),
            features=dict(it.get("features", {})),
            description=it.get("description", ""),
        )
        for it in data.get("items", [])
    ]
    return Listing(**data)


def _offer_from_snapshot(item: dict) -> Offer:
    data = dict(item)
    if data.get("shipping_cost") is not None:
        data["shipping_cost"] = Decimal(str(data["shipping_cost"]))
    data["lines"] = [
        OfferLine(
            quantity=Decimal(str(ln["quantity"])) if ln.get("quantity") is not None else None,
            unit=ln.get("unit"),
            unit_price=Decimal(str(ln["unit_price"])) if ln.get("unit_price") is not None else None,
            currency=ln.get("currency"),
            features=dict(ln.get("features", {})),
            product=ln.get("product"),
        )
        for ln in data.get("lines", [])
    ]
    return Offer(**data)


def _agreement_from_snapshot(item: dict) -> Agreement:
    data = dict(item)
    if data.get("total") is not None:
        data["total"] = Decimal(str(data["total"]))
    return Agreement(**data)


def _snapshot_items(data: Any) -> list[dict]:
    if isinstance(data, dict):
        items = data.get("items")
        if isinstance(items, list):
            return items
        # Eski/serbest biçim: tek kayıt listesi.
        for key in ("listings", "offers", "agreements", "messages", "notifications"):
            if isinstance(data.get(key), list):
                return data[key]
    if isinstance(data, list):
        return data
    return []


# ---------------------------------------------------------------- listing

class ListingStore(Protocol):
    def create(self, kind: str, owner_user: str, company_id: str = "default",
               title: str = "", raw_text: str = "", **fields: Any) -> Listing: ...
    def get(self, listing_id: str) -> Listing: ...
    def list(self) -> list[Listing]: ...
    def list_published(self, kind: str | None = None) -> list[Listing]: ...
    def update(self, listing: Listing) -> Listing: ...
    def publish(self, listing_id: str, confirmed: bool = False) -> Listing: ...
    def close(self, listing_id: str) -> Listing: ...
    def to_snapshot(self) -> dict: ...
    def load_snapshot(self, data: dict) -> None: ...


class InMemoryListingStore:
    def __init__(self) -> None:
        self._items: dict[str, Listing] = {}
        self._lock = threading.Lock()

    def create(self, kind: str, owner_user: str, company_id: str = "default",
               title: str = "", raw_text: str = "", **fields: Any) -> Listing:
        with self._lock:
            listing = Listing(
                id=uuid.uuid4().hex, kind=kind, owner_user=owner_user,
                company_id=company_id, title=title, raw_text=raw_text, **fields,
            )
            self._items[listing.id] = listing
            return copy.deepcopy(listing)

    def get(self, listing_id: str) -> Listing:
        with self._lock:
            try:
                return copy.deepcopy(self._items[listing_id])
            except KeyError:
                raise KeyError(listing_id) from None

    def list(self) -> list[Listing]:
        with self._lock:
            return copy.deepcopy(list(self._items.values()))

    def list_published(self, kind: str | None = None) -> list[Listing]:
        with self._lock:
            return copy.deepcopy([
                item for item in self._items.values()
                if item.status == "published" and (kind is None or item.kind == kind)
            ])

    def update(self, listing: Listing) -> Listing:
        with self._lock:
            if listing.id not in self._items:
                raise KeyError(listing.id)
            listing.updated_at = time.time()
            self._items[listing.id] = copy.deepcopy(listing)
            return copy.deepcopy(listing)

    def publish(self, listing_id: str, confirmed: bool = False) -> Listing:
        if not confirmed:
            raise ValueError("yayımlama için kullanıcı onayı gerekli")
        with self._lock:
            listing = self._get_locked(listing_id)
            if listing.status != "draft":
                raise ValueError("yalnızca taslak ilan yayımlanır")
            listing.status = "published"
            listing.updated_at = time.time()
            return copy.deepcopy(listing)

    def award(self, listing_id: str) -> Listing:
        with self._lock:
            listing = self._get_locked(listing_id)
            listing.status = "awarded"
            listing.updated_at = time.time()
            return copy.deepcopy(listing)

    def close(self, listing_id: str) -> Listing:
        with self._lock:
            listing = self._get_locked(listing_id)
            listing.status = "closed"
            listing.updated_at = time.time()
            return copy.deepcopy(listing)

    def _get_locked(self, listing_id: str) -> Listing:
        try:
            return self._items[listing_id]
        except KeyError:
            raise KeyError(listing_id) from None

    def to_snapshot(self) -> dict:
        with self._lock:
            return {"items": [asdict(item) for item in self._items.values()]}

    def load_snapshot(self, data: dict) -> None:
        with self._lock:
            self._items = {
                item["id"]: _listing_from_snapshot(item)
                for item in _snapshot_items(data)
            }


# ---------------------------------------------------------------- offer

class OfferStore(Protocol):
    def create(self, listing_id: str, offerer_user: str,
               offerer_company_id: str = "default", **fields: Any) -> Offer: ...
    def get(self, offer_id: str) -> Offer: ...
    def list_for_listing(self, listing_id: str, viewer_user: str | None = None,
                         viewer_company_id: str | None = None,
                         listing_owner_user: str | None = None) -> list[Offer]: ...
    def submit(self, offer_id: str, confirmed: bool = False) -> Offer: ...
    def request_revision(self, offer_id: str, note: str = "") -> Offer: ...
    def create_revision(self, parent_offer_id: str, **changes: Any) -> Offer: ...
    def select(self, offer_id: str, confirmed: bool = False) -> Offer: ...
    def to_snapshot(self) -> dict: ...
    def load_snapshot(self, data: dict) -> None: ...


class InMemoryOfferStore:
    def __init__(self) -> None:
        self._items: dict[str, Offer] = {}
        self._lock = threading.Lock()

    def create(self, listing_id: str, offerer_user: str,
               offerer_company_id: str = "default", **fields: Any) -> Offer:
        with self._lock:
            offer = Offer(
                id=uuid.uuid4().hex, listing_id=listing_id,
                offerer_user=offerer_user,
                offerer_company_id=offerer_company_id, **fields,
            )
            self._items[offer.id] = offer
            return copy.deepcopy(offer)

    def get(self, offer_id: str) -> Offer:
        with self._lock:
            try:
                return copy.deepcopy(self._items[offer_id])
            except KeyError:
                raise KeyError(offer_id) from None

    def list(self) -> list[Offer]:
        with self._lock:
            return copy.deepcopy(list(self._items.values()))

    def list_for_listing(self, listing_id: str, viewer_user: str | None = None,
                         viewer_company_id: str | None = None,
                         listing_owner_user: str | None = None) -> list[Offer]:
        """Rakip gizliliği: sahip olmayan izleyici yalnızca kendisininkini görür.

        ``viewer_user`` verilmezse güvenilir iç çağrı sayılır ve tümü döner.
        """
        with self._lock:
            offers = [o for o in self._items.values() if o.listing_id == listing_id]
            if viewer_user is not None and viewer_user != listing_owner_user:
                offers = [
                    o for o in offers
                    if o.offerer_user == viewer_user
                    or (viewer_company_id is not None and o.offerer_company_id == viewer_company_id and viewer_company_id != "default")
                ]
            return copy.deepcopy(offers)

    def list_for_offerer(self, offerer_user: str) -> list[Offer]:
        with self._lock:
            return copy.deepcopy([
                o for o in self._items.values() if o.offerer_user == offerer_user
            ])

    def compare(self, listing_id: str) -> list[Offer]:
        """Alıcının karşılaştırması: gönderilmiş teklifler toplam tutara göre."""
        with self._lock:
            offers = [
                o for o in self._items.values()
                if o.listing_id == listing_id and o.status in ("submitted", "selected", "revision_requested")
            ]
            return copy.deepcopy(sorted(offers, key=lambda o: o.total()))

    def update(self, offer: Offer) -> Offer:
        with self._lock:
            if offer.id not in self._items:
                raise KeyError(offer.id)
            offer.updated_at = time.time()
            self._items[offer.id] = copy.deepcopy(offer)
            return copy.deepcopy(offer)

    def submit(self, offer_id: str, confirmed: bool = False) -> Offer:
        if not confirmed:
            raise ValueError("gönderim için kullanıcı onayı gerekli")
        with self._lock:
            offer = self._get_locked(offer_id)
            if offer.status not in ("draft", "revision_requested"):
                raise ValueError("yalnızca taslak/revize bekleyen teklif gönderilir")
            offer.status = "submitted"
            offer.updated_at = time.time()
            return copy.deepcopy(offer)

    def request_revision(self, offer_id: str, note: str = "") -> Offer:
        with self._lock:
            offer = self._get_locked(offer_id)
            if offer.status != "submitted":
                raise ValueError("yalnızca gönderilmiş tekliften revize istenir")
            offer.status = "revision_requested"
            if note:
                offer.note = note
            offer.updated_at = time.time()
            return copy.deepcopy(offer)

    def create_revision(self, parent_offer_id: str, **changes: Any) -> Offer:
        with self._lock:
            parent = self._get_locked(parent_offer_id)
            data: dict[str, Any] = {
                "listing_id": parent.listing_id,
                "offerer_user": parent.offerer_user,
                "offerer_company_id": parent.offerer_company_id,
                "revision_no": parent.revision_no + 1,
                "parent_offer_id": parent.id,
                "lines": copy.deepcopy(parent.lines),
                "tax_included": parent.tax_included,
                "shipping_included": parent.shipping_included,
                "shipping_cost": parent.shipping_cost,
                "delivery_days": parent.delivery_days,
                "payment_terms": parent.payment_terms,
                "conditional": parent.conditional,
                "note": parent.note,
                "status": "draft",
            }
            data.update(changes)
            offer = Offer(id=uuid.uuid4().hex, **data)
            self._items[offer.id] = offer
            return copy.deepcopy(offer)

    def select(self, offer_id: str, confirmed: bool = False) -> Offer:
        if not confirmed:
            raise ValueError("seçim için kullanıcı onayı gerekli")
        with self._lock:
            offer = self._get_locked(offer_id)
            if offer.status not in ("submitted", "revision_requested"):
                raise ValueError("yalnızca gönderilmiş teklif seçilir")
            offer.status = "selected"
            offer.updated_at = time.time()
            for other in self._items.values():
                if other.listing_id == offer.listing_id and other.id != offer.id and other.status == "submitted":
                    other.status = "rejected"
                    other.updated_at = time.time()
            return copy.deepcopy(offer)

    def reject(self, offer_id: str) -> Offer:
        with self._lock:
            offer = self._get_locked(offer_id)
            offer.status = "rejected"
            offer.updated_at = time.time()
            return copy.deepcopy(offer)

    def withdraw(self, offer_id: str) -> Offer:
        with self._lock:
            offer = self._get_locked(offer_id)
            offer.status = "withdrawn"
            offer.updated_at = time.time()
            return copy.deepcopy(offer)

    def _get_locked(self, offer_id: str) -> Offer:
        try:
            return self._items[offer_id]
        except KeyError:
            raise KeyError(offer_id) from None

    def to_snapshot(self) -> dict:
        with self._lock:
            return {"items": [asdict(item) for item in self._items.values()]}

    def load_snapshot(self, data: dict) -> None:
        with self._lock:
            self._items = {
                item["id"]: _offer_from_snapshot(item)
                for item in _snapshot_items(data)
            }


# ---------------------------------------------------------------- agreement

class AgreementStore(Protocol):
    def create(self, listing_id: str, offer_id: str, **fields: Any) -> Agreement: ...
    def get(self, agreement_id: str) -> Agreement: ...
    def list(self) -> list[Agreement]: ...
    def list_for_listing(self, listing_id: str) -> list[Agreement]: ...
    def to_snapshot(self) -> dict: ...
    def load_snapshot(self, data: dict) -> None: ...


class InMemoryAgreementStore:
    def __init__(self) -> None:
        self._items: dict[str, Agreement] = {}
        self._lock = threading.Lock()

    def create(self, listing_id: str, offer_id: str, **fields: Any) -> Agreement:
        with self._lock:
            agreement = Agreement(
                id=uuid.uuid4().hex, listing_id=listing_id, offer_id=offer_id, **fields,
            )
            self._items[agreement.id] = agreement
            return copy.deepcopy(agreement)

    def get(self, agreement_id: str) -> Agreement:
        with self._lock:
            try:
                return copy.deepcopy(self._items[agreement_id])
            except KeyError:
                raise KeyError(agreement_id) from None

    def list(self) -> list[Agreement]:
        with self._lock:
            return copy.deepcopy(list(self._items.values()))

    def list_for_listing(self, listing_id: str) -> list[Agreement]:
        with self._lock:
            return copy.deepcopy([
                a for a in self._items.values() if a.listing_id == listing_id
            ])

    def to_snapshot(self) -> dict:
        with self._lock:
            return {"items": [asdict(item) for item in self._items.values()]}

    def load_snapshot(self, data: dict) -> None:
        with self._lock:
            self._items = {
                item["id"]: _agreement_from_snapshot(item)
                for item in _snapshot_items(data)
            }


# ---------------------------------------------------------------- message

class MessageStore(Protocol):
    def create(self, listing_id: str, sender_user: str, body: str, **fields: Any) -> Message: ...
    def list_for_listing(self, listing_id: str) -> list[Message]: ...
    def to_snapshot(self) -> dict: ...
    def load_snapshot(self, data: dict) -> None: ...


class InMemoryMessageStore:
    def __init__(self) -> None:
        self._items: dict[str, Message] = {}
        self._lock = threading.Lock()

    def create(self, listing_id: str, sender_user: str, body: str, **fields: Any) -> Message:
        with self._lock:
            message = Message(
                id=uuid.uuid4().hex, listing_id=listing_id,
                sender_user=sender_user, body=body, **fields,
            )
            self._items[message.id] = message
            return copy.deepcopy(message)

    def get(self, message_id: str) -> Message:
        with self._lock:
            try:
                return copy.deepcopy(self._items[message_id])
            except KeyError:
                raise KeyError(message_id) from None

    def list(self) -> list[Message]:
        with self._lock:
            return copy.deepcopy(list(self._items.values()))

    def list_for_listing(self, listing_id: str) -> list[Message]:
        with self._lock:
            return copy.deepcopy([
                m for m in self._items.values() if m.listing_id == listing_id
            ])

    def to_snapshot(self) -> dict:
        with self._lock:
            return {"items": [asdict(item) for item in self._items.values()]}

    def load_snapshot(self, data: dict) -> None:
        with self._lock:
            self._items = {
                item["id"]: Message(**item) for item in _snapshot_items(data)
            }


# ---------------------------------------------------------------- notification

class NotificationStore(Protocol):
    def create(self, user: str, text: str, **fields: Any) -> Notification: ...
    def list_for_user(self, user: str) -> list[Notification]: ...
    def mark_read(self, notification_id: str) -> Notification: ...
    def to_snapshot(self) -> dict: ...
    def load_snapshot(self, data: dict) -> None: ...


class InMemoryNotificationStore:
    def __init__(self) -> None:
        self._items: dict[str, Notification] = {}
        self._lock = threading.Lock()

    def create(self, user: str, text: str, **fields: Any) -> Notification:
        with self._lock:
            note = Notification(id=uuid.uuid4().hex, user=user, text=text, **fields)
            self._items[note.id] = note
            return copy.deepcopy(note)

    def get(self, notification_id: str) -> Notification:
        with self._lock:
            try:
                return copy.deepcopy(self._items[notification_id])
            except KeyError:
                raise KeyError(notification_id) from None

    def list(self) -> list[Notification]:
        with self._lock:
            return copy.deepcopy(list(self._items.values()))

    def list_for_user(self, user: str) -> list[Notification]:
        with self._lock:
            return copy.deepcopy([
                n for n in self._items.values() if n.user == user
            ])

    def mark_read(self, notification_id: str) -> Notification:
        with self._lock:
            try:
                note = self._items[notification_id]
            except KeyError:
                raise KeyError(notification_id) from None
            note.read = True
            return copy.deepcopy(note)

    def to_snapshot(self) -> dict:
        with self._lock:
            return {"items": [asdict(item) for item in self._items.values()]}

    def load_snapshot(self, data: dict) -> None:
        with self._lock:
            self._items = {
                item["id"]: Notification(**item) for item in _snapshot_items(data)
            }


def select_offer(
    listing_store: InMemoryListingStore,
    offer_store: InMemoryOfferStore,
    agreement_store: InMemoryAgreementStore,
    listing_id: str,
    offer_id: str,
    *,
    confirmed: bool = False,
) -> Agreement:
    """Alıcı bir teklifi seçer: teklif seçilir, ilan ödüllenir, anlaşma doğar.

    Ödeme/lojistik kapsam dışıdır; anlaşma yalnızca seçimin kaydıdır.
    """
    if not confirmed:
        raise ValueError("seçim için kullanıcı onayı gerekli")
    listing = listing_store.get(listing_id)
    offer = offer_store.get(offer_id)
    if offer.listing_id != listing_id:
        raise ValueError("teklif bu ilana ait değil")
    # demand: alıcı ilan sahibi, satıcı teklif veren; supply: tersi.
    if listing.kind == "demand":
        buyer_user, buyer_company = listing.owner_user, listing.company_id
        seller_user, seller_company = offer.offerer_user, offer.offerer_company_id
    else:
        buyer_user, buyer_company = offer.offerer_user, offer.offerer_company_id
        seller_user, seller_company = listing.owner_user, listing.company_id
    selected = offer_store.select(offer_id, confirmed=True)
    listing_store.award(listing_id)
    return agreement_store.create(
        listing_id=listing_id, offer_id=offer_id,
        buyer_user=buyer_user, buyer_company_id=buyer_company,
        seller_user=seller_user, seller_company_id=seller_company,
        total=selected.total(), currency=selected.currency,
    )
