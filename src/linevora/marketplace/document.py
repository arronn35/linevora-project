"""İlan ve teklif belgeleri (dilekçe benzeri düz metin).

Belirtilmemiş alan metne değer olarak yazılmaz; ``Netleştirilecek
bilgiler`` altında listelenir. Sistem fiyat/teknik/ödeme uydurmaz.
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
        "product": "Ürün", "quantity": "Miktar", "unit": "Birim",
        "delivery_place": "Teslim yeri", "delivery_days": "Teslim süresi",
        "cap": "Çap", "boy": "Boy/uzunluk", "et_kalinligi": "Et kalınlığı",
        "unit_price": "Birim fiyat", "currency": "Para birimi",
        "tax_included": "KDV durumu", "shipping_included": "Nakliye durumu",
        "shipping_cost": "Nakliye tutarı", "payment_terms": "Ödeme şartları",
    }
    result: list[str] = []
    for name in _get(obj, "missing_fields", []) or []:
        result.append(labels.get(str(name), str(name)))
    # Parsed nesnelerindeki sorulardan da eksikleri topla (tekrar etmeden).
    for question in _get(obj, "missing_questions", []) or []:
        field_name = _get(question, "field")
        if field_name and labels.get(str(field_name)) not in result:
            if str(field_name) in (_get(obj, "missing_fields", []) or []):
                continue
            result.append(labels.get(str(field_name), str(field_name)))
    return result


def render_listing_document(listing: Any) -> str:
    """İlanı dilekçe benzeri başlıklı metne çevirir."""
    kind = _get(listing, "kind", "demand")
    is_demand = kind == "demand"
    subject_kind = "Tedarik Talebi" if is_demand else "Satış İlanı"
    product = _get(listing, "product")
    title = _get(listing, "title") or product or ""
    subject = f"{title} — {subject_kind}".strip(" —") if title else subject_kind

    lines: list[str] = [f"Konu: {subject}", ""]

    intro = "Tedarik Talebi" if is_demand else "Satış İlanı"
    lines.append(f"{intro} aşağıda belirtilmektedir.")
    lines.append("")

    quantity = _get(listing, "quantity")
    unit = _get(listing, "unit")
    if product:
        verb = "tedarik edilmek istenmektedir" if is_demand else "satışa sunulmaktadır"
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
        "dn": "DN", "cap_mm": "Çap (mm)", "et_kalinligi_mm": "Et kalınlığı (mm)",
        "boy": "Boy", "basinc_sinifi": "Basınç sınıfı",
        "kaplama": "Kaplama", "malzeme": "Malzeme",
    }
    for key, value in features.items():
        lines.append(f"{feature_labels.get(str(key), str(key))}: {value}")

    delivery_place = _get(listing, "delivery_place")
    if delivery_place:
        lines.append(f"Teslim yeri: {delivery_place}")
    delivery_days = _get(listing, "delivery_days")
    if delivery_days is not None:
        lines.append(f"Teslim süresi: {delivery_days} gün")

    lines.append("")
    lines.append("Tekliflerde belirtilmesi rica olunur:")
    for item in (
        "Birim fiyat ve para birimi",
        "KDV durumu (dahil/hariç)",
        "Teslim süresi",
        "Nakliye durumu (dahil/hariç)",
        "Ödeme şartları",
    ):
        lines.append(f"- {item}")

    missing = _missing_labels(listing)
    if _get(listing, "needs_clarification"):
        missing.append("Teknik özellikler (tedarikçi önerisi bekleniyor)")
    if missing:
        lines.append("")
        lines.append("Netleştirilecek bilgiler:")
        for item in missing:
            lines.append(f"- {item}")
    return "\n".join(lines).strip() + "\n"


def render_offer_document(offer: Any, listing: Any = None) -> str:
    """Teklifi fiyat tablosu + şartlar içeren metne çevirir."""
    product = _get(listing, "product") if listing is not None else None
    if not product and _get(offer, "lines"):
        first = _get(offer, "lines")[0]
        product = _get(first, "product")
    subject = f"{product} — Teklif" if product else "Teklif"
    lines: list[str] = [f"Konu: {subject}", "", "Fiyat tablosu:"]

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
        lines.append("- (kalem belirtilmemiştir)")

    shipping_included = _get(offer, "shipping_included")
    shipping_cost = _get(offer, "shipping_cost")
    if total is not None and shipping_included is False and shipping_cost is not None:
        total += shipping_cost if isinstance(shipping_cost, Decimal) else Decimal(str(shipping_cost))
    if total is not None:
        lines.append(f"Toplam: {_fmt_decimal(total)} {currency or ''}".strip())

    lines.append("")
    lines.append("Şartlar:")
    tax_included = _get(offer, "tax_included")
    if tax_included is True:
        lines.append("- KDV: dahil")
    elif tax_included is False:
        lines.append("- KDV: hariç")
    if shipping_included is True:
        lines.append("- Nakliye: dahil")
    elif shipping_included is False:
        if shipping_cost is not None:
            lines.append(f"- Nakliye: hariç ({_fmt_decimal(shipping_cost)} {currency or ''})".strip())
        else:
            lines.append("- Nakliye: hariç")
    delivery_days = _get(offer, "delivery_days")
    if delivery_days is not None:
        lines.append(f"- Teslim süresi: {delivery_days} gün")
    payment_terms = _get(offer, "payment_terms")
    if payment_terms:
        lines.append(f"- Ödeme: {payment_terms}")
    if _get(offer, "conditional"):
        lines.append("- Bu teklif şartlıdır.")
    note = _get(offer, "note")
    if note:
        lines.append(f"- Not: {note}")
    if len(lines) == 0 or lines[-1] == "Şartlar:":
        lines.append("- (şart belirtilmemiştir)")

    missing = _missing_labels(offer)
    if missing:
        lines.append("")
        lines.append("Netleştirilecek bilgiler:")
        for item in missing:
            lines.append(f"- {item}")
    return "\n".join(lines).strip() + "\n"


# Takma adlar.
generate_listing_document = render_listing_document
generate_offer_document = render_offer_document
listing_document = render_listing_document
offer_document = render_offer_document
