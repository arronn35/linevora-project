"""HMAC imzalı, durum taşımayan erişim belirteçleri (MVP).

Biçim: base64url(gövde) + "." + hex(HMAC-SHA256(imza anahtarı, gövde)).
Gövde: {"sub": kullanıcı, "roles": [...], "exp": unix zaman}.
Üretim sertleştirmesi (anahtar rotasyonu, iptal listesi) Adım 8'dedir.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time
from typing import Any


class TokenError(Exception):
    """Belirteç geçersiz ya da süresi dolmuş."""


def _b64encode(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def _b64decode(data: str) -> bytes:
    return base64.urlsafe_b64decode(data + "=" * (-len(data) % 4))


def issue_token(secret: str, subject: str, roles: list[str], ttl_seconds: int, tenant: str = "default") -> str:
    payload = {
        "sub": subject,
        "roles": roles,
        "exp": int(time.time()) + ttl_seconds,
        "jti": hashlib.sha256(f"{subject}:{time.time_ns()}".encode()).hexdigest()[:32],
        "tenant": tenant,
    }
    body = _b64encode(json.dumps(payload, separators=(",", ":")).encode("utf-8"))
    signature = hmac.new(secret.encode(), body.encode(), hashlib.sha256).hexdigest()
    return f"{body}.{signature}"


class RevokedTokens:
    """İptal edilmiş belirteç kimlikleri (jti). Süreç içi; kalıcı sürüm
    aynı arayüzle DB arkasına geçebilir."""

    def __init__(self) -> None:
        self._revoked: set[str] = set()

    def revoke(self, jti: str) -> None:
        if jti:
            self._revoked.add(jti)

    def is_revoked(self, jti: str | None) -> bool:
        return bool(jti) and jti in self._revoked


def verify_token(secret: str, token: str) -> dict[str, Any]:
    try:
        body, signature = token.rsplit(".", 1)
    except ValueError:
        raise TokenError("bozuk belirteç")
    expected = hmac.new(secret.encode(), body.encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected, signature):
        raise TokenError("geçersiz imza")
    try:
        payload = json.loads(_b64decode(body))
        expired = int(payload.get("exp", 0)) < time.time()
    except (ValueError, TypeError):
        raise TokenError("bozuk gövde")
    if expired:
        raise TokenError("süresi dolmuş")
    if not payload.get("sub"):
        raise TokenError("özne yok")
    return {
        "subject": payload["sub"],
        "roles": list(payload.get("roles", [])),
        "jti": payload.get("jti", ""),
        "tenant": payload.get("tenant", "default"),
    }
