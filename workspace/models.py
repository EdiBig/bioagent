"""
Data models for workspace organization and analysis tracking.

Defines the core dataclasses: Project, Analysis, FileRecord.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any


class AnalysisStatus(str, Enum):
    """Status of an analysis session."""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"


class FileType(str, Enum):
    """Type of file in an analysis."""
    INPUT = "input"
    OUTPUT = "output"
    REPORT = "report"
    LOG = "log"
    INTERMEDIATE = "intermediate"


class FileCategory(str, Enum):
    """Category of file content."""
    DATA = "data"
    FIGURE = "figure"
    TABLE = "table"
    NOTEBOOK = "notebook"
    SCRIPT = "script"
    LOG = "log"
    RESULT = "result"
    REFERENCE = "reference"
    OTHER = "other"


@dataclass
class FileRecord:
    """
    A file registered within an analysis session.

    Every file is tagged with its parent analysis for complete provenance.
    """
    id: str                         # Unique file ID (hash-based)
    analysis_id: str                # Parent analysis
    file_name: str                  # Original filename
    file_path: str                  # Path relative to workspace
    file_type: FileType             # input, output, report, log
    category: FileCategory          # figure, table, data, notebook, etc.
    format: str                     # File extension/format (csv, png, vcf)

    # Metadata
    description: str = ""
    tags: list[str] = field(default_factory=list)
    size_bytes: int = 0
    md5: str = ""
    created_at: str = ""

    # Provenance (for outputs)
    source_tool: str | None = None  # Tool that generated this file
    source_query: str | None = None # Query/command that produced this

    def __post_init__(self):
        if not self.created_at:
            self.created_at = datetime.now().isoformat()
        # Ensure enums
        if isinstance(self.file_type, str):
            self.file_type = FileType(self.file_type)
        if isinstance(self.category, str):
            self.category = FileCategory(self.category)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "id": self.id,
            "analysis_id": self.analysis_id,
            "file_name": self.file_name,
            "file_path": self.file_path,
            "file_type": self.file_type.value,
            "category": self.category.value,
            "format": self.format,
            "description": self.description,
            "tags": self.tags,
            "size_bytes": self.size_bytes,
            "md5": self.md5,
            "created_at": self.created_at,
            "source_tool": self.source_tool,
            "source_query": self.source_query,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "FileRecord":
        """Create from dictionary."""
        return cls(
            id=data["id"],
            analysis_id=data["analysis_id"],
            file_name=data["file_name"],
            file_path=data["file_path"],
            file_type=FileType(data["file_type"]),
            category=FileCategory(data["category"]),
            format=data["format"],
            description=data.get("description", ""),
            tags=data.get("tags", []),
            size_bytes=data.get("size_bytes", 0),
            md5=data.get("md5", ""),
            created_at=data.get("created_at", ""),
            source_tool=data.get("source_tool"),
            source_query=data.get("source_query"),
        )


@dataclass
class Analysis:
    """
    An analysis session with complete provenance tracking.

    Each analysis has a unique ID (BIO-YYYYMMDD-SEQ) and tracks all
    inputs, outputs, tools used, and metadata.
    """
    id: str                         # BIO-20250205-001 format
    title: str                      # Human-readable title

    # Optional fields
    project_id: str | None = None   # Parent project
    description: str = ""
    analysis_type: str = "general"  # rnaseq, variant, enrichment, etc.
    status: AnalysisStatus = AnalysisStatus.IN_PROGRESS

    # Timestamps
    created_at: str = ""
    updated_at: str = ""
    completed_at: str | None = None

    # Original query that started this analysis
    query: str = ""

    # Tools used during analysis
    tools_used: list[str] = field(default_factory=list)

    # Files (stored separately but tracked here by ID)
    input_ids: list[str] = field(default_factory=list)
    output_ids: list[str] = field(default_factory=list)

    # Tags & metadata
    tags: list[str] = field(default_factory=list)
    labels: dict[str, str] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)

    # Workspace path
    workspace_path: str = ""

    # Summary (added on completion)
    summary: str = ""

    def __post_init__(self):
        if not self.created_at:
            self.created_at = datetime.now().isoformat()
        if not self.updated_at:
            self.updated_at = self.created_at
        if isinstance(self.status, str):
            self.status = AnalysisStatus(self.status)

    def add_tool(self, tool_name: str) -> None:
        """Record a tool being used."""
        if tool_name not in self.tools_used:
            self.tools_used.append(tool_name)
            self.updated_at = datetime.now().isoformat()

    def add_input(self, file_id: str) -> None:
        """Register an input file."""
        if file_id not in self.input_ids:
            self.input_ids.append(file_id)
            self.updated_at = datetime.now().isoformat()

    def add_output(self, file_id: str) -> None:
        """Register an output file."""
        if file_id not in self.output_ids:
            self.output_ids.append(file_id)
            self.updated_at = datetime.now().isoformat()

    def complete(self, summary: str = "", status: AnalysisStatus = AnalysisStatus.COMPLETED) -> None:
        """Mark analysis as complete."""
        self.status = status
        self.completed_at = datetime.now().isoformat()
        self.updated_at = self.completed_at
        if summary:
            self.summary = summary

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "id": self.id,
            "title": self.title,
            "project_id": self.project_id,
            "description": self.description,
            "analysis_type": self.analysis_type,
            "status": self.status.value,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "completed_at": self.completed_at,
            "query": self.query,
            "tools_used": self.tools_used,
            "input_ids": self.input_ids,
            "output_ids": self.output_ids,
            "tags": self.tags,
            "labels": self.labels,
            "metadata": self.metadata,
            "workspace_path": self.workspace_path,
            "summary": self.summary,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Analysis":
        """Create from dictionary."""
        return cls(
            id=data["id"],
            title=data["title"],
            project_id=data.get("project_id"),
            description=data.get("description", ""),
            analysis_type=data.get("analysis_type", "general"),
            status=AnalysisStatus(data.get("status", "in_progress")),
            created_at=data.get("created_at", ""),
            updated_at=data.get("updated_at", ""),
            completed_at=data.get("completed_at"),
            query=data.get("query", ""),
            tools_used=data.get("tools_used", []),
            input_ids=data.get("input_ids", []),
            output_ids=data.get("output_ids", []),
            tags=data.get("tags", []),
            labels=data.get("labels", {}),
            metadata=data.get("metadata", {}),
            workspace_path=data.get("workspace_path", ""),
            summary=data.get("summary", ""),
        )


@dataclass
class Project:
    """
    A project groups related analyses.

    Projects represent larger research efforts like a paper, clinical study,
    or ongoing research program.
    """
    id: str                         # e.g., "cancer_rna_seq_2025"
    name: str                       # Human-readable name

    # Optional fields
    description: str = ""
    created_at: str = ""
    updated_at: str = ""

    # Tags for categorization
    tags: list[str] = field(default_factory=list)

    # Analysis IDs in this project
    analysis_ids: list[str] = field(default_factory=list)

    # Custom metadata (PI, institution, grant, etc.)
    metadata: dict[str, Any] = field(default_factory=dict)

    # Workspace path
    workspace_path: str = ""

    def __post_init__(self):
        if not self.created_at:
            self.created_at = datetime.now().isoformat()
        if not self.updated_at:
            self.updated_at = self.created_at

    def add_analysis(self, analysis_id: str) -> None:
        """Add an analysis to this project."""
        if analysis_id not in self.analysis_ids:
            self.analysis_ids.append(analysis_id)
            self.updated_at = datetime.now().isoformat()

    def remove_analysis(self, analysis_id: str) -> None:
        """Remove an analysis from this project."""
        if analysis_id in self.analysis_ids:
            self.analysis_ids.remove(analysis_id)
            self.updated_at = datetime.now().isoformat()

    @property
    def statistics(self) -> dict[str, int]:
        """Get project statistics."""
        return {
            "total_analyses": len(self.analysis_ids),
        }

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "tags": self.tags,
            "analysis_ids": self.analysis_ids,
            "metadata": self.metadata,
            "workspace_path": self.workspace_path,
            "statistics": self.statistics,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Project":
        """Create from dictionary."""
        return cls(
            id=data["id"],
            name=data["name"],
            description=data.get("description", ""),
            created_at=data.get("created_at", ""),
            updated_at=data.get("updated_at", ""),
            tags=data.get("tags", []),
            analysis_ids=data.get("analysis_ids", []),
            metadata=data.get("metadata", {}),
            workspace_path=data.get("workspace_path", ""),
        )
