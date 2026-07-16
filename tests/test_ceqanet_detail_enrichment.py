from constructionsight.adapters.ceqanet_detail_enrichment import (
    enrich_ceqanet_result_record,
    enrich_ceqanet_result_records,
)


def _sch_only_result() -> dict[str, object]:
    return {
        "title": "2017101033",
        "detail_url": "https://ceqanet.lci.ca.gov/Project/2017101033",
        "sch_number": "2017101033",
        "document_type": None,
        "lead_agency": None,
        "county": None,
        "city": None,
        "source_url": "https://ceqanet.lci.ca.gov/Search?County=San+Bernardino",
        "raw_text": "2017101033 | SCH Number | 2017101033",
        "title_source": "sch_number",
        "requires_detail_enrichment": True,
    }


def _detail_parse() -> dict[str, object]:
    return {
        "metadata": {
            "schema_version": "ceqanet_detail_page_parse.v1",
            "has_human_title": True,
            "label_count": 2,
            "link_count": 19,
        },
        "detail": {
            "title": "San Bernardino Countywide Plan",
            "title_source": "human_label",
            "sch_number": "2017101033",
            "document_type": None,
            "lead_agency": None,
            "county": None,
            "city": None,
            "project_location": None,
            "project_description": "Comprehensive countywide plan.",
            "contact": None,
            "raw_text": "Project Title | San Bernardino Countywide Plan",
        },
    }


def test_enrich_ceqanet_result_record_recovers_human_title_from_detail_page() -> None:
    record = enrich_ceqanet_result_record(_sch_only_result(), _detail_parse())

    assert record.enrichment_status == "enriched"
    assert record.title == "San Bernardino Countywide Plan"
    assert record.title_source == "human_label"
    assert record.sch_number == "2017101033"
    assert record.has_human_title is True
    assert record.requires_detail_enrichment is False
    assert record.project_description == "Comprehensive countywide plan."
    assert record.field_sources["title"] == "detail_page"
    assert record.field_sources["project_description"] == "detail_page"
    assert record.field_sources["document_type"] == "unavailable"


def test_enrich_ceqanet_result_record_preserves_result_when_detail_missing() -> None:
    record = enrich_ceqanet_result_record(_sch_only_result(), None)

    assert record.enrichment_status == "missing_detail"
    assert record.title == "2017101033"
    assert record.title_source == "sch_number"
    assert record.has_human_title is False
    assert record.requires_detail_enrichment is True
    assert record.field_sources["title"] == "result_page"
    assert record.field_sources["project_description"] == "unavailable"


def test_enrich_ceqanet_result_record_rejects_sch_mismatch() -> None:
    detail_parse = _detail_parse()
    detail = detail_parse["detail"]
    assert isinstance(detail, dict)
    detail["sch_number"] = "2026060698"

    record = enrich_ceqanet_result_record(_sch_only_result(), detail_parse)

    assert record.enrichment_status == "sch_mismatch"
    assert record.title == "2017101033"
    assert record.has_human_title is False
    assert record.requires_detail_enrichment is True
    assert record.warnings == ("SCH mismatch: result=2017101033 detail=2026060698",)


def test_enrich_ceqanet_result_records_matches_details_by_sch_number() -> None:
    report = enrich_ceqanet_result_records([_sch_only_result()], [_detail_parse()])

    assert report.record_count == 1
    assert report.enriched_count == 1
    assert report.missing_detail_count == 0
    assert report.sch_mismatch_count == 0
    assert report.records[0].title == "San Bernardino Countywide Plan"


def test_enrich_ceqanet_result_records_serializes_report() -> None:
    payload = enrich_ceqanet_result_records([_sch_only_result()], [_detail_parse()]).to_dict()

    assert payload["metadata"]["schema_version"] == "ceqanet_detail_enrichment.v1"
    assert payload["metadata"]["record_count"] == 1
    assert payload["metadata"]["enriched_count"] == 1
    assert payload["records"][0]["title"] == "San Bernardino Countywide Plan"
    assert payload["records"][0]["field_sources"]["title"] == "detail_page"


def test_enrich_ceqanet_result_record_preserves_result_only_detail_fields() -> None:
    result = _sch_only_result()
    result["project_location"] = "Redlands, California"
    result["project_description"] = "Warehouse and site work."
    result["contact"] = "Planning Department"

    record = enrich_ceqanet_result_record(result, None)

    assert record.enrichment_status == "missing_detail"
    assert record.project_location == "Redlands, California"
    assert record.project_description == "Warehouse and site work."
    assert record.contact == "Planning Department"
    assert record.field_sources["project_location"] == "result_page"
    assert record.field_sources["project_description"] == "result_page"
    assert record.field_sources["contact"] == "result_page"
