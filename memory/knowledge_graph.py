"""
Knowledge Graph for biological entity and relationship tracking.

This module provides a JSON-based knowledge graph that tracks biological
entities (genes, proteins, variants, pathways, etc.) and their relationships.
"""

from __future__ import annotations

import json
import re
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

from .types import (
    Entity,
    EntityType,
    Relationship,
    RelationshipType,
    estimate_tokens,
)


class KnowledgeGraphResult:
    """Result of a knowledge graph operation."""

    def __init__(
        self,
        success: bool,
        message: str,
        entities: list[Entity] | None = None,
        relationships: list[Relationship] | None = None,
        entity: Entity | None = None,
    ):
        self.success = success
        self.message = message
        self.entities = entities or []
        self.relationships = relationships or []
        self.entity = entity

    def to_string(self) -> str:
        """Format for Claude."""
        if not self.success:
            return f"Knowledge graph error: {self.message}"

        if self.entity:
            props = json.dumps(self.entity.properties, indent=2)
            return (
                f"Entity: {self.entity.name}\n"
                f"Type: {self.entity.entity_type.value}\n"
                f"Source: {self.entity.source}\n"
                f"Aliases: {', '.join(self.entity.aliases) if self.entity.aliases else 'None'}\n"
                f"Properties:\n{props}"
            )

        lines = []
        if self.entities:
            lines.append(f"Found {len(self.entities)} entity/entities:")
            for e in self.entities[:20]:
                aliases = f" (also: {', '.join(e.aliases[:3])})" if e.aliases else ""
                lines.append(
                    f"  - [{e.entity_type.value}] {e.name}{aliases}"
                )
            if len(self.entities) > 20:
                lines.append(f"  ... and {len(self.entities) - 20} more")

        if self.relationships:
            lines.append(f"\nFound {len(self.relationships)} relationship(s):")
            for r in self.relationships[:20]:
                lines.append(
                    f"  - {r.source_id} --[{r.relationship_type.value}]--> {r.target_id}"
                )
            if len(self.relationships) > 20:
                lines.append(f"  ... and {len(self.relationships) - 20} more")

        return "\n".join(lines) if lines else self.message


class KnowledgeGraph:
    """JSON-based knowledge graph for biological entities.

    Tracks entities like genes, proteins, variants, pathways, and their
    relationships. Supports auto-extraction of entities from tool results
    using regex patterns.
    """

    # Regex patterns for entity extraction
    ENTITY_PATTERNS = {
        EntityType.GENE: [
            r'\b([A-Z][A-Z0-9]{1,10})\b',  # Gene symbols like TP53, BRCA1
            r'gene[:\s]+([A-Za-z0-9_-]+)',  # "gene: xyz"
            r'Gene ID[:\s]+(\d+)',  # Entrez IDs
        ],
        EntityType.PROTEIN: [
            r'\b([A-Z][A-Z0-9]{2,10}_[A-Z]+)\b',  # UniProt accessions
            r'protein[:\s]+([A-Za-z0-9_-]+)',  # "protein: xyz"
            r'\b(P\d{5})\b',  # UniProt IDs
        ],
        EntityType.VARIANT: [
            r'(rs\d+)',  # dbSNP rsIDs
            r'([A-Z]\d+[A-Z])',  # Amino acid changes like V600E
            r'(c\.\d+[ACGT]>[ACGT])',  # cDNA changes
        ],
        EntityType.PATHWAY: [
            r'(hsa\d{5})',  # KEGG pathway IDs
            r'(R-HSA-\d+)',  # Reactome IDs
            r'pathway[:\s]+([A-Za-z0-9_ -]+)',  # "pathway: xyz"
        ],
        EntityType.GO_TERM: [
            r'(GO:\d{7})',  # GO terms
        ],
        EntityType.STRUCTURE: [
            r'\b(\d[A-Za-z0-9]{3})\b',  # PDB IDs like 1ABC
            r'(AF-[A-Z0-9]+-F\d+)',  # AlphaFold IDs
        ],
        EntityType.ORGANISM: [
            r'organism[:\s]+([A-Za-z]+ [a-z]+)',  # Species names
            r'(Homo sapiens|Mus musculus|Escherichia coli)',  # Common organisms
        ],
    }

    def __init__(
        self,
        kg_file: str,
        max_entities: int = 10000,
        max_relationships: int = 50000,
        auto_extract: bool = True,
    ):
        """Initialize knowledge graph.

        Args:
            kg_file: Path to JSON file for persistence
            max_entities: Maximum number of entities to store
            max_relationships: Maximum number of relationships
            auto_extract: Whether to auto-extract entities from text
        """
        self.kg_file = Path(kg_file)
        self.kg_file.parent.mkdir(parents=True, exist_ok=True)
        self.max_entities = max_entities
        self.max_relationships = max_relationships
        self.auto_extract = auto_extract

        self._entities: dict[str, Entity] = {}
        self._relationships: dict[str, Relationship] = {}
        self._name_index: dict[str, str] = {}  # name/alias -> entity_id
        self._load()

    def _load(self) -> None:
        """Load graph from disk."""
        if self.kg_file.exists():
            try:
                with open(self.kg_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self._entities = {
                        k: Entity.from_dict(v)
                        for k, v in data.get("entities", {}).items()
                    }
                    self._relationships = {
                        k: Relationship.from_dict(v)
                        for k, v in data.get("relationships", {}).items()
                    }
                    self._rebuild_name_index()
            except (json.JSONDecodeError, KeyError) as e:
                print(f"Warning: Could not load knowledge graph: {e}")
                self._entities = {}
                self._relationships = {}

    def _save(self) -> None:
        """Save graph to disk."""
        data = {
            "entities": {k: v.to_dict() for k, v in self._entities.items()},
            "relationships": {
                k: v.to_dict() for k, v in self._relationships.items()
            },
        }
        with open(self.kg_file, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, default=str)

    def _rebuild_name_index(self) -> None:
        """Rebuild the name->id index."""
        self._name_index = {}
        for entity_id, entity in self._entities.items():
            self._name_index[entity.name.lower()] = entity_id
            for alias in entity.aliases:
                self._name_index[alias.lower()] = entity_id

    def _generate_id(self, entity_type: EntityType, name: str) -> str:
        """Generate unique entity ID."""
        safe_name = "".join(c if c.isalnum() else "_" for c in name[:20])
        return f"{entity_type.value}_{safe_name}_{uuid.uuid4().hex[:8]}"

    def add_entity(
        self,
        name: str,
        entity_type: str | EntityType,
        source: str,
        properties: dict[str, Any] | None = None,
        aliases: list[str] | None = None,
    ) -> KnowledgeGraphResult:
        """Add an entity to the knowledge graph.

        Args:
            name: Entity name
            entity_type: Type of entity
            source: Source that identified this entity
            properties: Additional properties
            aliases: Alternative names

        Returns:
            KnowledgeGraphResult with the entity
        """
        # Convert string type to enum
        if isinstance(entity_type, str):
            try:
                entity_type = EntityType(entity_type)
            except ValueError:
                entity_type = EntityType.OTHER

        # Check if entity already exists
        existing_id = self._name_index.get(name.lower())
        if existing_id and existing_id in self._entities:
            existing = self._entities[existing_id]
            # Update existing entity
            if properties:
                existing.properties.update(properties)
            if aliases:
                for alias in aliases:
                    if alias not in existing.aliases:
                        existing.aliases.append(alias)
                        self._name_index[alias.lower()] = existing_id
            existing.update_access()
            self._save()
            return KnowledgeGraphResult(
                success=True,
                message="Entity updated",
                entity=existing,
            )

        # Check capacity
        if len(self._entities) >= self.max_entities:
            # Remove least accessed entities
            self._prune_entities()

        # Create new entity
        entity_id = self._generate_id(entity_type, name)
        entity = Entity(
            id=entity_id,
            name=name,
            entity_type=entity_type,
            source=source,
            properties=properties or {},
            aliases=aliases or [],
        )

        self._entities[entity_id] = entity
        self._name_index[name.lower()] = entity_id
        for alias in entity.aliases:
            self._name_index[alias.lower()] = entity_id

        self._save()

        return KnowledgeGraphResult(
            success=True,
            message="Entity added",
            entity=entity,
        )

    def _prune_entities(self) -> None:
        """Remove least accessed entities to make room."""
        # Sort by access count, then by last accessed
        sorted_entities = sorted(
            self._entities.items(),
            key=lambda x: (x[1].access_count, x[1].last_accessed),
        )

        # Remove bottom 10%
        to_remove = int(len(sorted_entities) * 0.1)
        for entity_id, entity in sorted_entities[:to_remove]:
            # Remove from name index
            if self._name_index.get(entity.name.lower()) == entity_id:
                del self._name_index[entity.name.lower()]
            for alias in entity.aliases:
                if self._name_index.get(alias.lower()) == entity_id:
                    del self._name_index[alias.lower()]
            # Remove entity
            del self._entities[entity_id]
            # Remove associated relationships
            self._relationships = {
                k: v for k, v in self._relationships.items()
                if v.source_id != entity_id and v.target_id != entity_id
            }

    def add_relationship(
        self,
        source_name: str,
        target_name: str,
        relationship_type: str | RelationshipType,
        source_tool: str,
        confidence: float = 1.0,
        properties: dict[str, Any] | None = None,
        evidence: list[str] | None = None,
    ) -> KnowledgeGraphResult:
        """Add a relationship between entities.

        Args:
            source_name: Source entity name
            target_name: Target entity name
            relationship_type: Type of relationship
            source_tool: Tool that discovered this relationship
            confidence: Confidence score (0-1)
            properties: Additional properties
            evidence: Supporting evidence

        Returns:
            KnowledgeGraphResult with status
        """
        # Convert string type to enum
        if isinstance(relationship_type, str):
            try:
                relationship_type = RelationshipType(relationship_type)
            except ValueError:
                relationship_type = RelationshipType.ASSOCIATED_WITH

        # Find or create source entity
        source_id = self._name_index.get(source_name.lower())
        if not source_id:
            # Auto-create entity
            result = self.add_entity(
                name=source_name,
                entity_type=EntityType.OTHER,
                source=source_tool,
            )
            if result.entity:
                source_id = result.entity.id

        # Find or create target entity
        target_id = self._name_index.get(target_name.lower())
        if not target_id:
            # Auto-create entity
            result = self.add_entity(
                name=target_name,
                entity_type=EntityType.OTHER,
                source=source_tool,
            )
            if result.entity:
                target_id = result.entity.id

        if not source_id or not target_id:
            return KnowledgeGraphResult(
                success=False,
                message="Could not resolve entity names",
            )

        # Check for existing relationship
        for rel in self._relationships.values():
            if (
                rel.source_id == source_id
                and rel.target_id == target_id
                and rel.relationship_type == relationship_type
            ):
                # Update existing
                rel.confidence = max(rel.confidence, confidence)
                if properties:
                    rel.properties.update(properties)
                if evidence:
                    rel.evidence.extend(evidence)
                self._save()
                return KnowledgeGraphResult(
                    success=True,
                    message="Relationship updated",
                    relationships=[rel],
                )

        # Check capacity
        if len(self._relationships) >= self.max_relationships:
            # Remove lowest confidence relationships
            sorted_rels = sorted(
                self._relationships.items(),
                key=lambda x: x[1].confidence,
            )
            to_remove = int(len(sorted_rels) * 0.1)
            for rel_id, _ in sorted_rels[:to_remove]:
                del self._relationships[rel_id]

        # Create new relationship
        rel_id = f"rel_{uuid.uuid4().hex[:12]}"
        relationship = Relationship(
            id=rel_id,
            source_id=source_id,
            target_id=target_id,
            relationship_type=relationship_type,
            source_tool=source_tool,
            confidence=confidence,
            properties=properties or {},
            evidence=evidence or [],
        )

        self._relationships[rel_id] = relationship
        self._save()

        return KnowledgeGraphResult(
            success=True,
            message="Relationship added",
            relationships=[relationship],
        )

    def find_entities(
        self,
        query: str | None = None,
        entity_type: str | EntityType | None = None,
        limit: int = 20,
    ) -> KnowledgeGraphResult:
        """Search for entities.

        Args:
            query: Search in names and aliases
            entity_type: Filter by type
            limit: Maximum results

        Returns:
            KnowledgeGraphResult with matching entities
        """
        # Convert string type to enum
        if isinstance(entity_type, str):
            try:
                entity_type = EntityType(entity_type)
            except ValueError:
                entity_type = None

        results = []
        for entity in self._entities.values():
            # Filter by type
            if entity_type and entity.entity_type != entity_type:
                continue

            # Search query
            if query:
                query_lower = query.lower()
                searchable = [entity.name.lower()] + [
                    a.lower() for a in entity.aliases
                ]
                if not any(query_lower in s for s in searchable):
                    continue

            results.append(entity)

        # Sort by access count
        results.sort(key=lambda e: e.access_count, reverse=True)
        results = results[:limit]

        return KnowledgeGraphResult(
            success=True,
            message=f"Found {len(results)} entities",
            entities=results,
        )

    def get_entity(self, name: str) -> KnowledgeGraphResult:
        """Get a specific entity by name.

        Args:
            name: Entity name or alias

        Returns:
            KnowledgeGraphResult with entity
        """
        entity_id = self._name_index.get(name.lower())
        if not entity_id or entity_id not in self._entities:
            return KnowledgeGraphResult(
                success=False,
                message=f"Entity not found: {name}",
            )

        entity = self._entities[entity_id]
        entity.update_access()
        self._save()

        return KnowledgeGraphResult(
            success=True,
            message="Entity found",
            entity=entity,
        )

    def get_neighbors(
        self,
        entity_name: str,
        relationship_type: str | RelationshipType | None = None,
        direction: str = "both",
        limit: int = 20,
    ) -> KnowledgeGraphResult:
        """Get entities connected to a given entity.

        Args:
            entity_name: Starting entity name
            relationship_type: Filter by relationship type
            direction: 'outgoing', 'incoming', or 'both'
            limit: Maximum results

        Returns:
            KnowledgeGraphResult with neighbors and relationships
        """
        entity_id = self._name_index.get(entity_name.lower())
        if not entity_id:
            return KnowledgeGraphResult(
                success=False,
                message=f"Entity not found: {entity_name}",
            )

        # Convert string type to enum
        if isinstance(relationship_type, str):
            try:
                relationship_type = RelationshipType(relationship_type)
            except ValueError:
                relationship_type = None

        # Find relationships
        matching_rels = []
        neighbor_ids = set()

        for rel in self._relationships.values():
            # Filter by type
            if relationship_type and rel.relationship_type != relationship_type:
                continue

            # Check direction
            if direction in ("outgoing", "both") and rel.source_id == entity_id:
                matching_rels.append(rel)
                neighbor_ids.add(rel.target_id)
            if direction in ("incoming", "both") and rel.target_id == entity_id:
                matching_rels.append(rel)
                neighbor_ids.add(rel.source_id)

        # Get neighbor entities
        neighbors = [
            self._entities[nid] for nid in neighbor_ids
            if nid in self._entities
        ][:limit]

        return KnowledgeGraphResult(
            success=True,
            message=f"Found {len(neighbors)} neighbors",
            entities=neighbors,
            relationships=matching_rels[:limit],
        )

    def extract_entities_from_text(
        self,
        text: str,
        source: str,
    ) -> KnowledgeGraphResult:
        """Extract and add entities from text using regex patterns.

        Args:
            text: Text to extract from
            source: Source identifier

        Returns:
            KnowledgeGraphResult with extracted entities
        """
        if not self.auto_extract:
            return KnowledgeGraphResult(
                success=True,
                message="Auto-extraction disabled",
                entities=[],
            )

        extracted = []
        seen = set()

        for entity_type, patterns in self.ENTITY_PATTERNS.items():
            for pattern in patterns:
                try:
                    matches = re.findall(pattern, text)
                    for match in matches:
                        if isinstance(match, tuple):
                            match = match[0]
                        match = match.strip()

                        # Skip very short or already seen
                        if len(match) < 2 or match.lower() in seen:
                            continue

                        # Skip common words that match patterns
                        if match.lower() in {
                            "the", "and", "for", "with", "are", "was",
                            "gene", "protein", "pathway", "cell", "data",
                        }:
                            continue

                        seen.add(match.lower())

                        # Add entity
                        result = self.add_entity(
                            name=match,
                            entity_type=entity_type,
                            source=source,
                        )
                        if result.entity:
                            extracted.append(result.entity)

                except re.error:
                    continue

        return KnowledgeGraphResult(
            success=True,
            message=f"Extracted {len(extracted)} entities",
            entities=extracted,
        )

    def format_for_context(
        self,
        relevant_entities: list[str] | None = None,
        max_tokens: int = 5000,
    ) -> str:
        """Format knowledge graph for context injection.

        Args:
            relevant_entities: Entity names to focus on
            max_tokens: Maximum tokens

        Returns:
            Formatted context string
        """
        if not self._entities:
            return ""

        lines = ["## Known Biological Entities\n"]
        current_tokens = estimate_tokens(lines[0])

        # If specific entities requested, prioritize those
        if relevant_entities:
            for name in relevant_entities:
                entity_id = self._name_index.get(name.lower())
                if entity_id and entity_id in self._entities:
                    entity = self._entities[entity_id]
                    entity_text = self._format_entity(entity)
                    entity_tokens = estimate_tokens(entity_text)

                    if current_tokens + entity_tokens > max_tokens:
                        break

                    lines.append(entity_text)
                    current_tokens += entity_tokens

                    # Add neighbors
                    neighbors_result = self.get_neighbors(name, limit=5)
                    for rel in neighbors_result.relationships[:3]:
                        rel_text = self._format_relationship(rel)
                        rel_tokens = estimate_tokens(rel_text)
                        if current_tokens + rel_tokens > max_tokens:
                            break
                        lines.append(rel_text)
                        current_tokens += rel_tokens
        else:
            # Show most accessed entities
            sorted_entities = sorted(
                self._entities.values(),
                key=lambda e: e.access_count,
                reverse=True,
            )

            for entity in sorted_entities[:50]:
                entity_text = f"- {entity.name} ({entity.entity_type.value})"
                entity_tokens = estimate_tokens(entity_text)

                if current_tokens + entity_tokens > max_tokens:
                    break

                lines.append(entity_text)
                current_tokens += entity_tokens

        return "\n".join(lines)

    def _format_entity(self, entity: Entity) -> str:
        """Format a single entity for display."""
        lines = [f"**{entity.name}** ({entity.entity_type.value})"]
        if entity.aliases:
            lines.append(f"  Aliases: {', '.join(entity.aliases[:5])}")
        if entity.properties:
            for key, value in list(entity.properties.items())[:3]:
                lines.append(f"  {key}: {value}")
        return "\n".join(lines)

    def _format_relationship(self, rel: Relationship) -> str:
        """Format a relationship for display."""
        source_name = self._get_entity_name(rel.source_id)
        target_name = self._get_entity_name(rel.target_id)
        return f"  → {source_name} --[{rel.relationship_type.value}]--> {target_name}"

    def _get_entity_name(self, entity_id: str) -> str:
        """Get entity name by ID."""
        if entity_id in self._entities:
            return self._entities[entity_id].name
        return entity_id

    def get_stats(self) -> dict[str, Any]:
        """Get knowledge graph statistics.

        Returns:
            Dictionary with stats
        """
        type_counts = {}
        for entity in self._entities.values():
            t = entity.entity_type.value
            type_counts[t] = type_counts.get(t, 0) + 1

        rel_counts = {}
        for rel in self._relationships.values():
            t = rel.relationship_type.value
            rel_counts[t] = rel_counts.get(t, 0) + 1

        return {
            "total_entities": len(self._entities),
            "total_relationships": len(self._relationships),
            "entities_by_type": type_counts,
            "relationships_by_type": rel_counts,
            "auto_extract_enabled": self.auto_extract,
        }

    def clear(self) -> KnowledgeGraphResult:
        """Clear the entire knowledge graph.

        Returns:
            KnowledgeGraphResult with status
        """
        self._entities = {}
        self._relationships = {}
        self._name_index = {}
        self._save()

        return KnowledgeGraphResult(
            success=True,
            message="Knowledge graph cleared",
        )
