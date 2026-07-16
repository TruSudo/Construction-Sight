from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from constructionsight.ceqanet_csv_live_models import (
    CeqanetCsvLiveExecution,
    CeqanetCsvLiveVerification,
)
from constructionsight.ceqanet_csv_live_service import verify_ceqanet_csv_live_execution
from constructionsight.models import PublicSource, VerificationStatus

ROOT = Path(__file__).resolve().parents[1]
EVIDENCE_DIR = ROOT / "evidence/source_verification"
EXECUTION_PATH = EVIDENCE_DIR / "ceqanet_csv_live_execution_2026-07-12.json"
VERIFICATION_PATH = EVIDENCE_DIR / "ceqanet_csv_live_verification_2026-07-12.json"
REPORT_PATH = ROOT / "docs/audits/ceqanet_csv_live_proof_2026-07-12.md"


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def test_live_csv_evidence_is_replayable_and_does_not_promote_source() -> None:
    assert EXECUTION_PATH.is_file()
    assert VERIFICATION_PATH.is_file()
    assert REPORT_PATH.is_file()

    execution = CeqanetCsvLiveExecution.model_validate(_load_json(EXECUTION_PATH))
    stored_verification = CeqanetCsvLiveVerification.model_validate(_load_json(VERIFICATION_PATH))
    recomputed = verify_ceqanet_csv_live_execution(execution)

    assert execution.request.sch_number == "2026030377"
    assert execution.request.document_id is None
    assert execution.request_url == (
        "https://ceqanet.lci.ca.gov/Search?OutputFormat=CSV&Sch=2026030377"
    )
    assert execution.method == "GET"
    assert execution.network_executed is True
    assert execution.retry_count == 0
    assert execution.documents_downloaded is False
    assert execution.persistence_mutated is False
    execution.assert_integrity()
    assert stored_verification.passed is False
    assert stored_verification.findings == [
        "live CSV offline inspection failed: CEQAnet CSV body must use UTF-8 or UTF-8 with BOM",
        "live CSV inspection recorded error: CEQAnet CSV body must use UTF-8 or UTF-8 with BOM",
    ]
    assert recomputed.passed is False
    assert recomputed.findings == [
        "live CSV execution lacks the successful offline inspection",
        "live CSV inspection recorded error: CEQAnet CSV body must use UTF-8 or UTF-8 with BOM",
    ]

    if stored_verification.passed:
        assert execution.status_code == 200
        assert execution.inspection is not None
        assert execution.inspection_error is None
        assert stored_verification.findings == []
    else:
        assert stored_verification.finding_count > 0
        assert stored_verification.findings

    sources = [
        PublicSource.model_validate(item)
        for item in _load_json(ROOT / "data/source_registry.seed.json")
    ]
    ceqanet = [source for source in sources if source.platform_family.value == "ceqanet"]
    assert len(ceqanet) == 1
    assert ceqanet[0].verification_status is VerificationStatus.PARTIAL

    temporary_paths = (
        ROOT / ".github/workflows/ceqanet-live-csv-proof.yml",
        ROOT / "scripts/record_ceqanet_live_csv_proof.py",
    )
    assert all(not path.exists() for path in temporary_paths)
