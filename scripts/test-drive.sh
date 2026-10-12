#!/usr/bin/env bash
# Start an isolated, read-only trial using retained public-source evidence.
set -euo pipefail

cs_repo="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
cs_python="${CONSTRUCTIONSIGHT_PYTHON:-python3}"
cs_home="${CONSTRUCTIONSIGHT_TEST_DRIVE_HOME:-${XDG_DATA_HOME:-$HOME/.local/share}/ConstructionSight/test-drive}"
cs_browser=(--open-browser)
case "${1:-}" in
    --no-browser) cs_browser=() ;;
    "") ;;
    *) echo "Usage: bash scripts/test-drive.sh [--no-browser]" >&2; exit 2 ;;
esac
cs_version="$("$cs_python" -c 'import sys; print(f"{sys.version_info.major}{sys.version_info.minor}")')"
case "$cs_version" in
    311|312) ;;
    *) echo "Use Python 3.11 or 3.12 (set CONSTRUCTIONSIGHT_PYTHON to its executable)." >&2; exit 2 ;;
esac
mkdir -p -- "$cs_home/sessions"
if [[ ! -x "$cs_home/venv/bin/python" ]]; then
    "$cs_python" -m venv "$cs_home/venv"
fi
cs_runtime="$cs_home/venv/bin"
cs_installed_version="$("$cs_runtime/python" -c 'import sys; print(f"{sys.version_info.major}{sys.version_info.minor}")')"
if [[ "$cs_installed_version" != "$cs_version" ]]; then
    echo "The trial environment uses another Python version. Choose a new CONSTRUCTIONSIGHT_TEST_DRIVE_HOME." >&2
    exit 2
fi
"$cs_runtime/python" -m pip install --disable-pip-version-check --require-hashes \
    --only-binary=:all: --no-deps -r "$cs_repo/requirements/py$cs_version.lock"
"$cs_runtime/python" -m pip install --disable-pip-version-check --no-index \
    --no-deps --no-build-isolation --force-reinstall "$cs_repo"
"$cs_runtime/python" -m pip check

cs_session="$(mktemp -d "$cs_home/sessions/trial-XXXXXXXX")"
cs_database="$cs_session/constructionsight.sqlite3"
cd -- "$cs_repo"
"$cs_runtime/constructionsight-ceqanet-csv" verify-replay \
    evidence/source_verification/ceqanet_csv_live_execution_2026-07-12.json \
    evidence/source_verification/ceqanet_csv_windows1252_replay_2026-07-12.json \
    --output "$cs_session/source-verification.json"
"$cs_runtime/constructionsight" init-db --database-url "sqlite:///$cs_database"
"$cs_runtime/constructionsight" load-sources data/source_registry.seed.json \
    --database-url "sqlite:///$cs_database"
"$cs_runtime/constructionsight-ceqanet-persistence-apply" execute \
    --write-plan examples/private_test_drive/ceqanet_retained_write_plan.json \
    --database-path "$cs_database" --execute-write --json-output \
    --authorization-reason "Load the two retained July 12 public CEQAnet observations into an isolated private trial." \
    --output "$cs_session/intake-result.json"

# Confirm the real, retained source -> canonical database -> review queue boundary.
# No new collection, commercial lead mutation or network request is authorized here.
"$cs_runtime/python" - "$cs_database" <<'PY'
import sys
from pathlib import Path

from sqlalchemy.orm import Session

from constructionsight.operator_source_review_queue import build_source_review_queue
from constructionsight.storage.operator_read_store import create_operator_read_engine

engine = create_operator_read_engine(Path(sys.argv[1]))
try:
    with Session(engine, autoflush=False) as session:
        queue = build_source_review_queue(
            session, kind="ceqa", county="Riverside", query="Cabazon", limit=10
        )
        assert queue.total_source_records == 2 and queue.returned == 2
        assert queue.read_only and not queue.network_executed
        assert not queue.source_records_mutated and not queue.lead_created
        assert not queue.outreach_authorized and not queue.bid_authorized
        assert len({item.record_id for item in queue.items}) == 2
        required = {
            "provenance", "county", "site", "parties",
            "current_activity", "deduplication", "commercial_review",
        }
        for item in queue.items:
            assert len(item.normalized_source_sha256) == 64
            assert item.preview_id.startswith("source-candidate-preview:")
            assert item.state in {"hold", "review_required"}
            assert {check.key for check in item.checks} == required
            assert not item.outreach_authorized and not item.bid_authorized
        print(
            "Retained source pilot: 2 real July 2026 CEQA observations "
            "reached evidence-bound review; 0 commercial leads authorized."
        )
finally:
    engine.dispose()
PY

echo "Private trial database: $cs_database"
echo "Two retained CEQAnet records from July 12, 2026; no fresh collection or outreach."
echo "Open http://127.0.0.1:8765 on this computer. Press Ctrl+C to stop."
exec "$cs_runtime/constructionsight-operator" --database "$cs_database" "${cs_browser[@]}"
