import json
from pathlib import Path

import pytest

from constructionsight.ceqanet_operator_bundle import build_ceqanet_operator_bundle


def _operator_package() -> dict[str, object]:
    return {
        "metadata": {
            "schema_version": "ceqanet_operator_package.v1",
            "result_record_count": 1,
            "ceqa_record_count": 1,
            "site_count": 1,
            "entity_count": 0,
            "operation_count": 2,
            "warning_count": 0,
            "network_executed": False,
            "database_opened": False,
            "persistence_mutated": False,
        },
        "persistence_preview": {
            "metadata": {"schema_version": "ceqanet_persistence_preview.v1"},
            "ceqa_records": [
                {
                    "ceqa_key": "ceqa:ceqanet:2017101033",
                    "title": "Countywide Plan",
                    "state_clearinghouse_number": "2017101033",
                    "county": "San Bernardino",
                    "lead_agency": "County Agency",
                }
            ],
        },
        "write_plan": {
            "metadata": {"schema_version": "ceqanet_write_plan.v1"},
            "operations": [
                {
                    "operation_id": "ceqa_records:ceqa:ceqanet:2017101033",
                    "action": "upsert_preview",
                    "target_collection": "ceqa_records",
                    "target_key": "ceqa:ceqanet:2017101033",
                },
                {
                    "operation_id": "sites:site:ceqanet:2017101033",
                    "action": "upsert_preview",
                    "target_collection": "sites",
                    "target_key": "site:ceqanet:2017101033",
                },
            ],
        },
        "warnings": [],
    }


def test_build_ceqanet_operator_bundle_writes_review_artifacts(tmp_path: Path) -> None:
    bundle = build_ceqanet_operator_bundle(_operator_package(), output_dir=tmp_path)
    manifest = bundle.to_dict()

    assert manifest["metadata"]["schema_version"] == "ceqanet_operator_bundle.v1"
    assert manifest["metadata"]["artifact_count"] == 6
    assert manifest["metadata"]["network_executed"] is False
    assert manifest["metadata"]["database_opened"] is False
    assert manifest["metadata"]["persistence_mutated"] is False

    assert (tmp_path / "operator-package.json").exists()
    assert (tmp_path / "persistence-preview.json").exists()
    assert (tmp_path / "write-plan.json").exists()
    assert (tmp_path / "operator-report.json").exists()
    assert (tmp_path / "operator-report.md").exists()
    assert (tmp_path / "manifest.json").exists()

    preview = json.loads((tmp_path / "persistence-preview.json").read_text(encoding="utf-8"))
    plan = json.loads((tmp_path / "write-plan.json").read_text(encoding="utf-8"))
    assert preview["metadata"]["schema_version"] == "ceqanet_persistence_preview.v1"
    assert plan["metadata"]["schema_version"] == "ceqanet_write_plan.v1"

    report_markdown = (tmp_path / "operator-report.md").read_text(encoding="utf-8")
    assert "# CEQAnet Operator Report" in report_markdown
    assert "Countywide Plan" in report_markdown

    manifest_json = json.loads((tmp_path / "manifest.json").read_text(encoding="utf-8"))
    assert manifest_json["metadata"]["artifact_count"] == 5
    assert len(manifest["artifacts"]) == 6
    artifact_names = {artifact["filename"] for artifact in manifest["artifacts"]}
    assert artifact_names == {
        "operator-package.json",
        "persistence-preview.json",
        "write-plan.json",
        "operator-report.json",
        "operator-report.md",
        "manifest.json",
    }
    assert all(artifact["sha256"] for artifact in manifest["artifacts"])


def test_build_ceqanet_operator_bundle_rejects_invalid_package(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="ceqanet_operator_package.v1"):
        build_ceqanet_operator_bundle(
            {"metadata": {"schema_version": "wrong.v1"}},
            output_dir=tmp_path,
        )


def test_build_ceqanet_operator_bundle_rejects_missing_component(tmp_path: Path) -> None:
    package = _operator_package()
    del package["write_plan"]

    with pytest.raises(ValueError, match="write_plan object"):
        build_ceqanet_operator_bundle(package, output_dir=tmp_path)
