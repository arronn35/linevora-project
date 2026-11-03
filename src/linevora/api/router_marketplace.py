"""Marketplace API surfaces: listings, offers, comparison, messages, notifications.

A parallel module, independent of the existing inquiry/quote flow. Every
signed-in user (no role restriction) can open both a buying (demand) and
a selling (supply) listing. Publishing/sending is done with confirmed POST
actions; an unspecified price, technical detail or payment term is never
invented (``None`` plus missing-field questions). Competing offers never
see each other; the comparison never returns a "best" field.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel

from ..audit.store import AuditStore
from ..marketplace.document import render_listing_document, render_offer_document
from ..marketplace.models import OfferLine, to_decimal
from ..marketplace.parser import parse_listing, parse_offer
from ..marketplace.store import select_offer
from .deps import get_current_user

router = APIRouter()


# ------------------------------------------------------------------ models

class ParseListingRequest(BaseModel):
    kind: str = "demand"
    text: str = ""
    raw_text: str | None = None


class CreateListingRequest(BaseModel):
    kind: str = "demand"
    raw_text: str | None = None
    text: str | None = None
    title: str | None = None
    product: str | None = None
    quantity: Any = None
    unit: str | None = None
    delivery_place: str | None = None
    delivery_days: int | None = None
    category: str | None = None
    features: dict[str, Any] | None = None
    missing_fields: list[str] | None = None
    needs_clarification: bool | None = None


class PatchListingRequest(BaseModel):
    raw_text: str | None = None
    text: str | None = None
    title: str | None = None
    product: str | None = None
    quantity: Any = None
    unit: str | None = None
    delivery_place: str | None = None
    delivery_days: int | None = None
    category: str | None = None
    features: dict[str, Any] | None = None
    missing_fields: list[str] | None = None
    needs_clarification: bool | None = None


class ConfirmRequest(BaseModel):
    confirmed: bool | None = None


class ParseOfferRequest(BaseModel):
    text: str = ""
    raw_text: str | None = None


class OfferLineIn(BaseModel):
    quantity: Any = None
    unit: str | None = None
    unit_price: Any = None
    currency: str | None = None
    product: str | None = None
    features: dict[str, Any] | None = None


class CreateOfferRequest(BaseModel):
    text: str | None = None
    raw_text: str | None = None
    lines: list[OfferLineIn] | None = None
    quantity: Any = None
    unit: str | None = None
    unit_price: Any = None
    currency: str | None = None
    tax_included: bool | None = None
    shipping_included: bool | None = None
    shipping_cost: Any = None
    delivery_days: int | None = None
    payment_terms: str | None = None
    note: str | None = None
    catalog_price: Any = None
    catalog_currency: str | None = None
    catalog_product_id: str | None = None
    confirmed: bool | None = None


class ReviseOfferRequest(BaseModel):
    text: str | None = None
    raw_text: str | None = None
    lines: list[OfferLineIn] | None = None
    quantity: Any = None
    unit: str | None = None
    unit_price: Any = None
    currency: str | None = None
    tax_included: bool | None = None
    shipping_included: bool | None = None
    shipping_cost: Any = None
    delivery_days: int | None = None
    payment_terms: str | None = None
    note: str | None = None
    confirmed: bool | None = None


class RequestRevisionRequest(BaseModel):
    note: str = ""


class MessageRequest(BaseModel):
    body: str = ""


# ------------------------------------------------------------------ helpers

def _tenant(user: dict) -> str:
    return str(user.get("tenant") or "default")


def _subject(user: dict) -> str:
    return str(user.get("subject") or "")


def _stores(request: Request):
    s = request.app.state
    return (
        s.marketplace_listing_store,
        s.marketplace_offer_store,
        s.marketplace_agreement_store,
        s.marketplace_message_store,
        s.marketplace_notification_store,
    )


def _audit(request: Request) -> AuditStore:
    return request.app.state.audit_store


def _check_confirmed(confirmed: bool | None) -> None:
    if confirmed is False:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="user approval is required for this action",
        )


def _listing_or_404(store, listing_id: str):
    try:
        return store.get(listing_id)
    except KeyError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="listing not found"
        )


def _offer_or_404(store, offer_id: str):
    try:
        return store.get(offer_id)
    except KeyError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="offer not found"
        )


def _dec_str(value) -> str | None:
    if value is None:
        return None
    if isinstance(value, Decimal):
        return format(value, "f")
    return str(value)


def _listing_payload(listing) -> dict[str, Any]:
    return {
        "id": listing.id,
        "kind": listing.kind,
        "owner_user": listing.owner_user,
        "company_id": listing.company_id,
        "title": listing.title,
        "raw_text": listing.raw_text,
        "product": listing.product,
        "quantity": _dec_str(listing.quantity),
        "unit": listing.unit,
        "delivery_place": listing.delivery_place,
        "delivery_days": listing.delivery_days,
        "category": listing.category,
        "features": dict(listing.features or {}),
        "items": [
            {
                "product": i.product,
                "quantity": _dec_str(i.quantity),
                "unit": i.unit,
                "category": i.category,
                "features": dict(i.features or {}),
                "description": i.description,
            }
            for i in (listing.items or [])
        ],
        "missing_fields": list(listing.missing_fields or []),
        "needs_clarification": bool(listing.needs_clarification),
        "status": listing.status,
        "created_at": listing.created_at,
        "updated_at": listing.updated_at,
    }


def _offer_payload(offer) -> dict[str, Any]:
    return {
        "id": offer.id,
        "listing_id": offer.listing_id,
        "offerer_user": offer.offerer_user,
        "offerer_company_id": offer.offerer_company_id,
        "revision_no": offer.revision_no,
        "parent_offer_id": offer.parent_offer_id,
        "lines": [
            {
                "quantity": _dec_str(ln.quantity),
                "unit": ln.unit,
                "unit_price": _dec_str(ln.unit_price),
                "currency": ln.currency,
                "features": dict(ln.features or {}),
                "product": ln.product,
                "line_total": _dec_str(ln.line_total),
            }
            for ln in (offer.lines or [])
        ],
        "total": _dec_str(offer.total()),
        "currency": offer.currency,
        "tax_included": offer.tax_included,
        "shipping_included": offer.shipping_included,
        "shipping_cost": _dec_str(offer.shipping_cost),
        "delivery_days": offer.delivery_days,
        "payment_terms": offer.payment_terms,
        "conditional": bool(offer.conditional),
        "note": offer.note,
        "status": offer.status,
        "created_at": offer.created_at,
        "updated_at": offer.updated_at,
    }


def _agreement_payload(agreement) -> dict[str, Any]:
    return {
        "id": agreement.id,
        "listing_id": agreement.listing_id,
        "offer_id": agreement.offer_id,
        "buyer_user": agreement.buyer_user,
        "buyer_company_id": agreement.buyer_company_id,
        "seller_user": agreement.seller_user,
        "seller_company_id": agreement.seller_company_id,
        "total": _dec_str(agreement.total),
        "currency": agreement.currency,
        "status": agreement.status,
        "created_at": agreement.created_at,
    }


def _notify(request: Request, user: str, text: str, *, kind: str = "info",
            listing_id: str | None = None, offer_id: str | None = None,
            company_id: str = "default"):
    _ls, _os, _as, _ms, notifications = _stores(request)
    return notifications.create(
        user=user, text=text, kind=kind, company_id=company_id,
        listing_id=listing_id, offer_id=offer_id,
    )


# ------------------------------------------------------------ trust helpers

def _all_items(store) -> list:
    fn = getattr(store, "list", None)
    if callable(fn):
        try:
            return list(fn())
        except Exception:
            return []
    return []


def _derive_display_name(tenant: str, subject: str) -> str:
    if tenant and tenant != "default":
        return tenant
    return subject


def _company_summary(request: Request, company_id: str, *, owner_user: str | None = None) -> dict[str, Any]:
    listings, offers, agreements, _m, _n = _stores(request)
    all_listings = _all_items(listings)
    # The "default" tenant is a placeholder: company separation is done via the user.
    scoped = company_id != "default" or owner_user is None
    if scoped:
        company_listings = [l for l in all_listings if l.company_id == company_id]
    else:
        company_listings = [l for l in all_listings if l.owner_user == owner_user]
    published_now = sum(1 for l in company_listings if l.status == "published")
    has_published = any(l.status in ("published", "awarded", "closed") for l in company_listings)
    all_agreements = _all_items(agreements)
    if scoped:
        company_agreements = [
            a for a in all_agreements
            if a.buyer_company_id == company_id or a.seller_company_id == company_id
        ]
    else:
        company_agreements = [
            a for a in all_agreements
            if a.buyer_user == owner_user or a.seller_user == owner_user
        ]
    completed = sum(1 for a in company_agreements if a.status != "cancelled")
    if scoped:
        offers_sent = sum(
            1 for o in _all_items(offers) if o.offerer_company_id == company_id
        )
    else:
        offers_sent = sum(
            1 for o in _all_items(offers) if o.offerer_user == owner_user
        )
    has_agreement = completed > 0
    if has_agreement:
        level = "verified"
    elif has_published:
        level = "active"
    else:
        level = "new"
    return {
        "company_id": company_id,
        "level": level,
        "trust_level": level,
        "has_published": bool(has_published),
        "has_agreement": bool(has_agreement),
        "published_listings": published_now,
        "agreements_completed": completed,
        "completed_agreements": completed,
        "offers_sent": offers_sent,
    }


def _company_block(request: Request, company_id: str, owner_user: str) -> dict[str, Any]:
    s = _company_summary(request, company_id, owner_user=owner_user)
    return {
        "company_id": s["company_id"],
        "display_name": _derive_display_name(company_id, owner_user),
        "level": s["level"],
        "trust_level": s["level"],
        "has_published": s["has_published"],
        "has_agreement": s["has_agreement"],
        "agreements_completed": s["agreements_completed"],
        "completed_agreements": s["completed_agreements"],
        "published_listings": s["published_listings"],
    }


def _with_trust(request: Request, payload: dict[str, Any], company_id: str, owner_user: str) -> dict[str, Any]:
    block = _company_block(request, company_id, owner_user)
    payload["company"] = block
    payload["owner_company"] = dict(block)
    payload["trust"] = {
        "level": block["level"],
        "has_published": block["has_published"],
        "has_agreement": block["has_agreement"],
        "agreements_completed": block["agreements_completed"],
    }
    return payload


def _member_since(request: Request, subject: str) -> float | None:
    try:
        entries = _audit(request).list()
    except Exception:
        return None
    stamps = [e.timestamp for e in entries if e.actor == subject]
    return min(stamps) if stamps else None


# ------------------------------------------------------------ panel / firma

@router.get("/marketplace/dashboard")
def marketplace_dashboard(
    request: Request,
    user: dict = Depends(get_current_user),
) -> dict[str, Any]:
    subject = _subject(user)
    listings, offers, agreements, messages, notifications = _stores(request)
    all_listings = _all_items(listings)
    all_offers = _all_items(offers)
    all_agreements = _all_items(agreements)
    all_messages = _all_items(messages)
    my = [l for l in all_listings if l.owner_user == subject]
    my_ids = {l.id for l in my}
    by_id = {l.id: l for l in all_listings}

    my_listings = {
        "draft": sum(1 for l in my if l.status == "draft"),
        "published": sum(1 for l in my if l.status == "published"),
        "awarded": sum(1 for l in my if l.status == "awarded"),
        "closed": sum(1 for l in my if l.status == "closed"),
        "total": len(my),
    }
    offers_received_open = sum(
        1 for o in all_offers if o.listing_id in my_ids and o.status == "submitted"
    )
    offers_sent_open = sum(
        1 for o in all_offers if o.offerer_user == subject and o.status == "submitted"
    )
    revision_requested = sum(
        1 for o in all_offers if o.offerer_user == subject and o.status == "revision_requested"
    )
    unread = sum(
        1 for n in notifications.list_for_user(subject) if not n.read
    )

    activity: list[dict[str, Any]] = []

    def _push(ts, typ, text, listing_id=None, offer_id=None):
        activity.append({
            "type": typ,
            "timestamp": ts,
            "created_at": ts,
            "text": text,
            "description": text,
            "listing_id": listing_id,
            "offer_id": offer_id,
        })

    for l in my:
        _push(l.created_at, "listing",
              f"Listing created: {l.title}", listing_id=l.id)
        if l.status in ("published", "awarded", "closed") and l.updated_at != l.created_at:
            _push(l.updated_at, "listing",
                  f"Listing {l.status}: {l.title}", listing_id=l.id)
    for o in all_offers:
        title = by_id[o.listing_id].title if o.listing_id in by_id else o.listing_id
        if o.offerer_user == subject:
            _push(o.created_at, "offer_sent",
                  f"Offer sent: {title}", listing_id=o.listing_id, offer_id=o.id)
            if o.status == "revision_requested":
                _push(o.updated_at, "revision_requested",
                      f"Revision requested for offer: {title}",
                      listing_id=o.listing_id, offer_id=o.id)
        elif o.listing_id in my_ids:
            _push(o.created_at, "offer_received",
                  f"Offer received: {title}", listing_id=o.listing_id, offer_id=o.id)
            if o.status == "revision_requested":
                _push(o.updated_at, "revision_requested",
                      f"Revize istendi: {title}",
                      listing_id=o.listing_id, offer_id=o.id)
    for m in all_messages:
        if m.sender_user == subject or m.recipient_user == subject:
            title = by_id[m.listing_id].title if m.listing_id in by_id else m.listing_id
            _push(m.created_at, "message",
                  f"Mesaj: {title}", listing_id=m.listing_id, offer_id=m.offer_id)
    for a in all_agreements:
        if a.buyer_user == subject or a.seller_user == subject:
            title = by_id[a.listing_id].title if a.listing_id in by_id else a.listing_id
            _push(a.created_at, "agreement",
                  f"Agreement created: {title}", listing_id=a.listing_id, offer_id=a.offer_id)

    activity.sort(key=lambda e: e["timestamp"], reverse=True)
    return {
        "my_listings": my_listings,
        "offers_received_open": offers_received_open,
        "offers_sent_open": offers_sent_open,
        "revision_requested": revision_requested,
        "unread_notifications": unread,
        "recent_activity": activity[:10],
    }


@router.get("/marketplace/company/me")
def marketplace_company_me(
    request: Request,
    user: dict = Depends(get_current_user),
) -> dict[str, Any]:
    tenant = _tenant(user)
    subject = _subject(user)
    summary = _company_summary(request, tenant, owner_user=subject)
    return {
        "company_id": tenant,
        "display_name": _derive_display_name(tenant, subject),
        "member_since": _member_since(request, subject),
        "stats": {
            "published_listings": summary["published_listings"],
            "agreements_completed": summary["agreements_completed"],
            "offers_sent": summary["offers_sent"],
        },
        "trust": {
            "has_published": summary["has_published"],
            "has_agreement": summary["has_agreement"],
            "level": summary["level"],
        },
    }


# ------------------------------------------------------------------ listing parsing

@router.post("/marketplace/parse-listing")
def parse_listing_endpoint(
    body: ParseListingRequest,
    request: Request,
    user: dict = Depends(get_current_user),
) -> dict[str, Any]:
    _ = user
    text = body.raw_text if body.raw_text is not None else body.text
    try:
        parsed = parse_listing(text or "", kind=body.kind or "demand")
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    payload = parsed.to_dict()
    payload["document"] = render_listing_document(parsed)
    return payload


@router.post("/marketplace/listings", status_code=status.HTTP_201_CREATED)
def create_listing(
    body: CreateListingRequest,
    request: Request,
    user: dict = Depends(get_current_user),
) -> dict[str, Any]:
    listings, _o, _a, _m, _n = _stores(request)
    raw_text = body.raw_text if body.raw_text is not None else (body.text or "")
    kind = body.kind or "demand"
    parsed = None
    if raw_text:
        try:
            parsed = parse_listing(raw_text, kind=kind)
        except ValueError as exc:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    fields: dict[str, Any] = {}
    if parsed is not None:
        fields = {
            "title": parsed.title, "product": parsed.product,
            "quantity": parsed.quantity, "unit": parsed.unit,
            "delivery_place": parsed.delivery_place,
            "delivery_days": parsed.delivery_days, "category": parsed.category,
            "features": dict(parsed.features),
            "missing_fields": list(parsed.missing_fields),
            "needs_clarification": bool(parsed.needs_clarification),
        }
    # Fields edited by the user override the parsing result.
    if body.title is not None:
        fields["title"] = body.title
    if body.product is not None:
        fields["product"] = body.product
    if body.quantity is not None:
        fields["quantity"] = to_decimal(body.quantity)
    if body.unit is not None:
        fields["unit"] = body.unit
    if body.delivery_place is not None:
        fields["delivery_place"] = body.delivery_place
    if body.delivery_days is not None:
        fields["delivery_days"] = body.delivery_days
    if body.category is not None:
        fields["category"] = body.category
    if body.features is not None:
        merged = dict(fields.get("features") or {})
        merged.update(body.features)
        fields["features"] = merged
    if body.missing_fields is not None:
        fields["missing_fields"] = list(body.missing_fields)
    if body.needs_clarification is not None:
        fields["needs_clarification"] = bool(body.needs_clarification)
    try:
        listing = listings.create(
            kind=kind, owner_user=_subject(user), company_id=_tenant(user),
            raw_text=raw_text or "", **fields,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    _audit(request).append(
        actor=_subject(user), action="marketplace.listing_create",
        target=f"listing:{listing.id}",
    )
    payload = _listing_payload(listing)
    payload["document"] = render_listing_document(listing)
    return payload


@router.patch("/marketplace/listings/{listing_id}")
def patch_listing(
    listing_id: str,
    body: PatchListingRequest,
    request: Request,
    user: dict = Depends(get_current_user),
) -> dict[str, Any]:
    listings, _o, _a, _m, _n = _stores(request)
    listing = _listing_or_404(listings, listing_id)
    if listing.owner_user != _subject(user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="only the listing owner can edit",
        )
    if listing.status != "draft":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="only a draft listing can be edited",
        )
    raw_text = body.raw_text if body.raw_text is not None else body.text
    if raw_text is not None:
        listing.raw_text = raw_text
        try:
            parsed = parse_listing(raw_text, kind=listing.kind)
        except ValueError as exc:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
        # New text only pre-fills empty fields.
        if not listing.product:
            listing.product = parsed.product
        if listing.quantity is None:
            listing.quantity = parsed.quantity
        if not listing.unit:
            listing.unit = parsed.unit
        if not listing.delivery_place:
            listing.delivery_place = parsed.delivery_place
        if listing.delivery_days is None:
            listing.delivery_days = parsed.delivery_days
        if not listing.category:
            listing.category = parsed.category
        if not listing.features:
            listing.features = dict(parsed.features)
        listing.missing_fields = list(parsed.missing_fields)
        listing.needs_clarification = bool(parsed.needs_clarification)
    if body.title is not None:
        listing.title = body.title
    if body.product is not None:
        listing.product = body.product
    if body.quantity is not None:
        listing.quantity = to_decimal(body.quantity)
    if body.unit is not None:
        listing.unit = body.unit
    if body.delivery_place is not None:
        listing.delivery_place = body.delivery_place
    if body.delivery_days is not None:
        listing.delivery_days = body.delivery_days
    if body.category is not None:
        listing.category = body.category
    if body.features is not None:
        merged = dict(listing.features or {})
        merged.update(body.features)
        listing.features = merged
    if body.missing_fields is not None:
        listing.missing_fields = list(body.missing_fields)
    if body.needs_clarification is not None:
        listing.needs_clarification = bool(body.needs_clarification)
    updated = listings.update(listing)
    _audit(request).append(
        actor=_subject(user), action="marketplace.listing_update",
        target=f"listing:{updated.id}",
    )
    return _listing_payload(updated)


@router.post("/marketplace/listings/{listing_id}/publish")
def publish_listing(
    listing_id: str,
    request: Request,
    body: ConfirmRequest | None = None,
    user: dict = Depends(get_current_user),
) -> dict[str, Any]:
    _check_confirmed(body.confirmed if body else None)
    listings, _o, _a, _m, _n = _stores(request)
    listing = _listing_or_404(listings, listing_id)
    if listing.owner_user != _subject(user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="only the listing owner can publish",
        )
    # If information is missing the listing is still published; the label stays visible.
    if listing.missing_fields and not listing.needs_clarification:
        listing.needs_clarification = True
        listings.update(listing)
    try:
        published = listings.publish(listing_id, confirmed=True)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    _audit(request).append(
        actor=_subject(user), action="marketplace.listing_publish",
        target=f"listing:{published.id}",
    )
    payload = _listing_payload(published)
    payload["document"] = render_listing_document(published)
    return payload


@router.get("/marketplace/listings")
def list_listings(
    request: Request,
    kind: str | None = None,
    category: str | None = None,
    q: str | None = None,
    location: str | None = None,
    max_delivery_days: int | None = None,
    sort: str | None = None,
    open_only: bool = False,
    only_open: bool | None = None,
    open: bool | None = None,
    user: dict = Depends(get_current_user),
) -> dict[str, Any]:
    _ = user
    listings, _o, _a, _m, _n = _stores(request)
    items = listings.list_published(kind=kind)
    if open_only or only_open or open:
        items = [i for i in items if i.status == "published"]

    def low(value: Any) -> str:
        return str(value or "").lower()

    if category:
        items = [i for i in items if low(i.category) == category.lower()]
    if q:
        needle = q.lower()
        items = [
            i for i in items
            if needle in low(i.product) or needle in low(i.title)
            or needle in low(i.category) or needle in low(i.raw_text)
        ]
    if location:
        needle = location.lower()
        items = [i for i in items if needle in low(i.delivery_place)]
    if max_delivery_days is not None:
        items = [
            i for i in items
            if i.delivery_days is not None and i.delivery_days <= max_delivery_days
        ]
    if sort in ("delivery", "delivery_days"):
        items = sorted(
            items,
            key=lambda i: (i.delivery_days is None, i.delivery_days or 0, -i.created_at),
        )
    elif sort == "newest":
        items = sorted(items, key=lambda i: i.created_at, reverse=True)
    return {"listings": [_with_trust(request, _listing_payload(i), i.company_id, i.owner_user) for i in items]}


@router.get("/marketplace/my/listings")
def my_listings(
    request: Request,
    user: dict = Depends(get_current_user),
) -> dict[str, Any]:
    listings, _o, _a, _m, _n = _stores(request)
    items = [i for i in listings.list() if i.owner_user == _subject(user)]
    return {"listings": [_with_trust(request, _listing_payload(i), i.company_id, i.owner_user) for i in items]}


@router.get("/marketplace/listings/{listing_id}")
def get_listing(
    listing_id: str,
    request: Request,
    user: dict = Depends(get_current_user),
) -> dict[str, Any]:
    listings, _o, _a, _m, _n = _stores(request)
    listing = _listing_or_404(listings, listing_id)
    if listing.status == "draft" and listing.owner_user != _subject(user):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="listing not found"
        )
    payload = _listing_payload(listing)
    payload["document"] = render_listing_document(listing)
    summary = _company_summary(request, listing.company_id, owner_user=listing.owner_user)
    company_block = {
        "company_id": summary["company_id"],
        "display_name": _derive_display_name(listing.company_id, listing.owner_user),
        "level": summary["level"],
        "trust_level": summary["level"],
        "has_published": summary["has_published"],
        "has_agreement": summary["has_agreement"],
        "agreements_completed": summary["agreements_completed"],
        "completed_agreements": summary["completed_agreements"],
        "published_listings": summary["published_listings"],
    }
    payload["company"] = company_block
    payload["owner_company"] = dict(company_block)
    payload["trust"] = {
        "level": summary["level"],
        "has_published": summary["has_published"],
        "has_agreement": summary["has_agreement"],
        "agreements_completed": summary["agreements_completed"],
    }
    return payload


# ------------------------------------------------------------------ offers

def _catalog_prefill(request: Request, body) -> tuple[Decimal | None, str | None]:
    """A catalog price is only an optional pre-fill; it is not mandatory."""
    price = to_decimal(body.catalog_price) if getattr(body, "catalog_price", None) is not None else None
    currency = getattr(body, "catalog_currency", None)
    product_id = getattr(body, "catalog_product_id", None)
    if price is None and product_id:
        price_store = getattr(request.app.state, "price_store", None)
        if price_store is not None:
            try:
                effective = price_store.effective_for_product(product_id)
            except Exception:
                effective = None
            if effective is not None:
                price = to_decimal(effective.price)
                currency = currency or effective.currency
    return price, currency


def _build_offer_lines(request: Request, listing, body) -> tuple[list[OfferLine], dict[str, Any]]:
    """Builds offer lines from text, a structured body, or a catalog pre-fill."""
    text = getattr(body, "raw_text", None) or getattr(body, "text", None)
    parsed = parse_offer(text) if text else None
    extras: dict[str, Any] = {}
    if parsed is not None:
        extras = {
            "tax_included": parsed.tax_included,
            "shipping_included": parsed.shipping_included,
            "shipping_cost": parsed.shipping_cost,
            "delivery_days": parsed.delivery_days,
            "payment_terms": parsed.payment_terms,
            "conditional": parsed.conditional,
        }
    lines: list[OfferLine] = []
    if getattr(body, "lines", None):
        for item in body.lines:
            lines.append(OfferLine(
                quantity=to_decimal(item.quantity) if item.quantity is not None else None,
                unit=item.unit, unit_price=to_decimal(item.unit_price) if item.unit_price is not None else None,
                currency=item.currency, product=item.product,
                features=dict(item.features or {}),
            ))
    elif parsed is not None and parsed.lines:
        lines = [
            OfferLine(quantity=ln.quantity, unit=ln.unit, unit_price=ln.unit_price,
                      currency=ln.currency, features=dict(ln.features or {}), product=ln.product)
            for ln in parsed.lines
        ]
    body_qty = to_decimal(body.quantity) if getattr(body, "quantity", None) is not None else None
    body_price = to_decimal(body.unit_price) if getattr(body, "unit_price", None) is not None else None
    if lines:
        for line in lines:
            if body_qty is not None:
                line.quantity = body_qty
            if getattr(body, "unit", None) is not None:
                line.unit = body.unit
            if body_price is not None:
                line.unit_price = body_price
            if getattr(body, "currency", None) is not None:
                line.currency = body.currency
    elif body_price is not None or body_qty is not None:
        lines = [OfferLine(quantity=body_qty, unit=getattr(body, "unit", None),
                           unit_price=body_price, currency=getattr(body, "currency", None))]
    cat_price, cat_currency = _catalog_prefill(request, body)
    if not lines and cat_price is not None:
        lines = [OfferLine(
            quantity=listing.quantity, unit=listing.unit,
            unit_price=cat_price,
            currency=cat_currency or getattr(body, "currency", None),
            product=listing.product,
        )]
    for line in lines:
        if line.quantity is None:
            line.quantity = listing.quantity
        if not line.unit:
            line.unit = listing.unit
        if not line.product:
            line.product = listing.product
        if line.unit_price is None and cat_price is not None:
            line.unit_price = cat_price
        if not line.currency and cat_currency:
            line.currency = cat_currency
        if getattr(body, "currency", None) and not line.currency:
            line.currency = body.currency
    for key in ("tax_included", "shipping_included", "shipping_cost",
                "delivery_days", "payment_terms"):
        value = getattr(body, key, None)
        if value is not None:
            extras[key] = to_decimal(value) if key == "shipping_cost" else value
    if getattr(body, "note", None) is not None:
        extras["note"] = body.note
    return lines, extras


def _validate_offer_lines(lines: list[OfferLine]) -> None:
    if not lines:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="at least one priced line is required for an offer",
        )
    for line in lines:
        if line.unit_price is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="a unit price is required; an unspecified price is never invented",
            )
        if line.unit_price <= 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="the unit price must be greater than zero",
            )


@router.post("/marketplace/listings/{listing_id}/offers/parse")
def parse_offer_endpoint(
    listing_id: str,
    body: ParseOfferRequest,
    request: Request,
    user: dict = Depends(get_current_user),
) -> dict[str, Any]:
    _ = user
    listings, _o, _a, _m, _n = _stores(request)
    listing = _listing_or_404(listings, listing_id)
    text = body.raw_text if body.raw_text is not None else body.text
    parsed = parse_offer(text or "")
    payload = parsed.to_dict()
    lines = []
    for ln in parsed.lines:
        qty = ln.quantity if ln.quantity is not None else listing.quantity
        unit = ln.unit or listing.unit
        line_total = qty * ln.unit_price if (qty is not None and ln.unit_price is not None) else None
        lines.append({
            "quantity": _dec_str(qty), "unit": unit,
            "unit_price": _dec_str(ln.unit_price), "currency": ln.currency,
            "features": dict(ln.features or {}),
            "line_total": _dec_str(line_total),
        })
    total: Decimal | None = None
    for ln in lines:
        if ln["line_total"] is not None:
            total = (total or Decimal("0")) + Decimal(ln["line_total"])
    if total is not None and parsed.shipping_included is False and parsed.shipping_cost is not None:
        total += parsed.shipping_cost
    payload["lines"] = lines
    payload["total"] = _dec_str(total)
    payload["listing_id"] = listing.id
    return payload


@router.post("/marketplace/listings/{listing_id}/offers", status_code=status.HTTP_201_CREATED)
def create_offer(
    listing_id: str,
    body: CreateOfferRequest,
    request: Request,
    catalog_price: Any = None,
    user: dict = Depends(get_current_user),
) -> dict[str, Any]:
    _check_confirmed(body.confirmed)
    if body.catalog_price is None and catalog_price is not None:
        body.catalog_price = catalog_price
    listings, offers, _a, _m, _n = _stores(request)
    listing = _listing_or_404(listings, listing_id)
    if listing.owner_user == _subject(user):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="you cannot make an offer on your own listing",
        )
    if listing.status != "published":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="offers can only be made on a published listing",
        )
    lines, extras = _build_offer_lines(request, listing, body)
    _validate_offer_lines(lines)
    offer = offers.create(
        listing_id=listing.id, offerer_user=_subject(user),
        offerer_company_id=_tenant(user), lines=lines, status="draft", **extras,
    )
    try:
        submitted = offers.submit(offer.id, confirmed=True)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    _audit(request).append(
        actor=_subject(user), action="marketplace.offer_submit",
        target=f"offer:{submitted.id}",
    )
    _notify(request, listing.owner_user,
            f"New offer on your listing: {listing.title}",
            kind="offer", listing_id=listing.id, offer_id=submitted.id,
            company_id=listing.company_id)
    payload = _offer_payload(submitted)
    payload["document"] = render_offer_document(submitted, listing)
    return payload


@router.get("/marketplace/listings/{listing_id}/offers")
def list_offers(
    listing_id: str,
    request: Request,
    user: dict = Depends(get_current_user),
) -> dict[str, Any]:
    listings, offers, _a, _m, _n = _stores(request)
    listing = _listing_or_404(listings, listing_id)
    all_offers = offers.list_for_listing(listing.id)
    if listing.owner_user == _subject(user):
        visible = all_offers
    else:
        visible = [o for o in all_offers if o.offerer_user == _subject(user)]
    return {"offers": [_offer_payload(o) for o in visible]}


@router.get("/marketplace/my/offers")
def my_offers(
    request: Request,
    user: dict = Depends(get_current_user),
) -> dict[str, Any]:
    _l, offers, _a, _m, _n = _stores(request)
    items = offers.list_for_offerer(_subject(user))
    return {"offers": [_offer_payload(o) for o in items]}


@router.post("/marketplace/offers/{offer_id}/revise", status_code=status.HTTP_201_CREATED)
def revise_offer(
    offer_id: str,
    body: ReviseOfferRequest,
    request: Request,
    user: dict = Depends(get_current_user),
) -> dict[str, Any]:
    _check_confirmed(body.confirmed)
    listings, offers, _a, _m, _n = _stores(request)
    parent = _offer_or_404(offers, offer_id)
    if parent.offerer_user != _subject(user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="only the offerer can revise",
        )
    listing = _listing_or_404(listings, parent.listing_id)
    changes: dict[str, Any] = {}
    has_lines_input = bool(body.lines) or bool(body.text) or bool(body.raw_text) or body.unit_price is not None or body.quantity is not None
    if has_lines_input:
        lines, extras = _build_offer_lines(request, listing, body)
        _validate_offer_lines(lines)
        changes["lines"] = lines
        changes.update({k: v for k, v in extras.items() if v is not None or k == "note"})
    else:
        for key in ("tax_included", "shipping_included", "shipping_cost",
                    "delivery_days", "payment_terms", "note"):
            value = getattr(body, key)
            if value is not None:
                changes[key] = to_decimal(value) if key == "shipping_cost" else value
    try:
        revision = offers.create_revision(offer_id, **changes)
        submitted = offers.submit(revision.id, confirmed=True)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    try:
        current = offers.get(offer_id)
        if current.status in ("submitted", "revision_requested"):
            offers.withdraw(offer_id)
    except Exception:
        pass
    _audit(request).append(
        actor=_subject(user), action="marketplace.offer_revise",
        target=f"offer:{submitted.id}", detail=f"parent:{offer_id}",
    )
    _notify(request, listing.owner_user,
            f"Teklif revize edildi: {listing.title}",
            kind="offer_revision", listing_id=listing.id, offer_id=submitted.id,
            company_id=listing.company_id)
    return _offer_payload(submitted)


@router.post("/marketplace/offers/{offer_id}/request-revision")
def request_revision(
    offer_id: str,
    body: RequestRevisionRequest,
    request: Request,
    user: dict = Depends(get_current_user),
) -> dict[str, Any]:
    listings, offers, _a, messages, _n = _stores(request)
    offer = _offer_or_404(offers, offer_id)
    listing = _listing_or_404(listings, offer.listing_id)
    if listing.owner_user != _subject(user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="only the listing owner can request a revision",
        )
    try:
        updated = offers.request_revision(offer_id, note=body.note or "")
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    note_text = body.note or "Revize istendi"
    messages.create(
        listing_id=listing.id, sender_user=_subject(user), body=note_text,
        recipient_user=offer.offerer_user, offer_id=offer.id,
        company_id=listing.company_id,
    )
    _notify(request, offer.offerer_user,
            f"A revision was requested for your offer: {listing.title}",
            kind="revision_requested", listing_id=listing.id, offer_id=offer.id,
            company_id=offer.offerer_company_id)
    _audit(request).append(
        actor=_subject(user), action="marketplace.offer_request_revision",
        target=f"offer:{offer.id}",
    )
    return _offer_payload(updated)


@router.post("/marketplace/offers/{offer_id}/select")
def select_offer_endpoint(
    offer_id: str,
    request: Request,
    body: ConfirmRequest | None = None,
    user: dict = Depends(get_current_user),
) -> dict[str, Any]:
    _check_confirmed(body.confirmed if body else None)
    listings, offers, agreements, _m, _n = _stores(request)
    offer = _offer_or_404(offers, offer_id)
    listing = _listing_or_404(listings, offer.listing_id)
    if listing.owner_user != _subject(user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="only the listing owner can select an offer",
        )
    try:
        agreement = select_offer(
            listings, offers, agreements, listing.id, offer_id, confirmed=True,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    selected = _offer_or_404(offers, offer_id)
    _audit(request).append(
        actor=_subject(user), action="marketplace.offer_select",
        target=f"offer:{offer_id}", detail=f"agreement:{agreement.id}",
    )
    _notify(request, offer.offerer_user,
            f"Your offer was selected: {listing.title}",
            kind="offer_selected", listing_id=listing.id, offer_id=offer_id,
            company_id=offer.offerer_company_id)
    return {
        "offer": _offer_payload(selected),
        "agreement": _agreement_payload(agreement),
        "listing": _listing_payload(_listing_or_404(listings, listing.id)),
    }


@router.get("/marketplace/listings/{listing_id}/comparison")
def comparison(
    listing_id: str,
    request: Request,
    user: dict = Depends(get_current_user),
) -> dict[str, Any]:
    listings, offers, _a, _m, _n = _stores(request)
    listing = _listing_or_404(listings, listing_id)
    if listing.owner_user != _subject(user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="only the listing owner can see the comparison",
        )
    candidates = [
        o for o in offers.list_for_listing(listing.id)
        if o.status in ("submitted", "revision_requested", "selected")
    ]
    currencies = {o.currency for o in candidates if o.currency}
    first_currency = candidates[0].currency if candidates else None
    entries = []
    for offer in candidates:
        reasons: list[str] = []
        for line in (offer.lines or []):
            if listing.unit and line.unit and line.unit != listing.unit:
                reasons.append(f"unit mismatch: offer {line.unit}, listing {listing.unit}")
            for key, expected in (listing.features or {}).items():
                if key in (line.features or {}) and str(line.features[key]) != str(expected):
                    reasons.append(f"{key} mismatch: offer {line.features[key]}, listing {expected}")
        line_currencies = {ln.currency for ln in (offer.lines or []) if ln.currency}
        if len(line_currencies) > 1:
            reasons.append("the offer contains multiple currencies")
        if len(currencies) > 1 and offer.currency != first_currency:
            reasons.append("the currency differs from the other offers")
        missing_costs: list[str] = []
        if offer.tax_included is None:
            missing_costs.append("VAT not specified")
        if offer.shipping_included is None:
            missing_costs.append("shipping not specified")
        elif offer.shipping_included is False and offer.shipping_cost is None:
            missing_costs.append("shipping amount not specified")
        _block = _company_block(request, offer.offerer_company_id, offer.offerer_user)
        entries.append({
            "offer_id": offer.id,
            "offerer_user": offer.offerer_user,
            "company": _block,
            "trust": {"level": _block["level"], "has_published": _block["has_published"], "has_agreement": _block["has_agreement"], "agreements_completed": _block["agreements_completed"]},
            "revision_no": offer.revision_no,
            "status": offer.status,
            "total": _dec_str(offer.total()),
            "currency": offer.currency,
            "tax_included": offer.tax_included,
            "shipping_included": offer.shipping_included,
            "shipping_cost": _dec_str(offer.shipping_cost),
            "delivery_days": offer.delivery_days,
            "payment_terms": offer.payment_terms,
            "missing_costs": missing_costs,
            "comparable": not reasons,
            "comparable_reasons": reasons,
            "offer": _offer_payload(offer),
        })
    return {"listing_id": listing.id, "offers": entries}


def _offer_parties(request: Request, offer_id: str):
    listings, offers, _a, _m, _n = _stores(request)
    offer = _offer_or_404(offers, offer_id)
    listing = _listing_or_404(listings, offer.listing_id)
    return listing, offer


def _check_party(listing, offer, user: dict) -> None:
    if _subject(user) not in (listing.owner_user, offer.offerer_user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="only the two parties can see the messages",
        )


@router.post("/marketplace/offers/{offer_id}/messages", status_code=status.HTTP_201_CREATED)
def post_message(
    offer_id: str,
    body: MessageRequest,
    request: Request,
    user: dict = Depends(get_current_user),
) -> dict[str, Any]:
    if not (body.body or "").strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="mesaj metni gerekli",
        )
    _l, _o, _a, messages, _n = _stores(request)
    listing, offer = _offer_parties(request, offer_id)
    _check_party(listing, offer, user)
    recipient = offer.offerer_user if _subject(user) == listing.owner_user else listing.owner_user
    message = messages.create(
        listing_id=listing.id, sender_user=_subject(user), body=body.body,
        recipient_user=recipient, offer_id=offer.id, company_id=listing.company_id,
    )
    _audit(request).append(
        actor=_subject(user), action="marketplace.message_create",
        target=f"offer:{offer.id}",
    )
    _notify(request, recipient, f"Yeni mesaj: {listing.title}",
            kind="message", listing_id=listing.id, offer_id=offer.id,
            company_id=listing.company_id)
    return {
        "id": message.id, "listing_id": message.listing_id,
        "offer_id": message.offer_id, "sender_user": message.sender_user,
        "recipient_user": message.recipient_user, "body": message.body,
        "created_at": message.created_at,
    }


@router.get("/marketplace/offers/{offer_id}/messages")
def list_messages(
    offer_id: str,
    request: Request,
    user: dict = Depends(get_current_user),
) -> dict[str, Any]:
    _l, _o, _a, messages, _n = _stores(request)
    listing, offer = _offer_parties(request, offer_id)
    _check_party(listing, offer, user)
    items = [
        m for m in messages.list_for_listing(listing.id) if m.offer_id == offer.id
    ]
    items.sort(key=lambda m: m.created_at)
    return {"messages": [
        {
            "id": m.id, "listing_id": m.listing_id, "offer_id": m.offer_id,
            "sender_user": m.sender_user, "recipient_user": m.recipient_user,
            "body": m.body, "created_at": m.created_at,
        }
        for m in items
    ]}


@router.get("/marketplace/notifications")
def list_notifications(
    request: Request,
    user: dict = Depends(get_current_user),
) -> dict[str, Any]:
    _l, _o, _a, _m, notifications = _stores(request)
    items = notifications.list_for_user(_subject(user))
    items.sort(key=lambda n: n.created_at)
    return {"notifications": [
        {
            "id": n.id, "user": n.user, "text": n.text, "kind": n.kind,
            "company_id": n.company_id, "listing_id": n.listing_id,
            "offer_id": n.offer_id, "read": bool(n.read),
            "created_at": n.created_at,
        }
        for n in items
    ]}


@router.post("/marketplace/notifications/{notification_id}/read")
def read_notification(
    notification_id: str,
    request: Request,
    user: dict = Depends(get_current_user),
) -> dict[str, Any]:
    _l, _o, _a, _m, notifications = _stores(request)
    try:
        note = notifications.get(notification_id)
    except KeyError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="notification not found"
        )
    if note.user != _subject(user):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="notification not found"
        )
    updated = notifications.mark_read(notification_id)
    _audit(request).append(
        actor=_subject(user), action="marketplace.notification_read",
        target=f"notification:{notification_id}",
    )
    return {
        "id": updated.id, "user": updated.user, "text": updated.text,
        "kind": updated.kind, "read": bool(updated.read),
        "listing_id": updated.listing_id, "offer_id": updated.offer_id,
        "created_at": updated.created_at,
    }


