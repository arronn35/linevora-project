"""İş koşucu: yeniden deneme, terminal durumlar, denetim."""

import time

from linevora.audit.store import InMemoryAuditStore
from linevora.jobs.runner import JobRunner
from linevora.jobs.store import InMemoryJobStore


def _runner(handlers, **kwargs):
    audit = InMemoryAuditStore()
    store = InMemoryJobStore()
    kwargs.setdefault("inline", True)
    runner = JobRunner(store=store, audit=audit, handlers=handlers, **kwargs)
    return runner, store, audit


def test_inline_success():
    runner, store, audit = _runner({"topla": lambda p: {"sonuc": p["a"] + p["b"]}})
    job = runner.submit("topla", {"a": 1, "b": 2}, actor="uzman")
    assert job.status == "done"
    assert job.result == {"sonuc": 3}
    assert job.attempts == 1
    assert [entry.action for entry in audit.list()] == ["job.submit", "job.done"]


def test_retry_then_success():
    calls = []

    def flaky(payload):
        calls.append(1)
        if len(calls) < 2:
            raise RuntimeError("geçici")
        return {"ok": True}

    runner, store, _ = _runner({"dalgali": flaky})
    job = runner.submit("dalgali", {}, actor="u")
    assert job.status == "done"
    assert job.attempts == 2


def test_exhausted_attempts_mark_failed():
    def broken(payload):
        raise RuntimeError("sürekli")

    runner, store, audit = _runner({"bozuk": broken}, max_attempts=2)
    job = runner.submit("bozuk", {}, actor="u")
    assert job.status == "failed"
    assert job.attempts == 2
    assert "sürekli" in (job.error or "")
    assert [entry.action for entry in audit.list()][-1] == "job.failed"


def test_unknown_kind_fails_without_retry():
    runner, store, _ = _runner({})
    job = runner.submit("yok", {}, actor="u")
    assert job.status == "failed"
    assert job.attempts == 0


def test_threaded_smoke():
    runner, store, _ = _runner({"yanki": lambda p: {"ok": True}}, inline=False)
    try:
        job = runner.submit("yanki", {}, actor="u")
        deadline = time.time() + 5
        while store.get(job.id).status in ("queued", "running") and time.time() < deadline:
            time.sleep(0.02)
        assert store.get(job.id).status == "done"
    finally:
        runner.shutdown()
