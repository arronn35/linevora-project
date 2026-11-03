"""Report records: missing information and alternative suggestions."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class InformationGap:
    id: str
    version_id: str
    requirement_id: str
    field: str
    question: str
    severity: str = "mandatory"  # mandatory | info
    status: str = "open"
    answer: str = ""


@dataclass(frozen=True)
class ComparisonRow:
    criterion: str
    wanted: Any
    offered: Any
    match: bool


@dataclass(frozen=True)
class Alternative:
    id: str
    requirement_id: str
    product_id: str
    score: float
    comparison: tuple[ComparisonRow, ...] = ()
    reasons: tuple[str, ...] = ()
    status: str = "pending"
