"""Adım 7 API yüzeyleri: fiyat/şart sürümleri, teklif ve onay akışı."""

from __future__ import annotations

import time
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel

from ..auth.roles import Role
from ..audit.store import AuditStore
from ..catalog.store import CatalogStore
from ..inquiries.store import InquiryStore
from ..matching.store import RequirementStore
from ..quotes.models import Quote
from ..quotes.store import PriceStore, QuoteLineStore, QuoteStore, TermsStore
from .common import find_version
from .deps import require_roles

router = APIRouter()

_VIEWERS = (Role.ADMIN, Role.SPECIALIST, Role.VIEWER)
_EDITORS = (Role.ADMIN, Role.SPECIALIST)


class PriceRequest(BaseModel):
    product_id: str
    price: float
    currency: str


class TermsRequest(BaseModel):
    name: str
    text: str


class LineItem(BaseModel):
    requirement_id: str
    product_id: str
    quantity: float | None = None


class LinesRequest(BaseModel):
    lines: list[LineItem]


def _quote_or_404(quotes: QuoteStore, quote_id: str) -> Quote:
    try:
        return quotes.get(quote_id)
    except KeyError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="teklif yok")


def _version_no(inquiries: InquiryStore, inquiry_id: str, version_id: str) -> int | None:
    try:
        versions = inquiries.list_versions(inquiry_id)
    except KeyError:
        return None
    for version in versions:
        if version.id == version_id:
            return version.version_no
    return None


def _resolve_lines(requirements, catalog, prices, version, raw_lines):
    if not raw_lines:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="en az bir kalem gerekli"
        )
    known = {item.id: item for item in requirements.list_for_version(version.id)}
    drafts = []
    for item in raw_lines:
        requirement = known.get(item.requirement_id)
        if requirement is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="gereksinim bu sürümde yok",
            )
        try:
            product = catalog.get(item.product_id)
        except KeyError:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="ürün yok"
            )
        price = prices.effective_for_product(product.id)
        if price is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"{product.code} için yürürlükte fiyat yok",
            )
        quantity = item.quantity if item.quantity is not None else requirement.quantity
        if quantity is None or quantity <= 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="miktar geçersiz"
            )
        drafts.append(
            {
                "requirement_id": requirement.id,
                "product": product,
                "quantity": quantity,
                "unit": requirement.unit or product.unit,
                "price": price,
                "amount": float(
                    (Decimal(str(quantity)) * Decimal(str(price.price))).quantize(
                        Decimal("0.01")
                    )
                ),
            }
        )
    return drafts


def _detail(request: Request, quote: Quote) -> dict[str, object]:
    inquiries: InquiryStore = request.app.state.inquiry_store
    catalog: CatalogStore = request.app.state.catalog_store
    lines: QuoteLineStore = request.app.state.line_store
    inquiry = inquiries.get_inquiry(quote.inquiry_id)
    totals: dict[str, float] = {}
    line_payloads = []
    for line in lines.list_for_quote(quote.id):
        product = catalog.get(line.product_id)
        totals[line.currency] = float(Decimal(str(totals.get(line.currency, 0.0))) + Decimal(str(line.amount)))
        line_payloads.append(
            {
                "id": line.id,
                "requirement_id": line.requirement_id,
                "product": {
                    "code": product.code,
                    "names": list(product.names),
                    "unit": product.unit,
                },
                "quantity": line.quantity,
                "unit": line.unit,
                "unit_price": line.unit_price,
                "currency": line.currency,
                "amount": line.amount,
                "price_version_id": line.price_version_id,
            }
        )
    return {
        "id": quote.id,
        "inquiry_id": quote.inquiry_id,
        "customer": inquiry.customer,
        "version_no": _version_no(inquiries, quote.inquiry_id, quote.version_id),
        "status": quote.status,
        "terms_version_id": quote.terms_version_id,
        "lines": line_payloads,
        "totals": [
            {"currency": currency, "amount": amount}
            for currency, amount in sorted(totals.items())
        ],
        "created_by": quote.created_by,
        "approved_by": quote.approved_by,
    }


@router.post("/prices", status_code=status.HTTP_201_CREATED)
def create_price(
    body: PriceRequest,
    request: Request,
    user: dict = Depends(require_roles(Role.ADMIN)),
) -> dict[str, object]:
    catalog: CatalogStore = request.app.state.catalog_store
    prices: PriceStore = request.app.state.price_store
    audit: AuditStore = request.app.state.audit_store
    try:
        catalog.get(body.product_id)
    except KeyError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="ürün yok")
    if body.price <= 0 or not body.currency.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="fiyat geçersiz"
        )
    version = prices.create(
        product_id=body.product_id, price=body.price, currency=body.currency.strip()
    )
    audit.append(actor=user["subject"], action="price.create", target=f"price:{version.id}")
    return {"id": version.id, "status": version.status}


@router.post("/prices/{version_id}/activate")
def activate_price(
    version_id: str,
    request: Request,
    user: dict = Depends(require_roles(Role.ADMIN)),
) -> dict[str, object]:
    prices: PriceStore = request.app.state.price_store
    audit: AuditStore = request.app.state.audit_store
    try:
        version = prices.activate(version_id)
    except KeyError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="fiyat sürümü yok"
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    audit.append(
        actor=user["subject"], action="price.activate", target=f"price:{version.id}"
    )
    return {"id": version.id, "status": version.status}


@router.get("/prices")
def list_prices(
    request: Request,
    product_id: str | None = None,
    user: dict = Depends(require_roles(*_VIEWERS)),
) -> dict[str, object]:
    _ = user
    prices: PriceStore = request.app.state.price_store
    if product_id is not None:
        items = prices.list_for_product(product_id)
    else:
        items = []
    return {
        "prices": [
            {
                "id": item.id,
                "product_id": item.product_id,
                "price": item.price,
                "currency": item.currency,
                "status": item.status,
            }
            for item in items
        ]
    }


@router.post("/terms", status_code=status.HTTP_201_CREATED)
def create_terms(
    body: TermsRequest,
    request: Request,
    user: dict = Depends(require_roles(Role.ADMIN)),
) -> dict[str, object]:
    terms: TermsStore = request.app.state.terms_store
    audit: AuditStore = request.app.state.audit_store
    version = terms.create(name=body.name, text=body.text)
    audit.append(actor=user["subject"], action="terms.create", target=f"terms:{version.id}")
    return {"id": version.id, "status": version.status}


@router.post("/terms/{version_id}/activate")
def activate_terms(
    version_id: str,
    request: Request,
    user: dict = Depends(require_roles(Role.ADMIN)),
) -> dict[str, object]:
    terms: TermsStore = request.app.state.terms_store
    audit: AuditStore = request.app.state.audit_store
    try:
        version = terms.activate(version_id)
    except KeyError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="şart sürümü yok"
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    audit.append(
        actor=user["subject"], action="terms.activate", target=f"terms:{version.id}"
    )
    return {"id": version.id, "status": version.status}


@router.get("/terms")
def list_terms(
    request: Request,
    user: dict = Depends(require_roles(*_VIEWERS)),
) -> dict[str, object]:
    _ = user
    terms: TermsStore = request.app.state.terms_store
    return {
        "terms": [
            {
                "id": item.id,
                "name": item.name,
                "text": item.text,
                "status": item.status,
            }
            for item in terms.list()
        ]
    }


@router.post(
    "/inquiries/{inquiry_id}/versions/{version_no}/quotes",
    status_code=status.HTTP_201_CREATED,
)
def build_quote(
    inquiry_id: str,
    version_no: int,
    body: LinesRequest,
    request: Request,
    user: dict = Depends(require_roles(*_EDITORS)),
) -> dict[str, object]:
    inquiries: InquiryStore = request.app.state.inquiry_store
    requirements: RequirementStore = request.app.state.requirement_store
    catalog: CatalogStore = request.app.state.catalog_store
    prices: PriceStore = request.app.state.price_store
    terms: TermsStore = request.app.state.terms_store
    quotes: QuoteStore = request.app.state.quote_store
    lines: QuoteLineStore = request.app.state.line_store
    audit: AuditStore = request.app.state.audit_store
    version = find_version(inquiries, inquiry_id, version_no)
    gaps = request.app.state.gap_store
    open_mandatory = [
        gap
        for gap in gaps.list_for_version(version.id)
        if gap.severity == "zorunlu" and gap.status == "açık"
    ]
    if open_mandatory:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"{len(open_mandatory)} zorunlu eksik bilgi açıkken teklif kurulamaz",
        )
    drafts = _resolve_lines(requirements, catalog, prices, version, body.lines)
    effective_terms = terms.effective()
    if effective_terms is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="yürürlükte şart yok"
        )
    quote = quotes.create(
        inquiry_id=inquiry_id,
        version_id=version.id,
        terms_version_id=effective_terms.id,
        created_by=user["subject"],
    )
    for draft in drafts:
        lines.add(
            quote_id=quote.id,
            requirement_id=draft["requirement_id"],
            product_id=draft["product"].id,
            quantity=draft["quantity"],
            unit=draft["unit"],
            price_version_id=draft["price"].id,
            unit_price=draft["price"].price,
            currency=draft["price"].currency,
            amount=draft["amount"],
        )
    audit.append(actor=user["subject"], action="quote.create", target=f"quote:{quote.id}")
    return _detail(request, quote)


@router.put("/quotes/{quote_id}/lines")
def edit_lines(
    quote_id: str,
    body: LinesRequest,
    request: Request,
    user: dict = Depends(require_roles(*_EDITORS)),
) -> dict[str, object]:
    inquiries: InquiryStore = request.app.state.inquiry_store
    requirements: RequirementStore = request.app.state.requirement_store
    catalog: CatalogStore = request.app.state.catalog_store
    prices: PriceStore = request.app.state.price_store
    quotes: QuoteStore = request.app.state.quote_store
    lines: QuoteLineStore = request.app.state.line_store
    audit: AuditStore = request.app.state.audit_store
    quote = _quote_or_404(quotes, quote_id)
    if quote.status != "taslak":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="yalnızca taslak düzenlenir",
        )
    versions = inquiries.list_versions(quote.inquiry_id)
    version = next((v for v in versions if v.id == quote.version_id), None)
    if version is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="sürüm yok")
    drafts = _resolve_lines(requirements, catalog, prices, version, body.lines)
    lines.delete_for_quote(quote.id)
    for draft in drafts:
        lines.add(
            quote_id=quote.id,
            requirement_id=draft["requirement_id"],
            product_id=draft["product"].id,
            quantity=draft["quantity"],
            unit=draft["unit"],
            price_version_id=draft["price"].id,
            unit_price=draft["price"].price,
            currency=draft["price"].currency,
            amount=draft["amount"],
        )
    quotes.update(quote)
    audit.append(actor=user["subject"], action="quote.lines_edit", target=f"quote:{quote.id}")
    return _detail(request, quote)


@router.get("/quotes/{quote_id}")
def read_quote(
    quote_id: str,
    request: Request,
    user: dict = Depends(require_roles(*_VIEWERS)),
) -> dict[str, object]:
    _ = user
    quotes: QuoteStore = request.app.state.quote_store
    return _detail(request, _quote_or_404(quotes, quote_id))


@router.get("/inquiries/{inquiry_id}/quotes")
def list_quotes(
    inquiry_id: str,
    request: Request,
    user: dict = Depends(require_roles(*_VIEWERS)),
) -> dict[str, object]:
    _ = user
    inquiries: InquiryStore = request.app.state.inquiry_store
    quotes: QuoteStore = request.app.state.quote_store
    try:
        inquiries.get_inquiry(inquiry_id)
    except KeyError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="talep yok")
    return {
        "quotes": [
            {
                "id": quote.id,
                "status": quote.status,
                "version_no": _version_no(inquiries, inquiry_id, quote.version_id),
                "created_by": quote.created_by,
                "approved_by": quote.approved_by,
            }
            for quote in quotes.list_for_inquiry(inquiry_id)
        ]
    }


@router.post("/quotes/{quote_id}/submit")
def submit_quote(
    quote_id: str,
    request: Request,
    user: dict = Depends(require_roles(*_EDITORS)),
) -> dict[str, object]:
    quotes: QuoteStore = request.app.state.quote_store
    audit: AuditStore = request.app.state.audit_store
    quote = _quote_or_404(quotes, quote_id)
    if quote.status != "taslak":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="yalnızca taslak sunulur"
        )
    quote.status = "incelemede"
    quotes.update(quote)
    audit.append(actor=user["subject"], action="quote.submit", target=f"quote:{quote.id}")
    return _detail(request, quote)


@router.post("/quotes/{quote_id}/return")
def return_quote(
    quote_id: str,
    request: Request,
    user: dict = Depends(require_roles(Role.ADMIN)),
) -> dict[str, object]:
    quotes: QuoteStore = request.app.state.quote_store
    audit: AuditStore = request.app.state.audit_store
    quote = _quote_or_404(quotes, quote_id)
    if quote.status != "incelemede":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="yalnızca incelemedeki iade edilir"
        )
    quote.status = "taslak"
    quotes.update(quote)
    audit.append(actor=user["subject"], action="quote.return", target=f"quote:{quote.id}")
    return _detail(request, quote)


@router.post("/quotes/{quote_id}/approve")
def approve_quote(
    quote_id: str,
    request: Request,
    user: dict = Depends(require_roles(Role.ADMIN)),
) -> dict[str, object]:
    quotes: QuoteStore = request.app.state.quote_store
    audit: AuditStore = request.app.state.audit_store
    quote = _quote_or_404(quotes, quote_id)
    if quote.status != "incelemede":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="yalnızca incelemedeki onaylanır"
        )
    quote.status = "onaylandı"
    quote.approved_by = user["subject"]
    quote.approved_at = time.time()
    quotes.update(quote)
    audit.append(
        actor=user["subject"], action="quote.approve", target=f"quote:{quote.id}"
    )
    return _detail(request, quote)


def _export_document(
    quote_id: str, request: Request, user: dict, *, mark_exported: bool = True
) -> dict[str, object]:
    inquiries: InquiryStore = request.app.state.inquiry_store
    catalog: CatalogStore = request.app.state.catalog_store
    prices: PriceStore = request.app.state.price_store
    terms: TermsStore = request.app.state.terms_store
    quotes: QuoteStore = request.app.state.quote_store
    lines: QuoteLineStore = request.app.state.line_store
    audit: AuditStore = request.app.state.audit_store
    quote = _quote_or_404(quotes, quote_id)
    if quote.status not in ("onaylandı", "dışa aktarıldı"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="onaylanmadan dışa aktarılmaz",
        )
    try:
        terms_version = terms.get(quote.terms_version_id)
    except KeyError:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="sabitlenen şart sürümü bulunamadı",
        )
    inquiry = inquiries.get_inquiry(quote.inquiry_id)
    totals: dict[str, float] = {}
    line_payloads = []
    for line in lines.list_for_quote(quote.id):
        product = catalog.get(line.product_id)
        totals[line.currency] = float(Decimal(str(totals.get(line.currency, 0.0))) + Decimal(str(line.amount)))
        line_payloads.append(
            {
                "product_code": product.code,
                "product_names": list(product.names),
                "quantity": line.quantity,
                "unit": line.unit,
                "unit_price": line.unit_price,
                "currency": line.currency,
                "amount": line.amount,
                "price_version_id": line.price_version_id,
            }
        )
    if mark_exported:
        quote.status = "dışa aktarıldı"
        quotes.update(quote)
        audit.append(actor=user["subject"], action="quote.export", target=f"quote:{quote.id}")
    else:
        audit.append(actor=user["subject"], action="quote.preview", target=f"quote:{quote.id}")
    return {
        "quote_id": quote.id,
        "status": quote.status,
        "customer": inquiry.customer,
        "title": inquiry.title,
        "version_no": _version_no(inquiries, quote.inquiry_id, quote.version_id),
        "lines": line_payloads,
        "totals": [
            {"currency": currency, "amount": amount}
            for currency, amount in sorted(totals.items())
        ],
        "terms": {
            "name": terms_version.name,
            "text": terms_version.text,
            "terms_version_id": terms_version.id,
        },
        "prepared_by": quote.created_by,
        "approved_by": quote.approved_by,
    }


@router.get("/quotes/{quote_id}/preview")
def preview_quote(
    quote_id: str,
    request: Request,
    user: dict = Depends(require_roles(*_EDITORS)),
) -> dict[str, object]:
    return _export_document(quote_id, request, user, mark_exported=False)


@router.get("/quotes/{quote_id}/export")
def export_quote(
    quote_id: str,
    request: Request,
    user: dict = Depends(require_roles(*_EDITORS)),
) -> dict[str, object]:
    return _export_document(quote_id, request, user)


@router.get("/quotes/{quote_id}/export.pdf")
def export_quote_pdf(
    quote_id: str,
    request: Request,
    user: dict = Depends(require_roles(*_EDITORS)),
):
    from fastapi.responses import Response

    from ..quotes.pdf import render_quote_pdf

    document = _export_document(quote_id, request, user)
    return Response(
        content=render_quote_pdf(document),
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="teklif-{quote_id}.pdf"'
        },
    )
