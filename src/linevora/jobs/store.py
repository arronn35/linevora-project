"""İş deposu. MVP gerçeklemesi bellek içidir; kalıcı gerçekleme
Adım 8'de yönetilen veritabanıyla bu arayüzün arkasına geçer.
"""

from __future__ import annotations

import copy

import threading
import time
import uuid
from dataclasses import asdict
from typing import Any, Protocol

from .models import Job


class JobStore(Protocol):
    def submit(
        self, kind: str, payload: dict[str, Any], actor: str, max_attempts: int = 3
    ) -> Job:
        ...

    def get(self, job_id: str) -> Job:
        ...

    def list(self) -> list[Job]:
        ...

    def update(self, job: Job) -> Job:
        ...


class InMemoryJobStore:
    def __init__(self) -> None:
        self._jobs: dict[str, Job] = {}
        self._lock = threading.Lock()

    def submit(
        self, kind: str, payload: dict[str, Any], actor: str, max_attempts: int = 3
    ) -> Job:
        with self._lock:
            job = Job(
                id=uuid.uuid4().hex,
                kind=kind,
                payload=dict(payload),
                actor=actor,
                max_attempts=max_attempts,
            )
            self._jobs[job.id] = job
            return job

    def get(self, job_id: str) -> Job:
        with self._lock:
            try:
                return copy.deepcopy(self._jobs[job_id])
            except KeyError:
                raise KeyError(job_id)

    def update(self, job: Job) -> Job:
        with self._lock:
            job.updated_at = time.time()
            self._jobs[job.id] = job
            return job

    def list(self) -> list[Job]:
        with self._lock:
            return copy.deepcopy(list(self._jobs.values()))

    def to_snapshot(self) -> dict:
        with self._lock:
            return {"items": [asdict(job) for job in self._jobs.values()]}

    def load_snapshot(self, data: dict) -> None:
        with self._lock:
            self._jobs = {item["id"]: Job(**item) for item in data.get("items", [])}
