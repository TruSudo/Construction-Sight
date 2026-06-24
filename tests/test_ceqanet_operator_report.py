import pytest

from constructionsight.ceqanet_operator_report import build_ceqanet_operator_report


def _operator_package() -> dict[str, object]:
    return {
        "metadata": {
            "schema_version": "ceqanet_operator_package.v1",
            "result_record_count": 1,
            "ceqa_record_count": 1,
            "site_count": 1,
            "entity_count": 1,
            "operation_count": 3,
            "warning_count": 1,
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
                {
                    "operation_id": "entities:entity:lead-agency:county-agency",
                    "action": "upsert_preview",
                    "target_collection": "entities",
                    "target_key": "entity:lead-agency:county-agency",
                },
            ],
        },
        "warnings": ["Chain report contains result records missing detail-page enrichment."],
    }


def test_build_ceqanet_operator_report_creates_markdown_report() -> None:
    report = build_ceqanet_operator_report(_operator_package()).to_dict()

    assert report["metadata"]["schema_version"] == "ceqanet_operator_report.v1"
    assert report["metadata"]["package_schema_version"] == "ceqanet_operator_package.v1"
    assert report["metadata"]["ceqa_record_count"] == 1
    assert report["metadata"]["operation_count"] == 3
    assert report["metadata"]["warning_count"] == 1
    assert report["metadata"]["network_executed"] is False
    assert report["metadata"]["database_opened"] is False
    assert report["metadata"]["persistence_mutated"] is False

    markdown = report["markdown"]
    assert "# CEQAnet Operator Report" in markdown
    assert "## Summary" in markdown
    assert "## Review Warnings" in markdown
    assert "Countywide Plan" in markdown
    assert "ceqa_records:ceqa:ceqanet:2017101033" in markdown
    assert "Chain report contains result records missing detail-page enrichment." in markdown


def test_build_ceqanet_operator_report_handles_empty_sections() -> None:
    package = _operator_package()
    preview = package["persistence_preview"]
    assert isinstance(preview, dict)
    preview["ceqa_records"] = []
    write_plan = package["write_plan"]
    assert isinstance(write_plan, dict)
    write_plan["operations"] = []
    package["warnings"] = []

    markdown = build_ceqanet_operator_report(package).markdown

    assert "No package-level warnings." in markdown
    assert "No CEQA record previews." in markdown
    assert "No planned operations." in markdown


def test_build_ceqanet_operator_report_escapes_markdown_table_cells() -> None:
    package = _operator_package()
    preview = package["persistence_preview"]
    assert isinstance(preview, dict)
    records = preview["ceqa_records"]
    assert isinstance(records, list)
    records[0]["title"] = "A | B"

    markdown = build_ceqanet_operator_report(package).markdown

    assert "A \\| B" in markdown


def test_build_ceqanet_operator_report_rejects_missing_metadata() -> None:
    with pytest.raises(ValueError, match="must contain metadata"):
        build_ceqanet_operator_report({})


def test_build_ceqanet_operator_report_rejects_wrong_schema() -> None:
    with pytest.raises(ValueError, match="ceqanet_operator_package.v1"):
        build_ceqanet_operator_report({"metadata": {"schema_version": "wrong.v1"}})


def test_build_ceqanet_operator_report_rejects_missing_components() -> None:
    with pytest.raises(ValueError, match="persistence_preview object"):
        build_ceqanet_operator_report(
            {"metadata": {"schema_version": "ceqanet_operator_package.v1"}}
        )
