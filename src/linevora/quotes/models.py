"""Teklif kayıtları: sürümlü fiyat/şart, teklif ve kalemler.

Durumlar — fiyat/şart: taslak / yürürlükte / arşiv;
teklif: taslak / incelemede / onaylandı / dışa aktarıldı.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field


@dataclass(frozen=True)
class PriceVersion:
    id: str
    product_id: str
    price: float
    currency: str
    status: str = "taslak"
    created_at: float = field(default_factory=time.time)


@dataclass(frozen=True)
class TermsVersion:
    id: str
    name: str
    text: str
    status: str = "taslak"
    created_at: float = field(default_factory=time.time)


@dataclass
class Quote:
    id: str
    inquiry_id: str
    version_id: str
    terms_version_id: str
    created_by: str
    status: str = "taslak"
    approved_by: str | None = None
    created_at: float = field(default_factory=time.time)
    approved_at: float | None = None
    updated_at: float = field(default_factory=time.time)


@dataclass(frozen=True)
class QuoteLine:
    id: str
    quote_id: str
    requirement_id: str
    product_id: str
    quantity: float
    unit: str
    price_version_id: str
    unit_price: float
    currency: str
    amount: float
