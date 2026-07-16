import pytest

from constructionsight.ceqanet_operator_package import build_ceqanet_operator_package


def _chain_report() -> dict[str, object]:
    return {
        "metadata": {
            "schema_version": "ceqanet_chain_report.v1",
            "result_record_count": 2,
            "missing_detail_count": 1,
            "sch_mismatch_count": 0,
            "network_executed": False,
            "persistence_mutated": False,
        },
        "enrichment": {
            "metadata": {
                "schema_version": "ceqanet_detail_enrichment.v1",
                "record_count": 2,
                "enriched_count": 1,
                "missing_detail_count": 1,
                "sch_mismatch_count": 0,
            },
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
                },
                {
                    "title": "2026061234",
                    "detail_url": "https://ceqanet.lci.ca.gov/Project/2026061234",
                    "sch_number": "2026061234",
                    "document_type": None,
                    "lead_agency": None,
                    "county": "San Bernardino",
                    "city": None,
                    "project_location": None,
                    "project_description": None,
                    "source_url": "https://ceqanet.lci.ca.gov/Search",
                    "raw_result_text": "SCH Number 2026061234",
                    "raw_detail_text": "",
                    "title_source": "sch_number",
                    "has_human_title": False,
                    "requires_detail_enrichment": True,
                    "enrichment_status": "missing_detail",
                    "field_sources": {"title": "result_page"},
                    "warnings": [],
                },
            ],
        },
    }


def test_build_ceqanet_operator_package_combines_review_artifacts() -> None:
    package = build_ceqanet_operator_package(_chain_report()).to_dict()

    assert package["metadata"]["schema_version"] == "ceqanet_operator_package.v1"
    assert package["metadata"]["chain_schema_version"] == "ceqanet_chain_report.v1"
    assert package["metadata"]["preview_schema_version"] == "ceqanet_persistence_preview.v1"
    assert package["metadata"]["write_plan_schema_version"] == "ceqanet_write_plan.v1"
    assert package["metadata"]["result_record_count"] == 2
    assert package["metadata"]["ceqa_record_count"] == 2
    assert package["metadata"]["site_count"] == 2
    assert package["metadata"]["entity_count"] == 1
    assert package["metadata"]["operation_count"] == 5
    assert package["metadata"]["warning_count"] == 1
    assert package["metadata"]["network_executed"] is False
    assert package["metadata"]["database_opened"] is False
    assert package["metadata"]["persistence_mutated"] is False
    assert package["warnings"] == [
        "Chain report contains result records missing detail-page enrichment."
    ]
    assert package["persistence_preview"]["metadata"]["planned_write_count"] == 5
    assert package["write_plan"]["metadata"]["operation_count"] == 5


def test_build_ceqanet_operator_package_warns_on_empty_plan() -> None:
    chain_report = _chain_report()
    enrichment = chain_report["enrichment"]
    assert isinstance(enrichment, dict)
    enrichment["records"] = []
    metadata = chain_report["metadata"]
    assert isinstance(metadata, dict)
    metadata["missing_detail_count"] = 0

    package = build_ceqanet_operator_package(chain_report).to_dict()

    assert package["metadata"]["operation_count"] == 0
    assert "Write plan contains no operations." in package["warnings"]


def test_build_ceqanet_operator_package_rejects_missing_metadata() -> None:
    with pytest.raises(ValueError, match="must contain metadata"):
        build_ceqanet_operator_package({})


def test_build_ceqanet_operator_package_rejects_wrong_schema() -> None:
    with pytest.raises(ValueError, match="ceqanet_chain_report.v1"):
        build_ceqanet_operator_package({"metadata": {"schema_version": "wrong.v1"}})


def test_build_ceqanet_operator_package_rejects_missing_enrichment() -> None:
    with pytest.raises(ValueError, match="must contain an enrichment object"):
        build_ceqanet_operator_package({"metadata": {"schema_version": "ceqanet_chain_report.v1"}})
