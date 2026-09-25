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
"$cs_runtime/constructionsight-ceqanet-persistence-apply" execute \
    --write-plan examples/private_test_drive/ceqanet_retained_write_plan.json \
    --database-path "$cs_database" --execute-write --json-output \
    --authorization-reason "Load the two retained July 12 public CEQAnet observations into an isolated private trial." \
    --output "$cs_session/intake-result.json"
echo "Private trial database: $cs_database"
echo "Two retained CEQAnet records from July 12, 2026; no fresh collection or outreach."
echo "Open http://127.0.0.1:8765 on this computer. Press Ctrl+C to stop."
exec "$cs_runtime/constructionsight-operator" --database "$cs_database" "${cs_browser[@]}"
