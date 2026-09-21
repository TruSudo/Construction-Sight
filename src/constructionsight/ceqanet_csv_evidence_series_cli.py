"""CLI for governed CEQAnet official-CSV evidence series."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Annotated, Any

import typer
from rich.console import Console

from constructionsight.ceqanet_csv_access_policy_models import (
    CeqanetCsvAccessPolicy,
    CeqanetCsvAccessPolicyVerification,
)
from constructionsight.ceqanet_csv_evidence_series_models import (
    CeqanetCsvEvidenceExecution,
    CeqanetCsvEvidenceSeries,
)
from constructionsight.ceqanet_csv_evidence_series_service import (
    EvidenceExecutionInput,
    build_ceqanet_csv_evidence_series,
    execute_ceqanet_csv_evidence_request,
    verify_ceqanet_csv_evidence_series,
)
from constructionsight.ceqanet_csv_live_models import CeqanetCsvLiveExecution
from constructionsight.ceqanet_csv_replay_models import (
    CeqanetCsvEncodingReplay,
    CeqanetCsvEncodingReplayVerification,
)
from constructionsight.ceqanet_csv_service import (
    build_ceqanet_csv_export_request,
)
from constructionsight.ceqanet_maturity_proposal_models import (
    CeqanetSourceMaturityProposal,
    CeqanetSourceMaturityProposalVerification,
)
from constructionsight.models import PublicSource
from constructionsight.storage.runtime_artifacts import read_runtime_text

app = typer.Typer(help="ConstructionSight governed CEQAnet CSV evidence series.")
console = Console()
PolicyContext = tuple[
    list[PublicSource],
    CeqanetCsvLiveExecution,
    CeqanetCsvEncodingReplay,
    CeqanetCsvEncodingReplayVerification,
    CeqanetSourceMaturityProposal,
    CeqanetSourceMaturityProposalVerification,
    CeqanetCsvAccessPolicy,
    CeqanetCsvAccessPolicyVerification,
]


def _load_json(path: Path) -> Any:
    return json.loads(read_runtime_text(path))


def _load_policy_context(
    registry_path: Path,
    original_execution_path: Path,
    replay_path: Path,
    replay_verification_path: Path,
    maturity_proposal_path: Path,
    maturity_verification_path: Path,
    policy_path: Path,
    policy_verification_path: Path,
) -> PolicyContext:
    registry_payload: Any = _load_json(registry_path)
    if not isinstance(registry_payload, list):
        raise ValueError("source registry JSON must be a list")
    return (
        [PublicSource.model_validate(item) for item in registry_payload],
        CeqanetCsvLiveExecution.model_validate(
            _load_json(original_execution_path)
        ),
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
        CeqanetCsvAccessPolicy.model_validate(_load_json(policy_path)),
        CeqanetCsvAccessPolicyVerification.model_validate(
            _load_json(policy_verification_path)
        ),
    )


def _load_evidence_executions(
    paths: list[Path] | None,
    artifact_refs: list[str] | None,
) -> list[EvidenceExecutionInput]:
    normalized_paths = paths or []
    normalized_refs = artifact_refs or []
    if len(normalized_paths) != len(normalized_refs):
        raise ValueError(
            "--evidence-execution and --artifact-ref counts must match"
        )
    return [
        (
            artifact_ref,
            CeqanetCsvEvidenceExecution.model_validate(_load_json(path)),
        )
        for artifact_ref, path in zip(
            normalized_refs,
            normalized_paths,
            strict=True,
        )
    ]


def _input_paths(
    registry_path: Path,
    original_execution_path: Path,
    replay_path: Path,
    replay_verification_path: Path,
    maturity_proposal_path: Path,
    maturity_verification_path: Path,
    policy_path: Path,
    policy_verification_path: Path,
    evidence_execution_paths: list[Path] | None,
    *additional: Path,
) -> tuple[Path, ...]:
    return (
        registry_path,
        original_execution_path,
        replay_path,
        replay_verification_path,
        maturity_proposal_path,
        maturity_verification_path,
        policy_path,
        policy_verification_path,
        *(evidence_execution_paths or []),
        *additional,
    )


def _require_output_available(
    output: Path,
    *,
    inputs: tuple[Path, ...],
    overwrite: bool,
) -> None:
    output_identity = output.resolve()
    if any(path.resolve() == output_identity for path in inputs):
        raise ValueError("output path must differ from every input path")
    if output.exists() and not overwrite:
        raise ValueError(
            f"output already exists: {output}; pass --overwrite to replace it"
        )
    output.parent.mkdir(parents=True, exist_ok=True)


def _write_json(
    output: Path,
    payload: object,
    *,
    inputs: tuple[Path, ...],
    overwrite: bool,
) -> None:
    _require_output_available(
        output,
        inputs=inputs,
        overwrite=overwrite,
    )
    rendered = json.dumps(payload, indent=2, sort_keys=True, default=str)
    temporary = output.with_name(f".{output.name}.tmp")
    temporary.write_text(f"{rendered}\n", encoding="utf-8")
    temporary.replace(output)


@app.callback()
def evidence_series_root() -> None:
    """ConstructionSight CEQAnet CSV evidence-series commands."""


@app.command("build")
def build_series(
    registry_path: Annotated[Path, typer.Argument(help="Current source registry.")],
    original_execution_path: Annotated[
        Path,
        typer.Argument(help="Canonical original live execution."),
    ],
    replay_path: Annotated[
        Path,
        typer.Argument(help="Canonical Windows-1252 replay."),
    ],
    replay_verification_path: Annotated[
        Path,
        typer.Argument(help="Canonical replay verification."),
    ],
    maturity_proposal_path: Annotated[
        Path,
        typer.Argument(help="Canonical keep-partial maturity proposal."),
    ],
    maturity_verification_path: Annotated[
        Path,
        typer.Argument(help="Canonical maturity verification."),
    ],
    policy_path: Annotated[
        Path,
        typer.Argument(help="Current CSV access policy."),
    ],
    policy_verification_path: Annotated[
        Path,
        typer.Argument(help="Current independent policy verification."),
    ],
    output: Annotated[
        Path,
        typer.Option("--output", help="Required evidence-series JSON output."),
    ],
    evidence_execution_paths: Annotated[
        list[Path] | None,
        typer.Option(
            "--evidence-execution",
            help="Complete policy-bound execution artifact; repeat as needed.",
        ),
    ] = None,
    artifact_refs: Annotated[
        list[str] | None,
        typer.Option(
            "--artifact-ref",
            help="Repo-relative artifact ref paired by order; repeat as needed.",
        ),
    ] = None,
    overwrite: Annotated[bool, typer.Option("--overwrite")] = False,
) -> None:
    """Build an immutable evidence-series snapshot without network access."""

    try:
        context = _load_policy_context(
            registry_path,
            original_execution_path,
            replay_path,
            replay_verification_path,
            maturity_proposal_path,
            maturity_verification_path,
            policy_path,
            policy_verification_path,
        )
        evidence_executions = _load_evidence_executions(
            evidence_execution_paths,
            artifact_refs,
        )
        series = build_ceqanet_csv_evidence_series(
            *context,
            evidence_executions,
        )
        _write_json(
            output,
            series.model_dump(mode="json"),
            inputs=_input_paths(
                registry_path,
                original_execution_path,
                replay_path,
                replay_verification_path,
                maturity_proposal_path,
                maturity_verification_path,
                policy_path,
                policy_verification_path,
                evidence_execution_paths,
            ),
            overwrite=overwrite,
        )
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        raise typer.BadParameter(str(exc)) from exc
    console.print(f"Wrote CEQAnet CSV evidence series to {output}")
    console.print(f"Series status: {series.status.value}")
    console.print(f"Series digest: {series.series_digest}")


@app.command("verify")
def verify_series(
    registry_path: Annotated[Path, typer.Argument(help="Current source registry.")],
    original_execution_path: Annotated[
        Path,
        typer.Argument(help="Canonical original live execution."),
    ],
    replay_path: Annotated[
        Path,
        typer.Argument(help="Canonical Windows-1252 replay."),
    ],
    replay_verification_path: Annotated[
        Path,
        typer.Argument(help="Canonical replay verification."),
    ],
    maturity_proposal_path: Annotated[
        Path,
        typer.Argument(help="Canonical keep-partial maturity proposal."),
    ],
    maturity_verification_path: Annotated[
        Path,
        typer.Argument(help="Canonical maturity verification."),
    ],
    policy_path: Annotated[
        Path,
        typer.Argument(help="Current CSV access policy."),
    ],
    policy_verification_path: Annotated[
        Path,
        typer.Argument(help="Current independent policy verification."),
    ],
    series_path: Annotated[
        Path,
        typer.Argument(help="Evidence-series JSON to verify."),
    ],
    output: Annotated[
        Path,
        typer.Option("--output", help="Required verification JSON output."),
    ],
    evidence_execution_paths: Annotated[
        list[Path] | None,
        typer.Option(
            "--evidence-execution",
            help="Complete policy-bound execution artifact; repeat as needed.",
        ),
    ] = None,
    artifact_refs: Annotated[
        list[str] | None,
        typer.Option(
            "--artifact-ref",
            help="Repo-relative artifact ref paired by order; repeat as needed.",
        ),
    ] = None,
    overwrite: Annotated[bool, typer.Option("--overwrite")] = False,
) -> None:
    """Independently verify a series without network access."""

    try:
        context = _load_policy_context(
            registry_path,
            original_execution_path,
            replay_path,
            replay_verification_path,
            maturity_proposal_path,
            maturity_verification_path,
            policy_path,
            policy_verification_path,
        )
        evidence_executions = _load_evidence_executions(
            evidence_execution_paths,
            artifact_refs,
        )
        series = CeqanetCsvEvidenceSeries.model_validate(
            _load_json(series_path)
        )
        verification = verify_ceqanet_csv_evidence_series(
            *context,
            evidence_executions,
            series,
        )
        _write_json(
            output,
            verification.model_dump(mode="json"),
            inputs=_input_paths(
                registry_path,
                original_execution_path,
                replay_path,
                replay_verification_path,
                maturity_proposal_path,
                maturity_verification_path,
                policy_path,
                policy_verification_path,
                evidence_execution_paths,
                series_path,
            ),
            overwrite=overwrite,
        )
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        raise typer.BadParameter(str(exc)) from exc
    console.print(f"Wrote CEQAnet CSV series verification to {output}")
    console.print(f"Verification passed: {verification.passed}")
    if not verification.passed:
        raise typer.Exit(code=1)


@app.command("execute")
def execute_evidence(
    registry_path: Annotated[Path, typer.Argument(help="Current source registry.")],
    original_execution_path: Annotated[
        Path,
        typer.Argument(help="Canonical original live execution."),
    ],
    replay_path: Annotated[
        Path,
        typer.Argument(help="Canonical Windows-1252 replay."),
    ],
    replay_verification_path: Annotated[
        Path,
        typer.Argument(help="Canonical replay verification."),
    ],
    maturity_proposal_path: Annotated[
        Path,
        typer.Argument(help="Canonical keep-partial maturity proposal."),
    ],
    maturity_verification_path: Annotated[
        Path,
        typer.Argument(help="Canonical maturity verification."),
    ],
    policy_path: Annotated[
        Path,
        typer.Argument(help="Current CSV access policy."),
    ],
    policy_verification_path: Annotated[
        Path,
        typer.Argument(help="Current independent policy verification."),
    ],
    series_path: Annotated[
        Path,
        typer.Argument(help="Current independently verifiable series."),
    ],
    sch_number: Annotated[
        str,
        typer.Option("--sch-number", help="Exact 10-digit SCH number."),
    ],
    output: Annotated[
        Path,
        typer.Option("--output", help="Required evidence-execution output."),
    ],
    document_id: Annotated[
        int | None,
        typer.Option("--document-id", min=1),
    ] = None,
    evidence_execution_paths: Annotated[
        list[Path] | None,
        typer.Option(
            "--evidence-execution",
            help="Prior execution artifact; repeat as needed.",
        ),
    ] = None,
    artifact_refs: Annotated[
        list[str] | None,
        typer.Option(
            "--artifact-ref",
            help="Prior repo-relative artifact ref; repeat as needed.",
        ),
    ] = None,
    execute_live: Annotated[
        bool,
        typer.Option(
            "--execute-live",
            help="Explicitly authorize one policy-bound public GET.",
        ),
    ] = False,
    max_retained_rows: Annotated[
        int,
        typer.Option("--max-retained-rows", min=0, max=1_000),
    ] = 1_000,
    overwrite: Annotated[bool, typer.Option("--overwrite")] = False,
) -> None:
    """Execute one governed request after full policy and ledger verification."""

    if not execute_live:
        raise typer.BadParameter(
            "explicit --execute-live authorization is required"
        )
    try:
        context = _load_policy_context(
            registry_path,
            original_execution_path,
            replay_path,
            replay_verification_path,
            maturity_proposal_path,
            maturity_verification_path,
            policy_path,
            policy_verification_path,
        )
        evidence_executions = _load_evidence_executions(
            evidence_execution_paths,
            artifact_refs,
        )
        series = CeqanetCsvEvidenceSeries.model_validate(
            _load_json(series_path)
        )
        request = build_ceqanet_csv_export_request(
            sch_number=sch_number,
            document_id=document_id,
        )
        inputs = _input_paths(
            registry_path,
            original_execution_path,
            replay_path,
            replay_verification_path,
            maturity_proposal_path,
            maturity_verification_path,
            policy_path,
            policy_verification_path,
            evidence_execution_paths,
            series_path,
        )
        _require_output_available(
            output,
            inputs=inputs,
            overwrite=overwrite,
        )
        execution = execute_ceqanet_csv_evidence_request(
            *context,
            series,
            evidence_executions,
            request,
            execute_live=True,
            max_retained_rows=max_retained_rows,
        )
        _write_json(
            output,
            execution.model_dump(mode="json"),
            inputs=inputs,
            overwrite=overwrite,
        )
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        raise typer.BadParameter(str(exc)) from exc
    console.print(f"Wrote CEQAnet CSV evidence execution to {output}")
    console.print(
        f"Independent live verification passed: "
        f"{execution.live_verification.passed}"
    )
    if not execution.live_verification.passed:
        raise typer.Exit(code=1)
