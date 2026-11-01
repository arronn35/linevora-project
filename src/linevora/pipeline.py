"""Belge işleme hattı servisi (main.py'den ayrıştırıldı).

Sürüm işleme: gereksinim çıkarma → eşleştirme → alternatif → eksik.
Atomik değişim: tüm sonuçlar önce hesaplanır, tek noktada eskiyle
değiştirilir; hata hâlinde önceki sonuçlar korunur (P1.2).
"""

from __future__ import annotations

from typing import Any, Callable

from .matching.extractor import extract_requirements
from .matching.models import Requirement
from .model.client import MeteringClient, ModelClient
from .reports.alternatives import build_alternatives
from .reports.rules import find_gaps


class ProcessVersionService:
    def __init__(
        self,
        *,
        inquiry_store: Any,
        requirement_store: Any,
        suggestion_store: Any,
        alternative_store: Any,
        gap_store: Any,
        catalog_store: Any,
        matcher: Any,
        get_model_client: Callable[[], ModelClient],
        set_model_client: Callable[[ModelClient], None],
    ) -> None:
        self._inquiries = inquiry_store
        self._requirements = requirement_store
        self._suggestions = suggestion_store
        self._alternatives = alternative_store
        self._gaps = gap_store
        self._catalog = catalog_store
        self._matcher = matcher
        self._get_client = get_model_client
        self._set_client = set_model_client

    def __call__(self, payload: dict) -> dict[str, int]:
        inquiry_id = payload["inquiry_id"]
        version_no = payload["version_no"]
        versions = self._inquiries.list_versions(inquiry_id)
        version = next((v for v in versions if v.version_no == version_no), None)
        if version is None:
            raise ValueError("sürüm yok")
        client = self._get_client()
        if not isinstance(client, MeteringClient):
            client = MeteringClient(client)
            self._set_client(client)
        drafts = extract_requirements(client, version.pages)
        products = self._catalog.list()
        planned = []
        for draft in drafts:
            temp = Requirement(
                id="planned",
                version_id=version.id,
                product_type=draft["product_type"],
                features=draft.get("features") or {},
                quantity=draft.get("quantity"),
                unit=draft.get("unit"),
                page=draft["source"]["page"],
                quote=draft["source"]["quote"],
            )
            scored = self._matcher.suggest(temp, products)
            planned.append(
                (draft, scored, build_alternatives(temp, scored), find_gaps(temp))
            )
        removed = self._requirements.delete_for_version(version.id)
        self._suggestions.delete_for_requirements(removed)
        self._alternatives.delete_for_requirements(removed)
        self._gaps.delete_for_version(version.id)
        counts = {"requirements": 0, "suggestions": 0, "gaps": 0, "alternatives": 0}
        for draft, scored, alternatives, gaps in planned:
            requirement = self._requirements.add(
                version_id=version.id,
                product_type=draft["product_type"],
                features=draft.get("features") or {},
                quantity=draft.get("quantity"),
                unit=draft.get("unit"),
                page=draft["source"]["page"],
                quote=draft["source"]["quote"],
            )
            counts["requirements"] += 1
            for item in scored:
                self._suggestions.add(
                    requirement_id=requirement.id,
                    product_id=item.product.id,
                    score=item.score,
                    reasons=list(item.reasons),
                    page=requirement.page,
                    quote=requirement.quote,
                )
                counts["suggestions"] += 1
            for alternative in alternatives:
                self._alternatives.add(
                    requirement_id=requirement.id,
                    product_id=alternative.product_id,
                    score=alternative.score,
                    comparison=list(alternative.comparison),
                    reasons=alternative.reasons,
                )
                counts["alternatives"] += 1
            for gap in gaps:
                self._gaps.add(
                    version_id=version.id,
                    requirement_id=requirement.id,
                    field=gap.field,
                    question=gap.question,
                    severity=gap.severity,
                )
                counts["gaps"] += 1
        return counts
