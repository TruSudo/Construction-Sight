"""Verify that the frozen Phase 8 historical path ledger loses no branch evidence.

The ledger is an observation against one recorded tree, not runtime parity proof.
This test deliberately never upgrades P8-01 or relies on live GitHub/network.
"""

from __future__ import annotations

import json
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
_BASELINE = _ROOT / "docs/audits/unification-preservation-baseline-2026-10-16.json"
_LEDGER = _ROOT / "docs/audits/p8-01-historical-path-ledger-2026-10-21.json"


def test_p8_01_ledger_accounts_for_every_retained_historical_path() -> None:
    baseline = json.loads(_BASELINE.read_text(encoding="utf-8"))
    ledger = json.loads(_LEDGER.read_text(encoding="utf-8"))

    expected: dict[str, dict[str, set[str]]] = {}
    for branch in baseline["contribution_inventory"]["branches"]:
        for file in branch["contributed_files"]:
            record = expected.setdefault(
                file["path"],
                {"branches": set(), "blobs": set(), "comparisons": set()},
            )
            record["branches"].add(branch["ref"])
            if file.get("branch_blob"):
                record["blobs"].add(file["branch_blob"])
            record["comparisons"].add(file["comparison"])

    for path, branches in baseline["contribution_inventory"]["missing_paths"].items():
        record = expected.setdefault(
            path,
            {"branches": set(), "blobs": set(), "comparisons": set()},
        )
        record["branches"].update(branches)

    rows = ledger["entries"]
    paths = [row["path"] for row in rows]
    assert len(paths) == len(set(paths)) == len(expected) == 302
    assert set(paths) == set(expected)
    assert ledger["history_branches_examined"] == len(
        baseline["contribution_inventory"]["branches"]
    ) == 83
    assert ledger["frozen_baseline_sha"] == baseline["baseline"]
    assert ledger["development_tree_truncated"] is False
    assert ledger["accepted_p8_01"] is False
    assert ledger["accepted_integration_gates_before_audit"] == 10
    assert ledger["total_integration_gates"] == 15

    observations: dict[str, int] = {}
    for row in rows:
        known = expected[row["path"]]
        assert set(row["branch_refs"]) == known["branches"]
        assert set(row["historical_blob_shas"]) == known["blobs"]
        assert set(row["baseline_comparison_classes"]) == known["comparisons"]
        assert row["functional_equivalence"] == "not_assessed_by_this_ledger"

        current_sha = row["current_blob_sha"]
        if current_sha is None:
            observation = "absent"
        elif current_sha in known["blobs"]:
            observation = "present_exact_historical_blob"
        else:
            observation = "present_different_blob_or_unproven"
        assert row["storage_observation"] == observation
        observations[observation] = observations.get(observation, 0) + 1

    assert observations == ledger["storage_observations"]
    assert observations == {
        "absent": 43,
        "present_exact_historical_blob": 95,
        "present_different_blob_or_unproven": 164,
    }
