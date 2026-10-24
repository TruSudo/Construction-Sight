import json
from datetime import UTC, datetime

import pytest

from constructionsight.agenda_models import AgendaItemRecord
from constructionsight.document_models import DocumentRecord
from constructionsight.intake_models import ExtractedMaterialFact, FactConfidence, MaterialFactKind
from constructionsight.intake_service import IntakeInspectionInput, inspect_lawful_input
from constructionsight.intelligence.artifact_identity import IdentityArtifactType as Artifact
from constructionsight.intelligence.investigation_sources import normalize_retained_record
from constructionsight.investigation_cli import main
from constructionsight.planning_models import PlanningCaseRecord
from constructionsight.provenance import Provenance
from constructionsight.site_models import Site

AT = datetime(2026, 10, 16, tzinfo=UTC)


def test_remaining_producers_persist_replay_and_paginate_without_mutating_reads(tmp_path, capsys):
    provenance = [Provenance(source_name="Synthetic city", captured_at=AT)]
    site = Site(
        site_key="site:planning",
        county="Riverside",
        apn="123-456-789",
        latitude=33.9,
        longitude=-117.2,
    )
    records = {
        "planning": PlanningCaseRecord(
            case_key="planning:1",
            case_number="CUP-1",
            county="Riverside",
            jurisdiction="Test city",
            site=site,
            provenance=provenance,
        ),
        "agenda": AgendaItemRecord(
            agenda_key="agenda:1",
            meeting_body="Planning Commission",
            county="Riverside",
            jurisdiction="Test city",
            provenance=provenance,
        ),
        "document": DocumentRecord(
            document_key="document:1",
            source_name="Synthetic city",
            captured_at=AT,
            text_extract="Synthetic retained staff report",
        ),
        "intake": inspect_lawful_input(
            IntakeInspectionInput(
                content=b"Unresolved synthetic source",
                source_name="Synthetic intake",
                original_filename="record.txt",
            )
        ),
    }
    database = tmp_path / "private" / "investigations.sqlite3"
    ids = set()
    for kind, record in records.items():
        source = tmp_path / f"{kind}.json"
        content = record.model_dump_json(round_trip=True).encode()
        source.write_bytes(content)
        args = ["--database", str(database), "--source", str(source), "--kind", kind]
        assert main(args) == 0
        first = json.loads(capsys.readouterr().out)
        assert main(args) == 0
        assert json.loads(capsys.readouterr().out) == first
        assert source.read_bytes() == content
        ids.update(first["investigation_ids"])
    before = database.read_bytes()
    seen = set()
    after = []
    pages = []
    while True:
        assert main(["--database", str(database), "--inventory", "--limit", "1", *after]) == 0
        page = json.loads(capsys.readouterr().out)
        pages.append(page)
        assert page["total"] == 4 and len(page["rows"]) == 1
        row = page["rows"][0]
        assert row["investigation_id"] not in seen
        seen.add(row["investigation_id"])
        assert row["assessment"]["identity_independently_verified"] is False
        assert row["assessment"]["commercial_authority_granted"] is False
        assert main(["--database", str(database), "--show", row["investigation_id"]]) == 0
        dossier = json.loads(capsys.readouterr().out)
        assert len(dossier["source_observations"]) == 1
        assert dossier["evidence"][0]["content_hash"]
        assert dossier["chronology"]
        if not page["has_more"]:
            assert page["next_cursor"] is None
            break
        after = ["--after-inventory", page["next_cursor"]]
    assert seen == ids
    assert sum(page["mapped_on_page"] for page in pages) == 1
    assert sum(len(page["unmapped_on_page"]) for page in pages) == 3
    assert database.read_bytes() == before


@pytest.mark.parametrize("kind", ["planning", "agenda", "document"])
def test_remaining_sources_require_a_retained_time(kind):
    values = {
        "planning": {
            "case_key": "one",
            "case_number": "one",
            "jurisdiction": "Test",
            "county": "Riverside",
        },
        "agenda": {
            "agenda_key": "one",
            "meeting_body": "Test",
            "jurisdiction": "Test",
            "county": "Riverside",
        },
        "document": {"document_key": "one", "source_name": "Test"},
    }
    with pytest.raises(ValueError, match="captured provenance"):
        normalize_retained_record(kind, values[kind])


def test_planning_agenda_document_and_unfamiliar_intake_share_the_observation_contract():
    provenance = [
        Provenance(
            source_name="Synthetic source",
            captured_at=AT,
            evidence_text="Synthetic retained source claim",
        )
    ]
    records = {
        "planning": PlanningCaseRecord(
            case_key="case:test",
            case_number="CUP-1",
            jurisdiction="Test city",
            county="Riverside",
            provenance=provenance,
        ),
        "agenda": AgendaItemRecord(
            agenda_key="agenda:test",
            meeting_body="Planning Commission",
            jurisdiction="Test city",
            county="Riverside",
            provenance=provenance,
        ),
        "document": DocumentRecord(
            document_key="document:test",
            source_name="Synthetic source",
            captured_at=AT,
            text_extract="Retained document with unresolved location",
        ),
        "intake": inspect_lawful_input(
            IntakeInspectionInput(
                content=b"\x00\xff\x01\x02",
                source_name="Synthetic unknown input",
                original_filename="unknown.bin",
            )
        ),
    }
    for kind, record in records.items():
        item = normalize_retained_record(kind, record.model_dump(mode="json", round_trip=True))
        assert item.evidence.record_type == kind
        assert item.latitude is None and item.longitude is None
        assert item.evidence.content_hash
        assert item.evidence.limitations
    assert (
        normalize_retained_record("intake", records["intake"].model_dump(mode="json")).artifacts
        == {}
    )


def test_uncertain_facts_and_forged_normalization_cannot_become_location_or_identity_anchors():
    intake = inspect_lawful_input(
        IntakeInspectionInput(
            content=b"Warehouse at 123 Main St",
            source_name="Synthetic source",
            original_filename="record.txt",
        )
    )
    address = ExtractedMaterialFact(
        fact_id="fact:address",
        fact_kind=MaterialFactKind.ADDRESS,
        value="123 Main St",
        normalized_value="34.1, -117.2",
        evidence_id=intake.evidence.evidence_id,
    )
    uncertain_apn = ExtractedMaterialFact(
        fact_id="fact:uncertain",
        fact_kind=MaterialFactKind.APN,
        value="123-456-789",
        evidence_id=intake.evidence.evidence_id,
        confidence=FactConfidence.AMBIGUOUS,
    )
    intake = intake.model_copy(update={"extracted_facts": [address, uncertain_apn]})
    item = normalize_retained_record("intake", intake.model_dump(mode="json"))
    assert item.artifacts[Artifact.EXACT_SITE_ADDRESS] == ["123 Main St"]
    assert Artifact.APN not in item.artifacts
    assert item.latitude is None and item.longitude is None
    assert any("uncertain/inferred" in note for note in item.evidence.limitations)
    broken = intake.model_copy(
        update={
            "extracted_facts": [address.model_copy(update={"evidence_id": "different-evidence"})]
        }
    )
    with pytest.raises(ValueError, match="not bound"):
        normalize_retained_record("intake", broken.model_dump(mode="json"))
