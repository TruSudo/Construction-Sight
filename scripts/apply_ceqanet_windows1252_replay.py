"""Apply CEQAnet Windows-1252 compatibility and finalize offline replay evidence."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

from constructionsight.ceqanet_csv_live_models import CeqanetCsvLiveExecution
from constructionsight.ceqanet_csv_replay_models import (
    CeqanetCsvEncodingReplay,
    CeqanetCsvEncodingReplayVerification,
)
from constructionsight.ceqanet_csv_replay_service import (
    verify_ceqanet_csv_encoding_replay,
)
from constructionsight.models import PublicSource, VerificationStatus

ROOT = Path(__file__).resolve().parents[1]
DATE = "2026-07-12"
EVIDENCE_DIR = ROOT / "evidence/source_verification"
EXECUTION_PATH = EVIDENCE_DIR / f"ceqanet_csv_live_execution_{DATE}.json"
REPLAY_PATH = EVIDENCE_DIR / f"ceqanet_csv_windows1252_replay_{DATE}.json"
VERIFICATION_PATH = EVIDENCE_DIR / f"ceqanet_csv_windows1252_replay_verification_{DATE}.json"
REPORT_PATH = ROOT / f"docs/audits/ceqanet_csv_windows1252_replay_{DATE}.md"


def _replace_once(path: Path, old: str, new: str) -> None:
    text = path.read_text(encoding="utf-8")
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"expected one replay anchor in {path}, found {count}: {old!r}")
    path.write_text(text.replace(old, new, 1), encoding="utf-8")


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def patch() -> None:
    _patch_service()
    _patch_cli()


def _patch_service() -> None:
    path = ROOT / "src/constructionsight/ceqanet_csv_service.py"
    _replace_once(
        path,
        "    try:\n        text = content.decode(\"utf-8-sig\")\n    except UnicodeDecodeError as exc:\n        raise ValueError(\n            \"CEQAnet CSV body must use UTF-8 or UTF-8 with BOM\"\n        ) from exc\n",
        "    text, encoding = _decode_csv_body(content)\n",
    )
    _replace_once(
        path,
        "    warnings = [\n        \"unknown source columns are preserved without unsupported semantic assignment\",\n        \"offline inspection does not establish live availability or recurring source maturity\",\n    ]\n",
        "    warnings = [\n        \"unknown source columns are preserved without unsupported semantic assignment\",\n        \"offline inspection does not establish live availability or recurring source maturity\",\n    ]\n    if encoding == \"windows-1252\":\n        warnings.append(\n            \"source body decoded as Windows-1252 after strict UTF-8 failure\"\n        )\n",
    )
    _replace_once(
        path,
        "        \"content_type\": normalized_content_type,\n        \"byte_length\": len(content),\n",
        "        \"content_type\": normalized_content_type,\n        \"encoding\": encoding,\n        \"byte_length\": len(content),\n",
    )
    _replace_once(
        path,
        "\ndef _validate_sch_number(value: str) -> None:\n",
        "\ndef _decode_csv_body(content: bytes) -> tuple[str, str]:\n"
        "    try:\n"
        "        return content.decode(\"utf-8-sig\"), \"utf-8-sig\"\n"
        "    except UnicodeDecodeError:\n"
        "        pass\n"
        "    try:\n"
        "        return content.decode(\"windows-1252\"), \"windows-1252\"\n"
        "    except UnicodeDecodeError as exc:\n"
        "        raise ValueError(\n"
        "            \"CEQAnet CSV body must use UTF-8, UTF-8 with BOM, or Windows-1252\"\n"
        "        ) from exc\n\n\n"
        "def _validate_sch_number(value: str) -> None:\n",
    )


def _patch_cli() -> None:
    path = ROOT / "src/constructionsight/ceqanet_csv_cli.py"
    _replace_once(
        path,
        "from constructionsight.ceqanet_csv_live_service import (\n"
        "    execute_ceqanet_csv_live_request,\n"
        "    verify_ceqanet_csv_live_execution,\n"
        ")\n",
        "from constructionsight.ceqanet_csv_live_service import (\n"
        "    execute_ceqanet_csv_live_request,\n"
        "    verify_ceqanet_csv_live_execution,\n"
        ")\n"
        "from constructionsight.ceqanet_csv_replay_models import CeqanetCsvEncodingReplay\n"
        "from constructionsight.ceqanet_csv_replay_service import (\n"
        "    build_ceqanet_csv_encoding_replay,\n"
        "    verify_ceqanet_csv_encoding_replay,\n"
        ")\n",
    )
    marker = "\ndef _write_json_file(path: Path, payload: object, *, overwrite: bool) -> None:\n"
    commands = '''\n\n@app.command("replay-execution")\ndef replay_csv_execution(\n    execution_path: Annotated[\n        Path,\n        typer.Argument(help="Path to a retained live CSV execution artifact."),\n    ],\n    output: Annotated[\n        Path,\n        typer.Option("--output", help="Required derived replay JSON output path."),\n    ],\n    max_retained_rows: Annotated[\n        int,\n        typer.Option("--max-retained-rows", min=0),\n    ] = 1_000,\n    overwrite: Annotated[bool, typer.Option("--overwrite")] = False,\n) -> None:\n    """Replay retained response bytes offline using the current CSV parser."""\n\n    try:\n        payload: Any = json.loads(execution_path.read_text(encoding="utf-8"))\n        execution = CeqanetCsvLiveExecution.model_validate(payload)\n        replay = build_ceqanet_csv_encoding_replay(\n            execution,\n            max_retained_rows=max_retained_rows,\n        )\n    except (OSError, ValueError, json.JSONDecodeError) as exc:\n        raise typer.BadParameter(str(exc)) from exc\n    _write_json_file(output, replay.model_dump(mode="json"), overwrite=overwrite)\n    console.print(f"Wrote CEQAnet CSV encoding replay to {output}")\n\n\n@app.command("verify-replay")\ndef verify_csv_replay(\n    execution_path: Annotated[\n        Path,\n        typer.Argument(help="Path to the source live CSV execution artifact."),\n    ],\n    replay_path: Annotated[\n        Path,\n        typer.Argument(help="Path to the derived encoding replay artifact."),\n    ],\n    output: Annotated[\n        Path | None,\n        typer.Option("--output", help="Optional replay verification JSON output path."),\n    ] = None,\n) -> None:\n    """Verify a derived replay against the original retained live response."""\n\n    try:\n        execution_payload: Any = json.loads(\n            execution_path.read_text(encoding="utf-8")\n        )\n        replay_payload: Any = json.loads(replay_path.read_text(encoding="utf-8"))\n        execution = CeqanetCsvLiveExecution.model_validate(execution_payload)\n        replay = CeqanetCsvEncodingReplay.model_validate(replay_payload)\n        verification = verify_ceqanet_csv_encoding_replay(execution, replay)\n    except (OSError, ValueError, json.JSONDecodeError) as exc:\n        raise typer.BadParameter(str(exc)) from exc\n    _emit_json(verification.model_dump(mode="json"), output)\n    if not verification.passed:\n        raise typer.Exit(code=1)\n'''
    text = path.read_text(encoding="utf-8")
    if text.count(marker) != 1:
        raise RuntimeError("CEQAnet CSV CLI replay insertion anchor mismatch")
    path.write_text(text.replace(marker, commands + marker, 1), encoding="utf-8")


def finalize() -> None:
    execution = CeqanetCsvLiveExecution.model_validate(_load_json(EXECUTION_PATH))
    replay = CeqanetCsvEncodingReplay.model_validate(_load_json(REPLAY_PATH))
    stored = CeqanetCsvEncodingReplayVerification.model_validate(
        _load_json(VERIFICATION_PATH)
    )
    recomputed = verify_ceqanet_csv_encoding_replay(execution, replay)
    if stored != recomputed or not stored.passed:
        raise RuntimeError("CEQAnet Windows-1252 replay did not verify cleanly")
    if replay.inspection.encoding != "windows-1252":
        raise RuntimeError("retained CEQAnet body did not select Windows-1252")
    if replay.inspection.body_sha256 != execution.body_sha256:
        raise RuntimeError("replay body hash differs from the retained live evidence")
    if replay.inspection.byte_length != execution.observed_body_byte_length:
        raise RuntimeError("replay body length differs from the retained live evidence")

    sources = [
        PublicSource.model_validate(item)
        for item in _load_json(ROOT / "data/source_registry.seed.json")
    ]
    ceqanet = [source for source in sources if source.platform_family.value == "ceqanet"]
    if len(ceqanet) != 1 or ceqanet[0].verification_status is not VerificationStatus.PARTIAL:
        raise RuntimeError("encoding replay must preserve CEQAnet partial maturity")

    _write_report(execution, replay, stored)
    _reconcile_readme(replay)
    _reconcile_architecture(replay)
    _reconcile_status(replay)
    _reconcile_audit(replay)


def _write_report(
    execution: CeqanetCsvLiveExecution,
    replay: CeqanetCsvEncodingReplay,
    verification: CeqanetCsvEncodingReplayVerification,
) -> None:
    inspection = replay.inspection
    report = f"""# CEQAnet Windows-1252 Offline Replay

Replayed at: `{replay.replayed_at.isoformat()}`

## Source evidence

- Source execution digest: `{execution.execution_digest}`
- Source request URL: `{execution.request_url}`
- Source HTTP status: `{execution.status_code}`
- Source body bytes: `{execution.observed_body_byte_length}`
- Source body SHA-256: `{execution.body_sha256}`
- New network request: `false`
- Persistence mutated: `false`

## Corrected inspection

- Encoding: `{inspection.encoding}`
- Content type: `{inspection.content_type}`
- Columns: `{inspection.column_count}`
- Rows: `{inspection.row_count}`
- Retained rows: `{inspection.retained_row_count}`
- Rows truncated: `{str(inspection.rows_truncated).lower()}`
- Normalized headers: `{json.dumps(inspection.normalized_headers)}`
- Unknown columns: `{json.dumps(inspection.unknown_columns)}`
- Inspection digest: `{inspection.inspection_digest}`
- Replay digest: `{replay.replay_digest}`

## Independent verification

- Passed: `{str(verification.passed).lower()}`
- Finding count: `{verification.finding_count}`
- Findings: `{json.dumps(verification.findings)}`

## Maturity decision

CEQAnet remains `partial`. The successful offline replay proves that the one retained HTTP 200 response is structurally valid source-provided CSV when decoded as Windows-1252. It does not itself authorize promotion, another request, recurring operation, persistence, or broader coverage claims.

## Next gate

Review the successful point-in-time CSV proof and replay in a separate controlled source-maturity phase. Any promotion must bind both the original execution and replay digests and preserve the HTML 403 limitation as surface-specific evidence.

## Evidence artifacts

- `{EXECUTION_PATH.relative_to(ROOT).as_posix()}`
- `{REPLAY_PATH.relative_to(ROOT).as_posix()}`
- `{VERIFICATION_PATH.relative_to(ROOT).as_posix()}`
"""
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(report, encoding="utf-8")


def _reconcile_readme(replay: CeqanetCsvEncodingReplay) -> None:
    path = ROOT / "README.md"
    inspection = replay.inspection
    _replace_once(
        path,
        "ConstructionSight has an official CSV contract that plans exact project/document export URLs, validates already-obtained CSV bytes, and performs one explicitly authorized bounded GET with no retry. The bounded project CSV proof failed and was preserved without retry or bypass. HTTP status: 200; findings: live CSV offline inspection failed: CEQAnet CSV body must use UTF-8 or UTF-8 with BOM; live CSV inspection recorded error: CEQAnet CSV body must use UTF-8 or UTF-8 with BOM Source maturity remains `partial`; promotion remains a separate controlled decision supported only by reviewed evidence.",
        "ConstructionSight has an official CSV contract that plans exact project/document export URLs, validates already-obtained CSV bytes, and performs one explicitly authorized bounded GET with no retry. The original HTTP 200 proof failed under the former UTF-8-only parser and remains preserved. An offline replay of the exact retained body now passes as Windows-1252 with "
        + str(inspection.row_count)
        + " source rows and an independently verified replay digest. Source maturity remains `partial`; promotion remains a separate controlled decision supported only by reviewed evidence.",
    )
    _replace_once(
        path,
        "- One-request CEQAnet CSV live-proof execution with explicit authorization and no retries\n",
        "- One-request CEQAnet CSV live-proof execution with explicit authorization and no retries\n"
        "- Strict UTF-8-first and explicit Windows-1252 fallback for source-provided CSV\n"
        "- Offline encoding replay linked to the original execution digest and body hash\n",
    )
    _replace_once(
        path,
        "- `docs/audits/ceqanet_csv_live_proof_2026-07-12.md`\n",
        "- `docs/audits/ceqanet_csv_live_proof_2026-07-12.md`\n"
        "- `evidence/source_verification/ceqanet_csv_windows1252_replay_2026-07-12.json`\n"
        "- `evidence/source_verification/ceqanet_csv_windows1252_replay_verification_2026-07-12.json`\n"
        "- `docs/audits/ceqanet_csv_windows1252_replay_2026-07-12.md`\n",
    )
    _replace_once(
        path,
        "- The bounded project CSV proof failed and was preserved without retry or bypass. HTTP status: 200; findings: live CSV offline inspection failed: CEQAnet CSV body must use UTF-8 or UTF-8 with BOM; live CSV inspection recorded error: CEQAnet CSV body must use UTF-8 or UTF-8 with BOM\n- One point-in-time CSV result does not establish recurring availability, completeness, or broader source coverage.\n",
        "- The original UTF-8 inspection failure remains preserved; the derived Windows-1252 replay passes against the same retained body hash without a second request.\n"
        "- One point-in-time CSV success and offline replay do not establish recurring availability, completeness, or broader source coverage.\n",
    )


def _reconcile_architecture(replay: CeqanetCsvEncodingReplay) -> None:
    path = ROOT / "docs/architecture/ceqanet_official_csv_contract.md"
    _replace_once(
        path,
        "4. decodes UTF-8 with optional BOM;\n",
        "4. decodes strict UTF-8 with optional BOM, then explicit Windows-1252 only if UTF-8 fails;\n",
    )
    _replace_once(
        path,
        "The implementation proves deterministic planning, strict offline validation, and a bounded live-proof mechanism. The bounded project CSV proof failed and was preserved without retry or bypass. HTTP status: 200; findings: live CSV offline inspection failed: CEQAnet CSV body must use UTF-8 or UTF-8 with BOM; live CSV inspection recorded error: CEQAnet CSV body must use UTF-8 or UTF-8 with BOM The recorded automated HTML path returned HTTP 403 and remains blocked.",
        "The implementation proves deterministic planning, strict offline validation, and a bounded live-proof mechanism. The original HTTP 200 execution and UTF-8 failure remain preserved. A derived offline replay of the exact body now passes as Windows-1252 with "
        + str(replay.inspection.row_count)
        + " rows and no second network request. The recorded automated HTML path returned HTTP 403 and remains blocked.",
    )
    _replace_once(
        path,
        "One self-removing evidence phase performed the project-scoped request for SCH `2026030377` and committed the execution and offline verification artifacts.\n\nKeep CEQAnet partial. Any further access investigation, source clarification, or later proof must be a separate explicitly authorized phase; no retry or bypass is implied.",
        "One self-removing evidence phase performed the project-scoped request for SCH `2026030377`. A later offline-only phase replayed the exact retained body as Windows-1252 and committed a verified derived inspection without another request.\n\nReview the successful proof and replay in a separate controlled maturity phase. No promotion, retry, scheduling, persistence, or broader coverage is implied.",
    )
    _replace_once(
        path,
        "constructionsight-ceqanet-csv verify-execution <artifact> [--output <verification>]\n",
        "constructionsight-ceqanet-csv verify-execution <artifact> [--output <verification>]\n"
        "constructionsight-ceqanet-csv replay-execution <execution> --output <replay>\n"
        "constructionsight-ceqanet-csv verify-replay <execution> <replay> [--output <verification>]\n",
    )


def _reconcile_status(replay: CeqanetCsvEncodingReplay) -> None:
    path = ROOT / "docs/architecture/current_implementation_status.md"
    _replace_once(
        path,
        "| CEQAnet official CSV contract | Yes | Yes | Yes | Artifact-only | Yes | Guarded proof only | Exact URL planning, offline inspection, and one-request/no-retry proof execution are implemented. The bounded project CSV proof failed and was preserved without retry or bypass. HTTP status: 200; findings: live CSV offline inspection failed: CEQAnet CSV body must use UTF-8 or UTF-8 with BOM; live CSV inspection recorded error: CEQAnet CSV body must use UTF-8 or UTF-8 with BOM No persistence, scheduling, or source promotion is claimed. |",
        "| CEQAnet official CSV contract | Yes | Yes | Yes | Artifact-only | Yes | Guarded proof only | Exact planning, one-request proof execution, strict UTF-8-first/Windows-1252 decoding, and offline replay verification are implemented. The retained HTTP 200 body replays successfully with "
        + str(replay.inspection.row_count)
        + " rows. No persistence, scheduling, or source promotion is claimed. |",
    )
    _replace_once(
        path,
        "| CS-PLAN-002 | Verified recurring live adapters | CEQAnet has `partial` maturity, verified-only recurring-run governance, and a committed one-request CSV proof artifact. Automated HTML collection received HTTP 403 and remains blocked; no scheduler exists. | Keep CEQAnet partial. Any further access investigation, source clarification, or later proof must be a separate explicitly authorized phase; no retry or bypass is implied. |",
        "| CS-PLAN-002 | Verified recurring live adapters | CEQAnet has `partial` maturity, a committed HTTP 200 CSV proof, and a verified Windows-1252 offline replay of the exact retained body. HTML automation remains blocked by HTTP 403; no scheduler exists. | Review a separate controlled source-maturity proposal that binds the execution and replay digests while preserving surface-specific limitations. |",
    )
    _replace_once(
        path,
        "| CS-VIAM-018 | P1 | CEQAnet evidence tree | The prior evidence phase merged temporary collector files while its claimed proof artifacts were absent from `main`. | PR #94 removed temporary tooling, committed the evidence/checklist/audit artifacts, restored canonical CI, and preserved HTTP 403 without bypass or maturity overclaim. |",
        "| CS-VIAM-018 | P1 | CEQAnet evidence tree | The prior evidence phase merged temporary collector files while its claimed proof artifacts were absent from `main`. | PR #94 removed temporary tooling, committed the evidence/checklist/audit artifacts, restored canonical CI, and preserved HTTP 403 without bypass or maturity overclaim. |\n"
        "| CS-VIAM-019 | P1 | CEQAnet CSV encoding | The first live CSV proof returned HTTP 200 but the UTF-8-only parser rejected a source Windows-1252 byte. | Parsing now prefers strict UTF-8 and falls back explicitly to Windows-1252; the exact retained body is replayed offline, digest-bound, independently verified, and tested without another request. |",
    )


def _reconcile_audit(replay: CeqanetCsvEncodingReplay) -> None:
    path = ROOT / "docs/audits/full_repo_audit_inventory.md"
    _replace_once(
        path,
        "ConstructionSight is not yet a production recurring live-source platform. Most adapter families are contracts or planned integrations. CEQAnet is canonically `partial`: its official public pages, policies, data fields, and CSV links are materially observed, but bounded automated HTML collection received HTTP 403 and no bypass was attempted. The bounded project CSV proof failed and was preserved without retry or bypass. HTTP status: 200; findings: live CSV offline inspection failed: CEQAnet CSV body must use UTF-8 or UTF-8 with BOM; live CSV inspection recorded error: CEQAnet CSV body must use UTF-8 or UTF-8 with BOM The other three canonical sources remain unverified. No source is currently `verified`, no production scheduler exists, and no external outreach-sending behavior or GUI/operator application is implemented.",
        "ConstructionSight is not yet a production recurring live-source platform. Most adapter families are contracts or planned integrations. CEQAnet is canonically `partial`: HTML automation returned HTTP 403 without bypass, while the source-provided CSV endpoint returned one retained HTTP 200 response. The original UTF-8 failure remains preserved, and an offline Windows-1252 replay of the exact body now passes with "
        + str(replay.inspection.row_count)
        + " rows. The other three canonical sources remain unverified. No source is currently `verified`, no production scheduler exists, and no external outreach-sending behavior or GUI/operator application is implemented.",
    )
    _replace_once(
        path,
        "| CEQAnet official CSV contract | Yes | Yes | Yes | Artifact-only | Yes | Guarded proof only | Exact planning, offline inspection, and one explicit no-retry GET are canonical. The bounded project CSV proof failed and was preserved without retry or bypass. HTTP status: 200; findings: live CSV offline inspection failed: CEQAnet CSV body must use UTF-8 or UTF-8 with BOM; live CSV inspection recorded error: CEQAnet CSV body must use UTF-8 or UTF-8 with BOM The execution and verification artifacts are committed; no persistence is claimed. |",
        "| CEQAnet official CSV contract | Yes | Yes | Yes | Artifact-only | Yes | Guarded proof only | Exact planning, one no-retry GET, strict UTF-8-first/Windows-1252 parsing, and offline replay are canonical. The retained HTTP 200 body replays successfully with "
        + str(replay.inspection.row_count)
        + " rows; no persistence is claimed. |",
    )
    _replace_once(
        path,
        "| CS-AUDIT-024 | P1 | CEQAnet observation logic | Brittle text markers and a robots media-type assumption rejected valid source behavior and obscured the true access boundary. | Official page shapes and policies were reviewed, diagnostic failures are preserved, HTTP 403 is treated as a blocker, and no bypass is permitted. |",
        "| CS-AUDIT-024 | P1 | CEQAnet observation logic | Brittle text markers and a robots media-type assumption rejected valid source behavior and obscured the true access boundary. | Official page shapes and policies were reviewed, diagnostic failures are preserved, HTTP 403 is treated as a blocker, and no bypass is permitted. |\n"
        "| CS-AUDIT-025 | P1 | CEQAnet CSV encoding | The first live CSV proof returned valid source bytes containing Windows-1252 data that the UTF-8-only parser rejected. | Strict UTF-8 remains preferred; explicit Windows-1252 fallback is digest-visible, tested, and used to derive a separately verified replay from the original retained body without network access. |",
    )
    _replace_once(
        path,
        "| CS-PLAN-002 | Verified recurring live source adapters | CEQAnet is `partial`, verified-only recurring-run governance exists, and one bounded CSV proof is committed. Automated HTML collection received HTTP 403; no attempt ledger or scheduler exists. | Keep CEQAnet partial. Any further access investigation, source clarification, or later proof must be a separate explicitly authorized phase; no retry or bypass is implied. |",
        "| CS-PLAN-002 | Verified recurring live source adapters | CEQAnet is `partial`, one HTTP 200 CSV proof is committed, and the exact body has a verified Windows-1252 replay. HTML automation remains blocked by HTTP 403; no attempt ledger or scheduler exists. | Review a separate controlled source-maturity proposal binding the original execution and replay digests while preserving surface-specific limitations. |",
    )
    _replace_once(
        path,
        "| Official CSV contract | Deterministic planning, offline inspection, and one-request/no-retry proof execution exist. The bounded project CSV proof failed and was preserved without retry or bypass. HTTP status: 200; findings: live CSV offline inspection failed: CEQAnet CSV body must use UTF-8 or UTF-8 with BOM; live CSV inspection recorded error: CEQAnet CSV body must use UTF-8 or UTF-8 with BOM |",
        "| Official CSV contract | Deterministic planning, one no-retry HTTP 200 proof, and a verified Windows-1252 offline replay of the exact retained body exist. |",
    )
    _replace_once(
        path,
        "| CEQAnet CSV inspections/executions | Schema-versioned offline inspections and live-proof execution envelopes may be written by the operator CLI; no database write, attachment download, retry, or schedule is authorized. |",
        "| CEQAnet CSV inspections/executions/replays | Schema-versioned offline inspections, live-proof envelopes, and derived encoding replays may be written by the operator CLI; no database write, attachment download, retry, or schedule is authorized. |",
    )


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit("usage: apply_ceqanet_windows1252_replay.py patch|finalize")
    command = sys.argv[1]
    if command == "patch":
        patch()
    elif command == "finalize":
        finalize()
    else:
        raise SystemExit(f"unknown command: {command}")


if __name__ == "__main__":
    main()
