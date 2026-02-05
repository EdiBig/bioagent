"""
Analysis Tracker - Core tracking and management for analysis sessions.

The AnalysisTracker is the central component for:
- Starting and completing analysis sessions
- Registering files to analyses
- Managing directory structures
- Generating manifests
- Searching and filtering analyses
"""

import hashlib
import json
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any

from .models import Analysis, AnalysisStatus, FileRecord, FileType, FileCategory
from .id_generator import IDGenerator, generate_file_id


class AnalysisTracker:
    """
    Central analysis tracking and management.

    Manages the complete lifecycle of analyses: creation, file registration,
    completion, and retrieval.
    """

    def __init__(self, workspace_dir: str, id_prefix: str = "BIO"):
        """
        Initialize the tracker.

        Args:
            workspace_dir: Root workspace directory
            id_prefix: Prefix for analysis IDs
        """
        self.workspace_dir = Path(workspace_dir)
        self.registry_dir = self.workspace_dir / "registry"
        self.projects_dir = self.workspace_dir / "projects"

        # Ensure directories exist
        self.registry_dir.mkdir(parents=True, exist_ok=True)
        self.projects_dir.mkdir(parents=True, exist_ok=True)

        # Initialize ID generator
        self.id_generator = IDGenerator(self.registry_dir, prefix=id_prefix)

        # Registry files
        self._analyses_file = self.registry_dir / "analyses.json"
        self._files_file = self.registry_dir / "files.json"

        # In-memory cache
        self._analyses: dict[str, Analysis] = {}
        self._files: dict[str, FileRecord] = {}

        # Load existing data
        self._load_registry()

    def _load_registry(self) -> None:
        """Load analyses and files from persistent storage."""
        # Load analyses
        if self._analyses_file.exists():
            try:
                with open(self._analyses_file, "r") as f:
                    data = json.load(f)
                    self._analyses = {
                        aid: Analysis.from_dict(a)
                        for aid, a in data.items()
                    }
            except (json.JSONDecodeError, IOError):
                self._analyses = {}
        else:
            self._analyses = {}

        # Load files
        if self._files_file.exists():
            try:
                with open(self._files_file, "r") as f:
                    data = json.load(f)
                    self._files = {
                        fid: FileRecord.from_dict(fr)
                        for fid, fr in data.items()
                    }
            except (json.JSONDecodeError, IOError):
                self._files = {}
        else:
            self._files = {}

    def _save_registry(self) -> None:
        """Save analyses and files to persistent storage."""
        self.registry_dir.mkdir(parents=True, exist_ok=True)

        # Save analyses
        with open(self._analyses_file, "w") as f:
            json.dump(
                {aid: a.to_dict() for aid, a in self._analyses.items()},
                f, indent=2
            )

        # Save files
        with open(self._files_file, "w") as f:
            json.dump(
                {fid: fr.to_dict() for fid, fr in self._files.items()},
                f, indent=2
            )

    # ── Analysis Lifecycle ────────────────────────────────────────────

    def start_analysis(
        self,
        title: str,
        query: str = "",
        description: str = "",
        analysis_type: str = "general",
        project_id: str | None = None,
        tags: list[str] | None = None,
        labels: dict[str, str] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> str:
        """
        Create a new analysis session.

        Args:
            title: Human-readable title for the analysis
            query: Original user query that started this analysis
            description: Detailed description
            analysis_type: Type of analysis (rnaseq, variant, enrichment, etc.)
            project_id: Optional parent project
            tags: List of tags for categorization
            labels: Key-value labels
            metadata: Custom metadata

        Returns:
            Analysis ID (e.g., "BIO-20250205-001")
        """
        # Generate tag from analysis type if provided
        tag = analysis_type if analysis_type != "general" else None
        analysis_id = self.id_generator.generate(tag=tag)

        # Create workspace path
        if project_id:
            workspace_path = str(
                self.projects_dir / project_id / "analyses" / analysis_id
            )
        else:
            workspace_path = str(
                self.projects_dir / "_standalone" / "analyses" / analysis_id
            )

        # Create analysis
        analysis = Analysis(
            id=analysis_id,
            title=title,
            project_id=project_id,
            description=description,
            analysis_type=analysis_type,
            status=AnalysisStatus.IN_PROGRESS,
            query=query,
            tags=tags or [],
            labels=labels or {},
            metadata=metadata or {},
            workspace_path=workspace_path,
        )

        # Create directory structure
        self._create_analysis_structure(analysis_id, workspace_path)

        # Save analysis
        self._analyses[analysis_id] = analysis
        self._save_registry()

        # Save initial manifest
        self._save_analysis_manifest(analysis)

        return analysis_id

    def complete_analysis(
        self,
        analysis_id: str,
        summary: str = "",
        status: str = "completed",
    ) -> bool:
        """
        Mark an analysis as complete.

        Args:
            analysis_id: The analysis to complete
            summary: Final summary of results
            status: Final status ("completed" or "failed")

        Returns:
            True if successful
        """
        analysis = self._analyses.get(analysis_id)
        if not analysis:
            return False

        status_enum = (
            AnalysisStatus.COMPLETED
            if status == "completed"
            else AnalysisStatus.FAILED
        )
        analysis.complete(summary=summary, status=status_enum)

        # Update registry and manifest
        self._save_registry()
        self._save_analysis_manifest(analysis)

        return True

    def get_analysis(self, analysis_id: str) -> Analysis | None:
        """Get an analysis by ID."""
        return self._analyses.get(analysis_id)

    def list_analyses(
        self,
        project_id: str | None = None,
        analysis_type: str | None = None,
        status: str | None = None,
        tags: list[str] | None = None,
        date_from: str | None = None,
        date_to: str | None = None,
        limit: int = 20,
    ) -> list[Analysis]:
        """
        List analyses with filtering.

        Args:
            project_id: Filter by project
            analysis_type: Filter by type
            status: Filter by status
            tags: Filter by tags (any match)
            date_from: Filter by start date (ISO format)
            date_to: Filter by end date (ISO format)
            limit: Maximum results

        Returns:
            List of matching analyses, sorted by creation date (newest first)
        """
        results = list(self._analyses.values())

        # Apply filters
        if project_id:
            results = [a for a in results if a.project_id == project_id]

        if analysis_type:
            results = [a for a in results if a.analysis_type == analysis_type]

        if status:
            status_enum = AnalysisStatus(status)
            results = [a for a in results if a.status == status_enum]

        if tags:
            results = [
                a for a in results
                if any(t in a.tags for t in tags)
            ]

        if date_from:
            results = [a for a in results if a.created_at >= date_from]

        if date_to:
            results = [a for a in results if a.created_at <= date_to]

        # Sort by creation date (newest first)
        results.sort(key=lambda a: a.created_at, reverse=True)

        return results[:limit]

    def update_analysis(
        self,
        analysis_id: str,
        title: str | None = None,
        description: str | None = None,
        tags: list[str] | None = None,
        labels: dict[str, str] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> bool:
        """Update analysis metadata."""
        analysis = self._analyses.get(analysis_id)
        if not analysis:
            return False

        if title is not None:
            analysis.title = title
        if description is not None:
            analysis.description = description
        if tags is not None:
            analysis.tags = tags
        if labels is not None:
            analysis.labels.update(labels)
        if metadata is not None:
            analysis.metadata.update(metadata)

        analysis.updated_at = datetime.now().isoformat()
        self._save_registry()
        self._save_analysis_manifest(analysis)

        return True

    def add_tool_usage(self, analysis_id: str, tool_name: str) -> bool:
        """Record a tool being used in an analysis."""
        analysis = self._analyses.get(analysis_id)
        if not analysis:
            return False

        analysis.add_tool(tool_name)
        self._save_registry()
        return True

    # ── File Management ───────────────────────────────────────────────

    def register_file(
        self,
        analysis_id: str,
        file_path: str,
        file_type: str = "output",
        category: str = "data",
        description: str = "",
        tags: list[str] | None = None,
        source_tool: str | None = None,
        source_query: str | None = None,
        copy_to_workspace: bool = False,
    ) -> str | None:
        """
        Register a file to an analysis.

        Args:
            analysis_id: Parent analysis
            file_path: Path to the file (absolute or relative to workspace)
            file_type: input, output, report, log
            category: figure, table, data, notebook, etc.
            description: File description
            tags: Tags for categorization
            source_tool: Tool that generated this file (for outputs)
            source_query: Query that produced this file
            copy_to_workspace: If True, copy file to analysis workspace

        Returns:
            File ID if successful, None otherwise
        """
        analysis = self._analyses.get(analysis_id)
        if not analysis:
            return None

        # Resolve file path
        path = Path(file_path)
        if not path.is_absolute():
            path = self.workspace_dir / file_path

        if not path.exists():
            # File doesn't exist yet, maybe will be created
            pass

        # Generate file ID
        file_id = generate_file_id(str(path), analysis_id)

        # Determine relative path for storage
        try:
            rel_path = str(path.relative_to(self.workspace_dir))
        except ValueError:
            rel_path = str(path)

        # Copy to workspace if requested
        if copy_to_workspace and path.exists():
            dest_dir = Path(analysis.workspace_path) / self._get_file_subdir(file_type)
            dest_dir.mkdir(parents=True, exist_ok=True)
            dest_path = dest_dir / path.name
            shutil.copy2(path, dest_path)
            rel_path = str(dest_path.relative_to(self.workspace_dir))

        # Get file info
        size_bytes = 0
        md5_hash = ""
        if path.exists():
            size_bytes = path.stat().st_size
            md5_hash = self._compute_md5(path)

        # Create file record
        file_record = FileRecord(
            id=file_id,
            analysis_id=analysis_id,
            file_name=path.name,
            file_path=rel_path,
            file_type=FileType(file_type),
            category=FileCategory(category),
            format=path.suffix.lstrip(".") or "unknown",
            description=description,
            tags=tags or [],
            size_bytes=size_bytes,
            md5=md5_hash,
            source_tool=source_tool,
            source_query=source_query,
        )

        # Update analysis
        if file_type == "input":
            analysis.add_input(file_id)
        else:
            analysis.add_output(file_id)

        # Save
        self._files[file_id] = file_record
        self._save_registry()
        self._save_analysis_manifest(analysis)

        return file_id

    def get_file(self, file_id: str) -> FileRecord | None:
        """Get a file record by ID."""
        return self._files.get(file_id)

    def get_analysis_files(
        self,
        analysis_id: str,
        file_type: str | None = None,
        category: str | None = None,
    ) -> list[FileRecord]:
        """
        Get all files for an analysis.

        Args:
            analysis_id: The analysis ID
            file_type: Optional filter by type (input, output, report)
            category: Optional filter by category (figure, table, data)

        Returns:
            List of matching file records
        """
        files = [
            f for f in self._files.values()
            if f.analysis_id == analysis_id
        ]

        if file_type:
            files = [f for f in files if f.file_type.value == file_type]

        if category:
            files = [f for f in files if f.category.value == category]

        return files

    def _get_file_subdir(self, file_type: str) -> str:
        """Get subdirectory for a file type."""
        type_dirs = {
            "input": "inputs",
            "output": "outputs",
            "report": "reports",
            "log": "logs",
            "intermediate": "intermediate",
        }
        return type_dirs.get(file_type, "outputs")

    def _compute_md5(self, path: Path, chunk_size: int = 8192) -> str:
        """Compute MD5 hash of a file."""
        hash_md5 = hashlib.md5()
        try:
            with open(path, "rb") as f:
                for chunk in iter(lambda: f.read(chunk_size), b""):
                    hash_md5.update(chunk)
            return hash_md5.hexdigest()
        except IOError:
            return ""

    # ── Directory Management ──────────────────────────────────────────

    def get_analysis_path(self, analysis_id: str) -> Path | None:
        """Get workspace path for an analysis."""
        analysis = self._analyses.get(analysis_id)
        if analysis:
            return Path(analysis.workspace_path)
        return None

    def _create_analysis_structure(
        self,
        analysis_id: str,
        workspace_path: str
    ) -> None:
        """Create directory structure for an analysis."""
        base = Path(workspace_path)

        # Create subdirectories
        (base / "inputs").mkdir(parents=True, exist_ok=True)
        (base / "outputs").mkdir(parents=True, exist_ok=True)
        (base / "reports").mkdir(parents=True, exist_ok=True)
        (base / "logs").mkdir(parents=True, exist_ok=True)

    def _save_analysis_manifest(self, analysis: Analysis) -> None:
        """Save analysis manifest to its workspace directory."""
        workspace_path = Path(analysis.workspace_path)
        workspace_path.mkdir(parents=True, exist_ok=True)

        manifest_path = workspace_path / "ANALYSIS_MANIFEST.json"

        # Get file records for this analysis
        input_files = [
            self._files[fid].to_dict()
            for fid in analysis.input_ids
            if fid in self._files
        ]
        output_files = [
            self._files[fid].to_dict()
            for fid in analysis.output_ids
            if fid in self._files
        ]

        # Build manifest
        manifest = {
            "id": analysis.id,
            "title": analysis.title,
            "description": analysis.description,
            "analysis_type": analysis.analysis_type,
            "status": analysis.status.value,
            "project_id": analysis.project_id,
            "created_at": analysis.created_at,
            "updated_at": analysis.updated_at,
            "completed_at": analysis.completed_at,
            "query": analysis.query,
            "tools_used": analysis.tools_used,
            "tags": analysis.tags,
            "labels": analysis.labels,
            "metadata": analysis.metadata,
            "files": {
                "inputs": input_files,
                "outputs": output_files,
            },
            "summary": analysis.summary,
        }

        with open(manifest_path, "w") as f:
            json.dump(manifest, f, indent=2)

    # ── Search ────────────────────────────────────────────────────────

    def search_analyses(self, query: str, limit: int = 10) -> list[Analysis]:
        """
        Full-text search across analyses.

        Searches in title, description, tags, and query fields.
        """
        query_lower = query.lower()
        scored = []

        for analysis in self._analyses.values():
            score = 0

            # Title match (highest weight)
            if query_lower in analysis.title.lower():
                score += 10

            # Description match
            if query_lower in analysis.description.lower():
                score += 5

            # Tag match
            for tag in analysis.tags:
                if query_lower in tag.lower():
                    score += 3

            # Query match
            if query_lower in analysis.query.lower():
                score += 2

            # Analysis type match
            if query_lower in analysis.analysis_type.lower():
                score += 2

            if score > 0:
                scored.append((analysis, score))

        # Sort by score descending
        scored.sort(key=lambda x: x[1], reverse=True)

        return [a for a, _ in scored[:limit]]

    def find_files_by_tag(self, tags: list[str]) -> list[FileRecord]:
        """Find files matching any of the given tags."""
        return [
            f for f in self._files.values()
            if any(t in f.tags for t in tags)
        ]

    def find_files_by_category(self, category: str) -> list[FileRecord]:
        """Find all files of a given category."""
        return [
            f for f in self._files.values()
            if f.category.value == category
        ]

    # ── Statistics ────────────────────────────────────────────────────

    def get_stats(self) -> dict[str, Any]:
        """Get tracker statistics."""
        analyses = list(self._analyses.values())

        status_counts = {}
        for a in analyses:
            status = a.status.value
            status_counts[status] = status_counts.get(status, 0) + 1

        type_counts = {}
        for a in analyses:
            atype = a.analysis_type
            type_counts[atype] = type_counts.get(atype, 0) + 1

        return {
            "total_analyses": len(analyses),
            "total_files": len(self._files),
            "by_status": status_counts,
            "by_type": type_counts,
        }
