"""Operator CLI for governed CEQAnet official CSV planning, inspection, and proof."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Annotated, Any

import typer
from rich.console import Console

from constructionsight.authorization_decision import AuthorizationDeniedError
from constructionsight.ceqanet_csv_live_models import CeqanetCsvLiveExecution
from constructionsight.ceqanet_csv_replay_models import CeqanetCsvEncodingReplay
from constructionsight.ceqanet_csv_replay_service import (
    build_ceqanet_csv_encoding_replay,
    verify_ceqanet_csv_encoding_replay,
)
from constructionsight.ceqanet_csv_service import (
    build_ceqanet_csv_export_request,
    inspect_ceqanet_csv_bytes,
    parse_ceqanet_csv_export_url,
)
from constructionsight.legal import SourceAccessProfile
from constructionsight.operator_services.ceqanet_csv_service import (
    execute_authorized_ceqanet_csv,
    verify_retained_ceqanet_csv,
)

app = typer.Typer(help="Governed CEQAnet official CSV planning, inspection, and proof.")
console = Console()


@app.callback()
def ceqanet_csv_root() -> None:
    """ConstructionSight CEQAnet official CSV contract commands."""


@app.command("plan")
def plan_csv_export(
    sch_number: Annotated[
        str,
        typer.Option("--sch-number", help="Exact 10-digit CEQAnet SCH number."),
    ],
    document_id: Annotated[
        int | None,
        typer.Option("--document-id", min=1, help="Optional positive document ID."),
    ] = None,
    output: Annotated[
        Path | None,
        typer.Option("--output", help="Optional JSON artifact output path."),
    ] = None,
) -> None:
    """Build a deterministic official CSV URL identity without making a request."""

    try:
        request = build_ceqanet_csv_export_request(
            sch_number=sch_number,
            document_id=document_id,
        )
    except ValueError as exc:
        raise typer.BadParameter(str(exc)) from exc
    _emit_json(request.model_dump(mode="json"), output)


@app.command("inspect-file")
def inspect_csv_file(
    csv_path: Annotated[Path, typer.Argument(help="Path to an already-obtained CSV file.")],
    source_url: Annotated[
        str,
        typer.Option("--source-url", help="Exact official CEQAnet CSV URL identity."),
    ],
    content_type: Annotated[
        str | None,
        typer.Option("--content-type", help="Optional observed response Content-Type."),
    ] = None,
    max_retained_rows: Annotated[
        int,
        typer.Option(
            "--max-retained-rows",
            min=0,
            help="Maximum normalized rows retained in the JSON inspection artifact.",
        ),
    ] = 1_000,
    output: Annotated[
        Path | None,
        typer.Option("--output", help="Optional JSON inspection output path."),
    ] = None,
) -> None:
    """Inspect a local CSV body without network access or persistence mutation."""

    try:
        request = parse_ceqanet_csv_export_url(source_url)
        with csv_path.open("rb") as csv_file:
            content = csv_file.read(10_000_001)
        if len(content) > 10_000_000:
            raise ValueError("CEQAnet CSV file exceeds the 10000000-byte limit")
        inspection = inspect_ceqanet_csv_bytes(
            request,
            content,
            content_type=content_type,
            max_retained_rows=max_retained_rows,
        )
    except (OSError, ValueError) as exc:
        raise typer.BadParameter(str(exc)) from exc
    _emit_json(inspection.model_dump(mode="json"), output)


@app.command("execute-live")
def execute_live_csv_export(
    sch_number: Annotated[
        str,
        typer.Option("--sch-number", help="Exact 10-digit CEQAnet SCH number."),
    ],
    output: Annotated[
        Path,
        typer.Option("--output", help="Required live execution evidence path."),
    ],
    document_id: Annotated[
        int | None,
        typer.Option("--document-id", min=1, help="Optional positive document ID."),
    ] = None,
    operator_id: Annotated[
        str | None,
        typer.Option(
            "--operator-id",
            help=(
                "Optional local audit identity. Defaults to CONSTRUCTIONSIGHT_OPERATOR_ID "
                "or the local OS account; this is not authentication."
            ),
        ),
    ] = None,
    authorization_reason: Annotated[
        str,
        typer.Option(
            "--authorization-reason",
            help="Reason for this exact one-request authorization.",
        ),
    ] = "Execute one reviewed CEQAnet CSV evidence request.",
    execute_live: Annotated[
        bool,
        typer.Option(
            "--execute-live",
            help=(
                "Additional caller confirmation. This Boolean is not the operative "
                "authorization decision."
            ),
        ),
    ] = False,
    public_url: Annotated[
        str,
        typer.Option(help="Public source URL evaluated by lawful-access policy."),
    ] = "https://ceqanet.lci.ca.gov/",
    requires_login: Annotated[
        bool,
        typer.Option(help="Mark the source as requiring login."),
    ] = False,
    has_captcha: Annotated[
        bool,
        typer.Option(help="Mark the source as presenting captcha."),
    ] = False,
    robots_disallows_collection: Annotated[
        bool,
        typer.Option(help="Mark the intended path as robots-disallowed."),
    ] = False,
    terms_disallow_collection: Annotated[
        bool,
        typer.Option(help="Mark source terms as disallowing collection."),
    ] = False,
    paywalled: Annotated[
        bool,
        typer.Option(help="Mark the source as paywalled."),
    ] = False,
    timeout_seconds: Annotated[
        float,
        typer.Option("--timeout-seconds", min=0.1, max=20.0),
    ] = 20.0,
    max_body_bytes: Annotated[
        int,
        typer.Option("--max-body-bytes", min=1, max=10_000_000),
    ] = 10_000_000,
    max_retained_rows: Annotated[
        int,
        typer.Option("--max-retained-rows", min=0, max=1_000),
    ] = 1_000,
    overwrite: Annotated[bool, typer.Option("--overwrite")] = False,
) -> None:
    """Authorize one exact CSV GET and retain its verification envelope."""

    profile = SourceAccessProfile(
        public_url=public_url,
        requires_login=requires_login,
        has_captcha=has_captcha,
        robots_disallows_collection=robots_disallows_collection,
        terms_disallow_collection=terms_disallow_collection,
        paywalled=paywalled,
    )
    try:
        request = build_ceqanet_csv_export_request(
            sch_number=sch_number,
            document_id=document_id,
        )
        result = execute_authorized_ceqanet_csv(
            request=request,
            access_profile=profile,
            authorization_reason=authorization_reason,
            caller_confirmation=execute_live,
            timeout_seconds=timeout_seconds,
            max_body_bytes=max_body_bytes,
            max_retained_rows=max_retained_rows,
            operator_id=operator_id,
        )
    except (AuthorizationDeniedError, ValueError) as exc:
        typer.echo(f"CEQAnet CSV execution blocked: {exc}", err=True)
        raise typer.Exit(code=1) from exc

    _write_json_file(
        output,
        result.execution.model_dump(mode="json"),
        overwrite=overwrite,
    )
    authorization = result.authorization.to_dict()
    console.print(f"Wrote CEQAnet CSV live execution evidence to {output}")
    console.print(f"Authorization decision: {authorization['decision_id']}")
    console.print(f"Authorization preflight: {authorization['preflight_id']}")
    console.print(f"Verification passed: {result.verification.passed}")
    if not result.verification.passed:
        for finding in result.verification.findings:
            console.print(f"- {finding}")
        raise typer.Exit(code=1)


@app.command("verify-execution")
def verify_live_csv_execution(
    execution_path: Annotated[
        Path,
        typer.Argument(help="Path to a retained live execution JSON artifact."),
    ],
    output: Annotated[
        Path | None,
        typer.Option("--output", help="Optional verification JSON output path."),
    ] = None,
) -> None:
    """Verify a retained live execution artifact without network access."""

    try:
        payload: Any = json.loads(execution_path.read_text(encoding="utf-8"))
        execution = CeqanetCsvLiveExecution.model_validate(payload)
        verification = verify_retained_ceqanet_csv(execution)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        raise typer.BadParameter(str(exc)) from exc
    _emit_json(verification.model_dump(mode="json"), output)
    if not verification.passed:
        raise typer.Exit(code=1)


@app.command("replay-execution")
def replay_csv_execution(
    execution_path: Annotated[
        Path,
        typer.Argument(help="Path to a retained live CSV execution artifact."),
    ],
    output: Annotated[
        Path,
        typer.Option("--output", help="Required derived replay JSON output path."),
    ],
    max_retained_rows: Annotated[
        int,
        typer.Option("--max-retained-rows", min=0),
    ] = 1_000,
    overwrite: Annotated[bool, typer.Option("--overwrite")] = False,
) -> None:
    """Replay retained response bytes offline using the current CSV parser."""

    try:
        payload: Any = json.loads(execution_path.read_text(encoding="utf-8"))
        execution = CeqanetCsvLiveExecution.model_validate(payload)
        replay = build_ceqanet_csv_encoding_replay(
            execution,
            max_retained_rows=max_retained_rows,
        )
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        raise typer.BadParameter(str(exc)) from exc
    _write_json_file(
        output,
        replay.model_dump(mode="json"),
        overwrite=overwrite,
    )
    console.print(f"Wrote CEQAnet CSV encoding replay to {output}")


@app.command("verify-replay")
def verify_csv_replay(
    execution_path: Annotated[
        Path,
        typer.Argument(help="Path to the source live CSV execution artifact."),
    ],
    replay_path: Annotated[
        Path,
        typer.Argument(help="Path to the derived encoding replay artifact."),
    ],
    output: Annotated[
        Path | None,
        typer.Option("--output", help="Optional replay verification JSON output path."),
    ] = None,
) -> None:
    """Verify a derived replay against the original retained live response."""

    try:
        execution_payload: Any = json.loads(
            execution_path.read_text(encoding="utf-8")
        )
        replay_payload: Any = json.loads(replay_path.read_text(encoding="utf-8"))
        execution = CeqanetCsvLiveExecution.model_validate(execution_payload)
        replay = CeqanetCsvEncodingReplay.model_validate(replay_payload)
        verification = verify_ceqanet_csv_encoding_replay(execution, replay)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        raise typer.BadParameter(str(exc)) from exc
    _emit_json(verification.model_dump(mode="json"), output)
    if not verification.passed:
        raise typer.Exit(code=1)


def _write_json_file(path: Path, payload: object, *, overwrite: bool) -> None:
    if path.exists() and not overwrite:
        raise typer.BadParameter(
            f"output already exists: {path}; pass --overwrite to replace it"
        )
    rendered = json.dumps(payload, indent=2, sort_keys=True)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp")
    temporary.write_text(f"{rendered}\n", encoding="utf-8")
    temporary.replace(path)


def _emit_json(payload: object, output: Path | None) -> None:
    rendered = json.dumps(payload, indent=2, sort_keys=True)
    if output is not None:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(f"{rendered}\n", encoding="utf-8")
        console.print(f"Wrote CEQAnet CSV artifact to {output}")
        return
    console.print_json(rendered)


if __name__ == "__main__":
    app()
