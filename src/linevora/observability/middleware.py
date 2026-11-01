"""HTTP ara katmanı: istek kimliği, süre ölçümü, kayıt, güvenlik başlıkları."""

from __future__ import annotations

import logging
import time
import uuid

logger = logging.getLogger("linevora.http")


class RateLimiter:
    """IP başına kayan pencere hız sınırı (özellikle token uç noktası)."""

    def __init__(self, per_minute: int = 60, window_seconds: float = 60.0) -> None:
        self._limit = max(1, per_minute)
        self._window = window_seconds
        self._hits: dict[str, list[float]] = {}

    def allow(self, key: str) -> bool:
        now = time.monotonic()
        hits = [t for t in self._hits.get(key, []) if now - t < self._window]
        if len(hits) >= self._limit:
            self._hits[key] = hits
            return False
        hits.append(now)
        self._hits[key] = hits
        return True


def setup_observability(app) -> None:
    @app.middleware("http")
    async def rate_limit(request, call_next):
        if request.url.path.startswith("/v1/auth/token"):
            limiter = getattr(request.app.state, "rate_limiter", None)
            client = request.client.host if request.client else "unknown"
            if limiter is not None and not limiter.allow(client):
                from fastapi.responses import JSONResponse

                return JSONResponse(
                    status_code=429, content={"detail": "çok fazla istek"}
                )
        return await call_next(request)

    @app.middleware("http")
    async def observability(request, call_next):
        request_id = request.headers.get("x-request-id") or uuid.uuid4().hex
        request.state.request_id = request_id
        start = time.perf_counter()
        response = await call_next(request)
        elapsed_ms = (time.perf_counter() - start) * 1000
        request.app.state.metrics.record(response.status_code)
        logger.info(
            "%s %s -> %s (%.1fms) rid=%s",
            request.method,
            request.url.path,
            response.status_code,
            elapsed_ms,
            request_id,
        )
        response.headers["X-Request-ID"] = request_id
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "no-referrer"
        return response
