"""Catalog product record (Product in the data model)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class Product:
    id: str
    code: str
    names: tuple[str, ...]
    synonyms: tuple[str, ...] = ()
    features: dict[str, Any] = field(default_factory=dict)
    unit: str = "pcs"
