"""Command-line parcel source registry tools."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Annotated, cast

import httpx
import typer
from rich.console import Console
from rich.table import Table

from constructionsight.parcel_row_preview import load_row_preview_input, preview_rows
from constructionsight.parcel_schema_preview import (
    load_schema_preview_input,
    preview_schema,
    preview_schema_for_source_key,
)
from constructionsight.parcel_source_acquisition import (
    build_arcgis_acquisition_assessment,
    build_arcgis_probe_plan,
    get_official_arcgis_acquisition_assessments,
    get_official_arcgis_capability_snapshots,
    get_official_arcgis_probe_plans,
)
from constructionsight.parcel_source_acquisition_bundle import (
    build_arcgis_bounded_proof_bundle,
    build_arcgis_proof_persistence_receipt,
    load_arcgis_bounded_proof_bundle,
    verify_arcgis_bounded_proof_bundle,
)
from constructionsight.parcel_source_acquisition_http import (
    ParcelArcGISHTTPPolicy,
    ParcelArcGISProbeExecutionError,
    execute_arcgis_probe_plan,
    fetch_arcgis_capability_snapshot,
)
from constructionsight.parcel_source_models import ParcelProviderKind
from constructionsight.parcel_source_registry import (
    build_parcel_source_report,
    get_parcel_sources,
    parcel_source_matrix_rows,
)
from constructionsight.parcel_source_verification import (
    build_parcel_county_coverage_report,
    get_parcel_source_evidence,
    get_verified_parcel_source_profiles,
)
from constructionsight.storage.database import (
    create_database_engine,
    initialize_database,
    managed_session,
    session_factory,
)
from constructionsight.storage.parcel_source_acquisition_bundle_store import (
    store_arcgis_bounded_proof_bundle_chain,
)

app = typer.Typer(help="Inspect parcel source targets and readiness.")
console = Console(width=240, color_system=None)


@app.callback()
def main() -> None:
    """Inspect parcel source targets and readiness."""


def _reject_output_without_json(output_path: Path | None, json_output: bool) -> None:
    """Reject file output without machine-readable JSON output."""

    if output_path is not None and not json_output:
        typer.echo("--output requires --json-output.")
        raise typer.Exit(code=1)


def _write_json_file(output_path: Path, payload: object) -> None:
    """Write deterministic UTF-8 JSON output."""

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(payload, indent=2, sort_keys=True, default=str) + "\n",
        encoding="utf-8",
    )


def _provider_filter(value: str | None) -> ParcelProviderKind | None:
    """Parse an optional provider-kind filter."""

    return ParcelProviderKind(value) if value is not None else None


def _render_matrix(rows: list[dict[str, str]]) -> None:
    """Render compact source matrix rows."""

    table = Table(title="Parcel Source Registry")
    table.add_column("County")
    table.add_column("Source")
    table.add_column("Provider")
    table.add_column("Status")
    table.add_column("Geometry")
    table.add_column("Priority")
    for row in rows:
        table.add_row(
            row["county"],
            row["source_name"],
            row["provider_kind"],
            row["coverage_status"],
            row["geometry_support"],
            row["priority"],
        )
    console.print(table)


def _render_report(payload: dict[str, object]) -> None:
    """Render a compact registry report."""

    table = Table(title="Parcel Source Registry Report")
    table.add_column("Field")
    table.add_column("Value")
    table.add_row("report_id", str(payload["report_id"]))
    table.add_row("sources_reviewed", str(payload["sources_reviewed"]))
    table.add_row("counties", ", ".join(cast(list[str], payload["counties"])))
    table.add_row("ready_sources", str(len(cast(list[object], payload["ready_sources"]))))
    table.add_row("target_sources", str(len(cast(list[object], payload["target_sources"]))))
    table.add_row(
        "blocked_sources",
        str(len(cast(list[object], payload["blocked_sources"]))),
    )
    console.print(table)


def _render_schema_preview(payload: dict[str, object]) -> None:
    """Render a compact schema preview report."""

    table = Table(title="Parcel Source Schema Preview")
    table.add_column("Field")
    table.add_column("Value")
    for field_name in (
        "preview_id",
        "source_key",
        "status",
        "observed_field_count",
        "geometry_support",
        "spatial_reference",
        "next_action",
    ):
        table.add_row(field_name, str(payload.get(field_name)))
    console.print(table)

    mapped_fields = cast(list[dict[str, object]], payload.get("mapped_fields", []))
    if mapped_fields:
        mapped_table = Table(title="Mapped Parcel Fields")
        mapped_table.add_column("Source Field")
        mapped_table.add_column("Role")
        mapped_table.add_column("Score")
        for field in mapped_fields:
            mapped_table.add_row(
                str(field.get("source_field") or ""),
                str(field.get("field_role") or ""),
                str(field.get("confidence_score") or ""),
            )
        console.print(mapped_table)


def _render_row_preview(payload: dict[str, object]) -> None:
    """Render a compact parcel row preview report."""

    table = Table(title="Parcel Row Preview")
    table.add_column("Field")
    table.add_column("Value")
    for field_name in (
        "preview_id",
        "source_key",
        "status",
        "row_count",
        "usable_row_count",
        "skipped_row_count",
        "next_action",
    ):
        table.add_row(field_name, str(payload.get(field_name)))
    console.print(table)

    rows = cast(list[dict[str, object]], payload.get("rows", []))
    if rows:
        row_table = Table(title="Row Preview Samples")
        row_table.add_column("Row")
        row_table.add_column("Usable")
        row_table.add_column("APN")
        row_table.add_column("County")
        for row in rows[:10]:
            row_table.add_row(
                str(row.get("row_number") or ""),
                str(row.get("usable") or ""),
                str(row.get("normalized_apn") or ""),
                str(row.get("county") or ""),
            )
        console.print(row_table)


def _render_verification_profiles(payload: list[dict[str, object]]) -> None:
    """Render verified parcel source profiles."""

    table = Table(title="Parcel Source Verification Profiles")
    table.add_column("County")
    table.add_column("Source")
    table.add_column("Status")
    table.add_column("Schema fields")
    table.add_column("Authoritative fields")
    for profile in payload:
        table.add_row(
            str(profile["county"]),
            str(profile["source_key"]),
            str(profile["status"]),
            str(len(cast(list[object], profile["schema_fields"]))),
            ", ".join(cast(list[str], profile["authoritative_fields"])),
        )
    console.print(table)


def _render_coverage_report(payload: dict[str, object]) -> None:
    """Render countywide parcel coverage gaps."""

    summary = Table(title="Parcel County Coverage Report")
    summary.add_column("Field")
    summary.add_column("Value")
    summary.add_row("report_id", str(payload["report_id"]))
    summary.add_row("status", str(payload["status"]))
    summary.add_row("counties", ", ".join(cast(list[str], payload["counties"])))
    summary.add_row("gaps", str(len(cast(list[object], payload["gaps"]))))
    console.print(summary)

    gaps = cast(list[dict[str, object]], payload["gaps"])
    if gaps:
        table = Table(title="Unresolved County Coverage Gaps")
        table.add_column("County")
        table.add_column("Code")
        table.add_column("Fields")
        table.add_column("Next action")
        for gap in gaps:
            table.add_row(
                str(gap["county"]),
                str(gap["code"]),
                ", ".join(cast(list[str], gap["field_roles"])),
                str(gap["next_action"]),
            )
        console.print(table)


def _render_arcgis_capabilities(payload: list[dict[str, object]]) -> None:
    """Render advertised ArcGIS metadata without implying query proof."""

    table = Table(title="Parcel ArcGIS Capability Snapshots")
    table.add_column("County")
    table.add_column("Source")
    table.add_column("Probe advertised")
    table.add_column("Fields")
    table.add_column("Max page")
    for snapshot in payload:
        advertised = all(
            bool(snapshot[field])
            for field in (
                "supports_query",
                "supports_count",
                "supports_order_by",
                "supports_pagination",
                "object_id_is_unique",
            )
        )
        table.add_row(
            str(snapshot["county"]),
            str(snapshot["source_key"]),
            str(advertised),
            str(len(cast(list[object], snapshot["fields"]))),
            str(snapshot["max_record_count"]),
        )
    console.print(table)


def _render_arcgis_plans(payload: list[dict[str, object]]) -> None:
    """Render bounded probe plans."""

    table = Table(title="Parcel ArcGIS Bounded Probe Plans")
    table.add_column("County")
    table.add_column("Source")
    table.add_column("Requests")
    table.add_column("Sample")
    table.add_column("Bulk authorized")
    for plan in payload:
        table.add_row(
            str(plan["county"]),
            str(plan["source_key"]),
            str(len(cast(list[object], plan["requests"]))),
            str(plan["sample_size"]),
            str(plan["bulk_run_authorized"]),
        )
    console.print(table)


def _render_arcgis_assessments(payload: list[dict[str, object]]) -> None:
    """Render conservative ArcGIS acquisition readiness."""

    table = Table(title="Parcel ArcGIS Acquisition Readiness")
    table.add_column("County")
    table.add_column("Source")
    table.add_column("Status")
    table.add_column("Gaps")
    table.add_column("Bulk verified")
    for assessment in payload:
        table.add_row(
            str(assessment["county"]),
            str(assessment["source_key"]),
            str(assessment["status"]),
            str(len(cast(list[object], assessment["gaps"]))),
            str(assessment["bulk_acquisition_verified"]),
        )
    console.print(table)


def _render_arcgis_proof_result(
    payload: dict[str, object],
    *,
    title: str,
) -> None:
    """Render a compact offline verification or persistence result."""

    table = Table(title=title)
    table.add_column("Field")
    table.add_column("Value")
    for field_name in (
        "bundle_id",
        "source_key",
        "county",
        "status",
        "assessment_id",
        "evidence_count",
        "observation_count",
        "valid",
        "mutation_authorized",
        "bulk_run_authorized",
        "next_action",
    ):
        if field_name in payload:
            table.add_row(field_name, str(payload[field_name]))
    console.print(table)


@app.command("evidence")
def source_evidence(
    json_output: Annotated[
        bool,
        typer.Option("--json-output", help="Emit machine-readable evidence JSON."),
    ] = False,
) -> None:
    """Show digest-bound official evidence for county parcel sources."""

    payload = [evidence.to_dict() for evidence in get_parcel_source_evidence()]
    if json_output:
        typer.echo(json.dumps(payload, indent=2, sort_keys=True, default=str))
        return
    table = Table(title="Parcel Source Evidence")
    table.add_column("County")
    table.add_column("Kind")
    table.add_column("Source")
    table.add_column("Observed")
    for evidence in payload:
        table.add_row(
            str(evidence["county"]),
            str(evidence["evidence_kind"]),
            str(evidence["source_key"]),
            str(evidence["observed_at"]),
        )
    console.print(table)


@app.command("verification")
def source_verification(
    json_output: Annotated[
        bool,
        typer.Option("--json-output", help="Emit machine-readable profile JSON."),
    ] = False,
) -> None:
    """Show evidence-bound source profiles and authority limits."""

    payload = [profile.to_dict() for profile in get_verified_parcel_source_profiles()]
    if json_output:
        typer.echo(json.dumps(payload, indent=2, sort_keys=True, default=str))
        return
    _render_verification_profiles(payload)


@app.command("coverage")
def county_coverage(
    json_output: Annotated[
        bool,
        typer.Option("--json-output", help="Emit machine-readable coverage JSON."),
    ] = False,
) -> None:
    """Show exhaustive countywide parcel coverage and corroboration gaps."""

    payload = build_parcel_county_coverage_report().to_dict()
    if json_output:
        typer.echo(json.dumps(payload, indent=2, sort_keys=True, default=str))
        return
    _render_coverage_report(payload)


@app.command("acquisition-capabilities")
def acquisition_capabilities(
    json_output: Annotated[
        bool,
        typer.Option("--json-output", help="Emit machine-readable capability JSON."),
    ] = False,
) -> None:
    """Show advertised ArcGIS metadata separately from executed query proof."""

    payload = [
        snapshot.to_dict() for snapshot in get_official_arcgis_capability_snapshots()
    ]
    if json_output:
        typer.echo(json.dumps(payload, indent=2, sort_keys=True, default=str))
        return
    _render_arcgis_capabilities(payload)


@app.command("acquisition-plans")
def acquisition_plans(
    json_output: Annotated[
        bool,
        typer.Option("--json-output", help="Emit machine-readable bounded plans."),
    ] = False,
) -> None:
    """Show non-mutating count, adjacent-page, and replay requests."""

    payload = [plan.to_dict() for plan in get_official_arcgis_probe_plans()]
    if json_output:
        typer.echo(json.dumps(payload, indent=2, sort_keys=True, default=str))
        return
    _render_arcgis_plans(payload)


@app.command("acquisition-readiness")
def acquisition_readiness(
    json_output: Annotated[
        bool,
        typer.Option("--json-output", help="Emit machine-readable readiness JSON."),
    ] = False,
) -> None:
    """Show metadata, probe, and complete-rehearsal acquisition maturity."""

    payload = [
        assessment.to_dict()
        for assessment in get_official_arcgis_acquisition_assessments()
    ]
    if json_output:
        typer.echo(json.dumps(payload, indent=2, sort_keys=True, default=str))
        return
    _render_arcgis_assessments(payload)


@app.command("acquisition-probe")
def acquisition_probe(
    source_key: Annotated[
        str,
        typer.Option("--source-key", help="Verified county ArcGIS source key."),
    ],
    sample_size: Annotated[
        int,
        typer.Option("--sample-size", min=1, max=100, help="Bounded page sample size."),
    ] = 2,
    timeout_seconds: Annotated[
        float,
        typer.Option("--timeout-seconds", min=1.0, max=120.0),
    ] = 30.0,
    json_output: Annotated[
        bool,
        typer.Option("--json-output", help="Emit machine-readable probe bundle JSON."),
    ] = False,
    output_path: Annotated[
        Path | None,
        typer.Option(
            "--output",
            help="Write probe bundle JSON to a file. Requires --json-output.",
        ),
    ] = None,
) -> None:
    """Refresh schema and execute four bounded read-only ArcGIS requests."""

    _reject_output_without_json(output_path, json_output)
    profiles = {
        profile.source_key: profile for profile in get_verified_parcel_source_profiles()
    }
    profile = profiles.get(source_key)
    if profile is None:
        typer.echo(f"Unknown verified ArcGIS source key: {source_key}")
        raise typer.Exit(code=1)
    policy = ParcelArcGISHTTPPolicy(timeout_seconds=timeout_seconds)
    try:
        with httpx.Client(follow_redirects=False) as client:
            snapshot = fetch_arcgis_capability_snapshot(
                profile,
                client,
                limitations=(
                    "Advertised capabilities require executed probe proof.",
                    "This command executes a bounded probe, not a complete acquisition.",
                ),
                policy=policy,
            )
            plan = build_arcgis_probe_plan(snapshot, sample_size=sample_size)
            observations = execute_arcgis_probe_plan(
                snapshot,
                plan,
                client,
                policy=policy,
            )
        assessment = build_arcgis_acquisition_assessment(
            snapshot,
            plan,
            observations,
        )
        evidence_by_id = {
            item.evidence_id: item for item in get_parcel_source_evidence()
        }
        bundle = build_arcgis_bounded_proof_bundle(
            profile,
            (evidence_by_id[evidence_id] for evidence_id in profile.evidence_ids),
            snapshot,
            plan,
            observations,
            assessment,
        )
    except (KeyError, ValueError, ParcelArcGISProbeExecutionError) as exc:
        typer.echo(f"ArcGIS acquisition probe blocked: {exc}")
        raise typer.Exit(code=1) from exc
    payload = bundle.to_dict()
    if output_path is not None:
        _write_json_file(output_path, payload)
        typer.echo(f"Wrote ArcGIS acquisition probe JSON to {output_path}.")
        return
    if json_output:
        typer.echo(json.dumps(payload, indent=2, sort_keys=True, default=str))
        return
    _render_arcgis_assessments([assessment.to_dict()])


@app.command("acquisition-verify-bundle")
def acquisition_verify_bundle(
    input_path: Annotated[
        Path,
        typer.Option("--input", help="Portable bounded-proof bundle JSON."),
    ],
    json_output: Annotated[
        bool,
        typer.Option("--json-output", help="Emit machine-readable verification JSON."),
    ] = False,
) -> None:
    """Independently verify a bounded proof bundle without network or database access."""

    try:
        bundle = load_arcgis_bounded_proof_bundle(input_path)
        verification = verify_arcgis_bounded_proof_bundle(bundle)
    except ValueError as exc:
        typer.echo(f"ArcGIS bounded-proof verification failed: {exc}")
        raise typer.Exit(code=1) from exc
    payload = verification.to_dict()
    if json_output:
        typer.echo(json.dumps(payload, indent=2, sort_keys=True, default=str))
        return
    _render_arcgis_proof_result(payload, title="Parcel ArcGIS Proof Verification")


@app.command("acquisition-persist-bundle")
def acquisition_persist_bundle(
    input_path: Annotated[
        Path,
        typer.Option("--input", help="Portable bounded-proof bundle JSON."),
    ],
    expected_bundle_id: Annotated[
        str,
        typer.Option(
            "--expected-bundle-id",
            help="Exact digest-bound bundle identity approved for persistence.",
        ),
    ],
    database_url: Annotated[
        str | None,
        typer.Option("--database-url", help="Optional SQLAlchemy database URL."),
    ] = None,
    authorize_persistence: Annotated[
        bool,
        typer.Option(
            "--authorize-persistence",
            help="Explicitly authorize the local transactional write.",
        ),
    ] = False,
    json_output: Annotated[
        bool,
        typer.Option("--json-output", help="Emit machine-readable receipt JSON."),
    ] = False,
) -> None:
    """Persist one exact verified bundle; never authorize bulk acquisition."""

    if not authorize_persistence:
        typer.echo("ArcGIS bounded-proof persistence requires --authorize-persistence.")
        raise typer.Exit(code=1)
    try:
        bundle = load_arcgis_bounded_proof_bundle(input_path)
    except ValueError as exc:
        typer.echo(f"ArcGIS bounded-proof persistence blocked: {exc}")
        raise typer.Exit(code=1) from exc
    if bundle.bundle_id != expected_bundle_id:
        typer.echo(
            "ArcGIS bounded-proof persistence blocked: expected bundle ID does not "
            "match the verified artifact."
        )
        raise typer.Exit(code=1)
    try:
        engine = create_database_engine(database_url)
        initialize_database(engine)
        factory = session_factory(engine)
        with managed_session(factory) as session:
            store_arcgis_bounded_proof_bundle_chain(session, bundle)
    except ValueError as exc:
        typer.echo(f"ArcGIS bounded-proof persistence blocked: {exc}")
        raise typer.Exit(code=1) from exc
    receipt = build_arcgis_proof_persistence_receipt(bundle)
    payload = receipt.to_dict()
    if json_output:
        typer.echo(json.dumps(payload, indent=2, sort_keys=True, default=str))
        return
    _render_arcgis_proof_result(payload, title="Parcel ArcGIS Proof Persistence")


@app.command("matrix")
def matrix(
    county: Annotated[
        str | None,
        typer.Option("--county", help="Optional county filter."),
    ] = None,
    provider_kind: Annotated[
        str | None,
        typer.Option("--provider-kind", help="Optional provider-kind filter."),
    ] = None,
    json_output: Annotated[
        bool,
        typer.Option("--json-output", help="Emit machine-readable matrix JSON."),
    ] = False,
    output_path: Annotated[
        Path | None,
        typer.Option(
            "--output",
            help="Write matrix JSON to a file. Requires --json-output.",
        ),
    ] = None,
) -> None:
    """Show parcel source targets."""

    _reject_output_without_json(output_path, json_output)
    sources = get_parcel_sources(
        county=county,
        provider_kind=_provider_filter(provider_kind),
    )
    rows = parcel_source_matrix_rows(sources)
    if output_path is not None:
        _write_json_file(output_path, rows)
        typer.echo(f"Wrote parcel source matrix JSON to {output_path}.")
        return
    if json_output:
        typer.echo(json.dumps(rows, indent=2, sort_keys=True, default=str))
        return
    _render_matrix(rows)


@app.command("report")
def report(
    json_output: Annotated[
        bool,
        typer.Option("--json-output", help="Emit machine-readable report JSON."),
    ] = False,
    output_path: Annotated[
        Path | None,
        typer.Option(
            "--output",
            help="Write report JSON to a file. Requires --json-output.",
        ),
    ] = None,
) -> None:
    """Show parcel source readiness report."""

    _reject_output_without_json(output_path, json_output)
    payload = build_parcel_source_report().to_dict()
    if output_path is not None:
        _write_json_file(output_path, payload)
        typer.echo(f"Wrote parcel source registry report JSON to {output_path}.")
        return
    if json_output:
        typer.echo(json.dumps(payload, indent=2, sort_keys=True, default=str))
        return
    _render_report(payload)


@app.command("preview-schema")
def preview_schema_command(
    input_path: Annotated[
        Path | None,
        typer.Option(
            "--input",
            exists=True,
            file_okay=True,
            dir_okay=False,
            readable=True,
            help="Schema preview input JSON. Omit when using --source-key.",
        ),
    ] = None,
    source_key: Annotated[
        str | None,
        typer.Option("--source-key", help="Registered source key to preview."),
    ] = None,
    json_output: Annotated[
        bool,
        typer.Option("--json-output", help="Emit machine-readable preview JSON."),
    ] = False,
    output_path: Annotated[
        Path | None,
        typer.Option(
            "--output",
            help="Write schema preview JSON to a file. Requires --json-output.",
        ),
    ] = None,
) -> None:
    """Preview a parcel source schema without importing parcel data."""

    _reject_output_without_json(output_path, json_output)
    if (input_path is None) == (source_key is None):
        typer.echo("Provide exactly one of --input or --source-key.")
        raise typer.Exit(code=1)
    result = (
        preview_schema(load_schema_preview_input(input_path))
        if input_path is not None
        else preview_schema_for_source_key(cast(str, source_key))
    ).to_dict()
    if output_path is not None:
        _write_json_file(output_path, result)
        typer.echo(f"Wrote parcel source schema preview JSON to {output_path}.")
        return
    if json_output:
        typer.echo(json.dumps(result, indent=2, sort_keys=True, default=str))
        return
    _render_schema_preview(result)


@app.command("preview-rows")
def preview_rows_command(
    input_path: Annotated[
        Path,
        typer.Option(
            "--input",
            exists=True,
            file_okay=True,
            dir_okay=False,
            readable=True,
            help="Parcel row preview input JSON.",
        ),
    ],
    json_output: Annotated[
        bool,
        typer.Option("--json-output", help="Emit machine-readable row preview JSON."),
    ] = False,
    output_path: Annotated[
        Path | None,
        typer.Option(
            "--output",
            help="Write row preview JSON to a file. Requires --json-output.",
        ),
    ] = None,
) -> None:
    """Preview candidate parcel rows without persistence."""

    _reject_output_without_json(output_path, json_output)
    result = preview_rows(load_row_preview_input(input_path)).to_dict()
    if output_path is not None:
        _write_json_file(output_path, result)
        typer.echo(f"Wrote parcel row preview JSON to {output_path}.")
        return
    if json_output:
        typer.echo(json.dumps(result, indent=2, sort_keys=True, default=str))
        return
    _render_row_preview(result)
