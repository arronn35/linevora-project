"""Requirement and match-suggestion records."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class Requirement:
    id: str
    version_id: str
    product_type: str
    features: dict[str, Any] = field(default_factory=dict)
    quantity: Any = None
    unit: str | None = None
    page: int = 1
    quote: str = ""


@dataclass(frozen=True)
class MatchSuggestion:
    id: str
    requirement_id: str
    product_id: str
    score: float
    reasons: tuple[str, ...] = ()
    status: str = "pending"
    page: int = 1
    quote: str = ""
