"""Lexical baseline matcher: a transparent, measurable starting point.

Score = 0.50 name similarity + 0.35 feature match + 0.15 unit match.
A vector-index adapter moves behind the same interface later; this
baseline is the comparison point on the eval set.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from ..catalog.models import Product
from .models import Requirement


@dataclass(frozen=True)
class ScoredProduct:
    product: Product
    score: float
    reasons: tuple[str, ...]


def tokens(text: str) -> set[str]:
    return set(re.findall(r"\w+", text.lower(), re.UNICODE))


def _norm(value: object) -> str:
    return str(value).strip().lower()


class LexicalMatcher:
    def __init__(self, top_k: int = 3, min_score: float = 0.35) -> None:
        self._top_k = top_k
        self._min_score = min_score

    def suggest(
        self, requirement: Requirement, products: list[Product]
    ) -> list[ScoredProduct]:
        scored = [self._score(requirement, product) for product in products]
        kept = [item for item in scored if item.score >= self._min_score]
        kept.sort(key=lambda item: item.score, reverse=True)
        return kept[: self._top_k]

    def _score(self, requirement: Requirement, product: Product) -> ScoredProduct:
        reasons: list[str] = []
        wanted = tokens(requirement.product_type)
        offered = tokens(" ".join([*product.names, *product.synonyms, product.code]))
        overlap = (len(wanted & offered) / len(wanted)) if wanted else 0.0
        if wanted & offered:
            matched = " ".join(sorted(wanted & offered))
            reasons.append(f"product name matched: {matched}")
        feature_fraction = 0.0
        if requirement.features:
            hits = 0
            lowered = {_norm(key): value for key, value in product.features.items()}
            for key, value in requirement.features.items():
                if _norm(key) in lowered and _norm(lowered[_norm(key)]) == _norm(value):
                    hits += 1
                    reasons.append(f"feature matched: {key}={value}")
            feature_fraction = hits / len(requirement.features)
        unit_hit = (
            1.0
            if requirement.unit and product.unit and _norm(requirement.unit) == _norm(product.unit)
            else 0.0
        )
        if unit_hit:
            reasons.append(f"unit matched: {requirement.unit}")
        score = 0.50 * overlap + 0.35 * feature_fraction + 0.15 * unit_hit
        return ScoredProduct(product=product, score=score, reasons=tuple(reasons))
