"""Native manual original-source verification checklist retains exact original evidence."""

from __future__ import annotations

import hashlib
import threading
from copy import deepcopy
from pathlib import Path

import httpx
from sqlalchemy.orm import Session

from constructionsight.adapters import default_adapter_family_specs
from constructionsight.live_command_center import make_server
from constructionsight.source_promotion_plan_service import build_source_promotion_plan
from constructionsight.source_registry_update_plan_service import build_source_registry_update_plan
from constructionsight.source_verification_checklist_models import SourceVerificationObservation
from constructionsight.source_verification_checklist_service import (
    build_source_verification_checklist_report,
)
from constructionsight.storage.database import create_database_engine, initialize_database
from constructionsight.storage.source_registry import SourceRegistryStore
from tests.test_command_center_investigation_bridge import snapshot
from tests.test_operator_source_registry import _source


def _strip_build_times(payload: dict) -> dict:
    normalized = deepcopy(payload)
    assert normalized.pop("generated_at")
    for row in normalized["rows"]:
        assert row.pop("generated_at")
    return normalized


def test_native_review_reuses_original_checklist_without_source_mutation(
    tmp_path: Path,
) -> None:
    original = tmp_path / "original.sqlite3"
    engine = create_database_engine(f"sqlite:///{original}")
    initialize_database(engine)
    source = _source("Synthetic original manual checklist source", county="Riverside")
    with Session(engine) as session, session.begin():
        SourceRegistryStore(session).upsert_source(source)
    engine.dispose()
    before = hashlib.sha256(original.read_bytes()).hexdigest()
    private = tmp_path / "private"
    server = make_server(snapshot(), 0, private, operator_database=original)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        host = f"http://127.0.0.1:{server.server_port}"
        params = {"source_name": source.source_name, "public_url": str(source.public_url)}
        with httpx.Client(base_url=host, trust_env=False) as client:
            preview_response = client.get("/api/source-checklist-preview", params=params)
            assert preview_response.status_code == 200, preview_response.text
            preview = preview_response.json()
            assert preview["source_promoted"] is False
            assert preview["network_executed"] is False
            assert preview["original_observation_template"]["detail_page_observed"] is None
            assert client.get("/api/source-checklist-preview", params={
                **params, "check_http": "true",
            }).status_code == 409
            observation = {
                "source_key": preview["source_key"],
                "source_name": source.source_name,
                "public_entry_observed": None,
                "query_behavior_observed": None,
                "result_list_observed": None,
                "detail_page_observed": True,
                "access_barrier_observed": None,
                "terms_review_observed": None,
                "notes": "Manual fixture observation, not independent verification.",
                "evidence_refs": ["manual:original-source:test-evidence"],
            }
            payload = {
                **params,
                "expected_source_sha256": preview["expected_source_sha256"],
                "review_reason": "Review one exact retained original source by hand.",
                "caller_confirmation": True,
                "observation": observation,
            }
            assert client.post("/api/source-checklist-review", json=payload).status_code == 403
            assert client.post("/api/source-checklist-review", json=payload, headers={
                "Origin": "https://untrusted.invalid",
            }).status_code == 403
            for bad in (
                {**payload, "caller_confirmation": False},
                {**payload, "expected_source_sha256": "f" * 64},
                {**payload, "observation": {**observation, "source_key": "substituted"}},
                {**payload, "observation": {**observation, "evidence_refs": []}},
                {**payload, "observation": {**observation, "detail_page_observed": "yes"}},
                {**payload, "observation": {**observation, "extra": True}},
                {**payload, "extra": "verify"},
            ):
                denied = client.post("/api/source-checklist-review", json=bad, headers={
                    "Origin": host,
                })
                assert denied.status_code == 400, denied.text
            accepted = client.post("/api/source-checklist-review", json=payload, headers={
                "Origin": host,
            })
            assert accepted.status_code == 200, accepted.text
            result = accepted.json()
            assert result["original_registry_mutated"] is False
            assert result["network_executed"] is False
            assert result["source_promoted"] is False
            assert result["commercial_authority_granted"] is False
            assert result["operator_observations_not_independent_verification"] is True
            assert result["original_manual_checklist"]["source_count"] == 1
            assert result["original_manual_checklist"]["rows"][0][
                "checklist_status"
            ] == "detail_behavior_observed"
            expected = build_source_verification_checklist_report(
                [source], default_adapter_family_specs(), check_http=False,
                observations=[SourceVerificationObservation.model_validate(observation)],
            ).to_dict()
            assert _strip_build_times(result["original_manual_checklist"]) == (
                _strip_build_times(expected)
            )
            parsed = SourceVerificationObservation.model_validate(observation)
            adapters = default_adapter_family_specs()
            assert _strip_build_times(result["original_promotion_plan"]) == (
                _strip_build_times(build_source_promotion_plan(
                    [source], adapters, check_http=False, observations=[parsed],
                ).to_dict())
            )
            assert _strip_build_times(result["original_registry_update_plan"]) == (
                _strip_build_times(build_source_registry_update_plan(
                    [source], adapters, check_http=False, observations=[parsed],
                ).to_dict())
            )
            assert result["original_promotion_plan"]["rows"][0][
                "planned_action"
            ] == "mark_partial_candidate"
            assert result["original_registry_update_plan"]["rows"][0][
                "evidence_refs"
            ] == observation["evidence_refs"]
            assert hashlib.sha256(original.read_bytes()).hexdigest() == before
            assert not (private / "investigations.sqlite3").exists()
    finally:
        server.shutdown()
        server.server_close()
        thread.join()
