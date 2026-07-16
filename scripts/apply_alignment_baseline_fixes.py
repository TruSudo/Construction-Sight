"""Apply the exact executable-alignment corrections proven by CI evidence."""

from __future__ import annotations

from pathlib import Path
from textwrap import dedent

ROOT = Path(__file__).resolve().parents[1]


def replace_once(relative: str, old: str, new: str) -> None:
    path = ROOT / relative
    content = path.read_text(encoding="utf-8")
    count = content.count(old)
    if count != 1:
        raise RuntimeError(f"{relative}: expected one replacement target, found {count}")
    path.write_text(content.replace(old, new, 1), encoding="utf-8")


def overwrite(relative: str, required: tuple[str, ...], content: str) -> None:
    path = ROOT / relative
    current = path.read_text(encoding="utf-8")
    missing = [fragment for fragment in required if fragment not in current]
    if missing:
        raise RuntimeError(f"{relative}: missing required stale fragments: {missing}")
    path.write_text(dedent(content).lstrip(), encoding="utf-8")


def main() -> None:
    # Detail CLI: align operator defaults with other operator CLIs and reject absent
    # confirmation before output validation, URL validation, or transport composition.
    replace_once(
        "src/constructionsight/ceqanet_detail_execute_cli.py",
        "from constructionsight.legal import SourceAccessProfile\n",
        "from constructionsight.legal import SourceAccessProfile\n"
        "from constructionsight.local_operator_authorization import resolve_local_operator_id\n",
    )
    replace_once(
        "src/constructionsight/ceqanet_detail_execute_cli.py",
        "    operator_id: Annotated[\n"
        "        str,\n"
        "        typer.Option(\n"
        "            \"--operator-id\",\n"
        "            help=\"Explicit local operator audit identity; this is not authentication.\",\n"
        "        ),\n"
        "    ],\n",
        "    operator_id: Annotated[\n"
        "        str | None,\n"
        "        typer.Option(\n"
        "            \"--operator-id\",\n"
        "            help=\"Optional local operator audit identity; this is not authentication.\",\n"
        "        ),\n"
        "    ] = None,\n",
    )
    replace_once(
        "src/constructionsight/ceqanet_detail_execute_cli.py",
        "    authorization_reason: Annotated[\n"
        "        str,\n"
        "        typer.Option(\n"
        "            \"--authorization-reason\",\n"
        "            help=\"Nonblank reason for this exact one-request authorization.\",\n"
        "        ),\n"
        "    ],\n",
        "    authorization_reason: Annotated[\n"
        "        str,\n"
        "        typer.Option(\n"
        "            \"--authorization-reason\",\n"
        "            help=\"Nonblank reason for this exact one-request authorization.\",\n"
        "        ),\n"
        "    ] = \"Execute one reviewed CEQAnet detail read.\",\n",
    )
    replace_once(
        "src/constructionsight/ceqanet_detail_execute_cli.py",
        "    _reject_output_without_json(output_path, json_output)\n",
        "    if not execute_live:\n"
        "        typer.echo(\n"
        "            \"CEQAnet detail execution blocked: caller confirmation is required \"\n"
        "            \"in addition to scope-bound authority\",\n"
        "            err=True,\n"
        "        )\n"
        "        raise typer.Exit(code=1)\n"
        "    _reject_output_without_json(output_path, json_output)\n",
    )
    replace_once(
        "src/constructionsight/ceqanet_detail_execute_cli.py",
        "            operator_id=operator_id,\n",
        "            operator_id=resolve_local_operator_id(operator_id),\n",
    )

    # Listing CLI/service: fail fast on confirmation and report lawful-access denial
    # before treating a blocked plan's empty request sequence as malformed.
    replace_once(
        "src/constructionsight/ceqanet_listing_execute_cli.py",
        "    _reject_output_without_json(output_path, json_output)\n",
        "    if not execute_live:\n"
        "        typer.echo(\n"
        "            \"CEQAnet listing execution blocked: caller confirmation is required \"\n"
        "            \"in addition to scope-bound authority\",\n"
        "            err=True,\n"
        "        )\n"
        "        raise typer.Exit(code=1)\n"
        "    _reject_output_without_json(output_path, json_output)\n",
    )
    replace_once(
        "src/constructionsight/ceqanet_listing_service.py",
        "    policy = CeqanetListingExecutionPolicy(\n"
        "        timeout_seconds=timeout_seconds,\n"
        "        max_response_bytes=max_response_bytes,\n"
        "    )\n"
        "    dry_run = CeqanetListingDryRunExecutor().run(plan)\n"
        "    if not dry_run.requests or dry_run.planned_request_count != len(dry_run.requests):\n"
        "        raise ValueError(\"listing plan must contain its exact nonempty request sequence\")\n"
        "    if dry_run.downloads_documents or dry_run.mutates_remote_state:\n"
        "        raise AuthorizationDeniedError(\n"
        "            \"listing plan attempts an authority outside read-only listing\"\n"
        "        )\n\n"
        "    access = evaluate_access(access_profile)\n"
        "    _verify_current_plan_access(\n"
        "        plan,\n"
        "        decision=access.decision,\n"
        "        reason=access.reason,\n"
        "    )\n",
        "    access = evaluate_access(access_profile)\n"
        "    _verify_current_plan_access(\n"
        "        plan,\n"
        "        decision=access.decision,\n"
        "        reason=access.reason,\n"
        "    )\n"
        "    policy = CeqanetListingExecutionPolicy(\n"
        "        timeout_seconds=timeout_seconds,\n"
        "        max_response_bytes=max_response_bytes,\n"
        "    )\n"
        "    dry_run = CeqanetListingDryRunExecutor().run(plan)\n"
        "    if not dry_run.requests or dry_run.planned_request_count != len(dry_run.requests):\n"
        "        raise ValueError(\"listing plan must contain its exact nonempty request sequence\")\n"
        "    if dry_run.downloads_documents or dry_run.mutates_remote_state:\n"
        "        raise AuthorizationDeniedError(\n"
        "            \"listing plan attempts an authority outside read-only listing\"\n"
        "        )\n",
    )

    # Persistence CLI: no file read, directory creation, plan validation, or database
    # composition before caller confirmation. Parent creation belongs to the authorized
    # executor, not destination identity composition.
    replace_once(
        "src/constructionsight/ceqanet_persistence_execute_cli.py",
        "    if database_path is not None:\n"
        "        database_path.parent.mkdir(parents=True, exist_ok=True)\n"
        "        return database_url_from_path(database_path)\n",
        "    if database_path is not None:\n"
        "        return database_url_from_path(database_path)\n",
    )
    replace_once(
        "src/constructionsight/ceqanet_persistence_execute_cli.py",
        "    _reject_output_without_json(output_path, json_output)\n",
        "    if not execute_write:\n"
        "        typer.echo(\n"
        "            \"CEQAnet persistence execution blocked: caller confirmation is \"\n"
        "            \"required in addition to scope-bound authority\",\n"
        "            err=True,\n"
        "        )\n"
        "        raise typer.Exit(code=1)\n"
        "    _reject_output_without_json(output_path, json_output)\n",
    )

    # Recurring-run CLI and application facade: confirmation precedes artifact reads,
    # and replay identity is based only on stable, already-verified evidence digests.
    replace_once(
        "src/constructionsight/ceqanet_recurring_run_cli.py",
        "    definition = _load_model(definition_path, CeqanetRecurringRunDefinition)\n",
        "    if not execute_live:\n"
        "        typer.echo(\n"
        "            \"CEQAnet recurring-run execution blocked: caller confirmation is \"\n"
        "            \"required in addition to scope-bound authority\",\n"
        "            err=True,\n"
        "        )\n"
        "        raise typer.Exit(code=1)\n"
        "    definition = _load_model(definition_path, CeqanetRecurringRunDefinition)\n",
    )
    replace_once(
        "src/constructionsight/operator_services/ceqanet_recurring_run_service.py",
        "    current_state_identity = authorization_digest(\n"
        "        \"ceqanet-recurring-run-current-state\",\n"
        "        {\n"
        "            \"definition\": definition.model_dump(mode=\"json\"),\n"
        "            \"manifest\": manifest.model_dump(mode=\"json\"),\n"
        "            \"sources\": [source.model_dump(mode=\"json\") for source in sources],\n"
        "            \"checklist\": checklist_report.model_dump(mode=\"json\"),\n"
        "            \"attempt_sequence\": attempt_sequence,\n"
        "        },\n"
        "    )\n",
        "    current_state_identity = authorization_digest(\n"
        "        \"ceqanet-recurring-run-current-state\",\n"
        "        {\n"
        "            \"definition_digest\": definition.definition_digest,\n"
        "            \"manifest_digest\": manifest.manifest_digest,\n"
        "            \"source_registry_digest\": definition.source_registry_digest,\n"
        "            \"checklist_evidence_digest\": definition.checklist_evidence_digest,\n"
        "            \"attempt_sequence\": attempt_sequence,\n"
        "        },\n"
        "    )\n",
    )

    # Parcel persistence: confirmation must precede bundle loading or database work.
    replace_once(
        "src/constructionsight/parcel_source_cli.py",
        "    try:\n"
        "        bundle = load_arcgis_bounded_proof_bundle(input_path)\n",
        "    if not authorize_persistence:\n"
        "        typer.echo(\n"
        "            \"ArcGIS bounded-proof persistence blocked: acquisition-persist-bundle \"\n"
        "            \"requires --authorize-persistence in addition to scope-bound authority\",\n"
        "            err=True,\n"
        "        )\n"
        "        raise typer.Exit(code=1)\n"
        "    try:\n"
        "        bundle = load_arcgis_bounded_proof_bundle(input_path)\n",
    )

    # Stale lawful-access assertions exposed internal field names instead of the
    # user-facing denial contract.
    for relative in (
        "tests/test_ceqanet_csv_operator_service.py",
        "tests/test_ceqanet_detail_service.py",
        "tests/test_ceqanet_listing_service.py",
    ):
        replace_once(relative, 'match="requires_login"', 'match="requires login"')

    overwrite(
        "tests/test_ceqanet_detail_execute_cli.py",
        (
            "monkeypatch.setattr(cli.httpx, \"get\", fake_get)",
            "--max-body-chars",
            "Refusing live execution without --execute-live",
        ),
        r'''
        import json
        from pathlib import Path

        from typer.testing import CliRunner

        import constructionsight.ceqanet_detail_execute_cli as cli

        runner = CliRunner()
        _URL = "https://ceqanet.lci.ca.gov/Project/2017101033"


        def _payload(*, body_text: str = "detail", body_length: int = 6, truncated: bool = False):
            return {
                "metadata": {
                    "schema_version": "ceqanet_detail_execution.v2",
                    "allowed": True,
                    "reason": "synthetic authorized detail execution",
                    "requested_url": _URL,
                    "executed_request_count": 1,
                    "successful_response_count": 1,
                    "failed_response_count": 0,
                    "authorization": {
                        "actor_id": "operator:test",
                        "decision_id": "authorization-decision:" + ("d" * 64),
                        "preflight_id": "authorization-preflight:" + ("p" * 64),
                        "valid_until": "2026-07-15T12:05:00+00:00",
                    },
                },
                "snapshots": [
                    {
                        "request_url": _URL,
                        "final_url": _URL,
                        "status_code": 200,
                        "reachable": True,
                        "failure_kind": "none",
                        "body_text": body_text,
                        "body_length": body_length,
                        "body_truncated": truncated,
                        "attempt_count": 1,
                    }
                ],
            }


        def test_ceqanet_detail_execute_cli_writes_json_output(tmp_path: Path, monkeypatch) -> None:
            output_path = tmp_path / "detail-execution.json"
            calls: list[dict[str, object]] = []

            def fake_execute(**kwargs):
                calls.append(kwargs)
                return _payload()

            monkeypatch.setattr(cli, "execute_authorized_ceqanet_detail", fake_execute)
            result = runner.invoke(
                cli.app,
                [
                    "execute",
                    "--url",
                    _URL,
                    "--operator-id",
                    "operator:test",
                    "--authorization-reason",
                    "Review one exact detail page.",
                    "--execute-live",
                    "--json-output",
                    "--output",
                    str(output_path),
                ],
            )

            assert result.exit_code == 0
            assert "Wrote CEQAnet detail execution JSON" in result.output
            assert calls[0]["detail_url"] == _URL
            assert calls[0]["operator_id"] == "operator:test"
            payload = json.loads(output_path.read_text(encoding="utf-8"))
            assert payload["metadata"]["schema_version"] == "ceqanet_detail_execution.v2"
            assert payload["metadata"]["allowed"] is True
            assert payload["metadata"]["executed_request_count"] == 1
            assert payload["metadata"]["successful_response_count"] == 1
            assert payload["snapshots"][0]["request_url"] == _URL
            assert payload["snapshots"][0]["reachable"] is True


        def test_ceqanet_detail_execute_cli_rejects_without_live_consent() -> None:
            result = runner.invoke(cli.app, ["execute", "--url", _URL, "--json-output"])

            assert result.exit_code != 0
            assert "caller confirmation is required in addition" in result.output


        def test_ceqanet_detail_execute_cli_rejects_output_without_json(tmp_path: Path) -> None:
            result = runner.invoke(
                cli.app,
                [
                    "execute",
                    "--url",
                    _URL,
                    "--execute-live",
                    "--output",
                    str(tmp_path / "detail-execution.json"),
                ],
            )

            assert result.exit_code != 0
            assert "--output requires --json-output" in result.output


        def test_ceqanet_detail_execute_cli_rejects_non_ceqanet_url() -> None:
            result = runner.invoke(
                cli.app,
                [
                    "execute",
                    "--url",
                    "https://example.com/Project/2017101033",
                    "--execute-live",
                    "--json-output",
                ],
            )

            assert result.exit_code != 0
            assert "must target the exact public CEQAnet host" in result.output


        def test_ceqanet_detail_execute_cli_forwards_bounded_body_ceiling(
            tmp_path: Path, monkeypatch
        ) -> None:
            output_path = tmp_path / "detail-execution.json"
            calls: list[dict[str, object]] = []

            def fake_execute(**kwargs):
                calls.append(kwargs)
                return _payload(body_text="abc", body_length=6, truncated=True)

            monkeypatch.setattr(cli, "execute_authorized_ceqanet_detail", fake_execute)
            result = runner.invoke(
                cli.app,
                [
                    "execute",
                    "--url",
                    _URL,
                    "--execute-live",
                    "--max-body-bytes",
                    "3",
                    "--json-output",
                    "--output",
                    str(output_path),
                ],
            )

            assert result.exit_code == 0
            assert calls[0]["max_body_bytes"] == 3
            snapshot = json.loads(output_path.read_text(encoding="utf-8"))["snapshots"][0]
            assert snapshot["body_text"] == "abc"
            assert snapshot["body_length"] == 6
            assert snapshot["body_truncated"] is True
        ''',
    )

    overwrite(
        "tests/test_ceqanet_listing_execute_cli.py",
        (
            "Refusing live execution without --execute-live",
            "assert result.exit_code == 0",
            "writes_blocked_json_output",
        ),
        r'''
        from pathlib import Path

        from typer.testing import CliRunner

        from constructionsight.ceqanet_listing_execute_cli import app

        runner = CliRunner()


        def test_ceqanet_listing_execute_cli_requires_explicit_live_consent() -> None:
            result = runner.invoke(app, ["execute", "--county", "San Bernardino"])

            assert result.exit_code != 0
            assert "caller confirmation is required in addition" in result.output


        def test_ceqanet_listing_execute_cli_blocks_captcha_access() -> None:
            result = runner.invoke(
                app,
                [
                    "execute",
                    "--county",
                    "San Bernardino",
                    "--has-captcha",
                    "--execute-live",
                    "--json-output",
                ],
            )

            assert result.exit_code == 1
            assert "lawful access preflight denied execution" in result.output
            assert "captcha" in result.output.lower()


        def test_ceqanet_listing_execute_cli_does_not_write_blocked_output(
            tmp_path: Path,
        ) -> None:
            output_path = tmp_path / "execution.json"
            result = runner.invoke(
                app,
                [
                    "execute",
                    "--county",
                    "Riverside",
                    "--robots-disallows-collection",
                    "--execute-live",
                    "--json-output",
                    "--output",
                    str(output_path),
                ],
            )

            assert result.exit_code == 1
            assert "robots" in result.output.lower()
            assert not output_path.exists()


        def test_ceqanet_listing_execute_cli_rejects_output_without_json(
            tmp_path: Path,
        ) -> None:
            output_path = tmp_path / "execution.json"
            result = runner.invoke(
                app,
                [
                    "execute",
                    "--county",
                    "San Bernardino",
                    "--execute-live",
                    "--output",
                    str(output_path),
                ],
            )

            assert result.exit_code != 0
            assert "--output requires --json-output" in result.output


        def test_ceqanet_listing_execute_cli_rejects_unbounded_query_even_with_live_consent() -> None:
            result = runner.invoke(app, ["execute", "--execute-live"])

            assert result.exit_code != 0
            assert "requires at least one bounding query filter" in result.output
        ''',
    )

    overwrite(
        "tests/test_ceqanet_persistence_execute_cli.py",
        (
            '"metadata": {"schema_version": "ceqanet_write_plan.v1"}',
            "ceqanet_persistence_execution.v1",
            "Refusing persistence execution without --execute-write",
        ),
        r'''
        import json
        from pathlib import Path

        from typer.testing import CliRunner

        from constructionsight.ceqanet_persistence_execute_cli import app

        runner = CliRunner()


        def _plan(path: Path) -> None:
            payload = {
                "metadata": {
                    "schema_version": "ceqanet_write_plan.v1",
                    "operation_count": 3,
                    "skipped_item_count": 0,
                    "network_executed": False,
                    "database_opened": False,
                    "persistence_mutated": False,
                },
                "operations": [
                    {
                        "operation_id": "sites:site:ceqanet:2017101033",
                        "action": "upsert_preview",
                        "target_collection": "sites",
                        "target_key": "site:ceqanet:2017101033",
                        "source_index": 0,
                        "payload": {
                            "site_key": "site:ceqanet:2017101033",
                            "county": "San Bernardino",
                            "city": "San Bernardino",
                        },
                    },
                    {
                        "operation_id": "entities:entity:ceqanet:lead-agency:san-bernardino-county",
                        "action": "upsert_preview",
                        "target_collection": "entities",
                        "target_key": "entity:ceqanet:lead-agency:san-bernardino-county",
                        "source_index": 0,
                        "payload": {
                            "entity_key": "entity:ceqanet:lead-agency:san-bernardino-county",
                            "name": "San Bernardino County",
                            "role": "agency",
                            "county": "San Bernardino",
                        },
                    },
                    {
                        "operation_id": "ceqa_records:ceqa:ceqanet:2017101033",
                        "action": "upsert_preview",
                        "target_collection": "ceqa_records",
                        "target_key": "ceqa:ceqanet:2017101033",
                        "source_index": 0,
                        "payload": {
                            "ceqa_key": "ceqa:ceqanet:2017101033",
                            "title": "San Bernardino Countywide Plan",
                            "county": "San Bernardino",
                            "lead_agency": "San Bernardino County",
                            "state_clearinghouse_number": "2017101033",
                            "description": "Countywide policy plan.",
                        },
                    },
                ],
                "skipped_items": [],
            }
            path.write_text(json.dumps(payload), encoding="utf-8")


        def test_ceqanet_persistence_cli_json_output(tmp_path: Path) -> None:
            plan_path = tmp_path / "plan.json"
            db_path = tmp_path / "construction.sqlite3"
            _plan(plan_path)

            result = runner.invoke(
                app,
                [
                    "execute",
                    "--write-plan",
                    str(plan_path),
                    "--database-path",
                    str(db_path),
                    "--execute-write",
                    "--json-output",
                ],
            )

            assert result.exit_code == 0
            payload = json.loads(result.stdout)
            assert payload["metadata"]["schema_version"] == "ceqanet_persistence_execution.v2"
            assert payload["metadata"]["applied_count"] == 3
            assert payload["metadata"]["database_opened"] is True
            assert payload["metadata"]["persistence_mutated"] is True
            assert db_path.exists()


        def test_ceqanet_persistence_cli_refuses_without_consent(tmp_path: Path) -> None:
            plan_path = tmp_path / "plan.json"
            db_path = tmp_path / "construction.sqlite3"
            _plan(plan_path)

            result = runner.invoke(
                app,
                [
                    "execute",
                    "--write-plan",
                    str(plan_path),
                    "--database-path",
                    str(db_path),
                    "--json-output",
                ],
            )

            assert result.exit_code != 0
            assert "caller confirmation is required in addition" in result.output
            assert not db_path.exists()


        def test_ceqanet_persistence_cli_requires_json_for_file_output(tmp_path: Path) -> None:
            plan_path = tmp_path / "plan.json"
            db_path = tmp_path / "construction.sqlite3"
            _plan(plan_path)

            result = runner.invoke(
                app,
                [
                    "execute",
                    "--write-plan",
                    str(plan_path),
                    "--database-path",
                    str(db_path),
                    "--execute-write",
                    "--output",
                    str(tmp_path / "out.json"),
                ],
            )

            assert result.exit_code != 0
            assert "--output requires --json-output" in result.output


        def test_ceqanet_persistence_cli_requires_database_target(tmp_path: Path) -> None:
            plan_path = tmp_path / "plan.json"
            _plan(plan_path)

            result = runner.invoke(
                app,
                [
                    "execute",
                    "--write-plan",
                    str(plan_path),
                    "--execute-write",
                    "--json-output",
                ],
            )

            assert result.exit_code != 0
            assert "target database" in result.output
        ''',
    )

    replace_once(
        "tests/test_ceqanet_recurring_run_cli.py",
        'assert "explicit live execution authorization is required" in result.output',
        'assert "caller confirmation is required in addition" in result.output',
    )
    replace_once(
        "tests/test_parcel_source_cli.py",
        'assert "expected bundle ID does not match" in result.output',
        'assert "expected bundle identity does not match" in result.output',
    )
    replace_once(
        "tests/test_parcel_source_cli.py",
        "    payload = json.loads(result.output)\n"
        "    assert payload[\"bundle_id\"] == bundle.bundle_id\n",
        "    payload = json.loads(result.stdout)\n"
        "    assert payload[\"bundle_id\"] == bundle.bundle_id\n",
    )


if __name__ == "__main__":
    main()
