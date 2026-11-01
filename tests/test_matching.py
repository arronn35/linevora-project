"""Sözlüksel eşleştirme ve gereksinim çıkarma."""

import json

import pytest

from linevora.catalog.store import InMemoryCatalogStore, seed_demo_catalog
from linevora.ingest.extract import Page
from linevora.matching.extractor import extract_requirements
from linevora.matching.matcher import LexicalMatcher
from linevora.matching.models import Requirement
from linevora.model import FakeModelClient, SchemaValidationError


def _catalog():
    store = InMemoryCatalogStore()
    seed_demo_catalog(store)
    return store


def _requirement(**overrides):
    fields = {
        "id": "r1",
        "version_id": "v1",
        "product_type": "sürgülü vana",
        "features": {"DN": "80", "basinc_sinifi": "PN16"},
        "quantity": 4,
        "unit": "adet",
        "page": 1,
        "quote": "4 adet DN80 sürgülü vana",
    }
    fields.update(overrides)
    return Requirement(**fields)


def test_top_match_is_exact_product():
    scored = LexicalMatcher().suggest(_requirement(), _catalog().list())
    assert scored[0].product.code == "V-001"
    assert scored[0].score > 0.7
    assert any("sürgülü vana" in reason.lower() for reason in scored[0].reasons)


def test_unrelated_products_score_low():
    requirement = _requirement(
        product_type="santrifüj pompa", features={"DN": "50"}, quantity=10
    )
    scored = LexicalMatcher().suggest(requirement, _catalog().list())
    by_code = {item.product.code: item.score for item in scored}
    assert by_code["P-001"] > 0.7
    assert all(score < 0.5 for code, score in by_code.items() if code != "P-001")


def test_top_k_limits_results():
    scored = LexicalMatcher(top_k=1).suggest(_requirement(), _catalog().list())
    assert [item.product.code for item in scored] == ["V-001"]


def test_extractor_parses_and_validates():
    pages = (Page(number=1, text="DN50 pompa 10 adet"),)
    raw = json.dumps(
        {
            "requirements": [
                {
                    "product_type": "pompa",
                    "quantity": 10,
                    "source": {"page": 1, "quote": "DN50 pompa"},
                }
            ]
        }
    )
    client = FakeModelClient(responses={"Sayfa 1:\nDN50 pompa 10 adet": raw})
    drafts = extract_requirements(client, pages)
    assert drafts[0]["product_type"] == "pompa"


def test_extractor_rejects_out_of_range_page():
    pages = (Page(number=1, text="bir şey"),)
    raw = json.dumps(
        {
            "requirements": [
                {"product_type": "x", "source": {"page": 5, "quote": "yok"}}
            ]
        }
    )
    client = FakeModelClient(responses={"Sayfa 1:\nbir şey": raw})
    with pytest.raises(SchemaValidationError):
        extract_requirements(client, pages)


def test_extractor_rejects_missing_source():
    pages = (Page(number=1, text="bir şey"),)
    client = FakeModelClient(
        responses={"Sayfa 1:\nbir şey": '{"requirements": [{"product_type": "x"}]}'}
    )
    with pytest.raises(SchemaValidationError):
        extract_requirements(client, pages)
