"""End-to-end retained multi-source acceptance for the shared background engine.

The records and jurisdictions here are deliberately synthetic. This is an
offline functional test, not evidence of live public-source coverage or a
reviewed grant to acquire data.
"""

from datetime import UTC, datetime
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

from constructionsight.agenda_models import AgendaItemRecord
from constructionsight.ceqa_models import CeqaRecord
from constructionsight.intelligence.investigation_query_service import InvestigationQueryService
from constructionsight.investigation_runtime import InvestigationRuntime
from constructionsight.parcel_core_models import ParcelCoreRecord
from constructionsight.permit_models import PermitRecord
from constructionsight.planning_models import PlanningCaseRecord
from constructionsight.provenance import Provenance
from constructionsight.site_models import Site
from constructionsight.storage.database import managed_session
from constructionsight.storage.intelligence_store import IntelligenceStore

AT = datetime(2026, 10, 16, tzinfo=UTC)
APN = "123-456-789"


def retained_inputs():
    """Five independent public-record families with a shared location claim."""
    site = Site(site_key="synthetic:site", county="Riverside", apn=APN)
    provenance = [Provenance(source_name="Synthetic public source", captured_at=AT)]
    return [
        (
            "ceqa",
            CeqaRecord(
                ceqa_key="synthetic:ceqa:1",
                title="Synthetic environmental review",
                county="Riverside",
                document_type="NOP",
                state_clearinghouse_number="2026101234",
                site=site,
                provenance=provenance,
            ),
        ),
        (
            "planning",
            PlanningCaseRecord(
                case_key="synthetic:planning:1",
                case_number="CUP-123",
                county="Riverside",
                jurisdiction="Synthetic city",
                status="pending",
                site=site,
                provenance=provenance,
            ),
        ),
        (
            "permit",
            PermitRecord(
                permit_key="synthetic:permit:1",
                permit_number="BLD-123",
                county="Riverside",
                jurisdiction="Synthetic city",
                status="issued",
                site=site,
                provenance=provenance,
            ),
        ),
        (
            "parcel",
            ParcelCoreRecord(
                parcel_record_id="synthetic:parcel:1",
                source_key="synthetic:assessor",
                source_record_id="P-123",
                apn=APN,
                normalized_apn="123456789",
                county="Riverside",
                created_at=AT,
            ),
        ),
        (
            "agenda",
            AgendaItemRecord(
                agenda_key="synthetic:agenda:1",
                meeting_body="Planning Commission",
                county="Riverside",
                jurisdiction="Synthetic city",
                provenance=provenance,
            ),
        ),
    ]


@pytest.mark.parametrize("parcel_first", [True, False])
def test_retained_source_families_cooperate_across_worker_restarts_without_false_merges(
    tmp_path, parcel_first
):
    directory = tmp_path / "private"
    directory.mkdir(mode=0o700)
    source_files = []
    sources = retained_inputs()
    if parcel_first:
        sources = sorted(sources, key=lambda entry: entry[0] != "parcel")

    # Each source is delivered independently, not merged by a shared APN.
    for kind, record in sources:
        path = directory / "investigation-inbox" / kind / f"{kind}.json"
        original = record.model_dump_json(round_trip=True).encode()
        source_files.append((path, kind, original))

    for path, _, original in source_files[:2]:
        path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        path.write_bytes(original)
        runtime = InvestigationRuntime(directory)
        try:
            # The worker discovers new inputs itself, without a manual enqueue.
            report = runtime.process(max_jobs=100, poll_inbox=True)
            assert report["failed_jobs"] == report["inbox_failed"] == 0
        finally:
            runtime.close()

    # Simulate another independent worker process after the initial evidence.
    runtime = InvestigationRuntime(directory)
    try:
        for path, _, original in source_files[2:]:
            path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
            path.write_bytes(original)
        report = runtime.process(max_jobs=150, poll_inbox=True)
        assert report["failed_jobs"] == report["inbox_failed"] == 0
        with managed_session(runtime.queue.factory) as session:
            store = IntelligenceStore(session)
            query = InvestigationQueryService(store)
            inventory = query.inventory(limit=20)

            # Five retained source identities, not one "verified" project.
            assert inventory["total"] == 5
            assert {row["source_records"][0]["source_family"] for row in inventory["rows"]} == {
                "ceqa", "planning", "permit", "parcel", "agenda"
            }
            assert inventory["mapped_on_page"] == 0
            assert len(inventory["unmapped_on_page"]) == 5
            assert all(len(row["source_records"]) == 1 for row in inventory["rows"])
            assert all(
                not row["assessment"]["identity_independently_verified"]
                and not row["assessment"]["commercial_authority_granted"]
                for row in inventory["rows"]
            )

            permit_row = next(
                row for row in inventory["rows"]
                if row["source_records"][0]["source_family"] == "permit"
            )
            permit_dossier = query.dossier(permit_row["investigation_id"])
            assert len(permit_dossier["source_observations"]) == 1
            assert permit_dossier["source_claimed_points"] == []
            assert any(
                relation["predicate"] == "parcel_location_candidate"
                for relation in permit_dossier["relationships"]
            )
            assert any(
                candidate["apn"] == "123456789"
                for assessment in permit_dossier["location_assessments"]
                for candidate in assessment["result"]["candidates"]
            )
            assert any(
                relation.predicate == "possible_same_project_requires_review"
                for relation in store.list_relationships()
            )
            assert all(
                query.dossier(row["investigation_id"])["assessment"]["commercial_readiness"]
                == "unassessed"
                for row in inventory["rows"]
            )
            cursor = store.runtime_event_cursor()
    finally:
        runtime.close()

    # Replay is idempotent even after another process/worker has taken over.
    runtime = InvestigationRuntime(directory)
    try:
        for path, _, original in source_files:
            assert path.read_bytes() == original
        report = runtime.process(max_jobs=150, poll_inbox=True)
        assert report["failed_jobs"] == 0
        assert report["processed_jobs"] == 0
        with managed_session(runtime.queue.factory) as session:
            store = IntelligenceStore(session)
            assert store.runtime_event_cursor() == cursor
            assert InvestigationQueryService(store).inventory()["total"] == 5
    finally:
        runtime.close()


def test_actual_cli_processes_resume_five_source_families_from_retained_inbox(tmp_path):
    """Distinct OS processes use the same durable queue; no network or UI is involved."""
    directory = tmp_path / "private"
    directory.mkdir(mode=0o700)
    items = retained_inputs()
    source_files = []
    for kind, record in items:
        path = directory / "investigation-inbox" / kind / f"{kind}.json"
        source_files.append((path, record.model_dump_json(round_trip=True).encode()))

    repository = Path(__file__).parents[1]
    environment = {
        **os.environ,
        "PYTHONPATH": str(repository / "src") + os.pathsep + os.environ.get("PYTHONPATH", ""),
    }

    def turn(max_jobs):
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "constructionsight.investigation_runtime",
                "--data-dir",
                str(directory),
                "run",
                "--poll-inbox",
                "--max-jobs",
                str(max_jobs),
            ],
            env=environment,
            capture_output=True,
            text=True,
            timeout=90,
        )
        assert result.returncode == 0, result.stderr
        return json.loads(result.stdout)

    # The first process exits with unfinished dependent jobs on disk.
    first_path, first_bytes = source_files[0]
    first_path.parent.mkdir(parents=True, mode=0o700)
    first_path.write_bytes(first_bytes)
    first = turn(1)
    assert first["processed_jobs"] == 1
    assert first["inbox_failed"] == 0

    # A different process discovers remaining jurisdictions and resumes everything.
    for path, content in source_files[1:]:
        path.parent.mkdir(parents=True, mode=0o700)
        path.write_bytes(content)
    second = turn(150)
    assert second["failed_jobs"] == second["inbox_failed"] == 0
    assert second["processed_jobs"] >= 4

    runtime = InvestigationRuntime(directory)
    try:
        with managed_session(runtime.queue.factory) as session:
            store = IntelligenceStore(session)
            query = InvestigationQueryService(store)
            inventory = query.inventory(limit=20)
            assert inventory["total"] == 5
            assert all(
                not row["assessment"]["identity_independently_verified"]
                and not row["assessment"]["commercial_authority_granted"]
                for row in inventory["rows"]
            )
            assert any(
                relationship.predicate == "possible_same_project_requires_review"
                for relationship in store.list_relationships()
            )
            cursor = store.runtime_event_cursor()
    finally:
        runtime.close()

    # A third independent OS process must not replay an unchanged source.
    third = turn(150)
    assert third["processed_jobs"] == third["failed_jobs"] == 0
    runtime = InvestigationRuntime(directory)
    try:
        with managed_session(runtime.queue.factory) as session:
            assert IntelligenceStore(session).runtime_event_cursor() == cursor
    finally:
        runtime.close()

    for path, content in source_files:
        assert path.read_bytes() == content
        digest = hashlib.sha256(content).hexdigest()
        assert (directory / "investigation-inputs" / digest).read_bytes() == content
