"""
BioAgent Memory Subsystem

This package provides intelligent memory and context management for long-running
bioinformatics analyses. It includes:

1. **RAG System** (vector_store.py): Vector store for semantic search over past
   analyses using ChromaDB and sentence-transformers.

2. **Session Summaries** (summarizer.py): Auto-summarize completed conversation
   segments to compress history while preserving key information.

3. **Knowledge Graph** (knowledge_graph.py): Track biological entity relationships
   including genes, proteins, variants, pathways, and samples.

4. **Artifact Storage** (artifacts.py): Save intermediate results with metadata
   for later retrieval.

5. **Context Manager** (context_manager.py): Unified interface that orchestrates
   all subsystems and assembles enhanced context for Claude.

Usage:
    from memory import ContextManager, MemoryConfig

    # Initialize with configuration
    config = MemoryConfig.from_env(workspace_dir="/path/to/workspace")
    memory = ContextManager(config, anthropic_client)

    # Get enhanced context before Claude calls
    context = memory.get_enhanced_context(user_message, messages, round_num)

    # Update memory after tool execution
    memory.on_tool_result(tool_name, tool_input, result)

    # Check for summarization at end of round
    memory.on_round_complete(messages, round_num, tools_used)
"""

from .types import (
    # Enums
    EntityType,
    RelationshipType,
    ArtifactType,
    # Dataclasses
    Entity,
    Relationship,
    Artifact,
    SessionSummary,
    RAGResult,
    MemoryStats,
    # Utilities
    serialize_to_json,
    estimate_tokens,
    truncate_to_tokens,
)

from .config import MemoryConfig

# Lazy imports for optional dependencies
def get_vector_store():
    """Get VectorStore class (requires chromadb, sentence-transformers)."""
    from .vector_store import VectorStore
    return VectorStore

def get_summarizer():
    """Get SessionSummarizer class."""
    from .summarizer import SessionSummarizer
    return SessionSummarizer

def get_knowledge_graph():
    """Get KnowledgeGraph class."""
    from .knowledge_graph import KnowledgeGraph
    return KnowledgeGraph

def get_artifact_store():
    """Get ArtifactStore class."""
    from .artifacts import ArtifactStore
    return ArtifactStore

def get_context_manager():
    """Get ContextManager class."""
    from .context_manager import ContextManager
    return ContextManager

# Direct imports for commonly used classes
# These are imported at module level for convenience
try:
    from .artifacts import ArtifactStore
    from .knowledge_graph import KnowledgeGraph
    from .summarizer import SessionSummarizer
    from .context_manager import ContextManager
    # VectorStore has heavy dependencies, keep it lazy
except ImportError:
    # Some components may not be available if dependencies are missing
    pass

__all__ = [
    # Configuration
    "MemoryConfig",
    # Types
    "EntityType",
    "RelationshipType",
    "ArtifactType",
    "Entity",
    "Relationship",
    "Artifact",
    "SessionSummary",
    "RAGResult",
    "MemoryStats",
    # Utilities
    "serialize_to_json",
    "estimate_tokens",
    "truncate_to_tokens",
    # Lazy getters
    "get_vector_store",
    "get_summarizer",
    "get_knowledge_graph",
    "get_artifact_store",
    "get_context_manager",
    # Direct classes (may not be available)
    "ArtifactStore",
    "KnowledgeGraph",
    "SessionSummarizer",
    "ContextManager",
]
