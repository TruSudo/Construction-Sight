"""Offline synthetic investigation fixture for native Command Center browser acceptance."""

from __future__ import annotations

import sys
from datetime import UTC, datetime
from pathlib import Path

from constructionsight.agenda_models import AgendaItemRecord
from constructionsight.ceqa_models import CeqaRecord
from constructionsight.investigation_runtime import InvestigationRuntime
from constructionsight.provenance import Provenance
from constructionsight.site_models import Site


def main() -> None:
    directory = Path(sys.argv[1])
    directory.mkdir(mode=0o700, parents=True, exist_ok=True)
    provenance = [Provenance(source_name="Offline browser fixture", captured_at=datetime(2026, 10, 16, tzinfo=UTC))]
    site = Site(site_key="synthetic:shared-workspace-site", county="Riverside", apn="123-456-789")
    records = (
        ("ceqa", CeqaRecord(
            ceqa_key="synthetic:browser:ceqa:1",
            title="Synthetic CEQA application",
            county="Riverside",
            state_clearinghouse_number="2026101234",
            site=site,
            provenance=provenance,
        )),
        ("agenda", AgendaItemRecord(
            agenda_key="synthetic:browser:agenda:1",
            title="Synthetic planning hearing",
            meeting_body="Planning Commission",
            jurisdiction="Synthetic municipality",
            county="Riverside",
            site=site,
            provenance=provenance,
        )),
    )
    runtime = InvestigationRuntime(directory)
    try:
        for kind, record in records:
            runtime.enqueue_bytes(record.model_dump_json(round_trip=True).encode(), kind)
        report = runtime.process(max_jobs=100)
        if report["failed_jobs"] or report["processed_jobs"] < 2:
            raise RuntimeError("synthetic browser investigation fixture did not complete")
    finally:
        runtime.close()


if __name__ == "__main__":
    main()
