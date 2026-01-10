"""Unit tests for app.infrastructure.db.models.default utilities and base models."""

from datetime import UTC, datetime
from enum import Enum
from uuid import UUID

from app.infrastructure.db.models.default import (
    AuditableBase,
    UUIDBase,
    datetime_to_gmt_str,
    enum_values,
)


class SampleEnum(Enum):
    FOO = "foo"
    BAR = "bar"


def test_datetime_to_gmt_str_adds_timezone_when_naive():
    naive_dt = datetime(2025, 1, 1, 12, 0, 0)
    result = datetime_to_gmt_str(naive_dt)

    # Should include timezone offset and be ISO format
    assert result.startswith("2025-01-01T12:00:00")
    assert result.endswith("+00:00") or result.endswith("Z")


def test_datetime_to_gmt_str_preserves_timezone():
    aware_dt = datetime(2025, 1, 1, 12, 0, 0, tzinfo=UTC)
    result = datetime_to_gmt_str(aware_dt)

    assert result.startswith("2025-01-01T12:00:00")
    assert result.endswith("+00:00") or result.endswith("Z")


def test_enum_values_returns_values():
    values = enum_values(SampleEnum)
    assert values == ["foo", "bar"]


def test_uuid_base_default_id_generated():
    instance = UUIDBase()
    assert isinstance(instance.id, UUID)


def test_auditable_base_defaults():
    instance = AuditableBase()
    assert isinstance(instance.created_at, datetime)
    assert instance.created_at.tzinfo is not None
    assert isinstance(instance.updated_at, datetime)
    assert instance.deleted_at is None
