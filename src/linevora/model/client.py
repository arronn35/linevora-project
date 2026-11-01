"""Model istemci arayüzü: tüm model çağrıları buradan geçer.

Sağlayıcı değişimi bu arayüzü etkilemez. Yönetilen servis bağdaştırıcısı
Adım 5 ile eklenir; o zamana dek sahte istemci + ölçüm sarayıcı kullanılır.
"""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from typing import Any, Callable, Protocol


class ModelError(Exception):
    """Model çağrısı başarısız."""


class ModelClient(Protocol):
    @property
    def name(self) -> str:
        ...

    def complete(self, system: str, user: str) -> str:
        """Ham metin yanıt döndürür; ayrıştırma/doğrulama schemas.py işidir."""
        ...


class FakeModelClient:
    """Betiklenmiş yanıtlar veren istemci: test ve geliştirme için."""

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
            raise ModelError("betiklenmemiş girdi")


class HttpModelClient:
    """Yönetilen model servisi bağdaştırıcısı (OpenAI-uyumlu chat API).

    Yapılandırma ortam değişkenleriyle: ``LINEVORA_MODEL_URL`` (örn.
    ``https://.../v1/chat/completions``), ``LINEVORA_MODEL_API_KEY``,
    ``LINEVORA_MODEL_NAME``. Sağlayıcıya özgü kod barındırmaz; uç nokta
    ``{model, messages}`` kabul edip ``choices[0].message.content``
    döndüren herhangi bir servisle çalışır. Ağ hatasında sınırlı yeniden
    deneme yapar, sonra ``ModelError`` fırlatır (şema dışı yanıt hatta
    girmez; doğrulama ``schemas.py`` katmanındadır).
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
            raise ValueError("model URL gerekli")
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
                    raise ModelError("boş model yanıtı")
                return content
            except ModelError:
                raise
            except Exception as exc:  # ağ / HTTP / JSON hataları
                last_error = exc
        raise ModelError(f"model çağrısı başarısız: {last_error}")


@dataclass(frozen=True)
class CallRecord:
    model: str
    prompt_chars: int
    response_chars: int
    latency_ms: float
    ok: bool

    @property
    def estimated_tokens(self) -> int:
        # Sağlayıcı usage alanı yokken kaba tahmin: ~4 karakter/token.
        return (self.prompt_chars + self.response_chars + 3) // 4


@dataclass
class MeteringClient:
    """Çağrı adedi/hacim kaydı tutan sarayıcı (maliyet takibinin temeli)."""

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
