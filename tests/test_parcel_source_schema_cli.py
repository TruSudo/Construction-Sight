import json
from pathlib import Path

from typer.testing import CliRunner

from constructionsight.parcel_schema_models import ParcelSchemaField, ParcelSchemaPreviewInput
from constructionsight.parcel_source_cli import app
from constructionsight.parcel_source_models import (
    ParcelGeometrySupport,
    ParcelSourceFormat,
)

runner = CliRunner()


def _write_schema_preview_input(path: Path) -> None:
    preview_input = ParcelSchemaPreviewInput(
        source_key="test:cli-schema",
        source_name="CLI Schema Test Source",
        source_format=ParcelSourceFormat.GEOJSON,
        observed_fields=[
            ParcelSchemaField(source_field="parcelnumb"),
            ParcelSchemaField(source_field="county"),
            ParcelSchemaField(source_field="owner_name"),
            ParcelSchemaField(source_field="geometry"),
        ],
        geometry_support=ParcelGeometrySupport.POLYGON,
        spatial_reference="EPSG:4326",
    )
    path.write_text(preview_input.model_dump_json(), encoding="utf-8")


def test_parcel_source_cli_renders_schema_preview_from_source_key() -> None:
    result = runner.invoke(
        app,
        ["preview-schema", "--source-key", "regrid:licensed-parcel-provider"],
    )

    assert result.exit_code == 0
    assert "Parcel Source Schema Preview" in result.output
    assert "regrid:licensed-parcel-provider" in result.output


def test_parcel_source_cli_emits_schema_preview_json(tmp_path: Path) -> None:
    input_path = tmp_path / "schema-preview.json"
    _write_schema_preview_input(input_path)

    result = runner.invoke(
        app,
        ["preview-schema", "--input", str(input_path), "--json-output"],
    )

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["source_key"] == "test:cli-schema"
    assert payload["status"] == "ready_for_import_preview"
    assert payload["mapped_fields"]


def test_parcel_source_cli_writes_schema_preview_json(tmp_path: Path) -> None:
    input_path = tmp_path / "schema-preview.json"
    output_path = tmp_path / "schema-preview-report.json"
    _write_schema_preview_input(input_path)

    result = runner.invoke(
        app,
        [
            "preview-schema",
            "--input",
            str(input_path),
            "--json-output",
            "--output",
            str(output_path),
        ],
    )

    assert result.exit_code == 0
    assert "Wrote parcel source schema preview JSON" in result.output
    payload = json.loads(output_path.read_text(encoding="utf-8"))
    assert payload["preview_id"].startswith("parcel-schema-preview:")


def test_parcel_source_cli_rejects_schema_preview_without_source_or_input() -> None:
    result = runner.invoke(app, ["preview-schema"])

    assert result.exit_code != 0
    assert "Provide exactly one of --input or --source-key" in result.output


def test_parcel_source_cli_rejects_schema_preview_output_without_json(tmp_path: Path) -> None:
    input_path = tmp_path / "schema-preview.json"
    _write_schema_preview_input(input_path)

    result = runner.invoke(
        app,
        [
            "preview-schema",
            "--input",
            str(input_path),
            "--output",
            str(tmp_path / "schema-preview-report.json"),
        ],
    )

    assert result.exit_code != 0
    assert "--output requires --json-output" in result.output
