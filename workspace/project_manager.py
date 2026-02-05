"""
Project Manager - CRUD operations for projects.

Projects group related analyses (e.g., a research paper, clinical study).
"""

import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any

from .models import Project


class ProjectManager:
    """
    Manages projects: creation, updates, listing, and deletion.
    """

    def __init__(self, workspace_dir: str):
        """
        Initialize the project manager.

        Args:
            workspace_dir: Root workspace directory
        """
        self.workspace_dir = Path(workspace_dir)
        self.projects_dir = self.workspace_dir / "projects"
        self.registry_dir = self.workspace_dir / "registry"

        # Ensure directories exist
        self.projects_dir.mkdir(parents=True, exist_ok=True)
        self.registry_dir.mkdir(parents=True, exist_ok=True)

        # Registry file
        self._projects_file = self.registry_dir / "projects.json"

        # In-memory cache
        self._projects: dict[str, Project] = {}

        # Load existing data
        self._load_projects()

    def _load_projects(self) -> None:
        """Load projects from persistent storage."""
        if self._projects_file.exists():
            try:
                with open(self._projects_file, "r") as f:
                    data = json.load(f)
                    self._projects = {
                        pid: Project.from_dict(p)
                        for pid, p in data.items()
                    }
            except (json.JSONDecodeError, IOError):
                self._projects = {}
        else:
            self._projects = {}

    def _save_projects(self) -> None:
        """Save projects to persistent storage."""
        self.registry_dir.mkdir(parents=True, exist_ok=True)

        with open(self._projects_file, "w") as f:
            json.dump(
                {pid: p.to_dict() for pid, p in self._projects.items()},
                f, indent=2
            )

    def _generate_project_id(self, name: str) -> str:
        """Generate a project ID from the name."""
        # Lowercase, replace spaces with underscores
        project_id = name.lower().replace(" ", "_").replace("-", "_")

        # Keep only alphanumeric and underscores
        project_id = re.sub(r"[^a-z0-9_]", "", project_id)

        # Remove consecutive underscores
        project_id = re.sub(r"_+", "_", project_id)

        # Remove leading/trailing underscores
        project_id = project_id.strip("_")

        # Limit length
        if len(project_id) > 50:
            project_id = project_id[:50].rsplit("_", 1)[0]

        # Ensure uniqueness
        base_id = project_id
        counter = 1
        while project_id in self._projects:
            project_id = f"{base_id}_{counter}"
            counter += 1

        return project_id

    # ── Project CRUD ──────────────────────────────────────────────────

    def create_project(
        self,
        name: str,
        description: str = "",
        tags: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> str:
        """
        Create a new project.

        Args:
            name: Human-readable project name
            description: Project description
            tags: Tags for categorization
            metadata: Custom metadata (PI, institution, grant, etc.)

        Returns:
            Project ID
        """
        project_id = self._generate_project_id(name)

        # Create workspace path
        workspace_path = str(self.projects_dir / project_id)

        # Create project
        project = Project(
            id=project_id,
            name=name,
            description=description,
            tags=tags or [],
            metadata=metadata or {},
            workspace_path=workspace_path,
        )

        # Create directory structure
        self._create_project_structure(project_id, workspace_path)

        # Save project
        self._projects[project_id] = project
        self._save_projects()

        # Save manifest
        self._save_project_manifest(project)

        return project_id

    def get_project(self, project_id: str) -> Project | None:
        """Get a project by ID."""
        return self._projects.get(project_id)

    def update_project(
        self,
        project_id: str,
        name: str | None = None,
        description: str | None = None,
        tags: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> bool:
        """
        Update project metadata.

        Args:
            project_id: The project to update
            name: New name (optional)
            description: New description (optional)
            tags: New tags (replaces existing)
            metadata: Additional metadata (merges with existing)

        Returns:
            True if successful
        """
        project = self._projects.get(project_id)
        if not project:
            return False

        if name is not None:
            project.name = name
        if description is not None:
            project.description = description
        if tags is not None:
            project.tags = tags
        if metadata is not None:
            project.metadata.update(metadata)

        project.updated_at = datetime.now().isoformat()

        self._save_projects()
        self._save_project_manifest(project)

        return True

    def list_projects(
        self,
        tags: list[str] | None = None,
        limit: int = 50,
    ) -> list[Project]:
        """
        List all projects with optional filtering.

        Args:
            tags: Filter by tags (any match)
            limit: Maximum results

        Returns:
            List of projects, sorted by updated date (newest first)
        """
        results = list(self._projects.values())

        if tags:
            results = [
                p for p in results
                if any(t in p.tags for t in tags)
            ]

        # Sort by updated date (newest first)
        results.sort(key=lambda p: p.updated_at, reverse=True)

        return results[:limit]

    def delete_project(self, project_id: str, delete_files: bool = False) -> bool:
        """
        Delete a project.

        Args:
            project_id: The project to delete
            delete_files: If True, also delete project files

        Returns:
            True if successful
        """
        project = self._projects.get(project_id)
        if not project:
            return False

        # Remove from registry
        del self._projects[project_id]
        self._save_projects()

        # Optionally delete files
        if delete_files:
            import shutil
            project_path = Path(project.workspace_path)
            if project_path.exists():
                shutil.rmtree(project_path, ignore_errors=True)

        return True

    # ── Analysis Linking ──────────────────────────────────────────────

    def add_analysis_to_project(
        self,
        project_id: str,
        analysis_id: str,
    ) -> bool:
        """
        Link an analysis to a project.

        Args:
            project_id: The project
            analysis_id: The analysis to add

        Returns:
            True if successful
        """
        project = self._projects.get(project_id)
        if not project:
            return False

        project.add_analysis(analysis_id)
        self._save_projects()
        self._save_project_manifest(project)

        return True

    def remove_analysis_from_project(
        self,
        project_id: str,
        analysis_id: str,
    ) -> bool:
        """
        Unlink an analysis from a project.

        Args:
            project_id: The project
            analysis_id: The analysis to remove

        Returns:
            True if successful
        """
        project = self._projects.get(project_id)
        if not project:
            return False

        project.remove_analysis(analysis_id)
        self._save_projects()
        self._save_project_manifest(project)

        return True

    def get_project_for_analysis(self, analysis_id: str) -> Project | None:
        """Find the project containing an analysis."""
        for project in self._projects.values():
            if analysis_id in project.analysis_ids:
                return project
        return None

    # ── Directory Management ──────────────────────────────────────────

    def _create_project_structure(
        self,
        project_id: str,
        workspace_path: str
    ) -> None:
        """Create directory structure for a project."""
        base = Path(workspace_path)

        # Create subdirectories
        (base / "analyses").mkdir(parents=True, exist_ok=True)
        (base / "data").mkdir(parents=True, exist_ok=True)

    def _save_project_manifest(self, project: Project) -> None:
        """Save project manifest to its workspace directory."""
        workspace_path = Path(project.workspace_path)
        workspace_path.mkdir(parents=True, exist_ok=True)

        manifest_path = workspace_path / "PROJECT_MANIFEST.json"

        manifest = project.to_dict()

        with open(manifest_path, "w") as f:
            json.dump(manifest, f, indent=2)

    # ── Search ────────────────────────────────────────────────────────

    def search_projects(self, query: str, limit: int = 10) -> list[Project]:
        """
        Search projects by name, description, or tags.

        Args:
            query: Search query
            limit: Maximum results

        Returns:
            List of matching projects
        """
        query_lower = query.lower()
        scored = []

        for project in self._projects.values():
            score = 0

            # Name match (highest weight)
            if query_lower in project.name.lower():
                score += 10

            # Description match
            if query_lower in project.description.lower():
                score += 5

            # Tag match
            for tag in project.tags:
                if query_lower in tag.lower():
                    score += 3

            # ID match
            if query_lower in project.id.lower():
                score += 2

            if score > 0:
                scored.append((project, score))

        # Sort by score descending
        scored.sort(key=lambda x: x[1], reverse=True)

        return [p for p, _ in scored[:limit]]

    # ── Statistics ────────────────────────────────────────────────────

    def get_stats(self) -> dict[str, Any]:
        """Get project statistics."""
        projects = list(self._projects.values())

        total_analyses = sum(len(p.analysis_ids) for p in projects)

        return {
            "total_projects": len(projects),
            "total_analyses_in_projects": total_analyses,
        }
