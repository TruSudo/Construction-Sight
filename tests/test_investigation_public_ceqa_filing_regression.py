"""Public CEQAnet filing identity regression for the offline investigation worker.

These are selectively transcribed fields from two publicly readable official
CEQAnet HTML pages, inspected October 16, 2026. This is NOT a captured raw
HTTP response, a verified source-adapter acquisition, or proof of field activity.

https://ceqanet.lci.ca.gov/2025100627    (MND received 2025-10-14)
https://ceqanet.lci.ca.gov/2025100627/3  (NOD received 2026-02-18)

Both public notices use SCH 2025100627. The source page's APN string
contains an incomplete 'through' range; it is deliberately not converted
into parcel identifiers or site geometry.
"""

import hashlib
from datetime import UTC, date, datetime

import constructionsight.effect_consumption as effect_consumption
from constructionsight.agenda_models import AgendaItemRecord
from constructionsight.ceqa_models import CeqaRecord
from constructionsight.intelligence.investigation_query_service import InvestigationQueryService
from constructionsight.intelligence.investigation_review_service import InvestigationReviewService
from constructionsight.investigation_runtime import InvestigationRuntime
from constructionsight.provenance import Provenance
from constructionsight.site_models import Site
from constructionsight.storage.database import managed_session
from constructionsight.storage.intelligence_store import IntelligenceStore

REVIEWED_AT = datetime(2026, 10, 16, tzinfo=UTC)
SCH = "2025100627"


def official_page_excerpts() -> list[CeqaRecord]:
    """Model only source-backed, manually transcribed public-page fields."""
    sources = (
        ("mnd:2025-10-14", "MND", date(2025, 10, 14), "https://ceqanet.lci.ca.gov/2025100627"),
        ("nod:2026-02-18", "NOD", date(2026, 2, 18), "https://ceqanet.lci.ca.gov/2025100627/3"),
    )
    return [
        CeqaRecord(
            ceqa_key=f"ceqanet:filing:{SCH}:{suffix}",
            title="Fontana Walnut Residential Project",
            county="San Bernardino",
            lead_agency="City of Fontana",
            document_type=document_type,
            state_clearinghouse_number=SCH,
            received_date=received,
            site=Site(
                site_key=f"ceqanet:unresolved-site:{SCH}:{suffix}",
                county="San Bernardino",
                jurisdiction="City of Fontana",
                city="Fontana",
                # The online parcel-range display is truncated: do not invent
                # an individual APN or interpolate unconfirmed parcel geometry.
            ),
            provenance=[
                Provenance(
                    source_name="CEQAnet public filing (manual field excerpt)",
                    source_url=url,
                    captured_at=REVIEWED_AT,
                    notes="Selected official HTML fields only, not retained raw HTTP capture.",
                )
            ],
        )
        for suffix, document_type, received, url in sources
    ]


def test_official_two_filing_sch_replay_preserves_separate_evidence_and_unknowns(tmp_path):
    """Same SCH number is not sufficient to confirm one construction site."""
    directory = tmp_path / "private"
    directory.mkdir(mode=0o700)
    records = official_page_excerpts()
    originals = [item.model_dump_json(round_trip=True).encode() for item in records]

    runtime = InvestigationRuntime(directory)
    try:
        first_job = runtime.enqueue_bytes(originals[0], "ceqa")
        assert first_job.job_id
        assert runtime.process(max_jobs=100)["failed_jobs"] == 0
    finally:
        runtime.close()

    # Simulate a second independent worker lifetime and a later filing.
    runtime = InvestigationRuntime(directory)
    try:
        second_job = runtime.enqueue_bytes(originals[1], "ceqa")
        assert second_job.job_id != first_job.job_id
        assert runtime.process(max_jobs=100)["failed_jobs"] == 0

        with managed_session(runtime.queue.factory) as session:
            store = IntelligenceStore(session)
            query = InvestigationQueryService(store)
            inventory = query.inventory(limit=20)
            assert inventory["total"] == 2
            assert {row["source_records"][0]["source_record_id"] for row in inventory["rows"]} == {
                item.ceqa_key for item in records
            }
            # Two distinct CEQA filing identities must not be fused solely
            # because they share an SCH number, title and jurisdiction.
            for row in inventory["rows"]:
                assert len(row["source_records"]) == 1
                assert row["assessment"]["identity_independently_verified"] is False
                assert row["assessment"]["commercial_authority_granted"] is False
                dossier = query.dossier(row["investigation_id"])
                assert len(dossier["source_observations"]) == 1
                evidence = dossier["source_observations"][0]["evidence"]
                normalized = evidence["raw_observations"]["normalized_source_record"]
                assert normalized["state_clearinghouse_number"] == SCH
                assert normalized["site"]["apn"] is None
                assert normalized["site"]["latitude"] is None
                assert normalized["site"]["longitude"] is None
                assert evidence["source_url"] in {
                    "https://ceqanet.lci.ca.gov/2025100627",
                    "https://ceqanet.lci.ca.gov/2025100627/3",
                }
                assert dossier["assessment"]["commercial_readiness"] == "unassessed"
            event_cursor = store.runtime_event_cursor()

        # Restart-safe exact-byte retention: reprocessing does not invent
        # a new observation, promote a candidate or duplicate an event.
        replay = runtime.process(max_jobs=100)
        assert replay["processed_jobs"] == replay["failed_jobs"] == 0
        with managed_session(runtime.queue.factory) as session:
            store = IntelligenceStore(session)
            assert store.runtime_event_cursor() == event_cursor
            assert InvestigationQueryService(store).inventory()["total"] == 2
    finally:
        runtime.close()

    for original in originals:
        digest = hashlib.sha256(original).hexdigest()
        assert (directory / "investigation-inputs" / digest).read_bytes() == original


def test_public_ceqa_and_city_hearing_reviewed_context_with_later_nod(tmp_path, monkeypatch):
    """Real page-backed field excerpts, not an authorized live source-acquisition test.

    California CEQAnet MND: https://ceqanet.lci.ca.gov/2025100627
    Fontana Legistar public hearing item 25-0659:
    https://fontana.legistar.com/LegislationDetail.aspx?ID=7737395

    Both list APN 0228-051-01. This is one explicitly named parcel in a
    multi-parcel proposal, not an inferred sole project footprint. A shared
    parcel must create no independently verified same-project identity.
    """
    directory = tmp_path / "private"
    directory.mkdir(mode=0o700)
    monkeypatch.setattr(
        effect_consumption,
        "_CONSUMPTION_DATABASE_PATH",
        tmp_path / "public-page-excerpts-review-effects.sqlite3",
    )
    apn = "0228-051-01"
    ceqa = official_page_excerpts()[0].model_copy(
        update={
            "site": Site(
                site_key="ceqanet:one-explicitly-listed-parcel:2025100627",
                county="San Bernardino",
                jurisdiction="City of Fontana",
                city="Fontana",
                apn=apn,
            )
        }
    )
    agenda = AgendaItemRecord(
        agenda_key="fontana:legistar:25-0659",
        meeting_body="Planning Commission",
        jurisdiction="City of Fontana",
        county="San Bernardino",
        meeting_date=date(2025, 11, 18),
        item_number="25-0659",
        title="Fontana Walnut Residential Project - MCN 24-0060",
        site=Site(
            site_key="fontana:legistar:25-0659:one-listed-parcel",
            county="San Bernardino",
            jurisdiction="City of Fontana",
            city="Fontana",
            apn=apn,
        ),
        provenance=[
            Provenance(
                source_name="Fontana Legistar public agenda (manual field excerpt)",
                source_url=(
                    "https://fontana.legistar.com/LegislationDetail.aspx?"
                    "GUID=3577A726-0646-4B6A-B3D5-126C8DB52D2B&"
                    "ID=7737395&Options=&Search="
                ),
                captured_at=REVIEWED_AT,
                notes="Selected official HTML fields only, not retained raw HTTP capture.",
            )
        ],
    )

    runtime = InvestigationRuntime(directory)
    try:
        for kind, record in (("ceqa", ceqa), ("agenda", agenda)):
            runtime.enqueue_bytes(record.model_dump_json(round_trip=True).encode(), kind)
        report = runtime.process(max_jobs=100)
        assert report["failed_jobs"] == 0
        with managed_session(runtime.queue.factory) as session:
            store = IntelligenceStore(session)
            query = InvestigationQueryService(store)
            rows = query.inventory(limit=10)["rows"]
            assert len(rows) == 2
            assert {row["source_records"][0]["source_family"] for row in rows} == {
                "ceqa", "agenda"
            }
            # Candidate is backed by a shared explicit APN, not promoted by
            # similar names, a public hearing, or the existence of an MND.
            relations = [
                relation
                for relation in store.list_relationships()
                if relation.predicate == "possible_same_project_requires_review"
            ]
            assert relations
            anchor_id = next(
                row["investigation_id"]
                for row in rows
                if row["source_records"][0]["source_family"] == "ceqa"
            )
            candidate_id = relations[0].relationship_id
            assert all(
                not row["assessment"]["identity_independently_verified"]
                and not row["assessment"]["commercial_authority_granted"]
                for row in rows
            )
            for row in rows:
                dossier = query.dossier(row["investigation_id"])
                assert len(dossier["source_membership"]) == 1
                assert dossier["assessment"]["commercial_readiness"] == "unassessed"
                assert dossier["candidate_source_links"]
                assert all(
                    not item["identity_verified"] and not item["membership_confirmed"]
                    for item in dossier["candidate_source_links"]
                )

        # This reviewer is explicitly synthetic: it tests the operator-review
        # boundary, and does NOT establish factual project identity.
        reviewer = InvestigationReviewService(runtime.engine)
        preview = reviewer.preview(candidate_id)
        result = reviewer.review(
            candidate_id,
            decision="associate",
            target_id=anchor_id,
            expected_identity=preview["expected_identity"],
            reason="Offline test: retain two public page excerpts as related context only",
            caller_confirmation=True,
            operator_id="operator:offline-public-page-test",
        )
        assert result["identity_independently_verified"] is False

        with managed_session(runtime.queue.factory) as session:
            query = InvestigationQueryService(IntelligenceStore(session))
            assert query.inventory(limit=10)["total"] == 1
            dossier = query.dossier(anchor_id)
            assert {row["source_family"] for row in dossier["source_membership"]} == {
                "ceqa", "agenda"
            }
            assert dossier["cross_source_investigation"]["reviewed_context_source_count"] == 1
            assert len(dossier["chronology"]) == 2
            assert dossier["assessment"]["identity_independently_verified"] is False
            assert dossier["assessment"]["commercial_authority_granted"] is False

        # A later NOD under the same SCH is a distinct official filing.
        # The site has multiple parcels; review of MND/agenda does not grant
        # approval to silently attach later government evidence.
        nod = official_page_excerpts()[1]
        runtime.enqueue_bytes(nod.model_dump_json(round_trip=True).encode(), "ceqa")
        assert runtime.process(max_jobs=100)["failed_jobs"] == 0
        with managed_session(runtime.queue.factory) as session:
            query = InvestigationQueryService(IntelligenceStore(session))
            inventory = query.inventory(limit=10)
            assert inventory["total"] == 2
            dossier = query.dossier(anchor_id)
            assert {row["source_family"] for row in dossier["source_membership"]} == {
                "ceqa", "agenda"
            }
            assert len(dossier["chronology"]) == 2
            assert dossier["assessment"]["identity_independently_verified"] is False
            assert dossier["assessment"]["commercial_authority_granted"] is False
            assert dossier["assessment"]["commercial_readiness"] == "unassessed"
            assert any(
                row["source_records"][0]["source_record_id"] == nod.ceqa_key
                for row in inventory["rows"]
            )

        replay = runtime.process(max_jobs=100)
        assert replay["processed_jobs"] == replay["failed_jobs"] == 0
    finally:
        runtime.close()
