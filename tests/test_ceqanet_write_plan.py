import pytest

from constructionsight.ceqanet_write_plan import build_ceqanet_write_plan


def _preview_payload() -> dict[str, object]:
    return {
        "metadata": {
            "schema_version": "ceqanet_persistence_preview.v1",
            "ceqa_record_count": 1,
            "site_count": 1,
            "entity_count": 1,
            "skipped_record_count": 0,
            "planned_write_count": 3,
            "network_executed": False,
            "persistence_mutated": False,
        },
        "ceqa_records": [
            {
                "ceqa_key": "ceqa:ceqanet:2017101033",
                "title": "San Bernardino Countywide Plan",
                "state_clearinghouse_number": "2017101033",
            }
        ],
        "sites": [
            {
                "site_key": "site:ceqanet:2017101033",
                "county": "San Bernardino",
            }
        ],
        "entities": [
            {
                "entity_key": "entity:ceqanet:lead-agency:san-bernardino-county",
                "name": "San Bernardino County",
                "role": "agency",
            }
        ],
        "skipped_records": [],
    }


def test_build_ceqanet_write_plan_creates_operations() -> None:
    plan = build_ceqanet_write_plan(_preview_payload())
    payload = plan.to_dict()

    assert payload["metadata"]["schema_version"] == "ceqanet_write_plan.v1"
    assert payload["metadata"]["operation_count"] == 3
    assert payload["metadata"]["skipped_item_count"] == 0
    assert payload["metadata"]["counts_by_target"] == {
        "ceqa_records": 1,
        "sites": 1,
        "entities": 1,
    }
    assert payload["metadata"]["network_executed"] is False
    assert payload["metadata"]["database_opened"] is False
    assert payload["metadata"]["persistence_mutated"] is False

    operations = payload["operations"]
    assert operations[0]["operation_id"] == "ceqa_records:ceqa:ceqanet:2017101033"
    assert operations[0]["action"] == "upsert_preview"
    assert operations[0]["target_collection"] == "ceqa_records"
    assert operations[0]["target_key"] == "ceqa:ceqanet:2017101033"
    assert operations[1]["target_collection"] == "sites"
    assert operations[2]["target_collection"] == "entities"


def test_build_ceqanet_write_plan_tracks_skipped_items() -> None:
    preview = _preview_payload()
    ceqa_records = preview["ceqa_records"]
    assert isinstance(ceqa_records, list)
    ceqa_records.append({"title": "Missing key"})
    ceqa_records.append("not an object")

    payload = build_ceqanet_write_plan(preview).to_dict()

    assert payload["metadata"]["operation_count"] == 3
    assert payload["metadata"]["skipped_item_count"] == 2
    assert payload["skipped_items"][0]["reason"] == "missing ceqa_key"
    assert payload["skipped_items"][1]["reason"] == "item is not an object"


def test_build_ceqanet_write_plan_rejects_missing_metadata() -> None:
    with pytest.raises(ValueError, match="must contain metadata"):
        build_ceqanet_write_plan({})


def test_build_ceqanet_write_plan_rejects_wrong_schema() -> None:
    with pytest.raises(ValueError, match="schema_version"):
        build_ceqanet_write_plan({"metadata": {"schema_version": "wrong.v1"}})


def test_build_ceqanet_write_plan_rejects_missing_collection() -> None:
    preview = _preview_payload()
    del preview["sites"]

    with pytest.raises(ValueError, match="must contain sites list"):
        build_ceqanet_write_plan(preview)
