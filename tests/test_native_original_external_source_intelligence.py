"""Original Shovels/Regrid research matrices remain read-only in native UI."""

from __future__ import annotations

import json
import threading
from pathlib import Path

import httpx

from constructionsight.command_center_external_source_intelligence import (
    original_external_source_intelligence,
)
from constructionsight.external_gap_registry import (
    build_gap_alignment_report,
    gap_matrix_rows,
    get_implementation_steps,
    get_knowledge_gaps,
    roadmap_rows,
)
from constructionsight.external_intelligence_registry import (
    build_capability_gap_report,
    capability_matrix_rows,
    get_external_capabilities,
)
from constructionsight.live_command_center import make_server
from tests.test_command_center_investigation_bridge import snapshot


def test_original_external_research_native_equivalence_without_vendor_access() -> None:
    report = original_external_source_intelligence()
    capability = get_external_capabilities()
    gaps = get_knowledge_gaps()
    assert report["original_capability_matrix"] == capability_matrix_rows(capability)
    assert report["original_capability_gap_report"] == (
        build_capability_gap_report(capability).model_dump(mode="json")
    )
    assert report["original_research_gap_matrix"] == gap_matrix_rows(gaps)
    assert report["original_alignment_report"] == (
        build_gap_alignment_report().model_dump(mode="json")
    )
    assert report["original_implementation_roadmap"] == roadmap_rows(
        get_implementation_steps()
    )
    assert report["network_executed"] is False
    assert report["source_database_mutated"] is False
    assert report["vendor_subscription_configured"] is False
    assert report["current_external_coverage_verified"] is False
    assert report["commercial_authority_granted"] is False
    assert {"shovels", "regrid"}.issubset(
        {row["platform"] for row in report["original_capability_matrix"]}
    )
    assert json.dumps(report, allow_nan=False)


def test_native_original_gap_research_endpoint_has_no_write_or_query(
    tmp_path: Path,
) -> None:
    server = make_server(snapshot(), 0, tmp_path)
    worker = threading.Thread(target=server.serve_forever, daemon=True)
    worker.start()
    try:
        host = f"http://127.0.0.1:{server.server_port}"
        with httpx.Client(base_url=host, trust_env=False) as client:
            response = client.get("/api/source-external-intelligence")
            assert response.status_code == 200, response.text
            assert response.json() == original_external_source_intelligence()
            assert client.get(
                "/api/source-external-intelligence?enable-vendor=true"
            ).status_code == 409
            assert client.post(
                "/api/source-external-intelligence",
                json={}, headers={"Origin": host},
            ).status_code == 501
    finally:
        server.shutdown()
        server.server_close()
        worker.join()
