"""Embedding provider abstraction.

Default: local hashing embeddings (no service). When ``LINEVORA_EMBEDDING_URL``
is given, an OpenAI-compatible ``/embeddings`` endpoint is used:
``{model, input}`` → ``data[0].embedding``.
"""

from __future__ import annotations

import json
import math
import urllib.request
from typing import Any, Callable, Protocol

from .vector_matcher import _cosine, _vector


class Embedder(Protocol):
    def embed(self, text: str) -> dict[int, float] | list[float]:
        ...


class HashingEmbedder:
    """Local, deterministic embedding (no external service)."""

    def embed(self, text: str) -> dict[int, float]:
        return _vector(text)


class HttpEmbedder:
    def __init__(
        self,
        url: str,
        api_key: str = "",
        model: str = "",
        timeout_seconds: float = 30.0,
        opener: Callable[..., Any] | None = None,
    ) -> None:
        if not url:
            raise ValueError("an embedding URL is required")
        self._url = url
        self._api_key = api_key
        self._model = model
        self._timeout = timeout_seconds
        self._opener = opener or urllib.request.urlopen
        self._cache: dict[str, list[float]] = {}

    def embed(self, text: str) -> list[float]:
        if text in self._cache:
            return self._cache[text]
        request = urllib.request.Request(
            self._url,
            data=json.dumps({"model": self._model, "input": text}).encode(),
            headers={
                "Content-Type": "application/json",
                **({"Authorization": f"Bearer {self._api_key}"} if self._api_key else {}),
            },
            method="POST",
        )
        with self._opener(request, timeout=self._timeout) as response:
            body = json.loads(response.read().decode("utf-8"))
        vector = [float(x) for x in body["data"][0]["embedding"]]
        self._cache[text] = vector
        return vector


def _to_dense(vector: Any) -> list[float]:
    if isinstance(vector, dict):
        size = max(vector) + 1 if vector else 0
        dense = [0.0] * size
        for idx, value in vector.items():
            dense[idx] = value
        return dense
    return list(vector)


def cosine_any(a: Any, b: Any) -> float:
    if isinstance(a, dict) and isinstance(b, dict):
        return _cosine(a, b)
    da, db = _to_dense(a), _to_dense(b)
    size = max(len(da), len(db))
    da += [0.0] * (size - len(da))
    db += [0.0] * (size - len(db))
    dot = sum(x * y for x, y in zip(da, db))
    na = math.sqrt(sum(x * x for x in da))
    nb = math.sqrt(sum(x * x for x in db))
    return dot / (na * nb) if na and nb else 0.0
