"""CLI for offline CEQAnet source-maturity proposals."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Annotated, Any

import typer
from rich.console import Console

from constructionsight.ceqanet_csv_live_models import CeqanetCsvLiveExecution
from constructionsight.ceqanet_csv_replay_models import (
    CeqanetCsvEncodingReplay,
    CeqanetCsvEncodingReplayVerification,
)
from constructionsight.ceqanet_maturity_proposal_models import (
    CeqanetSourceMaturityProposal,
)
from constructionsight.ceqanet_maturity_proposal_service import (
    build_ceqanet_source_maturity_proposal,
    verify_ceqanet_source_maturity_proposal,
)
from constructionsight.models import PublicSource

app = typer.Typer(help="ConstructionSight offline CEQAnet maturity proposal tools.")
console = Console()


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _load_sources(path: Path) -> list[PublicSource]:
    payload: Any = _load_json(path)
    if not isinstance(payload, list):
        raise ValueError("source registry JSON must be a list")
    return [PublicSource.model_validate(item) for item in payload]


def _write_json(path: Path, payload: object, *, overwrite: bool) -> None:
    if path.exists() and not overwrite:
        raise ValueError(f"output already exists: {path}; pass --overwrite to replace it")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True, default=str) + "\n",
        encoding="utf-8",
    )


def _require_distinct_output(output: Path, inputs: tuple[Path, ...]) -> None:
    output_identity = output.resolve()
    if any(path.resolve() == output_identity for path in inputs):
        raise ValueError("output path must differ from every evidence input path")


@app.callback()
def maturity_root() -> None:
    """ConstructionSight CEQAnet source-maturity proposal commands."""


@app.command("build")
def build_proposal(
    registry_path: Annotated[Path, typer.Argument(help="Current source registry JSON.")],
    execution_path: Annotated[
        Path,
        typer.Argument(help="Retained CEQAnet live CSV execution JSON."),
    ],
    replay_path: Annotated[
        Path,
        typer.Argument(help="Verified CEQAnet Windows-1252 replay JSON."),
    ],
    replay_verification_path: Annotated[
        Path,
        typer.Argument(help="Independent replay verification JSON."),
    ],
    output: Annotated[
        Path,
        typer.Option("--output", help="Required proposal JSON output path."),
    ],
    overwrite: Annotated[bool, typer.Option("--overwrite")] = False,
) -> None:
    """Build a report-only keep-partial proposal without network or mutation."""

    inputs = (
        registry_path,
        execution_path,
        replay_path,
        replay_verification_path,
    )
    try:
        _require_distinct_output(output, inputs)
        proposal = build_ceqanet_source_maturity_proposal(
            _load_sources(registry_path),
            CeqanetCsvLiveExecution.model_validate(_load_json(execution_path)),
            CeqanetCsvEncodingReplay.model_validate(_load_json(replay_path)),
            CeqanetCsvEncodingReplayVerification.model_validate(
                _load_json(replay_verification_path)
            ),
        )
        _write_json(
            output,
            proposal.model_dump(mode="json"),
            overwrite=overwrite,
        )
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        raise typer.BadParameter(str(exc)) from exc
    console.print(f"Wrote CEQAnet source-maturity proposal to {output}")
    console.print(f"Proposal digest: {proposal.proposal_digest}")


@app.command("verify")
def verify_proposal(
    registry_path: Annotated[Path, typer.Argument(help="Current source registry JSON.")],
    execution_path: Annotated[
        Path,
        typer.Argument(help="Retained CEQAnet live CSV execution JSON."),
    ],
    replay_path: Annotated[
        Path,
        typer.Argument(help="Verified CEQAnet Windows-1252 replay JSON."),
    ],
    replay_verification_path: Annotated[
        Path,
        typer.Argument(help="Independent replay verification JSON."),
    ],
    proposal_path: Annotated[
        Path,
        typer.Argument(help="Source-maturity proposal JSON to verify."),
    ],
    output: Annotated[
        Path | None,
        typer.Option("--output", help="Optional verification JSON output path."),
    ] = None,
    overwrite: Annotated[bool, typer.Option("--overwrite")] = False,
) -> None:
    """Verify a proposal against exact current evidence and registry content."""

    try:
        verification = verify_ceqanet_source_maturity_proposal(
            _load_sources(registry_path),
            CeqanetCsvLiveExecution.model_validate(_load_json(execution_path)),
            CeqanetCsvEncodingReplay.model_validate(_load_json(replay_path)),
            CeqanetCsvEncodingReplayVerification.model_validate(
                _load_json(replay_verification_path)
            ),
            CeqanetSourceMaturityProposal.model_validate(_load_json(proposal_path)),
        )
        payload = verification.model_dump(mode="json")
        if output is None:
            console.print_json(json.dumps(payload))
        else:
            _require_distinct_output(
                output,
                (
                    registry_path,
                    execution_path,
                    replay_path,
                    replay_verification_path,
                    proposal_path,
                ),
            )
            _write_json(output, payload, overwrite=overwrite)
            console.print(f"Wrote CEQAnet maturity verification to {output}")
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        raise typer.BadParameter(str(exc)) from exc
    if not verification.passed:
        raise typer.Exit(code=1)
