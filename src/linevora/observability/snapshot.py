"""Snapshot: a JSON backup of all in-memory stores.

Until a persistent database is connected, durability is provided this
way: `POST /v1/admin/snapshot` writes a consistent file and the app loads
it at startup when present. Writes are atomic (temp file + rename) and
the last N generations are kept. The file store (`blob_dir`) is backed
up separately.
"""

from __future__ import annotations

import json
import os
import threading
from typing import Any, Callable

ToSnapshot = Callable[[], Any]
LoadSnapshot = Callable[[Any], None]


class SnapshotManager:
    def __init__(
        self,
        path: str,
        providers: dict[str, tuple[ToSnapshot, LoadSnapshot]],
        keep: int = 5,
    ) -> None:
        self._path = path
        self._providers = dict(providers)
        self._keep = keep
        self._lock = threading.Lock()

    @property
    def path(self) -> str:
        return self._path

    def save(self) -> str:
        with self._lock:
            data = {name: to_snapshot() for name, (to_snapshot, _) in self._providers.items()}
            parent = os.path.dirname(os.path.abspath(self._path))
            os.makedirs(parent, exist_ok=True)
            self._rotate()
            tmp_path = f"{self._path}.tmp"
            with open(tmp_path, "w", encoding="utf-8") as handle:
                json.dump(data, handle, ensure_ascii=False)
            os.replace(tmp_path, self._path)
            return self._path

    def load(self) -> bool:
        if not os.path.exists(self._path):
            return False
        with open(self._path, encoding="utf-8") as handle:
            data = json.load(handle)
        for name, (_, load_snapshot) in self._providers.items():
            if name in data:
                load_snapshot(data[name])
        return True

    def _rotate(self) -> None:
        for index in range(self._keep - 1, 0, -1):
            older = f"{self._path}.{index}"
            if os.path.exists(older):
                os.replace(older, f"{self._path}.{index + 1}")
        if os.path.exists(self._path):
            os.replace(self._path, f"{self._path}.1")
        overflow = f"{self._path}.{self._keep + 1}"
        if os.path.exists(overflow):
            os.remove(overflow)
