"""Authorized persistence boundaries for legacy source-registry workflows."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from constructionsight.authorization_decision_models import authorization_digest
from constructionsight.effect_consumption import _execute_owned_effect
from constructionsight.effect_consumption_models import EffectReplayPolicy
from constructionsight.local_operator_authorization import (
    LocalAuthorizationResult,
    authorize_local_operator_operation,
)
from constructionsight.models import PublicSource, SourceVerificationResult
from constructionsight.source_registry_integrity import source_registry_digest
from constructionsight.storage.source_registry import SourceRegistryStore
from constructionsight.storage.verification_store import VerificationStore


class SourceRegistryPersistenceReport(BaseModel):
    processed_count: int = Field(ge=0)
    desired_registry_digest: str = Field(pattern=r"^[0-9a-f]{64}$")


class SourceVerificationPersistenceReport(BaseModel):
    verification_id: int = Field(ge=1)
    source_id: int | None
    source_name: str = Field(min_length=1)
    checked_at: datetime
    result_digest: str = Field(pattern=r"^source-verification-result:[0-9a-f]{64}$")


@dataclass(frozen=True)
class AuthorizedSourceRegistryPersistenceResult:
    report: SourceRegistryPersistenceReport
    authorization: LocalAuthorizationResult


@dataclass(frozen=True)
class AuthorizedSourceVerificationPersistenceResult:
    report: SourceVerificationPersistenceReport
    authorization: LocalAuthorizationResult


def _canonical_sources(sources: list[PublicSource]) -> list[PublicSource]:
    keys = [(source.source_name, str(source.public_url)) for source in sources]
    if len(keys) != len(set(keys)):
        raise ValueError("source registry persistence requires unique name/URL pairs")
    return sorted(
        sources,
        key=lambda source: (source.source_name.casefold(), str(source.public_url)),
    )


def persist_authorized_source_registry_records(
    session: Session,
    sources: list[PublicSource],
    *,
    caller_confirmation: bool,
    authorization_reason: str,
    operator_id: str | None = None,
) -> AuthorizedSourceRegistryPersistenceResult:
    """Authorize and persist one exact set of source-registry record upserts."""

    desired = _canonical_sources(sources)
    store = SourceRegistryStore(session)
    current = _canonical_sources(store.list_sources())
    current_digest = source_registry_digest(current)
    desired_digest = source_registry_digest(desired)
    state_identity = authorization_digest(
        "source-registry-persistence-state",
        {
            "current_registry_digest": current_digest,
            "desired_registry_digest": desired_digest,
            "desired_source_count": len(desired),
        },
    )
    resource_id = authorization_digest(
        "source-registry-persistence-resource",
        {
            "desired_registry_digest": desired_digest,
            "desired_source_count": len(desired),
        },
    )
    authorization = authorize_local_operator_operation(
        action="persist-source-registry-records",
        resource_type="primary-source-registry",
        resource_id=resource_id,
        exact_scope=tuple(
            sorted(
                {
                    f"current-registry-digest:{current_digest}",
                    f"desired-registry-digest:{desired_digest}",
                    f"source-count:{len(desired)}",
                    "write-mode:exact-upsert-set",
                },
                key=str.casefold,
            )
        ),
        current_state_identity=state_identity,
        expected_identity=state_identity,
        granted_authority=("persist the exact reviewed source-registry records",),
        denied_authority=tuple(
            sorted(
                {
                    "automatic source deletion",
                    "generic database editing",
                    "network execution",
                    "outreach sending",
                    "unreviewed source substitution",
                },
                key=str.casefold,
            )
        ),
        reason=authorization_reason,
        caller_confirmation=caller_confirmation,
        limitations=tuple(
            sorted(
                {
                    "records absent from the supplied set are not deleted",
                    "registry import does not authorize source verification",
                    "one durable exact-state allowance across processes",
                },
                key=str.casefold,
            )
        ),
        operator_id=operator_id,
        current_revocation_identity=state_identity,
    )

    def execute(_trusted_at: datetime) -> SourceRegistryPersistenceReport:
        processed = store.upsert_many(desired)
        session.commit()
        return SourceRegistryPersistenceReport(
            processed_count=processed,
            desired_registry_digest=desired_digest,
        )

    report = _execute_owned_effect(
        authorization,
        allowance_identity=authorization_digest(
            "source-registry-persistence-allowance",
            {
                "resource_id": resource_id,
                "state_identity": state_identity,
            },
        ),
        content_identity=desired_digest,
        implementation_id=(
            "constructionsight.storage.source_registry.SourceRegistryStore.upsert_many"
        ),
        replay_policy=EffectReplayPolicy.EXACT,
        effect=execute,
        encode_result=lambda result: result.model_dump(mode="json"),
        decode_result=lambda payload: SourceRegistryPersistenceReport.model_validate(payload),
    )
    return AuthorizedSourceRegistryPersistenceResult(
        report=report,
        authorization=authorization,
    )


def persist_authorized_source_verification_result(
    session: Session,
    result: SourceVerificationResult,
    *,
    caller_confirmation: bool,
    authorization_reason: str,
    operator_id: str | None = None,
) -> AuthorizedSourceVerificationPersistenceResult:
    """Authorize one append-only retained source-verification evidence record."""

    store = SourceRegistryStore(session)
    current_source = next(
        (
            source
            for source in store.list_sources()
            if source.source_name == result.source_name
            and str(source.public_url) == str(result.public_url)
        ),
        None,
    )
    result_digest = authorization_digest(
        "source-verification-result",
        result.model_dump(mode="json"),
    )
    state_identity = authorization_digest(
        "source-verification-persistence-state",
        {
            "source": (
                current_source.model_dump(mode="json")
                if current_source is not None
                else None
            ),
            "result_digest": result_digest,
        },
    )
    resource_id = authorization_digest(
        "source-verification-persistence-resource",
        {
            "source_name": result.source_name,
            "public_url": str(result.public_url),
            "checked_at": result.checked_at.isoformat(),
        },
    )
    authorization = authorize_local_operator_operation(
        action="persist-source-verification-evidence",
        resource_type="source-verification-evidence",
        resource_id=resource_id,
        exact_scope=tuple(
            sorted(
                {
                    "append-only:true",
                    f"result-digest:{result_digest}",
                    f"source-name:{result.source_name}",
                    f"source-url:{result.public_url}",
                },
                key=str.casefold,
            )
        ),
        current_state_identity=state_identity,
        expected_identity=state_identity,
        granted_authority=("append one exact source-verification evidence record",),
        denied_authority=tuple(
            sorted(
                {
                    "generic database editing",
                    "network execution",
                    "source confidence mutation",
                    "source status mutation",
                    "source identity mutation",
                },
                key=str.casefold,
            )
        ),
        reason=authorization_reason,
        caller_confirmation=caller_confirmation,
        limitations=tuple(
            sorted(
                {
                    "verification evidence does not itself authorize registry status changes",
                    "one durable exact-evidence allowance across processes",
                },
                key=str.casefold,
            )
        ),
        operator_id=operator_id,
        current_revocation_identity=state_identity,
    )

    def execute(_trusted_at: datetime) -> SourceVerificationPersistenceReport:
        record = VerificationStore(session).add_result(result)
        session.commit()
        if record.id is None:
            raise RuntimeError("verification evidence persistence did not assign an ID")
        return SourceVerificationPersistenceReport(
            verification_id=record.id,
            source_id=record.source_id,
            source_name=record.source_name,
            checked_at=record.checked_at,
            result_digest=result_digest,
        )

    report = _execute_owned_effect(
        authorization,
        allowance_identity=authorization_digest(
            "source-verification-persistence-allowance",
            {
                "resource_id": resource_id,
                "result_digest": result_digest,
            },
        ),
        content_identity=result_digest,
        implementation_id=(
            "constructionsight.storage.verification_store.VerificationStore.add_result"
        ),
        replay_policy=EffectReplayPolicy.EXACT,
        effect=execute,
        encode_result=lambda persisted: persisted.model_dump(mode="json"),
        decode_result=lambda payload: SourceVerificationPersistenceReport.model_validate(payload),
    )
    return AuthorizedSourceVerificationPersistenceResult(
        report=report,
        authorization=authorization,
    )
