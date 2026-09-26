import pytest
from sqlalchemy import func, select

from constructionsight.ceqanet_persistence_execute import execute_ceqanet_write_plan
from constructionsight.storage.database import (
    create_database_engine,
    initialize_database,
)
from constructionsight.storage.domain_orm import (
    CeqaDomainRecord,
    EntityRecord,
    SiteRecord,
)


def _write_plan() -> dict[str, object]:
    return {
        "metadata": {
            "schema_version": "ceqanet_write_plan.v1",
            "operation_count": 3,
            "skipped_item_count": 0,
            "network_executed": False,
            "database_opened": False,
            "persistence_mutated": False,
        },
        "operations": [
            {
                "operation_id": "sites:site:ceqanet:2017101033",
                "action": "upsert_preview",
                "target_collection": "sites",
                "target_key": "site:ceqanet:2017101033",
                "source_index": 0,
                "payload": {
                    "site_key": "site:ceqanet:2017101033",
                    "county": "San Bernardino",
                    "city": "San Bernardino",
                },
            },
            {
                "operation_id": "entities:entity:ceqanet:lead-agency:san-bernardino-county",
                "action": "upsert_preview",
                "target_collection": "entities",
                "target_key": "entity:ceqanet:lead-agency:san-bernardino-county",
                "source_index": 0,
                "payload": {
                    "entity_key": "entity:ceqanet:lead-agency:san-bernardino-county",
                    "name": "San Bernardino County",
                    "role": "agency",
                    "county": "San Bernardino",
                },
            },
            {
                "operation_id": "ceqa_records:ceqa:ceqanet:2017101033",
                "action": "upsert_preview",
                "target_collection": "ceqa_records",
                "target_key": "ceqa:ceqanet:2017101033",
                "source_index": 0,
                "payload": {
                    "ceqa_key": "ceqa:ceqanet:2017101033",
                    "title": "San Bernardino Countywide Plan",
                    "county": "San Bernardino",
                    "lead_agency": "San Bernardino County",
                    "state_clearinghouse_number": "2017101033",
                    "description": "Countywide policy plan.",
                },
            },
        ],
        "skipped_items": [],
    }


def test_execute_ceqanet_write_plan_persists_domain_records_atomically() -> None:
    engine = create_database_engine("sqlite+pysqlite:///:memory:")
    result = execute_ceqanet_write_plan(_write_plan(), engine=engine)
    payload = result.to_dict()

    assert payload["metadata"]["schema_version"] == "ceqanet_persistence_execution.v2"
    assert payload["metadata"]["transactional"] is True
    assert payload["metadata"]["applied_count"] == 3
    assert payload["metadata"]["failed_count"] == 0
    assert payload["metadata"]["skipped_count"] == 0
    assert payload["metadata"]["counts_by_target"] == {
        "ceqa_records": 1,
        "sites": 1,
        "entities": 1,
    }
    assert payload["metadata"]["network_executed"] is False
    assert payload["metadata"]["database_opened"] is True
    assert payload["metadata"]["persistence_mutated"] is True

    with engine.connect() as connection:
        assert connection.scalar(select(SiteRecord.site_key)) == "site:ceqanet:2017101033"
        assert connection.scalar(select(EntityRecord.entity_key)) == (
            "entity:ceqanet:lead-agency:san-bernardino-county"
        )
        assert connection.scalar(select(CeqaDomainRecord.ceqa_key)) == "ceqa:ceqanet:2017101033"


def test_execute_ceqanet_write_plan_updates_existing_records() -> None:
    engine = create_database_engine("sqlite+pysqlite:///:memory:")
    execute_ceqanet_write_plan(_write_plan(), engine=engine)
    plan = _write_plan()
    operations = plan["operations"]
    assert isinstance(operations, list)
    operations[2]["payload"]["title"] = "Updated Countywide Plan"

    result = execute_ceqanet_write_plan(plan, engine=engine, initialize=False)

    assert result.applied_count == 3
    with engine.connect() as connection:
        assert connection.scalar(select(CeqaDomainRecord.title)) == "Updated Countywide Plan"


def test_invalid_operation_blocks_entire_plan_before_any_commit() -> None:
    engine = create_database_engine("sqlite+pysqlite:///:memory:")
    initialize_database(engine)
    plan = _write_plan()
    operations = plan["operations"]
    assert isinstance(operations, list)
    operations.append(
        {
            "operation_id": "bad-target",
            "action": "upsert_preview",
            "target_collection": "unknown",
            "target_key": "unknown",
            "source_index": 99,
            "payload": {},
        }
    )
    metadata = plan["metadata"]
    assert isinstance(metadata, dict)
    metadata["operation_count"] = len(operations)

    with pytest.raises(ValueError, match="unsupported target_collection"):
        execute_ceqanet_write_plan(plan, engine=engine, initialize=False)

    with engine.connect() as connection:
        assert connection.scalar(select(func.count()).select_from(SiteRecord)) == 0
        assert connection.scalar(select(func.count()).select_from(EntityRecord)) == 0
        assert connection.scalar(select(func.count()).select_from(CeqaDomainRecord)) == 0


def test_invalid_payload_blocks_entire_plan_before_any_commit() -> None:
    engine = create_database_engine("sqlite+pysqlite:///:memory:")
    initialize_database(engine)
    plan = _write_plan()
    operations = plan["operations"]
    assert isinstance(operations, list)
    operations[1]["payload"] = {"county": "San Bernardino"}

    with pytest.raises(ValueError, match="payload is invalid"):
        execute_ceqanet_write_plan(plan, engine=engine, initialize=False)

    with engine.connect() as connection:
        assert connection.scalar(select(func.count()).select_from(SiteRecord)) == 0
        assert connection.scalar(select(func.count()).select_from(EntityRecord)) == 0
        assert connection.scalar(select(func.count()).select_from(CeqaDomainRecord)) == 0


def test_execute_ceqanet_write_plan_rejects_bad_schema() -> None:
    engine = create_database_engine("sqlite+pysqlite:///:memory:")

    with pytest.raises(ValueError, match="ceqanet_write_plan.v1"):
        execute_ceqanet_write_plan(
            {"metadata": {"schema_version": "wrong.v1"}},
            engine=engine,
        )


def test_execute_ceqanet_write_plan_rejects_count_drift() -> None:
    engine = create_database_engine("sqlite+pysqlite:///:memory:")
    plan = _write_plan()
    metadata = plan["metadata"]
    assert isinstance(metadata, dict)
    metadata["operation_count"] = 2

    with pytest.raises(ValueError, match="operation_count"):
        execute_ceqanet_write_plan(plan, engine=engine)


def test_execute_ceqanet_write_plan_can_use_preinitialized_database() -> None:
    engine = create_database_engine("sqlite+pysqlite:///:memory:")
    initialize_database(engine)

    result = execute_ceqanet_write_plan(_write_plan(), engine=engine, initialize=False)

    assert result.applied_count == 3


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("target_key", "site:tampered", "target_key does not match payload"),
        ("operation_id", "sites:site:tampered", "canonical target identity"),
        ("source_index", 7, "source_index must equal 0"),
    ],
)
# Regression: CS-SR-086
def test_tampered_operation_identity_blocks_plan_before_commit(
    field: str,
    value: object,
    message: str,
) -> None:
    engine = create_database_engine("sqlite+pysqlite:///:memory:")
    initialize_database(engine)
    plan = _write_plan()
    operations = plan["operations"]
    assert isinstance(operations, list)
    operation = operations[0]
    assert isinstance(operation, dict)
    operation[field] = value

    with pytest.raises(ValueError, match=message):
        execute_ceqanet_write_plan(plan, engine=engine, initialize=False)

    with engine.connect() as connection:
        assert connection.scalar(select(func.count()).select_from(SiteRecord)) == 0
        assert connection.scalar(select(func.count()).select_from(EntityRecord)) == 0
        assert connection.scalar(select(func.count()).select_from(CeqaDomainRecord)) == 0
