"""Adım 5 API yüzeyleri: sürüm işleme, iş durumu, öneri listeleme."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel

from ..audit.store import AuditStore
from ..auth.roles import Role
from ..catalog.store import CatalogStore
from ..inquiries.store import InquiryStore
from ..jobs.runner import JobRunner
from ..jobs.store import JobStore
from ..matching.store import RequirementStore, SuggestionStore
from .common import find_version
from .deps import require_roles

router = APIRouter()


@router.post("/inquiries/{inquiry_id}/versions/{version_no}/process", status_code=202)
def process_version(
    inquiry_id: str,
    version_no: int,
    request: Request,
    user: dict = Depends(require_roles(Role.ADMIN, Role.SPECIALIST)),
) -> dict[str, str]:
    inquiries: InquiryStore = request.app.state.inquiry_store
    find_version(inquiries, inquiry_id, version_no)
    runner: JobRunner = request.app.state.job_runner
    job = runner.submit(
        "process_version",
        {"inquiry_id": inquiry_id, "version_no": version_no},
        actor=user["subject"],
    )
    return {"job_id": job.id, "status": job.status}


@router.get("/jobs/dead-letter")
def dead_letter_jobs(
    request: Request,
    user: dict = Depends(require_roles(Role.ADMIN)),
) -> dict[str, object]:
    _ = user
    jobs: JobStore = request.app.state.job_store
    failed = [job for job in jobs.list() if job.status == "failed"]
    return {
        "jobs": [
            {
                "job_id": job.id,
                "kind": job.kind,
                "status": job.status,
                "attempts": job.attempts,
                "error": job.error,
            }
            for job in failed
        ]
    }


@router.get("/jobs/{job_id}")
def job_status(
    job_id: str,
    request: Request,
    user: dict = Depends(require_roles(Role.ADMIN, Role.SPECIALIST, Role.VIEWER)),
) -> dict[str, object]:
    _ = user
    jobs: JobStore = request.app.state.job_store
    try:
        job = jobs.get(job_id)
    except KeyError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="iş yok")
    return {
        "job_id": job.id,
        "kind": job.kind,
        "status": job.status,
        "attempts": job.attempts,
        "result": job.result,
        "error": job.error,
    }


@router.get("/inquiries/{inquiry_id}/versions/{version_no}/suggestions")
def list_suggestions(
    inquiry_id: str,
    version_no: int,
    request: Request,
    user: dict = Depends(require_roles(Role.ADMIN, Role.SPECIALIST, Role.VIEWER)),
) -> dict[str, object]:
    _ = user
    inquiries: InquiryStore = request.app.state.inquiry_store
    requirements: RequirementStore = request.app.state.requirement_store
    suggestions: SuggestionStore = request.app.state.suggestion_store
    catalog: CatalogStore = request.app.state.catalog_store
    version = find_version(inquiries, inquiry_id, version_no)
    requirement_payloads = []
    suggestion_payloads = []
    for requirement in requirements.list_for_version(version.id):
        if not str(requirement.quote).strip():
            continue  # Değişmez-1: kaynaksız kayıt gösterilmez.
        requirement_payloads.append(
            {
                "id": requirement.id,
                "product_type": requirement.product_type,
                "features": requirement.features,
                "quantity": requirement.quantity,
                "unit": requirement.unit,
                "source": {"page": requirement.page, "quote": requirement.quote},
            }
        )
        for suggestion in suggestions.list_for_requirement(requirement.id):
            try:
                product = catalog.get(suggestion.product_id)
            except KeyError:
                continue
            suggestion_payloads.append(
                {
                    "id": suggestion.id,
                    "requirement_id": requirement.id,
                    "product": {
                        "code": product.code,
                        "names": list(product.names),
                        "unit": product.unit,
                    },
                    "score": round(suggestion.score, 4),
                    "reasons": list(suggestion.reasons),
                    "status": suggestion.status,
                    "source": {
                        "page": suggestion.page or requirement.page,
                        "quote": suggestion.quote or requirement.quote,
                    },
                }
            )
    return {"requirements": requirement_payloads, "suggestions": suggestion_payloads}


class SuggestionDecision(BaseModel):
    status: str  # onaylandı | reddedildi | düzeltildi
    note: str = ""


class RequirementUpdate(BaseModel):
    product_type: str | None = None
    features: dict | None = None
    quantity: float | None = None
    unit: str | None = None


@router.patch("/suggestions/{suggestion_id}")
def decide_suggestion(
    suggestion_id: str,
    body: SuggestionDecision,
    request: Request,
    user: dict = Depends(require_roles(Role.ADMIN, Role.SPECIALIST)),
) -> dict[str, object]:
    suggestions: SuggestionStore = request.app.state.suggestion_store
    audit: AuditStore = request.app.state.audit_store
    try:
        updated = suggestions.update_status(suggestion_id, body.status)
    except KeyError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="öneri yok")
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    audit.append(
        actor=user["subject"],
        action=f"suggestion.{body.status}",
        target=f"suggestion:{suggestion_id}",
        detail=body.note,
    )
    return {
        "id": updated.id,
        "requirement_id": updated.requirement_id,
        "product_id": updated.product_id,
        "score": updated.score,
        "status": updated.status,
        "source": {"page": updated.page, "quote": updated.quote},
    }


@router.patch("/requirements/{requirement_id}")
def update_requirement(
    requirement_id: str,
    body: RequirementUpdate,
    request: Request,
    user: dict = Depends(require_roles(Role.ADMIN, Role.SPECIALIST)),
) -> dict[str, object]:
    requirements: RequirementStore = request.app.state.requirement_store
    audit: AuditStore = request.app.state.audit_store
    try:
        updated = requirements.update(
            requirement_id,
            product_type=body.product_type,
            features=body.features,
            quantity=body.quantity,
            unit=body.unit,
        )
    except KeyError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="gereksinim yok")
    audit.append(
        actor=user["subject"],
        action="requirement.update",
        target=f"requirement:{requirement_id}",
    )
    return {
        "id": updated.id,
        "product_type": updated.product_type,
        "features": updated.features,
        "quantity": updated.quantity,
        "unit": updated.unit,
        "source": {"page": updated.page, "quote": updated.quote},
    }
