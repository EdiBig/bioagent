"""
Workspace Organization & Analysis Tracking System.

Provides comprehensive workspace organization with:
- Unique Analysis IDs linking all related files
- Organized directory structure by project/analysis type
- Rich metadata and tagging for easy discovery
- Automatic manifests and provenance tracking
- Easy retrieval and search capabilities
"""

from .models import (
    Project,
    Analysis,
    FileRecord,
    AnalysisStatus,
    FileType,
    FileCategory,
)
from .id_generator import IDGenerator
from .analysis_tracker import AnalysisTracker
from .project_manager import ProjectManager
from .file_registry import FileRegistry
from .search import WorkspaceSearch

__all__ = [
    # Models
    "Project",
    "Analysis",
    "FileRecord",
    "AnalysisStatus",
    "FileType",
    "FileCategory",
    # Core classes
    "IDGenerator",
    "AnalysisTracker",
    "ProjectManager",
    "FileRegistry",
    "WorkspaceSearch",
]
