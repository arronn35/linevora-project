"""Adım 2 API yüzeyleri: sağlık, belirteç, kendini görme, denetim okuma."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel

from .. import __version__
from ..audit.store import AuditStore
from ..auth.passwords import verify_password
from ..auth.roles import Role
from ..auth.tokens import issue_token
from ..config import get_settings
from ..jobs.store import JobStore
from ..model.client import FakeModelClient, MeteringClient
from ..observability.metrics import MetricsRegistry
from ..quotes.store import QuoteStore
from .deps import get_current_user, require_roles

router = APIRouter()


class TokenRequest(BaseModel):
    username: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


def get_store(request: Request) -> AuditStore:
    return request.app.state.audit_store


@router.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "version": __version__}


@router.get("/health/ready")
def readiness(request: Request) -> dict[str, object]:
    checks: dict[str, bool] = {}
    try:
        request.app.state.inquiry_store.list()
        checks["stores"] = True
    except Exception:
        checks["stores"] = False
    try:
        request.app.state.job_store.list()
        checks["jobs"] = True
    except Exception:
        checks["jobs"] = False
    ready = all(checks.values())
    if not ready:
        raise HTTPException(status_code=503, detail="hazır değil")
    return {"status": "ready", "checks": checks}


@router.get("/metrics/prometheus")
def prometheus_metrics(
    request: Request, user: dict = Depends(require_roles(Role.ADMIN))
):
    from fastapi.responses import PlainTextResponse

    _ = user
    metrics: MetricsRegistry = request.app.state.metrics
    snap = metrics.snapshot()
    jobs: JobStore = request.app.state.job_store
    by_status: dict[str, int] = {}
    for job in jobs.list():
        by_status[job.status] = by_status.get(job.status, 0) + 1
    lines = [
        "# HELP linevora_http_requests_total HTTP istekleri",
        "# TYPE linevora_http_requests_total counter",
        f"linevora_http_requests_total {snap.get('total', 0)}",
        "# HELP linevora_jobs İş durumları",
        "# TYPE linevora_jobs gauge",
    ]
    for job_status, count in sorted(by_status.items()):
        lines.append(f'linevora_jobs{{status="{job_status}"}} {count}')
    return PlainTextResponse("\n".join(lines) + "\n", media_type="text/plain")


@router.post("/auth/token", response_model=TokenResponse)
def create_token(body: TokenRequest, request: Request) -> TokenResponse:
    settings = get_settings()
    store: AuditStore = request.app.state.audit_store
    record = settings.users.get(body.username)
    ok = record is not None and verify_password(record[0], body.password)
    store.append(
        actor=body.username,
        action="auth.token_issue",
        target=f"user:{body.username}",
        detail="ok" if ok else "hatalı kimlik",
    )
    if not ok or record is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="geçersiz kimlik"
        )
    token = issue_token(settings.secret_key, body.username, [record[1]], settings.token_ttl_seconds, tenant=record[2] if len(record) > 2 else "default")
    return TokenResponse(access_token=token)


@router.post("/auth/revoke")
def revoke_token(
    request: Request, user: dict = Depends(get_current_user)
) -> dict[str, object]:
    revoked = getattr(request.app.state, "revoked_tokens", None)
    if revoked is not None:
        revoked.revoke(user.get("jti", ""))
    store: AuditStore = request.app.state.audit_store
    store.append(actor=user["subject"], action="auth.revoke", target=f"user:{user['subject']}")
    return {"revoked": True}


@router.get("/me")
def me(user: dict = Depends(get_current_user)) -> dict[str, object]:
    return {"username": user["subject"], "roles": user["roles"]}


@router.get("/audit")
def read_audit(
    request: Request,
    user: dict = Depends(require_roles(Role.ADMIN)),
    limit: int = 200,
    offset: int = 0,
) -> dict[str, object]:
    store: AuditStore = request.app.state.audit_store
    store.append(actor=user["subject"], action="audit.read", target="audit")
    entries = store.list()
    page = entries[max(0, offset) : max(0, offset) + max(1, min(limit, 1000))]
    return {"total": len(entries), "limit": limit, "offset": offset, "entries": [entry.to_dict() for entry in page]}


@router.get("/metrics")
def read_metrics(
    request: Request, user: dict = Depends(require_roles(Role.ADMIN))
) -> dict[str, object]:
    _ = user
    metrics: MetricsRegistry = request.app.state.metrics
    jobs: JobStore = request.app.state.job_store
    quotes: QuoteStore = request.app.state.quote_store
    jobs_by_status: dict[str, int] = {}
    for job in jobs.list():
        jobs_by_status[job.status] = jobs_by_status.get(job.status, 0) + 1
    quotes_by_status: dict[str, int] = {}
    approval_durations: list[float] = []
    for quote in quotes.list():
        quotes_by_status[quote.status] = quotes_by_status.get(quote.status, 0) + 1
        if quote.approved_at is not None:
            approval_durations.append(quote.approved_at - quote.created_at)
    client = request.app.state.model_client
    calls = client.calls if isinstance(client, MeteringClient) else []
    return {
        "http": metrics.snapshot(),
        "jobs": {"by_status": jobs_by_status},
        "model": {
            "calls": len(calls),
            "ok": sum(1 for call in calls if call.ok),
            "failed": sum(1 for call in calls if not call.ok),
        },
        "quotes": {
            "by_status": quotes_by_status,
            "exported": quotes_by_status.get("dışa aktarıldı", 0),
            "avg_approval_seconds": (
                round(sum(approval_durations) / len(approval_durations), 1)
                if approval_durations
                else None
            ),
        },
    }


@router.get("/metrics/model-usage")
def read_model_usage(
    request: Request, user: dict = Depends(require_roles(Role.ADMIN))
) -> dict[str, object]:
    _ = user
    client = request.app.state.model_client
    calls = client.calls if isinstance(client, MeteringClient) else []
    return {
        "calls": len(calls),
        "ok": sum(1 for call in calls if call.ok),
        "failed": sum(1 for call in calls if not call.ok),
        "prompt_chars": sum(call.prompt_chars for call in calls),
        "response_chars": sum(call.response_chars for call in calls),
        "estimated_tokens": sum(call.estimated_tokens for call in calls),
        "avg_latency_ms": (
            round(sum(call.latency_ms for call in calls) / len(calls), 1)
            if calls
            else None
        ),
        "by_model": sorted({call.model for call in calls}),
    }


@router.post("/admin/snapshot")
def save_snapshot(
    request: Request, user: dict = Depends(require_roles(Role.ADMIN))
) -> dict[str, object]:
    manager = request.app.state.snapshot
    if manager is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="snapshot yapılandırılmamış"
        )
    store: AuditStore = request.app.state.audit_store
    path = manager.save()
    store.append(actor=user["subject"], action="admin.snapshot", target="snapshot")
    return {"saved": True, "path": path}


class DemoModelRequest(BaseModel):
    scripts: dict[str, str]


@router.post("/admin/demo-model")
def set_demo_model(
    body: DemoModelRequest, request: Request, user: dict = Depends(require_roles(Role.ADMIN))
) -> dict[str, object]:
    if get_settings().env != "dev":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="yalnızca dev"
        )
    request.app.state.model_client = FakeModelClient(body.scripts)
    store: AuditStore = request.app.state.audit_store
    store.append(actor=user["subject"], action="admin.demo_model", target="demo-model")
    return {"scripted": len(body.scripts)}
