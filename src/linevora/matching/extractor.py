"""Model çıktısından gereksinim çıkarma (şema doğrulamalı)."""

from __future__ import annotations

from typing import Any

from ..ingest.extract import Page
from ..model.client import ModelClient
from ..model.schemas import REQUIREMENTS_SCHEMA, SchemaValidationError, parse_and_validate

SYSTEM_PROMPT = (
    "Endüstriyel talep metninden ürün gereksinimlerini çıkar. "
    "Yalnızca JSON döndür: "
    '{"requirements": [{"product_type": "...", "features": {...}, '
    '"quantity": ..., "unit": "...", "source": {"page": ..., "quote": "..."}}]}. '
    "Her gereksinime, dayandığı sayfayı ve birebir alıntıyı kaynak olarak yaz."
)


def _user_prompt(pages: tuple[Page, ...]) -> str:
    return "\n\n".join(f"Sayfa {page.number}:\n{page.text}" for page in pages)


def _normalize(text: str) -> str:
    return " ".join(str(text).casefold().split())


def quote_in_page(quote: str, page_text: str) -> bool:
    """Alıntı, sayfa metninde normalize alt-dize olarak var mı?"""
    return bool(_normalize(quote)) and _normalize(quote) in _normalize(page_text)


_UNIT_ALIASES = {
    "ad": "adet",
    "adet": "adet",
    "pcs": "adet",
    "m": "metre",
    "metre": "metre",
    "mt": "metre",
    "lt": "litre",
    "litre": "litre",
    "l": "litre",
}


def _normalize_draft(draft: dict[str, Any]) -> dict[str, Any]:
    unit = draft.get("unit")
    if isinstance(unit, str):
        draft["unit"] = _UNIT_ALIASES.get(unit.strip().casefold(), unit.strip())
    quantity = draft.get("quantity")
    if isinstance(quantity, float) and quantity.is_integer():
        draft["quantity"] = int(quantity)
    features = draft.get("features")
    if isinstance(features, dict):
        draft["features"] = {
            str(key).strip(): (str(value).strip() if isinstance(value, str) else value)
            for key, value in features.items()
        }
    return draft


def extract_requirements(
    client: ModelClient, pages: tuple[Page, ...]
) -> list[dict[str, Any]]:
    # Uzun belgeler 5 sayfalık parçalarla çağrılır, sonuçlar birleştirilir.
    if len(pages) > 5:
        merged: list[dict[str, Any]] = []
        for start in range(0, len(pages), 5):
            merged.extend(extract_requirements(client, pages[start : start + 5]))
        return merged
    raw = client.complete(SYSTEM_PROMPT, _user_prompt(pages))
    parsed = parse_and_validate(raw, REQUIREMENTS_SCHEMA)
    by_number = {page.number: page for page in pages}
    for draft in parsed["requirements"]:
        page_no = draft["source"]["page"]
        page = by_number.get(page_no)
        if page is None:
            raise SchemaValidationError(f"kaynak sayfa aralık dışı: {page_no}")
        # Değişmez-1: uydurma alıntı şemayı geçemez.
        if not quote_in_page(draft["source"]["quote"], page.text):
            raise SchemaValidationError(
                f"kaynak alıntı sayfa metninde bulunamadı (sayfa {page_no})"
            )
        quantity = draft.get("quantity")
        if quantity is not None and (
            not isinstance(quantity, (int, float)) or quantity != quantity or quantity <= 0
        ):
            raise SchemaValidationError(f"geçersiz miktar: {quantity!r}")
        _normalize_draft(draft)
    return parsed["requirements"]
