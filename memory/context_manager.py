"""
Context Manager for unified memory orchestration.

This module provides the ContextManager class that orchestrates all memory
subsystems (RAG, summaries, knowledge graph, artifacts) and assembles
enhanced context for Claude with token budgets.
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, TYPE_CHECKING

from .config import MemoryConfig
from .types import estimate_tokens, truncate_to_tokens

if TYPE_CHECKING:
    import anthropic


class ContextManagerResult:
    """Result of a context manager operation."""

    def __init__(
        self,
        success: bool,
        message: str,
        context: str = "",
        stats: dict[str, Any] | None = None,
    ):
        self.success = success
        self.message = message
        self.context = context
        self.stats = stats or {}

    def to_string(self) -> str:
        """Format for display."""
        if not self.success:
            return f"Context error: {self.message}"
        return self.message


class ContextManager:
    """Orchestrates all memory subsystems.

    Provides a unified interface for:
    - Getting enhanced context for Claude calls
    - Updating memory after tool executions
    - Triggering summarization
    - Managing session state
    """

    def __init__(
        self,
        config: MemoryConfig,
        client: "anthropic.Anthropic",
    ):
        """Initialize context manager.

        Args:
            config: Memory configuration
            client: Anthropic client for summarization
        """
        self.config = config
        self.client = client
        self.session_id = config.session_id or str(uuid.uuid4())

        # Ensure directories exist
        config.ensure_directories()

        # Initialize subsystems lazily
        self._vector_store = None
        self._summarizer = None
        self._knowledge_graph = None
        self._artifact_store = None

        # Session state
        self._tools_used_this_session: list[str] = []
        self._rounds_since_summary = 0
        self._pending_tool_results: list[dict] = []

    @property
    def vector_store(self):
        """Lazy initialization of vector store."""
        if self._vector_store is None and self.config.enable_rag:
            from .vector_store import VectorStore
            self._vector_store = VectorStore(
                persist_dir=self.config.chroma_persist_dir,
                collection_name=self.config.rag_collection_name,
                embedding_model=self.config.embedding_model,
                max_results=self.config.max_rag_results,
                similarity_threshold=self.config.similarity_threshold,
            )
        return self._vector_store

    @property
    def summarizer(self):
        """Lazy initialization of summarizer."""
        if self._summarizer is None and self.config.enable_summaries:
            from .summarizer import SessionSummarizer
            self._summarizer = SessionSummarizer(
                summaries_file=self.config.summaries_file,
                client=self.client,
                summary_after_rounds=self.config.summary_after_rounds,
                summary_model=self.config.summary_model,
                max_summary_tokens=self.config.max_summary_tokens,
            )
        return self._summarizer

    @property
    def knowledge_graph(self):
        """Lazy initialization of knowledge graph."""
        if self._knowledge_graph is None and self.config.enable_knowledge_graph:
            from .knowledge_graph import KnowledgeGraph
            self._knowledge_graph = KnowledgeGraph(
                kg_file=self.config.kg_file,
                max_entities=self.config.max_entities,
                max_relationships=self.config.max_relationships,
                auto_extract=self.config.auto_extract_entities,
            )
        return self._knowledge_graph

    @property
    def artifact_store(self):
        """Lazy initialization of artifact store."""
        if self._artifact_store is None and self.config.enable_artifacts:
            from .artifacts import ArtifactStore
            self._artifact_store = ArtifactStore(
                artifacts_dir=self.config.artifacts_dir,
                max_size_mb=self.config.max_artifact_size_mb,
            )
        return self._artifact_store

    def get_enhanced_context(
        self,
        user_message: str,
        messages: list[dict],
        round_num: int,
    ) -> str:
        """Build enhanced context for Claude.

        Assembles relevant context from all memory subsystems respecting
        token budgets:
        - RAG results: ~20k tokens
        - Summaries: ~10k tokens
        - Knowledge graph: ~5k tokens

        Args:
            user_message: Current user query
            messages: Conversation history
            round_num: Current round number

        Returns:
            Formatted context string to inject
        """
        if not self.config.enable_memory:
            return ""

        context_parts = []
        total_tokens = 0

        # 1. RAG Context - semantic search over past analyses
        if self.config.enable_rag and self.vector_store:
            rag_context = self._get_rag_context(
                user_message,
                max_tokens=self.config.rag_context_tokens,
            )
            if rag_context:
                context_parts.append(rag_context)
                total_tokens += estimate_tokens(rag_context)

        # 2. Summary Context - compressed conversation history
        if self.config.enable_summaries and self.summarizer:
            summary_context = self._get_summary_context(
                max_tokens=self.config.summary_context_tokens,
            )
            if summary_context:
                context_parts.append(summary_context)
                total_tokens += estimate_tokens(summary_context)

        # 3. Knowledge Graph Context - relevant entities
        if self.config.enable_knowledge_graph and self.knowledge_graph:
            kg_context = self._get_kg_context(
                user_message,
                max_tokens=self.config.kg_context_tokens,
            )
            if kg_context:
                context_parts.append(kg_context)
                total_tokens += estimate_tokens(kg_context)

        if not context_parts:
            return ""

        # Assemble final context
        header = (
            f"## Memory Context (Session: {self.session_id[:8]}, "
            f"Round: {round_num})\n\n"
        )
        return header + "\n\n---\n\n".join(context_parts)

    def _get_rag_context(self, query: str, max_tokens: int) -> str:
        """Get relevant context from vector store."""
        if not self.vector_store or not self.vector_store.is_available():
            return ""

        result = self.vector_store.search(
            query=query,
            max_results=self.config.max_rag_results,
        )

        if not result.success or not result.results:
            return ""

        lines = ["## Relevant Past Analyses\n"]
        current_tokens = estimate_tokens(lines[0])

        for i, rag_result in enumerate(result.results, 1):
            result_text = (
                f"### Memory {i} (similarity: {rag_result.similarity:.2f})\n"
                f"{rag_result.content}\n"
            )

            result_tokens = estimate_tokens(result_text)
            if current_tokens + result_tokens > max_tokens:
                # Truncate this result
                remaining_tokens = max_tokens - current_tokens - 100
                if remaining_tokens > 200:
                    truncated = truncate_to_tokens(
                        rag_result.content, remaining_tokens
                    )
                    lines.append(
                        f"### Memory {i} (similarity: {rag_result.similarity:.2f})\n"
                        f"{truncated}\n"
                    )
                break

            lines.append(result_text)
            current_tokens += result_tokens

        return "\n".join(lines)

    def _get_summary_context(self, max_tokens: int) -> str:
        """Get context from session summaries."""
        if not self.summarizer:
            return ""

        summaries = self.summarizer.get_context_summaries(
            session_id=self.session_id,
            max_summaries=10,
        )

        if not summaries:
            # Try getting summaries from other sessions
            summaries = self.summarizer.get_context_summaries(
                session_id=None,
                max_summaries=5,
            )

        if not summaries:
            return ""

        return self.summarizer.format_summaries_for_context(
            summaries, max_tokens
        )

    def _get_kg_context(self, query: str, max_tokens: int) -> str:
        """Get context from knowledge graph."""
        if not self.knowledge_graph:
            return ""

        # Extract potential entity names from query
        words = query.split()
        relevant_entities = []
        for word in words:
            if len(word) >= 2:
                result = self.knowledge_graph.find_entities(
                    query=word, limit=3
                )
                if result.entities:
                    relevant_entities.extend(
                        [e.name for e in result.entities]
                    )

        return self.knowledge_graph.format_for_context(
            relevant_entities=relevant_entities[:10] if relevant_entities else None,
            max_tokens=max_tokens,
        )

    def on_tool_result(
        self,
        tool_name: str,
        tool_input: dict[str, Any],
        result: str | dict | Any,
    ) -> None:
        """Update memory after tool execution.

        Called after each tool execution to:
        - Index result in vector store
        - Extract entities for knowledge graph
        - Track tools used

        Args:
            tool_name: Name of the tool
            tool_input: Tool input parameters
            result: Tool output (string or dict)
        """
        if not self.config.enable_memory:
            return

        # Convert result to string if needed
        if isinstance(result, dict):
            result_str = json.dumps(result, indent=2, default=str)
        elif not isinstance(result, str):
            result_str = str(result)
        else:
            result_str = result

        # Track tool usage
        if tool_name not in self._tools_used_this_session:
            self._tools_used_this_session.append(tool_name)

        # Store for batch processing
        self._pending_tool_results.append({
            "tool_name": tool_name,
            "tool_input": tool_input,
            "result": result_str,
            "timestamp": datetime.now().isoformat(),
        })

        # Index in vector store
        if self.config.enable_rag and self.vector_store:
            # Only index substantial results
            if len(result_str) >= 100:
                self.vector_store.add_tool_result(
                    tool_name=tool_name,
                    tool_input=tool_input,
                    result=result_str,
                    session_id=self.session_id,
                )

        # Extract entities for knowledge graph
        if self.config.enable_knowledge_graph and self.knowledge_graph:
            self.knowledge_graph.extract_entities_from_text(
                text=result_str,
                source=tool_name,
            )

    def on_round_complete(
        self,
        messages: list[dict],
        round_num: int,
        tools_used: list[str],
    ) -> None:
        """Handle end of conversation round.

        Called at the end of each round to:
        - Check if summarization is needed
        - Update session state

        Args:
            messages: Conversation history
            round_num: Completed round number
            tools_used: Tools used this round
        """
        if not self.config.enable_memory:
            return

        self._rounds_since_summary += 1

        # Check for summarization trigger
        if (
            self.config.enable_summaries
            and self.summarizer
            and self.summarizer.should_summarize(round_num)
        ):
            self._trigger_summarization(messages, round_num)

        # Clear pending results
        self._pending_tool_results = []

    def _trigger_summarization(
        self,
        messages: list[dict],
        current_round: int,
    ) -> None:
        """Trigger conversation summarization."""
        if not self.summarizer:
            return

        # Calculate segment to summarize
        start_round = current_round - self.config.summary_after_rounds + 1
        start_round = max(1, start_round)

        # Get messages for this segment (approximate)
        segment_size = min(
            len(messages),
            self.config.summary_after_rounds * 4,  # ~4 messages per round
        )
        segment_messages = messages[-segment_size:]

        result = self.summarizer.summarize_segment(
            messages=segment_messages,
            start_round=start_round,
            end_round=current_round,
            session_id=self.session_id,
            tools_used=self._tools_used_this_session.copy(),
        )

        if result.success:
            self._rounds_since_summary = 0

    def on_analysis_complete(
        self,
        query: str,
        result: str,
        tools_used: list[str],
    ) -> None:
        """Handle completed analysis (final response).

        Called when the agent returns a final response to index
        the complete analysis.

        Args:
            query: Original user query
            result: Final analysis result
            tools_used: All tools used
        """
        if not self.config.enable_memory:
            return

        # Index complete analysis in vector store
        if self.config.enable_rag and self.vector_store:
            self.vector_store.add_analysis_result(
                query=query,
                result=result,
                tools_used=tools_used,
                session_id=self.session_id,
            )

    def compact_messages(
        self,
        messages: list[dict],
        max_tokens: int = 50000,
    ) -> list[dict]:
        """Compact message history to fit within token budget.

        Replaces older message content with summaries when the
        total token count exceeds the budget.

        Args:
            messages: Full message history
            max_tokens: Target token budget

        Returns:
            Compacted message list
        """
        if not messages:
            return messages

        # Estimate current token count
        total_tokens = sum(
            estimate_tokens(self._get_message_text(m))
            for m in messages
        )

        if total_tokens <= max_tokens:
            return messages

        # Need to compact - keep recent messages, summarize older ones
        compacted = []
        recent_count = min(len(messages), 10)  # Keep last 10 messages
        older_messages = messages[:-recent_count] if len(messages) > recent_count else []
        recent_messages = messages[-recent_count:]

        # Create summary of older messages if we have summarizer
        if older_messages and self.summarizer:
            older_text = "\n".join(
                self._get_message_text(m) for m in older_messages
            )
            older_tokens = estimate_tokens(older_text)

            if older_tokens > 1000:
                # Worth summarizing
                compacted.append({
                    "role": "user",
                    "content": (
                        f"[Previous conversation ({len(older_messages)} messages) "
                        f"summarized - see memory context for details]"
                    ),
                })
            else:
                # Just include older messages
                compacted.extend(older_messages)
        elif older_messages:
            # Truncate older messages
            for msg in older_messages:
                text = self._get_message_text(msg)
                if len(text) > 500:
                    if isinstance(msg.get("content"), str):
                        msg = msg.copy()
                        msg["content"] = text[:500] + "... [truncated]"
                compacted.append(msg)

        # Add recent messages
        compacted.extend(recent_messages)

        return compacted

    def _get_message_text(self, message: dict) -> str:
        """Extract text content from a message."""
        content = message.get("content", "")
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            parts = []
            for block in content:
                if isinstance(block, dict):
                    if block.get("type") == "text":
                        parts.append(block.get("text", ""))
                    elif block.get("type") == "tool_result":
                        parts.append(str(block.get("content", ""))[:200])
                elif hasattr(block, "type") and block.type == "text":
                    parts.append(block.text)
            return "\n".join(parts)
        return str(content)

    # ─── Tool Interface Methods ───────────────────────────────────────

    def search_memory(self, query: str, max_results: int = 5) -> str:
        """Search memory (for memory_search tool).

        Args:
            query: Search query
            max_results: Maximum results

        Returns:
            Formatted search results
        """
        if not self.config.enable_rag or not self.vector_store:
            return "Memory search not available (RAG disabled)"

        result = self.vector_store.search(query=query, max_results=max_results)
        return result.to_string()

    def save_artifact(
        self,
        name: str,
        content: Any,
        artifact_type: str,
        description: str,
        tags: list[str] | None = None,
    ) -> str:
        """Save an artifact (for memory_save_artifact tool).

        Args:
            name: Artifact name
            content: Artifact content
            artifact_type: Type of artifact
            description: Description
            tags: Optional tags

        Returns:
            Result message
        """
        if not self.config.enable_artifacts or not self.artifact_store:
            return "Artifact storage not available (disabled)"

        result = self.artifact_store.save_artifact(
            name=name,
            content=content,
            artifact_type=artifact_type,
            description=description,
            tags=tags,
            source_tool="manual",
            source_query="",
        )
        return result.to_string()

    def list_artifacts(
        self,
        artifact_type: str | None = None,
        query: str | None = None,
    ) -> str:
        """List artifacts (for memory_list_artifacts tool).

        Args:
            artifact_type: Filter by type
            query: Search query

        Returns:
            Formatted artifact list
        """
        if not self.config.enable_artifacts or not self.artifact_store:
            return "Artifact storage not available (disabled)"

        result = self.artifact_store.find_artifacts(
            query=query,
            artifact_type=artifact_type,
        )
        return result.to_string()

    def get_entities(
        self,
        query: str | None = None,
        entity_type: str | None = None,
        include_relationships: bool = False,
    ) -> str:
        """Query knowledge graph (for memory_get_entities tool).

        Args:
            query: Search query
            entity_type: Filter by type
            include_relationships: Include relationships

        Returns:
            Formatted entity list
        """
        if not self.config.enable_knowledge_graph or not self.knowledge_graph:
            return "Knowledge graph not available (disabled)"

        result = self.knowledge_graph.find_entities(
            query=query,
            entity_type=entity_type,
        )

        output = result.to_string()

        # Optionally include relationships
        if include_relationships and result.entities:
            for entity in result.entities[:5]:
                neighbors = self.knowledge_graph.get_neighbors(entity.name, limit=5)
                if neighbors.relationships:
                    output += f"\n\nRelationships for {entity.name}:\n"
                    for rel in neighbors.relationships:
                        output += f"  {rel.source_id} --[{rel.relationship_type.value}]--> {rel.target_id}\n"

        return output

    def read_artifact(self, artifact_id: str) -> str:
        """Read artifact content (for reading artifacts).

        Args:
            artifact_id: Artifact identifier

        Returns:
            Artifact content
        """
        if not self.config.enable_artifacts or not self.artifact_store:
            return "Artifact storage not available (disabled)"

        result = self.artifact_store.read_artifact(artifact_id)
        return result.to_string()

    # ─── Statistics and Management ────────────────────────────────────

    def get_stats(self) -> dict[str, Any]:
        """Get memory system statistics.

        Returns:
            Dictionary with stats from all subsystems
        """
        stats = {
            "session_id": self.session_id,
            "config": self.config.to_dict(),
            "tools_used": self._tools_used_this_session,
            "rounds_since_summary": self._rounds_since_summary,
        }

        if self.vector_store:
            stats["vector_store"] = self.vector_store.get_stats()

        if self.summarizer:
            stats["summarizer"] = self.summarizer.get_stats()

        if self.knowledge_graph:
            stats["knowledge_graph"] = self.knowledge_graph.get_stats()

        if self.artifact_store:
            stats["artifact_store"] = self.artifact_store.get_stats()

        return stats

    def clear_session(self) -> str:
        """Clear all memory for current session.

        Returns:
            Status message
        """
        cleared = []

        if self.summarizer:
            self.summarizer.clear_session(self.session_id)
            cleared.append("summaries")

        self._tools_used_this_session = []
        self._rounds_since_summary = 0
        self._pending_tool_results = []
        cleared.append("session state")

        return f"Cleared: {', '.join(cleared)}"

    def clear_all(self) -> str:
        """Clear all memory (dangerous!).

        Returns:
            Status message
        """
        cleared = []

        if self.vector_store:
            self.vector_store.clear()
            cleared.append("vector store")

        if self.knowledge_graph:
            self.knowledge_graph.clear()
            cleared.append("knowledge graph")

        # Note: artifacts are not cleared automatically

        self._tools_used_this_session = []
        self._rounds_since_summary = 0
        self._pending_tool_results = []
        cleared.append("session state")

        return f"Cleared: {', '.join(cleared)}"
