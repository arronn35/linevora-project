"""Model çıktılarının şema doğrulaması.

Kural: şemaya uymayan yanıt iş hattına girmez. Kaynak işaretçisi
(page + quote) her gereksinimde zorunludur (değişmez kural 1).
"""

from __future__ import annotations

import json
from typing import Any

import jsonschema

REQUIREMENTS_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "requirements": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "product_type": {"type": "string", "minLength": 1},
                    "features": {"type": "object"},
                    "quantity": {"type": "number"},
                    "unit": {"type": "string"},
                    "source": {
                        "type": "object",
                        "properties": {
                            "page": {"type": "integer", "minimum": 1},
                            "quote": {"type": "string", "minLength": 1},
                        },
                        "required": ["page", "quote"],
                        "additionalProperties": False,
                    },
                },
                "required": ["product_type", "source"],
                "additionalProperties": False,
            },
        }
    },
    "required": ["requirements"],
    "additionalProperties": False,
}


class SchemaValidationError(Exception):
    """Model yanıtı ayrıştırılamadı ya da şemaya uymadı."""


def parse_and_validate(raw: str, schema: dict[str, Any]) -> dict[str, Any]:
    try:
        instance = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise SchemaValidationError(f"geçersiz JSON: {exc}")
    try:
        jsonschema.validate(instance, schema)
    except jsonschema.ValidationError as exc:
        raise SchemaValidationError(f"şema ihlali: {exc.message}")
    return instance
