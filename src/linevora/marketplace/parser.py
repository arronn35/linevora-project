"""Deterministik, kural tabanlı Türkçe çıkarım.

Model olmadan da çalışır. Yalnızca metinde açıkça yazan bilgi çıkarılır;
belirtilmemiş fiyat/teknik/ödeme alanı ``None`` kalır ve soru olarak
döner — sistem değer uydurmaz.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any

from .models import ListingItem, OfferLine, to_decimal

_NUMBER_WORDS = {
    "bir": 1, "iki": 2, "üç": 3, "uc": 3, "dört": 4, "dort": 4,
    "beş": 5, "bes": 5, "altı": 6, "alti": 6, "yedi": 7,
    "sekiz": 8, "dokuz": 9, "on": 10, "onbir": 11, "oniki": 12,
    "onbeş": 15, "onbes": 15, "yirmi": 20, "otuz": 30,
}

_CITIES = [
    "İstanbul", "Ankara", "İzmir", "Bursa", "Antalya", "Adana", "Konya",
    "Gaziantep", "Kayseri", "Mersin", "Eskişehir", "Samsun", "Trabzon",
    "Diyarbakır", "Şanlıurfa", "Van", "Denizli", "Sakarya", "Kocaeli",
    "Tekirdağ", "Balıkesir", "Kahramanmaraş", "Erzurum", "Elazığ",
    "Muğla", "Aydın", "Hatay", "Manisa", "Çanakkale", "Edirne",
]

_UNITS = [
    "adet", "kg", "kilogram", "ton", "metre", "mt", "m", "litre", "lt",
    "kutu", "paket", "palet", "m2", "m3", "set", "takım", "takim",
    "çift", "cift", "rulo", "bidon", "çuval", "cuval",
]

_KNOWN_PRODUCTS = [
    "galvaniz boru", "çelik boru", "celik boru", "paslanmaz boru",
    "sürgülü vana", "surgulu vana", "küresel vana", "kuresel vana",
    "santrifüj pompa", "santrifuj pompa", "dalgıç pompa", "dalgic pompa",
    "çekvalf", "cekvalf", "boru", "vana", "pompa", "kablo", "profil",
    "sac", "çimento", "cimento", "demir", "vida", "cıvata", "civata",
    "somun", "flanş", "flans", "dirsek", "musluk", "batarya",
    "jeneratör", "jenerator", "trafo", "motor", "rulman", "boya",
]

_CATEGORY = {
    "boru": "boru", "vana": "vana", "çekvalf": "vana", "cekvalf": "vana",
    "pompa": "pompa", "kablo": "elektrik", "flanş": "baglanti",
    "flans": "baglanti", "dirsek": "baglanti",
}

_STOP_TOKENS = {
    "arıyorum", "ariyorum", "istiyorum", "lazım", "lazim", "satıyorum",
    "satiyorum", "satılık", "satilik", "aranıyor", "araniyor",
    "gerekiyor", "gerekli", "teslim", "içinde", "icinde", "için", "icin",
    "fiyat", "teklif", "lütfen", "lutfen", "adet", "ve", "ile",
}

_CLARIFY_PHRASES = (
    "bilmiyorum", "bilgim yok", "tedarikçi önerisi", "tedarikci onerisi",
    "tedarikçinin önerisi", "tedarikcinin onerisi", "önerinize açığım",
    "onerinize acigim", "siz önerin", "siz onerin", "uzman önerisi",
)


def tr_lower(text: str) -> str:
    return text.replace("I", "ı").replace("İ", "i").lower()


def _strip_diacritics(text: str) -> str:
    return (
        text.replace("ç", "c").replace("ğ", "g").replace("ı", "i")
        .replace("ö", "o").replace("ş", "s").replace("ü", "u")
    )


def _needs_clarification(lowered: str) -> bool:
    plain = _strip_diacritics(lowered)
    return any(
        phrase in lowered or _strip_diacritics(phrase) in plain
        for phrase in _CLARIFY_PHRASES
    )


def _parse_tr_number(raw: str) -> Decimal:
    raw = raw.strip()
    if "." in raw and "," in raw:
        raw = raw.replace(".", "").replace(",", ".")
    elif "," in raw:
        raw = raw.replace(",", ".")
    return Decimal(raw)


def _quantity_unit(lowered: str, require_unit: bool = False) -> tuple[Decimal | None, str | None]:
    units = "|".join(re.escape(u) for u in sorted(_UNITS, key=len, reverse=True))
    m = re.search(rf"(\d+(?:[.,]\d+)?)\s*({units})\b", lowered)
    if m:
        return _parse_tr_number(m.group(1)), m.group(2)
    # Yazıyla miktar: "yüz adet", "on adet" (basit biçimler).
    m = re.search(rf"\b({'|'.join(_NUMBER_WORDS)})\s*({units})\b", lowered)
    if m:
        return Decimal(_NUMBER_WORDS[m.group(1)]), m.group(2)
    if require_unit:
        return None, None
    m = re.search(r"(\d+(?:[.,]\d+)?)\b", lowered)
    if m:
        return _parse_tr_number(m.group(1)), None
    return None, None


def _delivery_days(lowered: str) -> int | None:
    m = re.search(r"(\d+)\s*g(?:ü|u)n\b", lowered)
    if m:
        return int(m.group(1))
    m = re.search(r"(\d+)\s*hafta\b", lowered)
    if m:
        return int(m.group(1)) * 7
    words = "|".join(re.escape(w) for w in sorted(_NUMBER_WORDS, key=len, reverse=True))
    m = re.search(rf"\b({words})\s*hafta\b", lowered)
    if m:
        return _NUMBER_WORDS[m.group(1)] * 7
    m = re.search(rf"\b({words})\s*g(?:ü|u)n\b", lowered)
    if m:
        return _NUMBER_WORDS[m.group(1)]
    return None


def _delivery_place(lowered: str) -> str | None:
    plain = _strip_diacritics(lowered)
    for city in _CITIES:
        for hay, needle in ((lowered, tr_lower(city)), (plain, _strip_diacritics(tr_lower(city)))):
            # Kelime sınırı şart: "galvaniz" içindeki "van" şehir sayılmaz.
            if re.search(rf"(?<![a-zçğışöü]){re.escape(needle)}(?![a-zçğışöü])", hay):
                return city
    return None


def _features(lowered: str) -> dict[str, Any]:
    feats: dict[str, Any] = {}
    m = re.search(r"\bdn\s*(\d+)\b", lowered)
    if m:
        feats["dn"] = m.group(1)
    m = re.search(r"(?:çap[ıi]?|ø)\s*(\d+(?:[.,]\d+)?)\s*(mm|cm)?", lowered)
    if m:
        feats["cap_mm"] = m.group(1).replace(",", ".")
    m = re.search(r"et\s*kalınlığı\s*(\d+(?:[.,]\d+)?)\s*mm", lowered)
    if m:
        feats["et_kalinligi_mm"] = m.group(1).replace(",", ".")
    m = re.search(r"boy(?:u)?\s*(\d+(?:[.,]\d+)?)\s*(metre|m|mm)\b", lowered)
    if m:
        feats["boy"] = f"{m.group(1).replace(',', '.')} {m.group(2)}"
    m = re.search(r"\bpn\s*(\d+)\b", lowered)
    if m:
        feats["basinc_sinifi"] = f"PN{m.group(1)}"
    if "galvaniz" in lowered:
        feats["kaplama"] = "galvaniz"
    elif "paslanmaz" in lowered:
        feats["malzeme"] = "paslanmaz"
    return feats


def _product(lowered: str) -> str | None:
    plain = _strip_diacritics(lowered)
    best: tuple[int, str] | None = None
    for cand in _KNOWN_PRODUCTS:
        cl = tr_lower(cand)
        for hay, needle in ((lowered, cl), (plain, _strip_diacritics(cl))):
            idx = hay.find(needle)
            if idx >= 0 and (best is None or len(cand) > len(best[1])):
                # Metindeki özgün kesimi koru.
                orig = lowered[idx: idx + len(needle)].strip()
                best = (idx, orig)
                break
    if best is not None:
        return best[1]
    # Bilinen ürün yoksa miktar sonrasındaki ifadeyi al.
    units = "|".join(re.escape(u) for u in sorted(_UNITS, key=len, reverse=True))
    m = re.search(rf"(?:\d+(?:[.,]\d+)?\s*(?:{units})\b\s+)(.+)", lowered)
    source = m.group(1) if m else lowered
    tokens = [
        t.strip(".,;:!?")
        for t in re.split(r"\s+", source)
        if t.strip(".,;:!?") and t.strip(".,;:!?") not in _STOP_TOKENS
        and not re.fullmatch(r"\d+(?:[.,]\d+)?", t.strip(".,;:!?"))
    ]
    tokens = [t for t in tokens if tr_lower(t) not in _STOP_TOKENS]
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
    """İlan metninden yalnızca açıkça yazan alanları çıkarır."""
    if kind not in ("demand", "supply"):
        raise ValueError(f"geçersiz ilan türü: {kind!r}")
    raw = (text or "").strip()
    lowered = tr_lower(raw)
    quantity, unit = _quantity_unit(lowered)
    product = _product(lowered)
    category = None
    if product:
        for key, cat in _CATEGORY.items():
            if key in _strip_diacritics(tr_lower(product)):
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
        ask("product", "Ürün nedir?")
    if quantity is None:
        ask("quantity", "Miktar kaçtır?")
    if not unit:
        ask("unit", "Birim nedir? (adet, kg, metre vb.)")
    if not delivery_place:
        ask("delivery_place", "Teslim yeri neresidir?")
    if delivery_days is None:
        ask("delivery_days", "Teslim süresi kaç gündür?")
    # Boru için teknik sorular; kullanıcı "bilmiyorum / tedarikçi
    # önerisi" dediyse soru kapatılır, değer uydurulmaz.
    if product and "boru" in _strip_diacritics(tr_lower(product)) and not needs:
        if "cap_mm" not in features and "dn" not in features:
            ask("cap", "Borunun çapı nedir? Bilmiyorsanız 'tedarikçi önerisi' yazabilirsiniz.")
        if "boy" not in features:
            ask("boy", "Borunun boyu/uzunluğu nedir? Bilmiyorsanız 'tedarikçi önerisi' yazabilirsiniz.")
        if "et_kalinligi_mm" not in features:
            ask("et_kalinligi", "Borunun et kalınlığı nedir? Bilmiyorsanız 'tedarikçi önerisi' yazabilirsiniz.")

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
    (re.compile(r"(\d+(?:[.,]\d+)?)\s*(?:tl|try|₺)\b", re.I), "TRY"),
    (re.compile(r"₺\s*(\d+(?:[.,]\d+)?)"), "TRY"),
    (re.compile(r"(\d+(?:[.,]\d+)?)\s*(?:usd|\$|dolar)\b", re.I), "USD"),
    (re.compile(r"\$\s*(\d+(?:[.,]\d+)?)"), "USD"),
    (re.compile(r"(\d+(?:[.,]\d+)?)\s*(?:eur|€|euro|avro)\b", re.I), "EUR"),
    (re.compile(r"€\s*(\d+(?:[.,]\d+)?)"), "EUR"),
]


def _price(lowered: str) -> tuple[Decimal | None, str | None]:
    for pattern, currency in _CURRENCY_PATTERNS:
        m = pattern.search(lowered)
        if m:
            return _parse_tr_number(m.group(1)), currency
    return None, None


def parse_offer(text: str) -> ParsedOffer:
    """Teklif metninden yalnızca açıkça yazan alanları çıkarır."""
    raw = (text or "").strip()
    lowered = tr_lower(raw)
    quantity, unit = _quantity_unit(lowered, require_unit=True)
    unit_price, currency = _price(lowered)
    features = _features(lowered)
    needs = _needs_clarification(lowered)

    if "kdv dahil" in lowered or "kdv dâhil" in lowered:
        tax_included: bool | None = True
    elif "kdv hariç" in lowered or "kdv haric" in _strip_diacritics(lowered) or "+ kdv" in lowered or "+kdv" in lowered:
        tax_included = False
    else:
        tax_included = None

    shipping_cost: Decimal | None = None
    if "nakliye dahil" in lowered or "nakliye dâhil" in lowered or "kargo dahil" in lowered:
        shipping_included: bool | None = True
    elif "nakliye hariç" in lowered or "nakliye haric" in _strip_diacritics(lowered) or "nakliye alıcıya ait" in lowered or "kargo alıcıya ait" in lowered:
        shipping_included = False
        m = re.search(r"nakliye[^0-9]{0,20}(\d+(?:[.,]\d+)?)\s*(?:tl|try|₺)", lowered)
        if m:
            shipping_cost = _parse_tr_number(m.group(1))
    else:
        shipping_included = None

    delivery_days = _delivery_days(lowered)

    payment_terms: str | None = None
    m = re.search(r"(%\s*\d+\s*peşin[^.,;]*)", lowered)
    if m:
        payment_terms = m.group(1).strip()
        rest = re.search(r"(kalan[^.,;]*(?:vadeli|vade|peşin)[^.,;]*)", lowered)
        if rest and rest.group(1) not in payment_terms:
            payment_terms = f"{payment_terms}, {rest.group(1).strip()}"
    else:
        m2 = re.search(r"(\d+\s*gün\s*vade\w*|vadeli|peşin|havale(?:\s*ile)?|çekle|cekle)", lowered)
        if m2:
            payment_terms = m2.group(1).strip()

    conditional = any(w in lowered for w in ("şartlı", "sartli", "koşullu", "kosullu", "stokla sınırlı", "stokla sinirli"))

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
        ask("unit_price", "Birim fiyat nedir?")
    if currency is None:
        ask("currency", "Para birimi nedir? (TRY, USD, EUR)")
    if tax_included is None:
        ask("tax_included", "Fiyat KDV dahil mi, hariç mi?")
    if delivery_days is None:
        ask("delivery_days", "Teslim süresi kaç gündür?")
    if shipping_included is None:
        ask("shipping_included", "Nakliye dahil mi, hariç mi?")
    if payment_terms is None:
        ask("payment_terms", "Ödeme şartları nedir?")

    return ParsedOffer(
        raw_text=raw, quantity=quantity, unit=unit, unit_price=unit_price,
        currency=currency, tax_included=tax_included,
        shipping_included=shipping_included, shipping_cost=shipping_cost,
        delivery_days=delivery_days, payment_terms=payment_terms,
        conditional=conditional, features=features, lines=lines,
        missing_fields=missing, missing_questions=questions,
        needs_clarification=needs,
    )
