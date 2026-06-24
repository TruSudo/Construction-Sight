from pathlib import Path

import pytest

from constructionsight.ceqanet_operator_export import build_ceqanet_operator_export


def _chain_report() -> dict[str, object]:
    return {
        "metadata": {
            "schema_version": "ceqanet_chain_report.v1",
            "result_record_count": 1,
            "missing_detail_count": 0,
            "sch_mismatch_count": 0,
            "network_executed": False,
            "persistence_mutated": False,
        },
        "enrichment": {
            "metadata": {"schema_version": "ceqanet_detail_enrichment.v1"},
            "records": [
                {
                    "title": "Countywide Plan",
                    "detail_url": "https://ceqanet.lci.ca.gov/Project/2017101033",
                    "sch_number": "2017101033",
                    "document_type": "Environmental Impact Report",
                    "lead_agency": "County Agency",
                    "county": "San Bernardino",
                    "city": "San Bernardino",
                    "project_location": "San Bernardino County, California",
                    "project_description": "Countywide policy plan.",
                    "source_url": "https://ceqanet.lci.ca.gov/Search",
                    "raw_result_text": "SCH Number 2017101033",
                    "raw_detail_text": "Project Title Countywide Plan",
                    "title_source": "human_label",
                    "has_human_title": True,
                    "requires_detail_enrichment": False,
                    "enrichment_status": "enriched",
                    "field_sources": {"title": "detail_page"},
                    "warnings": [],
                }
            ],
        },
    }


def test_build_ceqanet_operator_export_builds_and_verifies_bundle(tmp_path: Path) -> None:
    export = build_ceqanet_operator_export(_chain_report(), output_dir=tmp_path).to_dict()

    assert export["metadata"]["schema_version"] == "ceqanet_operator_export.v1"
    assert export["metadata"]["package_schema_version"] == "ceqanet_operator_package.v1"
    assert export["metadata"]["bundle_schema_version"] == "ceqanet_operator_bundle.v1"
    assert export["metadata"]["verification_schema_version"] == (
        "ceqanet_operator_bundle_verification.v1"
    )
    assert export["metadata"]["ceqa_record_count"] == 1
    assert export["metadata"]["operation_count"] == 3
    assert export["metadata"]["bundle_artifact_count"] == 6
    assert export["metadata"]["verified_artifact_count"] == 5
    assert export["metadata"]["missing_artifact_count"] == 0
    assert export["metadata"]["mismatched_artifact_count"] == 1
    assert export["metadata"]["malformed_artifact_count"] == 0
    assert export["metadata"]["verification_passed"] is False
    assert export["metadata"]["network_executed"] is False
    assert export["metadata"]["database_opened"] is False
    assert export["metadata"]["persistence_mutated"] is False

    assert (tmp_path / "operator-package.json").exists()
    assert (tmp_path / "persistence-preview.json").exists()
    assert (tmp_path / "write-plan.json").exists()
    assert (tmp_path / "operator-report.json").exists()
    assert (tmp_path / "operator-report.md").exists()
    assert (tmp_path / "manifest.json").exists()


def test_build_ceqanet_operator_export_rejects_bad_chain_report(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="ceqanet_chain_report.v1"):
        build_ceqanet_operator_export(
            {"metadata": {"schema_version": "wrong.v1"}},
            output_dir=tmp_path,
        )
