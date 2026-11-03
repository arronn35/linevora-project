"""Alternative suggestions: criterion-compared candidates when there is no exact match."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ..catalog.models import Product
from ..matching.matcher import ScoredProduct, tokens
from ..matching.models import Requirement
from .models import ComparisonRow

EXACT_THRESHOLD = 0.85


@dataclass(frozen=True)
class AlternativeDraft:
    product_id: str
    score: float
    comparison: list[ComparisonRow]
    reasons: list[str]


def _norm(value: Any) -> str:
    return str(value).strip().lower() if value is not None else ""


def compare(requirement: Requirement, product: Product) -> list[ComparisonRow]:
    rows = [
        ComparisonRow(
            criterion="product name",
            wanted=requirement.product_type,
            offered=", ".join(product.names),
            match=bool(tokens(requirement.product_type) & tokens(" ".join(product.names))),
        )
    ]
    for key, wanted in requirement.features.items():
        offered = product.features.get(key)
        rows.append(
            ComparisonRow(
                criterion=f"feature:{key}",
                wanted=wanted,
                offered=offered,
                match=offered is not None and _norm(offered) == _norm(wanted),
            )
        )
    if requirement.unit:
        rows.append(
            ComparisonRow(
                criterion="unit",
                wanted=requirement.unit,
                offered=product.unit,
                match=_norm(product.unit) == _norm(requirement.unit),
            )
        )
    return rows


def build_alternatives(
    requirement: Requirement, scored: list[ScoredProduct]
) -> list[AlternativeDraft]:
    """If the best candidate counts as exact, no alternative is produced."""
    if any(item.score >= EXACT_THRESHOLD for item in scored):
        return []
    return [
        AlternativeDraft(
            product_id=item.product.id,
            score=item.score,
            comparison=compare(requirement, item.product),
            reasons=list(item.reasons),
        )
        for item in scored
    ]
