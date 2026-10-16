"""Explicit, evidence-bound local review of investigation associations.

Associations group source context for investigation. They never independently
verify identity, erase source IDs, or authorize commercial action.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from sqlalchemy import Engine

from constructionsight.authorization_decision import AuthorizationDeniedError
from constructionsight.effect_consumption import _execute_owned_effect
from constructionsight.effect_consumption_models import EffectReplayPolicy
from constructionsight.intelligence.graph_service import IntelligenceGraphService
from constructionsight.intelligence.investigation_service import _identity
from constructionsight.intelligence.relationship_query_service import canonical_investigation_id
from constructionsight.intelligence.schemas import (
    RelationshipAssertion,
    RelationshipStatus,
    RuntimeEvent,
    RuntimeEventType,
)
from constructionsight.local_operator_authorization import authorize_local_operator_operation
from constructionsight.storage.database import (
    ensure_database_transaction,
    managed_session,
    session_factory,
)
from constructionsight.storage.intelligence_store import IntelligenceStore


class InvestigationReviewService:
    def __init__(self, engine: Engine) -> None:
        self.factory = session_factory(engine)

    @staticmethod
    def _load(
        store: IntelligenceStore,
        relationship_id: str,
    ) -> tuple[RelationshipAssertion, str, list[RelationshipAssertion]]:
        ensure_database_transaction(store.session)
        relation = store.get_relationship(relationship_id)
        if relation is None or relation.predicate != "possible_same_project_requires_review":
            raise ValueError("review requires an existing identity candidate relationship")
        clusters = [
            store.get_project_cluster(identity)
            for identity in (relation.subject_entity_id, relation.object_entity_id)
        ]
        if any(cluster is None for cluster in clusters):
            raise ValueError("candidate references a missing investigation")
        adjacent = {
            r.relationship_id: r
            for cluster in clusters
            if cluster is not None
            for r in store.list_relationships_for_target(cluster.project_cluster_id)
        }
        state = {
            "candidate": relation.model_dump(mode="json"),
            "investigations": [c.model_dump(mode="json") for c in clusters if c is not None],
            "context": [
                r.model_dump(mode="json")
                for r in sorted(adjacent.values(), key=lambda item: item.relationship_id)
                if r.predicate in {"reviewed_investigation_alias", "reviewed_source_context"}
            ],
        }
        return relation, _identity("investigation-review-state", state), list(adjacent.values())

    def preview(self, relationship_id: str) -> dict[str, Any]:
        with managed_session(self.factory) as session:
            relation, state, _ = self._load(IntelligenceStore(session), relationship_id)
            return {
                "review_applied": False,
                "relationship": relation.model_dump(mode="json"),
                "expected_identity": state,
                "target_choices": [relation.subject_entity_id, relation.object_entity_id],
                "identity_independently_verified": False,
                "limitations": [
                    "Association records reviewed source context, not independent verification.",
                    "No source record, evidence or original investigation is deleted.",
                ],
            }

    def review(
        self,
        relationship_id: str,
        *,
        decision: Literal["associate", "reject"],
        target_id: str | None,
        expected_identity: str,
        reason: str,
        caller_confirmation: bool,
        operator_id: str | None = None,
    ) -> dict[str, Any]:
        if decision not in {"associate", "reject"}:
            raise ValueError("unknown investigation review decision")
        if decision == "reject" and target_id is not None:
            raise ValueError("rejection does not select a target investigation")
        if not reason.strip() or len(reason) > 4000:
            raise ValueError("review requires a nonblank reason of at most 4000 characters")
        with managed_session(self.factory) as session:
            store = IntelligenceStore(session)
            relation, state, _ = self._load(store, relationship_id)
            if state != expected_identity:
                raise AuthorizationDeniedError("candidate changed; refresh the review preview")
            choices = {relation.subject_entity_id, relation.object_entity_id}
            if decision == "associate" and target_id not in choices:
                raise ValueError("target must be one of the reviewed candidate investigations")
            if (
                decision == "associate"
                and canonical_investigation_id(store, str(target_id)) != target_id
            ):
                raise ValueError(
                    "choose the current canonical investigation or reject the old association"
                )
        authorization = authorize_local_operator_operation(
            action="review-investigation-association",
            resource_type="investigation-candidate",
            resource_id=relationship_id,
            exact_scope=(decision, target_id or "no-target", state),
            current_state_identity=state,
            expected_identity=expected_identity,
            granted_authority=("record reviewed source association or rejection",),
            denied_authority=(
                "verify project identity",
                "erase source records",
                "send outreach",
                "submit bids",
                "change commercial readiness",
            ),
            reason=reason,
            caller_confirmation=caller_confirmation,
            operator_id=operator_id,
            limitations=(
                "Local operator identity is an audit identity, not authentication.",
                "No independent identity verification or commercial authority is granted.",
            ),
        )

        def apply(trusted_at: datetime) -> dict[str, Any]:
            with managed_session(self.factory) as session:
                store = IntelligenceStore(session)
                current, actual, adjacent = self._load(store, relationship_id)
                if actual != expected_identity:
                    raise AuthorizationDeniedError(
                        "candidate changed after review; refresh the preview"
                    )
                graph = IntelligenceGraphService(store, source_service="investigation_review")
                review_id = _identity(
                    "event:investigation-review",
                    {
                        "decision_id": authorization.decision.decision_id,
                        "relationship_id": relationship_id,
                    },
                )
                desired: list[RelationshipAssertion] = []
                if decision == "associate":
                    assert target_id is not None
                    other = (
                        current.object_entity_id
                        if target_id == current.subject_entity_id
                        else current.subject_entity_id
                    )
                    other_canonical = canonical_investigation_id(store, other)
                    if other_canonical not in {other, target_id}:
                        raise AuthorizationDeniedError(
                            "source already belongs to a different reviewed context"
                        )
                    evidence_ids = sorted(
                        set(current.supporting_evidence_ids + current.contradictory_evidence_ids)
                    )
                    desired.append(
                        RelationshipAssertion(
                            relationship_id=_identity(
                                "relationship:reviewed-alias", relationship_id
                            ),
                            subject_entity_id=other,
                            object_entity_id=target_id,
                            predicate="reviewed_investigation_alias",
                            relationship_status=RelationshipStatus.PROBABLE,
                            supporting_evidence_ids=evidence_ids,
                            enrichment_run_id=relationship_id,
                            evidence_summary="Reviewed context; identity unverified.",
                            first_seen=trusted_at,
                            last_seen=trusted_at,
                        )
                    )
                    for source in adjacent:
                        if (
                            source.object_entity_id == other
                            and source.predicate
                            in {
                                "source_record_for_unresolved_investigation",
                                "reviewed_source_context",
                            }
                            and source.relationship_status
                            not in {RelationshipStatus.SUPERSEDED, RelationshipStatus.REJECTED}
                        ):
                            desired.append(
                                RelationshipAssertion(
                                    relationship_id=_identity(
                                        "relationship:reviewed-context",
                                        [relationship_id, source.subject_entity_id, target_id],
                                    ),
                                    subject_entity_id=source.subject_entity_id,
                                    object_entity_id=target_id,
                                    predicate="reviewed_source_context",
                                    relationship_status=RelationshipStatus.PROBABLE,
                                    supporting_evidence_ids=evidence_ids,
                                    enrichment_run_id=relationship_id,
                                    evidence_summary="Reviewed context; identity unverified.",
                                    first_seen=trusted_at,
                                    last_seen=trusted_at,
                                )
                            )
                desired_ids = {r.relationship_id for r in desired}
                for old in adjacent:
                    if (
                        old.enrichment_run_id == relationship_id
                        and old.predicate
                        in {"reviewed_investigation_alias", "reviewed_source_context"}
                        and old.relationship_id not in desired_ids
                        and old.relationship_status is not RelationshipStatus.SUPERSEDED
                    ):
                        graph.upsert_relationship(
                            old.model_copy(
                                update={
                                    "relationship_status": RelationshipStatus.SUPERSEDED,
                                    "last_seen": trusted_at,
                                }
                            )
                        )
                for row in desired:
                    prior_row = store.get_relationship(row.relationship_id)
                    if prior_row is not None:
                        row = row.model_copy(update={"first_seen": prior_row.first_seen})
                    graph.upsert_relationship(row)
                updated = current.model_copy(
                    update={
                        "relationship_status": (
                            RelationshipStatus.PROBABLE
                            if decision == "associate"
                            else RelationshipStatus.REJECTED
                        ),
                        "enrichment_run_id": review_id,
                        "last_seen": trusted_at,
                    }
                )
                graph.upsert_relationship(updated)
                source_revisions = {}
                for row in adjacent + desired:
                    if row.predicate in {
                        "source_record_for_unresolved_investigation",
                        "reviewed_source_context",
                    }:
                        entity = store.get_entity(row.subject_entity_id)
                        if entity is not None:
                            source_revisions[entity.entity_id] = entity.evidence_record_ids
                result = {
                    "review_applied": True,
                    "review_event_id": review_id,
                    "relationship_id": relationship_id,
                    "decision": decision,
                    "target_id": target_id if decision == "associate" else None,
                    "identity_independently_verified": False,
                    "commercial_authority_granted": False,
                }
                store.add_runtime_event(
                    RuntimeEvent(
                        event_id=review_id,
                        event_type=RuntimeEventType.RELATIONSHIP_UPDATED,
                        source_service="investigation_identity_review",
                        created_at=trusted_at,
                        project_cluster_refs=sorted(choices),
                        source_record_refs=current.supporting_evidence_ids,
                        payload={
                            **result,
                            "reason": reason,
                            "authorization": authorization.to_dict(),
                            "source_revisions": source_revisions,
                            "previous_relationship": current.model_dump(mode="json"),
                            "current_relationship": updated.model_dump(mode="json"),
                        },
                        message="Association review committed; identity remains unverified.",
                    )
                )
            return result

        return _execute_owned_effect(
            authorization,
            allowance_identity=expected_identity,
            content_identity=_identity(
                "investigation-review-request", [decision, target_id, reason]
            ),
            implementation_id="constructionsight.intelligence.investigation_review_service.review",
            replay_policy=EffectReplayPolicy.DENY,
            effect=apply,
            encode_result=lambda value: value,
            decode_result=lambda value: dict(value),
        )
