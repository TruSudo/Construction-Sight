import pytest

from constructionsight.ceqanet_persistence_preview import build_ceqanet_persistence_preview


def _chain_report() -> dict[str, object]:
    return {
        "metadata": {"schema_version": "ceqanet_chain_report.v1"},
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
                    "title": "San Bernardino Countywide Plan",
                    "detail_url": "https://ceqanet.lci.ca.gov/Project/2017101033",
                    "sch_number": "2017101033",
                    "document_type": "Environmental Impact Report",
                    "lead_agency": "San Bernardino County",
                    "county": "San Bernardino",
                    "city": "San Bernardino",
                    "project_location": "San Bernardino County, California",
                    "project_description": "Countywide policy plan.",
                    "source_url": "https://ceqanet.lci.ca.gov/Search?County=San+Bernardino",
                    "raw_result_text": "SCH Number 2017101033",
                    "raw_detail_text": "Project Title San Bernardino Countywide Plan",
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
                    "lead_agency": "Fontana, City of",
                    "county": "San Bernardino",
                    "city": "Fontana",
                    "project_location": None,
                    "project_description": None,
                    "source_url": "https://ceqanet.lci.ca.gov/Search?County=San+Bernardino",
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


def test_build_ceqanet_persistence_preview_creates_domain_records() -> None:
    preview = build_ceqanet_persistence_preview(_chain_report())
    payload = preview.to_dict()

    assert payload["metadata"]["schema_version"] == "ceqanet_persistence_preview.v1"
    assert payload["metadata"]["ceqa_record_count"] == 2
    assert payload["metadata"]["site_count"] == 2
    assert payload["metadata"]["entity_count"] == 2
    assert payload["metadata"]["skipped_record_count"] == 0
    assert payload["metadata"]["planned_write_count"] == 6
    assert payload["metadata"]["network_executed"] is False
    assert payload["metadata"]["persistence_mutated"] is False

    first_record = payload["ceqa_records"][0]
    assert first_record["ceqa_key"] == "ceqa:ceqanet:2017101033"
    assert first_record["title"] == "San Bernardino Countywide Plan"
    assert first_record["state_clearinghouse_number"] == "2017101033"
    assert first_record["description"] == "Countywide policy plan."
    assert first_record["site"]["site_key"] == "site:ceqanet:2017101033"
    assert first_record["entities"][0]["role"] == "agency"
    assert first_record["provenance"][0]["verified"] is False
    assert first_record["provenance"][0]["confidence_score"] == 90


def test_build_ceqanet_persistence_preview_skips_unusable_records() -> None:
    chain_report = _chain_report()
    records = chain_report["enrichment"]["records"]
    assert isinstance(records, list)
    records.append({"title": "Missing SCH"})
    records.append("not an object")

    preview = build_ceqanet_persistence_preview(chain_report).to_dict()

    assert preview["metadata"]["ceqa_record_count"] == 2
    assert preview["metadata"]["skipped_record_count"] == 2
    assert preview["skipped_records"][0]["reason"] == "missing SCH number or title"
    assert preview["skipped_records"][1]["reason"] == "record is not an object"


def test_build_ceqanet_persistence_preview_rejects_missing_enrichment() -> None:
    with pytest.raises(ValueError, match="must contain an enrichment object"):
        build_ceqanet_persistence_preview({})


def test_build_ceqanet_persistence_preview_rejects_missing_records() -> None:
    with pytest.raises(ValueError, match="must contain a records list"):
        build_ceqanet_persistence_preview({"enrichment": {}})
