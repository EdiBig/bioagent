"""
Workspace Search - Search and query utilities.

Provides unified search across analyses, projects, and files.
"""

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from .models import Analysis, Project, FileRecord


@dataclass
class SearchResult:
    """A search result with metadata."""
    type: str           # "analysis", "project", "file"
    id: str             # Object ID
    title: str          # Display title
    description: str    # Description or snippet
    score: float        # Relevance score
    metadata: dict[str, Any]  # Additional metadata


class WorkspaceSearch:
    """
    Unified search across the workspace.

    Searches analyses, projects, and files with relevance ranking.
    """

    def __init__(self, tracker: "AnalysisTracker", project_manager: "ProjectManager"):
        """
        Initialize the search interface.

        Args:
            tracker: The analysis tracker instance
            project_manager: The project manager instance
        """
        self.tracker = tracker
        self.project_manager = project_manager

    def search(
        self,
        query: str,
        types: list[str] | None = None,
        limit: int = 20,
    ) -> list[SearchResult]:
        """
        Search across all workspace objects.

        Args:
            query: Search query
            types: Object types to search ("analysis", "project", "file")
            limit: Maximum results

        Returns:
            List of search results sorted by relevance
        """
        if types is None:
            types = ["analysis", "project", "file"]

        results = []

        if "analysis" in types:
            results.extend(self._search_analyses(query))

        if "project" in types:
            results.extend(self._search_projects(query))

        if "file" in types:
            results.extend(self._search_files(query))

        # Sort by score (descending)
        results.sort(key=lambda r: r.score, reverse=True)

        return results[:limit]

    def _search_analyses(self, query: str) -> list[SearchResult]:
        """Search analyses."""
        query_lower = query.lower()
        results = []

        for analysis in self.tracker._analyses.values():
            score = 0.0

            # Title match (highest weight)
            if query_lower in analysis.title.lower():
                score += 10.0
                if analysis.title.lower().startswith(query_lower):
                    score += 5.0

            # Analysis type match
            if query_lower == analysis.analysis_type.lower():
                score += 8.0
            elif query_lower in analysis.analysis_type.lower():
                score += 3.0

            # Tag match
            for tag in analysis.tags:
                if query_lower == tag.lower():
                    score += 6.0
                elif query_lower in tag.lower():
                    score += 2.0

            # Description match
            if query_lower in analysis.description.lower():
                score += 4.0

            # Query match
            if query_lower in analysis.query.lower():
                score += 2.0

            # ID match
            if query_lower in analysis.id.lower():
                score += 3.0

            if score > 0:
                results.append(SearchResult(
                    type="analysis",
                    id=analysis.id,
                    title=analysis.title,
                    description=analysis.description[:200] if analysis.description else f"Type: {analysis.analysis_type}",
                    score=score,
                    metadata={
                        "status": analysis.status.value,
                        "type": analysis.analysis_type,
                        "created_at": analysis.created_at,
                        "tags": analysis.tags,
                    }
                ))

        return results

    def _search_projects(self, query: str) -> list[SearchResult]:
        """Search projects."""
        query_lower = query.lower()
        results = []

        for project in self.project_manager._projects.values():
            score = 0.0

            # Name match (highest weight)
            if query_lower in project.name.lower():
                score += 10.0
                if project.name.lower().startswith(query_lower):
                    score += 5.0

            # Tag match
            for tag in project.tags:
                if query_lower == tag.lower():
                    score += 6.0
                elif query_lower in tag.lower():
                    score += 2.0

            # Description match
            if query_lower in project.description.lower():
                score += 4.0

            # ID match
            if query_lower in project.id.lower():
                score += 3.0

            if score > 0:
                results.append(SearchResult(
                    type="project",
                    id=project.id,
                    title=project.name,
                    description=project.description[:200] if project.description else f"{len(project.analysis_ids)} analyses",
                    score=score,
                    metadata={
                        "analysis_count": len(project.analysis_ids),
                        "created_at": project.created_at,
                        "tags": project.tags,
                    }
                ))

        return results

    def _search_files(self, query: str) -> list[SearchResult]:
        """Search files."""
        query_lower = query.lower()
        results = []

        for file_record in self.tracker._files.values():
            score = 0.0

            # File name match (highest weight)
            if query_lower in file_record.file_name.lower():
                score += 10.0
                if file_record.file_name.lower().startswith(query_lower):
                    score += 5.0

            # Tag match
            for tag in file_record.tags:
                if query_lower == tag.lower():
                    score += 6.0
                elif query_lower in tag.lower():
                    score += 2.0

            # Description match
            if query_lower in file_record.description.lower():
                score += 4.0

            # Format match
            if query_lower == file_record.format.lower():
                score += 5.0

            # Category match
            if query_lower == file_record.category.value.lower():
                score += 4.0

            # Source tool match
            if file_record.source_tool and query_lower in file_record.source_tool.lower():
                score += 3.0

            if score > 0:
                results.append(SearchResult(
                    type="file",
                    id=file_record.id,
                    title=file_record.file_name,
                    description=file_record.description[:200] if file_record.description else f"{file_record.category.value} ({file_record.format})",
                    score=score,
                    metadata={
                        "analysis_id": file_record.analysis_id,
                        "file_type": file_record.file_type.value,
                        "category": file_record.category.value,
                        "format": file_record.format,
                        "size_bytes": file_record.size_bytes,
                        "tags": file_record.tags,
                    }
                ))

        return results

    def search_by_date(
        self,
        date_from: str | None = None,
        date_to: str | None = None,
        types: list[str] | None = None,
        limit: int = 50,
    ) -> list[SearchResult]:
        """
        Search by date range.

        Args:
            date_from: Start date (ISO format)
            date_to: End date (ISO format)
            types: Object types to search
            limit: Maximum results

        Returns:
            List of results within the date range
        """
        if types is None:
            types = ["analysis", "project", "file"]

        results = []

        if "analysis" in types:
            for analysis in self.tracker._analyses.values():
                if self._in_date_range(analysis.created_at, date_from, date_to):
                    results.append(SearchResult(
                        type="analysis",
                        id=analysis.id,
                        title=analysis.title,
                        description=analysis.description[:200] if analysis.description else "",
                        score=1.0,
                        metadata={
                            "created_at": analysis.created_at,
                            "status": analysis.status.value,
                            "type": analysis.analysis_type,
                        }
                    ))

        if "project" in types:
            for project in self.project_manager._projects.values():
                if self._in_date_range(project.created_at, date_from, date_to):
                    results.append(SearchResult(
                        type="project",
                        id=project.id,
                        title=project.name,
                        description=project.description[:200] if project.description else "",
                        score=1.0,
                        metadata={
                            "created_at": project.created_at,
                            "analysis_count": len(project.analysis_ids),
                        }
                    ))

        if "file" in types:
            for file_record in self.tracker._files.values():
                if self._in_date_range(file_record.created_at, date_from, date_to):
                    results.append(SearchResult(
                        type="file",
                        id=file_record.id,
                        title=file_record.file_name,
                        description=file_record.description[:200] if file_record.description else "",
                        score=1.0,
                        metadata={
                            "created_at": file_record.created_at,
                            "category": file_record.category.value,
                        }
                    ))

        # Sort by date (newest first)
        results.sort(key=lambda r: r.metadata.get("created_at", ""), reverse=True)

        return results[:limit]

    def _in_date_range(
        self,
        date_str: str,
        date_from: str | None,
        date_to: str | None,
    ) -> bool:
        """Check if a date is within the specified range."""
        if not date_str:
            return False

        if date_from and date_str < date_from:
            return False

        if date_to and date_str > date_to:
            return False

        return True

    def search_by_tags(
        self,
        tags: list[str],
        match_all: bool = False,
        types: list[str] | None = None,
        limit: int = 50,
    ) -> list[SearchResult]:
        """
        Search by tags.

        Args:
            tags: Tags to search for
            match_all: If True, require all tags to match; otherwise any match
            types: Object types to search
            limit: Maximum results

        Returns:
            List of matching results
        """
        if types is None:
            types = ["analysis", "project", "file"]

        tags_lower = [t.lower() for t in tags]
        results = []

        def matches_tags(obj_tags: list[str]) -> bool:
            obj_tags_lower = [t.lower() for t in obj_tags]
            if match_all:
                return all(t in obj_tags_lower for t in tags_lower)
            else:
                return any(t in obj_tags_lower for t in tags_lower)

        if "analysis" in types:
            for analysis in self.tracker._analyses.values():
                if matches_tags(analysis.tags):
                    results.append(SearchResult(
                        type="analysis",
                        id=analysis.id,
                        title=analysis.title,
                        description=analysis.description[:200] if analysis.description else "",
                        score=len(set(tags_lower) & set(t.lower() for t in analysis.tags)),
                        metadata={
                            "tags": analysis.tags,
                            "type": analysis.analysis_type,
                        }
                    ))

        if "project" in types:
            for project in self.project_manager._projects.values():
                if matches_tags(project.tags):
                    results.append(SearchResult(
                        type="project",
                        id=project.id,
                        title=project.name,
                        description=project.description[:200] if project.description else "",
                        score=len(set(tags_lower) & set(t.lower() for t in project.tags)),
                        metadata={
                            "tags": project.tags,
                        }
                    ))

        if "file" in types:
            for file_record in self.tracker._files.values():
                if matches_tags(file_record.tags):
                    results.append(SearchResult(
                        type="file",
                        id=file_record.id,
                        title=file_record.file_name,
                        description=file_record.description[:200] if file_record.description else "",
                        score=len(set(tags_lower) & set(t.lower() for t in file_record.tags)),
                        metadata={
                            "tags": file_record.tags,
                        }
                    ))

        # Sort by match count (descending)
        results.sort(key=lambda r: r.score, reverse=True)

        return results[:limit]

    def get_recent(
        self,
        types: list[str] | None = None,
        limit: int = 10,
    ) -> list[SearchResult]:
        """
        Get most recent items.

        Args:
            types: Object types to include
            limit: Maximum results

        Returns:
            List of recent items
        """
        if types is None:
            types = ["analysis", "project"]

        results = []

        if "analysis" in types:
            for analysis in self.tracker._analyses.values():
                results.append(SearchResult(
                    type="analysis",
                    id=analysis.id,
                    title=analysis.title,
                    description=f"{analysis.analysis_type} - {analysis.status.value}",
                    score=0.0,
                    metadata={
                        "created_at": analysis.created_at,
                        "updated_at": analysis.updated_at,
                    }
                ))

        if "project" in types:
            for project in self.project_manager._projects.values():
                results.append(SearchResult(
                    type="project",
                    id=project.id,
                    title=project.name,
                    description=f"{len(project.analysis_ids)} analyses",
                    score=0.0,
                    metadata={
                        "created_at": project.created_at,
                        "updated_at": project.updated_at,
                    }
                ))

        # Sort by updated_at (newest first)
        results.sort(
            key=lambda r: r.metadata.get("updated_at", r.metadata.get("created_at", "")),
            reverse=True
        )

        return results[:limit]
