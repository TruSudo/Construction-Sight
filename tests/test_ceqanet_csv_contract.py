from __future__ import annotations

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from constructionsight.ceqanet_csv_cli import app
from constructionsight.ceqanet_csv_models import (
    CeqanetCsvCanonicalRole,
    CeqanetCsvExportKind,
)
from constructionsight.ceqanet_csv_service import (
    build_ceqanet_csv_export_request,
    inspect_ceqanet_csv_bytes,
    parse_ceqanet_csv_export_url,
)

ROOT = Path(__file__).resolve().parents[1]
PROJECT_FIXTURE = ROOT / "tests/fixtures/ceqanet/project_export.csv"
DOCUMENT_FIXTURE = ROOT / "tests/fixtures/ceqanet/document_export.csv"
runner = CliRunner()


def test_project_export_request_is_deterministic_and_nonexecuting() -> None:
    request = build_ceqanet_csv_export_request(sch_number="2026030377")

    assert request.export_kind is CeqanetCsvExportKind.PROJECT
    assert request.document_id is None
    assert request.source_url == (
        "https://ceqanet.lci.ca.gov/Search?OutputFormat=CSV&Sch=2026030377"
    )
    assert request.network_authorized is False
    assert request.persistence_authorized is False
    assert parse_ceqanet_csv_export_url(request.source_url) == request


def test_document_export_request_is_deterministic_and_nonexecuting() -> None:
    request = build_ceqanet_csv_export_request(
        sch_number="2026070311",
        document_id=1,
    )

    assert request.export_kind is CeqanetCsvExportKind.DOCUMENT
    assert request.document_id == 1
    assert request.source_url == (
        "https://ceqanet.lci.ca.gov/Search?DocumentId=1&OutputFormat=CSV&Sch=2026070311"
    )
    assert parse_ceqanet_csv_export_url(request.source_url) == request


@pytest.mark.parametrize(
    ("url", "message"),
    [
        (
            "http://ceqanet.lci.ca.gov/Search?OutputFormat=CSV&Sch=2026030377",
            "approved official HTTPS host",
        ),
        (
            "https://example.com/Search?OutputFormat=CSV&Sch=2026030377",
            "approved official HTTPS host",
        ),
        (
            "https://ceqanet.lci.ca.gov/Other?OutputFormat=CSV&Sch=2026030377",
            "official /Search path",
        ),
        (
            "https://ceqanet.lci.ca.gov/Search?OutputFormat=HTML&Sch=2026030377",
            "OutputFormat=CSV",
        ),
        (
            "https://ceqanet.lci.ca.gov/Search?OutputFormat=CSV&Sch=2026030377&Page=2",
            "unsupported query keys",
        ),
        (
            "https://ceqanet.lci.ca.gov/Search?OutputFormat=CSV&Sch=2026030377&Sch=2026030377",
            "duplicate query keys",
        ),
    ],
)
def test_export_url_rejects_unapproved_shapes(url: str, message: str) -> None:
    with pytest.raises(ValueError, match=message):
        parse_ceqanet_csv_export_url(url)


def test_export_request_rejects_invalid_identities() -> None:
    with pytest.raises(ValueError, match="exactly 10 digits"):
        build_ceqanet_csv_export_request(sch_number="202603377")
    with pytest.raises(ValueError, match="greater than 0"):
        build_ceqanet_csv_export_request(
            sch_number="2026030377",
            document_id=0,
        )


def test_project_fixture_inspection_preserves_unknown_columns_and_integrity() -> None:
    request = build_ceqanet_csv_export_request(sch_number="2026030377")
    content = PROJECT_FIXTURE.read_bytes()

    inspection = inspect_ceqanet_csv_bytes(
        request,
        content,
        content_type="text/csv; charset=utf-8",
    )

    assert inspection.content_type == "text/csv"
    assert inspection.row_count == 2
    assert inspection.retained_row_count == 2
    assert inspection.rows_truncated is False
    assert inspection.unknown_columns == ["project_acres"]
    assert inspection.rows[0]["sch_number"] == "2026030377"
    assert inspection.rows[0]["project_acres"] == "145.2"
    assert inspection.network_executed is False
    assert inspection.persistence_authorized is False
    roles = {
        column.canonical_role for column in inspection.columns if column.canonical_role
    }
    assert CeqanetCsvCanonicalRole.SCH_NUMBER in roles
    assert CeqanetCsvCanonicalRole.LEAD_AGENCY in roles
    assert CeqanetCsvCanonicalRole.DESCRIPTION in roles
    inspection.assert_integrity()



@pytest.mark.parametrize(
    ("document_id", "canonical_title", "unassigned_title"),
    [
        (None, "project_title", "document_title"),
        (1, "document_title", "project_title"),
    ],
)
def test_scope_selects_one_canonical_title_without_discarding_columns(
    document_id: int | None,
    canonical_title: str,
    unassigned_title: str,
) -> None:
    request = build_ceqanet_csv_export_request(
        sch_number="2026030377",
        document_id=document_id,
    )
    content = (
        b"SCH Number,Document Title,Project Title\r\n"
        b"2026030377,Document value,Project value\r\n"
    )

    inspection = inspect_ceqanet_csv_bytes(
        request,
        content,
        content_type="text/csv",
    )

    roles = {
        column.normalized_name: column.canonical_role
        for column in inspection.columns
    }
    assert roles[canonical_title] is CeqanetCsvCanonicalRole.TITLE
    assert roles[unassigned_title] is None
    assert inspection.unknown_columns == [unassigned_title]
    assert inspection.rows[0]["document_title"] == "Document value"
    assert inspection.rows[0]["project_title"] == "Project value"
    assert (
        "multiple title columns were preserved; canonical title was assigned "
        "by export scope"
    ) in inspection.warnings

def test_document_fixture_inspection_maps_high_value_roles() -> None:
    request = build_ceqanet_csv_export_request(
        sch_number="2026070311",
        document_id=1,
    )

    inspection = inspect_ceqanet_csv_bytes(
        request,
        DOCUMENT_FIXTURE.read_bytes(),
        content_type="application/vnd.ms-excel",
    )

    roles = {
        column.canonical_role for column in inspection.columns if column.canonical_role
    }
    assert inspection.row_count == 1
    assert inspection.unknown_columns == []
    assert CeqanetCsvCanonicalRole.DOCUMENT_ID in roles
    assert CeqanetCsvCanonicalRole.DOCUMENT_TYPE in roles
    assert CeqanetCsvCanonicalRole.CONTACT_EMAIL in roles
    assert CeqanetCsvCanonicalRole.PARCEL_NUMBER in roles
    inspection.assert_integrity()


def test_utf8_bom_is_supported_without_changing_values() -> None:
    request = build_ceqanet_csv_export_request(sch_number="2026030377")
    content = b"\xef\xbb\xbf" + PROJECT_FIXTURE.read_bytes()

    inspection = inspect_ceqanet_csv_bytes(request, content, content_type="text/csv")

    assert inspection.rows[0]["sch_number"] == "2026030377"
    assert inspection.encoding == "utf-8-sig"


def test_row_retention_limit_preserves_total_count_and_body_digest() -> None:
    request = build_ceqanet_csv_export_request(sch_number="2026030377")
    content = PROJECT_FIXTURE.read_bytes()

    full = inspect_ceqanet_csv_bytes(request, content, max_retained_rows=100)
    limited = inspect_ceqanet_csv_bytes(request, content, max_retained_rows=1)

    assert full.row_count == limited.row_count == 2
    assert limited.retained_row_count == 1
    assert limited.rows_truncated is True
    assert full.body_sha256 == limited.body_sha256
    assert full.inspection_digest != limited.inspection_digest


@pytest.mark.parametrize(
    "content_type",
    ["text/html", "application/json", "application/pdf"],
)
def test_inspection_rejects_non_csv_content_types(content_type: str) -> None:
    request = build_ceqanet_csv_export_request(sch_number="2026030377")

    with pytest.raises(ValueError, match="unsupported CEQAnet CSV content type"):
        inspect_ceqanet_csv_bytes(
            request,
            PROJECT_FIXTURE.read_bytes(),
            content_type=content_type,
        )


def test_missing_content_type_is_retained_as_a_warning() -> None:
    request = build_ceqanet_csv_export_request(sch_number="2026030377")

    inspection = inspect_ceqanet_csv_bytes(request, PROJECT_FIXTURE.read_bytes())

    assert inspection.content_type is None
    assert "content type was not supplied" in inspection.warnings[0]


@pytest.mark.parametrize(
    ("content", "message"),
    [
        (b"", "must not be empty"),
        (b"Title\nOnly a row\n", "identifiable SCH number column"),
        (
            b"SCH Number,Title\n2026070311,Wrong project\n",
            "does not match the request",
        ),
        (
            b"SCH Number,Title\nnot-a-sch,Bad identity\n",
            "invalid SCH number",
        ),
        (
            b"SCH Number,Title\n2026030377,Good,Extra\n",
            "values; expected",
        ),
        (
            b"SCH Number,SCH-Number\n2026030377,2026030377\n",
            "duplicate normalized headers",
        ),
        (
            b"SCH Number,Contact,Contact Name\n2026030377,A,B\n",
            "ambiguous canonical roles",
        ),
        (b"SCH Number,\n2026030377,Value\n", "blank header"),
        (b"\xff\xfe\x00\x00", "NUL character"),
        (b"\x81", "UTF-8.*Windows-1252"),
    ],
)
def test_inspection_rejects_malformed_or_mismatched_bodies(
    content: bytes,
    message: str,
) -> None:
    request = build_ceqanet_csv_export_request(sch_number="2026030377")

    with pytest.raises(ValueError, match=message):
        inspect_ceqanet_csv_bytes(request, content, content_type="text/csv")


def test_inspection_rejects_request_field_and_url_disagreement() -> None:
    request = build_ceqanet_csv_export_request(sch_number="2026030377").model_copy(
        update={"sch_number": "2026070311"}
    )

    with pytest.raises(ValueError, match="do not agree with source_url"):
        inspect_ceqanet_csv_bytes(request, PROJECT_FIXTURE.read_bytes())


def test_plan_cli_emits_exact_nonexecuting_request() -> None:
    result = runner.invoke(
        app,
        ["plan", "--sch-number", "2026030377"],
    )

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["export_kind"] == "project"
    assert payload["network_authorized"] is False
    assert payload["persistence_authorized"] is False
    assert payload["source_url"].endswith("OutputFormat=CSV&Sch=2026030377")


def test_inspect_file_cli_writes_digest_bound_artifact(tmp_path: Path) -> None:
    output_path = tmp_path / "inspection.json"
    result = runner.invoke(
        app,
        [
            "inspect-file",
            str(DOCUMENT_FIXTURE),
            "--source-url",
            "https://ceqanet.lci.ca.gov/Search?DocumentId=1&OutputFormat=CSV&Sch=2026070311",
            "--content-type",
            "text/csv",
            "--output",
            str(output_path),
        ],
    )

    assert result.exit_code == 0
    assert "Wrote CEQAnet CSV artifact" in result.output
    payload = json.loads(output_path.read_text(encoding="utf-8"))
    assert payload["schema_version"] == "ceqanet_csv_inspection.v1"
    assert payload["request"]["export_kind"] == "document"
    assert payload["row_count"] == 1
    assert len(payload["inspection_digest"]) == 64


def test_inspect_file_cli_rejects_html_response_body(tmp_path: Path) -> None:
    html_path = tmp_path / "blocked.csv"
    html_path.write_text("<html>Forbidden</html>", encoding="utf-8")

    result = runner.invoke(
        app,
        [
            "inspect-file",
            str(html_path),
            "--source-url",
            "https://ceqanet.lci.ca.gov/Search?OutputFormat=CSV&Sch=2026030377",
            "--content-type",
            "text/html",
        ],
    )

    assert result.exit_code != 0
    assert "unsupported CEQAnet CSV content type" in result.output
