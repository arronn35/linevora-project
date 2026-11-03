"""Deterministic, rule-based English extraction.

Works without a model. Only information explicitly written in the text is
extracted; an unspecified price, technical detail or payment field stays
``None`` and comes back as a question — the system never invents values.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any

from .models import ListingItem, OfferLine, to_decimal

_NUMBER_WORDS = {
    "one": 1, "two": 2, "three": 3, "four": 4,
    "five": 5, "six": 6, "seven": 7,
    "eight": 8, "nine": 9, "ten": 10, "eleven": 11, "twelve": 12,
    "fifteen": 15, "twenty": 20, "thirty": 30, "hundred": 100,
}

_CITIES = [
    "Istanbul", "Ankara", "Izmir", "Bursa", "Antalya", "Adana", "Konya",
    "Gaziantep", "Kayseri", "Mersin", "Eskisehir", "Samsun", "Trabzon",
    "Diyarbakir", "Sanliurfa", "Van", "Denizli", "Sakarya", "Kocaeli",
    "Tekirdag", "Balikesir", "Kahramanmaras", "Erzurum", "Elazig",
    "Mugla", "Aydin", "Hatay", "Manisa", "Canakkale", "Edirne",
]

_UNITS = [
    "pcs", "pc", "pieces", "piece", "kg", "kilogram", "ton", "meter", "metre", "mt", "m", "liter", "litre", "lt",
    "box", "package", "pallet", "m2", "m3", "set", "pair", "roll", "drum", "bag",
]

_KNOWN_PRODUCTS = [
    "galvanized pipe", "steel pipe", "stainless pipe",
    "gate valve", "ball valve",
    "centrifugal pump", "submersible pump",
    "check valve", "pipe", "valve", "pump", "cable", "profile",
    "sheet", "cement", "iron", "screw", "bolt",
    "nut", "flange", "elbow", "faucet", "tap",
    "generator", "transformer", "motor", "bearing", "paint",
]

_CATEGORY = {
    "pipe": "pipe", "valve": "valve", "check valve": "valve",
    "pump": "pump", "cable": "electrical", "flange": "fitting",
    "elbow": "fitting",
}

_STOP_TOKENS = {
    "looking", "for", "want", "need", "selling",
    "sale", "wanted", "required", "delivery", "within", "please",
    "price", "offer", "and", "with", "the", "a", "an", "to", "in",
}

_CLARIFY_PHRASES = (
    "i don't know", "i do not know", "no idea", "supplier suggestion",
    "open to suggestions", "you suggest", "expert suggestion",
    "supplier's suggestion",
)


def en_lower(text: str) -> str:
    return text.lower()


def _needs_clarification(lowered: str) -> bool:
    return any(phrase in lowered for phrase in _CLARIFY_PHRASES)


def _parse_number(raw: str) -> Decimal:
    raw = raw.strip()
    if "." in raw and "," in raw:
        raw = raw.replace(",", "")
    elif "," in raw:
        if re.fullmatch(r"\d{1,3}(,\d{3})+", raw):
            raw = raw.replace(",", "")
        else:
            raw = raw.replace(",", ".")
    return Decimal(raw)


def _quantity_unit(lowered: str, require_unit: bool = False) -> tuple[Decimal | None, str | None]:
    units = "|".join(re.escape(u) for u in sorted(_UNITS, key=len, reverse=True))
    m = re.search(rf"(\d+(?:[.,]\d+)?)\s*({units})\b", lowered)
    if m:
        return _parse_number(m.group(1)), m.group(2)
    # Quantity in words: "hundred pcs", "ten pcs" (simple forms).
    m = re.search(rf"\b({'|'.join(_NUMBER_WORDS)})\s*({units})\b", lowered)
    if m:
        return Decimal(_NUMBER_WORDS[m.group(1)]), m.group(2)
    if require_unit:
        return None, None
    m = re.search(r"(\d+(?:[.,]\d+)?)\b", lowered)
    if m:
        return _parse_number(m.group(1)), None
    return None, None


def _delivery_days(lowered: str) -> int | None:
    m = re.search(r"(\d+)\s*days?\b", lowered)
    if m:
        return int(m.group(1))
    m = re.search(r"(\d+)\s*weeks?\b", lowered)
    if m:
        return int(m.group(1)) * 7
    words = "|".join(re.escape(w) for w in sorted(_NUMBER_WORDS, key=len, reverse=True))
    m = re.search(rf"\b({words})\s*weeks?\b", lowered)
    if m:
        return _NUMBER_WORDS[m.group(1)] * 7
    m = re.search(rf"\b({words})\s*days?\b", lowered)
    if m:
        return _NUMBER_WORDS[m.group(1)]
    # "within two weeks" style is covered by the word-week rule above.
    m = re.search(r"within\s+(\d+)\s*days?\b", lowered)
    if m:
        return int(m.group(1))
    return None


def _delivery_place(lowered: str) -> str | None:
    for city in _CITIES:
        needle = en_lower(city)
        # A word boundary is required: "van" inside another word is not a city.
        if re.search(rf"(?<![a-z]){re.escape(needle)}(?![a-z])", lowered):
            return city
    return None


def _features(lowered: str) -> dict[str, Any]:
    feats: dict[str, Any] = {}
    m = re.search(r"\bdn\s*(\d+)\b", lowered)
    if m:
        feats["dn"] = m.group(1)
    m = re.search(r"(?:diameter|ø)\s*(?:of\s*)?(\d+(?:[.,]\d+)?)\s*(mm|cm)?", lowered)
    if m:
        feats["diameter_mm"] = m.group(1).replace(",", ".")
    m = re.search(r"wall\s*thickness\s*(\d+(?:[.,]\d+)?)\s*mm", lowered)
    if m:
        feats["wall_thickness_mm"] = m.group(1).replace(",", ".")
    m = re.search(r"length\s*(\d+(?:[.,]\d+)?)\s*(meter|metre|m|mm)\b", lowered)
    if m:
        feats["length"] = f"{m.group(1).replace(',', '.')} {m.group(2)}"
    m = re.search(r"\bpn\s*(\d+)\b", lowered)
    if m:
        feats["pressure_class"] = f"PN{m.group(1)}"
    if "galvanized" in lowered:
        feats["coating"] = "galvanized"
    elif "stainless" in lowered:
        feats["material"] = "stainless"
    return feats


def _product(lowered: str) -> str | None:
    best: tuple[int, str] | None = None
    for cand in _KNOWN_PRODUCTS:
        cl = en_lower(cand)
        idx = lowered.find(cl)
        if idx >= 0 and (best is None or len(cand) > len(best[1])):
            # Preserve the original slice from the text.
            orig = lowered[idx: idx + len(cl)].strip()
            best = (idx, orig)
    if best is not None:
        return best[1]
    # When no known product matches, take the phrase after the quantity.
    units = "|".join(re.escape(u) for u in sorted(_UNITS, key=len, reverse=True))
    m = re.search(rf"(?:\d+(?:[.,]\d+)?\s*(?:{units})\b\s+)(.+)", lowered)
    source = m.group(1) if m else lowered
    tokens = [
        t.strip(".,;:!?")
        for t in re.split(r"\s+", source)
        if t.strip(".,;:!?") and t.strip(".,;:!?") not in _STOP_TOKENS
        and not re.fullmatch(r"\d+(?:[.,]\d+)?", t.strip(".,;:!?"))
    ]
    tokens = [t for t in tokens if en_lower(t) not in _STOP_TOKENS]
    return " ".join(tokens[:4]) or None


@dataclass
class MissingQuestion:
    field: str
    question: str

    def to_dict(self) -> dict[str, str]:
        return {"field": self.field, "question": self.question}


@dataclass
class ParsedListing:
    kind: str
    raw_text: str
    title: str = ""
    product: str | None = None
    quantity: Decimal | None = None
    unit: str | None = None
    delivery_place: str | None = None
    delivery_days: int | None = None
    category: str | None = None
    features: dict[str, Any] = field(default_factory=dict)
    items: list[ListingItem] = field(default_factory=list)
    missing_fields: list[str] = field(default_factory=list)
    missing_questions: list[MissingQuestion] = field(default_factory=list)
    needs_clarification: bool = False

    @property
    def fields(self) -> dict[str, Any]:
        return {
            "kind": self.kind, "title": self.title, "product": self.product,
            "quantity": self.quantity, "unit": self.unit,
            "delivery_place": self.delivery_place,
            "delivery_days": self.delivery_days, "category": self.category,
            "features": dict(self.features),
            "missing_fields": list(self.missing_fields),
            "needs_clarification": self.needs_clarification,
        }

    def to_dict(self) -> dict[str, Any]:
        data = self.fields
        data["quantity"] = str(self.quantity) if self.quantity is not None else None
        data["items"] = [
            {"product": i.product,
             "quantity": str(i.quantity) if i.quantity is not None else None,
             "unit": i.unit, "category": i.category,
             "features": dict(i.features)}
            for i in self.items
        ]
        data["missing_questions"] = [q.to_dict() for q in self.missing_questions]
        data["raw_text"] = self.raw_text
        return data


@dataclass
class ParsedOffer:
    raw_text: str
    quantity: Decimal | None = None
    unit: str | None = None
    unit_price: Decimal | None = None
    currency: str | None = None
    tax_included: bool | None = None
    shipping_included: bool | None = None
    shipping_cost: Decimal | None = None
    delivery_days: int | None = None
    payment_terms: str | None = None
    conditional: bool = False
    features: dict[str, Any] = field(default_factory=dict)
    lines: list[OfferLine] = field(default_factory=list)
    missing_fields: list[str] = field(default_factory=list)
    missing_questions: list[MissingQuestion] = field(default_factory=list)
    needs_clarification: bool = False

    @property
    def fields(self) -> dict[str, Any]:
        return {
            "quantity": self.quantity, "unit": self.unit,
            "unit_price": self.unit_price, "currency": self.currency,
            "tax_included": self.tax_included,
            "shipping_included": self.shipping_included,
            "shipping_cost": self.shipping_cost,
            "delivery_days": self.delivery_days,
            "payment_terms": self.payment_terms,
            "conditional": self.conditional,
            "features": dict(self.features),
            "missing_fields": list(self.missing_fields),
            "needs_clarification": self.needs_clarification,
        }

    def total(self) -> Decimal | None:
        if not self.lines:
            return None
        result: Decimal | None = None
        for line in self.lines:
            if line.line_total is not None:
                result = (result or Decimal("0")) + line.line_total
        if result is not None and self.shipping_included is False and self.shipping_cost is not None:
            result += self.shipping_cost
        return result

    def to_dict(self) -> dict[str, Any]:
        data = self.fields
        for key in ("quantity", "unit_price", "shipping_cost"):
            data[key] = str(data[key]) if data[key] is not None else None
        total = self.total()
        data["total"] = str(total) if total is not None else None
        data["missing_questions"] = [q.to_dict() for q in self.missing_questions]
        data["raw_text"] = self.raw_text
        return data


def parse_listing(text: str, kind: str = "demand") -> ParsedListing:
    """Extracts only the fields explicitly written in the listing text."""
    if kind not in ("demand", "supply"):
        raise ValueError(f"invalid listing kind: {kind!r}")
    raw = (text or "").strip()
    lowered = en_lower(raw)
    quantity, unit = _quantity_unit(lowered)
    product = _product(lowered)
    category = None
    if product:
        for key, cat in _CATEGORY.items():
            if key in en_lower(product):
                category = cat
                break
    features = _features(lowered)
    needs = _needs_clarification(lowered)
    delivery_place = _delivery_place(lowered)
    delivery_days = _delivery_days(lowered)

    questions: list[MissingQuestion] = []
    missing: list[str] = []

    def ask(field_name: str, question: str) -> None:
        missing.append(field_name)
        questions.append(MissingQuestion(field_name, question))

    if not product:
        ask("product", "What is the product?")
    if quantity is None:
        ask("quantity", "What is the quantity?")
    if not unit:
        ask("unit", "What is the unit? (pcs, kg, meter, etc.)")
    if not delivery_place:
        ask("delivery_place", "Where is the delivery place?")
    if delivery_days is None:
        ask("delivery_days", "How many days is the delivery time?")
    # Technical questions for pipe; if the user said "I don't know /
    # supplier suggestion" the question is closed and no value is invented.
    if product and "pipe" in en_lower(product) and not needs:
        if "diameter_mm" not in features and "dn" not in features:
            ask("diameter", "What is the pipe diameter? If you don't know, you can write 'supplier suggestion'.")
        if "length" not in features:
            ask("length", "What is the pipe length? If you don't know, you can write 'supplier suggestion'.")
        if "wall_thickness_mm" not in features:
            ask("wall_thickness", "What is the pipe wall thickness? If you don't know, you can write 'supplier suggestion'.")

    title_parts = [
        str(quantity) if quantity is not None else "", unit or "", product or "",
    ]
    title = " ".join(p for p in title_parts if p).strip()
    items = (
        [ListingItem(product=product, quantity=quantity, unit=unit,
                     category=category, features=dict(features))]
        if (product or quantity is not None) else []
    )
    return ParsedListing(
        kind=kind, raw_text=raw, title=title, product=product,
        quantity=quantity, unit=unit, delivery_place=delivery_place,
        delivery_days=delivery_days, category=category, features=features,
        items=items, missing_fields=missing, missing_questions=questions,
        needs_clarification=needs,
    )


_CURRENCY_PATTERNS = [
    (re.compile(r"(\d+(?:[.,]\d+)?)\s*(?:usd|\$|dollar)\b", re.I), "USD"),
    (re.compile(r"\$\s*(\d+(?:[.,]\d+)?)"), "USD"),
    (re.compile(r"(\d+(?:[.,]\d+)?)\s*(?:eur|€|euro)\b", re.I), "EUR"),
    (re.compile(r"€\s*(\d+(?:[.,]\d+)?)"), "EUR"),
    (re.compile(r"(\d+(?:[.,]\d+)?)\s*(?:try|₺|lira)\b", re.I), "TRY"),
    (re.compile(r"₺\s*(\d+(?:[.,]\d+)?)"), "TRY"),
    (re.compile(r"(\d+(?:[.,]\d+)?)\s*(?:gbp|£|pound)\b", re.I), "GBP"),
    (re.compile(r"£\s*(\d+(?:[.,]\d+)?)"), "GBP"),
]


def _price(lowered: str) -> tuple[Decimal | None, str | None]:
    for pattern, currency in _CURRENCY_PATTERNS:
        m = pattern.search(lowered)
        if m:
            return _parse_number(m.group(1)), currency
    return None, None


def parse_offer(text: str) -> ParsedOffer:
    """Extracts only the fields explicitly written in the offer text."""
    raw = (text or "").strip()
    lowered = en_lower(raw)
    quantity, unit = _quantity_unit(lowered, require_unit=True)
    unit_price, currency = _price(lowered)
    features = _features(lowered)
    needs = _needs_clarification(lowered)

    if "vat included" in lowered or "tax included" in lowered:
        tax_included: bool | None = True
    elif "vat excluded" in lowered or "tax excluded" in lowered or "+ vat" in lowered or "+vat" in lowered:
        tax_included = False
    else:
        tax_included = None

    shipping_cost: Decimal | None = None
    if "shipping included" in lowered or "freight included" in lowered or "delivery included" in lowered:
        shipping_included: bool | None = True
    elif "shipping excluded" in lowered or "shipping at buyer's expense" in lowered or "freight at buyer's expense" in lowered:
        shipping_included = False
        m = re.search(r"shipping[^0-9]{0,20}(\d+(?:[.,]\d+)?)\s*(?:usd|eur|try|gbp|\$|€|£)", lowered)
        if m:
            shipping_cost = _parse_number(m.group(1))
    else:
        shipping_included = None

    delivery_days = _delivery_days(lowered)

    payment_terms: str | None = None
    m = re.search(r"(%\s*\d+\s*upfront[^.,;]*)", lowered)
    if m:
        payment_terms = m.group(1).strip()
        rest = re.search(r"(remainder[^.,;]*(?:net|due|upfront)[^.,;]*)", lowered)
        if rest and rest.group(1) not in payment_terms:
            payment_terms = f"{payment_terms}, {rest.group(1).strip()}"
    else:
        m2 = re.search(r"(\d+\s*days?\s*(?:net|due)\w*|net\s*\d+|upfront|wire(?:\s*transfer)?|by\s+check|check)", lowered)
        if m2:
            payment_terms = m2.group(1).strip()

    conditional = any(w in lowered for w in ("conditional", "subject to stock", "while stocks last", "while stock lasts"))

    lines: list[OfferLine] = []
    if unit_price is not None or quantity is not None:
        lines = [OfferLine(quantity=quantity, unit=unit, unit_price=unit_price,
                           currency=currency, features=dict(features))]

    questions: list[MissingQuestion] = []
    missing: list[str] = []

    def ask(field_name: str, question: str) -> None:
        missing.append(field_name)
        questions.append(MissingQuestion(field_name, question))

    if unit_price is None:
        ask("unit_price", "What is the unit price?")
    if currency is None:
        ask("currency", "What is the currency? (USD, EUR, TRY, GBP)")
    if tax_included is None:
        ask("tax_included", "Is VAT included or excluded in the price?")
    if delivery_days is None:
        ask("delivery_days", "How many days is the delivery time?")
    if shipping_included is None:
        ask("shipping_included", "Is shipping included or excluded?")
    if payment_terms is None:
        ask("payment_terms", "What are the payment terms?")

    return ParsedOffer(
        raw_text=raw, quantity=quantity, unit=unit, unit_price=unit_price,
        currency=currency, tax_included=tax_included,
        shipping_included=shipping_included, shipping_cost=shipping_cost,
        delivery_days=delivery_days, payment_terms=payment_terms,
        conditional=conditional, features=features, lines=lines,
        missing_fields=missing, missing_questions=questions,
        needs_clarification=needs,
    )
