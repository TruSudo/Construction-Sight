"""Parcel-backed location assessment using the existing resolver and stores."""

from __future__ import annotations

from constructionsight.intelligence.artifact_identity import IdentityArtifactType as Artifact
from constructionsight.intelligence.investigation_service import InvestigationService, _identity
from constructionsight.intelligence.investigation_sources import from_parcel
from constructionsight.intelligence.schemas import (
    RelationshipAssertion,
    RelationshipStatus,
    RuntimeEvent,
    RuntimeEventType,
)
from constructionsight.parcel_core_models import ParcelCoreRecord
from constructionsight.parcel_site_resolution import resolve_site_with_parcels
from constructionsight.site_resolution_models import (
    GeometryHint,
    GeometryHintKind,
    SiteIdentifier,
    SiteIdentifierKind,
    SiteResolutionInput,
    SiteResolutionResult,
)
from constructionsight.site_resolution_service import normalize_address, normalize_apn
from constructionsight.storage.database import ensure_database_transaction
from constructionsight.storage.intelligence_store import IntelligenceStore
from constructionsight.storage.parcel_site_store import store_site_resolution_result


class InvestigationLocationService:
    def __init__(self, store: IntelligenceStore) -> None:
        self.store = store
        self.investigations = InvestigationService(store)

    def resolve(
        self,
        source_id: str,
        parcels: list[ParcelCoreRecord],
    ) -> SiteResolutionResult:
        """Assess a bounded retained parcel pool; never assert verified project identity."""
        if len(parcels) > 1000:
            raise ValueError("parcel assessment requires at most 1000 retained inputs")
        ensure_database_transaction(self.store.session)
        observation = self.investigations.current_observation(source_id)
        if not observation.county or not observation.county.strip():
            raise ValueError("parcel assessment requires an explicitly known county")
        parcels = [
            ParcelCoreRecord.model_validate(item.model_dump(round_trip=True)) for item in parcels
        ]
        parcel_inputs = sorted(
            _identity("parcel-input", parcel.model_dump(mode="json", round_trip=True))
            for parcel in parcels
        )
        event_id = _identity(
            "event:investigation-location", [observation.receipt_id, parcel_inputs]
        )
        existing = self.store.get_runtime_event(event_id)
        if existing is not None:
            return SiteResolutionResult.model_validate(existing.payload["result"])
        identifiers = []
        for artifact, kind, normalize in (
            (Artifact.APN, SiteIdentifierKind.APN, normalize_apn),
            (Artifact.EXACT_SITE_ADDRESS, SiteIdentifierKind.ADDRESS, normalize_address),
        ):
            seen = set()
            for value in observation.artifacts.get(artifact, []):
                normalized = normalize(value)
                if not normalized or normalized in seen:
                    continue
                seen.add(normalized)
                identifiers.append(
                    SiteIdentifier(
                        identifier_kind=kind,
                        value=value,
                        normalized_value=normalized,
                        evidence_id=observation.evidence.evidence_id,
                    )
                )
        geometry = []
        if observation.latitude is not None and observation.longitude is not None:
            geometry.append(
                GeometryHint(
                    geometry_kind=GeometryHintKind.POINT,
                    latitude=observation.latitude,
                    longitude=observation.longitude,
                    source_name=observation.evidence.source_name,
                    evidence_id=observation.evidence.evidence_id,
                )
            )
        site_input = SiteResolutionInput(
            source_name=observation.evidence.source_name,
            evidence_id=observation.evidence.evidence_id,
            identifiers=identifiers,
            geometry_hints=geometry,
            source_hints={"county": observation.county},
        )
        result = resolve_site_with_parcels(site_input, parcels)
        county = " ".join(observation.county.casefold().split()).removesuffix(" county")
        supported_apns = {
            normalize_apn(candidate.apn) for candidate in result.candidates if candidate.apn
        }
        evidence_ids = [observation.evidence.evidence_id]
        with self.store.session.begin_nested():
            for parcel in parcels:
                parcel_county = " ".join(parcel.county.casefold().split()).removesuffix(" county")
                if parcel_county != county or parcel.normalized_apn not in supported_apns:
                    continue
                retained_parcel = from_parcel(parcel)
                self.investigations.ingest(retained_parcel)
                evidence_ids.append(retained_parcel.evidence.evidence_id)
                self.investigations.graph.upsert_relationship(
                    RelationshipAssertion(
                        relationship_id=_identity(
                            "relationship:parcel-location-candidate",
                            [
                                observation.investigation_id,
                                retained_parcel.source_entity_id,
                                result.resolution_id,
                            ],
                        ),
                        subject_entity_id=retained_parcel.source_entity_id,
                        object_entity_id=observation.investigation_id,
                        predicate="parcel_location_candidate",
                        relationship_status=RelationshipStatus.POSSIBLE,
                        supporting_evidence_ids=[
                            observation.evidence.evidence_id,
                            retained_parcel.evidence.evidence_id,
                        ],
                        evidence_summary="Parcel location candidate; project identity unverified.",
                        enrichment_run_id=result.resolution_id,
                    )
                )
            store_site_resolution_result(self.store.session, result)
            self.store.add_runtime_event(
                RuntimeEvent(
                    event_id=event_id,
                    event_type=RuntimeEventType.RELATIONSHIP_UPDATED,
                    source_service="investigation_parcel_resolution",
                    project_cluster_refs=[observation.investigation_id],
                    source_record_refs=sorted(set(evidence_ids)),
                    payload={
                        "result": result.model_dump(mode="json"),
                        "input_parcel_digests": parcel_inputs,
                        "candidate_pool_complete": False,
                        "project_identity_verified": False,
                    },
                    message="Retained parcel assessment recorded; project identity unverified.",
                )
            )
            source_entity = self.store.get_entity(source_id)
            if source_entity is None:
                raise ValueError("location assessment lost its source identity")
            self.investigations.graph.upsert_entity(
                source_entity.model_copy(
                    update={
                        "identifiers": {
                            **source_entity.identifiers,
                            "current_location_assessment": event_id,
                        },
                    }
                )
            )
        return result
