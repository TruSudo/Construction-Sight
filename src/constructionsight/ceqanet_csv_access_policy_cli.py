"""CLI for offline CEQAnet CSV evidence-access policy governance."""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from typing import Annotated, Any

import typer
from rich.console import Console

from constructionsight.ceqanet_csv_access_policy_models import (
    CeqanetCsvAccessPolicy,
)
from constructionsight.ceqanet_csv_access_policy_service import (
    assert_ceqanet_csv_access_policy_current,
    build_ceqanet_csv_access_policy,
    verify_ceqanet_csv_access_policy,
)
from constructionsight.ceqanet_csv_live_models import CeqanetCsvLiveExecution
from constructionsight.ceqanet_csv_replay_models import (
    CeqanetCsvEncodingReplay,
    CeqanetCsvEncodingReplayVerification,
)
from constructionsight.ceqanet_maturity_proposal_models import (
    CeqanetSourceMaturityProposal,
    CeqanetSourceMaturityProposalVerification,
)
from constructionsight.models import PublicSource
from constructionsight.storage.runtime_artifacts import read_runtime_text, write_runtime_text

app = typer.Typer(help="ConstructionSight bounded CEQAnet CSV access policies.")
console = Console()


def _load_json(path: Path) -> Any:
    return json.loads(read_runtime_text(path))


def _load_sources(path: Path) -> list[PublicSource]:
    payload: Any = _load_json(path)
    if not isinstance(payload, list):
        raise ValueError("source registry JSON must be a list")
    return [PublicSource.model_validate(item) for item in payload]


def _parse_date(value: str, label: str) -> date:
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise ValueError(f"{label} must use YYYY-MM-DD") from exc


def _write_json(path: Path, payload: object, *, overwrite: bool) -> None:
    if path.exists() and not overwrite:
        raise ValueError(f"output already exists: {path}; pass --overwrite to replace it")
    write_runtime_text(
        path,
        json.dumps(payload, indent=2, sort_keys=True, default=str) + "\n", overwrite=overwrite,
    )


def _require_distinct_output(output: Path, inputs: tuple[Path, ...]) -> None:
    output_identity = output.resolve()
    if any(path.resolve() == output_identity for path in inputs):
        raise ValueError("output path must differ from every evidence input path")


def _evidence_inputs(
    registry_path: Path,
    execution_path: Path,
    replay_path: Path,
    replay_verification_path: Path,
    maturity_proposal_path: Path,
    maturity_verification_path: Path,
) -> tuple[Path, ...]:
    return (
        registry_path,
        execution_path,
        replay_path,
        replay_verification_path,
        maturity_proposal_path,
        maturity_verification_path,
    )


def _build_from_paths(
    registry_path: Path,
    execution_path: Path,
    replay_path: Path,
    replay_verification_path: Path,
    maturity_proposal_path: Path,
    maturity_verification_path: Path,
    *,
    effective_date: date,
    expires_on: date,
) -> CeqanetCsvAccessPolicy:
    return build_ceqanet_csv_access_policy(
        _load_sources(registry_path),
        CeqanetCsvLiveExecution.model_validate(_load_json(execution_path)),
        CeqanetCsvEncodingReplay.model_validate(_load_json(replay_path)),
        CeqanetCsvEncodingReplayVerification.model_validate(
            _load_json(replay_verification_path)
        ),
        CeqanetSourceMaturityProposal.model_validate(
            _load_json(maturity_proposal_path)
        ),
        CeqanetSourceMaturityProposalVerification.model_validate(
            _load_json(maturity_verification_path)
        ),
        effective_date=effective_date,
        expires_on=expires_on,
    )


@app.callback()
def policy_root() -> None:
    """ConstructionSight CEQAnet CSV access policy commands."""


@app.command("build")
def build_policy(
    registry_path: Annotated[Path, typer.Argument(help="Current source registry JSON.")],
    execution_path: Annotated[
        Path,
        typer.Argument(help="Retained live CSV execution JSON."),
    ],
    replay_path: Annotated[Path, typer.Argument(help="Verified CSV replay JSON.")],
    replay_verification_path: Annotated[
        Path,
        typer.Argument(help="Independent replay verification JSON."),
    ],
    maturity_proposal_path: Annotated[
        Path,
        typer.Argument(help="Canonical keep-partial maturity proposal JSON."),
    ],
    maturity_verification_path: Annotated[
        Path,
        typer.Argument(help="Independent maturity proposal verification JSON."),
    ],
    effective_date: Annotated[
        str,
        typer.Option("--effective-date", help="First authorized UTC date, YYYY-MM-DD."),
    ],
    expires_on: Annotated[
        str,
        typer.Option("--expires-on", help="Last authorized UTC date, YYYY-MM-DD."),
    ],
    output: Annotated[
        Path,
        typer.Option("--output", help="Required access policy JSON output path."),
    ],
    overwrite: Annotated[bool, typer.Option("--overwrite")] = False,
) -> None:
    """Build an offline, expiring official-CSV evidence policy."""

    inputs = _evidence_inputs(
        registry_path,
        execution_path,
        replay_path,
        replay_verification_path,
        maturity_proposal_path,
        maturity_verification_path,
    )
    try:
        _require_distinct_output(output, inputs)
        policy = _build_from_paths(
            registry_path,
            execution_path,
            replay_path,
            replay_verification_path,
            maturity_proposal_path,
            maturity_verification_path,
            effective_date=_parse_date(effective_date, "effective-date"),
            expires_on=_parse_date(expires_on, "expires-on"),
        )
        _write_json(output, policy.model_dump(mode="json"), overwrite=overwrite)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        raise typer.BadParameter(str(exc)) from exc
    console.print(f"Wrote CEQAnet CSV access policy to {output}")
    console.print(f"Policy digest: {policy.policy_digest}")


@app.command("verify")
def verify_policy(
    registry_path: Annotated[Path, typer.Argument(help="Current source registry JSON.")],
    execution_path: Annotated[
        Path,
        typer.Argument(help="Retained live CSV execution JSON."),
    ],
    replay_path: Annotated[Path, typer.Argument(help="Verified CSV replay JSON.")],
    replay_verification_path: Annotated[
        Path,
        typer.Argument(help="Independent replay verification JSON."),
    ],
    maturity_proposal_path: Annotated[
        Path,
        typer.Argument(help="Canonical maturity proposal JSON."),
    ],
    maturity_verification_path: Annotated[
        Path,
        typer.Argument(help="Independent maturity verification JSON."),
    ],
    policy_path: Annotated[Path, typer.Argument(help="CSV access policy to verify.")],
    output: Annotated[
        Path | None,
        typer.Option("--output", help="Optional verification JSON output path."),
    ] = None,
    overwrite: Annotated[bool, typer.Option("--overwrite")] = False,
) -> None:
    """Verify policy content against the exact current evidence chain."""

    try:
        policy = CeqanetCsvAccessPolicy.model_validate(_load_json(policy_path))
        verification = verify_ceqanet_csv_access_policy(
            _load_sources(registry_path),
            CeqanetCsvLiveExecution.model_validate(_load_json(execution_path)),
            CeqanetCsvEncodingReplay.model_validate(_load_json(replay_path)),
            CeqanetCsvEncodingReplayVerification.model_validate(
                _load_json(replay_verification_path)
            ),
            CeqanetSourceMaturityProposal.model_validate(
                _load_json(maturity_proposal_path)
            ),
            CeqanetSourceMaturityProposalVerification.model_validate(
                _load_json(maturity_verification_path)
            ),
            policy,
        )
        payload = verification.model_dump(mode="json")
        if output is None:
            console.print_json(json.dumps(payload))
        else:
            _require_distinct_output(
                output,
                (
                    *_evidence_inputs(
                        registry_path,
                        execution_path,
                        replay_path,
                        replay_verification_path,
                        maturity_proposal_path,
                        maturity_verification_path,
                    ),
                    policy_path,
                ),
            )
            _write_json(output, payload, overwrite=overwrite)
            console.print(f"Wrote CEQAnet CSV policy verification to {output}")
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        raise typer.BadParameter(str(exc)) from exc
    if not verification.passed:
        raise typer.Exit(code=1)


@app.command("check-current")
def check_current_policy(
    policy_path: Annotated[Path, typer.Argument(help="CSV access policy JSON.")],
    as_of_date: Annotated[
        str,
        typer.Option("--as-of-date", help="UTC date to check, YYYY-MM-DD."),
    ],
) -> None:
    """Check whether a verified policy date window is active."""

    try:
        policy = CeqanetCsvAccessPolicy.model_validate(_load_json(policy_path))
        assert_ceqanet_csv_access_policy_current(
            policy,
            as_of_date=_parse_date(as_of_date, "as-of-date"),
        )
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        raise typer.BadParameter(str(exc)) from exc
    console.print(f"CEQAnet CSV access policy is current for {as_of_date}.")
