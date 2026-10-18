"""Isolated Phase 8 native/legacy read-only browser fixture. No external collection."""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import UTC, date, datetime
from pathlib import Path

from sqlalchemy.orm import Session

from constructionsight.ceqa_models import CeqaRecord
from constructionsight.entity_models import Entity
from constructionsight.investigation_runtime import InvestigationRuntime
from constructionsight.lead_operator_service import transition_persisted_lead_workflow
from constructionsight.lead_workflow_models import LeadWorkflowStatus
from constructionsight.lead_workflow_service import create_lead_workflow
from constructionsight.live_command_center import make_server
from constructionsight.permit_models import PermitRecord
from constructionsight.provenance import Provenance
from constructionsight.result_ledger_models import ResultLedgerStatus
from constructionsight.result_ledger_service import (
    build_result_ledger_record,
    supersede_result_ledger_record,
)
from constructionsight.site_models import Site
from constructionsight.storage.database import create_database_engine, initialize_database
from constructionsight.storage.domain_store import CeqaStore, PermitStore
from constructionsight.storage.lead_workflow_store import (
    store_lead_review_package,
    store_lead_workflow_record,
    store_result_ledger_record,
)
from constructionsight.storage.source_registry import SourceRegistryStore
from tests.test_bid_proposal_service import _package
from tests.test_ceqanet_operator_export import _chain_report
from tests.test_operator_capture_queue import _payload as capture_fixture
from tests.test_operator_ingestion_inbox import _write_artifacts
from tests.test_operator_source_registry import _source
from tests.test_smarts_parcel_review import _change, _environment, _parcel

parser = argparse.ArgumentParser()
parser.add_argument("--data-dir", type=Path, required=True)
parser.add_argument("--port", type=int, default=8783)
args = parser.parse_args()
args.data_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
database = args.data_dir / "operator-source.sqlite3"
engine = create_database_engine(f"sqlite:///{database}")
initialize_database(engine)
with Session(engine) as session, session.begin():
    SourceRegistryStore(session).upsert_source(_source(
        "Synthetic retained portal", county="Riverside",
    ))
    source_candidate_id = "source-candidate:" + hashlib.sha256(
        json.dumps(
            ["ceqa", "phase8:browser:source"],
            separators=(",", ":"), ensure_ascii=False,
        ).encode("utf-8")
    ).hexdigest()
    package = _package().model_copy(update={"base_candidate_id": source_candidate_id})
    workflow = create_lead_workflow(package=package)
    store_lead_review_package(session, package)
    store_lead_workflow_record(session, workflow)
    root_result = build_result_ledger_record(
        workflow=workflow, status=ResultLedgerStatus.UNKNOWN,
        reasons=["Synthetic fixture result not established"],
    )
    revised_result = supersede_result_ledger_record(
        current=root_result, status=ResultLedgerStatus.WON,
        correction_reason="Fixture illustrates correction, not actual award",
        gross_value=1234.56, share_rate=0.1,
    )
    store_result_ledger_record(session, root_result)
    store_result_ledger_record(session, revised_result)
    evidence = Provenance(
        source_name="Synthetic Phase 8 retained fixture",
        evidence_text="Not an actual jurisdictional observation",
        captured_at=datetime(2026, 10, 17, tzinfo=UTC),
    )
    CeqaStore(session).upsert(
        CeqaRecord(
            ceqa_key="phase8:browser:source",
            title="Synthetic retained source observation",
            county="Riverside",
            lead_agency="Synthetic Planning Department",
            state_clearinghouse_number="2099012345",
            received_date=date(2026, 10, 12),
            posted_date=date(2026, 10, 13),
            entities=[Entity(
                entity_key="phase8:browser:entity", name="Synthetic Contractor",
                role="contractor", provenance=[evidence],
            )],
            site=Site(
                site_key="phase8:browser:site",
                county="Riverside",
                apn="000-111-222",
                latitude=33.95,
                longitude=-117.36,
                provenance=[evidence],
            ),
            provenance=[evidence],
        )
    )
    # A second exact retained source is already committed by the native
    # investigation worker. It exercises dossier-level historical lineage
    # without affecting the first source's explicit replay-queue browser test.
    dossier_record = CeqaRecord(
        ceqa_key="phase8:browser:dossier",
        title="Synthetic native dossier with retained historical outcome",
        county="Riverside",
        lead_agency="Synthetic Local Review",
        site=Site(
            site_key="phase8:browser:dossier-site",
            county="Riverside",
            apn="999-888-777",
            provenance=[evidence],
        ),
        provenance=[evidence],
    )
    CeqaStore(session).upsert(dossier_record)
    CeqaStore(session).upsert(CeqaRecord(
        ceqa_key="phase8:browser:batch:ceqa",
        title="Synthetic scoped migration source",
        county="Riverside", provenance=[evidence],
    ))
    PermitStore(session).upsert(PermitRecord(
        permit_key="phase8:browser:batch:permit",
        permit_number="Synthetic scoped migration permit",
        jurisdiction="Synthetic Planning Department",
        county="Riverside", provenance=[evidence],
    ))
    dossier_candidate_id = "source-candidate:" + hashlib.sha256(
        json.dumps(
            ["ceqa", dossier_record.ceqa_key], separators=(",", ":"),
            ensure_ascii=False,
        ).encode("utf-8")
    ).hexdigest()
    dossier_package = _package().model_copy(update={
        "package_id": "lead-review:browser:dossier",
        "base_candidate_id": dossier_candidate_id,
    })
    dossier_workflow = create_lead_workflow(package=dossier_package)
    store_lead_review_package(session, dossier_package)
    store_lead_workflow_record(session, dossier_workflow)
    dossier_result = build_result_ledger_record(
        workflow=dossier_workflow, status=ResultLedgerStatus.WON,
        gross_value=2500.0, share_rate=0.08,
    )
    store_result_ledger_record(session, dossier_result)
    # Exactly twenty-six additional historical workflows and outcomes:
    # enough to demonstrate a second bounded page in both views.
    # They are deliberately unlinked synthetic history, never new native leads.
    for index in range(26):
        extra_package = _package().model_copy(update={
            "package_id": f"lead-review:phase8:pagination:{index:02d}",
            "base_candidate_id": f"synthetic:historical-page:{index:02d}",
        })
        extra_workflow = create_lead_workflow(package=extra_package)
        store_lead_review_package(session, extra_package)
        store_lead_workflow_record(session, extra_workflow)
        store_result_ledger_record(session, build_result_ledger_record(
            workflow=extra_workflow,
            status=ResultLedgerStatus.UNKNOWN,
            reasons=["Synthetic historical pagination record; no award or payment"],
        ))
with Session(engine) as session, session.begin():
    transition_persisted_lead_workflow(
        session, workflow_id=dossier_workflow.workflow_id,
        expected_current_status=LeadWorkflowStatus.READY,
        next_status=LeadWorkflowStatus.ACTIVE,
        reason="Synthetic history: original operator moved from ready to active",
    )
engine.dispose()
native = InvestigationRuntime(args.data_dir / "native")
try:
    native.enqueue_bytes(dossier_record.model_dump_json(round_trip=True).encode(), "ceqa")
    if native.process(max_jobs=10)["failed_jobs"]:
        raise RuntimeError("Synthetic native dossier fixture ingestion failed")
finally:
    native.close()
smarts_root, smarts_history, _unused_smarts_database = _environment(args.data_dir / "smarts")
_change(smarts_root, smarts_history)
_parcel(database, "parcel:browser:smarts")
listing, review = _write_artifacts(args.data_dir)
capture = args.data_dir / "capture.json"
capture.write_text(json.dumps(capture_fixture()), encoding="utf-8")
chain = args.data_dir / "ceqanet-chain-report.json"
chain.write_text(json.dumps(_chain_report()), encoding="utf-8")
aliases = args.data_dir / "source-attribution-aliases.json"
aliases.write_text(json.dumps({
    "schema_version": "constructionsight.source_attribution_aliases.v1",
    "mapping_count": 1, "network_executed": False, "persistence_mutated": False,
    "mappings": [{
        "alias_source_name": "Synthetic Phase 8 retained fixture",
        "canonical_source_name": "Synthetic retained portal",
        "reason": "Exact synthetic source-name attribution for native parity acceptance.",
        "evidence_refs": ["synthetic:phase8:registry-attribution"],
    }],
}), encoding="utf-8")
snapshot = {
    "rows": [],
    "captured_at": "2026-10-17T09:00:00+00:00",
    "requests": 0,
    "totals": {"San Bernardino": 0, "Riverside": 0},
    "baseline": True,
    "missing_count": 0,
}
server = make_server(
    snapshot, args.port, args.data_dir / "native", operator_database=database,
    operator_capture_queue=capture, operator_ceqanet_listing=listing,
    operator_ceqanet_review_queue=review,
    operator_smarts_history=smarts_history,
    operator_ceqanet_chain_report=chain,
    operator_source_attribution_aliases=aliases,
)
print("Phase 8 read-only source fixture", server.server_port, flush=True)
try:
    server.serve_forever()
finally:
    server.server_close()
