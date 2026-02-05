"""
Context management for multi-agent architecture.

Provides SpecialistContext for passing information between agents
and AgentSessionCache for caching session state.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass
class SpecialistContext:
    """
    Context passed from coordinator to specialist agents.

    Contains relevant information gathered from memory, previous outputs,
    and the original user query to help specialists understand their task.
    """

    # Original user query
    user_query: str

    # Memory context (from RAG search, knowledge graph, etc.)
    memory_context: str = ""

    # Entities relevant to this query (from knowledge graph)
    relevant_entities: list[dict[str, Any]] = field(default_factory=list)

    # Artifacts that might be useful (from artifact store)
    relevant_artifacts: list[dict[str, Any]] = field(default_factory=list)

    # Previous conversation summary (if multi-turn)
    conversation_summary: str = ""

    # Specific instructions from coordinator
    coordinator_notes: str = ""

    # Files/data references the user mentioned
    referenced_files: list[str] = field(default_factory=list)

    # Session metadata
    session_id: str = ""
    round_number: int = 1

    def to_prompt_section(self) -> str:
        """Format context as a prompt section for the specialist."""
        sections = []

        if self.memory_context:
            sections.append(f"## Relevant Memory Context\n{self.memory_context}")

        if self.relevant_entities:
            entity_lines = []
            for entity in self.relevant_entities[:10]:  # Limit to 10 entities
                entity_lines.append(
                    f"- **{entity.get('name', 'Unknown')}** ({entity.get('type', 'unknown')}): "
                    f"{entity.get('description', '')[:100]}"
                )
            if entity_lines:
                sections.append("## Relevant Biological Entities\n" + "\n".join(entity_lines))

        if self.relevant_artifacts:
            artifact_lines = []
            for artifact in self.relevant_artifacts[:5]:  # Limit to 5 artifacts
                artifact_lines.append(
                    f"- **{artifact.get('name', 'Unknown')}** ({artifact.get('type', 'unknown')}): "
                    f"{artifact.get('description', '')[:100]}"
                )
            if artifact_lines:
                sections.append("## Available Artifacts\n" + "\n".join(artifact_lines))

        if self.conversation_summary:
            sections.append(f"## Previous Conversation Summary\n{self.conversation_summary}")

        if self.coordinator_notes:
            sections.append(f"## Coordinator Notes\n{self.coordinator_notes}")

        if self.referenced_files:
            sections.append(
                "## Referenced Files\n" + "\n".join(f"- {f}" for f in self.referenced_files)
            )

        return "\n\n".join(sections)


@dataclass
class AgentSessionCache:
    """
    Cache for sharing state across agents within a session.

    Allows specialists to share intermediate results, avoid redundant
    database queries, and maintain consistency.
    """

    # Session identifier
    session_id: str

    # Cached database query results (tool_name -> query -> result)
    query_cache: dict[str, dict[str, str]] = field(default_factory=dict)

    # Shared data between agents (key -> value)
    shared_data: dict[str, Any] = field(default_factory=dict)

    # Entities discovered during this session
    session_entities: list[dict[str, Any]] = field(default_factory=list)

    # Files created/modified during this session
    session_files: list[str] = field(default_factory=list)

    # Timestamps
    created_at: datetime = field(default_factory=datetime.now)
    last_accessed: datetime = field(default_factory=datetime.now)

    def cache_query_result(self, tool_name: str, query_key: str, result: str):
        """Cache a database query result."""
        if tool_name not in self.query_cache:
            self.query_cache[tool_name] = {}
        self.query_cache[tool_name][query_key] = result
        self.last_accessed = datetime.now()

    def get_cached_query(self, tool_name: str, query_key: str) -> str | None:
        """Get a cached query result if available."""
        self.last_accessed = datetime.now()
        return self.query_cache.get(tool_name, {}).get(query_key)

    def set_shared_data(self, key: str, value: Any):
        """Store shared data accessible by all agents."""
        self.shared_data[key] = value
        self.last_accessed = datetime.now()

    def get_shared_data(self, key: str, default: Any = None) -> Any:
        """Retrieve shared data."""
        self.last_accessed = datetime.now()
        return self.shared_data.get(key, default)

    def add_entity(self, entity: dict[str, Any]):
        """Add a discovered entity to the session."""
        # Avoid duplicates by name
        existing_names = {e.get("name") for e in self.session_entities}
        if entity.get("name") not in existing_names:
            self.session_entities.append(entity)
        self.last_accessed = datetime.now()

    def add_file(self, filepath: str):
        """Track a file created/modified during the session."""
        if filepath not in self.session_files:
            self.session_files.append(filepath)
        self.last_accessed = datetime.now()

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "session_id": self.session_id,
            "query_cache": self.query_cache,
            "shared_data": self.shared_data,
            "session_entities": self.session_entities,
            "session_files": self.session_files,
            "created_at": self.created_at.isoformat(),
            "last_accessed": self.last_accessed.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "AgentSessionCache":
        """Deserialize from dictionary."""
        return cls(
            session_id=data["session_id"],
            query_cache=data.get("query_cache", {}),
            shared_data=data.get("shared_data", {}),
            session_entities=data.get("session_entities", []),
            session_files=data.get("session_files", []),
            created_at=datetime.fromisoformat(data["created_at"]) if "created_at" in data else datetime.now(),
            last_accessed=datetime.fromisoformat(data["last_accessed"]) if "last_accessed" in data else datetime.now(),
        )


class ContextBuilder:
    """
    Utility class for building SpecialistContext from various sources.
    """

    def __init__(self, memory=None, session_cache: AgentSessionCache | None = None):
        """
        Initialize the context builder.

        Args:
            memory: ContextManager from the memory system
            session_cache: Optional session cache for shared state
        """
        self.memory = memory
        self.session_cache = session_cache

    def build_context(
        self,
        user_query: str,
        conversation_history: list[dict] | None = None,
        round_number: int = 1,
    ) -> SpecialistContext:
        """
        Build a SpecialistContext for the given query.

        Args:
            user_query: The user's query/task
            conversation_history: Optional conversation history
            round_number: Current round number in multi-turn conversation

        Returns:
            SpecialistContext populated with relevant information
        """
        context = SpecialistContext(
            user_query=user_query,
            round_number=round_number,
            session_id=self.session_cache.session_id if self.session_cache else "",
        )

        # Get memory context if available
        if self.memory:
            try:
                # Get enhanced context from memory system
                memory_context = self.memory.get_enhanced_context(
                    user_query, conversation_history or [], round_number
                )
                context.memory_context = memory_context

                # Get relevant entities
                entities_result = self.memory.get_entities(
                    query=user_query,
                    include_relationships=False,
                )
                # Parse entities from result string (simplified)
                context.relevant_entities = self._parse_entities(entities_result)

                # Get relevant artifacts
                artifacts_result = self.memory.list_artifacts(query=user_query)
                context.relevant_artifacts = self._parse_artifacts(artifacts_result)

            except Exception:
                pass  # Continue without memory context if it fails

        # Add session entities if available
        if self.session_cache:
            for entity in self.session_cache.session_entities:
                if entity not in context.relevant_entities:
                    context.relevant_entities.append(entity)

        # Extract file references from query
        context.referenced_files = self._extract_file_references(user_query)

        return context

    def _parse_entities(self, entities_result: str) -> list[dict[str, Any]]:
        """Parse entities from memory_get_entities result string."""
        entities = []
        # Simple parsing - in practice this would be more sophisticated
        if "No entities found" in entities_result:
            return entities

        # Try to extract entity info from the result
        lines = entities_result.split("\n")
        for line in lines:
            if ":" in line and not line.startswith("#"):
                parts = line.split(":", 1)
                if len(parts) == 2:
                    entities.append({
                        "name": parts[0].strip().strip("-").strip("*").strip(),
                        "description": parts[1].strip(),
                        "type": "unknown",
                    })

        return entities[:10]  # Limit to 10

    def _parse_artifacts(self, artifacts_result: str) -> list[dict[str, Any]]:
        """Parse artifacts from memory_list_artifacts result string."""
        artifacts = []
        if "No artifacts found" in artifacts_result:
            return artifacts

        # Simple parsing
        lines = artifacts_result.split("\n")
        for line in lines:
            if ":" in line and not line.startswith("#"):
                parts = line.split(":", 1)
                if len(parts) == 2:
                    artifacts.append({
                        "name": parts[0].strip().strip("-").strip(),
                        "description": parts[1].strip(),
                        "type": "unknown",
                    })

        return artifacts[:5]  # Limit to 5

    def _extract_file_references(self, query: str) -> list[str]:
        """Extract file path references from the query."""
        import re

        # Match common file patterns
        patterns = [
            r'[\w/\\.-]+\.(?:csv|tsv|txt|vcf|bam|bed|fastq|fasta|fa|gff|gtf|sam|json|xml|xlsx?|py|r|rmd)',
            r'/[\w/.-]+',  # Unix paths
            r'[A-Za-z]:\\[\w\\.-]+',  # Windows paths
        ]

        files = []
        for pattern in patterns:
            matches = re.findall(pattern, query, re.IGNORECASE)
            files.extend(matches)

        return list(set(files))[:10]  # Unique, limited to 10
