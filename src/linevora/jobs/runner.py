"""Job runner: writes to the queue, a worker executes, errors are retried.

In `inline=True` mode the job runs in the same thread when submitted
(deterministic, for tests); in normal mode a background worker is used.
"""

from __future__ import annotations

import queue
import threading
import time
from typing import Any, Callable

from ..audit.store import AuditStore
from .models import Job
from .store import JobStore

Handler = Callable[[dict[str, Any]], dict[str, Any]]


class JobRunner:
    def __init__(
        self,
        store: JobStore,
        audit: AuditStore,
        handlers: dict[str, Handler],
        max_attempts: int = 3,
        inline: bool = False,
        retry_backoff_seconds: float = 0.0,
    ) -> None:
        self._store = store
        self._audit = audit
        self._handlers = dict(handlers)
        self._max_attempts = max_attempts
        self._inline = inline
        self._backoff = max(0.0, retry_backoff_seconds)
        self._queue: queue.Queue[str | None] = queue.Queue()
        self._worker: threading.Thread | None = None
        self.recover()
        if not inline:
            self._worker = threading.Thread(target=self._serve, daemon=True)
            self._worker.start()
            for job in self._pending:
                self._queue.put(job.id)

    def recover(self) -> list[Job]:
        """Re-queues jobs left half-finished at startup (running→queued)."""
        pending: list[Job] = []
        try:
            jobs = self._store.list()
        except Exception:
            jobs = []
        for job in jobs:
            if job.status == "running":
                job.status = "queued"
                job.error = "recovery: re-queued"
                self._store.update(job)
                pending.append(job)
            elif job.status == "queued":
                pending.append(job)
        self._pending = pending
        return pending

    def dead_letter(self) -> list[Job]:
        """DLQ view: permanently failed jobs."""
        return [job for job in self._store.list() if job.status == "failed"]

    def submit(self, kind: str, payload: dict[str, Any], actor: str) -> Job:
        job = self._store.submit(kind, payload, actor, self._max_attempts)
        self._audit.append(actor=actor, action="job.submit", target=f"job:{job.id}", detail=kind)
        if self._inline:
            self._execute(job.id)
        else:
            self._queue.put(job.id)
        return self._store.get(job.id)

    def shutdown(self, timeout: float = 5.0) -> None:
        if self._worker is not None:
            self._queue.put(None)
            self._worker.join(timeout=timeout)

    def _serve(self) -> None:
        while True:
            job_id = self._queue.get()
            if job_id is None:
                return
            try:
                self._execute(job_id)
            finally:
                self._queue.task_done()

    def _execute(self, job_id: str) -> None:
        job = self._store.get(job_id)
        handler = self._handlers.get(job.kind)
        if handler is None:
            job.status = "failed"
            job.error = f"unknown job kind: {job.kind}"
            self._store.update(job)
            self._audit.append(
                actor="system", action="job.failed", target=f"job:{job.id}", detail=job.error
            )
            return
        job.status = "running"
        self._store.update(job)
        while job.attempts < job.max_attempts:
            job.attempts += 1
            self._store.update(job)
            try:
                result = handler(dict(job.payload))
            except Exception as exc:  # error to be retried
                job.error = f"{type(exc).__name__}: {exc}"
                self._store.update(job)
                if self._backoff and job.attempts < job.max_attempts:
                    time.sleep(self._backoff * (2 ** (job.attempts - 1)))
                continue
            job.status = "done"
            job.result = result
            job.error = None
            self._store.update(job)
            self._audit.append(actor="system", action="job.done", target=f"job:{job.id}")
            return
        job.status = "failed"
        self._store.update(job)
        self._audit.append(
            actor="system",
            action="job.failed",
            target=f"job:{job.id}",
            detail=job.error or "",
        )
