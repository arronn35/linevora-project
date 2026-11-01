"""Eksik bilgi kuralları: zorunlu alan denetimi ve soru üretimi."""

from __future__ import annotations

from dataclasses import dataclass

from ..matching.models import Requirement


@dataclass(frozen=True)
class GapDraft:
    field: str
    question: str
    severity: str


def find_gaps(requirement: Requirement) -> list[GapDraft]:
    """Gereksinimdeki eksikleri kural tabanlı bulur (kodda sabit eşikler yok)."""
    gaps: list[GapDraft] = []
    if requirement.quantity is None:
        gaps.append(
            GapDraft(
                field="quantity",
                question=(
                    f"'{requirement.product_type}' için miktar belirtilmemiş. "
                    "Kaç adet gerekiyor?"
                ),
                severity="zorunlu",
            )
        )
    if not requirement.unit:
        gaps.append(
            GapDraft(
                field="unit",
                question=(
                    f"'{requirement.product_type}' için birim belirtilmemiş. "
                    "Miktar hangi birimle ifade ediliyor?"
                ),
                severity="zorunlu",
            )
        )
    if not requirement.features:
        gaps.append(
            GapDraft(
                field="features",
                question=(
                    f"'{requirement.product_type}' için özellik detayı yok. "
                    "Teknik özellikler netleştirilebilir mi?"
                ),
                severity="bilgi",
            )
        )
    return gaps
