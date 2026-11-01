"""Pazar yeri kayıtları: ilan, teklif, anlaşma, mesaj ve bildirim.

Mevcut inquiry/quote akışından bağımsız, paralel bir modüldür.
Para tutarları her zaman ``Decimal`` ile tutulur; belirtilmemiş
fiyat/teknik/ödeme alanları ``None`` kalır, sistem değer uydurmaz.
Tenant karşılığı ``company_id`` alanıdır (tokenlardaki ``tenant``).
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any

LISTING_KINDS = ("demand", "supply")
LISTING_STATUSES = ("draft", "published", "awarded", "closed")
OFFER_STATUSES = (
    "draft",
    "submitted",
    "revision_requested",
    "selected",
    "rejected",
    "withdrawn",
)


def to_decimal(value: Any) -> Decimal | None:
    """``value`` değerini ``Decimal``a çevirir; boşsa ``None`` döner."""
    if value is None or value == "":
        return None
    if isinstance(value, Decimal):
        return value
    # Türkçe ondalık virgülü de kabul et.
    return Decimal(str(value).replace(".", "").replace(",", ".") if _looks_tr_grouped(str(value)) else str(value).replace(",", "."))


def _looks_tr_grouped(text: str) -> bool:
    # "1.250,50" gibi binlik noktalı + virgüllü biçim.
    return "." in text and "," in text


def _dec_or_zero(value: Any) -> Decimal:
    result = to_decimal(value)
    return result if result is not None else Decimal("0")


@dataclass
class ListingItem:
    """İlandaki tek kalem. Tek kalem yeterli; ilan liste de taşıyabilir."""

    product: str | None = None
    quantity: Decimal | None = None
    unit: str | None = None
    category: str | None = None
    features: dict[str, Any] = field(default_factory=dict)
    description: str = ""

    def __post_init__(self) -> None:
        if self.quantity is not None and not isinstance(self.quantity, Decimal):
            self.quantity = to_decimal(self.quantity)
        self.features = dict(self.features or {})


@dataclass
class Listing:
    id: str
    kind: str  # demand | supply
    owner_user: str
    company_id: str = "default"  # tenant
    title: str = ""
    raw_text: str = ""
    product: str | None = None
    quantity: Decimal | None = None
    unit: str | None = None
    delivery_place: str | None = None
    delivery_days: int | None = None
    category: str | None = None
    features: dict[str, Any] = field(default_factory=dict)
    items: list[ListingItem] = field(default_factory=list)
    missing_fields: list[str] = field(default_factory=list)
    needs_clarification: bool = False
    status: str = "draft"  # draft | published | awarded | closed
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)

    def __post_init__(self) -> None:
        if self.kind not in LISTING_KINDS:
            raise ValueError(f"geçersiz ilan türü: {self.kind!r}")
        if self.status not in LISTING_STATUSES:
            raise ValueError(f"geçersiz ilan durumu: {self.status!r}")
        if self.quantity is not None and not isinstance(self.quantity, Decimal):
            self.quantity = to_decimal(self.quantity)
        self.features = dict(self.features or {})
        self.missing_fields = list(self.missing_fields or [])
        self.items = [
            item if isinstance(item, ListingItem) else ListingItem(**item)  # type: ignore[arg-type]
            for item in (self.items or [])
        ]
        if not self.items and (self.product or self.quantity is not None):
            self.items = [
                ListingItem(
                    product=self.product,
                    quantity=self.quantity,
                    unit=self.unit,
                    category=self.category,
                    features=dict(self.features),
                )
            ]
        if not self.title:
            parts = [
                str(self.quantity) if self.quantity is not None else "",
                self.unit or "",
                self.product or "",
            ]
            self.title = " ".join(p for p in parts if p).strip() or self.raw_text[:80]


@dataclass
class OfferLine:
    quantity: Decimal | None = None
    unit: str | None = None
    unit_price: Decimal | None = None
    currency: str | None = None
    features: dict[str, Any] = field(default_factory=dict)
    product: str | None = None

    def __post_init__(self) -> None:
        if self.quantity is not None and not isinstance(self.quantity, Decimal):
            self.quantity = to_decimal(self.quantity)
        if self.unit_price is not None and not isinstance(self.unit_price, Decimal):
            self.unit_price = to_decimal(self.unit_price)
        self.features = dict(self.features or {})

    @property
    def line_total(self) -> Decimal | None:
        if self.quantity is None or self.unit_price is None:
            return None
        return self.quantity * self.unit_price


@dataclass
class Offer:
    id: str
    listing_id: str
    offerer_user: str
    offerer_company_id: str = "default"
    revision_no: int = 1
    parent_offer_id: str | None = None
    lines: list[OfferLine] = field(default_factory=list)
    tax_included: bool | None = None
    shipping_included: bool | None = None
    shipping_cost: Decimal | None = None
    delivery_days: int | None = None
    payment_terms: str | None = None
    conditional: bool = False
    note: str = ""
    status: str = "draft"  # draft|submitted|revision_requested|selected|rejected|withdrawn
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)

    def __post_init__(self) -> None:
        if self.status not in OFFER_STATUSES:
            raise ValueError(f"geçersiz teklif durumu: {self.status!r}")
        if self.shipping_cost is not None and not isinstance(self.shipping_cost, Decimal):
            self.shipping_cost = to_decimal(self.shipping_cost)
        self.lines = [
            line if isinstance(line, OfferLine) else OfferLine(**line)  # type: ignore[arg-type]
            for line in (self.lines or [])
        ]

    def total(self) -> Decimal:
        """Satır toplamları (+ dahil değilse nakliye) ``Decimal`` ile."""
        result = Decimal("0")
        for line in self.lines:
            lt = line.line_total
            if lt is not None:
                result += lt
        if self.shipping_included is False and self.shipping_cost is not None:
            result += self.shipping_cost
        return result

    # Türkçe/uyumluluk takma adı.
    def toplam(self) -> Decimal:
        return self.total()

    @property
    def currency(self) -> str | None:
        for line in self.lines:
            if line.currency:
                return line.currency
        return None


@dataclass
class Agreement:
    id: str
    listing_id: str
    offer_id: str
    buyer_user: str = ""
    buyer_company_id: str = "default"
    seller_user: str = ""
    seller_company_id: str = "default"
    total: Decimal | None = None
    currency: str | None = None
    status: str = "agreed"  # agreed | cancelled
    created_at: float = field(default_factory=time.time)

    def __post_init__(self) -> None:
        if self.total is not None and not isinstance(self.total, Decimal):
            self.total = to_decimal(self.total)


@dataclass
class Message:
    id: str
    listing_id: str
    sender_user: str
    body: str
    recipient_user: str = ""
    offer_id: str | None = None
    company_id: str = "default"
    created_at: float = field(default_factory=time.time)


@dataclass
class Notification:
    id: str
    user: str
    text: str
    kind: str = "info"
    company_id: str = "default"
    listing_id: str | None = None
    offer_id: str | None = None
    read: bool = False
    created_at: float = field(default_factory=time.time)
