"""Native CEQAnet result-to-detail review uses retained offline semantics only."""

from __future__ import annotations

import hashlib
import threading
from pathlib import Path

import httpx
import pytest
from sqlalchemy.orm import Session

from constructionsight.storage.database import create_database_engine, initialize_database
from constructionsight.storage.domain_store import CeqaStore
from tests.test_operator_dashboard import _record
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


def test_retained_sch_crosswalk_unique_missing_and_ambiguous_without_writes(
    tmp_path: Path,
) -> None:
    original = tmp_path / "original.sqlite3"
    engine = create_database_engine(f"sqlite:///{original}")
    initialize_database(engine)
    with Session(engine) as session, session.begin():
        CeqaStore(session).upsert(_record("ceqa:unique", state_clearinghouse_number="2026102233"))
        CeqaStore(session).upsert(_record("ceqa:duplicate:a", state_clearinghouse_number="2026102244"))
        CeqaStore(session).upsert(_record("ceqa:duplicate:b", state_clearinghouse_number="2026102244"))
    engine.dispose()
    before = hashlib.sha256(original.read_bytes()).hexdigest()
    payload = _payload()
    records = payload["result_parse"]["records"]
    records.extend([
        {"title": "Not found", "sch_number": "2026102255"},
        {"title": "No SCH supplied", "sch_number": None},
    ])
    report = preview_original_ceqanet_enrichment(payload, original)
    matches = report["retained_source_matches"]
    assert [item["status"] for item in matches] == [
        "unique_retained_sch", "ambiguous_retained_sch",
        "not_in_retained_source", "missing_sch",
    ]
    assert matches[0]["record_id"] == "ceqa:unique"
    assert matches[0]["retained_count"] == 1
    assert matches[1]["retained_count"] == 2
    assert all(item["record_id"] is None for item in matches[1:])
    assert all(item["status"] == "source_database_unavailable" for item in
               preview_original_ceqanet_enrichment(payload)["retained_source_matches"])
    assert report["network_executed"] is False
    assert report["investigation_queued"] is False
    assert hashlib.sha256(original.read_bytes()).hexdigest() == before


def test_enrichment_http_exact_source_links_only_existing_reviewed_evidence(
    tmp_path: Path,
) -> None:
    original = tmp_path / "retained.sqlite3"
    engine = create_database_engine(f"sqlite:///{original}")
    initialize_database(engine)
    with Session(engine) as session, session.begin():
        CeqaStore(session).upsert(_record("phase8:retained:exact",
                                         state_clearinghouse_number="2026102233"))
    engine.dispose()
    before = hashlib.sha256(original.read_bytes()).hexdigest()
    server = make_server(
        snapshot(), 0, tmp_path / "native", operator_database=original,
    )
    worker = threading.Thread(target=server.serve_forever, daemon=True)
    worker.start()
    try:
        base = f"http://127.0.0.1:{server.server_port}"
        with httpx.Client(base_url=base, trust_env=False) as client:
            response = client.post(
                "/api/source-ceqanet-offline-enrichment",
                json=_payload(), headers={"Origin": base},
            )
            assert response.status_code == 200, response.text
            exact = response.json()["retained_source_matches"][0]
            assert exact["record_id"] == "phase8:retained:exact"
            assert exact["status"] == "unique_retained_sch"
            current = client.get("/api/source-reconciliation", params={
                "kind": "ceqa", "record_id": exact["record_id"],
            })
            assert current.status_code == 200, current.text
            assert current.json()["original_source"]["record_id"] == exact["record_id"]
            assert current.json()["replay_eligible"] is True
            assert current.json()["no_commercial_authorization"] is True
            assert client.get("/api/investigations").json()["available"] is False
    finally:
        server.shutdown()
        server.server_close()
        worker.join()
    assert hashlib.sha256(original.read_bytes()).hexdigest() == before


def test_enrichment_refuses_unsafe_original_database_and_overlong_sch(
    tmp_path: Path,
) -> None:
    missing = tmp_path / "missing.sqlite3"
    link = tmp_path / "linked.sqlite3"
    link.symlink_to(missing)
    for database in (missing, link):
        with pytest.raises(ValueError):
            preview_original_ceqanet_enrichment(_payload(), database)
    bad = _payload()
    bad["result_parse"]["records"][0]["sch_number"] = "1" * 129
    with pytest.raises(ValueError):
        preview_original_ceqanet_enrichment(bad)
