"""Isolated Phase 8 native/legacy read-only browser fixture. No external collection."""

from __future__ import annotations

import argparse
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy.orm import Session

from constructionsight.ceqa_models import CeqaRecord
from constructionsight.live_command_center import make_server
from constructionsight.provenance import Provenance
from constructionsight.site_models import Site
from constructionsight.storage.database import create_database_engine, initialize_database
from constructionsight.storage.domain_store import CeqaStore

parser = argparse.ArgumentParser()
parser.add_argument("--data-dir", type=Path, required=True)
parser.add_argument("--port", type=int, default=8783)
args = parser.parse_args()
args.data_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
database = args.data_dir / "operator-source.sqlite3"
engine = create_database_engine(f"sqlite:///{database}")
initialize_database(engine)
with Session(engine) as session, session.begin():
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
            site=Site(
                site_key="phase8:browser:site",
                county="Riverside",
                apn="000-111-222",
                provenance=[evidence],
            ),
            provenance=[evidence],
        )
    )
engine.dispose()
snapshot = {
    "rows": [],
    "captured_at": "2026-10-17T09:00:00+00:00",
    "requests": 0,
    "totals": {"San Bernardino": 0, "Riverside": 0},
    "baseline": True,
    "missing_count": 0,
}
server = make_server(
    snapshot, args.port, args.data_dir / "native", operator_database=database
)
print("Phase 8 read-only source fixture", server.server_port, flush=True)
try:
    server.serve_forever()
finally:
    server.server_close()
