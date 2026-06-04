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
    assert "domain_ceqa_records" in table_names
    assert "domain_agenda_items" in table_names
    assert "domain_documents" in table_names
    assert "domain_relationships" in table_names


def test_domain_orm_tables_have_expected_key_columns() -> None:
    engine = create_database_engine("sqlite+pysqlite:///:memory:")
    initialize_database(engine)
    inspector = inspect(engine)

    site_columns = {column["name"] for column in inspector.get_columns("domain_sites")}
    entity_columns = {column["name"] for column in inspector.get_columns("domain_entities")}
    permit_columns = {column["name"] for column in inspector.get_columns("domain_permits")}
    planning_columns = {column["name"] for column in inspector.get_columns("domain_planning_cases")}
    ceqa_columns = {column["name"] for column in inspector.get_columns("domain_ceqa_records")}
    agenda_columns = {column["name"] for column in inspector.get_columns("domain_agenda_items")}
    document_columns = {column["name"] for column in inspector.get_columns("domain_documents")}
    relationship_columns = {
        column["name"] for column in inspector.get_columns("domain_relationships")
    }

    assert {"site_key", "county", "apn", "provenance_json"}.issubset(site_columns)
    assert {"entity_key", "name", "role", "provenance_json"}.issubset(entity_columns)
    assert {"permit_key", "permit_number", "status", "site_json"}.issubset(permit_columns)
    assert {"case_key", "case_number", "hearing_date", "site_json"}.issubset(planning_columns)
    assert {"ceqa_key", "title", "document_type", "provenance_json"}.issubset(ceqa_columns)
    assert {"agenda_key", "meeting_body", "document_urls_json", "site_json"}.issubset(
        agenda_columns
    )
    assert {"document_key", "source_name", "text_extract", "provenance_json"}.issubset(
        document_columns
    )
    assert {"relationship_key", "subject_key", "relationship_type", "object_key"}.issubset(
        relationship_columns
    )
