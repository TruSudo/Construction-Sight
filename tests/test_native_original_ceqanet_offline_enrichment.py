"""Native CEQAnet result-to-detail review uses retained offline semantics only."""

from __future__ import annotations

import threading
from pathlib import Path

import httpx
import pytest

from constructionsight.command_center_ceqanet_enrichment import (
    preview_original_ceqanet_enrichment,
)
from constructionsight.live_command_center import make_server
from tests.test_command_center_investigation_bridge import snapshot


def _payload() -> dict[str, object]:
    return {
        "result_parse": {
            "metadata": {"schema_version": "ceqanet_result_page_parse.v1"},
            "records": [
                {
                    "title": "2026102233",
                    "title_source": "sch_number",
                    "sch_number": "2026102233",
                    "requires_detail_enrichment": True,
                    "detail_url": "https://ceqanet.lci.ca.gov/Project/2026102233",
                },
                {
                    "title": "Unmatched project",
                    "sch_number": "2026102244",
                    "requires_detail_enrichment": True,
                },
            ],
        },
        "detail_parses": [{
            "metadata": {
                "schema_version": "ceqanet_detail_page_parse.v1",
                "has_human_title": True,
            },
            "detail": {
                "sch_number": "2026102233",
                "title": "Verified only as original source title",
                "title_source": "human_label",
            },
        }],
    }


def test_retained_enrichment_matches_sch_without_claiming_site_verification() -> None:
    result = preview_original_ceqanet_enrichment(_payload())
    original = result["original_enrichment"]
    assert original["metadata"]["record_count"] == 2
    assert original["metadata"]["enriched_count"] == 1
    assert original["metadata"]["missing_detail_count"] == 1
    assert original["records"][0]["title"] == "Verified only as original source title"
    assert original["records"][0]["field_sources"]["title"] == "detail_page"
    assert original["records"][1]["enrichment_status"] == "missing_detail"
    assert result["network_executed"] is False
    assert result["source_database_mutated"] is False
    assert result["source_claim_only"] is True
    assert result["commercial_authority_granted"] is False


@pytest.mark.parametrize("mutation", [
    lambda value: value.update({"extra": 1}),
    lambda value: value["result_parse"]["metadata"].update({"schema_version": "fake"}),
    lambda value: value["result_parse"].update({"records": []}),
    lambda value: value["result_parse"].update({"records": [{}] * 51}),
    lambda value: value.update({"detail_parses": [{}]}),
    lambda value: value["detail_parses"].append(value["detail_parses"][0]),
    lambda value: value["detail_parses"][0]["detail"].update({"sch_number": ""}),
])
def test_malformed_or_ambiguous_evidence_fails_closed(mutation) -> None:
    data = _payload()
    mutation(data)
    with pytest.raises(ValueError):
        preview_original_ceqanet_enrichment(data)


def test_native_http_enrichment_preserves_local_only_authority(tmp_path: Path) -> None:
    server = make_server(snapshot(), 0, tmp_path / "private")
    worker = threading.Thread(target=server.serve_forever, daemon=True)
    worker.start()
    try:
        host = f"http://127.0.0.1:{server.server_port}"
        before = sorted(str(path.relative_to(tmp_path)) for path in tmp_path.rglob("*"))
        with httpx.Client(base_url=host, trust_env=False) as client:
            payload = _payload()
            assert client.post(
                "/api/source-ceqanet-offline-enrichment", json=payload,
            ).status_code == 403
            headers = {"Origin": host}
            for invalid_path in (
                "/api/source-ceqanet-offline-enrichment?execute=1",
                "/api/source-ceqanet-offline-enrichment#not-a-query",
            ):
                if "#" in invalid_path:
                    continue  # HTTP fragments are not sent to servers.
                assert client.post(
                    invalid_path, json=payload, headers=headers,
                ).status_code == 400
            assert client.post(
                "/api/source-ceqanet-offline-enrichment",
                json=payload, headers={"Origin": "https://foreign.invalid"},
            ).status_code == 403
            assert client.post(
                "/api/source-ceqanet-offline-enrichment",
                json=payload, headers={**headers, "Sec-Fetch-Site": "cross-site"},
            ).status_code == 400
            response = client.post(
                "/api/source-ceqanet-offline-enrichment", json=payload, headers=headers,
            )
            assert response.status_code == 200, response.text
            output = response.json()
            assert output["original_enrichment"]["metadata"]["enriched_count"] == 1
            assert output["network_executed"] is False
            assert output["investigation_queued"] is False
        after = sorted(str(path.relative_to(tmp_path)) for path in tmp_path.rglob("*"))
        assert before == after
    finally:
        server.shutdown()
        server.server_close()
        worker.join()
