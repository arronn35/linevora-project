"""Missing-information rules: mandatory-field checks and question generation."""

from __future__ import annotations

from dataclasses import dataclass

from ..matching.models import Requirement


@dataclass(frozen=True)
class GapDraft:
    field: str
    question: str
    severity: str


def find_gaps(requirement: Requirement) -> list[GapDraft]:
    """Finds the gaps in a requirement rule-by-rule (no hard-coded thresholds)."""
    gaps: list[GapDraft] = []
    if requirement.quantity is None:
        gaps.append(
            GapDraft(
                field="quantity",
                question=(
                    f"No quantity specified for '{requirement.product_type}'. "
                    "How many are needed?"
                ),
                severity="mandatory",
            )
        )
    if not requirement.unit:
        gaps.append(
            GapDraft(
                field="unit",
                question=(
                    f"No unit specified for '{requirement.product_type}'. "
                    "In what unit is the quantity expressed?"
                ),
                severity="mandatory",
            )
        )
    if not requirement.features:
        gaps.append(
            GapDraft(
                field="features",
                question=(
                    f"No feature detail for '{requirement.product_type}'. "
                    "Can the technical specifications be clarified?"
                ),
                severity="info",
            )
        )
    return gaps
