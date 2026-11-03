"""Immutable file store (content-addressed).

The same content always resolves to the same id; written content cannot
be changed. A managed object-store implementation moves behind this
interface.
"""

from __future__ import annotations

import hashlib
import os
from dataclasses import dataclass
from typing import Protocol

_HEX = frozenset("0123456789abcdef")


@dataclass(frozen=True)
class StoredFile:
    file_id: str  # sha256 hex
    name: str
    size: int
    sha256: str


class BlobStore(Protocol):
    def put(self, name: str, content: bytes) -> StoredFile:
        ...

    def get(self, file_id: str) -> bytes:
        ...


class LocalBlobStore:
    """Filesystem-based, single-node store."""

    def __init__(self, root: str) -> None:
        self._root = root
        os.makedirs(root, exist_ok=True)

    def put(self, name: str, content: bytes) -> StoredFile:
        digest = hashlib.sha256(content).hexdigest()
        path = os.path.join(self._root, digest)
        if not os.path.exists(path):
            tmp_path = f"{path}.tmp-{os.getpid()}"
            with open(tmp_path, "wb") as handle:
                handle.write(content)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(tmp_path, path)
        return StoredFile(file_id=digest, name=name, size=len(content), sha256=digest)

    def get(self, file_id: str) -> bytes:
        if not file_id or any(char not in _HEX for char in file_id):
            raise KeyError(file_id)
        try:
            with open(os.path.join(self._root, file_id), "rb") as handle:
                content = handle.read()
        except FileNotFoundError:
            raise KeyError(file_id)
        if hashlib.sha256(content).hexdigest() != file_id:
            raise ValueError(f"blob integrity error: {file_id}")
        return content
