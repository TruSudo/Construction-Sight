import pytest
from pydantic import ValidationError

from constructionsight.document_models import DocumentRecord
from constructionsight.provenance import Provenance


def test_document_model_accepts_minimum_required_fields() -> None:
    document = DocumentRecord(
        document_key="document:test:001",
        source_name="Synthetic Public Source",
    )

    assert document.document_key == "document:test:001"
    assert document.source_name == "Synthetic Public Source"
    assert document.has_text is False
    assert document.has_url is False


def test_document_model_detects_url_and_text() -> None:
    document = DocumentRecord(
        document_key="document:test:with-content",
        source_name="Synthetic Public Source",
        url="https://example.gov/document.pdf",
        text_extract="Synthetic staff report text.",
    )

    assert document.has_url is True
    assert document.has_text is True


def test_document_model_requires_source_name() -> None:
    with pytest.raises(ValidationError):
        DocumentRecord(
            document_key="document:test:missing-source",
            source_name="",
        )


def test_document_model_preserves_provenance() -> None:
    provenance = Provenance(
        source_name="Synthetic Public Source",
        confidence_score=90,
        verified=True,
    )
    document = DocumentRecord(
        document_key="document:test:provenance",
        source_name="Synthetic Public Source",
        provenance=[provenance],
    )

    assert document.provenance[0].band.value == "verified"
