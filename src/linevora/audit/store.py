"""Append-only audit log store.

The MVP implementation is in-memory; the persistent implementation
moves behind this interface with a managed database.
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
    """Single-process, append-only in-memory store. Records are immutable."""

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
