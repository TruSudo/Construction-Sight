"""Apply the locally validated PR92 hardening patch with exact anchors."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def replace_once(path: Path, old: str, new: str) -> None:
    text = path.read_text(encoding="utf-8")
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"expected one anchor in {path}, found {count}")
    path.write_text(text.replace(old, new, 1), encoding="utf-8")


def patch_service() -> None:
    path = ROOT / "src/constructionsight/ceqanet_recurring_run_service.py"
    replace_once(
        path,
        "from constructionsight.adapters.ceqanet_listing_executor import (\n",
        "from constructionsight.adapters.ceqanet_listing_dry_run import "
        "CeqanetListingDryRunExecutor\n"
        "from constructionsight.adapters.ceqanet_listing_executor import (\n",
    )
    replace_once(
        path,
        "    blockers = _definition_blockers(source, source_row, assumptions)\n",
        "    blockers = _definition_blockers(\n"
        "        source,\n"
        "        source_row,\n"
        "        assumptions,\n"
        "        execution_base_url=normalized_execution_url,\n"
        "    )\n",
    )
    replace_once(
        path,
        "        (\n"
        "            \"attempt sequence uniqueness is operator-controlled until a persisted \"\n"
        "            \"attempt ledger exists\"\n"
        "        ),\n",
        "        (\n"
        "            \"attempt sequence uniqueness is operator-controlled until a persisted \"\n"
        "            \"attempt ledger exists\"\n"
        "        ),\n"
        "        (\n"
        "            \"evidence references are bound as identifiers; referenced file content \"\n"
        "            \"requires separate archive verification\"\n"
        "        ),\n",
    )
    replace_once(
        path,
        "        \"checklist_evidence_digest\": _checklist_row_digest(source_row),\n"
        "        \"registry_verification_status\": source.verification_status.value,\n",
        "        \"checklist_evidence_digest\": _checklist_row_digest(source_row),\n"
        "        \"checklist_generated_at\": source_row.generated_at,\n"
        "        \"checklist_final_url\": source_row.final_url,\n"
        "        \"checklist_http_status_code\": source_row.http_status_code,\n"
        "        \"checklist_redirect_classification\": "
        "source_row.redirect_classification,\n"
        "        \"registry_verification_status\": source.verification_status.value,\n",
    )
    replace_once(
        path,
        "        (\n"
        "            row.checklist_status.value,\n"
        "            definition.checklist_status,\n"
        "            \"current checklist status does not match definition\",\n"
        "        ),\n",
        "        (\n"
        "            row.checklist_status.value,\n"
        "            definition.checklist_status,\n"
        "            \"current checklist status does not match definition\",\n"
        "        ),\n"
        "        (\n"
        "            row.generated_at,\n"
        "            definition.checklist_generated_at,\n"
        "            \"current checklist generation time does not match definition\",\n"
        "        ),\n"
        "        (\n"
        "            row.final_url,\n"
        "            definition.checklist_final_url,\n"
        "            \"current checklist final URL does not match definition\",\n"
        "        ),\n"
        "        (\n"
        "            row.http_status_code,\n"
        "            definition.checklist_http_status_code,\n"
        "            \"current checklist HTTP status does not match definition\",\n"
        "        ),\n"
        "        (\n"
        "            row.redirect_classification,\n"
        "            definition.checklist_redirect_classification,\n"
        "            \"current checklist redirect classification does not match definition\",\n"
        "        ),\n",
    )
    replace_once(
        path,
        "    blockers = _definition_blockers(source, row, definition.access_assumptions)\n",
        "    blockers = _definition_blockers(\n"
        "        source,\n"
        "        row,\n"
        "        definition.access_assumptions,\n"
        "        execution_base_url=definition.execution_base_url,\n"
        "    )\n",
    )
    replace_once(
        path,
        "    return CeqanetRecurringRunExecution(\n"
        "        run_id=manifest.run_id,\n",
        "    return CeqanetRecurringRunExecution.build(\n"
        "        run_id=manifest.run_id,\n",
    )
    replace_once(
        path,
        "        network_executed=report.executed_request_count > 0,\n"
        "        persistence_mutated=False,\n"
        "    )\n",
        "        network_executed=report.executed_request_count > 0,\n"
        "    )\n",
    )
    replace_once(
        path,
        "def _definition_blockers(\n"
        "    source: PublicSource,\n"
        "    row: SourceVerificationChecklistRow,\n"
        "    assumptions: CeqanetAccessAssumptions,\n"
        ") -> list[str]:\n",
        "def _definition_blockers(\n"
        "    source: PublicSource,\n"
        "    row: SourceVerificationChecklistRow,\n"
        "    assumptions: CeqanetAccessAssumptions,\n"
        "    *,\n"
        "    execution_base_url: str,\n"
        ") -> list[str]:\n",
    )
    replace_once(
        path,
        "    if source.verification_status is not VerificationStatus.VERIFIED:\n"
        "        blockers.append(\"source registry status is not verified\")\n"
        "    required_items = {\n",
        "    if source.verification_status is not VerificationStatus.VERIFIED:\n"
        "        blockers.append(\"source registry status is not verified\")\n"
        "    if row.registry_status != source.verification_status.value:\n"
        "        blockers.append(\"checklist registry status does not match source registry\")\n"
        "    if row.http_status_code is None or not 200 <= row.http_status_code < 400:\n"
        "        blockers.append(\n"
        "            \"checklist HTTP evidence is not a successful public response\"\n"
        "        )\n"
        "    if row.final_url is None:\n"
        "        blockers.append(\"checklist final URL evidence is missing\")\n"
        "    else:\n"
        "        final_url = urlparse(row.final_url)\n"
        "        execution_url = urlparse(execution_base_url)\n"
        "        if (\n"
        "            final_url.scheme != \"https\"\n"
        "            or final_url.netloc.lower() != execution_url.netloc.lower()\n"
        "        ):\n"
        "            blockers.append(\n"
        "                \"checklist final URL does not match the approved execution host\"\n"
        "            )\n"
        "    required_items = {\n",
    )
    replace_once(
        path,
        "def _checklist_row_digest(row: SourceVerificationChecklistRow) -> str:\n"
        "    return canonical_digest(row.model_dump(mode=\"json\", exclude={\"generated_at\"}))\n",
        "def _checklist_row_digest(row: SourceVerificationChecklistRow) -> str:\n"
        "    return canonical_digest(row.model_dump(mode=\"json\"))\n",
    )

    text = path.read_text(encoding="utf-8")
    marker = "def _verify_execution_report("
    if text.count(marker) != 1:
        raise RuntimeError("execution verifier tail anchor mismatch")
    head = text.split(marker, 1)[0]
    tail = '''def _verify_execution_report(
    manifest: CeqanetRecurringRunManifest,
    report: dict[str, Any],
    findings: list[str],
) -> int | None:
    _verify_exact_keys(
        report,
        {"metadata", "snapshots"},
        "execution report",
        findings,
    )
    metadata = report.get("metadata")
    snapshots = report.get("snapshots")
    if not isinstance(metadata, dict):
        findings.append("execution report metadata is missing")
        return None
    if not isinstance(snapshots, list):
        findings.append("execution report snapshots are missing")
        return None

    _verify_exact_keys(
        metadata,
        {
            "schema_version",
            "allowed",
            "reason",
            "planned_request_count",
            "executed_request_count",
            "successful_response_count",
            "failed_response_count",
            "maximum_records",
            "query",
        },
        "execution report metadata",
        findings,
    )
    _compare(
        findings,
        metadata.get("schema_version"),
        "ceqanet_listing_execution.v1",
        "execution report schema_version mismatch",
    )
    if metadata.get("allowed") is not True:
        findings.append("execution report allowed flag is not true")
    reason = metadata.get("reason")
    if not isinstance(reason, str) or not reason.strip():
        findings.append("execution report reason is missing")
    _compare(
        findings,
        metadata.get("query"),
        manifest.query,
        "execution report query does not match manifest",
    )
    maximum_records = _int_value(manifest.query, "page_size") * _int_value(
        manifest.query,
        "max_pages",
    )
    _compare(
        findings,
        metadata.get("maximum_records"),
        maximum_records,
        "execution report maximum_records does not match manifest",
    )

    planned = _report_int(metadata, "planned_request_count", findings)
    executed = _report_int(metadata, "executed_request_count", findings)
    successful = _report_int(metadata, "successful_response_count", findings)
    failed = _report_int(metadata, "failed_response_count", findings)
    max_pages = _int_value(manifest.query, "max_pages")
    if planned is not None and planned != max_pages:
        findings.append("planned_request_count does not equal manifest max_pages")
    if executed is not None and planned is not None and executed != planned:
        findings.append("executed_request_count does not equal planned request count")
    if executed is not None and executed != len(snapshots):
        findings.append("executed_request_count does not match snapshots")
    if None not in {executed, successful, failed}:
        assert executed is not None
        assert successful is not None
        assert failed is not None
        if successful + failed != executed:
            findings.append("successful and failed response counts do not equal executed count")

    expected_urls = _expected_request_urls(manifest, findings)
    expected_host = urlparse(manifest.execution_base_url).netloc.lower()
    page_numbers: set[int] = set()
    page_order: list[int] = []
    for index, snapshot in enumerate(snapshots):
        _verify_snapshot(
            snapshot,
            index=index,
            expected_host=expected_host,
            max_pages=max_pages,
            max_body_chars=manifest.max_body_chars,
            expected_urls=expected_urls,
            page_numbers=page_numbers,
            page_order=page_order,
            findings=findings,
        )
    expected_pages = set(range(1, max_pages + 1))
    if page_numbers != expected_pages:
        findings.append("snapshot page numbers do not cover the complete manifest range")
    if page_order != list(range(1, max_pages + 1)):
        findings.append("snapshot page order does not match the manifest range")
    return executed


def _expected_request_urls(
    manifest: CeqanetRecurringRunManifest,
    findings: list[str],
) -> dict[int, str]:
    access_result = evaluate_access(
        SourceAccessProfile(
            public_url=manifest.execution_base_url,
            requires_login=manifest.access_assumptions.requires_login,
            has_captcha=manifest.access_assumptions.has_captcha,
            robots_disallows_collection=(
                manifest.access_assumptions.robots_disallows_collection
            ),
            terms_disallow_collection=(
                manifest.access_assumptions.terms_disallow_collection
            ),
            paywalled=manifest.access_assumptions.paywalled,
        )
    )
    query = _listing_query_from_payload(manifest.query)
    search_url = f"{manifest.execution_base_url.rstrip('/')}/Search"
    plan = CeqanetReadOnlyListingPlanner(search_url=search_url).build_plan(query, access_result)
    if not plan.allowed:
        findings.append("manifest access assumptions do not produce an allowed request plan")
        return {}
    dry_run = CeqanetListingDryRunExecutor().run(plan)
    return {request.page_number: request.url for request in dry_run.requests}


def _verify_exact_keys(
    payload: dict[str, Any],
    expected_keys: set[str],
    label: str,
    findings: list[str],
) -> None:
    actual_keys = set(payload)
    missing = sorted(expected_keys - actual_keys)
    extra = sorted(actual_keys - expected_keys)
    if missing:
        findings.append(f"{label} is missing fields: {', '.join(missing)}")
    if extra:
        findings.append(f"{label} contains unknown fields: {', '.join(extra)}")


def _report_int(
    metadata: dict[str, Any],
    field_name: str,
    findings: list[str],
) -> int | None:
    value = metadata.get(field_name)
    if isinstance(value, bool) or not isinstance(value, int):
        findings.append(f"{field_name} is not an integer")
        return None
    if value < 0:
        findings.append(f"{field_name} cannot be negative")
    return value


def _verify_snapshot(
    snapshot: object,
    *,
    index: int,
    expected_host: str,
    max_pages: int,
    max_body_chars: int,
    expected_urls: dict[int, str],
    page_numbers: set[int],
    page_order: list[int],
    findings: list[str],
) -> None:
    if not isinstance(snapshot, dict):
        findings.append(f"snapshots[{index}] is not an object")
        return
    _verify_exact_keys(
        snapshot,
        {
            "page_number",
            "method",
            "request_url",
            "final_url",
            "status_code",
            "content_type",
            "body_text",
            "body_length",
            "body_truncated",
            "executed",
            "error",
            "reachable",
        },
        f"snapshots[{index}]",
        findings,
    )

    page_number = snapshot.get("page_number")
    valid_page_number: int | None = None
    if isinstance(page_number, bool) or not isinstance(page_number, int):
        findings.append(f"snapshots[{index}] page_number is not an integer")
    elif not 1 <= page_number <= max_pages:
        findings.append(f"snapshots[{index}] page_number exceeds manifest bounds")
    elif page_number in page_numbers:
        findings.append(f"snapshots[{index}] page_number is duplicated")
    else:
        valid_page_number = page_number
        page_numbers.add(page_number)
        page_order.append(page_number)

    if snapshot.get("method") != "GET":
        findings.append(f"snapshots[{index}] method is not GET")
    if snapshot.get("executed") is not True:
        findings.append(f"snapshots[{index}] executed flag is not true")

    request_url = snapshot.get("request_url")
    if not isinstance(request_url, str):
        findings.append(f"snapshots[{index}] request_url is missing")
    else:
        _verify_snapshot_url(
            request_url,
            index=index,
            label="request_url",
            expected_host=expected_host,
            findings=findings,
        )
        if valid_page_number is not None:
            expected_url = expected_urls.get(valid_page_number)
            if expected_url is None:
                findings.append(f"snapshots[{index}] has no expected request URL")
            elif request_url != expected_url:
                findings.append(f"snapshots[{index}] request_url does not match manifest query")

    final_url = snapshot.get("final_url")
    if not isinstance(final_url, str):
        findings.append(f"snapshots[{index}] final_url is missing")
    else:
        _verify_snapshot_url(
            final_url,
            index=index,
            label="final_url",
            expected_host=expected_host,
            findings=findings,
        )

    status_code = snapshot.get("status_code")
    error = snapshot.get("error")
    reachable = snapshot.get("reachable")
    if not isinstance(reachable, bool):
        findings.append(f"snapshots[{index}] reachable is not a boolean")
    if status_code is None:
        if not isinstance(error, str) or not error.strip():
            findings.append(f"snapshots[{index}] missing-status response has no error")
        if reachable is not False:
            findings.append(f"snapshots[{index}] missing-status response is marked reachable")
    elif isinstance(status_code, bool) or not isinstance(status_code, int):
        findings.append(f"snapshots[{index}] status_code is not an integer or null")
    else:
        if not 100 <= status_code <= 599:
            findings.append(f"snapshots[{index}] status_code is outside HTTP bounds")
        expected_reachable = 200 <= status_code < 400
        if reachable != expected_reachable:
            findings.append(f"snapshots[{index}] reachable does not match status_code")
        if error is not None:
            findings.append(f"snapshots[{index}] HTTP response unexpectedly contains an error")

    content_type = snapshot.get("content_type")
    if content_type is not None and not isinstance(content_type, str):
        findings.append(f"snapshots[{index}] content_type is not a string or null")

    body_text = snapshot.get("body_text")
    body_length = snapshot.get("body_length")
    body_truncated = snapshot.get("body_truncated")
    if not isinstance(body_text, str):
        findings.append(f"snapshots[{index}] body_text is not a string")
    elif len(body_text) > max_body_chars:
        findings.append(f"snapshots[{index}] retained body exceeds manifest limit")
    if isinstance(body_length, bool) or not isinstance(body_length, int):
        findings.append(f"snapshots[{index}] body_length is not an integer")
    elif body_length < 0:
        findings.append(f"snapshots[{index}] body_length cannot be negative")
    elif isinstance(body_text, str) and body_length < len(body_text):
        findings.append(f"snapshots[{index}] body_length is smaller than retained body")
    if not isinstance(body_truncated, bool):
        findings.append(f"snapshots[{index}] body_truncated is not a boolean")
    elif (
        isinstance(body_length, int)
        and not isinstance(body_length, bool)
        and body_truncated != (body_length > max_body_chars)
    ):
        findings.append(f"snapshots[{index}] body_truncated is inconsistent")


def _verify_snapshot_url(
    url: str,
    *,
    index: int,
    label: str,
    expected_host: str,
    findings: list[str],
) -> None:
    parsed = urlparse(url)
    if parsed.scheme != "https" or parsed.netloc.lower() != expected_host:
        findings.append(f"snapshots[{index}] {label} host is outside manifest")
    if parsed.path != "/Search":
        findings.append(f"snapshots[{index}] {label} path is not /Search")
'''
    path.write_text(head + tail, encoding="utf-8")


def patch_verifier() -> None:
    path = ROOT / "src/constructionsight/ceqanet_recurring_run_verifier.py"
    replace_once(
        path,
        "    semantic_verification = _verify_semantics(\n"
        "        definition,\n"
        "        manifest,\n"
        "        execution,\n"
        "        sources,\n"
        "        checklist_report,\n"
        "    )\n"
        "    findings = list(semantic_verification.findings)\n"
        "    try:\n"
        "        execution.assert_integrity()\n"
        "    except ValueError as exc:\n"
        "        findings.insert(0, str(exc))\n",
        "    findings: list[str] = []\n"
        "    try:\n"
        "        execution.assert_integrity()\n"
        "    except ValueError as exc:\n"
        "        findings.append(str(exc))\n"
        "    semantic_verification = _verify_semantics(\n"
        "        definition,\n"
        "        manifest,\n"
        "        execution,\n"
        "        sources,\n"
        "        checklist_report,\n"
        "    )\n"
        "    findings.extend(semantic_verification.findings)\n",
    )


def patch_tests() -> None:
    recurring = ROOT / "tests/test_ceqanet_recurring_run.py"
    replace_once(
        recurring,
        "from pydantic import HttpUrl\n",
        "from pydantic import HttpUrl, ValidationError\n",
    )
    replace_once(
        recurring,
        "    CeqanetWindowField,\n",
        "    CeqanetWindowField,\n    canonical_digest,\n",
    )
    replace_once(
        recurring,
        "    return PublicSource(\n        jurisdiction=Jurisdiction(",
        "    return PublicSource(\n"
        "        source_id=\"source-ceqanet-test\",\n"
        "        jurisdiction=Jurisdiction(",
    )
    replace_once(
        recurring,
        "    execution = CeqanetRecurringRunExecution(\n"
        "        run_id=tampered.run_id,\n"
        "        attempt_sequence=1,\n"
        "        attempt_id=\"0\" * 64,\n"
        "        definition_digest=definition.definition_digest,\n"
        "        manifest_digest=tampered.manifest_digest,\n"
        "        source_key=definition.source_key,\n"
        "        execution_report={},\n"
        "        network_executed=False,\n"
        "    )\n",
        "    execution = CeqanetRecurringRunExecution.build(\n"
        "        run_id=tampered.run_id,\n"
        "        attempt_sequence=1,\n"
        "        attempt_id=\"0\" * 64,\n"
        "        definition_digest=definition.definition_digest,\n"
        "        manifest_digest=tampered.manifest_digest,\n"
        "        source_key=definition.source_key,\n"
        "        execution_report={},\n"
        "        network_executed=False,\n"
        "    )\n",
    )
    insertion = '''

def test_execution_artifact_requires_stored_digest() -> None:
    definition = _ready_definition()
    manifest = build_ceqanet_recurring_run_manifest(
        definition,
        window_start=date(2026, 7, 1),
        window_end=date(2026, 7, 7),
    )
    execution = execute_ceqanet_recurring_run(
        definition,
        manifest,
        _ready_sources(),
        _ready_checklist(),
        attempt_sequence=1,
        execute_live=True,
        client=_FakeClient(),
    )
    payload = execution.model_dump(mode="json")
    del payload["execution_digest"]

    with pytest.raises(ValidationError, match="execution_digest"):
        CeqanetRecurringRunExecution.model_validate(payload)


def test_execution_artifact_rejects_unknown_top_level_fields() -> None:
    definition = _ready_definition()
    manifest = build_ceqanet_recurring_run_manifest(
        definition,
        window_start=date(2026, 7, 1),
        window_end=date(2026, 7, 7),
    )
    execution = execute_ceqanet_recurring_run(
        definition,
        manifest,
        _ready_sources(),
        _ready_checklist(),
        attempt_sequence=1,
        execute_live=True,
        client=_FakeClient(),
    )
    payload = execution.model_dump(mode="json")
    payload["unexpected"] = "value"

    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        CeqanetRecurringRunExecution.model_validate(payload)


def test_recomputed_execution_digest_cannot_authorize_request_query_drift() -> None:
    definition = _ready_definition()
    manifest = build_ceqanet_recurring_run_manifest(
        definition,
        window_start=date(2026, 7, 1),
        window_end=date(2026, 7, 7),
    )
    execution = execute_ceqanet_recurring_run(
        definition,
        manifest,
        _ready_sources(),
        _ready_checklist(),
        attempt_sequence=1,
        execute_live=True,
        client=_FakeClient(),
    )
    payload = execution.model_dump(mode="json")
    payload["execution_report"]["snapshots"][0]["request_url"] = (
        "https://ceqanet.lci.ca.gov/Search?County=Orange&page=1"
    )
    payload["execution_digest"] = canonical_digest(
        {
            key: value
            for key, value in payload.items()
            if key not in {"executed_at", "execution_digest"}
        }
    )
    tampered = CeqanetRecurringRunExecution.model_validate(payload)

    verification = verify_ceqanet_recurring_run_execution(
        definition,
        manifest,
        tampered,
        _ready_sources(),
        _ready_checklist(),
    )

    assert verification.passed is False
    assert "snapshots[0] request_url does not match manifest query" in verification.findings
'''
    replace_once(
        recurring,
        "\n\ndef test_access_assumption_blocker_prevents_ready_definition() -> None:\n",
        insertion + "\n\ndef test_access_assumption_blocker_prevents_ready_definition() -> None:\n",
    )

    cli = ROOT / "tests/test_ceqanet_recurring_run_cli.py"
    replace_once(
        cli,
        "    return PublicSource(\n        jurisdiction=Jurisdiction(",
        "    return PublicSource(\n"
        "        source_id=\"source-ceqanet-test\",\n"
        "        jurisdiction=Jurisdiction(",
    )


def main() -> None:
    patch_service()
    patch_verifier()
    patch_tests()


if __name__ == "__main__":
    main()
