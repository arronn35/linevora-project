"""Gereksinim ve öneri depoları. MVP gerçeklemesi bellek içidir;
kalıcı gerçekleme Adım 8'de yönetilen veritabanıyla bu arayüzlerin
arkasına geçer.
"""

from __future__ import annotations

import copy
import threading
import uuid
from dataclasses import asdict
from typing import Any, Protocol

from .models import MatchSuggestion, Requirement


class RequirementStore(Protocol):
    def add(
        self,
        version_id: str,
        product_type: str,
        features: dict[str, Any] | None = None,
        quantity: Any = None,
        unit: str | None = None,
        page: int = 1,
        quote: str = "",
    ) -> Requirement:
        ...

    def list_for_version(self, version_id: str) -> list[Requirement]:
        ...

    def get(self, requirement_id: str) -> Requirement:
        ...

    def update(self, requirement_id: str, **changes) -> Requirement:
        ...

    def delete_for_version(self, version_id: str) -> list[str]:
        """Sürümün gereksinimlerini siler, silinen kimlikleri döndürür."""
        ...


class SuggestionStore(Protocol):
    def add(
        self,
        requirement_id: str,
        product_id: str,
        score: float,
        reasons: list[str] | None = None,
        page: int = 1,
        quote: str = "",
    ) -> MatchSuggestion:
        ...

    def list_for_requirement(self, requirement_id: str) -> list[MatchSuggestion]:
        ...

    def get(self, suggestion_id: str) -> MatchSuggestion:
        ...

    def update_status(self, suggestion_id: str, status: str) -> MatchSuggestion:
        ...

    def delete_for_requirements(self, requirement_ids: list[str]) -> None:
        ...


class InMemoryRequirementStore:
    def __init__(self) -> None:
        self._items: dict[str, Requirement] = {}
        self._lock = threading.Lock()

    def add(
        self,
        version_id: str,
        product_type: str,
        features: dict[str, Any] | None = None,
        quantity: Any = None,
        unit: str | None = None,
        page: int = 1,
        quote: str = "",
    ) -> Requirement:
        # Değişmez-1: kaynaksız gereksinim yazılamaz.
        if not str(quote).strip():
            raise ValueError("kaynak alıntı (quote) zorunlu")
        if not isinstance(page, int) or page < 1:
            raise ValueError("kaynak sayfa (page) >= 1 olmalı")
        with self._lock:
            requirement = Requirement(
                id=uuid.uuid4().hex,
                version_id=version_id,
                product_type=product_type,
                features=dict(features or {}),
                quantity=quantity,
                unit=unit,
                page=page,
                quote=quote,
            )
            self._items[requirement.id] = requirement
            return requirement

    def get(self, requirement_id: str) -> Requirement:
        with self._lock:
            try:
                return copy.deepcopy(self._items[requirement_id])
            except KeyError:
                raise KeyError(requirement_id)

    def update(self, requirement_id: str, **changes) -> Requirement:
        from dataclasses import replace

        allowed = {"product_type", "features", "quantity", "unit"}
        with self._lock:
            current = self._items[requirement_id]
            updated = replace(
                current,
                **{k: v for k, v in changes.items() if k in allowed and v is not None},
            )
            self._items[requirement_id] = updated
            return updated

    def list_for_version(self, version_id: str) -> list[Requirement]:
        with self._lock:
            return copy.deepcopy([item for item in self._items.values() if item.version_id == version_id])

    def delete_for_version(self, version_id: str) -> list[str]:
        with self._lock:
            removed = [key for key, item in self._items.items() if item.version_id == version_id]
            for key in removed:
                del self._items[key]
            return removed

    def to_snapshot(self) -> dict:
        with self._lock:
            return {"items": [asdict(item) for item in self._items.values()]}

    def load_snapshot(self, data: dict) -> None:
        with self._lock:
            self._items = {}
            for item in data.get("items", []):
                self._items[item["id"]] = Requirement(
                    id=item["id"],
                    version_id=item["version_id"],
                    product_type=item["product_type"],
                    features=dict(item.get("features", {})),
                    quantity=item.get("quantity"),
                    unit=item.get("unit"),
                    page=item.get("page", 1),
                    quote=item.get("quote", ""),
                )


class InMemorySuggestionStore:
    def __init__(self) -> None:
        self._items: dict[str, MatchSuggestion] = {}
        self._lock = threading.Lock()

    def add(
        self,
        requirement_id: str,
        product_id: str,
        score: float,
        reasons: list[str] | None = None,
        page: int = 1,
        quote: str = "",
    ) -> MatchSuggestion:
        with self._lock:
            suggestion = MatchSuggestion(
                id=uuid.uuid4().hex,
                requirement_id=requirement_id,
                product_id=product_id,
                score=score,
                reasons=tuple(reasons or []),
                page=page,
                quote=quote,
            )
            self._items[suggestion.id] = suggestion
            return suggestion

    def get(self, suggestion_id: str) -> MatchSuggestion:
        with self._lock:
            try:
                return self._items[suggestion_id]
            except KeyError:
                raise KeyError(suggestion_id)

    def update_status(self, suggestion_id: str, status: str) -> MatchSuggestion:
        from dataclasses import replace

        if status not in ("bekliyor", "onaylandı", "reddedildi", "düzeltildi"):
            raise ValueError(f"geçersiz öneri durumu: {status}")
        with self._lock:
            updated = replace(self._items[suggestion_id], status=status)
            self._items[suggestion_id] = updated
            return updated

    def list_for_requirement(self, requirement_id: str) -> list[MatchSuggestion]:
        with self._lock:
            return [
                item for item in self._items.values() if item.requirement_id == requirement_id
            ]

    def delete_for_requirements(self, requirement_ids: list[str]) -> None:
        with self._lock:
            doomed = set(requirement_ids)
            for key in [
                key for key, item in self._items.items() if item.requirement_id in doomed
            ]:
                del self._items[key]

    def to_snapshot(self) -> dict:
        with self._lock:
            return {"items": [asdict(item) for item in self._items.values()]}

    def load_snapshot(self, data: dict) -> None:
        with self._lock:
            self._items = {}
            for item in data.get("items", []):
                self._items[item["id"]] = MatchSuggestion(
                    id=item["id"],
                    requirement_id=item["requirement_id"],
                    product_id=item["product_id"],
                    score=item["score"],
                    reasons=tuple(item.get("reasons", [])),
                    status=item.get("status", "bekliyor"),
                    page=item.get("page", 1),
                    quote=item.get("quote", ""),
                )
