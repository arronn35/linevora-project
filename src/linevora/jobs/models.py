"""Job record. Statuses: queued / running / done / failed."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any


@dataclass
class Job:
    id: str
    kind: str
    payload: dict[str, Any]
    actor: str
    max_attempts: int = 3
    status: str = "queued"
    attempts: int = 0
    result: dict[str, Any] | None = None
    error: str | None = None
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
