"""Raporlar: eksik bilgi, sürüm farkı, alternatif önerileri."""

from .alternatives import build_alternatives
from .diff import diff_requirements
from .models import Alternative, ComparisonRow, InformationGap
from .rules import find_gaps
from .store import (
    AlternativeStore,
    GapStore,
    InMemoryAlternativeStore,
    InMemoryGapStore,
)

__all__ = [
    "Alternative",
    "AlternativeStore",
    "ComparisonRow",
    "InMemoryAlternativeStore",
    "InMemoryGapStore",
    "InformationGap",
    "GapStore",
    "build_alternatives",
    "diff_requirements",
    "find_gaps",
]
