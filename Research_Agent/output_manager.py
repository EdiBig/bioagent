"""
Research Agent Output Manager — Organized file storage with workspace integration.

Provides consistent file naming, folder organization, and integration with
the BioAgent workspace tracking system.

Output Structure:
    workspace/projects/{project_id}/analyses/{analysis_id}/
    ├── reports/
    │   ├── research_report_{timestamp}.md
    │   ├── study_plan_{timestamp}.md
    │   └── sections/
    │       ├── abstract.md
    │       ├── introduction.md
    │       └── ...
    ├── references/
    │   ├── references_{timestamp}.bib
    │   └── reference_list_{timestamp}.md
    ├── presentations/
    │   ├── presentation_{timestamp}.pptx
    │   └── generate_pptx.js
    ├── visualizations/
    │   ├── viz_data_{timestamp}.json
    │   └── charts/
    ├── search_results/
    │   └── search_{query_slug}_{timestamp}.json
    └── logs/
        └── session_{timestamp}.json
"""

import json
import re
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

# Try to import workspace tracker
try:
    from workspace.analysis_tracker import AnalysisTracker
    from workspace.models import FileType, FileCategory
    WORKSPACE_AVAILABLE = True
except ImportError:
    WORKSPACE_AVAILABLE = False


class ResearchOutputManager:
    """
    Manages output file organization for the Research Agent.

    Features:
    - Consistent file naming with timestamps
    - Organized folder structure (reports, references, presentations, etc.)
    - Optional workspace tracking integration
    - File registration with provenance
    """

    def __init__(
        self,
        workspace_dir: str,
        project_id: Optional[str] = None,
        analysis_id: Optional[str] = None,
        enable_tracking: bool = True,
    ):
        """
        Initialize the output manager.

        Args:
            workspace_dir: Root workspace directory
            project_id: Optional project to organize under
            analysis_id: Optional analysis session ID (auto-created if None)
            enable_tracking: Whether to use workspace tracking (if available)
        """
        self.workspace_dir = Path(workspace_dir)
        self.project_id = project_id or "_research"
        self.enable_tracking = enable_tracking and WORKSPACE_AVAILABLE

        # Initialize tracker if available
        self._tracker: Optional[AnalysisTracker] = None
        self._analysis_id = analysis_id

        if self.enable_tracking:
            self._init_tracker()

        # Set up output directory structure
        self._setup_directories()

        # File registry for this session
        self._files: dict[str, dict] = {}

    def _init_tracker(self) -> None:
        """Initialize the workspace tracker."""
        try:
            self._tracker = AnalysisTracker(
                workspace_dir=str(self.workspace_dir),
                id_prefix="RES"  # Research prefix
            )
        except Exception as e:
            print(f"Warning: Could not initialize workspace tracker: {e}")
            self.enable_tracking = False

    def _setup_directories(self) -> None:
        """Set up the output directory structure."""
        if self._tracker and self._analysis_id:
            # Use tracker's workspace path
            analysis = self._tracker.get_analysis(self._analysis_id)
            if analysis:
                self.base_dir = Path(analysis.workspace_path)
            else:
                self.base_dir = self._get_default_base_dir()
        else:
            self.base_dir = self._get_default_base_dir()

        # Create subdirectories
        self.dirs = {
            "reports": self.base_dir / "reports",
            "sections": self.base_dir / "reports" / "sections",
            "references": self.base_dir / "references",
            "presentations": self.base_dir / "presentations",
            "visualizations": self.base_dir / "visualizations",
            "charts": self.base_dir / "visualizations" / "charts",
            "search_results": self.base_dir / "search_results",
            "logs": self.base_dir / "logs",
            "outputs": self.base_dir / "outputs",
        }

        for dir_path in self.dirs.values():
            dir_path.mkdir(parents=True, exist_ok=True)

    def _get_default_base_dir(self) -> Path:
        """Get default base directory when tracker is not available."""
        return self.workspace_dir / "projects" / self.project_id / "research_outputs"

    # ══════════════════════════════════════════════════════════════
    # ANALYSIS SESSION MANAGEMENT
    # ══════════════════════════════════════════════════════════════

    def start_analysis(
        self,
        title: str,
        description: str = "",
        query: str = "",
        tags: Optional[list[str]] = None,
    ) -> str:
        """
        Start a new research analysis session.

        Args:
            title: Analysis title
            description: Detailed description
            query: Original research query
            tags: Tags for categorization

        Returns:
            Analysis ID
        """
        if self._tracker:
            self._analysis_id = self._tracker.start_analysis(
                title=title,
                description=description,
                query=query,
                analysis_type="research",
                project_id=self.project_id if self.project_id != "_research" else None,
                tags=tags or ["research", "literature-review"],
            )
            # Update directories to use new analysis path
            self._setup_directories()
        else:
            # Generate a simple ID
            self._analysis_id = f"RES-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
            self._setup_directories()

        return self._analysis_id

    def complete_analysis(self, summary: str = "") -> bool:
        """Mark the current analysis as complete."""
        if self._tracker and self._analysis_id:
            return self._tracker.complete_analysis(
                analysis_id=self._analysis_id,
                summary=summary,
                status="completed"
            )
        return True

    @property
    def analysis_id(self) -> Optional[str]:
        """Get current analysis ID."""
        return self._analysis_id

    # ══════════════════════════════════════════════════════════════
    # FILE NAMING UTILITIES
    # ══════════════════════════════════════════════════════════════

    @staticmethod
    def _timestamp() -> str:
        """Generate a timestamp string."""
        return datetime.now().strftime("%Y%m%d_%H%M%S")

    @staticmethod
    def _slugify(text: str, max_length: int = 50) -> str:
        """Convert text to a safe filename slug."""
        # Convert to lowercase and replace spaces/special chars
        slug = re.sub(r'[^\w\s-]', '', text.lower())
        slug = re.sub(r'[\s_-]+', '_', slug)
        return slug[:max_length].strip('_')

    def _register_file(
        self,
        path: Path,
        file_type: str,
        category: str,
        description: str = "",
        source_tool: str = "",
        tags: Optional[list[str]] = None,
    ) -> str:
        """Register a file with the tracker."""
        file_id = f"{self._analysis_id or 'unknown'}:{path.name}"

        self._files[file_id] = {
            "path": str(path),
            "file_type": file_type,
            "category": category,
            "description": description,
            "source_tool": source_tool,
            "tags": tags or [],
            "created_at": datetime.now().isoformat(),
        }

        if self._tracker and self._analysis_id:
            try:
                self._tracker.register_file(
                    analysis_id=self._analysis_id,
                    file_path=str(path),
                    file_type=file_type,
                    category=category,
                    description=description,
                    source_tool=source_tool,
                    tags=tags,
                )
            except Exception as e:
                print(f"Warning: Could not register file with tracker: {e}")

        return file_id

    # ══════════════════════════════════════════════════════════════
    # REPORT OUTPUT METHODS
    # ══════════════════════════════════════════════════════════════

    def save_report(
        self,
        content: str,
        title: str = "research_report",
        format: str = "md",
    ) -> Path:
        """
        Save a research report.

        Args:
            content: Report content
            title: Report title (used in filename)
            format: Output format (md, docx)

        Returns:
            Path to saved file
        """
        slug = self._slugify(title)
        filename = f"{slug}_{self._timestamp()}.{format}"
        path = self.dirs["reports"] / filename

        path.write_text(content, encoding="utf-8")

        self._register_file(
            path=path,
            file_type="report",
            category="result",
            description=f"Research report: {title}",
            source_tool="compile_report",
            tags=["report", "research"],
        )

        return path

    def save_report_section(
        self,
        content: str,
        section_type: str,
        section_title: Optional[str] = None,
    ) -> Path:
        """
        Save a report section.

        Args:
            content: Section content
            section_type: Type of section (abstract, introduction, etc.)
            section_title: Optional custom title

        Returns:
            Path to saved file
        """
        title = section_title or section_type
        filename = f"{section_type}.md"
        path = self.dirs["sections"] / filename

        # Add header if not present
        if not content.startswith("#"):
            content = f"## {title.title()}\n\n{content}"

        path.write_text(content, encoding="utf-8")

        self._register_file(
            path=path,
            file_type="output",
            category="result",
            description=f"Report section: {title}",
            source_tool="generate_report_section",
            tags=["section", section_type],
        )

        return path

    def save_study_plan(self, content: str, topic: str = "") -> Path:
        """Save a study plan."""
        slug = self._slugify(topic) if topic else "study_plan"
        filename = f"{slug}_{self._timestamp()}.md"
        path = self.dirs["reports"] / filename

        path.write_text(content, encoding="utf-8")

        self._register_file(
            path=path,
            file_type="output",
            category="result",
            description=f"Study plan: {topic}",
            source_tool="plan_study",
            tags=["study-plan", "methodology"],
        )

        return path

    # ══════════════════════════════════════════════════════════════
    # REFERENCE OUTPUT METHODS
    # ══════════════════════════════════════════════════════════════

    def save_bibtex(self, content: str) -> Path:
        """Save BibTeX references."""
        filename = f"references_{self._timestamp()}.bib"
        path = self.dirs["references"] / filename

        path.write_text(content, encoding="utf-8")

        self._register_file(
            path=path,
            file_type="output",
            category="reference",
            description="BibTeX reference file",
            source_tool="export_bibtex",
            tags=["bibtex", "references"],
        )

        return path

    def save_reference_list(self, content: str, style: str = "harvard") -> Path:
        """Save formatted reference list."""
        filename = f"reference_list_{style}_{self._timestamp()}.md"
        path = self.dirs["references"] / filename

        path.write_text(content, encoding="utf-8")

        self._register_file(
            path=path,
            file_type="output",
            category="reference",
            description=f"Reference list ({style} style)",
            source_tool="format_reference_list",
            tags=["references", style],
        )

        return path

    # ══════════════════════════════════════════════════════════════
    # PRESENTATION OUTPUT METHODS
    # ══════════════════════════════════════════════════════════════

    def save_presentation_script(self, content: str, title: str = "") -> Path:
        """Save PptxGenJS script for presentation generation."""
        slug = self._slugify(title) if title else "presentation"
        filename = f"generate_{slug}.js"
        path = self.dirs["presentations"] / filename

        path.write_text(content, encoding="utf-8")

        self._register_file(
            path=path,
            file_type="output",
            category="script",
            description=f"Presentation generator script: {title}",
            source_tool="generate_presentation",
            tags=["presentation", "script"],
        )

        return path

    def get_presentation_output_path(self, title: str = "") -> Path:
        """Get the output path for a presentation."""
        slug = self._slugify(title) if title else "presentation"
        filename = f"{slug}_{self._timestamp()}.pptx"
        return self.dirs["presentations"] / filename

    # ══════════════════════════════════════════════════════════════
    # VISUALIZATION OUTPUT METHODS
    # ══════════════════════════════════════════════════════════════

    def save_visualization_data(
        self,
        data: dict,
        name: str = "viz_data",
    ) -> Path:
        """Save visualization data as JSON."""
        slug = self._slugify(name)
        filename = f"{slug}_{self._timestamp()}.json"
        path = self.dirs["visualizations"] / filename

        path.write_text(json.dumps(data, indent=2), encoding="utf-8")

        self._register_file(
            path=path,
            file_type="output",
            category="data",
            description=f"Visualization data: {name}",
            source_tool="create_visualization",
            tags=["visualization", "data"],
        )

        return path

    def save_chart_data(self, data: dict, chart_type: str = "chart") -> Path:
        """Save chart data for presentation inclusion."""
        filename = f"{chart_type}_{self._timestamp()}.json"
        path = self.dirs["charts"] / filename

        path.write_text(json.dumps(data, indent=2), encoding="utf-8")

        self._register_file(
            path=path,
            file_type="output",
            category="figure",
            description=f"Chart data: {chart_type}",
            source_tool="add_chart_slide",
            tags=["chart", chart_type],
        )

        return path

    # ══════════════════════════════════════════════════════════════
    # SEARCH RESULTS OUTPUT METHODS
    # ══════════════════════════════════════════════════════════════

    def save_search_results(
        self,
        results: dict,
        query: str,
        sources: Optional[list[str]] = None,
    ) -> Path:
        """Save literature search results."""
        slug = self._slugify(query)
        sources_str = "_".join(sources) if sources else "multi"
        filename = f"search_{slug}_{sources_str}_{self._timestamp()}.json"
        path = self.dirs["search_results"] / filename

        # Add metadata
        output = {
            "query": query,
            "sources": sources or [],
            "timestamp": datetime.now().isoformat(),
            "results": results,
        }

        path.write_text(json.dumps(output, indent=2), encoding="utf-8")

        self._register_file(
            path=path,
            file_type="output",
            category="data",
            description=f"Search results: {query[:50]}",
            source_tool="search_literature",
            tags=["search", "literature"],
        )

        return path

    # ══════════════════════════════════════════════════════════════
    # LOG OUTPUT METHODS
    # ══════════════════════════════════════════════════════════════

    def save_session_log(self, log_entries: list[dict]) -> Path:
        """Save session log."""
        filename = f"session_{self._timestamp()}.json"
        path = self.dirs["logs"] / filename

        output = {
            "analysis_id": self._analysis_id,
            "timestamp": datetime.now().isoformat(),
            "entries": log_entries,
        }

        path.write_text(json.dumps(output, indent=2), encoding="utf-8")

        self._register_file(
            path=path,
            file_type="log",
            category="other",
            description="Research session log",
            source_tool="research_agent",
            tags=["log", "session"],
        )

        return path

    # ══════════════════════════════════════════════════════════════
    # UTILITY METHODS
    # ══════════════════════════════════════════════════════════════

    def get_all_sections(self) -> list[Path]:
        """Get all report section files in order."""
        section_order = [
            "abstract", "introduction", "background", "methods",
            "results", "discussion", "conclusion", "limitations",
            "future_directions", "acknowledgments", "appendix"
        ]

        sections = []
        for section_name in section_order:
            section_path = self.dirs["sections"] / f"{section_name}.md"
            if section_path.exists():
                sections.append(section_path)

        # Add any other sections not in the standard order
        for path in sorted(self.dirs["sections"].glob("*.md")):
            if path not in sections:
                sections.append(path)

        return sections

    def get_files_summary(self) -> dict:
        """Get summary of all files created in this session."""
        by_type = {}
        for file_id, info in self._files.items():
            ftype = info["file_type"]
            if ftype not in by_type:
                by_type[ftype] = []
            by_type[ftype].append({
                "path": info["path"],
                "description": info["description"],
            })

        return {
            "analysis_id": self._analysis_id,
            "base_dir": str(self.base_dir),
            "total_files": len(self._files),
            "by_type": by_type,
        }

    def get_output_path(self, filename: str, category: str = "outputs") -> Path:
        """Get a path for a custom output file."""
        dir_path = self.dirs.get(category, self.dirs["outputs"])
        return dir_path / filename
