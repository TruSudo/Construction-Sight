from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from pydantic import ValidationError
from sqlalchemy import func, select

import constructionsight.ceqanet_persistence_execute as ceqanet_persistence_execute
import constructionsight.result_authority_service as result_authority_service
from constructionsight.authorization_decision import (
    AuthorizationDeniedError,
    AuthorizationUseLedger,
    authorize_and_claim,
    build_authorization_decision,
)
from constructionsight.authorization_decision_models import (
    AuthorizationDecision,
    AuthorizationReusePolicy,
)
from constructionsight.lead_dedupe_models import LeadDuplicateStatus
from constructionsight.lead_dedupe_service import (
    build_lead_fingerprint,
    check_lead_duplicate,
)
from constructionsight.lead_review_models import LeadReviewPackage, LeadReviewStatus
from constructionsight.lead_workflow_models import (
    LeadWorkflowEvent,
    LeadWorkflowRecord,
    LeadWorkflowStatus,
)
from constructionsight.result_ledger_models import ResultLedgerStatus
from constructionsight.storage.database import (
    create_database_engine,
    initialize_database,
    managed_session,
    session_factory,
)
from constructionsight.storage.domain_orm import EntityRecord, SiteRecord
from constructionsight.storage.lead_workflow_orm import ResultLedgerRecordRow
from constructionsight.storage.lead_workflow_store import store_lead_workflow_record
from constructionsight.storage.result_authority_orm import (
    ResultAuthorityEventRow,
    ResultAuthorityHeadRow,
)


def _authorization_decision() -> AuthorizationDecision:
    issued_at = datetime(2026, 7, 15, 12, 0, tzinfo=UTC)
    return build_authorization_decision(
        actor_id="operator:tyler",
        action="apply-status",
        resource_type="source-record",
        resource_id="source:county-parcel",
        exact_scope=("field:status", "transition:verified-candidate"),
        current_state_identity="state:abc123",
        expected_identity="state:abc123",
        granted_authority=("apply exact status transition",),
        denied_authority=("expand field scope",),
        reason="Apply the independently reviewed exact status transition.",
        issued_at=issued_at,
        not_before=issued_at,
        expires_at=issued_at + timedelta(minutes=15),
        reuse_policy=AuthorizationReusePolicy.SINGLE_USE,
        revocation_identity="revocation:none:v1",
        audit_identity="audit:status-transition:v1",
        caller_confirmation=True,
        limitations=("test-only local authority",),
    )


def _workflow() -> LeadWorkflowRecord:
    status = LeadWorkflowStatus.READY
    return LeadWorkflowRecord(
        workflow_id="lead-workflow:semantic-witness",
        package_id="lead-review:semantic-witness",
        base_candidate_id="candidate:semantic-witness",
        status=status,
        lead_score=88,
        events=[
            LeadWorkflowEvent(
                event_id="lead-workflow-event:semantic-witness",
                current_status=status,
                reason="semantic witness fixture",
            )
        ],
    )


def _review_package(candidate_id: str) -> LeadReviewPackage:
    return LeadReviewPackage(
        package_id=f"lead-review:{candidate_id}",
        base_candidate_id=candidate_id,
        lead_score=80,
        status=LeadReviewStatus.MONITOR,
        summary="semantic witness package",
    )


def _write_plan() -> dict[str, object]:
    return {
        "metadata": {
            "schema_version": "ceqanet_write_plan.v1",
            "operation_count": 2,
            "skipped_item_count": 0,
            "network_executed": False,
            "database_opened": False,
            "persistence_mutated": False,
        },
        "operations": [
            {
                "operation_id": "sites:site:semantic-witness",
                "action": "upsert_preview",
                "target_collection": "sites",
                "target_key": "site:semantic-witness",
                "source_index": 0,
                "payload": {
                    "site_key": "site:semantic-witness",
                    "county": "San Bernardino",
                    "city": "Redlands",
                },
            },
            {
                "operation_id": "entities:entity:semantic-witness",
                "action": "upsert_preview",
                "target_collection": "entities",
                "target_key": "entity:semantic-witness",
                "source_index": 0,
                "payload": {
                    "entity_key": "entity:semantic-witness",
                    "name": "Semantic Witness Entity",
                    "role": "agency",
                    "county": "San Bernardino",
                },
            },
        ],
        "skipped_items": [],
    }


def test_result_audit_failure_rolls_back_authoritative_transaction(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    database_url = f"sqlite:///{tmp_path / 'audit-rollback.sqlite3'}"
    engine = create_database_engine(database_url)
    initialize_database(engine)
    factory = session_factory(engine)
    with managed_session(factory) as session:
        store_lead_workflow_record(session, _workflow())

    def fail_audit_event(*_args: object, **_kwargs: object) -> None:
        raise ValueError("audit unavailable")

    monkeypatch.setattr(
        result_authority_service,
        "store_result_authority_event",
        fail_audit_event,
    )
    with managed_session(factory) as session:
        with pytest.raises(
            result_authority_service.ResultAuthorityError,
            match="audit unavailable",
        ):
            result_authority_service.apply_authoritative_result(
                session,
                workflow_id=_workflow().workflow_id,
                expected_current_ledger_id=None,
                status=ResultLedgerStatus.UNKNOWN,
                authority_reason="semantic witness audit rollback",
            )

    with managed_session(factory) as session:
        assert session.scalar(select(func.count()).select_from(ResultLedgerRecordRow)) == 0
        assert session.scalar(select(func.count()).select_from(ResultAuthorityHeadRow)) == 0
        assert session.scalar(select(func.count()).select_from(ResultAuthorityEventRow)) == 0


def test_duplicate_result_identity_is_order_independent() -> None:
    candidate = build_lead_fingerprint(
        package=_review_package("candidate:new"),
        site_key="site:shared",
        source_key="permit:new",
        source_record_id="new",
        title="New Warehouse",
    )
    first = build_lead_fingerprint(
        package=_review_package("candidate:first"),
        site_key="site:shared",
        source_key="permit:first",
        source_record_id="first",
        title="First Warehouse",
    )
    second = build_lead_fingerprint(
        package=_review_package("candidate:second"),
        site_key="site:shared",
        source_key="permit:second",
        source_record_id="second",
        title="Second Warehouse",
    )

    forward = check_lead_duplicate(candidate, [first, second])
    reversed_result = check_lead_duplicate(candidate, [second, first])

    assert forward.status == LeadDuplicateStatus.REVIEW_NEEDED
    assert reversed_result.status == LeadDuplicateStatus.REVIEW_NEEDED
    assert forward.result_id == reversed_result.result_id


def test_authorization_decision_rejects_unknown_extra_fields() -> None:
    payload = _authorization_decision().model_dump(mode="python")
    payload["unexpected"] = True

    with pytest.raises(ValidationError) as exc_info:
        AuthorizationDecision.model_validate(payload)

    assert any(error["type"] == "extra_forbidden" for error in exc_info.value.errors())


def test_authorization_decision_rejects_malformed_identity_schema() -> None:
    payload = _authorization_decision().model_dump(mode="python")
    payload["decision_id"] = "malformed"

    with pytest.raises(ValidationError) as exc_info:
        AuthorizationDecision.model_validate(payload)

    assert any(
        error["type"] == "string_pattern_mismatch"
        for error in exc_info.value.errors()
    )


def test_mid_transaction_failure_rolls_back_partial_writes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    engine = create_database_engine("sqlite+pysqlite:///:memory:")
    initialize_database(engine)
    original_apply = ceqanet_persistence_execute._apply_prepared_operation
    calls = 0

    def interrupted_apply(*args: object, **kwargs: object) -> None:
        nonlocal calls
        calls += 1
        if calls == 2:
            raise RuntimeError("interrupted")
        original_apply(*args, **kwargs)

    monkeypatch.setattr(
        ceqanet_persistence_execute,
        "_apply_prepared_operation",
        interrupted_apply,
    )

    with pytest.raises(ValueError, match="rolled back"):
        ceqanet_persistence_execute.execute_ceqanet_write_plan(
            _write_plan(),
            engine=engine,
            initialize=False,
        )

    with engine.connect() as connection:
        assert connection.scalar(select(func.count()).select_from(SiteRecord)) == 0
        assert connection.scalar(select(func.count()).select_from(EntityRecord)) == 0


def test_preflight_rejects_naive_checked_at() -> None:
    decision = _authorization_decision()

    with pytest.raises(AuthorizationDeniedError, match="preflight time must be aware"):
        authorize_and_claim(
            decision,
            actor_id=decision.actor_id,
            action=decision.action,
            resource_type=decision.resource_type,
            resource_id=decision.resource_id,
            exact_scope=decision.exact_scope,
            current_state_identity=decision.expected_identity,
            current_revocation_identity=decision.revocation_identity,
            replay_identity="result:semantic-witness",
            checked_at=datetime(2026, 7, 15, 12, 5),
            ledger=AuthorizationUseLedger(),
        )
