"""Listing and offer documents (petition-style plain text).

An unspecified field is not written into the text as a value; it is listed
under ``Information to be clarified``. The system never invents a price,
technical detail or payment term.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any


def _get(obj: Any, key: str, default: Any = None) -> Any:
    if obj is None:
        return default
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


def _fmt_decimal(value: Any) -> str:
    if isinstance(value, Decimal):
        return format(value, "f")
    return str(value)


def _missing_labels(obj: Any) -> list[str]:
    labels = {
        "product": "Product", "quantity": "Quantity", "unit": "Unit",
        "delivery_place": "Delivery place", "delivery_days": "Delivery time",
        "diameter": "Diameter", "length": "Length", "wall_thickness": "Wall thickness",
        "unit_price": "Unit price", "currency": "Currency",
        "tax_included": "VAT status", "shipping_included": "Shipping status",
        "shipping_cost": "Shipping amount", "payment_terms": "Payment terms",
    }
    result: list[str] = []
    for name in _get(obj, "missing_fields", []) or []:
        result.append(labels.get(str(name), str(name)))
    # Also collect gaps from the questions on parsed objects (without duplicates).
    for question in _get(obj, "missing_questions", []) or []:
        field_name = _get(question, "field")
        if field_name and labels.get(str(field_name)) not in result:
            if str(field_name) in (_get(obj, "missing_fields", []) or []):
                continue
            result.append(labels.get(str(field_name), str(field_name)))
    return result


def render_listing_document(listing: Any) -> str:
    """Renders the listing as headed, petition-style text."""
    kind = _get(listing, "kind", "demand")
    is_demand = kind == "demand"
    subject_kind = "Procurement Request" if is_demand else "Sales Listing"
    product = _get(listing, "product")
    title = _get(listing, "title") or product or ""
    subject = f"{title} — {subject_kind}".strip(" —") if title else subject_kind

    lines: list[str] = [f"Subject: {subject}", ""]

    intro = "Procurement Request" if is_demand else "Sales Listing"
    lines.append(f"The {intro.lower()} is set out below.")
    lines.append("")

    quantity = _get(listing, "quantity")
    unit = _get(listing, "unit")
    if product:
        verb = "is requested for procurement" if is_demand else "is offered for sale"
        qty_text = ""
        if quantity is not None:
            qty_text = _fmt_decimal(quantity)
            if unit:
                qty_text = f"{qty_text} {unit}"
        detail = f"{qty_text} {product}".strip()
        lines.append(f"{detail} {verb}.")
    elif _get(listing, "raw_text"):
        lines.append(str(_get(listing, "raw_text")))

    features = _get(listing, "features", {}) or {}
    feature_labels = {
        "dn": "DN", "diameter_mm": "Diameter (mm)", "wall_thickness_mm": "Wall thickness (mm)",
        "length": "Length", "pressure_class": "Pressure class",
        "coating": "Coating", "material": "Material",
    }
    for key, value in features.items():
        lines.append(f"{feature_labels.get(str(key), str(key))}: {value}")

    delivery_place = _get(listing, "delivery_place")
    if delivery_place:
        lines.append(f"Delivery place: {delivery_place}")
    delivery_days = _get(listing, "delivery_days")
    if delivery_days is not None:
        lines.append(f"Delivery time: {delivery_days} days")

    lines.append("")
    lines.append("Please state the following in offers:")
    for item in (
        "Unit price and currency",
        "VAT status (included/excluded)",
        "Delivery time",
        "Shipping status (included/excluded)",
        "Payment terms",
    ):
        lines.append(f"- {item}")

    missing = _missing_labels(listing)
    if _get(listing, "needs_clarification"):
        missing.append("Technical specifications (awaiting a supplier suggestion)")
    if missing:
        lines.append("")
        lines.append("Information to be clarified:")
        for item in missing:
            lines.append(f"- {item}")
    return "\n".join(lines).strip() + "\n"


def render_offer_document(offer: Any, listing: Any = None) -> str:
    """Renders the offer as a price table plus terms."""
    product = _get(listing, "product") if listing is not None else None
    if not product and _get(offer, "lines"):
        first = _get(offer, "lines")[0]
        product = _get(first, "product")
    subject = f"{product} — Offer" if product else "Offer"
    lines: list[str] = [f"Subject: {subject}", "", "Price table:"]

    offer_lines = _get(offer, "lines", []) or []
    total: Decimal | None = None
    currency: str | None = None
    if offer_lines:
        for line in offer_lines:
            qty = _get(line, "quantity")
            unit = _get(line, "unit")
            price = _get(line, "unit_price")
            cur = _get(line, "currency")
            if cur and currency is None:
                currency = cur
            lt = None
            if hasattr(line, "line_total"):
                lt = line.line_total
            parts = []
            if qty is not None:
                parts.append(f"{_fmt_decimal(qty)} {unit or ''}".strip())
            if price is not None:
                parts.append(f"x {_fmt_decimal(price)} {cur or ''}".strip())
            if lt is not None:
                parts.append(f"= {_fmt_decimal(lt)} {cur or ''}".strip())
                total = (total or Decimal("0")) + lt
            if parts:
                lines.append("- " + " ".join(parts))
    else:
        lines.append("- (no line specified)")

    shipping_included = _get(offer, "shipping_included")
    shipping_cost = _get(offer, "shipping_cost")
    if total is not None and shipping_included is False and shipping_cost is not None:
        total += shipping_cost if isinstance(shipping_cost, Decimal) else Decimal(str(shipping_cost))
    if total is not None:
        lines.append(f"Total: {_fmt_decimal(total)} {currency or ''}".strip())

    lines.append("")
    lines.append("Terms:")
    tax_included = _get(offer, "tax_included")
    if tax_included is True:
        lines.append("- VAT: included")
    elif tax_included is False:
        lines.append("- VAT: excluded")
    if shipping_included is True:
        lines.append("- Shipping: included")
    elif shipping_included is False:
        if shipping_cost is not None:
            lines.append(f"- Shipping: excluded ({_fmt_decimal(shipping_cost)} {currency or ''})".strip())
        else:
            lines.append("- Shipping: excluded")
    delivery_days = _get(offer, "delivery_days")
    if delivery_days is not None:
        lines.append(f"- Delivery time: {delivery_days} days")
    payment_terms = _get(offer, "payment_terms")
    if payment_terms:
        lines.append(f"- Payment: {payment_terms}")
    if _get(offer, "conditional"):
        lines.append("- This offer is conditional.")
    note = _get(offer, "note")
    if note:
        lines.append(f"- Note: {note}")
    if len(lines) == 0 or lines[-1] == "Terms:":
        lines.append("- (no terms specified)")

    missing = _missing_labels(offer)
    if missing:
        lines.append("")
        lines.append("Information to be clarified:")
        for item in missing:
            lines.append(f"- {item}")
    return "\n".join(lines).strip() + "\n"


# Aliases.
generate_listing_document = render_listing_document
generate_offer_document = render_offer_document
listing_document = render_listing_document
offer_document = render_offer_document
