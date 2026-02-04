"""
Shared dataclasses for the memory subsystem.

This module defines the core data types used across all memory components:
- Entity and Relationship for the knowledge graph
- Artifact for intermediate result storage
- SessionSummary for compressed conversation history
- RAGResult for vector search results
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field, asdict
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any


class EntityType(str, Enum):
    """Types of biological entities tracked in the knowledge graph."""
    GENE = "gene"
    PROTEIN = "protein"
    VARIANT = "variant"
    PATHWAY = "pathway"
    SAMPLE = "sample"
    ORGANISM = "organism"
    DISEASE = "disease"
    DRUG = "drug"
    PUBLICATION = "publication"
    STRUCTURE = "structure"
    DOMAIN = "domain"
    GO_TERM = "go_term"
    OTHER = "other"


class RelationshipType(str, Enum):
    """Types of relationships between entities."""
    INTERACTS_WITH = "interacts_with"
    REGULATES = "regulates"
    REGULATED_BY = "regulated_by"
    MEMBER_OF = "member_of"
    CONTAINS = "contains"
    ASSOCIATED_WITH = "associated_with"
    ENCODES = "encodes"
    ENCODED_BY = "encoded_by"
    VARIANT_OF = "variant_of"
    HAS_VARIANT = "has_variant"
    ORTHOLOG_OF = "ortholog_of"
    PARALOG_OF = "paralog_of"
    LOCATED_IN = "located_in"
    PARTICIPATES_IN = "participates_in"
    HAS_FUNCTION = "has_function"
    CAUSES = "causes"
    TREATS = "treats"
    CITED_IN = "cited_in"


class ArtifactType(str, Enum):
    """Types of artifacts that can be stored."""
    DATAFRAME = "dataframe"
    PLOT = "plot"
    SEQUENCE = "sequence"
    CODE = "code"
    ANALYSIS_RESULT = "analysis_result"
    ALIGNMENT = "alignment"
    STRUCTURE = "structure"
    TREE = "tree"
    NETWORK = "network"
    TABLE = "table"
    TEXT = "text"
    JSON = "json"
    OTHER = "other"


@dataclass
class Entity:
    """A biological entity in the knowledge graph."""
    id: str
    name: str
    entity_type: EntityType
    source: str  # Tool/database that identified this entity
    properties: dict[str, Any] = field(default_factory=dict)
    aliases: list[str] = field(default_factory=list)
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    last_accessed: str = field(default_factory=lambda: datetime.now().isoformat())
    access_count: int = 0

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        d = asdict(self)
        d["entity_type"] = self.entity_type.value
        return d

    @classmethod
    def from_dict(cls, data: dict) -> Entity:
        """Create from dictionary."""
        data = data.copy()
        data["entity_type"] = EntityType(data["entity_type"])
        return cls(**data)

    def update_access(self) -> None:
        """Update access tracking."""
        self.last_accessed = datetime.now().isoformat()
        self.access_count += 1


@dataclass
class Relationship:
    """A relationship between two entities in the knowledge graph."""
    id: str
    source_id: str
    target_id: str
    relationship_type: RelationshipType
    source_tool: str  # Tool that discovered this relationship
    confidence: float = 1.0  # 0-1 confidence score
    properties: dict[str, Any] = field(default_factory=dict)
    evidence: list[str] = field(default_factory=list)
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        d = asdict(self)
        d["relationship_type"] = self.relationship_type.value
        return d

    @classmethod
    def from_dict(cls, data: dict) -> Relationship:
        """Create from dictionary."""
        data = data.copy()
        data["relationship_type"] = RelationshipType(data["relationship_type"])
        return cls(**data)


@dataclass
class Artifact:
    """An intermediate result stored for later retrieval."""
    id: str
    name: str
    artifact_type: ArtifactType
    description: str
    file_path: str  # Path to the stored artifact file
    metadata: dict[str, Any] = field(default_factory=dict)
    tags: list[str] = field(default_factory=list)
    source_tool: str = ""  # Tool that generated this artifact
    source_query: str = ""  # Original query/command
    size_bytes: int = 0
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    last_accessed: str = field(default_factory=lambda: datetime.now().isoformat())
    access_count: int = 0

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        d = asdict(self)
        d["artifact_type"] = self.artifact_type.value
        return d

    @classmethod
    def from_dict(cls, data: dict) -> Artifact:
        """Create from dictionary."""
        data = data.copy()
        data["artifact_type"] = ArtifactType(data["artifact_type"])
        return cls(**data)

    def update_access(self) -> None:
        """Update access tracking."""
        self.last_accessed = datetime.now().isoformat()
        self.access_count += 1


@dataclass
class SessionSummary:
    """A compressed summary of a conversation segment."""
    id: str
    session_id: str
    start_round: int
    end_round: int
    summary: str
    key_findings: list[str] = field(default_factory=list)
    tools_used: list[str] = field(default_factory=list)
    entities_mentioned: list[str] = field(default_factory=list)
    artifacts_created: list[str] = field(default_factory=list)
    token_count_original: int = 0
    token_count_summary: int = 0
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> SessionSummary:
        """Create from dictionary."""
        return cls(**data)

    @property
    def compression_ratio(self) -> float:
        """Calculate compression ratio."""
        if self.token_count_original == 0:
            return 0.0
        return 1.0 - (self.token_count_summary / self.token_count_original)


@dataclass
class RAGResult:
    """A result from vector similarity search."""
    id: str
    content: str
    similarity: float
    source: str  # 'tool_result', 'analysis', 'summary', etc.
    metadata: dict[str, Any] = field(default_factory=dict)
    timestamp: str = ""

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> RAGResult:
        """Create from dictionary."""
        return cls(**data)


@dataclass
class MemoryStats:
    """Statistics about memory usage."""
    total_entities: int = 0
    total_relationships: int = 0
    total_artifacts: int = 0
    total_summaries: int = 0
    total_rag_documents: int = 0
    storage_bytes: int = 0
    last_updated: str = field(default_factory=lambda: datetime.now().isoformat())

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> MemoryStats:
        """Create from dictionary."""
        return cls(**data)


# Utility functions for working with types

def serialize_to_json(obj: Entity | Relationship | Artifact | SessionSummary | RAGResult) -> str:
    """Serialize a memory object to JSON string."""
    return json.dumps(obj.to_dict(), indent=2, default=str)


def estimate_tokens(text: str) -> int:
    """Estimate token count for text (rough approximation: ~4 chars per token)."""
    return len(text) // 4


def truncate_to_tokens(text: str, max_tokens: int) -> str:
    """Truncate text to approximately max_tokens."""
    max_chars = max_tokens * 4
    if len(text) <= max_chars:
        return text
    return text[:max_chars - 3] + "..."
