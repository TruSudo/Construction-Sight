"""Independent local worker for retained evidence and shared investigations.

Input snapshots are durable before jobs become visible. A claimed job's knowledge,
children and completion share one SQLite transaction. Network acquisition requires
a separate reviewed finite CEQA background plan;
retained processing itself grants no network or human identity-review authority.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sqlite3
import sys
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.exc import OperationalError, SQLAlchemyError

from constructionsight import data_folder
from constructionsight.ceqanet_csv_live_models import CeqanetCsvLiveExecution
from constructionsight.ceqanet_csv_operator_bridge import build_reviewed_ceqanet_csv_bridge
from constructionsight.collection_schedule import unit_quote
from constructionsight.intelligence.investigation_location_service import (
    InvestigationLocationService,
)
from constructionsight.intelligence.investigation_service import (
    InvestigationObservation,
    InvestigationService,
    NoCorrelationEvidence,
    ReviewedCorrelation,
    _identity,
)
from constructionsight.intelligence.investigation_sources import (
    RETAINED_SOURCE_KINDS,
    from_smarts,
    normalize_retained_record,
)
from constructionsight.intelligence.schemas import (
    EntityIdentity,
    EntityType,
    EvidenceRecord,
    RelationshipAssertion,
    RelationshipStatus,
    RuntimeEvent,
    RuntimeEventType,
)
from constructionsight.investigation_jobs import InvestigationJobQueue, JobDefinition, JobState
from constructionsight.parcel_core_models import ParcelCoreRecord
from constructionsight.smarts_evidence_ledger import read_smarts_observations
from constructionsight.storage.database import (
    create_private_database_engine,
    initialize_database,
    managed_session,
)
from constructionsight.storage.intelligence_orm import (
    IntelligenceEntityRecord,
    IntelligenceRuntimeEventRecord,
)
from constructionsight.storage.intelligence_store import IntelligenceStore
from constructionsight.storage.runtime_artifacts import (
    publish_runtime_artifact,
    read_runtime_artifact,
    read_runtime_text,
    runtime_artifact_parts,
    write_runtime_text,
)

MAX_INPUT_BYTES = 16 * 1024 * 1024
BATCH = 25
RUNTIME_SOURCE_KINDS = (*RETAINED_SOURCE_KINDS, "ceqa-csv-execution", "ceqa-listing-execution")


class InputRef(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    relative_path: str

    def path(self, directory: Path) -> Path:
        parts = runtime_artifact_parts(self.relative_path)
        if parts != ("investigation-inputs", self.sha256):
            raise ValueError("input reference is not a content-addressed retained artifact")
        return directory.joinpath(*parts)


def retain_input(directory: Path, content: bytes) -> InputRef:
    if not 0 < len(content) <= MAX_INPUT_BYTES:
        raise ValueError("retained input exceeds the bounded evidence size")
    digest = hashlib.sha256(content).hexdigest()
    reference = InputRef(sha256=digest, relative_path=f"investigation-inputs/{digest}")
    path = reference.path(directory)
    try:
        publish_runtime_artifact(path, [content], max_bytes=MAX_INPUT_BYTES)
    except FileExistsError:
        if read_runtime_artifact(path, max_bytes=MAX_INPUT_BYTES) != content:
            raise ValueError(
                "retained artifact differs from its immutable content identity"
            ) from None
    return reference


def read_input(directory: Path, reference: InputRef) -> bytes:
    content = read_runtime_artifact(reference.path(directory), max_bytes=MAX_INPUT_BYTES)
    if hashlib.sha256(content).hexdigest() != reference.sha256:
        raise ValueError("retained input failed its exact-byte integrity check")
    return content


class InvestigationRuntime:
    def __init__(self, directory: Path) -> None:
        self.directory = directory.absolute()
        self.engine = create_private_database_engine(self.directory / "investigations.sqlite3")
        try:
            initialize_database(self.engine)
        except Exception:
            self.engine.dispose()
            raise
        self.queue = InvestigationJobQueue(self.engine)

    def close(self) -> None:
        self.engine.dispose()

    def enqueue_json(self, path: Path, kind: str) -> JobState:
        return self.enqueue_bytes(read_runtime_artifact(path, max_bytes=MAX_INPUT_BYTES), kind)

    def enqueue_bytes(self, content: bytes, kind: str) -> JobState:
        if kind not in RUNTIME_SOURCE_KINDS:
            raise ValueError("unsupported retained source family")
        # Preserve even invalid source payloads before normalization is attempted.
        reference = retain_input(self.directory, content)
        parent_reference = None
        if kind == "ceqa-listing-execution":
            from constructionsight.ceqanet_background import BackgroundListingEvidence

            evidence = BackgroundListingEvidence.model_validate_json(content)
            rows = evidence.normalized_records()
            if not rows:
                raise ValueError("CEQA listing has no usable retained records")
            content = json.dumps(
                rows, sort_keys=True, separators=(",", ":"), allow_nan=False
            ).encode()
            parent_reference = reference
            reference = retain_input(self.directory, content)
            kind = "ceqa"
        if kind == "ceqa-csv-execution":
            payload = json.loads(content)
            if not isinstance(payload, dict):
                raise ValueError("CEQA execution evidence must be an object")
            execution = CeqanetCsvLiveExecution.model_validate(
                payload.get("live_execution", payload)
            )
            bridge = build_reviewed_ceqanet_csv_bridge(execution)
            content = json.dumps(
                [
                    row.model_dump(mode="json", round_trip=True)
                    for row in bridge.preview.ceqa_records
                ],
                sort_keys=True,
                separators=(",", ":"),
                allow_nan=False,
            ).encode()
            parent_reference = reference
            reference = retain_input(self.directory, content)
            kind = "ceqa"
        rows = self._json_rows(content)
        return self.queue.enqueue(
            JobDefinition(
                kind="retained_json_replay",
                inputs={
                    "input": reference.model_dump(),
                    "source_kind": kind,
                    "offset": 0,
                    "row_count": len(rows),
                    **({"parent_input": parent_reference.model_dump()} if parent_reference else {}),
                },
            )
        )

    @staticmethod
    def _json_rows(content: bytes) -> list[Any]:
        value = json.loads(content)
        rows = value if isinstance(value, list) else [value]
        if not rows or len(rows) > 10000:
            raise ValueError("retained JSON requires between 1 and 10000 records")
        return rows

    def enqueue_smarts(self, *, limit: int = BATCH) -> JobState | None:
        """Snapshot one validated journal page; resume only from committed lineage."""
        if type(limit) is not int or not 1 <= limit <= BATCH:
            raise ValueError("SMARTS snapshot limit must be between 1 and 25")
        journal = self.directory / "evidence.sqlite3"
        if not journal.exists():
            return None
        with managed_session(self.queue.factory) as session:
            row = session.scalar(
                select(IntelligenceRuntimeEventRecord)
                .where(
                    IntelligenceRuntimeEventRecord.source_service == "investigation_smarts_cursor"
                )
                .order_by(IntelligenceRuntimeEventRecord.id.desc())
                .limit(1)
            )
            cursor = RuntimeEvent.model_validate_json(row.payload_json).payload if row else None
            after = int(cursor["observation_id"]) if cursor else 0
        if cursor:
            retained = read_smarts_observations(journal, after_id=after - 1, limit=1)
            if (
                not retained
                or retained[0].observation_id != after
                or (from_smarts(retained[0]).receipt_id != cursor["receipt_id"])
            ):
                raise ValueError(
                    "SMARTS journal cursor lineage changed; operator recovery required"
                )
        page = read_smarts_observations(journal, after_id=after, limit=limit)
        if not page:
            return None
        observations = []
        for item in page:
            if item.page.raw_response_bytes is None:
                raise ValueError("validated SMARTS observation lost its original response")
            raw = retain_input(self.directory, item.page.raw_response_bytes)
            observations.append(
                {
                    "observation": from_smarts(item).model_dump(mode="json"),
                    "raw_input": raw.model_dump(),
                    "observation_id": item.observation_id,
                }
            )
        snapshot = retain_input(
            self.directory,
            json.dumps(
                {
                    "observations": observations,
                    "after_id": after,
                },
                sort_keys=True,
                separators=(",", ":"),
                allow_nan=False,
            ).encode(),
        )
        return self.queue.enqueue(
            JobDefinition(
                kind="smarts_replay",
                inputs={
                    "input": snapshot.model_dump(),
                },
            )
        )

    def _lineage(
        self, store: IntelligenceStore, reference: InputRef, item: InvestigationObservation
    ) -> None:
        evidence_id = "evidence:retained-input:" + reference.sha256
        old = store.get_evidence(evidence_id)
        if old is None:
            store.upsert_evidence(
                EvidenceRecord(
                    evidence_id=evidence_id,
                    source_family="retained_input",
                    source_name="Local retained exact bytes",
                    source_record_id=reference.sha256,
                    record_type="retained_input",
                    retrieved_at=datetime.now(UTC),
                    raw_observations=reference.model_dump(),
                    limitations=["Exact retained input bytes; source claims remain unverified."],
                )
            )
        document_id = "document:retained-input:" + reference.sha256
        graph = InvestigationService(store).graph
        if store.get_entity(document_id) is None:
            graph.upsert_entity(
                EntityIdentity(
                    entity_id=document_id,
                    entity_type=EntityType.DOCUMENT,
                    canonical_name="Retained input " + reference.sha256[:12],
                    identifiers={
                        "sha256": reference.sha256,
                        "relative_path": reference.relative_path,
                    },
                    evidence_record_ids=[evidence_id],
                )
            )
        graph.upsert_relationship(
            RelationshipAssertion(
                relationship_id=_identity(
                    "relationship:retained-input", [document_id, item.receipt_id]
                ),
                subject_entity_id=item.source_entity_id,
                object_entity_id=document_id,
                predicate="derived_from_retained_input",
                relationship_status=RelationshipStatus.CONFIRMED,
                supporting_evidence_ids=[evidence_id, item.evidence.evidence_id],
                first_seen=item.effective_at,
                last_seen=item.effective_at,
                evidence_summary="Exact input lineage, independent of project identity.",
            )
        )

    def _enrich(
        self, store: IntelligenceStore, item: InvestigationObservation, parent: str
    ) -> None:
        self.queue.enqueue_in_transaction(
            store,
            JobDefinition(
                kind="correlate_source",
                inputs={
                    "source_id": item.source_entity_id,
                    "receipt_id": item.receipt_id,
                    "after": "",
                },
                depends_on=[parent],
            ),
        )
        self._schedule_location(store, item, parent)

    def _schedule_location(
        self, store: IntelligenceStore, item: InvestigationObservation, parent: str
    ) -> None:
        if not item.county or item.evidence.record_type == "parcel":
            return
        self.queue.enqueue_in_transaction(
            store,
            JobDefinition(
                kind="parcel_assess",
                inputs={"source_id": item.source_entity_id, "receipt_id": item.receipt_id},
                depends_on=[parent],
            ),
        )

    def _handle(self, store: IntelligenceStore, claim: JobState) -> dict[str, Any]:
        inputs = claim.definition.inputs
        service = InvestigationService(store)
        kind = claim.definition.kind
        if kind in {"retained_json_replay", "smarts_replay"}:
            reference = InputRef.model_validate(inputs["input"])
            content = read_input(self.directory, reference)
            if kind == "retained_json_replay":
                rows = self._json_rows(content)
                offset = inputs["offset"]
                if type(offset) is not int or offset < 0 or offset >= len(rows):
                    raise ValueError("invalid retained input offset")
                items = [
                    normalize_retained_record(inputs["source_kind"], row)
                    for row in rows[offset : offset + BATCH]
                ]
                for item in items:
                    service.ingest(item)
                    self._lineage(store, reference, item)
                    if inputs.get("parent_input"):
                        parent_input = InputRef.model_validate(inputs["parent_input"])
                        read_input(self.directory, parent_input)
                        self._lineage(store, parent_input, item)
                    self._enrich(store, item, claim.job_id)
                following = offset + len(items)
                if following < len(rows):
                    self.queue.enqueue_in_transaction(
                        store,
                        JobDefinition(
                            kind=kind,
                            inputs={**inputs, "offset": following},
                            depends_on=[claim.job_id],
                        ),
                    )
                return {
                    "processed": len(items),
                    "next_offset": following,
                    "row_count": len(rows),
                    "input_sha256": reference.sha256,
                }
            snapshot = json.loads(content)
            entries = snapshot["observations"]
            if not 1 <= len(entries) <= BATCH:
                raise ValueError("SMARTS snapshot exceeds the bounded page")
            previous = store.session.scalar(
                select(IntelligenceRuntimeEventRecord)
                .where(
                    IntelligenceRuntimeEventRecord.source_service == "investigation_smarts_cursor"
                )
                .order_by(IntelligenceRuntimeEventRecord.id.desc())
                .limit(1)
            )
            current = (
                RuntimeEvent.model_validate_json(previous.payload_json).payload
                if previous
                else None
            )
            after = int(current["observation_id"]) if current else 0
            if after >= entries[-1]["observation_id"]:
                return {"superseded_by_cursor": after, "processed": 0}
            if snapshot["after_id"] > after:
                raise ValueError("SMARTS snapshot skips the committed source cursor")
            if snapshot["after_id"] < after:
                overlap = [entry for entry in entries if entry["observation_id"] == after]
                if (
                    current is None
                    or not overlap
                    or InvestigationObservation.model_validate(overlap[0]["observation"]).receipt_id
                    != current["receipt_id"]
                ):
                    raise ValueError("overlapping SMARTS snapshot changed retained cursor lineage")
            for entry in entries:
                item = InvestigationObservation.model_validate(entry["observation"])
                raw = InputRef.model_validate(entry["raw_input"])
                read_input(self.directory, raw)
                service.ingest(item)
                self._lineage(store, raw, item)
                self._enrich(store, item, claim.job_id)
            last = entries[-1]
            retained = InvestigationObservation.model_validate(last["observation"])
            cursor = {"observation_id": last["observation_id"], "receipt_id": retained.receipt_id}
            store.add_runtime_event(
                RuntimeEvent(
                    event_id=_identity("event:investigation-smarts-cursor", cursor),
                    event_type=RuntimeEventType.SOURCE_CURSOR_ADVANCED,
                    source_service="investigation_smarts_cursor",
                    payload=cursor,
                    message="Validated retained SMARTS journal cursor committed.",
                )
            )
            return {"processed": len(entries), **cursor}
        item = service.current_observation(inputs["source_id"])
        if item.receipt_id != inputs["receipt_id"]:
            self._enrich(store, item, claim.job_id)
            return {"superseded_by_receipt": item.receipt_id}
        if kind == "correlate_source":
            source_ids = list(
                store.session.scalars(
                    select(IntelligenceEntityRecord.entity_id)
                    .where(
                        IntelligenceEntityRecord.entity_id.startswith("source-record:"),
                        IntelligenceEntityRecord.entity_id > inputs["after"],
                        IntelligenceEntityRecord.entity_id != item.source_entity_id,
                    )
                    .order_by(IntelligenceEntityRecord.entity_id)
                    .limit(BATCH + 1)
                )
            )
            supported = []
            reviewed = 0
            for source_id in source_ids[:BATCH]:
                if item.evidence.record_type == "parcel":
                    other = service.current_observation(source_id)
                    county = " ".join((item.county or "").casefold().split()).removesuffix(
                        " county"
                    )
                    other_county = " ".join((other.county or "").casefold().split()).removesuffix(
                        " county"
                    )
                    if county and county == other_county:
                        # Location assessment is independent of project matching,
                        # including a rejected same-project relationship.
                        self._schedule_location(store, other, claim.job_id)
                try:
                    candidate = service.correlate(item.source_entity_id, source_id)
                    supported.append(candidate.candidate_id)
                except NoCorrelationEvidence:
                    continue
                except ReviewedCorrelation:
                    reviewed += 1
            if len(source_ids) > BATCH:
                self.queue.enqueue_in_transaction(
                    store,
                    JobDefinition(
                        kind=kind,
                        inputs={**inputs, "after": source_ids[BATCH - 1]},
                        depends_on=[claim.job_id],
                    ),
                )
            return {
                "examined": min(len(source_ids), BATCH),
                "candidates": supported,
                "reviewed_decisions_preserved": reviewed,
                "continued": len(source_ids) > BATCH,
            }
        if kind == "parcel_assess":
            # Query committed parcel observations, preserving each source identity.
            # Arrival of either a site or a related parcel triggers this same job.
            identities = list(
                store.session.scalars(
                    select(IntelligenceEntityRecord.entity_id)
                    .where(
                        IntelligenceEntityRecord.entity_type == EntityType.PARCEL.value,
                        IntelligenceEntityRecord.entity_id.startswith("source-record:"),
                    )
                    .order_by(IntelligenceEntityRecord.entity_id)
                    .limit(1001)
                )
            )
            county = " ".join((item.county or "").casefold().split()).removesuffix(" county")
            parcels = []
            for identity in identities[:1000]:
                parcel_item = service.current_observation(identity)
                parcel_county = " ".join(
                    (parcel_item.county or "").casefold().split()
                ).removesuffix(" county")
                if county != parcel_county:
                    continue
                parcels.append(
                    ParcelCoreRecord.model_validate(
                        parcel_item.evidence.raw_observations["parcel_record"]
                    )
                )
            result = InvestigationLocationService(store).resolve(item.source_entity_id, parcels)
            return {
                "resolution_id": result.resolution_id,
                "project_identity_verified": False,
                "parcel_observations_examined": min(len(identities), 1000),
                "parcel_pool_truncated": len(identities) > 1000,
            }
        raise ValueError("unsupported investigation job kind")

    def run_once(self, worker_id: str) -> JobState | None:
        claim = self.queue.claim(worker_id)
        if claim is None:
            return None
        try:
            with managed_session(self.queue.factory) as session:
                self.queue.begin_write(session)
                store = IntelligenceStore(session)
                self.queue.validate_claim(store, claim)
                result = self._handle(store, claim)
                return self.queue.complete_in_transaction(store, claim, result)
        except (OperationalError, sqlite3.OperationalError):
            return self.queue.fail(claim, error_code="local_database_unavailable", retryable=True)
        except (ValueError, OSError, KeyError, TypeError):
            # Preserve the retained input and mark the gap. Do not consume it as success,
            # bypass validation, or put source content/credentials into a log message.
            return self.queue.fail(
                claim, error_code="retained_input_or_state_validation_failed", retryable=False
            )

    def process(
        self,
        *,
        max_jobs: int = BATCH,
        poll_smarts: bool = False,
        poll_inbox: bool = False,
        poll_ceqa: bool = False,
        startup: Path | None = None,
    ) -> dict[str, int]:
        """Bound one independently scheduled turn; processing never authorizes collection."""
        if type(max_jobs) is not int or not 1 <= max_jobs <= 500:
            raise ValueError("max_jobs must be between 1 and 500")
        processed = failed = 0
        smarts_polled = False
        active_path = self.directory / "active.json"
        capture_at = (
            json.loads(read_runtime_text(active_path)).get("captured_at")
            if poll_smarts and active_path.exists()
            else None
        )
        acquisition = {}
        if poll_ceqa:
            from constructionsight.ceqanet_background import poll_background

            if startup is None or data_folder.resolve_folder(startup) == self.directory:
                try:
                    acquisition = poll_background(self)
                except (ValueError, OSError, SQLAlchemyError):
                    # An invalid acquisition capability cannot prevent already
                    # retained evidence from progressing through independent jobs.
                    acquisition = {"ceqa_acquired": 0, "ceqa_failed": 1}
                write_runtime_text(
                    self.directory / "ceqa-background-run.json",
                    json.dumps({"completed_at": datetime.now(UTC).isoformat(), **acquisition}),
                )
        inbox = {}
        if poll_inbox:
            from constructionsight.investigation_inbox import poll_retained_inbox

            inbox = poll_retained_inbox(self)
        worker = f"local:{os.getpid()}:{uuid.uuid4().hex}"
        for _ in range(max_jobs):
            if startup is not None and data_folder.resolve_folder(startup) != self.directory:
                break
            if poll_smarts:
                self.enqueue_smarts()
                smarts_polled = (self.directory / "evidence.sqlite3").exists()
            result = self.run_once(worker)
            if result is None:
                break
            processed += 1
            failed += result.status in {"failed", "blocked"}
        report = {"processed_jobs": processed, "failed_jobs": failed, **inbox, **acquisition}
        write_runtime_text(
            self.directory / "investigation-worker-run.json",
            json.dumps(
                {
                    "source_capture_at": capture_at,
                    "smarts_polled": smarts_polled,
                    "completed_at": datetime.now(UTC).isoformat(),
                    **report,
                }
            ),
        )
        return report


def enqueue_smarts_capture(directory: Path) -> dict[str, Any]:
    """Notify the common engine after acquisition; keep capture and processing outcomes distinct."""
    runtime = None
    try:
        runtime = InvestigationRuntime(directory)
        job = runtime.enqueue_smarts()
        return {"status": "queued" if job else "idle", "job_id": job.job_id if job else None}
    except (ValueError, OSError, SQLAlchemyError):
        # Exact source evidence is already retained. The independent worker can
        # resume its journal cursor later; a failed handoff is not hidden as success.
        return {"status": "error", "error_code": "investigation_handoff_failed"}
    finally:
        if runtime is not None:
            runtime.close()


def systemd_units(executable: Path, startup_directory: Path) -> dict[str, str]:
    command = " ".join(
        unit_quote(str(value))
        for value in (
            executable.absolute(),
            "-m",
            "constructionsight.investigation_runtime",
            "--data-dir",
            startup_directory.absolute(),
            "run",
            "--poll-smarts",
            "--poll-inbox",
            "--poll-ceqa",
            "--max-jobs",
            "100",
        )
    )
    return {
        "constructionsight-investigations.service": (
            "[Unit]\nDescription=ConstructionSight retained-evidence investigation worker\n"
            "[Service]\nType=oneshot\nUMask=0077\nNoNewPrivileges=true\n"
            f"ExecStart={command}\nTimeoutStartSec=900\n"
        ),
        "constructionsight-investigations.timer": (
            "[Unit]\nDescription=Resume ConstructionSight investigations independently of Work\n"
            "[Timer]\nOnBootSec=30s\nOnUnitInactiveSec=30s\nPersistent=true\n"
            "[Install]\nWantedBy=timers.target\n"
        ),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=Path, required=True)
    commands = parser.add_subparsers(dest="command", required=True)
    enqueue = commands.add_parser("enqueue")
    enqueue.add_argument("--source", required=True, type=Path)
    enqueue.add_argument("--kind", required=True, choices=RUNTIME_SOURCE_KINDS)
    run = commands.add_parser("run")
    run.add_argument("--poll-smarts", action="store_true")
    run.add_argument("--poll-inbox", action="store_true")
    run.add_argument("--poll-ceqa", action="store_true")
    run.add_argument("--max-jobs", default=25, type=int)
    commands.add_parser("status")
    commands.add_parser("units")
    args = parser.parse_args(argv)
    if args.command == "run" and not 1 <= args.max_jobs <= 500:
        parser.error("max-jobs must be between 1 and 500")
    startup = args.data_dir.absolute()
    if args.command == "units":
        print(json.dumps(systemd_units(Path(sys.executable), startup)))
        return 0
    directory = data_folder.resolve_folder(startup)
    runtime = InvestigationRuntime(directory)
    try:
        if args.command == "enqueue":
            print(runtime.enqueue_json(args.source, args.kind).model_dump_json())
            return 0
        if args.command == "status":
            print(
                json.dumps([state.model_dump(mode="json") for state in runtime.queue.list_jobs()])
            )
            return 0
        report = runtime.process(
            max_jobs=args.max_jobs,
            poll_smarts=args.poll_smarts,
            poll_inbox=args.poll_inbox,
            poll_ceqa=args.poll_ceqa,
            startup=startup,
        )
        print(json.dumps(report))
        return (
            1
            if report["failed_jobs"]
            or report.get("inbox_failed", 0)
            or report.get("ceqa_failed", 0)
            else 0
        )
    finally:
        runtime.close()


if __name__ == "__main__":
    raise SystemExit(main())
