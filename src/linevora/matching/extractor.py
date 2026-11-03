"""Extracting requirements from model output (schema-validated)."""

from __future__ import annotations

from typing import Any

from ..ingest.extract import Page
from ..model.client import ModelClient
from ..model.schemas import REQUIREMENTS_SCHEMA, SchemaValidationError, parse_and_validate

SYSTEM_PROMPT = (
     "Extract product requirements from the industrial inquiry text. "
    "Return only JSON: "
    '{"requirements": [{"product_type": "...", "features": {...}, '
    '"quantity": ..., "unit": "...", "source": {"page": ..., "quote": "..."}}]}. '
    "For each requirement, give the page it relies on and the verbatim quote as the source."
)


def _user_prompt(pages: tuple[Page, ...]) -> str:
    return "\n\n".join(f"Page {page.number}:\n{page.text}" for page in pages)


def _normalize(text: str) -> str:
    return " ".join(str(text).casefold().split())


def quote_in_page(quote: str, page_text: str) -> bool:
    """Is the quote present in the page text as a normalized substring?"""
    return bool(_normalize(quote)) and _normalize(quote) in _normalize(page_text)


_UNIT_ALIASES = {
    "pc": "pcs",
    "piece": "pcs",
    "pieces": "pcs",
    "pcs": "pcs",
    "ea": "pcs",
    "m": "meter",
    "meter": "meter",
    "meters": "meter",
    "metre": "meter",
    "metres": "meter",
    "mt": "meter",
    "lt": "liter",
    "liter": "liter",
    "liters": "liter",
    "litre": "liter",
    "litres": "liter",
    "l": "liter",
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
    # Long documents are called in 5-page chunks and the results are merged.
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
            raise SchemaValidationError(f"source page out of range: {page_no}")
        # Invariant: an invented quote cannot pass the schema.
        if not quote_in_page(draft["source"]["quote"], page.text):
            raise SchemaValidationError(
                f"source quote not found in the page text (page {page_no})"
            )
        quantity = draft.get("quantity")
        if quantity is not None and (
            not isinstance(quantity, (int, float)) or quantity != quantity or quantity <= 0
        ):
            raise SchemaValidationError(f"invalid quantity: {quantity!r}")
        _normalize_draft(draft)
    return parsed["requirements"]
