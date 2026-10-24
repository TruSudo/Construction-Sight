"""Append synthetic original result revisions to one exact browser-reviewed workflow."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from constructionsight.lead_operator_service import load_persisted_lead_workflow
from constructionsight.operator_results import read_validated_result_history
from constructionsight.result_ledger_models import ResultLedgerStatus
from constructionsight.result_ledger_service import (
    build_result_ledger_record,
    supersede_result_ledger_record,
)
from constructionsight.storage.database import create_private_database_engine
from constructionsight.storage.lead_workflow_orm import LeadFingerprintRecord
from constructionsight.storage.lead_workflow_store import store_result_ledger_record


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", type=Path)
    parser.add_argument("workflow_id")
    args = parser.parse_args()
    engine = create_private_database_engine(
        args.directory / "investigations.sqlite3", create=False,
    )
    try:
        with Session(engine) as session, session.begin():
            workflow = load_persisted_lead_workflow(session, args.workflow_id)
            fingerprint = session.scalar(select(LeadFingerprintRecord).where(
                LeadFingerprintRecord.fingerprint_key == workflow.fingerprint_key,
                LeadFingerprintRecord.source_key == "canonical_investigation",
            ))
            if (
                fingerprint is None or not fingerprint.source_record_id
                or "Canonical investigation: " + fingerprint.source_record_id
                not in workflow.notes
            ):
                raise ValueError("fixture requires the exact retained canonical workflow")
            if read_validated_result_history(session, workflow.workflow_id) is not None:
                raise ValueError("fixture refuses to replace an existing result history")
            root = build_result_ledger_record(
                workflow=workflow, status=ResultLedgerStatus.UNKNOWN,
                reasons=["Synthetic browser result is initially unestablished"],
            )
            calculated = supersede_result_ledger_record(
                current=root, status=ResultLedgerStatus.WON,
                gross_value=1234.56, share_rate=0.1,
                correction_reason="Synthetic recorded win for exact-money history inspection",
                reasons=["Fixture calculation is not an award, contract or entitlement"],
            )
            corrected = supersede_result_ledger_record(
                current=calculated, status=ResultLedgerStatus.LOST,
                correction_reason="Synthetic correction removes the current calculated share",
                reasons=["Prior calculated shares remain historical and must not be summed"],
            )
            for revision in (root, calculated, corrected):
                store_result_ledger_record(session, revision)
            session.flush()
            retained = read_validated_result_history(session, workflow.workflow_id)
            if retained is None or retained["revision_count"] != 3:
                raise RuntimeError("synthetic original result revisions were not retained")
        print(json.dumps(retained))
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
