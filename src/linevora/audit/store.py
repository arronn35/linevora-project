"""Yalnızca eklenebilen denetim kaydı deposu.

MVP gerçeklemesi bellek içidir; kalıcı gerçekleme Adım 8'de
yönetilen veritabanıyla bu arayüzün arkasına geçer.
"""

from __future__ import annotations

import threading
import time
from dataclasses import asdict, dataclass
from typing import Protocol


@dataclass(frozen=True)
class AuditEntry:
    seq: int
    timestamp: float
    actor: str
    action: str
    target: str
    detail: str = ""

    def to_dict(self) -> dict[str, object]:
        return {
            "seq": self.seq,
            "timestamp": self.timestamp,
            "actor": self.actor,
            "action": self.action,
            "target": self.target,
            "detail": self.detail,
        }


class AuditStore(Protocol):
    def append(self, actor: str, action: str, target: str, detail: str = "") -> AuditEntry:
        ...

    def list(self) -> list[AuditEntry]:
        ...


class InMemoryAuditStore:
    """Tek süreçlik, eklemeli bellek deposu. Kayıtlar değişmezdir."""

    def __init__(self) -> None:
        self._entries: list[AuditEntry] = []
        self._lock = threading.Lock()

    def append(self, actor: str, action: str, target: str, detail: str = "") -> AuditEntry:
        with self._lock:
            entry = AuditEntry(
                seq=len(self._entries) + 1,
                timestamp=time.time(),
                actor=actor,
                action=action,
                target=target,
                detail=detail,
            )
            self._entries.append(entry)
            return entry

    def list(self) -> list[AuditEntry]:
        with self._lock:
            return list(self._entries)

    def to_snapshot(self) -> list[dict]:
        with self._lock:
            return [asdict(entry) for entry in self._entries]

    def load_snapshot(self, data: list[dict]) -> None:
        with self._lock:
            self._entries = [AuditEntry(**item) for item in data]
