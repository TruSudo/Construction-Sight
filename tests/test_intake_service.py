import json
import zipfile
from io import BytesIO
from pathlib import Path

from constructionsight.intake_models import DigitalFormatFamily, MaterialFactKind
from constructionsight.intake_service import (
    IntakeInspectionInput,
    detect_format_family,
    inspect_lawful_file,
    inspect_lawful_input,
    normalize_fact_value,
)


def _zip_bytes(entries: dict[str, bytes]) -> bytes:
    buffer = BytesIO()
    with zipfile.ZipFile(buffer, mode="w") as archive_file:
        for filename, data in entries.items():
            archive_file.writestr(filename, data)
    return buffer.getvalue()


def test_detect_format_family_identifies_finite_binary_families() -> None:
    assert detect_format_family(b"%PDF-1.7\n").format_family == DigitalFormatFamily.PDF
    assert detect_format_family(b"\x89PNG\r\n\x1a\n").format_family == DigitalFormatFamily.IMAGE
    assert detect_format_family(b"SQLite format 3\x00").format_family == DigitalFormatFamily.SQLITE

    docx = _zip_bytes({"word/document.xml": b"<w:document/>"})
    xlsx = _zip_bytes({"xl/workbook.xml": b"<workbook/>"})
    pptx = _zip_bytes({"ppt/presentation.xml": b"<presentation/>"})
    generic_zip = _zip_bytes({"manifest.json": b"{}"})

    assert detect_format_family(docx, original_filename="record.docx").format_family == (
        DigitalFormatFamily.DOCX
    )
    assert detect_format_family(xlsx, original_filename="record.xlsx").format_family == (
        DigitalFormatFamily.XLSX
    )
    assert detect_format_family(pptx, original_filename="record.pptx").format_family == (
        DigitalFormatFamily.PPTX
    )
    assert detect_format_family(generic_zip).format_family == DigitalFormatFamily.ZIP


def test_detect_format_family_identifies_structured_text_families() -> None:
    assert detect_format_family(b'{"address": "123 Main St"}').format_family == (
        DigitalFormatFamily.JSON
    )
    assert detect_format_family(b'{"a": 1}\n{"a": 2}\n').format_family == DigitalFormatFamily.JSONL
    assert detect_format_family(b"name,address\nA,123 Main St\n").format_family == (
        DigitalFormatFamily.CSV
    )
    assert detect_format_family(b"name\taddress\nA\t123 Main St\n").format_family == (
        DigitalFormatFamily.TSV
    )
    assert detect_format_family(b"<html><body>123 Main St</body></html>").format_family == (
        DigitalFormatFamily.HTML
    )
    assert detect_format_family(b"<?xml version='1.0'?><record/>").format_family == (
        DigitalFormatFamily.XML
    )
    email_detection = detect_format_family(
        b"From: a@example.com\nTo: b@example.com\nSubject: Test\n"
    )
    assert email_detection.format_family == DigitalFormatFamily.EMAIL


def test_inspect_lawful_input_extracts_material_facts_and_routes_to_opportunity() -> None:
    content = """
    City of Hesperia reviewed SCH No. 2026061234 for warehouse construction.
    Project site: 123 Main Street. APN: 123-456-78.
    Contact: planner@example.gov. Estimated value: $1,250,000.
    """.encode()

    record = inspect_lawful_input(
        IntakeInspectionInput(content=content, source_name="manual test note")
    ).to_dict()

    assert record["format_detection"]["format_family"] == "plain_text"
    assert record["understanding_status"] == "partially_understood"
    assert record["routing"] == "opportunity_intake"
    facts = {(fact["fact_kind"], fact["normalized_value"]) for fact in record["extracted_facts"]}
    assert ("address", "123 Main Street") in facts
    assert ("apn", "12345678") in facts
    assert ("sch_number", "2026061234") in facts
    assert ("email", "planner@example.gov") in facts
    assert ("money", "$1,250,000") in facts
    assert ("agency", "city of hesperia") in facts
    assert ("keyword", "warehouse") in facts


def test_inspect_lawful_input_routes_unknown_binary_for_review() -> None:
    record = inspect_lawful_input(
        IntakeInspectionInput(content=b"\x00\x01\x02\x03", source_name="unknown binary")
    ).to_dict()

    assert record["format_detection"]["format_family"] == "binary"
    assert record["understanding_status"] == "preserved_only"
    assert record["routing"] == "human_review"
    assert record["extracted_facts"] == []
    assert record["unmapped_fragments"][0]["reason"] == (
        "binary requires a dedicated adapter or extractor"
    )


def test_inspect_lawful_input_uses_source_family_hint_for_adapter_route() -> None:
    record = inspect_lawful_input(
        IntakeInspectionInput(
            content=json.dumps({"project": "Warehouse", "apn": "123-456-78"}).encode(),
            source_name="CEQAnet snapshot",
            source_family="ceqanet",
        )
    ).to_dict()

    assert record["format_detection"]["format_family"] == "json"
    assert record["routing"] == "source_adapter"
    assert record["adapter_candidate"] == "ceqanet"


def test_inspect_lawful_file_preserves_snapshot_path(tmp_path: Path) -> None:
    input_path = tmp_path / "record.txt"
    input_path.write_text("APN: 123-456-78 at 123 Main Street", encoding="utf-8")

    record = inspect_lawful_file(input_path, source_name="local record").to_dict()

    assert record["evidence"]["snapshot_path"] == str(input_path)
    assert record["evidence"]["original_filename"] == "record.txt"
    assert record["record_hints"]["apn"] == "12345678"


def test_normalize_fact_value_is_deterministic() -> None:
    assert normalize_fact_value(kind=MaterialFactKind.ADDRESS, value="  A  B  ") == "A B"
    assert normalize_fact_value(kind=MaterialFactKind.APN, value="123-456-78") == "12345678"
