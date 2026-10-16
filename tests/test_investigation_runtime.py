"""Real worker transactions with explicitly synthetic retained-source fixtures."""

import hashlib
import json
from datetime import UTC, datetime

import pytest

import constructionsight.data_folder as data_folder
from constructionsight.data_folder import make_backup, preview_restore
from constructionsight.intelligence.investigation_query_service import InvestigationQueryService
from constructionsight.intelligence.schemas import RelationshipStatus
from constructionsight.investigation_runtime import (
    InvestigationRuntime,
    main,
    retain_input,
    systemd_units,
)
from constructionsight.parcel_core_models import ParcelCoreRecord
from constructionsight.permit_models import PermitRecord
from constructionsight.provenance import Provenance
from constructionsight.site_models import Site
from constructionsight.smarts_api import RESOURCE_IDS, SmartsPage
from constructionsight.smarts_evidence_ledger import record_smarts_page
from constructionsight.storage.database import managed_session
from constructionsight.storage.intelligence_store import IntelligenceStore


def source(tmp_path, *, count=1, key="permit", apn="123-456-789"):
    records = [
        PermitRecord(
            permit_key=f"{key}:{index}",
            permit_number=f"BLD-{index}",
            jurisdiction="Synthetic city",
            county="Riverside",
            site=Site(site_key=f"site:{key}:{index}", county="Riverside", apn=apn),
            provenance=[
                Provenance(
                    source_name="Synthetic permit portal",
                    captured_at=datetime(2026, 10, 16, tzinfo=UTC),
                )
            ],
        ).model_dump(mode="json", round_trip=True)
        for index in range(count)
    ]
    path = tmp_path / f"{key}.json"
    path.write_text(json.dumps(records))
    return path


def drain(runtime, *, maximum=100):
    states = []
    for _ in range(maximum):
        state = runtime.run_once("synthetic-worker")
        if state is None:
            return states
        assert state.status == "completed", state.model_dump()
        states.append(state)
    pytest.fail("worker did not reach its bounded idle state")


def test_worker_restart_preserves_exact_input_and_updates_shared_investigations(tmp_path):
    path = source(tmp_path, count=2)
    original = path.read_bytes()
    directory = tmp_path / "private"
    runtime = InvestigationRuntime(directory)
    job = runtime.enqueue_json(path, "permit")
    runtime.close()
    path.unlink()  # Worker must use retained inputs, never a later version of the import.
    runtime = InvestigationRuntime(directory)
    try:
        states = drain(runtime)
        assert states[0].job_id == job.job_id
        assert states[0].result["processed"] == 2
        with managed_session(runtime.queue.factory) as session:
            store = IntelligenceStore(session)
            query = InvestigationQueryService(store)
            inventory = query.inventory()
            assert inventory["total"] == 2
            relations = [
                r
                for r in store.list_relationships()
                if r.predicate == "possible_same_project_requires_review"
            ]
            assert len(relations) == 1
            assert relations[0].relationship_status in {
                RelationshipStatus.POSSIBLE,
                RelationshipStatus.PROBABLE,
            }
            for row in inventory["rows"]:
                dossier = query.dossier(row["investigation_id"])
                assert dossier["assessment"]["identity_independently_verified"] is False
                assert dossier["assessment"]["commercial_authority_granted"] is False
            cursor = store.runtime_event_cursor()
        assert (
            directory / "investigation-inputs" / hashlib.sha256(original).hexdigest()
        ).read_bytes() == original
        # Re-enqueue and restart do not create work, facts or fake activity.
        path.write_bytes(original)
        assert runtime.enqueue_json(path, "permit").status == "completed"
        assert runtime.run_once("second-worker") is None
        with managed_session(runtime.queue.factory) as session:
            assert IntelligenceStore(session).runtime_event_cursor() == cursor
    finally:
        runtime.close()


def test_invalid_or_tampered_input_is_preserved_and_never_published(tmp_path):
    runtime = InvestigationRuntime(tmp_path / "private")
    try:
        broken = tmp_path / "invalid.json"
        broken.write_bytes(b"not JSON")
        with pytest.raises(ValueError):
            runtime.enqueue_json(broken, "permit")
        assert (
            runtime.directory
            / "investigation-inputs"
            / hashlib.sha256(broken.read_bytes()).hexdigest()
        ).read_bytes() == broken.read_bytes()
        assert runtime.queue.list_jobs() == []
        path = source(tmp_path)
        state = runtime.enqueue_json(path, "permit")
        retained = runtime.directory / state.definition.inputs["input"]["relative_path"]
        retained.write_bytes(b"{}")  # Controlled disk corruption.
        failed = runtime.run_once("worker")
        assert failed.status == "failed"
        assert failed.error_code == "retained_input_or_state_validation_failed"
        with managed_session(runtime.queue.factory) as session:
            assert IntelligenceStore(session).list_project_clusters() == []
    finally:
        runtime.close()


def test_failed_worker_rolls_back_all_findings_and_child_jobs(tmp_path, monkeypatch):
    runtime = InvestigationRuntime(tmp_path / "private")
    try:
        runtime.enqueue_json(source(tmp_path), "permit")
        original = runtime._enrich

        def fail_after_child(*args):
            original(*args)
            raise ValueError("Synthetic failure after creating an enrichment job")

        monkeypatch.setattr(runtime, "_enrich", fail_after_child)
        assert runtime.run_once("worker").status == "failed"
        assert len(runtime.queue.list_jobs()) == 1
        with managed_session(runtime.queue.factory) as session:
            store = IntelligenceStore(session)
            assert store.list_project_clusters() == []
            assert store.list_entities() == []
            assert store.list_evidence() == []
    finally:
        runtime.close()


def test_json_replay_continues_in_bounded_restartable_pages(tmp_path):
    runtime = InvestigationRuntime(tmp_path / "private")
    try:
        runtime.enqueue_json(source(tmp_path, count=26), "permit")
        first = runtime.run_once("worker")
        assert first.status == "completed" and first.result["processed"] == 25
        runtime.close()
        runtime = InvestigationRuntime(tmp_path / "private")
        states = drain(runtime, maximum=100)
        replays = [s for s in states if s.definition.kind == "retained_json_replay"]
        assert len(replays) == 1 and replays[0].result["processed"] == 1
        with managed_session(runtime.queue.factory) as session:
            assert InvestigationQueryService(IntelligenceStore(session)).inventory()["total"] == 26
    finally:
        runtime.close()


def test_input_references_and_timer_are_bound_to_local_worker(tmp_path):
    reference = retain_input(tmp_path / "private", b"retained source")
    with pytest.raises(ValueError):
        reference.model_copy(update={"relative_path": "../outside"}).path(tmp_path)
    units = systemd_units(tmp_path / "python", tmp_path / "data")
    assert (
        "constructionsight.investigation_runtime"
        in units["constructionsight-investigations.service"]
    )
    assert "UMask=0077" in units["constructionsight-investigations.service"]
    assert "Persistent=true" in units["constructionsight-investigations.timer"]


def test_backup_restore_preserves_pending_job_inputs_and_resume(tmp_path):
    runtime = InvestigationRuntime(tmp_path / "private")
    path = source(tmp_path)
    original = path.read_bytes()
    job = runtime.enqueue_json(path, "permit")
    runtime.close()
    archive = tmp_path / "snapshot.zip"
    archive.write_bytes(make_backup(tmp_path / "private"))
    restored = tmp_path / "restored"
    report = preview_restore(archive, restored)
    input_path = job.definition.inputs["input"]["relative_path"]
    assert input_path in report["files"]
    assert (restored / input_path).read_bytes() == original
    path.unlink()
    runtime = InvestigationRuntime(restored)
    try:
        assert drain(runtime)[0].job_id == job.job_id
        with managed_session(runtime.queue.factory) as session:
            assert InvestigationQueryService(IntelligenceStore(session)).inventory()["total"] == 1
    finally:
        runtime.close()


def test_smarts_worker_retains_validated_response_and_commits_cursor_with_findings(tmp_path):
    directory = tmp_path / "private"
    runtime = InvestigationRuntime(directory)
    row = {
        "APP_ID": "100",
        "WDID": "8 33C123456",
        "SITE_COUNTY": "Riverside",
        "SITE_NAME": "Synthetic worker site",
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
    journal = directory / "evidence.sqlite3"
    record_smarts_page(journal, page)
    before = journal.read_bytes()
    try:
        job = runtime.enqueue_smarts()
        assert runtime.enqueue_smarts().job_id == job.job_id
        states = drain(runtime)
        assert states[0].result["processed"] == 1
        assert states[0].result["observation_id"] == 1
        assert runtime.enqueue_smarts() is None
        assert journal.read_bytes() == before
        assert (directory / "investigation-inputs" / page.response_sha256).read_bytes() == body
        runtime.close()
        runtime = InvestigationRuntime(directory)
        assert runtime.enqueue_smarts() is None
        with managed_session(runtime.queue.factory) as session:
            inventory = InvestigationQueryService(IntelligenceStore(session)).inventory()
            assert inventory["total"] == 1 and inventory["mapped_on_page"] == 1
    finally:
        runtime.close()


def test_cli_surfaces_failed_jobs_and_previews_units_without_creating_state(tmp_path, capsys):
    directory = tmp_path / "private"
    assert main(["--data-dir", str(directory), "units"]) == 0
    assert "constructionsight-investigations.timer" in json.loads(capsys.readouterr().out)
    assert not directory.exists()
    invalid = tmp_path / "invalid-domain.json"
    invalid.write_text('{"permit_key":"incomplete"}')
    assert (
        main(
            ["--data-dir", str(directory), "enqueue", "--source", str(invalid), "--kind", "permit"]
        )
        == 0
    )
    assert json.loads(capsys.readouterr().out)["status"] == "queued"
    assert main(["--data-dir", str(directory), "run", "--max-jobs", "1"]) == 1
    assert json.loads(capsys.readouterr().out) == {"processed_jobs": 1, "failed_jobs": 1}


def test_backup_includes_input_queued_after_its_initial_file_listing(tmp_path, monkeypatch):
    directory = tmp_path / "private"
    runtime = InvestigationRuntime(directory)
    path = source(tmp_path)
    (directory / "a.json").write_text("{}")
    copied = data_folder.shutil.copyfile
    queued = []

    def enqueue_during_backup(source_path, destination):
        if source_path.name == "a.json" and not queued:
            queued.append(runtime.enqueue_json(path, "permit"))
        return copied(source_path, destination)

    monkeypatch.setattr(data_folder.shutil, "copyfile", enqueue_during_backup)
    try:
        archive = tmp_path / "concurrent.zip"
        archive.write_bytes(make_backup(directory))
    finally:
        runtime.close()

    restored = tmp_path / "restored"
    report = preview_restore(archive, restored)
    assert queued[0].definition.inputs["input"]["relative_path"] in report["files"]
    runtime = InvestigationRuntime(restored)
    try:
        assert drain(runtime)[0].job_id == queued[0].job_id
    finally:
        runtime.close()


@pytest.mark.parametrize("parcel_first", [True, False])
def test_arrival_of_either_source_triggers_parcel_assessment_without_project_merge(
    tmp_path, parcel_first
):
    runtime = InvestigationRuntime(tmp_path / "private")
    permit = source(tmp_path)
    parcel = ParcelCoreRecord(
        parcel_record_id="parcel:synthetic",
        source_key="synthetic:assessor",
        source_record_id="p-1",
        apn="123-456-789",
        normalized_apn="123456789",
        county="Riverside",
        created_at=datetime(2026, 10, 16, tzinfo=UTC),
    )
    parcel_path = tmp_path / "parcel.json"
    parcel_path.write_text(parcel.model_dump_json(round_trip=True))
    inputs = [(parcel_path, "parcel"), (permit, "permit")]
    if not parcel_first:
        inputs.reverse()
    try:
        for path, kind in inputs:
            runtime.enqueue_json(path, kind)
            drain(runtime)
        with managed_session(runtime.queue.factory) as session:
            store = IntelligenceStore(session)
            query = InvestigationQueryService(store)
            inventory = query.inventory()
            assert inventory["total"] == 2
            row = next(
                row
                for row in inventory["rows"]
                if row["source_records"][0]["source_family"] == "permit"
            )
            dossier = query.dossier(row["investigation_id"])
            assessment = dossier["location_assessments"][0]
            assert any(
                candidate["apn"] == "123456789"
                for candidate in assessment["result"]["candidates"]
            )
            assert assessment["project_identity_verified"] is False
            assert assessment["candidate_pool_complete"] is False
            assert dossier["assessment"]["identity_independently_verified"] is False
            assert any(
                relation["predicate"] == "parcel_location_candidate"
                for relation in dossier["relationships"]
            )
            assert len(dossier["source_observations"]) == 1
    finally:
        runtime.close()
