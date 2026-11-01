"""Katalog deposu. MVP gerçeklemesi bellek içidir; kalıcı gerçekleme
Adım 8'de yönetilen veritabanıyla bu arayüzün arkasına geçer.
"""

from __future__ import annotations

import copy

import threading
import uuid
from dataclasses import asdict
from typing import Any, Protocol

from .models import Product


class CatalogStore(Protocol):
    def add(
        self,
        code: str,
        names: list[str],
        synonyms: list[str] | None = None,
        features: dict[str, Any] | None = None,
        unit: str = "adet",
    ) -> Product:
        ...

    def get(self, product_id: str) -> Product:
        ...

    def list(self) -> list[Product]:
        ...


class InMemoryCatalogStore:
    def __init__(self) -> None:
        self._products: dict[str, Product] = {}
        self._lock = threading.Lock()

    def add(
        self,
        code: str,
        names: list[str],
        synonyms: list[str] | None = None,
        features: dict[str, Any] | None = None,
        unit: str = "adet",
    ) -> Product:
        with self._lock:
            product = Product(
                id=uuid.uuid4().hex,
                code=code,
                names=tuple(names),
                synonyms=tuple(synonyms or []),
                features=dict(features or {}),
                unit=unit,
            )
            self._products[product.id] = product
            return product

    def get(self, product_id: str) -> Product:
        with self._lock:
            try:
                return copy.deepcopy(self._products[product_id])
            except KeyError:
                raise KeyError(product_id)

    def list(self) -> list[Product]:
        with self._lock:
            return copy.deepcopy(list(self._products.values()))

    def to_snapshot(self) -> dict:
        with self._lock:
            return {"products": [asdict(item) for item in self._products.values()]}

    def load_snapshot(self, data: dict) -> None:
        with self._lock:
            self._products = {}
            for item in data.get("products", []):
                self._products[item["id"]] = Product(
                    id=item["id"],
                    code=item["code"],
                    names=tuple(item["names"]),
                    synonyms=tuple(item.get("synonyms", [])),
                    features=dict(item.get("features", {})),
                    unit=item.get("unit", "adet"),
                )


def seed_demo_catalog(store: CatalogStore) -> list[Product]:
    """Pilot denemeleri için örnek ürünler."""
    return [
        store.add(
            code="P-001",
            names=["Santrifüj Pompa"],
            synonyms=["santrifuj pompa", "centrifugal pump"],
            features={"DN": "50", "basma_yuksekligi_m": 45, "basinc_sinifi": "PN16"},
        ),
        store.add(
            code="P-002",
            names=["Dalgıç Pompa"],
            synonyms=["derin kuyu pompası"],
            features={"DN": "80", "basma_yuksekligi_m": 60},
        ),
        store.add(
            code="V-001",
            names=["Sürgülü Vana"],
            synonyms=["sürgülü vana", "gate valve"],
            features={"DN": "80", "basinc_sinifi": "PN16"},
        ),
        store.add(
            code="V-002",
            names=["Çekvalf"],
            synonyms=["çek valf", "check valve"],
            features={"DN": "80", "basinc_sinifi": "PN16"},
        ),
        store.add(
            code="V-003",
            names=["Küresel Vana"],
            synonyms=["ball valve"],
            features={"DN": "25", "basinc_sinifi": "PN40"},
        ),
    ]
