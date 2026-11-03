"""Inquiry API surfaces: opening inquiries, uploading and listing versions."""

from __future__ import annotations

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile, status
from pydantic import BaseModel

from ..audit.store import AuditStore
from ..auth.roles import Role
from ..files.store import BlobStore
from ..ingest.extract import UnsupportedFormatError, extract_text
from ..inquiries.store import InquiryStore
from .deps import require_roles

router = APIRouter()

MAX_UPLOAD_BYTES = 25 * 1024 * 1024


class InquiryRequest(BaseModel):
    customer: str
    title: str


class PageModel(BaseModel):
    number: int
    text: str


class VersionModel(BaseModel):
    id: str
    inquiry_id: str
    version_no: int
    file_id: str
    filename: str
    pages: list[PageModel]


def _version_payload(version) -> dict[str, object]:
    return {
        "id": version.id,
        "inquiry_id": version.inquiry_id,
        "version_no": version.version_no,
        "file_id": version.file_id,
        "filename": version.filename,
        "pages": [{"number": page.number, "text": page.text} for page in version.pages],
    }


@router.post("/inquiries", status_code=status.HTTP_201_CREATED)
def create_inquiry(
    body: InquiryRequest,
    request: Request,
    user: dict = Depends(require_roles(Role.ADMIN, Role.SPECIALIST)),
) -> dict[str, object]:
    inquiries: InquiryStore = request.app.state.inquiry_store
    audit: AuditStore = request.app.state.audit_store
    inquiry = inquiries.create_inquiry(
        customer=body.customer,
        title=body.title,
        created_by=user["subject"],
        tenant_id=user.get("tenant", "default"),
    )
    audit.append(
        actor=user["subject"], action="inquiry.create", target=f"inquiry:{inquiry.id}"
    )
    return {
        "id": inquiry.id,
        "customer": inquiry.customer,
        "title": inquiry.title,
        "status": inquiry.status,
        "created_by": inquiry.created_by,
        "tenant_id": getattr(inquiry, "tenant_id", "default"),
    }



@router.post("/inquiries/{inquiry_id}/versions", status_code=status.HTTP_201_CREATED)
async def add_version(
    inquiry_id: str,
    request: Request,
    file: UploadFile = File(...),
    user: dict = Depends(require_roles(Role.ADMIN, Role.SPECIALIST)),
) -> dict[str, object]:
    inquiries: InquiryStore = request.app.state.inquiry_store
    blobs: BlobStore = request.app.state.blob_store
    audit: AuditStore = request.app.state.audit_store
    chunks: list[bytes] = []
    total = 0
    while chunk := await file.read(1024 * 1024):
        total += len(chunk)
        if total > MAX_UPLOAD_BYTES:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail="file too large (at most 25 MB)",
            )
        chunks.append(chunk)
    content = b"".join(chunks)
    filename = file.filename or "file"
    try:
        document = extract_text(filename, content)
    except UnsupportedFormatError as exc:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, detail=str(exc)
        )
    try:
        inquiries.get_inquiry(inquiry_id)
    except KeyError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="inquiry not found")
    stored = blobs.put(filename, content)
    version = inquiries.add_version(inquiry_id, stored, document.pages)
    audit.append(
        actor=user["subject"],
        action="inquiry.version_add",
        target=f"inquiry:{inquiry_id}/v{version.version_no}",
    )
    return _version_payload(version)


@router.get("/inquiries/{inquiry_id}/versions")
def list_versions(
    inquiry_id: str,
    request: Request,
    user: dict = Depends(
        require_roles(Role.ADMIN, Role.SPECIALIST, Role.VIEWER)
    ),
) -> dict[str, object]:
    inquiries: InquiryStore = request.app.state.inquiry_store
    try:
        _inquiry = inquiries.get_inquiry(inquiry_id)
        if getattr(_inquiry, "tenant_id", "default") != user.get("tenant", "default"):
            raise KeyError(inquiry_id)
        versions = inquiries.list_versions(inquiry_id)
    except KeyError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="inquiry not found")
    return {"versions": [_version_payload(version) for version in versions]}


@router.get("/inquiries")
def list_inquiries(
    request: Request,
    user: dict = Depends(require_roles(Role.ADMIN, Role.SPECIALIST, Role.VIEWER)),
    limit: int = 100,
    offset: int = 0,
) -> dict[str, object]:
    inquiries: InquiryStore = request.app.state.inquiry_store
    all_items = inquiries.list()
    page = all_items[max(0, offset) : max(0, offset) + max(1, min(limit, 500))]
    return {
        "total": len(all_items),
        "limit": limit,
        "offset": offset,
        "inquiries": [
            {
                "id": item.id,
                "customer": item.customer,
                "title": item.title,
                "status": item.status,
                "created_by": item.created_by,
            }
            for item in page
        ]
    }


@router.delete("/inquiries/{inquiry_id}")
def delete_inquiry(
    inquiry_id: str,
    request: Request,
    user: dict = Depends(require_roles(Role.ADMIN)),
) -> dict[str, object]:
    """Erasure: the inquiry and derived records are deleted; a trace is left in the audit log."""
    inquiries: InquiryStore = request.app.state.inquiry_store
    audit: AuditStore = request.app.state.audit_store
    try:
        inquiry = inquiries.get_inquiry(inquiry_id)
        if getattr(inquiry, "tenant_id", "default") != user.get("tenant", "default"):
            raise KeyError(inquiry_id)
        versions = inquiries.list_versions(inquiry_id)
    except KeyError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="inquiry not found")
    requirements = request.app.state.requirement_store
    for version in versions:
        removed = requirements.delete_for_version(version.id)
        request.app.state.suggestion_store.delete_for_requirements(removed)
        request.app.state.alternative_store.delete_for_requirements(removed)
        request.app.state.gap_store.delete_for_version(version.id)
    inquiries.delete_inquiry(inquiry_id)
    audit.append(actor=user["subject"], action="inquiry.erasure", target=f"inquiry:{inquiry_id}", detail="erasure")
    return {"deleted": True, "id": inquiry_id}
