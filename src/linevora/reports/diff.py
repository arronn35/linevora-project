"""Sürüm farkı: iki sürümün gereksinimlerini karşılaştırır.

Saf işlevdir; sonuç saklanmaz, istek anında hesaplanır.
"""

from __future__ import annotations

from typing import Any

from ..matching.models import Requirement


def _norm(value: Any) -> str:
    return str(value).strip().lower() if value is not None else ""


def _pair(
    old: list[Requirement], new: list[Requirement]
) -> list[tuple[Requirement | None, Requirement | None]]:
    unused = list(new)
    pairs: list[tuple[Requirement | None, Requirement | None]] = []
    for old_req in old:
        match = next(
            (cand for cand in unused if _norm(cand.product_type) == _norm(old_req.product_type)),
            None,
        )
        if match is not None:
            unused.remove(match)
        pairs.append((old_req, match))
    for remaining in unused:
        pairs.append((None, remaining))
    return pairs


def diff_requirements(
    old: list[Requirement], new: list[Requirement]
) -> list[dict[str, Any]]:
    changes: list[dict[str, Any]] = []
    for old_req, new_req in _pair(old, new):
        if old_req is None and new_req is not None:
            changes.append(
                {
                    "type": "eklendi",
                    "product_type": new_req.product_type,
                    "field": None,
                    "old": None,
                    "new": None,
                }
            )
        elif new_req is None and old_req is not None:
            changes.append(
                {
                    "type": "çıkarıldı",
                    "product_type": old_req.product_type,
                    "field": None,
                    "old": None,
                    "new": None,
                }
            )
        elif old_req is not None and new_req is not None:
            if old_req.quantity != new_req.quantity:
                changes.append(
                    {
                        "type": "değişti",
                        "product_type": old_req.product_type,
                        "field": "miktar",
                        "old": old_req.quantity,
                        "new": new_req.quantity,
                    }
                )
            if _norm(old_req.unit) != _norm(new_req.unit):
                changes.append(
                    {
                        "type": "değişti",
                        "product_type": old_req.product_type,
                        "field": "birim",
                        "old": old_req.unit,
                        "new": new_req.unit,
                    }
                )
            keys = set(old_req.features) | set(new_req.features)
            for key in sorted(keys):
                if _norm(old_req.features.get(key)) != _norm(new_req.features.get(key)):
                    changes.append(
                        {
                            "type": "değişti",
                            "product_type": old_req.product_type,
                            "field": f"özellik:{key}",
                            "old": old_req.features.get(key),
                            "new": new_req.features.get(key),
                        }
                    )
    changes.sort(key=lambda item: (item["product_type"], item["field"] or "", item["type"]))
    return changes
