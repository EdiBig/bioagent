"""
File Registry - Central file index for the workspace.

Provides fast lookup and tracking of all files across analyses.
"""

import json
from pathlib import Path
from typing import Any

from .models import FileRecord, FileType, FileCategory


class FileRegistry:
    """
    Central registry for all files in the workspace.

    Maintains indices for fast lookup by various criteria.
    """

    def __init__(self, workspace_dir: str):
        """
        Initialize the file registry.

        Args:
            workspace_dir: Root workspace directory
        """
        self.workspace_dir = Path(workspace_dir)
        self.registry_dir = self.workspace_dir / "registry"

        # Ensure directory exists
        self.registry_dir.mkdir(parents=True, exist_ok=True)

        # Registry file
        self._files_file = self.registry_dir / "files.json"

        # In-memory cache with indices
        self._files: dict[str, FileRecord] = {}
        self._by_analysis: dict[str, list[str]] = {}  # analysis_id -> file_ids
        self._by_type: dict[str, list[str]] = {}      # file_type -> file_ids
        self._by_category: dict[str, list[str]] = {}  # category -> file_ids
        self._by_format: dict[str, list[str]] = {}    # format -> file_ids

        # Load existing data
        self._load_registry()
        self._build_indices()

    def _load_registry(self) -> None:
        """Load files from persistent storage."""
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
        """Save files to persistent storage."""
        self.registry_dir.mkdir(parents=True, exist_ok=True)

        with open(self._files_file, "w") as f:
            json.dump(
                {fid: fr.to_dict() for fid, fr in self._files.items()},
                f, indent=2
            )

    def _build_indices(self) -> None:
        """Build lookup indices from loaded files."""
        self._by_analysis.clear()
        self._by_type.clear()
        self._by_category.clear()
        self._by_format.clear()

        for fid, file_record in self._files.items():
            # Index by analysis
            aid = file_record.analysis_id
            if aid not in self._by_analysis:
                self._by_analysis[aid] = []
            self._by_analysis[aid].append(fid)

            # Index by type
            ftype = file_record.file_type.value
            if ftype not in self._by_type:
                self._by_type[ftype] = []
            self._by_type[ftype].append(fid)

            # Index by category
            cat = file_record.category.value
            if cat not in self._by_category:
                self._by_category[cat] = []
            self._by_category[cat].append(fid)

            # Index by format
            fmt = file_record.format
            if fmt not in self._by_format:
                self._by_format[fmt] = []
            self._by_format[fmt].append(fid)

    def _add_to_indices(self, file_record: FileRecord) -> None:
        """Add a file to the indices."""
        fid = file_record.id

        # Analysis index
        aid = file_record.analysis_id
        if aid not in self._by_analysis:
            self._by_analysis[aid] = []
        if fid not in self._by_analysis[aid]:
            self._by_analysis[aid].append(fid)

        # Type index
        ftype = file_record.file_type.value
        if ftype not in self._by_type:
            self._by_type[ftype] = []
        if fid not in self._by_type[ftype]:
            self._by_type[ftype].append(fid)

        # Category index
        cat = file_record.category.value
        if cat not in self._by_category:
            self._by_category[cat] = []
        if fid not in self._by_category[cat]:
            self._by_category[cat].append(fid)

        # Format index
        fmt = file_record.format
        if fmt not in self._by_format:
            self._by_format[fmt] = []
        if fid not in self._by_format[fmt]:
            self._by_format[fmt].append(fid)

    # ── File Operations ───────────────────────────────────────────────

    def register_file(self, file_record: FileRecord) -> str:
        """
        Register a file in the registry.

        Args:
            file_record: The file record to register

        Returns:
            File ID
        """
        self._files[file_record.id] = file_record
        self._add_to_indices(file_record)
        self._save_registry()
        return file_record.id

    def get_file(self, file_id: str) -> FileRecord | None:
        """Get a file by ID."""
        return self._files.get(file_id)

    def get_files_by_analysis(self, analysis_id: str) -> list[FileRecord]:
        """Get all files for an analysis."""
        file_ids = self._by_analysis.get(analysis_id, [])
        return [self._files[fid] for fid in file_ids if fid in self._files]

    def get_files_by_type(self, file_type: str) -> list[FileRecord]:
        """Get all files of a given type."""
        file_ids = self._by_type.get(file_type, [])
        return [self._files[fid] for fid in file_ids if fid in self._files]

    def get_files_by_category(self, category: str) -> list[FileRecord]:
        """Get all files of a given category."""
        file_ids = self._by_category.get(category, [])
        return [self._files[fid] for fid in file_ids if fid in self._files]

    def get_files_by_format(self, format: str) -> list[FileRecord]:
        """Get all files with a given format/extension."""
        file_ids = self._by_format.get(format, [])
        return [self._files[fid] for fid in file_ids if fid in self._files]

    def update_file(
        self,
        file_id: str,
        description: str | None = None,
        tags: list[str] | None = None,
    ) -> bool:
        """
        Update file metadata.

        Args:
            file_id: The file to update
            description: New description
            tags: New tags (replaces existing)

        Returns:
            True if successful
        """
        file_record = self._files.get(file_id)
        if not file_record:
            return False

        if description is not None:
            file_record.description = description
        if tags is not None:
            file_record.tags = tags

        self._save_registry()
        return True

    def remove_file(self, file_id: str) -> bool:
        """
        Remove a file from the registry.

        Note: Does not delete the actual file.

        Args:
            file_id: The file to remove

        Returns:
            True if successful
        """
        if file_id not in self._files:
            return False

        file_record = self._files[file_id]
        del self._files[file_id]

        # Remove from indices
        aid = file_record.analysis_id
        if aid in self._by_analysis and file_id in self._by_analysis[aid]:
            self._by_analysis[aid].remove(file_id)

        ftype = file_record.file_type.value
        if ftype in self._by_type and file_id in self._by_type[ftype]:
            self._by_type[ftype].remove(file_id)

        cat = file_record.category.value
        if cat in self._by_category and file_id in self._by_category[cat]:
            self._by_category[cat].remove(file_id)

        fmt = file_record.format
        if fmt in self._by_format and file_id in self._by_format[fmt]:
            self._by_format[fmt].remove(file_id)

        self._save_registry()
        return True

    # ── Search ────────────────────────────────────────────────────────

    def search_files(
        self,
        query: str | None = None,
        tags: list[str] | None = None,
        file_type: str | None = None,
        category: str | None = None,
        format: str | None = None,
        analysis_id: str | None = None,
        limit: int = 50,
    ) -> list[FileRecord]:
        """
        Search files with multiple filters.

        Args:
            query: Text search in name and description
            tags: Filter by tags (any match)
            file_type: Filter by type
            category: Filter by category
            format: Filter by format
            analysis_id: Filter by analysis
            limit: Maximum results

        Returns:
            List of matching files
        """
        # Start with all files or filter by specific criteria
        if analysis_id:
            results = self.get_files_by_analysis(analysis_id)
        elif file_type:
            results = self.get_files_by_type(file_type)
        elif category:
            results = self.get_files_by_category(category)
        elif format:
            results = self.get_files_by_format(format)
        else:
            results = list(self._files.values())

        # Apply additional filters
        if file_type and analysis_id:
            results = [f for f in results if f.file_type.value == file_type]

        if category and (analysis_id or file_type):
            results = [f for f in results if f.category.value == category]

        if format and (analysis_id or file_type or category):
            results = [f for f in results if f.format == format]

        if tags:
            results = [
                f for f in results
                if any(t in f.tags for t in tags)
            ]

        if query:
            query_lower = query.lower()
            results = [
                f for f in results
                if query_lower in f.file_name.lower()
                or query_lower in f.description.lower()
            ]

        # Sort by creation date (newest first)
        results.sort(key=lambda f: f.created_at, reverse=True)

        return results[:limit]

    def find_by_tag(self, tags: list[str]) -> list[FileRecord]:
        """Find files matching any of the given tags."""
        return [
            f for f in self._files.values()
            if any(t in f.tags for t in tags)
        ]

    def find_by_source_tool(self, tool_name: str) -> list[FileRecord]:
        """Find files generated by a specific tool."""
        return [
            f for f in self._files.values()
            if f.source_tool == tool_name
        ]

    # ── Statistics ────────────────────────────────────────────────────

    def get_stats(self) -> dict[str, Any]:
        """Get registry statistics."""
        total_size = sum(f.size_bytes for f in self._files.values())

        type_counts = {}
        for ftype, fids in self._by_type.items():
            type_counts[ftype] = len(fids)

        category_counts = {}
        for cat, fids in self._by_category.items():
            category_counts[cat] = len(fids)

        format_counts = {}
        for fmt, fids in self._by_format.items():
            format_counts[fmt] = len(fids)

        return {
            "total_files": len(self._files),
            "total_size_bytes": total_size,
            "total_size_mb": round(total_size / (1024 * 1024), 2),
            "by_type": type_counts,
            "by_category": category_counts,
            "by_format": format_counts,
        }
