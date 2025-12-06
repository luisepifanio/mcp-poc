import pytest

from app.errors import AppError, ErrorCatalog, ErrorDetailBuilder


def test_error_detail_builder_success():
    builder = (
        ErrorDetailBuilder()
        .error(ErrorCatalog.NOT_FOUND)
        .detail("Missing resource")
        .metadata({"id": 1})
    )

    ed = builder.build()

    assert ed.error == ErrorCatalog.NOT_FOUND.value
    assert ed.detail == "Missing resource"
    assert ed.metadata == {"id": 1}


def test_error_detail_builder_missing_error_raises():
    builder = ErrorDetailBuilder().detail("no error set")
    with pytest.raises(ValueError):
        builder.build()


def test_apperror_as_error_detail():
    ex = AppError("boom", error=ErrorCatalog.VALIDATION_FAILED, metadata={"k": "v"})
    ed = ex.as_error_detail()
    assert ed.error == ErrorCatalog.VALIDATION_FAILED.value
    assert "boom" in ed.detail
    assert ed.metadata is not None
    assert "k" in ed.metadata
    assert ed.metadata["k"] == "v"
