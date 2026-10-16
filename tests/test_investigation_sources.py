import hashlib
import json
import sqlite3
from datetime import UTC, datetime

import pytest

from constructionsight.ceqa_models import CeqaRecord
from constructionsight.domain_types import PartyRole
from constructionsight.entity_models import Entity
from constructionsight.intelligence.artifact_identity import IdentityArtifactType as Artifact
from constructionsight.intelligence.investigation_query_service import InvestigationQueryService
from constructionsight.intelligence.investigation_service import InvestigationService
from constructionsight.intelligence.investigation_sources import (
    from_domain,
    from_parcel,
    from_smarts,
)
from constructionsight.intelligence.schemas import LifecyclePhase, RelationshipStatus
from constructionsight.investigation_cli import main
from constructionsight.parcel_core_models import ParcelCoreRecord
from constructionsight.permit_models import PermitRecord
from constructionsight.provenance import Provenance
from constructionsight.site_models import Site
from constructionsight.smarts_api import RESOURCE_IDS, SmartsPage
from constructionsight.smarts_evidence_ledger import (
    SmartsEvidenceError,
    read_smarts_observations,
    record_smarts_page,
)
from constructionsight.storage.database import (
    create_database_engine,
    initialize_database,
    managed_session,
    session_factory,
)
from constructionsight.storage.intelligence_store import IntelligenceStore

AT = datetime(2026, 10, 16, tzinfo=UTC)


def test_existing_contractor_assessment_is_retained_without_merging_or_verifying_license(tmp_path):
    record = PermitRecord(
        permit_key="permit:contractor",
        permit_number="BLD-1",
        county="Riverside",
        jurisdiction="Test city",
        entities=[
            Entity(
                entity_key="party:contractor",
                name="Synthetic Contractor",
                role=PartyRole.CONTRACTOR,
                license_number="1234567",
            )
        ],
        provenance=[
            Provenance(
                source_name="Synthetic permit portal",
                captured_at=AT,
                evidence_text="Synthetic retained permit record",
            )
        ],
    )
    item = from_domain(record)
    engine = create_database_engine(f"sqlite+pysqlite:///{tmp_path / 'contractors.sqlite3'}")
    initialize_database(engine)
    with managed_session(session_factory(engine)) as session:
        store = IntelligenceStore(session)
        service = InvestigationService(store)
        service.ingest(item)
        cursor = store.runtime_event_cursor()
        dossier = InvestigationQueryService(store).dossier(item.investigation_id)
        party = dossier["source_parties"][0]
        assert party["entity"]["entity_type"] == "contractor"
        assert party["entity"]["identifiers"]["source_claimed_license_number"] == "1234567"
        assert party["contractor_assessment"]["accepted_entity_merge"] is False
        assert party["contractor_assessment"]["license_independently_verified"] is False
        assert party["contractor_assessment"]["candidate"]["status"] == "unknown"
        service.ingest(item)
        assert store.runtime_event_cursor() == cursor
    engine.dispose()


def source_journal(tmp_path):
    directory = tmp_path / "private"
    directory.mkdir(mode=0o700)
    path = directory / "evidence.sqlite3"
    row = {
        "APP_ID": "100",
        "WDID": "8 33C123456",
        "SITE_COUNTY": "Riverside",
        "SITE_NAME": "Synthetic test site",
        "SITE_ADDRESS": "123 Main St",
        "SITE_LATITUDE": "33.9",
        "SITE_LONGITUDE": "-117.2",
        "STATUS": "Active",
    }
    body = json.dumps(
        {
            "success": True,
            "result": {
                "resource_id": RESOURCE_IDS["facilities"],
                "total": 1,
                "records": [row],
            },
        }
    ).encode()
    page = SmartsPage(
        resource="facilities",
        county="Riverside",
        offset=0,
        limit=100,
        total=1,
        request_url="https://publish.data.ca.gov/api/3/action/datastore_search?test=fixture",
        response_sha256=hashlib.sha256(body).hexdigest(),
        fields=tuple(row),
        records=(row,),
        raw_response_bytes=body,
    )
    record_smarts_page(path, page)
    return path


def test_smarts_reader_reuses_source_checks_without_modifying_original(tmp_path):
    source = source_journal(tmp_path)
    before = source.read_bytes()
    retained = read_smarts_observations(source, limit=1)
    item = from_smarts(retained[0])
    assert item.evidence.raw_observations["response_sha256"] == retained[0].page.response_sha256
    assert item.evidence.source_record_id == retained[0].source_key
    assert item.latitude == 33.9 and item.longitude == -117.2
    assert source.read_bytes() == before
    assert read_smarts_observations(source, after_id=retained[0].observation_id) == []
    with pytest.raises(ValueError, match="between 1 and 500"):
        read_smarts_observations(source, limit=501)


@pytest.mark.parametrize("table", ["smarts_aliases", "smarts_observations"])
def test_smarts_reader_rejects_tampered_response_and_alias_binding(tmp_path, table):
    source = source_journal(tmp_path)
    with sqlite3.connect(source) as connection:
        trigger = f"{table}_no_update"
        sql = connection.execute(
            "SELECT sql FROM sqlite_master WHERE type='trigger' AND name=?", (trigger,)
        ).fetchone()[0]
        # Controlled corruption beyond ordinary immutability enforcement.
        connection.execute(f"DROP TRIGGER {trigger}")
        if table == "smarts_aliases":
            connection.execute("UPDATE smarts_aliases SET source_key='different-source'")
        else:
            connection.execute("UPDATE smarts_observations SET raw_response=?", (b"{}",))
        connection.execute(sql)
    with pytest.raises(SmartsEvidenceError, match="exact-source validation"):
        read_smarts_observations(source)


def test_domain_and_parcel_normalizers_preserve_source_specific_claims(tmp_path):
    provenance = [
        Provenance(
            source_name="Synthetic government source",
            captured_at=AT,
            evidence_text="Synthetic retained test record",
        )
    ]
    site = Site(site_key="site:test", county="Riverside", apn="123-456-789", address="123 Main St")
    party = Entity(entity_key="party:test", name="Synthetic Developer", role=PartyRole.DEVELOPER)
    ceqa = CeqaRecord(
        ceqa_key="ceqa:test",
        title="Synthetic project",
        county="Riverside",
        state_clearinghouse_number="2026010001",
        site=site,
        entities=[party],
        provenance=provenance,
    )
    permit = PermitRecord(
        permit_key="permit:test",
        permit_number="BLD-1",
        county="Riverside",
        jurisdiction="Test city",
        status="Issued",
        site=site,
        provenance=provenance,
    )
    parcel = ParcelCoreRecord(
        parcel_record_id="parcel:test",
        source_key="parcel:test",
        apn=site.apn,
        normalized_apn="123456789",
        county="Riverside",
        created_at=AT,
    )
    observations = [from_domain(ceqa), from_domain(permit), from_parcel(parcel)]
    assert observations[0].artifacts[Artifact.CEQA_SCH_NUMBER] == ["2026010001"]
    assert (
        observations[1].evidence.raw_observations["normalized_source_record"]["status"] == "Issued"
    )
    assert all(item.latitude is None for item in observations)
    engine = create_database_engine(f"sqlite+pysqlite:///{tmp_path / 'shared.sqlite3'}")
    initialize_database(engine)
    with managed_session(session_factory(engine)) as session:
        store = IntelligenceStore(session)
        service = InvestigationService(store)
        for item in observations:
            cluster = service.ingest(item)
            assert cluster.lifecycle_phase == LifecyclePhase.UNKNOWN
        roles = [r for r in store.list_relationships() if r.predicate == "source_claimed_developer"]
        assert len(roles) == 1
        assert roles[0].relationship_status == RelationshipStatus.POSSIBLE
        assert len(store.list_project_clusters()) == 3
    engine.dispose()
    with pytest.raises(ValueError, match="captured provenance"):
        from_domain(ceqa.model_copy(update={"provenance": []}))


def test_cli_replays_into_shared_store_idempotently_and_keeps_source_bytes(tmp_path, capsys):
    source = source_journal(tmp_path)
    original = source.read_bytes()
    destination = tmp_path / "target" / "investigations.sqlite3"
    args = ["--database", str(destination), "--source", str(source), "--kind", "smarts-journal"]
    assert main(args) == 0
    first = json.loads(capsys.readouterr().out)
    with sqlite3.connect(destination) as connection:
        counts = [
            connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            for table in ("intelligence_evidence_records", "intelligence_runtime_events")
        ]
    assert main(args) == 0
    second = json.loads(capsys.readouterr().out)
    assert first["investigation_ids"] == second["investigation_ids"]
    assert first["network_executed"] is False
    assert first["identity_verified"] is False
    assert source.read_bytes() == original
    assert destination.stat().st_mode & 0o777 == 0o600
    database_bytes = destination.read_bytes()
    assert main(["--database", str(destination), "--show", first["investigation_ids"][0]]) == 0
    dossier = json.loads(capsys.readouterr().out)
    assert dossier["investigation"]["project_cluster_id"] == first["investigation_ids"][0]
    assert dossier["source_claimed_points"][0]["certainty"] == "source_claimed"
    assert destination.read_bytes() == database_bytes
    with sqlite3.connect(destination) as connection:
        assert counts == [
            connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            for table in ("intelligence_evidence_records", "intelligence_runtime_events")
        ]
        assert (
            connection.execute("SELECT COUNT(*) FROM intelligence_project_clusters").fetchone()[0]
            == 1
        )
