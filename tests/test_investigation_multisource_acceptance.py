"""End-to-end retained multi-source acceptance for the shared background engine.

The records and jurisdictions here are deliberately synthetic. This is an
offline functional test, not evidence of live public-source coverage or a
reviewed grant to acquire data.
"""

import hashlib
import json
import os
import subprocess
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

import constructionsight.effect_consumption as effect_consumption
from constructionsight.agenda_models import AgendaItemRecord
from constructionsight.ceqa_models import CeqaRecord
from constructionsight.intelligence.investigation_query_service import InvestigationQueryService
from constructionsight.intelligence.investigation_review_service import InvestigationReviewService
from constructionsight.intelligence.investigation_service import InvestigationService
from constructionsight.intelligence.schemas import RelationshipAssertion, RelationshipStatus
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
            # Cross-source candidates are visible, but not silently included
            # as verified project members or mixed into the source chronology.
            candidate_dossiers = [
                query.dossier(row["investigation_id"]) for row in inventory["rows"]
            ]
            assert any(dossier["candidate_source_links"] for dossier in candidate_dossiers)
            for dossier in candidate_dossiers:
                own_ids = {
                    item["evidence"]["evidence_id"]
                    for item in dossier["source_observations"]
                }
                for link in dossier["candidate_source_links"]:
                    assert link["membership_confirmed"] is False
                    assert link["identity_verified"] is False
                    assert link["supporting_evidence_ids"]
                    assert link["candidate_sources"]
                    assert link["candidate_investigation_id"] != (
                        dossier["investigation"]["project_cluster_id"]
                    )
                    for candidate in link["candidate_sources"]:
                        assert candidate["evidence_id"] not in own_ids
                        assert candidate["source_family"]
                        assert all(
                            event["evidence_id"] != candidate["evidence_id"]
                            for event in dossier["chronology"]
                        )
                if dossier["candidate_source_links"]:
                    assert any(
                        "Cross-source project candidates require identity review"
                        in gap for gap in dossier["assessment"]["gaps"]
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


def test_conflicting_cross_source_candidate_is_visible_but_does_not_merge_evidence(
    tmp_path,
):
    directory = tmp_path / "private"
    directory.mkdir(mode=0o700)
    runtime = InvestigationRuntime(directory)
    try:
        for kind, record in retained_inputs()[:2]:
            runtime.enqueue_bytes(record.model_dump_json(round_trip=True).encode(), kind)
        assert runtime.process(max_jobs=100)["failed_jobs"] == 0
        with managed_session(runtime.queue.factory) as session:
            store = IntelligenceStore(session)
            query = InvestigationQueryService(store)
            rows = query.inventory()["rows"]
            assert len(rows) == 2
            left, right = rows
            left_dossier = query.dossier(left["investigation_id"])
            right_dossier = query.dossier(right["investigation_id"])
            left_evidence = left_dossier["source_observations"][0]["evidence"]["evidence_id"]
            right_evidence = right_dossier["source_observations"][0]["evidence"]["evidence_id"]
            store.upsert_relationship(
                RelationshipAssertion(
                    relationship_id="synthetic:conflicting-potential-match",
                    subject_entity_id=left["investigation_id"],
                    object_entity_id=right["investigation_id"],
                    predicate="possible_same_project_requires_review",
                    relationship_status=RelationshipStatus.CONFLICTING,
                    evidence_summary="Synthetic identity artifacts disagree; review is mandatory.",
                    supporting_evidence_ids=[left_evidence, right_evidence],
                    contradictory_evidence_ids=[left_evidence, right_evidence],
                )
            )
            dossier = query.dossier(left["investigation_id"])
            link = next(
                item for item in dossier["candidate_source_links"]
                if item["relationship_id"] == "synthetic:conflicting-potential-match"
            )
            assert link["relationship_status"] == "conflicting"
            assert any(
                context["evidence_id"] == right_evidence
                for context in link["candidate_sources"]
            )
            assert link["candidate_investigation_id"] == right["investigation_id"]
            assert set(link["contradictory_evidence_ids"]) == {left_evidence, right_evidence}
            assert link["membership_confirmed"] is False
            assert link["identity_verified"] is False
            assert len(dossier["source_observations"]) == 1
            assert all(
                event["evidence_id"] != right_evidence for event in dossier["chronology"]
            )
            assert any(
                "Conflicting cross-source candidate evidence" in gap
                for gap in dossier["assessment"]["gaps"]
            )
    finally:
        runtime.close()


def test_reviewed_three_typed_source_families_assemble_and_reassess_after_retained_revision(
    tmp_path, monkeypatch
):
    """Real adapters + shared queue + authorized review, still entirely offline."""
    directory = tmp_path / "private"
    directory.mkdir(mode=0o700)
    monkeypatch.setattr(
        effect_consumption,
        "_CONSUMPTION_DATABASE_PATH",
        tmp_path / "typed-source-review-effects.sqlite3",
    )
    runtime = InvestigationRuntime(directory)
    try:
        sources = retained_inputs()[:3]
        for kind, record in sources:
            runtime.enqueue_bytes(record.model_dump_json(round_trip=True).encode(), kind)
        first = runtime.process(max_jobs=150)
        assert first["failed_jobs"] == 0

        with managed_session(runtime.queue.factory) as session:
            store = IntelligenceStore(session)
            service = InvestigationService(store)
            inventory = InvestigationQueryService(store).inventory(limit=20)
            assert inventory["total"] == 3
            source_ids = {
                row["source_records"][0]["source_family"]: InvestigationQueryService(store)
                .dossier(row["investigation_id"])["source_observations"][0]["evidence"]
                for row in inventory["rows"]
            }
            assert set(source_ids) == {"ceqa", "planning", "permit"}
            investigations = {
                row["source_records"][0]["source_family"]: row["investigation_id"]
                for row in inventory["rows"]
            }
            from constructionsight.intelligence.investigation_service import (
                source_record_identity,
            )
            for family in ("planning", "permit"):
                service.correlate(
                    source_record_identity(
                        service.current_observation(
                            next(
                                edge.subject_entity_id
                                for edge in store.list_relationships_for_target(
                                    investigations["ceqa"]
                                )
                                if edge.predicate
                                == "source_record_for_unresolved_investigation"
                            )
                        ).evidence
                    ),
                    next(
                        edge.subject_entity_id
                        for edge in store.list_relationships_for_target(
                            investigations[family]
                        )
                        if edge.predicate == "source_record_for_unresolved_investigation"
                    ),
                )
            candidates = {
                (
                    relation.object_entity_id
                    if relation.subject_entity_id == investigations["ceqa"]
                    else relation.subject_entity_id
                ): relation.relationship_id
                for relation in store.list_relationships()
                if relation.predicate == "possible_same_project_requires_review"
                and investigations["ceqa"] in {
                    relation.subject_entity_id,
                    relation.object_entity_id,
                }
            }
            assert investigations["planning"] in candidates
            assert investigations["permit"] in candidates

        reviewer = InvestigationReviewService(runtime.engine)
        for family in ("planning", "permit"):
            target = candidates[investigations[family]]
            preview = reviewer.preview(target)
            result = reviewer.review(
                target,
                decision="associate",
                target_id=investigations["ceqa"],
                expected_identity=preview["expected_identity"],
                reason="Synthetic typed source records reviewed for contextual association",
                caller_confirmation=True,
                operator_id="operator:synthetic-typed-sources",
            )
            assert result["identity_independently_verified"] is False

        with managed_session(runtime.queue.factory) as session:
            store = IntelligenceStore(session)
            query = InvestigationQueryService(store)
            assert query.inventory()["total"] == 1
            dossier = query.dossier(investigations["ceqa"])
            assert {item["source_family"] for item in dossier["source_membership"]} == {
                "ceqa", "planning", "permit"
            }
            assert dossier["cross_source_investigation"]["reviewed_context_source_count"] == 2
            assert len(dossier["chronology"]) == 3
            assert not dossier["pending_association_reviews"]

        permit = sources[2][1]
        revision = permit.model_copy(
            update={
                "description": "Synthetic revised building permit",
                "provenance": [
                    Provenance(source_name="Synthetic public source", captured_at=AT + timedelta(days=3))
                ],
            }
        )
        runtime.enqueue_bytes(revision.model_dump_json(round_trip=True).encode(), "permit")
        assert runtime.process(max_jobs=100)["failed_jobs"] == 0
        with managed_session(runtime.queue.factory) as session:
            dossier = InvestigationQueryService(IntelligenceStore(session)).dossier(
                investigations["ceqa"]
            )
            assert len(dossier["chronology"]) == 4
            revisions = [
                event for event in dossier["chronology"] if event["source_family"] == "permit"
            ]
            assert len(revisions) == 2
            assert [event["is_current_source_revision"] for event in revisions] == [False, True]
            assert dossier["pending_association_reviews"]
            assert dossier["cross_source_investigation"]["requires_association_reassessment"]
            assert dossier["cross_source_investigation"]["identity_independently_verified"] is False
            assert dossier["cross_source_investigation"]["commercial_authority_granted"] is False
    finally:
        runtime.close()
