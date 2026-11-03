"""Report API surfaces: gaps, version diff, alternatives."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel

from ..audit.store import AuditStore

from ..auth.roles import Role
from ..catalog.store import CatalogStore
from ..inquiries.store import InquiryStore
from ..matching.store import RequirementStore
from ..reports.diff import diff_requirements
from ..reports.store import AlternativeStore, GapStore
from .common import find_version
from .deps import require_roles

router = APIRouter()

_VIEWERS = (Role.ADMIN, Role.SPECIALIST, Role.VIEWER)


@router.get("/inquiries/{inquiry_id}/versions/{version_no}/gaps")
def list_gaps(
    inquiry_id: str,
    version_no: int,
    request: Request,
    user: dict = Depends(require_roles(*_VIEWERS)),
) -> dict[str, object]:
    _ = user
    inquiries: InquiryStore = request.app.state.inquiry_store
    gaps: GapStore = request.app.state.gap_store
    version = find_version(inquiries, inquiry_id, version_no)
    return {
        "gaps": [
            {
                "id": gap.id,
                "requirement_id": gap.requirement_id,
                "field": gap.field,
                "question": gap.question,
                "severity": gap.severity,
                "status": gap.status,
                "answer": gap.answer,
            }
            for gap in gaps.list_for_version(version.id)
        ]
    }


@router.get("/inquiries/{inquiry_id}/versions/{from_no}/diff/{to_no}")
def version_diff(
    inquiry_id: str,
    from_no: int,
    to_no: int,
    request: Request,
    user: dict = Depends(require_roles(*_VIEWERS)),
) -> dict[str, object]:
    _ = user
    inquiries: InquiryStore = request.app.state.inquiry_store
    requirements: RequirementStore = request.app.state.requirement_store
    old = find_version(inquiries, inquiry_id, from_no)
    new = find_version(inquiries, inquiry_id, to_no)
    changes = diff_requirements(
        requirements.list_for_version(old.id), requirements.list_for_version(new.id)
    )
    return {"from_version": from_no, "to_version": to_no, "changes": changes}


@router.get("/inquiries/{inquiry_id}/versions/{version_no}/alternatives")
def list_alternatives(
    inquiry_id: str,
    version_no: int,
    request: Request,
    user: dict = Depends(require_roles(*_VIEWERS)),
) -> dict[str, object]:
    _ = user
    inquiries: InquiryStore = request.app.state.inquiry_store
    requirements: RequirementStore = request.app.state.requirement_store
    alternatives: AlternativeStore = request.app.state.alternative_store
    catalog: CatalogStore = request.app.state.catalog_store
    version = find_version(inquiries, inquiry_id, version_no)
    payloads = []
    for requirement in requirements.list_for_version(version.id):
        for alternative in alternatives.list_for_requirement(requirement.id):
            try:
                product = catalog.get(alternative.product_id)
            except KeyError:
                continue
            payloads.append(
                {
                    "id": alternative.id,
                    "requirement_id": requirement.id,
                    "product": {
                        "code": product.code,
                        "names": list(product.names),
                        "unit": product.unit,
                    },
                    "score": round(alternative.score, 4),
                    "comparison": [
                        {
                            "criterion": row.criterion,
                            "wanted": row.wanted,
                            "offered": row.offered,
                            "match": row.match,
                        }
                        for row in alternative.comparison
                    ],
                    "reasons": list(alternative.reasons),
                    "status": alternative.status,
                }
            )
    return {"alternatives": payloads}


class GapAnswer(BaseModel):
    status: str = "answered"  # answered | waived
    answer: str = ""


class AlternativeDecision(BaseModel):
    status: str  # approved | rejected


@router.post("/gaps/{gap_id}/answer")
def answer_gap(
    gap_id: str,
    body: GapAnswer,
    request: Request,
    user: dict = Depends(require_roles(Role.ADMIN, Role.SPECIALIST)),
) -> dict[str, object]:
    gaps: GapStore = request.app.state.gap_store
    audit: AuditStore = request.app.state.audit_store
    try:
        updated = gaps.update_status(gap_id, body.status, body.answer)
    except KeyError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="gap not found")
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    audit.append(actor=user["subject"], action="gap.answer", target=f"gap:{gap_id}", detail=body.answer)
    return {"id": updated.id, "status": updated.status, "answer": updated.answer, "field": updated.field}


@router.patch("/alternatives/{alternative_id}")
def decide_alternative(
    alternative_id: str,
    body: AlternativeDecision,
    request: Request,
    user: dict = Depends(require_roles(Role.ADMIN, Role.SPECIALIST)),
) -> dict[str, object]:
    alternatives: AlternativeStore = request.app.state.alternative_store
    audit: AuditStore = request.app.state.audit_store
    try:
        updated = alternatives.update_status(alternative_id, body.status)
    except KeyError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="alternative not found")
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    audit.append(actor=user["subject"], action=f"alternative.{body.status}", target=f"alternative:{alternative_id}")
    return {
        "id": updated.id,
        "requirement_id": updated.requirement_id,
        "product_id": updated.product_id,
        "status": updated.status,
    }
