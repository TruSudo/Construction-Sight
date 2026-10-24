"""P8-11: native original saved-execution chain equals the retained CLI composer."""

from __future__ import annotations

import hashlib
import json
import threading
from pathlib import Path

import httpx
import pytest

from constructionsight.ceqanet_chain_cli import (
    _build_chain_report,
    build_chain_report_from_saved_executions,
)
from constructionsight.command_center_ceqanet_chain import original_offline_chain_preview
from constructionsight.live_command_center import make_server
from tests.test_ceqanet_chain_cli import _detail_html, _listing_html
from tests.test_command_center_investigation_bridge import snapshot


def _execution(body_text: str, final_url: str) -> dict[str, object]:
    return {
        "metadata": {"schema_version": "ceqanet_execution_fixture.v1"},
        "snapshots": [{
            "request_url": final_url,
            "final_url": final_url,
            "status_code": 200,
            "content_type": "text/html; charset=utf-8",
            "body_text": body_text,
            "body_length": len(body_text),
            "body_truncated": False,
            "executed": True,
            "reachable": True,
        }],
    }


def _payload() -> dict[str, object]:
    return {
        "listing_execution": _execution(
            _listing_html(), "https://ceqanet.lci.ca.gov/Search?County=San+Bernardino",
        ),
        "detail_executions": [
            _execution(_detail_html(), "https://ceqanet.lci.ca.gov/Project/2017101033")
        ],
        "listing_snapshot_index": 0,
    }


def test_native_reuses_original_chain_composition_exactly(tmp_path: Path) -> None:
    payload = _payload()
    listing = tmp_path / "listing.json"
    detail = tmp_path / "detail.json"
    listing.write_text(json.dumps(payload["listing_execution"]), encoding="utf-8")
    detail.write_text(json.dumps(payload["detail_executions"][0]), encoding="utf-8")
    before = {
        "listing": hashlib.sha256(listing.read_bytes()).hexdigest(),
        "detail": hashlib.sha256(detail.read_bytes()).hexdigest(),
    }
    cli = _build_chain_report(
        listing_execution_path=listing,
        detail_execution_paths=[detail],
        listing_snapshot_index=0,
    )
    same_builder = build_chain_report_from_saved_executions(
        payload["listing_execution"], payload["detail_executions"],
        listing_snapshot_index=0,
        listing_label=str(listing), detail_labels=[str(detail)],
    )
    assert same_builder == cli
    native = original_offline_chain_preview(payload)
    report = native["original_chain_report"]
    assert report["metadata"]["schema_version"] == "ceqanet_chain_report.v1"
    assert report["metadata"]["result_record_count"] == 2
    assert report["metadata"]["enriched_count"] == 1
    assert report["metadata"]["missing_detail_count"] == 1
    assert report["metadata"]["sch_mismatch_count"] == 0
    assert report["enrichment"] == cli["enrichment"]
    assert report["result_parse"]["records"] == cli["result_parse"]["records"]
    assert report["detail_parse_summaries"][0]["sch_number"] == "2017101033"
    assert report["metadata"]["listing_execution_path"] == (
        "native-offline-listing-execution"
    )
    assert report["metadata"]["detail_execution_paths"] == [
        "native-offline-detail-execution-0"
    ]
    assert all(len(digest) == 64 for digest in [
        native["input_canonical_json_sha256"]["listing_execution"],
        *native["input_canonical_json_sha256"]["detail_executions"],
    ])
    assert native["network_executed"] is False
    assert native["source_database_mutated"] is False
    assert native["chain_report_retained"] is False
    assert native["commercial_authority_granted"] is False
    assert hashlib.sha256(listing.read_bytes()).hexdigest() == before["listing"]
    assert hashlib.sha256(detail.read_bytes()).hexdigest() == before["detail"]


@pytest.mark.parametrize("mutation", [
    lambda p: p.update({"execute": True}),
    lambda p: p.update({"listing_execution": []}),
    lambda p: p.update({"detail_executions": [{}] * 26}),
    lambda p: p.update({"detail_executions": [{}]}),
    lambda p: p.update({"listing_snapshot_index": True}),
    lambda p: p.update({"listing_snapshot_index": -1}),
    lambda p: p.update({"listing_snapshot_index": 25}),
    lambda p: p["listing_execution"].update({"snapshots": []}),
    lambda p: p["listing_execution"]["snapshots"][0].update({"body_text": None}),
])
def test_native_saved_chain_invalid_or_ambiguous_input_fails_closed(mutation) -> None:
    payload = _payload()
    mutation(payload)
    with pytest.raises(ValueError):
        original_offline_chain_preview(payload)


def test_native_chain_snapshot_index_and_input_digest_boundaries() -> None:
    payload = _payload()
    original = original_offline_chain_preview(payload)
    changed = _payload()
    changed["listing_execution"]["snapshots"][0]["body_text"] += " "
    other = original_offline_chain_preview(changed)
    assert (
        original["input_canonical_json_sha256"]["listing_execution"]
        != other["input_canonical_json_sha256"]["listing_execution"]
    )
    assert original["input_canonical_json_sha256"]["detail_executions"] == (
        other["input_canonical_json_sha256"]["detail_executions"]
    )
    payload["listing_execution"]["snapshots"].append({"body_text": "<html></html>"})
    payload["listing_snapshot_index"] = 1
    second = original_offline_chain_preview(payload)
    assert second["original_chain_report"]["metadata"]["result_record_count"] == 0


def test_native_original_saved_chain_http_same_origin_and_no_writes(tmp_path: Path) -> None:
    private = tmp_path / "private"
    server = make_server(snapshot(), 0, private)
    worker = threading.Thread(target=server.serve_forever, daemon=True)
    worker.start()
    try:
        base = f"http://127.0.0.1:{server.server_port}"
        before = sorted(str(p.relative_to(tmp_path)) for p in tmp_path.rglob("*"))
        with httpx.Client(base_url=base, trust_env=False) as client:
            endpoint = "/api/source-ceqanet-offline-chain-preview"
            payload = _payload()
            assert client.post(endpoint, json=payload).status_code == 403
            assert client.post(
                endpoint, json=payload, headers={"Origin": "https://foreign.invalid"},
            ).status_code == 403
            assert client.post(
                endpoint + "?execute=true", json=payload, headers={"Origin": base},
            ).status_code == 400
            assert client.post(
                endpoint, json=payload,
                headers={"Origin": base, "Sec-Fetch-Site": "cross-site"},
            ).status_code == 400
            response = client.post(endpoint, json=payload, headers={"Origin": base})
            assert response.status_code == 200, response.text
            data = response.json()
            assert data["original_chain_report"]["metadata"]["enriched_count"] == 1
            assert data["chain_report_retained"] is False
            assert data["commercial_authority_granted"] is False
            assert data["network_executed"] is False
        after = sorted(str(p.relative_to(tmp_path)) for p in tmp_path.rglob("*"))
        assert before == after
    finally:
        server.shutdown()
        server.server_close()
        worker.join()
