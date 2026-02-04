"""
Memory-specific configuration for the memory subsystem.

This module provides configuration management for all memory components,
with support for environment variables and sensible defaults.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


def _get_bool_env(key: str, default: bool = True) -> bool:
    """Get boolean from environment variable."""
    value = os.getenv(key, str(default)).lower()
    return value in ("true", "1", "yes", "on")


def _get_int_env(key: str, default: int) -> int:
    """Get integer from environment variable."""
    try:
        return int(os.getenv(key, str(default)))
    except ValueError:
        return default


def _get_float_env(key: str, default: float) -> float:
    """Get float from environment variable."""
    try:
        return float(os.getenv(key, str(default)))
    except ValueError:
        return default


@dataclass
class MemoryConfig:
    """Configuration for the memory subsystem.

    All settings can be overridden via environment variables with the
    BIOAGENT_ prefix. For example, BIOAGENT_ENABLE_RAG=false.
    """

    # ── Master Toggle ─────────────────────────────────────────────────
    enable_memory: bool = True

    # ── Component Toggles ─────────────────────────────────────────────
    enable_rag: bool = True
    enable_summaries: bool = True
    enable_knowledge_graph: bool = True
    enable_artifacts: bool = True

    # ── Storage Paths ─────────────────────────────────────────────────
    memory_dir: str = ""  # Base directory for all memory storage
    chroma_persist_dir: str = ""  # ChromaDB persistence directory
    artifacts_dir: str = ""  # Artifact storage directory
    kg_file: str = ""  # Knowledge graph JSON file
    summaries_file: str = ""  # Session summaries JSON file

    # ── RAG Configuration ─────────────────────────────────────────────
    embedding_model: str = "all-MiniLM-L6-v2"
    max_rag_results: int = 5
    similarity_threshold: float = 0.7
    rag_collection_name: str = "bioagent_memory"

    # ── Summarization Configuration ───────────────────────────────────
    summary_after_rounds: int = 5  # Trigger summarization every N rounds
    summary_model: str = "claude-sonnet-4-20250514"  # Model for summaries
    max_summary_tokens: int = 1000  # Max tokens per summary

    # ── Knowledge Graph Configuration ─────────────────────────────────
    max_entities: int = 10000
    max_relationships: int = 50000
    auto_extract_entities: bool = True

    # ── Artifact Configuration ────────────────────────────────────────
    max_artifact_size_mb: int = 100  # Max size per artifact
    max_total_artifacts_gb: int = 10  # Max total artifact storage

    # ── Context Assembly Budget ───────────────────────────────────────
    rag_context_tokens: int = 20000
    summary_context_tokens: int = 10000
    kg_context_tokens: int = 5000

    # ── Session Configuration ─────────────────────────────────────────
    session_id: str = ""  # Current session identifier

    def __post_init__(self):
        """Initialize derived paths after dataclass creation."""
        if self.memory_dir:
            self._initialize_paths()

    def _initialize_paths(self) -> None:
        """Set up all storage paths based on memory_dir."""
        memory_path = Path(self.memory_dir)

        if not self.chroma_persist_dir:
            self.chroma_persist_dir = str(memory_path / "chroma")

        if not self.artifacts_dir:
            self.artifacts_dir = str(memory_path / "artifacts")

        if not self.kg_file:
            self.kg_file = str(memory_path / "knowledge_graph.json")

        if not self.summaries_file:
            self.summaries_file = str(memory_path / "summaries.json")

    @classmethod
    def from_env(cls, workspace_dir: str | None = None) -> MemoryConfig:
        """Create configuration from environment variables.

        Args:
            workspace_dir: Base workspace directory. Memory will be stored
                          in {workspace_dir}/memory/

        Returns:
            MemoryConfig instance with values from environment
        """
        # Determine memory directory
        if workspace_dir:
            memory_dir = str(Path(workspace_dir) / "memory")
        else:
            memory_dir = os.getenv(
                "BIOAGENT_MEMORY_DIR",
                str(Path.home() / ".bioagent" / "memory")
            )

        config = cls(
            # Master toggle
            enable_memory=_get_bool_env("BIOAGENT_ENABLE_MEMORY", True),

            # Component toggles
            enable_rag=_get_bool_env("BIOAGENT_ENABLE_RAG", True),
            enable_summaries=_get_bool_env("BIOAGENT_ENABLE_SUMMARIES", True),
            enable_knowledge_graph=_get_bool_env("BIOAGENT_ENABLE_KG", True),
            enable_artifacts=_get_bool_env("BIOAGENT_ENABLE_ARTIFACTS", True),

            # Storage paths
            memory_dir=memory_dir,
            chroma_persist_dir=os.getenv("BIOAGENT_CHROMA_DIR", ""),
            artifacts_dir=os.getenv("BIOAGENT_ARTIFACTS_DIR", ""),
            kg_file=os.getenv("BIOAGENT_KG_FILE", ""),
            summaries_file=os.getenv("BIOAGENT_SUMMARIES_FILE", ""),

            # RAG configuration
            embedding_model=os.getenv(
                "BIOAGENT_EMBEDDING_MODEL", "all-MiniLM-L6-v2"
            ),
            max_rag_results=_get_int_env("BIOAGENT_MAX_RAG_RESULTS", 5),
            similarity_threshold=_get_float_env(
                "BIOAGENT_SIMILARITY_THRESHOLD", 0.7
            ),
            rag_collection_name=os.getenv(
                "BIOAGENT_RAG_COLLECTION", "bioagent_memory"
            ),

            # Summarization configuration
            summary_after_rounds=_get_int_env("BIOAGENT_SUMMARY_ROUNDS", 5),
            summary_model=os.getenv(
                "BIOAGENT_SUMMARY_MODEL", "claude-sonnet-4-20250514"
            ),
            max_summary_tokens=_get_int_env("BIOAGENT_MAX_SUMMARY_TOKENS", 1000),

            # Knowledge graph configuration
            max_entities=_get_int_env("BIOAGENT_MAX_ENTITIES", 10000),
            max_relationships=_get_int_env("BIOAGENT_MAX_RELATIONSHIPS", 50000),
            auto_extract_entities=_get_bool_env(
                "BIOAGENT_AUTO_EXTRACT_ENTITIES", True
            ),

            # Artifact configuration
            max_artifact_size_mb=_get_int_env("BIOAGENT_MAX_ARTIFACT_SIZE_MB", 100),
            max_total_artifacts_gb=_get_int_env(
                "BIOAGENT_MAX_TOTAL_ARTIFACTS_GB", 10
            ),

            # Context budget
            rag_context_tokens=_get_int_env("BIOAGENT_RAG_CONTEXT_TOKENS", 20000),
            summary_context_tokens=_get_int_env(
                "BIOAGENT_SUMMARY_CONTEXT_TOKENS", 10000
            ),
            kg_context_tokens=_get_int_env("BIOAGENT_KG_CONTEXT_TOKENS", 5000),

            # Session
            session_id=os.getenv("BIOAGENT_SESSION_ID", ""),
        )

        # Initialize derived paths
        config._initialize_paths()

        return config

    def ensure_directories(self) -> None:
        """Create all necessary directories."""
        Path(self.memory_dir).mkdir(parents=True, exist_ok=True)
        Path(self.chroma_persist_dir).mkdir(parents=True, exist_ok=True)
        Path(self.artifacts_dir).mkdir(parents=True, exist_ok=True)

    def validate(self) -> list[str]:
        """Validate configuration and return list of issues."""
        issues = []

        if not self.enable_memory:
            return issues  # Nothing to validate if memory is disabled

        # Check memory directory
        if not self.memory_dir:
            issues.append("memory_dir is not set")

        # Validate token budgets
        total_budget = (
            self.rag_context_tokens +
            self.summary_context_tokens +
            self.kg_context_tokens
        )
        if total_budget > 100000:
            issues.append(
                f"Total context budget ({total_budget}) exceeds 100k tokens"
            )

        # Validate thresholds
        if not 0.0 <= self.similarity_threshold <= 1.0:
            issues.append(
                f"similarity_threshold must be 0-1, got {self.similarity_threshold}"
            )

        return issues

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "enable_memory": self.enable_memory,
            "enable_rag": self.enable_rag,
            "enable_summaries": self.enable_summaries,
            "enable_knowledge_graph": self.enable_knowledge_graph,
            "enable_artifacts": self.enable_artifacts,
            "memory_dir": self.memory_dir,
            "embedding_model": self.embedding_model,
            "summary_after_rounds": self.summary_after_rounds,
            "max_rag_results": self.max_rag_results,
            "similarity_threshold": self.similarity_threshold,
        }

    def __str__(self) -> str:
        """Human-readable string representation."""
        components = []
        if self.enable_rag:
            components.append("RAG")
        if self.enable_summaries:
            components.append("Summaries")
        if self.enable_knowledge_graph:
            components.append("KnowledgeGraph")
        if self.enable_artifacts:
            components.append("Artifacts")

        if not self.enable_memory:
            return "MemoryConfig(disabled)"

        return f"MemoryConfig(components=[{', '.join(components)}], dir={self.memory_dir})"
