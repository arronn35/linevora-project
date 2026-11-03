"""Model abstraction: fake client, metering, schema validation."""

import pytest

from linevora.model import (
    REQUIREMENTS_SCHEMA,
    FakeModelClient,
    MeteringClient,
    ModelError,
    SchemaValidationError,
    parse_and_validate,
)

GOOD = (
    '{"requirements": [{"product_type": "pump", '
    '"quantity": 10, "source": {"page": 2, "quote": "10 pcs pump"}}]}'
)


def test_fake_client_roundtrip():
    client = FakeModelClient(responses={"hello": "hi"})
    assert client.complete("system", "hello") == "hi"
    with pytest.raises(ModelError):
        client.complete("system", "unknown")


def test_metering_records_calls():
    inner = FakeModelClient(responses={"a": "b"})
    client = MeteringClient(inner)
    assert client.complete("s", "a") == "b"
    with pytest.raises(ModelError):
        client.complete("s", "missing")
    assert [call.ok for call in client.calls] == [True, False]
    assert client.calls[0].model == "fake"
    assert client.calls[0].prompt_chars == 2


def test_schema_accepts_valid():
    parsed = parse_and_validate(GOOD, REQUIREMENTS_SCHEMA)
    assert parsed["requirements"][0]["product_type"] == "pump"


def test_schema_rejects_missing_source():
    bad = '{"requirements": [{"product_type": "pump"}]}'
    with pytest.raises(SchemaValidationError):
        parse_and_validate(bad, REQUIREMENTS_SCHEMA)


def test_schema_rejects_bad_json():
    with pytest.raises(SchemaValidationError):
        parse_and_validate("{broken", REQUIREMENTS_SCHEMA)
