import json

import pytest
from sqlalchemy import select
from typer.testing import CliRunner

from constructionsight.storage.database import (
    create_database_engine,
    initialize_database,
    managed_session,
    session_factory,
)
from constructionsight.storage.movement_identity_orm import (
    ContractorIdentityRecord,
    DecisionRecordRow,
    PermitSnapshotRecord,
    PermitTransitionRecord,
)
from constructionsight.storage.parcel_site_orm import (
    ParcelAssuranceReportRow,
    ParcelCoreRecordRow,
    SiteResolutionResultRow,
)
from constructionsight.upstream_operator_cli import app
from constructionsight.upstream_operator_models import UpstreamOperatorRecordKind
from constructionsight.upstream_operator_service import (
    UpstreamOperatorError,
    get_upstream_operator_record,
    list_upstream_operator_records,
)


def _database_url(tmp_path) -> str:
    return f"sqlite:///{tmp_path / 'upstream-operator.sqlite3'}"


def _factory(database_url: str):
    engine = create_database_engine(database_url)
    initialize_database(engine)
    return session_factory(engine)


def _seed(database_url: str) -> None:
    factory = _factory(database_url)
    with managed_session(factory) as session:
        session.add_all(
            [
                PermitSnapshotRecord(
                    snapshot_id="permit-snapshot:test",
                    source_key="source:test",
                    source_record_id="permit:test",
                    permit_number="P-100",
                    status="issued",
                    site_key="site:test",
                    observed_at="2026-07-11T00:00:00+00:00",
                    payload_json=json.dumps(
                        {
                            "snapshot_id": "permit-snapshot:test",
                            "reasons": ["source record observed"],
                            "limitations": ["inspection history unavailable"],
                        }
                    ),
                ),
                PermitTransitionRecord(
                    transition_id="permit-transition:test",
                    transition_kind="status_changed",
                    source_key="source:test",
                    source_record_id="permit:test",
                    field_name="status",
                    opportunity_relevant=True,
                    detected_at="2026-07-11T01:00:00+00:00",
                    payload_json=json.dumps(
                        {
                            "transition_id": "permit-transition:test",
                            "previous_value": "submitted",
                            "current_value": "issued",
                            "limitations": [],
                        }
                    ),
                ),
                ContractorIdentityRecord(
                    contractor_key="contractor:test",
                    display_name="Test Construction LLC",
                    normalized_name="test construction llc",
                    source_kind="permit",
                    status="candidate",
                    confidence_score=72,
                    payload_json=json.dumps(
                        {
                            "contractor_key": "contractor:test",
                            "reasons": ["normalized name match"],
                            "limitations": ["license not independently verified"],
                        }
                    ),
                ),
                DecisionRecordRow(
                    decision_key="decision:test",
                    source_key="source:test",
                    source_record_id="decision-source:test",
                    source_kind="agenda",
                    decision_kind="planning_hearing",
                    site_key="site:test",
                    apn="0123-456-78",
                    confidence_score=64,
                    payload_json=json.dumps(
                        {
                            "decision_key": "decision:test",
                            "title": "Test Commerce Center",
                            "reasons": ["agenda item references project site"],
                            "limitations": ["applicant identity requires review"],
                        }
                    ),
                ),
                ParcelCoreRecordRow(
                    parcel_record_id="parcel:test",
                    source_key="parcel-source:test",
                    source_record_id="parcel-source-record:test",
                    apn="0123-456-78",
                    normalized_apn="012345678",
                    county="San Bernardino",
                    state="CA",
                    address="100 Test Avenue",
                    normalized_address="100 test avenue",
                    jurisdiction="Test City",
                    observed_created_at="2026-07-11T02:00:00+00:00",
                    payload_json=json.dumps(
                        {
                            "parcel_record_id": "parcel:test",
                            "apn": "0123-456-78",
                            "reasons": ["canonical parcel row"],
                            "limitations": ["geometry unavailable"],
                        }
                    ),
                ),
                ParcelAssuranceReportRow(
                    report_id="parcel-assurance:test",
                    normalized_apn="012345678",
                    county="San Bernardino",
                    review_status="incomplete",
                    requires_human_review=False,
                    source_count=1,
                    independent_lineage_count=1,
                    claim_count=1,
                    conflict_count=0,
                    missing_count=1,
                    observed_created_at="2026-07-11T02:30:00+00:00",
                    payload_json=json.dumps(
                        {
                            "report_id": "parcel-assurance:test",
                            "review_status": "incomplete",
                            "claims": [
                                {
                                    "claim_id": "parcel-claim:test",
                                    "source_key": "parcel-source:test",
                                    "lineage_key": "county-assessor-roll",
                                }
                            ],
                            "field_assurances": [{"field_role": "owner", "status": "missing"}],
                            "limitations": ["current supplied records only"],
                        }
                    ),
                ),
                SiteResolutionResultRow(
                    resolution_id="site-resolution:test",
                    source_name="test source",
                    evidence_id="evidence:test",
                    status="resolved",
                    primary_site_key="site:test",
                    candidate_count=1,
                    conflict_count=0,
                    limitation_count=1,
                    observed_created_at="2026-07-11T03:00:00+00:00",
                    payload_json=json.dumps(
                        {
                            "resolution_id": "site-resolution:test",
                            "primary_site_key": "site:test",
                            "reasons": ["APN exact match"],
                            "limitations": ["geometry confirmation unavailable"],
                        }
                    ),
                ),
            ]
        )


@pytest.mark.parametrize(
    ("record_kind", "record_id"),
    [
        (UpstreamOperatorRecordKind.PERMIT_SNAPSHOT, "permit-snapshot:test"),
        (UpstreamOperatorRecordKind.PERMIT_TRANSITION, "permit-transition:test"),
        (UpstreamOperatorRecordKind.CONTRACTOR, "contractor:test"),
        (UpstreamOperatorRecordKind.DECISION, "decision:test"),
        (UpstreamOperatorRecordKind.PARCEL, "parcel:test"),
        (
            UpstreamOperatorRecordKind.PARCEL_ASSURANCE,
            "parcel-assurance:test",
        ),
        (UpstreamOperatorRecordKind.SITE_RESOLUTION, "site-resolution:test"),
    ],
)
def test_detail_supports_each_record_family(tmp_path, record_kind, record_id) -> None:
    database_url = _database_url(tmp_path)
    _seed(database_url)
    factory = _factory(database_url)

    with managed_session(factory) as session:
        record = get_upstream_operator_record(session, record_kind, record_id)

    assert record is not None
    assert record.record_id == record_id
    assert "limitations" in record.payload


def test_parcel_list_filters_and_preserves_payload(tmp_path) -> None:
    database_url = _database_url(tmp_path)
    _seed(database_url)
    factory = _factory(database_url)

    with managed_session(factory) as session:
        records = list_upstream_operator_records(
            session,
            UpstreamOperatorRecordKind.PARCEL,
            source_key="parcel-source:test",
            apn="0123-456-78",
            county="San Bernardino",
        )

    assert len(records) == 1
    assert records[0].record_id == "parcel:test"
    assert records[0].payload["limitations"] == ["geometry unavailable"]


def test_parcel_assurance_list_filters_and_preserves_claims(tmp_path) -> None:
    database_url = _database_url(tmp_path)
    _seed(database_url)
    factory = _factory(database_url)

    with managed_session(factory) as session:
        records = list_upstream_operator_records(
            session,
            UpstreamOperatorRecordKind.PARCEL_ASSURANCE,
            status="incomplete",
            apn="012345678",
            county="San Bernardino",
        )

    assert len(records) == 1
    assert records[0].record_id == "parcel-assurance:test"
    assert records[0].status == "incomplete"
    assert records[0].payload["claims"][0]["lineage_key"] == "county-assessor-roll"


def test_list_rejects_unsupported_filter(tmp_path) -> None:
    database_url = _database_url(tmp_path)
    factory = _factory(database_url)

    with (
        managed_session(factory) as session,
        pytest.raises(UpstreamOperatorError, match="unsupported filter"),
    ):
        list_upstream_operator_records(
            session,
            UpstreamOperatorRecordKind.CONTRACTOR,
            county="San Bernardino",
        )


def test_detail_rejects_malformed_preserved_payload(tmp_path) -> None:
    database_url = _database_url(tmp_path)
    _seed(database_url)
    factory = _factory(database_url)

    with managed_session(factory) as session:
        row = session.execute(select(ContractorIdentityRecord)).scalar_one()
        row.payload_json = "["

    with (
        managed_session(factory) as session,
        pytest.raises(UpstreamOperatorError, match="malformed contractor payload"),
    ):
        get_upstream_operator_record(
            session,
            UpstreamOperatorRecordKind.CONTRACTOR,
            "contractor:test",
        )


def test_list_cli_outputs_machine_readable_decision_payload(tmp_path) -> None:
    database_url = _database_url(tmp_path)
    _seed(database_url)
    runner = CliRunner()

    result = runner.invoke(
        app,
        [
            "list",
            "decision",
            "--database-url",
            database_url,
            "--site-key",
            "site:test",
            "--json-output",
        ],
    )

    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload[0]["record_id"] == "decision:test"
    assert payload[0]["payload"]["limitations"] == ["applicant identity requires review"]


def test_list_cli_outputs_parcel_assurance_payload(tmp_path) -> None:
    database_url = _database_url(tmp_path)
    _seed(database_url)
    runner = CliRunner()

    result = runner.invoke(
        app,
        [
            "list",
            "parcel_assurance",
            "--database-url",
            database_url,
            "--status",
            "incomplete",
            "--apn",
            "012345678",
            "--json-output",
        ],
    )

    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload[0]["record_id"] == "parcel-assurance:test"
    assert payload[0]["payload"]["field_assurances"][0]["status"] == "missing"


def test_detail_cli_reports_missing_record(tmp_path) -> None:
    database_url = _database_url(tmp_path)
    runner = CliRunner()

    result = runner.invoke(
        app,
        [
            "detail",
            "parcel",
            "parcel:missing",
            "--database-url",
            database_url,
            "--json-output",
        ],
    )

    assert result.exit_code == 2
    assert "parcel record not found: parcel:missing" in result.stderr
