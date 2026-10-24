"""Finite background scope, real bounded transport, durable handoff and barriers."""

import json
import shutil
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

import httpx
import pytest
from pydantic import ValidationError

import constructionsight.ceqanet_background as background
import constructionsight.http_transport as transport
from constructionsight.authorization_decision import AuthorizationDeniedError
from constructionsight.ceqanet_recurring_run_service import (
    build_ceqanet_recurring_run_definition,
    build_ceqanet_recurring_run_manifest,
)
from constructionsight.intelligence.investigation_query_service import InvestigationQueryService
from constructionsight.investigation_runtime import InvestigationRuntime
from constructionsight.storage.database import managed_session
from constructionsight.storage.intelligence_store import IntelligenceStore
from tests.test_ceqanet_recurring_run import _ready_checklist, _ready_sources, _template

NOW = datetime(2026, 10, 16, 12, tzinfo=UTC)
HTML = """<article><a href="/2026101234/1">Synthetic CEQA project</a>
<p>SCH Number: 2026101234</p><p>County: Riverside</p>
<p>Document Type: NOP</p><p>Lead Agency: Synthetic city</p></article>"""


@pytest.fixture
def setup(tmp_path, monkeypatch):
    monkeypatch.setattr(background, "_now", lambda: NOW)
    monkeypatch.setattr(
        "constructionsight.effect_consumption.trusted_utc_now", lambda: background._now()
    )
    monkeypatch.setattr(
        "constructionsight.local_operator_authorization._trusted_authorization_time",
        lambda: background._now(),
    )
    sources = _ready_sources()
    checklist = _ready_checklist()
    registry_path = tmp_path / "registry.json"
    registry_path.write_text(json.dumps([s.model_dump(mode="json") for s in sources]))
    checklist_path = tmp_path / "checklist.json"
    checklist_path.write_text(checklist.model_dump_json())
    definition = build_ceqanet_recurring_run_definition(
        sources,
        checklist,
        source_key="source:ceqanet-state-clearinghouse",
        query_template=_template().model_copy(update={"max_pages": 1}),
    )
    windows = []
    for i in range(2):
        day = date(2026, 10, 15) + timedelta(days=i)
        windows.append(
            background.BackgroundWindow(
                due_at=NOW + timedelta(days=i),
                manifest=build_ceqanet_recurring_run_manifest(
                    definition, window_start=day, window_end=day
                ),
            )
        )
    plan = background.CeqanetBackgroundPlan(
        definition=definition,
        registry_path=str(registry_path),
        checklist_path=str(checklist_path),
        expires_at=NOW + timedelta(days=3),
        windows=windows,
    )
    requests = []
    response = {
        "status": 200,
        "body": HTML,
        "headers": {"content-type": "text/html; charset=utf-8"},
    }

    def respond(request):
        requests.append(str(request.url))
        return httpx.Response(
            response["status"], text=response["body"], headers=response["headers"]
        )

    monkeypatch.setattr(
        transport,
        "_build_http_client",
        lambda: httpx.Client(
            transport=httpx.MockTransport(respond),
            follow_redirects=False,
            trust_env=False,
        ),
    )
    runtime = InvestigationRuntime(tmp_path / "private")
    try:
        yield runtime, plan, requests, response
    finally:
        runtime.close()


def enable(runtime, plan):
    return background.enable_plan(
        runtime.directory, plan, approved_digest=plan.digest, confirm=True
    )


def test_review_is_separate_and_never_executes_requests(setup):
    runtime, plan, requests, _ = setup
    assert runtime.process(poll_ceqa=True)["ceqa_acquired"] == 0
    with pytest.raises(ValueError, match="digest"):
        background.enable_plan(runtime.directory, plan, approved_digest="0" * 64, confirm=True)
    with pytest.raises(AuthorizationDeniedError):
        background.enable_plan(runtime.directory, plan, approved_digest=plan.digest, confirm=False)
    assert not requests
    enable(runtime, plan)
    assert not requests
    receipt = json.loads((runtime.directory / "ceqa-background/active.json").read_text())
    assert receipt["authorization"]["action"] == background.ACTION
    assert all(w.manifest.persistence_authorized is False for w in plan.windows)


def test_background_response_reaches_shared_engine_and_replay_is_idle(setup, monkeypatch):
    runtime, plan, requests, _ = setup
    enable(runtime, plan)
    result = runtime.process(poll_ceqa=True, max_jobs=20)
    assert result["ceqa_acquired"] == 1
    assert result["failed_jobs"] == result["ceqa_failed"] == 0
    assert len(requests) == 1
    with managed_session(runtime.queue.factory) as session:
        inventory = InvestigationQueryService(IntelligenceStore(session)).inventory()
        assert inventory["total"] == 1
        assert len(inventory["unmapped_on_page"]) == 1
        assert inventory["rows"][0]["assessment"]["identity_independently_verified"] is False
    assert runtime.process(poll_ceqa=True)["processed_jobs"] == 0
    assert len(requests) == 1
    monkeypatch.setattr(background, "_now", lambda: NOW + timedelta(days=1))
    assert runtime.process(poll_ceqa=True)["ceqa_acquired"] == 1
    assert len(requests) == 2
    assert runtime.process(poll_ceqa=True)["ceqa_acquired"] == 0
    assert len(requests) == 2
    assert "--poll-ceqa" in background_units(runtime)


def background_units(runtime):
    from constructionsight.investigation_runtime import systemd_units

    return systemd_units(runtime.directory / "python", runtime.directory)[
        "constructionsight-investigations.service"
    ]


@pytest.mark.parametrize("failure", ["403", "redirect", "captcha", "oversize", "timeout"])
def test_failed_request_stops_remaining_windows_without_retry(setup, monkeypatch, failure):
    runtime, plan, requests, response = setup
    if failure == "403":
        response["status"] = 403
    elif failure == "redirect":
        response["status"] = 302
        response["headers"]["location"] = "https://example.com/login"
    elif failure == "captcha":
        response["body"] = '<html><div class="g-recaptcha">captcha</div></html>'
    elif failure == "oversize":
        response["body"] = "x" * 50001
    else:

        def fail(request):
            requests.append(str(request.url))
            raise httpx.ReadTimeout("Synthetic timeout", request=request)

        monkeypatch.setattr(
            transport,
            "_build_http_client",
            lambda: httpx.Client(transport=httpx.MockTransport(fail)),
        )
    enable(runtime, plan)
    assert runtime.process(poll_ceqa=True)["ceqa_failed"] == 1
    monkeypatch.setattr(background, "_now", lambda: NOW + timedelta(days=1))
    assert runtime.process(poll_ceqa=True)["ceqa_failed"] == 1
    assert len(requests) == 1
    assert not runtime.queue.list_jobs()
    assert list((runtime.directory / "ceqa-background").glob("result-*.json"))


@pytest.mark.parametrize("barrier", ["revoke", "expired", "stale-review", "copied-directory"])
def test_review_boundaries_prevent_network(setup, monkeypatch, tmp_path, barrier):
    runtime, plan, requests, _ = setup
    enable(runtime, plan)
    other = None
    if barrier == "revoke":
        background.revoke_plan(runtime.directory)
        with pytest.raises(ValueError, match="revoked"):
            enable(runtime, plan)
    elif barrier == "expired":
        monkeypatch.setattr(background, "_now", lambda: NOW + timedelta(days=4))
    elif barrier == "stale-review":
        payload = json.loads(Path(plan.registry_path).read_text())
        payload[0]["provenance_notes"] = "changed after approval"
        Path(plan.registry_path).write_text(json.dumps(payload))
    else:
        copied = tmp_path / "copied"
        shutil.copytree(runtime.directory, copied)
        other = InvestigationRuntime(copied)
    try:
        report = (other or runtime).process(poll_ceqa=True)
        assert report["ceqa_acquired"] == 0
        assert report["ceqa_failed"] == int(barrier in {"stale-review", "copied-directory"})
        assert not requests
    finally:
        if other:
            other.close()


def test_crash_after_reservation_never_repeats_network(setup, monkeypatch):
    runtime, plan, requests, _ = setup
    enable(runtime, plan)

    def crash(*args, **kwargs):
        raise KeyboardInterrupt("Synthetic process exit after reservation")

    monkeypatch.setattr(background, "execute_ceqanet_recurring_run", crash)
    with pytest.raises(KeyboardInterrupt):
        runtime.process(poll_ceqa=True)
    assert runtime.process(poll_ceqa=True)["ceqa_failed"] == 1
    assert not requests
    marker = json.loads(
        next((runtime.directory / "ceqa-background").glob("stopped-*.json")).read_text()
    )
    assert marker["error_code"] == "ambiguous_attempt_requires_review"


def test_crash_after_retention_recovers_handoff_after_revocation(setup, monkeypatch):
    runtime, plan, requests, _ = setup
    enable(runtime, plan)
    original = runtime.enqueue_bytes

    def crash(*args, **kwargs):
        raise KeyboardInterrupt("Synthetic process exit before enqueue")

    monkeypatch.setattr(runtime, "enqueue_bytes", crash)
    with pytest.raises(KeyboardInterrupt):
        runtime.process(poll_ceqa=True)
    assert len(requests) == 1
    background.revoke_plan(runtime.directory)
    monkeypatch.setattr(runtime, "enqueue_bytes", original)
    assert runtime.process(poll_ceqa=True)["processed_jobs"] > 0
    assert len(requests) == 1
    assert runtime.process(poll_ceqa=True)["processed_jobs"] == 0


def test_missed_windows_do_not_burst_catch_up_requests(setup, monkeypatch):
    runtime, plan, requests, _ = setup
    enable(runtime, plan)
    monkeypatch.setattr(background, "_now", lambda: NOW + timedelta(days=1, hours=1))
    assert runtime.process(poll_ceqa=True)["ceqa_acquired"] == 1
    assert len(requests) == 1
    missed = (
        runtime.directory
        / "ceqa-background"
        / f"attempt-{plan.windows[0].manifest.manifest_digest}.json"
    )
    assert json.loads(missed.read_text())["status"] == "missed"


def test_finite_plan_rejects_burst_and_expansion(setup):
    _, plan, _, _ = setup
    payload = plan.model_dump(mode="json", round_trip=True)
    payload["windows"][1]["due_at"] = NOW.isoformat()
    with pytest.raises(ValidationError, match="one day"):
        background.CeqanetBackgroundPlan.model_validate(payload)
    payload = plan.model_dump(mode="json", round_trip=True)
    payload["expires_at"] = (NOW + timedelta(days=32)).isoformat()
    with pytest.raises(ValidationError, match="31 days"):
        background.CeqanetBackgroundPlan.model_validate(payload)


def test_restoring_old_data_does_not_repeat_consumed_request(setup, tmp_path):
    runtime, plan, requests, _ = setup
    enable(runtime, plan)
    root = runtime.directory / "ceqa-background"
    snapshot = tmp_path / "snapshot"
    shutil.copytree(root, snapshot)
    assert runtime.process(poll_ceqa=True)["ceqa_acquired"] == 1
    shutil.rmtree(root)
    shutil.copytree(snapshot, root)
    # Exact global effect replay recovers the original result, without transport.
    assert runtime.process(poll_ceqa=True)["ceqa_failed"] == 0
    assert len(requests) == 1
    assert runtime.process(poll_ceqa=True)["processed_jobs"] == 0


@pytest.mark.parametrize("barrier", ["revoke", "access-stop"])
def test_restoring_old_data_cannot_undo_revocation_or_access_stop(setup, tmp_path, barrier):
    runtime, plan, requests, response = setup
    enable(runtime, plan)
    root = runtime.directory / "ceqa-background"
    snapshot = tmp_path / "snapshot"
    shutil.copytree(root, snapshot)
    if barrier == "revoke":
        background.revoke_plan(runtime.directory)
    else:
        response["status"] = 403
        assert runtime.process(poll_ceqa=True)["ceqa_failed"] == 1
    before = len(requests)
    shutil.rmtree(root)
    shutil.copytree(snapshot, root)
    assert runtime.process(poll_ceqa=True)["ceqa_acquired"] == 0
    assert len(requests) == before


def test_cli_build_and_preview_show_exact_scope_without_network(setup, tmp_path, capsys):
    runtime, plan, requests, _ = setup
    definition = tmp_path / "definition.json"
    definition.write_text(plan.definition.model_dump_json(round_trip=True))
    assert (
        background.main(
            [
                "--data-dir",
                str(runtime.directory),
                "build",
                "--definition",
                str(definition),
                "--registry",
                plan.registry_path,
                "--checklist",
                plan.checklist_path,
                "--first-due",
                NOW.isoformat(),
                "--days",
                "2",
            ]
        )
        == 0
    )
    built = background.CeqanetBackgroundPlan.model_validate_json(capsys.readouterr().out)
    path = tmp_path / "plan.json"
    path.write_text(built.model_dump_json(round_trip=True))
    assert (
        background.main(
            [
                "--data-dir",
                str(runtime.directory),
                "preview",
                "--plan",
                str(path),
            ]
        )
        == 0
    )
    preview = json.loads(capsys.readouterr().out)
    assert preview["plan_digest"] == built.digest
    assert preview["request_limit"] == 2
    assert not (runtime.directory / "ceqa-background").exists()
    assert not requests


def test_concurrent_workers_consume_one_window(setup):
    from concurrent.futures import ThreadPoolExecutor

    runtime, plan, requests, _ = setup
    enable(runtime, plan)
    other = InvestigationRuntime(runtime.directory)
    try:
        with ThreadPoolExecutor(max_workers=2) as executor:
            results = list(executor.map(background.poll_background, (runtime, other)))
        assert sum(result["ceqa_acquired"] for result in results) == 1
        assert len(requests) == 1
    finally:
        other.close()


def test_listing_documents_keep_distinct_source_records_and_missing_county(setup):
    runtime, plan, requests, response = setup
    response["body"] = HTML + HTML.replace("/2026101234/1", "/2026101234/2").replace(
        "NOP", "EIR"
    ).replace("<p>County: Riverside</p>", "")
    enable(runtime, plan)
    assert runtime.process(poll_ceqa=True)["failed_jobs"] == 0
    assert len(requests) == 1
    with managed_session(runtime.queue.factory) as session:
        inventory = InvestigationQueryService(IntelligenceStore(session)).inventory()
        assert inventory["total"] == 2
        assert len(inventory["unmapped_on_page"]) == 2


def test_malformed_background_config_cannot_block_retained_processing(setup):
    from tests.test_investigation_acquisition import permit

    runtime, _, requests, _ = setup
    root = runtime.directory / "ceqa-background"
    root.mkdir(mode=0o700)
    (root / "active.json").write_text('{"authorization": null}')
    runtime.enqueue_bytes(permit("independent").encode(), "permit")
    result = runtime.process(poll_ceqa=True)
    assert result["ceqa_failed"] == 1
    assert result["processed_jobs"] > 0
    assert not requests


def test_crash_before_access_failure_classification_still_stops_next_window(setup, monkeypatch):
    runtime, plan, requests, response = setup
    response["status"] = 403
    enable(runtime, plan)
    original = background.BackgroundListingEvidence.response_failed

    def crash(self):
        raise KeyboardInterrupt("Synthetic crash after retaining the denied response")

    monkeypatch.setattr(background.BackgroundListingEvidence, "response_failed", crash)
    with pytest.raises(KeyboardInterrupt):
        runtime.process(poll_ceqa=True)
    monkeypatch.setattr(background.BackgroundListingEvidence, "response_failed", original)
    monkeypatch.setattr(background, "_now", lambda: NOW + timedelta(days=1))
    assert runtime.process(poll_ceqa=True)["ceqa_failed"] == 1
    assert len(requests) == 1


def test_actual_request_spacing_remains_daily_after_delayed_collection(
    setup, monkeypatch, tmp_path
):
    runtime, plan, requests, _ = setup
    enable(runtime, plan)
    root = runtime.directory / "ceqa-background"
    snapshot = tmp_path / "before-delay"
    shutil.copytree(root, snapshot)
    monkeypatch.setattr(background, "_now", lambda: NOW + timedelta(hours=23))
    assert runtime.process(poll_ceqa=True)["ceqa_acquired"] == 1
    shutil.rmtree(root)
    shutil.copytree(snapshot, root)
    monkeypatch.setattr(background, "_now", lambda: NOW + timedelta(days=1))
    assert runtime.process(poll_ceqa=True)["ceqa_acquired"] == 0
    assert len(requests) == 1
    monkeypatch.setattr(background, "_now", lambda: NOW + timedelta(days=1, hours=23))
    assert runtime.process(poll_ceqa=True)["ceqa_acquired"] == 1
    assert len(requests) == 2


def test_ceqa_access_stop_stays_visible_after_retained_only_worker_turn(setup):
    from constructionsight.collection_schedule import warning

    runtime, plan, _, response = setup
    response["status"] = 403
    enable(runtime, plan)
    assert runtime.process(poll_ceqa=True)["ceqa_failed"] == 1
    runtime.process()
    assert "CEQA background acquisition stopped" in warning(runtime.directory)
