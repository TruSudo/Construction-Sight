from sqlalchemy import inspect

from constructionsight.storage.database import create_database_engine, initialize_database


def test_domain_orm_tables_are_created() -> None:
    engine = create_database_engine("sqlite+pysqlite:///:memory:")
    initialize_database(engine)

    table_names = set(inspect(engine).get_table_names())

    assert "domain_sites" in table_names
    assert "domain_entities" in table_names
    assert "domain_permits" in table_names
    assert "domain_planning_cases" in table_names


def test_domain_orm_tables_have_expected_key_columns() -> None:
    engine = create_database_engine("sqlite+pysqlite:///:memory:")
    initialize_database(engine)
    inspector = inspect(engine)

    site_columns = {column["name"] for column in inspector.get_columns("domain_sites")}
    entity_columns = {column["name"] for column in inspector.get_columns("domain_entities")}
    permit_columns = {column["name"] for column in inspector.get_columns("domain_permits")}
    planning_columns = {column["name"] for column in inspector.get_columns("domain_planning_cases")}

    assert {"site_key", "county", "apn", "provenance_json"}.issubset(site_columns)
    assert {"entity_key", "name", "role", "provenance_json"}.issubset(entity_columns)
    assert {"permit_key", "permit_number", "status", "site_json"}.issubset(permit_columns)
    assert {"case_key", "case_number", "hearing_date", "site_json"}.issubset(planning_columns)
