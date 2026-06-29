import json
from pathlib import Path

from typer.testing import CliRunner

from constructionsight.parcel_row_preview_models import ParcelRowPreviewInput
from constructionsight.parcel_schema_models import ParcelFieldRoleMatch
from constructionsight.parcel_source_cli import app
from constructionsight.parcel_source_models import (
    ParcelFieldRole,
    ParcelGeometrySupport,
    ParcelSourceFormat,
)

runner = CliRunner()


def _match(source_field: str, role: ParcelFieldRole) -> ParcelFieldRoleMatch:
    return ParcelFieldRoleMatch(
        source_field=source_field,
        field_role=role,
        match_reason="test mapping",
        confidence_score=95,
        required_role=role in {ParcelFieldRole.APN, ParcelFieldRole.COUNTY},
    )


def _write_row_preview_input(path: Path) -> None:
    preview_input = ParcelRowPreviewInput(
        source_key="test:cli-row-preview",
        source_name="CLI Row Preview Source",
        source_format=ParcelSourceFormat.CSV,
        field_role_matches=[
            _match("APN", ParcelFieldRole.APN),
            _match("County", ParcelFieldRole.COUNTY),
            _match("Address", ParcelFieldRole.ADDRESS),
        ],
        rows=[
            {"APN": "123-456-78", "County": "Riverside", "Address": "1 Main St"}
        ],
        geometry_support=ParcelGeometrySupport.CENTROID,
        spatial_reference="EPSG:4326",
    )
    path.write_text(preview_input.model_dump_json(), encoding="utf-8")


def test_parcel_source_cli_renders_row_preview(tmp_path: Path) -> None:
    input_path = tmp_path / "row-preview.json"
    _write_row_preview_input(input_path)

    result = runner.invoke(app, ["preview-rows", "--input", str(input_path)])

    assert result.exit_code == 0
    assert "Parcel Row Preview" in result.output
    assert "ready_for_parcel_record_model" in result.output


def test_parcel_source_cli_emits_row_preview_json(tmp_path: Path) -> None:
    input_path = tmp_path / "row-preview.json"
    _write_row_preview_input(input_path)

    result = runner.invoke(
        app,
        ["preview-rows", "--input", str(input_path), "--json-output"],
    )

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["source_key"] == "test:cli-row-preview"
    assert payload["usable_row_count"] == 1


def test_parcel_source_cli_writes_row_preview_json(tmp_path: Path) -> None:
    input_path = tmp_path / "row-preview.json"
    output_path = tmp_path / "row-preview-report.json"
    _write_row_preview_input(input_path)

    result = runner.invoke(
        app,
        [
            "preview-rows",
            "--input",
            str(input_path),
            "--json-output",
            "--output",
            str(output_path),
        ],
    )

    assert result.exit_code == 0
    assert "Wrote parcel row preview JSON" in result.output
    payload = json.loads(output_path.read_text(encoding="utf-8"))
    assert payload["preview_id"].startswith("parcel-row-preview:")


def test_parcel_source_cli_rejects_row_preview_output_without_json(tmp_path: Path) -> None:
    input_path = tmp_path / "row-preview.json"
    _write_row_preview_input(input_path)

    result = runner.invoke(
        app,
        [
            "preview-rows",
            "--input",
            str(input_path),
            "--output",
            str(tmp_path / "row-preview-report.json"),
        ],
    )

    assert result.exit_code != 0
    assert "--output requires --json-output" in result.output
