"""
Artifact Storage for intermediate results.

This module provides persistent storage for analysis artifacts including
dataframes, plots, sequences, code, and other intermediate results.
"""

from __future__ import annotations

import hashlib
import json
import os
import pickle
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any

from .types import Artifact, ArtifactType


class ArtifactResult:
    """Result of an artifact operation."""

    def __init__(
        self,
        success: bool,
        message: str,
        artifact: Artifact | None = None,
        artifacts: list[Artifact] | None = None,
        content: Any = None,
    ):
        self.success = success
        self.message = message
        self.artifact = artifact
        self.artifacts = artifacts or []
        self.content = content

    def to_string(self) -> str:
        """Format for Claude."""
        if not self.success:
            return f"Artifact error: {self.message}"

        if self.artifact:
            return (
                f"Artifact saved successfully:\n"
                f"  ID: {self.artifact.id}\n"
                f"  Name: {self.artifact.name}\n"
                f"  Type: {self.artifact.artifact_type.value}\n"
                f"  Path: {self.artifact.file_path}\n"
                f"  Size: {self._format_size(self.artifact.size_bytes)}"
            )

        if self.artifacts:
            lines = [f"Found {len(self.artifacts)} artifact(s):"]
            for art in self.artifacts[:20]:  # Limit display
                lines.append(
                    f"  - [{art.id}] {art.name} ({art.artifact_type.value}) "
                    f"- {art.description[:50]}..."
                )
            if len(self.artifacts) > 20:
                lines.append(f"  ... and {len(self.artifacts) - 20} more")
            return "\n".join(lines)

        if self.content is not None:
            content_str = str(self.content)
            if len(content_str) > 5000:
                content_str = content_str[:5000] + "\n... (truncated)"
            return f"{self.message}\n\n{content_str}"

        return self.message

    @staticmethod
    def _format_size(size_bytes: int) -> str:
        """Format bytes to human-readable size."""
        for unit in ["B", "KB", "MB", "GB"]:
            if size_bytes < 1024:
                return f"{size_bytes:.1f} {unit}"
            size_bytes /= 1024
        return f"{size_bytes:.1f} TB"


class ArtifactStore:
    """Manages persistent storage of analysis artifacts.

    Artifacts are stored in the workspace/artifacts/ directory with a
    JSON index for fast lookups. Each artifact has a unique ID based
    on content hash.
    """

    def __init__(self, artifacts_dir: str, max_size_mb: int = 100):
        """Initialize artifact store.

        Args:
            artifacts_dir: Directory for artifact storage
            max_size_mb: Maximum size per artifact in MB
        """
        self.artifacts_dir = Path(artifacts_dir)
        self.artifacts_dir.mkdir(parents=True, exist_ok=True)
        self.max_size_bytes = max_size_mb * 1024 * 1024
        self.index_file = self.artifacts_dir / "index.json"
        self._index: dict[str, Artifact] = {}
        self._load_index()

    def _load_index(self) -> None:
        """Load artifact index from disk."""
        if self.index_file.exists():
            try:
                with open(self.index_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self._index = {
                        k: Artifact.from_dict(v) for k, v in data.items()
                    }
            except (json.JSONDecodeError, KeyError) as e:
                print(f"Warning: Could not load artifact index: {e}")
                self._index = {}

    def _save_index(self) -> None:
        """Save artifact index to disk."""
        data = {k: v.to_dict() for k, v in self._index.items()}
        with open(self.index_file, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, default=str)

    def _generate_id(self, content: bytes | str, name: str) -> str:
        """Generate unique ID based on content hash."""
        if isinstance(content, str):
            content = content.encode("utf-8")
        content_hash = hashlib.sha256(content).hexdigest()[:12]
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        # Sanitize name for filesystem
        safe_name = "".join(c if c.isalnum() else "_" for c in name[:20])
        return f"{safe_name}_{timestamp}_{content_hash}"

    def _get_extension(self, artifact_type: ArtifactType) -> str:
        """Get file extension for artifact type."""
        extensions = {
            ArtifactType.DATAFRAME: ".csv",
            ArtifactType.PLOT: ".png",
            ArtifactType.SEQUENCE: ".fasta",
            ArtifactType.CODE: ".py",
            ArtifactType.ANALYSIS_RESULT: ".json",
            ArtifactType.ALIGNMENT: ".aln",
            ArtifactType.STRUCTURE: ".pdb",
            ArtifactType.TREE: ".nwk",
            ArtifactType.NETWORK: ".json",
            ArtifactType.TABLE: ".tsv",
            ArtifactType.TEXT: ".txt",
            ArtifactType.JSON: ".json",
            ArtifactType.OTHER: ".dat",
        }
        return extensions.get(artifact_type, ".dat")

    def save_artifact(
        self,
        name: str,
        content: Any,
        artifact_type: str | ArtifactType,
        description: str,
        tags: list[str] | None = None,
        source_tool: str = "",
        source_query: str = "",
        metadata: dict[str, Any] | None = None,
    ) -> ArtifactResult:
        """Save an artifact to storage.

        Args:
            name: Human-readable name for the artifact
            content: The artifact content (string, bytes, dict, or object)
            artifact_type: Type of artifact (see ArtifactType enum)
            description: Description of what this artifact contains
            tags: Optional tags for categorization
            source_tool: Tool that generated this artifact
            source_query: Original query that led to this artifact
            metadata: Additional metadata

        Returns:
            ArtifactResult with success status and artifact info
        """
        # Convert string type to enum
        if isinstance(artifact_type, str):
            try:
                artifact_type = ArtifactType(artifact_type)
            except ValueError:
                artifact_type = ArtifactType.OTHER

        # Serialize content based on type
        try:
            content_bytes, serialization = self._serialize_content(
                content, artifact_type
            )
        except Exception as e:
            return ArtifactResult(
                success=False,
                message=f"Failed to serialize content: {e}",
            )

        # Check size limit
        if len(content_bytes) > self.max_size_bytes:
            return ArtifactResult(
                success=False,
                message=(
                    f"Artifact size ({len(content_bytes) / 1024 / 1024:.1f} MB) "
                    f"exceeds limit ({self.max_size_bytes / 1024 / 1024:.1f} MB)"
                ),
            )

        # Generate ID and path
        artifact_id = self._generate_id(content_bytes, name)
        extension = self._get_extension(artifact_type)
        file_path = self.artifacts_dir / f"{artifact_id}{extension}"

        # Save to disk
        try:
            if serialization == "binary":
                with open(file_path, "wb") as f:
                    f.write(content_bytes)
            else:
                with open(file_path, "w", encoding="utf-8") as f:
                    f.write(content_bytes.decode("utf-8"))
        except Exception as e:
            return ArtifactResult(
                success=False,
                message=f"Failed to write artifact: {e}",
            )

        # Create artifact record
        artifact = Artifact(
            id=artifact_id,
            name=name,
            artifact_type=artifact_type,
            description=description,
            file_path=str(file_path),
            tags=tags or [],
            source_tool=source_tool,
            source_query=source_query,
            metadata=metadata or {},
            size_bytes=len(content_bytes),
        )

        # Update index
        self._index[artifact_id] = artifact
        self._save_index()

        return ArtifactResult(
            success=True,
            message="Artifact saved successfully",
            artifact=artifact,
        )

    def _serialize_content(
        self, content: Any, artifact_type: ArtifactType
    ) -> tuple[bytes, str]:
        """Serialize content based on type.

        Returns:
            Tuple of (bytes, serialization_method)
        """
        # Handle bytes directly
        if isinstance(content, bytes):
            return content, "binary"

        # Handle strings
        if isinstance(content, str):
            return content.encode("utf-8"), "text"

        # Handle dicts/lists as JSON
        if isinstance(content, (dict, list)):
            return json.dumps(content, indent=2, default=str).encode("utf-8"), "text"

        # Try to handle pandas DataFrames
        if hasattr(content, "to_csv"):
            return content.to_csv(index=False).encode("utf-8"), "text"

        # Try to handle matplotlib figures
        if hasattr(content, "savefig"):
            import io
            buf = io.BytesIO()
            content.savefig(buf, format="png", dpi=150, bbox_inches="tight")
            return buf.getvalue(), "binary"

        # Fallback to pickle
        return pickle.dumps(content), "binary"

    def get_artifact(self, artifact_id: str) -> ArtifactResult:
        """Get artifact metadata by ID.

        Args:
            artifact_id: Artifact identifier

        Returns:
            ArtifactResult with artifact info
        """
        if artifact_id not in self._index:
            return ArtifactResult(
                success=False,
                message=f"Artifact not found: {artifact_id}",
            )

        artifact = self._index[artifact_id]
        artifact.update_access()
        self._save_index()

        return ArtifactResult(
            success=True,
            message="Artifact found",
            artifact=artifact,
        )

    def read_artifact(self, artifact_id: str) -> ArtifactResult:
        """Read artifact content from disk.

        Args:
            artifact_id: Artifact identifier

        Returns:
            ArtifactResult with content
        """
        if artifact_id not in self._index:
            return ArtifactResult(
                success=False,
                message=f"Artifact not found: {artifact_id}",
            )

        artifact = self._index[artifact_id]
        file_path = Path(artifact.file_path)

        if not file_path.exists():
            return ArtifactResult(
                success=False,
                message=f"Artifact file missing: {file_path}",
            )

        try:
            # Try text first
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    content = f.read()
            except UnicodeDecodeError:
                # Fall back to binary
                with open(file_path, "rb") as f:
                    content = f.read()

            artifact.update_access()
            self._save_index()

            return ArtifactResult(
                success=True,
                message=f"Content of artifact '{artifact.name}':",
                content=content,
            )

        except Exception as e:
            return ArtifactResult(
                success=False,
                message=f"Failed to read artifact: {e}",
            )

    def find_artifacts(
        self,
        query: str | None = None,
        artifact_type: str | ArtifactType | None = None,
        tags: list[str] | None = None,
        source_tool: str | None = None,
        limit: int = 20,
    ) -> ArtifactResult:
        """Search for artifacts matching criteria.

        Args:
            query: Search in name and description
            artifact_type: Filter by type
            tags: Filter by tags (any match)
            source_tool: Filter by source tool
            limit: Maximum results

        Returns:
            ArtifactResult with matching artifacts
        """
        # Convert string type to enum
        if isinstance(artifact_type, str):
            try:
                artifact_type = ArtifactType(artifact_type)
            except ValueError:
                artifact_type = None

        results = []
        for artifact in self._index.values():
            # Filter by type
            if artifact_type and artifact.artifact_type != artifact_type:
                continue

            # Filter by source tool
            if source_tool and artifact.source_tool != source_tool:
                continue

            # Filter by tags
            if tags and not any(t in artifact.tags for t in tags):
                continue

            # Search query
            if query:
                query_lower = query.lower()
                searchable = (
                    f"{artifact.name} {artifact.description} "
                    f"{' '.join(artifact.tags)}"
                ).lower()
                if query_lower not in searchable:
                    continue

            results.append(artifact)

        # Sort by last accessed (most recent first)
        results.sort(key=lambda a: a.last_accessed, reverse=True)
        results = results[:limit]

        if not results:
            return ArtifactResult(
                success=True,
                message="No artifacts found matching criteria",
                artifacts=[],
            )

        return ArtifactResult(
            success=True,
            message=f"Found {len(results)} artifact(s)",
            artifacts=results,
        )

    def list_artifacts(
        self,
        artifact_type: str | ArtifactType | None = None,
        limit: int = 50,
    ) -> ArtifactResult:
        """List all artifacts, optionally filtered by type.

        Args:
            artifact_type: Filter by type
            limit: Maximum results

        Returns:
            ArtifactResult with artifacts list
        """
        return self.find_artifacts(artifact_type=artifact_type, limit=limit)

    def delete_artifact(self, artifact_id: str) -> ArtifactResult:
        """Delete an artifact.

        Args:
            artifact_id: Artifact identifier

        Returns:
            ArtifactResult with status
        """
        if artifact_id not in self._index:
            return ArtifactResult(
                success=False,
                message=f"Artifact not found: {artifact_id}",
            )

        artifact = self._index[artifact_id]
        file_path = Path(artifact.file_path)

        # Delete file
        if file_path.exists():
            try:
                file_path.unlink()
            except Exception as e:
                return ArtifactResult(
                    success=False,
                    message=f"Failed to delete artifact file: {e}",
                )

        # Remove from index
        del self._index[artifact_id]
        self._save_index()

        return ArtifactResult(
            success=True,
            message=f"Artifact '{artifact.name}' deleted",
        )

    def get_stats(self) -> dict[str, Any]:
        """Get storage statistics.

        Returns:
            Dictionary with storage stats
        """
        total_size = sum(a.size_bytes for a in self._index.values())
        type_counts = {}
        for artifact in self._index.values():
            t = artifact.artifact_type.value
            type_counts[t] = type_counts.get(t, 0) + 1

        return {
            "total_artifacts": len(self._index),
            "total_size_bytes": total_size,
            "total_size_mb": total_size / 1024 / 1024,
            "by_type": type_counts,
        }
