"""Vector-based semantic matcher.

It does not depend on an external service: texts are turned into
character n-gram + word hashing vectors and scored by cosine similarity.
For inquiries written with different terminology it produces candidates
that lexical matching misses. It is not the final decision-maker; inside
``HybridMatcher`` it is blended with the lexical score and A/B-compared
on the eval set.
"""

from __future__ import annotations

import hashlib
import math
import re

from ..catalog.models import Product
from .matcher import LexicalMatcher, ScoredProduct
from .models import Requirement

_DIM = 512


def _tokens(text: str) -> list[str]:
    return re.findall(r"\w+", text.lower(), re.UNICODE)


def _vector(text: str) -> dict[int, float]:
    vec: dict[int, float] = {}
    tokens = _tokens(text)
    features: list[str] = list(tokens)
    for token in tokens:  # character 3-grams: spelling/terminology tolerance
        padded = f"#{token}#"
        features.extend(padded[i : i + 3] for i in range(len(padded) - 2))
    for feature in features:
        digest = hashlib.md5(feature.encode("utf-8")).digest()
        idx = int.from_bytes(digest[:4], "little") % _DIM
        vec[idx] = vec.get(idx, 0.0) + 1.0
    return vec


def _cosine(a: dict[int, float], b: dict[int, float]) -> float:
    if not a or not b:
        return 0.0
    dot = sum(value * b.get(idx, 0.0) for idx, value in a.items())
    norm_a = math.sqrt(sum(v * v for v in a.values()))
    norm_b = math.sqrt(sum(v * v for v in b.values()))
    return dot / (norm_a * norm_b) if norm_a and norm_b else 0.0


def _product_text(product: Product) -> str:
    parts = [product.code, *product.names, *product.synonyms]
    parts.extend(f"{k} {v}" for k, v in product.features.items())
    return " ".join(str(p) for p in parts)


def _requirement_text(requirement: Requirement) -> str:
    parts = [requirement.product_type]
    parts.extend(f"{k} {v}" for k, v in requirement.features.items())
    if requirement.unit:
        parts.append(requirement.unit)
    return " ".join(str(p) for p in parts)


class VectorMatcher:
    def __init__(self, top_k: int = 3, min_score: float = 0.15) -> None:
        self._top_k = top_k
        self._min_score = min_score

    def suggest(
        self, requirement: Requirement, products: list[Product]
    ) -> list[ScoredProduct]:
        req_vec = _vector(_requirement_text(requirement))
        scored = []
        for product in products:
            score = _cosine(req_vec, _vector(_product_text(product)))
            if score >= self._min_score:
                scored.append(
                    ScoredProduct(
                        product=product,
                        score=round(score, 4),
                        reasons=(f"semantic similarity: {score:.2f}",),
                    )
                )
        scored.sort(key=lambda item: item.score, reverse=True)
        return scored[: self._top_k]


class EmbeddingMatcher:
    """Cosine matching behind an embedder (local hashing or HTTP)."""

    def __init__(self, embedder=None, top_k: int = 3, min_score: float = 0.15) -> None:
        from .embedder import HashingEmbedder, cosine_any

        self._embedder = embedder or HashingEmbedder()
        self._cosine = cosine_any
        self._top_k = top_k
        self._min_score = min_score

    def suggest(self, requirement, products):
        req_vec = self._embedder.embed(_requirement_text(requirement))
        scored = []
        for product in products:
            score = self._cosine(req_vec, self._embedder.embed(_product_text(product)))
            if score >= self._min_score:
                scored.append(
                    ScoredProduct(
                        product=product,
                        score=round(score, 4),
                        reasons=(f"embedding similarity: {score:.2f}",),
                    )
                )
        scored.sort(key=lambda item: item.score, reverse=True)
        return scored[: self._top_k]


class HybridMatcher:
    """Lexical (0.6) + vector (0.4) blend; a single interface for eval A/B."""

    def __init__(self, top_k: int = 3, min_score: float = 0.3) -> None:
        self._top_k = top_k
        self._min_score = min_score
        self._lexical = LexicalMatcher(top_k=10, min_score=0.0)
        self._vector = VectorMatcher(top_k=10, min_score=0.0)

    def suggest(
        self, requirement: Requirement, products: list[Product]
    ) -> list[ScoredProduct]:
        merged: dict[str, ScoredProduct] = {}
        for item in self._lexical.suggest(requirement, products):
            merged[item.product.id] = ScoredProduct(
                item.product, item.score * 0.6, item.reasons
            )
        for item in self._vector.suggest(requirement, products):
            if item.product.id in merged:
                prev = merged[item.product.id]
                merged[item.product.id] = ScoredProduct(
                    prev.product,
                    round(prev.score + item.score * 0.4, 4),
                    prev.reasons + item.reasons,
                )
            else:
                merged[item.product.id] = ScoredProduct(
                    item.product, round(item.score * 0.4, 4), item.reasons
                )
        kept = [i for i in merged.values() if i.score >= self._min_score]
        kept.sort(key=lambda i: i.score, reverse=True)
        return kept[: self._top_k]
