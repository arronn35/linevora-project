"""Eksik bilgi ve alternatif depoları. MVP gerçeklemesi bellek içidir;
kalıcı gerçekleme Adım 8'de yönetilen veritabanıyla bu arayüzlerin
arkasına geçer.
"""

from __future__ import annotations

import threading
import uuid
from dataclasses import asdict
from typing import Protocol

from .models import Alternative, ComparisonRow, InformationGap


class GapStore(Protocol):
    def add(
        self,
        version_id: str,
        requirement_id: str,
        field: str,
        question: str,
        severity: str = "zorunlu",
    ) -> InformationGap:
        ...

    def list_for_version(self, version_id: str) -> list[InformationGap]:
        ...

    def get(self, gap_id: str) -> InformationGap:
        ...

    def update_status(self, gap_id: str, status: str, answer: str = "") -> InformationGap:
        ...

    def delete_for_version(self, version_id: str) -> None:
        ...


class AlternativeStore(Protocol):
    def add(
        self,
        requirement_id: str,
        product_id: str,
        score: float,
        comparison: list[ComparisonRow] | None = None,
        reasons: list[str] | None = None,
    ) -> Alternative:
        ...

    def list_for_requirement(self, requirement_id: str) -> list[Alternative]:
        ...

    def get(self, alternative_id: str) -> Alternative:
        ...

    def update_status(self, alternative_id: str, status: str) -> Alternative:
        ...

    def delete_for_requirements(self, requirement_ids: list[str]) -> None:
        ...


class InMemoryGapStore:
    def __init__(self) -> None:
        self._items: dict[str, InformationGap] = {}
        self._lock = threading.Lock()

    def add(
        self,
        version_id: str,
        requirement_id: str,
        field: str,
        question: str,
        severity: str = "zorunlu",
    ) -> InformationGap:
        with self._lock:
            gap = InformationGap(
                id=uuid.uuid4().hex,
                version_id=version_id,
                requirement_id=requirement_id,
                field=field,
                question=question,
                severity=severity,
            )
            self._items[gap.id] = gap
            return gap

    def get(self, gap_id: str) -> InformationGap:
        with self._lock:
            try:
                return self._items[gap_id]
            except KeyError:
                raise KeyError(gap_id)

    def update_status(self, gap_id: str, status: str, answer: str = "") -> InformationGap:
        from dataclasses import replace

        if status not in ("açık", "yanıtlandı", "vazgeçildi"):
            raise ValueError(f"geçersiz eksik durumu: {status}")
        with self._lock:
            updated = replace(self._items[gap_id], status=status, answer=answer)
            self._items[gap_id] = updated
            return updated

    def list_for_version(self, version_id: str) -> list[InformationGap]:
        with self._lock:
            return [item for item in self._items.values() if item.version_id == version_id]

    def delete_for_version(self, version_id: str) -> None:
        with self._lock:
            for key in [
                key for key, item in self._items.items() if item.version_id == version_id
            ]:
                del self._items[key]

    def to_snapshot(self) -> dict:
        with self._lock:
            return {"items": [asdict(item) for item in self._items.values()]}

    def load_snapshot(self, data: dict) -> None:
        with self._lock:
            self._items = {
                item["id"]: InformationGap(**item) for item in data.get("items", [])
            }


class InMemoryAlternativeStore:
    def __init__(self) -> None:
        self._items: dict[str, Alternative] = {}
        self._lock = threading.Lock()

    def add(
        self,
        requirement_id: str,
        product_id: str,
        score: float,
        comparison: list[ComparisonRow] | None = None,
        reasons: list[str] | None = None,
    ) -> Alternative:
        with self._lock:
            alternative = Alternative(
                id=uuid.uuid4().hex,
                requirement_id=requirement_id,
                product_id=product_id,
                score=score,
                comparison=tuple(comparison or []),
                reasons=tuple(reasons or []),
            )
            self._items[alternative.id] = alternative
            return alternative

    def get(self, alternative_id: str) -> Alternative:
        with self._lock:
            try:
                return self._items[alternative_id]
            except KeyError:
                raise KeyError(alternative_id)

    def update_status(self, alternative_id: str, status: str) -> Alternative:
        from dataclasses import replace

        if status not in ("bekliyor", "onaylandı", "reddedildi"):
            raise ValueError(f"geçersiz alternatif durumu: {status}")
        with self._lock:
            updated = replace(self._items[alternative_id], status=status)
            self._items[alternative_id] = updated
            return updated

    def list_for_requirement(self, requirement_id: str) -> list[Alternative]:
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
                self._items[item["id"]] = Alternative(
                    id=item["id"],
                    requirement_id=item["requirement_id"],
                    product_id=item["product_id"],
                    score=item["score"],
                    comparison=tuple(
                        ComparisonRow(**row) for row in item.get("comparison", [])
                    ),
                    reasons=tuple(item.get("reasons", [])),
                    status=item.get("status", "bekliyor"),
                )
