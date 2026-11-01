"""Gereksinim çıkarma ve katalog eşleştirme."""

from .extractor import extract_requirements
from .matcher import LexicalMatcher, ScoredProduct
from .models import MatchSuggestion, Requirement
from .store import (
    InMemoryRequirementStore,
    InMemorySuggestionStore,
    RequirementStore,
    SuggestionStore,
)

__all__ = [
    "InMemoryRequirementStore",
    "InMemorySuggestionStore",
    "LexicalMatcher",
    "MatchSuggestion",
    "Requirement",
    "RequirementStore",
    "ScoredProduct",
    "SuggestionStore",
    "extract_requirements",
]
