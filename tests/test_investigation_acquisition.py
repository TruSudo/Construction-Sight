"""Source-to-worker integration using mocked transport and actual retained CEQA evidence."""

import hashlib
import json
import subprocess
from datetime import UTC, datetime
from pathlib import Path

import httpx
import pytest

from constructionsight import collection_schedule as schedule
from constructionsight import command_center_state as state
from constructionsight import smarts_active
from constructionsight.intelligence.investigation_query_service import InvestigationQueryService
from constructionsight.investigation_inbox import poll_retained_inbox
from constructionsight.investigation_runtime import InvestigationRuntime
from constructionsight.lead_workflow import begin_run, finish_run
from constructionsight.permit_models import PermitRecord
from constructionsight.provenance import Provenance
from constructionsight.smarts_api import RESOURCE_IDS, SmartsAccessDenied, SmartsApiError
from constructionsight.storage.database import managed_session
from constructionsight.storage.intelligence_store import IntelligenceStore


def permit(number, *, day=16):
    return PermitRecord(
        permit_key=f"permit:{number}",
        permit_number=f"BLD-{number}",
        jurisdiction="Synthetic city",
        county="Riverside",
        provenance=[
            Provenance(
                source_name="Synthetic permit portal",
                captured_at=datetime(2026, 10, day, tzinfo=UTC),
            )
        ],
    ).model_dump_json(round_trip=True)


@pytest.mark.parametrize("handoff_failure", [False, True])
def test_scheduled_capture_hands_off_real_transport_bytes_without_a_dashboard(
    tmp_path, monkeypatch, handoff_failure
):
    directory = tmp_path / "private"
    state.initialize(directory)
    state.save_settings(directory, {"source_enabled": True})
    schedule.write(directory, {**schedule.DEFAULT, "enabled": True})
    requests = []
    if handoff_failure:
        monkeypatch.setattr(
            "constructionsight.investigation_runtime.enqueue_smarts_capture",
            lambda directory: {"status": "error", "error_code": "synthetic_handoff_failure"},
        )

    def respond(request):
        requests.append(str(request.url))
        county = json.loads(request.url.params["filters"])["SITE_COUNTY"]
        row = {
            "_id": 1,
            "APP_ID": "1",
            "WDID": "8 33C123456",
            "SITE_COUNTY": county,
            "SITE_NAME": "Synthetic scheduled source",
            "STATUS": "Active",
        }
        return httpx.Response(
            200,
            json={
                "success": True,
                "result": {
                    "resource_id": RESOURCE_IDS["facilities"],
                    "total": 1,
                    "records": [row],
                    "fields": [{"id": name} for name in row],
                },
            },
        )

    def collect(_args):
        with httpx.Client(transport=httpx.MockTransport(respond)) as client:
            snapshot = smarts_active.collect_active(client, directory)
        assert snapshot["investigation_handoff"]["status"] in (
            {"error"} if handoff_failure else {"queued", "idle"}
        )
        return 0

    monkeypatch.setattr("constructionsight.live_command_center.main", collect)
    for _ in range(2):
        assert schedule.run(directory) == 0
        report = json.loads((directory / "schedule-run.json").read_text())
        assert report["capture_outcome"] == "ok"
        assert report["investigation"]["failed_jobs"] == 0
        assert schedule.warning(directory) is None
        runtime = InvestigationRuntime(directory)
        try:
            with managed_session(runtime.queue.factory) as session:
                inventory = InvestigationQueryService(IntelligenceStore(session)).inventory()
                assert inventory["total"] == 2
                assert len(inventory["unmapped_on_page"]) == 2
                assert all(
                    row["assessment"]["identity_independently_verified"] is False
                    for row in inventory["rows"]
                )
        finally:
            runtime.close()
    assert len(requests) == 4  # Acquisition only; replay/enrichment never fetch sources.


def test_worker_failure_does_not_reclassify_capture_or_reuse_an_old_403(tmp_path, monkeypatch):
    directory = tmp_path / "private"
    state.initialize(directory)
    state.save_settings(directory, {"source_enabled": True})
    schedule.write(directory, {**schedule.DEFAULT, "enabled": True})
    old = begin_run(directory)
    finish_run(directory, old, None, "HTTPStatusError: 403 Forbidden")
    monkeypatch.setattr("constructionsight.live_command_center.main", lambda _args: 0)

    def fail(*args, **kwargs):
        raise ValueError("Synthetic worker failure after successful acquisition")

    monkeypatch.setattr(InvestigationRuntime, "process", fail)
    assert schedule.run(directory) == 1
    result = json.loads((directory / "schedule-run.json").read_text())
    assert result["capture_outcome"] == "ok" and result["outcome"] == "error"
    assert "investigation processing failed" in result["error"]
    assert schedule.config(directory)["enabled"] is True
    assert state.settings(directory)["source_enabled"] is True


def test_real_smarts_403_stops_schedule_and_survives_restart(tmp_path, monkeypatch):
    directory = tmp_path / "private"
    state.initialize(directory)
    schedule.write(directory, {**schedule.DEFAULT, "enabled": True})
    requests = []

    def denied(request):
        requests.append(str(request.url))
        return httpx.Response(403)

    def collect(_args):
        run_id = begin_run(directory)
        try:
            with httpx.Client(transport=httpx.MockTransport(denied)) as client:
                smarts_active.collect_active(client, directory)
        except SmartsAccessDenied as exc:
            finish_run(directory, run_id, None, f"{type(exc).__name__}: {exc}")
            return 1
        pytest.fail("Denied source unexpectedly succeeded")

    monkeypatch.setattr("constructionsight.live_command_center.main", collect)
    assert schedule.run(directory) == 1
    assert len(requests) == 1
    assert not state.settings(directory)["source_enabled"]
    assert not schedule.config(directory)["enabled"]
    assert schedule.run(directory) == 0
    with (
        httpx.Client(transport=httpx.MockTransport(denied)) as client,
        pytest.raises(SmartsApiError, match="disabled"),
    ):
        smarts_active.collect_active(client, directory)
    assert len(requests) == 1


def test_reviewed_bundle_binds_worker_and_failure_disables_both_timers(tmp_path, monkeypatch):
    directory, units = tmp_path / "data", tmp_path / "units"
    before = schedule.preview(directory, directory)
    assert "--poll-inbox" in before["investigation_service"]
    assert "--poll-smarts" in before["investigation_service"]
    commands = []

    def manager(*args):
        commands.append(args)
        if args[0] == "show":
            return subprocess.CompletedProcess(args, 0, "ActiveState=inactive\n", "")
        return subprocess.CompletedProcess(args, 1, "", "Synthetic installation failure")

    monkeypatch.setattr(schedule, "systemctl", manager)
    with pytest.raises(ValueError, match="Synthetic installation failure"):
        schedule.install(
            directory,
            directory,
            {"reviewed": True, "digest": before["digest"]},
            unit_directory=units,
        )
    assert commands[-1] == (
        "disable",
        "--now",
        schedule.UNIT + ".timer",
        schedule.WORKER_UNIT + ".timer",
    )
    assert not schedule.config(directory)["enabled"]
    assert len(list(units.iterdir())) == 4
    result = subprocess.run(
        ["/usr/bin/systemd-analyze", "verify", *map(str, units.iterdir())],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr


def test_inbox_cursor_fairness_replay_failed_file_and_source_revision(tmp_path):
    runtime = InvestigationRuntime(tmp_path / "private")
    folder = runtime.directory / "investigation-inbox" / "permit"
    folder.mkdir(parents=True, mode=0o700)
    (folder / "0.json").write_text("invalid JSON")
    (folder / "1.json").write_text(permit(1))
    (folder / "2.json").write_text(permit(2))
    try:
        reports = [poll_retained_inbox(runtime, limit=1) for _ in range(3)]
        assert sum(row["inbox_failed"] for row in reports) == 1
        assert sum(row["inbox_accepted"] for row in reports) == 2
        assert len(runtime.queue.list_jobs()) == 2
        first = runtime.process(max_jobs=25)
        assert first["failed_jobs"] == 0
        with managed_session(runtime.queue.factory) as session:
            cursor = IntelligenceStore(session).runtime_event_cursor()
        for _ in range(3):
            poll_retained_inbox(runtime, limit=1)
        assert runtime.process(max_jobs=25)["processed_jobs"] == 0
        with managed_session(runtime.queue.factory) as session:
            assert IntelligenceStore(session).runtime_event_cursor() == cursor
        (folder / "1.json").write_text(permit(1, day=17))
        for _ in range(3):
            poll_retained_inbox(runtime, limit=1)
        assert runtime.process(max_jobs=25)["failed_jobs"] == 0
        with managed_session(runtime.queue.factory) as session:
            store = IntelligenceStore(session)
            inventory = InvestigationQueryService(store).inventory()
            assert inventory["total"] == 2
            assert sum(item.record_type == "permit" for item in store.list_evidence()) == 3
    finally:
        runtime.close()


def test_actual_retained_ceqa_execution_is_replayed_offline_with_original_lineage(
    tmp_path, monkeypatch
):
    evidence = (
        Path(__file__).parents[1]
        / "evidence/source_verification/ceqanet_csv_live_execution_2026-07-12.json"
    )
    content = evidence.read_bytes()
    runtime = InvestigationRuntime(tmp_path / "private")
    folder = runtime.directory / "investigation-inbox" / "ceqa-csv-execution"
    folder.mkdir(parents=True, mode=0o700)
    (folder / "retained.json").write_bytes(content)

    def no_network(*args, **kwargs):
        pytest.fail("Retained evidence processing must not make a network request")

    monkeypatch.setattr(httpx.Client, "send", no_network)
    try:
        report = runtime.process(max_jobs=25, poll_inbox=True)
        assert report["inbox_accepted"] == 1 and report["failed_jobs"] == 0
        assert report["processed_jobs"] == 5
        digest = hashlib.sha256(content).hexdigest()
        assert (runtime.directory / "investigation-inputs" / digest).read_bytes() == content
        with managed_session(runtime.queue.factory) as session:
            store = IntelligenceStore(session)
            inventory = InvestigationQueryService(store).inventory()
            assert inventory["total"] == 2 and inventory["mapped_on_page"] == 0
            relations = store.list_relationships()
            assert (
                sum(
                    r.predicate == "derived_from_retained_input"
                    and r.object_entity_id == "document:retained-input:" + digest
                    for r in relations
                )
                == 2
            )
            cursor = store.runtime_event_cursor()
        assert runtime.process(max_jobs=25, poll_inbox=True)["processed_jobs"] == 0
        with managed_session(runtime.queue.factory) as session:
            assert IntelligenceStore(session).runtime_event_cursor() == cursor
        assert evidence.read_bytes() == content
    finally:
        runtime.close()


def test_inbox_does_not_follow_source_file_or_directory_symlinks(tmp_path):
    runtime = InvestigationRuntime(tmp_path / "private")
    outside = tmp_path / "outside"
    outside.mkdir()
    source = outside / "record.json"
    source.write_text(permit(1))
    original = source.read_bytes()
    folder = runtime.directory / "investigation-inbox" / "permit"
    folder.mkdir(parents=True, mode=0o700)
    (folder / "linked.json").symlink_to(source)
    try:
        assert poll_retained_inbox(runtime)["inbox_failed"] == 1
        assert runtime.queue.list_jobs() == []
        (folder / "linked.json").unlink()
        folder.rmdir()
        folder.symlink_to(outside, target_is_directory=True)
        with pytest.raises((ValueError, OSError)):
            poll_retained_inbox(runtime)
        assert runtime.queue.list_jobs() == []
        assert source.read_bytes() == original
    finally:
        runtime.close()


def test_review_digest_covers_changes_to_independent_worker(tmp_path, monkeypatch):
    import constructionsight.investigation_runtime as runtime_module

    original = runtime_module.systemd_units
    before = schedule.preview(tmp_path, tmp_path)

    def changed(*args):
        units = original(*args)
        units[schedule.WORKER_UNIT + ".service"] += "# Synthetic changed worker\n"
        return units

    monkeypatch.setattr(runtime_module, "systemd_units", changed)
    assert schedule.preview(tmp_path, tmp_path)["digest"] != before["digest"]
    with pytest.raises(ValueError, match="Review"):
        schedule.install(tmp_path, tmp_path, {"reviewed": True, "digest": before["digest"]})
