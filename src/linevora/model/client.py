"""Model client interface: every model call goes through here.

Changing the provider does not affect this interface. Until a managed
service adapter is added, a fake client plus a metering wrapper is used.
"""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from typing import Any, Callable, Protocol


class ModelError(Exception):
    """The model call failed."""


class ModelClient(Protocol):
    @property
    def name(self) -> str:
        ...

    def complete(self, system: str, user: str) -> str:
        """Returns a raw text response; parsing/validation is the job of schemas.py."""
        ...


class FakeModelClient:
    """A client that returns scripted responses: for tests and development."""

    def __init__(self, responses: dict[str, str] | None = None) -> None:
        self._responses = dict(responses or {})

    @property
    def name(self) -> str:
        return "fake"

    def complete(self, system: str, user: str) -> str:
        _ = system
        try:
            return self._responses[user]
        except KeyError:
            raise ModelError("unscripted input")


class HttpModelClient:
    """Managed model-service adapter (OpenAI-compatible chat API).

    Configuration is via environment variables: ``LINEVORA_MODEL_URL``
    (e.g. ``https://.../v1/chat/completions``), ``LINEVORA_MODEL_API_KEY``,
    ``LINEVORA_MODEL_NAME``. It contains no provider-specific code; it works
    with any service whose endpoint accepts ``{model, messages}`` and returns
    ``choices[0].message.content``. On a network error it retries a limited
    number of times, then raises ``ModelError`` (an off-schema response never
    enters the pipeline; validation lives in the ``schemas.py`` layer).
    """

    def __init__(
        self,
        url: str,
        api_key: str = "",
        model: str = "",
        timeout_seconds: float = 30.0,
        max_attempts: int = 3,
        opener: Callable[..., Any] | None = None,
        backoff_seconds: float = 0.5,
    ) -> None:
        if not url:
            raise ValueError("a model URL is required")
        self._url = url
        self._api_key = api_key
        self._model = model
        self._timeout = timeout_seconds
        self._max_attempts = max(1, max_attempts)
        self._opener = opener or urllib.request.urlopen
        self._backoff = max(0.0, backoff_seconds)

    @property
    def name(self) -> str:
        return f"http:{self._model or 'default'}"

    def complete(self, system: str, user: str) -> str:
        payload = {
            "model": self._model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        }
        last_error: Exception | None = None
        for attempt in range(self._max_attempts):
            if attempt and self._backoff:
                time.sleep(self._backoff * (2 ** (attempt - 1)))
            try:
                request = urllib.request.Request(
                    self._url,
                    data=json.dumps(payload).encode("utf-8"),
                    headers={
                        "Content-Type": "application/json",
                        **(
                            {"Authorization": f"Bearer {self._api_key}"}
                            if self._api_key
                            else {}
                        ),
                    },
                    method="POST",
                )
                with self._opener(request, timeout=self._timeout) as response:
                    body = json.loads(response.read().decode("utf-8"))
                content = body["choices"][0]["message"]["content"]
                if not isinstance(content, str) or not content.strip():
                    raise ModelError("empty model response")
                return content
            except ModelError:
                raise
            except Exception as exc:  # network / HTTP / JSON errors
                last_error = exc
        raise ModelError(f"model call failed: {last_error}")


@dataclass(frozen=True)
class CallRecord:
    model: str
    prompt_chars: int
    response_chars: int
    latency_ms: float
    ok: bool

    @property
    def estimated_tokens(self) -> int:
        # Rough estimate when the provider has no usage field: ~4 chars/token.
        return (self.prompt_chars + self.response_chars + 3) // 4


@dataclass
class MeteringClient:
    """A wrapper that records call counts/volume (the basis of cost tracking)."""

    inner: ModelClient
    calls: list[CallRecord] = field(default_factory=list)

    @property
    def name(self) -> str:
        return self.inner.name

    def complete(self, system: str, user: str) -> str:
        start = time.perf_counter()
        ok = False
        try:
            response = self.inner.complete(system, user)
            ok = True
            return response
        finally:
            elapsed_ms = (time.perf_counter() - start) * 1000
            self.calls.append(
                CallRecord(
                    model=self.name,
                    prompt_chars=len(system) + len(user),
                    response_chars=len(response) if ok else 0,
                    latency_ms=elapsed_ms,
                    ok=ok,
                )
            )
