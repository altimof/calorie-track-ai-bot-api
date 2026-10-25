"""Tests for the shared UUID parsing helper."""

import uuid

import pytest

from calorie_track_ai_bot.utils.ids import parse_uuid

CANONICAL = "12345678-1234-5678-1234-567812345678"


@pytest.mark.parametrize(
    "value",
    [
        CANONICAL,
        CANONICAL.upper(),
        f"urn:uuid:{CANONICAL}",
        "{" + CANONICAL + "}",
        CANONICAL.replace("-", ""),
    ],
)
def test_accepted_forms_parse_to_canonical_uuid(value):
    parsed = parse_uuid(value)
    assert parsed == uuid.UUID(CANONICAL)
    assert str(parsed) == CANONICAL


@pytest.mark.parametrize("value", ["nonexistent", "", "1234", None, 123])
def test_invalid_values_return_none(value):
    assert parse_uuid(value) is None
