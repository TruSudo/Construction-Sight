"""Relationship query service for ConstructionSight intelligence records.

This read-only service composes persisted intelligence records into useful graph
queries for future GUI views, CLI inspection commands, and enrichment services.
"""

from __future__ import annotations

from constructionsight.intelligence.schemas import (
    EntityIdentity,
    OpportunitySignal,
    ProjectCluster,
    RelationshipAssertion,
)
from constructionsight.storage.intelligence_store import IntelligenceStore


class RelationshipQueryService:
    """Read-only graph query service over persisted intelligence records."""

    def __init__(self, store: IntelligenceStore) -> None:
        self.store = store

    def get_relationships_for_entity(self, entity_id: str) -> list[RelationshipAssertion]:
        """Return relationships where the entity is subject or object."""

        return self.store.list_relationships_for_target(entity_id)

    def get_relationships_for_project(self, project_cluster_id: str) -> list[RelationshipAssertion]:
        """Return relationships connected to a project cluster identifier."""

        return self.store.list_relationships_for_target(project_cluster_id)

    def get_entities_connected_to_entity(self, entity_id: str) -> list[EntityIdentity]:
        """Return entity identities directly connected to the given entity."""

        connected_ids = {
            relationship.object_entity_id
            for relationship in self.get_relationships_for_entity(entity_id)
            if relationship.subject_entity_id == entity_id
        }
        connected_ids.update(
            relationship.subject_entity_id
            for relationship in self.get_relationships_for_entity(entity_id)
            if relationship.object_entity_id == entity_id
        )
        return self.store.list_entities_by_ids(connected_ids)

    def get_projects_for_entity(self, entity_id: str) -> list[ProjectCluster]:
        """Return project clusters directly connected to the given entity."""

        project_ids = {
            relationship.object_entity_id
            for relationship in self.get_relationships_for_entity(entity_id)
            if relationship.subject_entity_id == entity_id
        }
        project_ids.update(
            relationship.subject_entity_id
            for relationship in self.get_relationships_for_entity(entity_id)
            if relationship.object_entity_id == entity_id
        )
        return self.store.list_project_clusters_by_ids(project_ids)

    def get_opportunities_for_project(self, project_cluster_id: str) -> list[OpportunitySignal]:
        """Return opportunities directly tied to a project cluster."""

        return self.store.list_opportunities_for_project(project_cluster_id)

    def get_opportunities_for_entity(self, entity_id: str) -> list[OpportunitySignal]:
        """Return opportunities tied directly or indirectly to an entity."""

        project_ids = {
            project.project_cluster_id for project in self.get_projects_for_entity(entity_id)
        }
        return [
            opportunity
            for opportunity in self.store.list_opportunities()
            if entity_id in opportunity.related_entity_ids
            or (
                opportunity.project_cluster_id is not None
                and opportunity.project_cluster_id in project_ids
            )
        ]
