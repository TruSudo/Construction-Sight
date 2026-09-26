"""Graph neighborhood query service for ConstructionSight intelligence records.

The neighborhood service returns the immediate relationship context around an
entity or project node. This is the backend shape that future relationship-map
and detail-panel views can render.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from constructionsight.intelligence.relationship_query_service import RelationshipQueryService
from constructionsight.intelligence.schemas import (
    EntityIdentity,
    OpportunitySignal,
    ProjectCluster,
    RelationshipAssertion,
)
from constructionsight.storage.intelligence_store import IntelligenceStore


class GraphNeighborhood(BaseModel):
    """Immediate graph context around one center node."""

    center_node_id: str = Field(min_length=1)
    center_node_kind: str = Field(min_length=1)
    connected_entities: list[EntityIdentity] = Field(default_factory=list)
    connected_projects: list[ProjectCluster] = Field(default_factory=list)
    relationships: list[RelationshipAssertion] = Field(default_factory=list)
    opportunities: list[OpportunitySignal] = Field(default_factory=list)

    @property
    def node_count(self) -> int:
        """Return total visible node count including the center node."""

        return (
            1
            + len(self.connected_entities)
            + len(self.connected_projects)
            + len(self.opportunities)
        )

    @property
    def edge_count(self) -> int:
        """Return total relationship edge count in the neighborhood."""

        return len(self.relationships)


class GraphNeighborhoodService:
    """Read-only service that composes immediate graph neighborhoods."""

    def __init__(self, store: IntelligenceStore) -> None:
        self.store = store
        self.relationship_queries = RelationshipQueryService(store)

    def get_entity_neighborhood(self, entity_id: str) -> GraphNeighborhood:
        """Return immediate graph context around an entity."""

        relationships = self.relationship_queries.get_relationships_for_entity(entity_id)
        connected_entities = self.relationship_queries.get_entities_connected_to_entity(entity_id)
        connected_projects = self.relationship_queries.get_projects_for_entity(entity_id)
        opportunities = self.relationship_queries.get_opportunities_for_entity(entity_id)
        return GraphNeighborhood(
            center_node_id=entity_id,
            center_node_kind="entity",
            connected_entities=connected_entities,
            connected_projects=connected_projects,
            relationships=relationships,
            opportunities=opportunities,
        )

    def get_project_neighborhood(self, project_cluster_id: str) -> GraphNeighborhood:
        """Return immediate graph context around a project cluster."""

        relationships = self.relationship_queries.get_relationships_for_project(project_cluster_id)
        connected_entity_ids = {
            relationship.subject_entity_id
            for relationship in relationships
            if relationship.subject_entity_id != project_cluster_id
        }
        connected_entity_ids.update(
            relationship.object_entity_id
            for relationship in relationships
            if relationship.object_entity_id != project_cluster_id
        )
        connected_entities = self.store.list_entities_by_ids(connected_entity_ids)
        opportunities = self.relationship_queries.get_opportunities_for_project(project_cluster_id)
        return GraphNeighborhood(
            center_node_id=project_cluster_id,
            center_node_kind="project_cluster",
            connected_entities=connected_entities,
            connected_projects=[],
            relationships=relationships,
            opportunities=opportunities,
        )
