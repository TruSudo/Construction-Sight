import json
from datetime import UTC, datetime
from pathlib import Path

from typer.testing import CliRunner

from constructionsight.parcel_source_acquisition import (
    build_arcgis_acquisition_assessment,
    build_arcgis_probe_plan,
    get_official_arcgis_capability_snapshots,
    parse_arcgis_probe_observation,
)
from constructionsight.parcel_source_acquisition_bundle import (
    build_arcgis_bounded_proof_bundle,
)
from constructionsight.parcel_source_acquisition_models import ParcelArcGISProbeKind
from constructionsight.parcel_source_cli import app
from constructionsight.parcel_source_verification import (
    get_parcel_source_evidence,
    get_verified_parcel_source_profiles,
)

runner = CliRunner()

_OBSERVED_AT = datetime(2026, 7, 14, 19, 0, tzinfo=UTC)


def _write_bounded_bundle(path: Path):
    snapshot = get_official_arcgis_capability_snapshots()[0]
    profile = next(
        item
        for item in get_verified_parcel_source_profiles()
        if item.profile_id == snapshot.profile_id
    )
    evidence_by_id = {
        item.evidence_id: item for item in get_parcel_source_evidence()
    }
    plan = build_arcgis_probe_plan(snapshot, generated_at=_OBSERVED_AT)
    response_by_kind = {
        ParcelArcGISProbeKind.COUNT: {"count": 6},
        ParcelArcGISProbeKind.INITIAL_PAGE: {
            "features": [
                {"attributes": {"OBJECTID": 1}},
                {"attributes": {"OBJECTID": 3}},
            ],
            "exceededTransferLimit": True,
        },
        ParcelArcGISProbeKind.NEXT_PAGE: {
            "features": [
                {"attributes": {"OBJECTID": 5}},
                {"attributes": {"OBJECTID": 7}},
            ],
            "exceededTransferLimit": True,
        },
        ParcelArcGISProbeKind.REPLAY_PAGE: {
            "features": [
                {"attributes": {"OBJECTID": 1}},
                {"attributes": {"OBJECTID": 3}},
            ],
            "exceededTransferLimit": True,
        },
    }
    observations = tuple(
        parse_arcgis_probe_observation(
            request,
            response_by_kind[request.kind],
            observed_at=_OBSERVED_AT,
        )
        for request in plan.requests
    )
    assessment = build_arcgis_acquisition_assessment(
        snapshot,
        plan,
        observations,
        generated_at=_OBSERVED_AT,
    )
    bundle = build_arcgis_bounded_proof_bundle(
        profile,
        (evidence_by_id[evidence_id] for evidence_id in profile.evidence_ids),
        snapshot,
        plan,
        observations,
        assessment,
        created_at=_OBSERVED_AT,
    )
    path.write_text(json.dumps(bundle.to_dict()), encoding="utf-8")
    return bundle


def test_parcel_source_cli_renders_matrix() -> None:
    result = runner.invoke(app, ["matrix", "--county", "San Bernardino"])

    assert result.exit_code == 0
    assert "Parcel Source Registry" in result.output
    assert "San Bernardino" in result.output


def test_parcel_source_cli_emits_filtered_json() -> None:
    result = runner.invoke(
        app,
        [
            "matrix",
            "--provider-kind",
            "county_gis",
            "--json-output",
        ],
    )

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload
    assert {row["provider_kind"] for row in payload} == {"county_gis"}


def test_parcel_source_cli_writes_report_json(tmp_path: Path) -> None:
    output_path = tmp_path / "parcel-source-report.json"

    result = runner.invoke(
        app,
        ["report", "--json-output", "--output", str(output_path)],
    )

    assert result.exit_code == 0
    assert "Wrote parcel source registry report JSON" in result.output
    payload = json.loads(output_path.read_text(encoding="utf-8"))
    assert payload["sources_reviewed"] >= 4
    assert payload["target_sources"]


def test_parcel_source_cli_rejects_output_without_json(tmp_path: Path) -> None:
    result = runner.invoke(
        app,
        ["matrix", "--output", str(tmp_path / "matrix.json")],
    )

    assert result.exit_code != 0
    assert "--output requires --json-output" in result.output


def test_parcel_source_cli_emits_digest_bound_evidence_json() -> None:
    result = runner.invoke(app, ["evidence", "--json-output"])

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert len(payload) == 8
    assert all(item["evidence_id"].startswith("parcel-source-evidence:") for item in payload)


def test_parcel_source_cli_renders_verification_profiles() -> None:
    result = runner.invoke(app, ["verification"])

    assert result.exit_code == 0
    assert "Parcel Source Verification Profiles" in result.output
    assert "verified_preview" in result.output
    assert "San Bernardino" in result.output
    assert "Riverside" in result.output


def test_parcel_source_cli_emits_county_coverage_gaps() -> None:
    result = runner.invoke(app, ["coverage", "--json-output"])

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["status"] == "incomplete"
    assert len(payload["gaps"]) == 10
    assert {gap["county"] for gap in payload["gaps"]} == {
        "Riverside",
        "San Bernardino",
    }


def test_parcel_source_cli_separates_advertised_capabilities_from_proof() -> None:
    capability_result = runner.invoke(
        app,
        ["acquisition-capabilities", "--json-output"],
    )
    readiness_result = runner.invoke(
        app,
        ["acquisition-readiness", "--json-output"],
    )

    assert capability_result.exit_code == 0
    capabilities = json.loads(capability_result.output)
    assert len(capabilities) == 2
    assert all(item["supports_pagination"] is True for item in capabilities)
    assert readiness_result.exit_code == 0
    assessments = json.loads(readiness_result.output)
    assert {item["status"] for item in assessments} == {"metadata_only"}
    assert all(item["bulk_acquisition_verified"] is False for item in assessments)


def test_parcel_source_cli_probe_plans_never_authorize_bulk() -> None:
    result = runner.invoke(app, ["acquisition-plans", "--json-output"])

    assert result.exit_code == 0
    plans = json.loads(result.output)
    assert len(plans) == 2
    assert all(plan["bulk_run_authorized"] is False for plan in plans)
    assert all(len(plan["requests"]) == 4 for plan in plans)


def test_live_acquisition_probe_rejects_unknown_source_before_network() -> None:
    result = runner.invoke(
        app,
        ["acquisition-probe", "--source-key", "not-a-source"],
    )

    assert result.exit_code != 0
    assert "Unknown verified ArcGIS source key" in result.output


def test_acquisition_bundle_cli_verifies_offline(tmp_path: Path) -> None:
    bundle_path = tmp_path / "bounded-proof.json"
    bundle = _write_bounded_bundle(bundle_path)

    result = runner.invoke(
        app,
        [
            "acquisition-verify-bundle",
            "--input",
            str(bundle_path),
            "--json-output",
        ],
    )

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["bundle_id"] == bundle.bundle_id
    assert payload["valid"] is True
    assert payload["assessment_recomputed"] is True
    assert payload["bulk_run_authorized"] is False


def test_acquisition_bundle_cli_requires_authorization_before_file_or_database() -> None:
    result = runner.invoke(
        app,
        [
            "acquisition-persist-bundle",
            "--input",
            "does-not-exist.json",
            "--expected-bundle-id",
            "parcel-arcgis-bounded-proof-bundle:" + ("0" * 64),
        ],
    )

    assert result.exit_code != 0
    assert "requires --authorize-persistence" in result.output


def test_acquisition_bundle_cli_rejects_unapproved_identity_before_database(
    tmp_path: Path,
) -> None:
    bundle_path = tmp_path / "bounded-proof.json"
    _write_bounded_bundle(bundle_path)

    result = runner.invoke(
        app,
        [
            "acquisition-persist-bundle",
            "--input",
            str(bundle_path),
            "--expected-bundle-id",
            "parcel-arcgis-bounded-proof-bundle:" + ("0" * 64),
            "--database-url",
            f"sqlite:///{tmp_path / 'must-not-exist.sqlite3'}",
            "--authorize-persistence",
        ],
    )

    assert result.exit_code != 0
    assert "expected bundle identity does not match" in result.output
    assert not (tmp_path / "must-not-exist.sqlite3").exists()


def test_acquisition_bundle_cli_persists_exact_authorized_artifact(
    tmp_path: Path,
) -> None:
    bundle_path = tmp_path / "bounded-proof.json"
    bundle = _write_bounded_bundle(bundle_path)
    database_path = tmp_path / "bounded-proof.sqlite3"

    result = runner.invoke(
        app,
        [
            "acquisition-persist-bundle",
            "--input",
            str(bundle_path),
            "--expected-bundle-id",
            bundle.bundle_id,
            "--database-url",
            f"sqlite:///{database_path}",
            "--authorize-persistence",
            "--json-output",
        ],
    )

    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["bundle_id"] == bundle.bundle_id
    assert payload["mutation_authorized"] is True
    assert payload["replay_policy"] == "insert_or_exact_replay"
    assert payload["bulk_run_authorized"] is False
    assert database_path.exists()
