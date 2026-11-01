"""Süreç-içi ölçüm kayıtları (MVP).

HTTP sayaçları ara katmanda tutulur; iş, model ve teklif ölçümleri
`/v1/metrics` anında depolardan taranır. Dışa aktarma (harici izleme
sistemine gönderim) pilot sonrasına bırakılmıştır.
"""

from __future__ import annotations

import threading
import time


class MetricsRegistry:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._started = time.time()
        self._counters = {"total": 0, "2xx": 0, "3xx": 0, "4xx": 0, "5xx": 0}

    def record(self, status_code: int) -> None:
        with self._lock:
            self._counters["total"] += 1
            bucket = f"{status_code // 100}xx"
            if bucket in self._counters:
                self._counters[bucket] += 1

    def snapshot(self) -> dict[str, object]:
        with self._lock:
            counters = dict(self._counters)
        return {
            "total": counters["total"],
            "by_class": {key: counters[key] for key in ("2xx", "3xx", "4xx", "5xx")},
            "uptime_seconds": round(time.time() - self._started, 1),
        }
