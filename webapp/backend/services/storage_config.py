"""
Storage Configuration Service

Manages consolidated output storage in the workspace directory
with automatic folder structure generation.

All outputs are stored in: BIOAGENT_WORKSPACE/
├── uploads/        - User uploaded files
├── outputs/        - Analysis outputs, results, reports
├── projects/       - Project-organized analyses
└── memory/         - System memory and artifacts
"""

import os
import sys
from pathlib import Path
from typing import Optional, Dict, Any
from dataclasses import dataclass, asdict
from datetime import datetime


@dataclass
class StoragePreferences:
    """User storage organization preferences."""
    create_subfolders: bool = True  # Auto-create organized subfolders
    subfolder_by_date: bool = True  # Organize by date (YYYY-MM-DD)
    subfolder_by_type: bool = True  # Organize by file type (results, reports, figures)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "StoragePreferences":
        """Create from dictionary, with defaults for missing keys."""
        return cls(
            create_subfolders=data.get("create_subfolders", True),
            subfolder_by_date=data.get("subfolder_by_date", True),
            subfolder_by_type=data.get("subfolder_by_type", True),
        )


class StorageConfigService:
    """
    Manages consolidated output file storage in the workspace directory.

    All files are stored under BIOAGENT_WORKSPACE with organized subfolders.
    """

    # File type to subfolder mapping
    FILE_TYPE_FOLDERS = {
        # Results
        "csv": "results",
        "tsv": "results",
        "json": "results",
        "parquet": "results",
        "xlsx": "results",

        # Reports
        "md": "reports",
        "html": "reports",
        "pdf": "reports",
        "ipynb": "reports",
        "Rmd": "reports",

        # Figures
        "png": "figures",
        "svg": "figures",
        "jpg": "figures",
        "jpeg": "figures",

        # Data
        "fastq": "data",
        "fasta": "data",
        "vcf": "data",
        "bam": "data",
        "bed": "data",
        "h5ad": "data",
        "gz": "data",

        # Logs
        "log": "logs",
        "txt": "logs",
    }

    def __init__(self):
        self._workspace_dir = self._get_workspace_dir()
        # Ensure workspace exists
        self._workspace_dir.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def _get_workspace_dir() -> Path:
        """Get the configured workspace directory."""
        if sys.platform == "win32":
            default = Path.home() / "bioagent_workspace"
        else:
            default = Path("/workspace")
        return Path(os.getenv("BIOAGENT_WORKSPACE", str(default)))

    @property
    def workspace_dir(self) -> Path:
        """Get the workspace directory."""
        return self._workspace_dir

    @property
    def uploads_dir(self) -> Path:
        """Get the uploads directory."""
        return self._workspace_dir / "uploads"

    @property
    def outputs_dir(self) -> Path:
        """Get the outputs directory."""
        return self._workspace_dir / "outputs"

    @property
    def projects_dir(self) -> Path:
        """Get the projects directory."""
        return self._workspace_dir / "projects"

    def get_output_path(
        self,
        filename: str,
        preferences: StoragePreferences,
        user_id: Optional[int] = None,
        file_category: Optional[str] = None,
        analysis_id: Optional[str] = None,
    ) -> Path:
        """
        Get the full output path for a file, with optional subfolder organization.

        Args:
            filename: Name of the file to save
            preferences: User's storage preferences
            user_id: Optional user ID for isolation
            file_category: Override automatic category detection
            analysis_id: Optional analysis ID for grouping related files

        Returns:
            Full path where the file should be saved
        """
        # Base is always the outputs directory
        base = self.outputs_dir

        # Add user isolation if provided
        if user_id:
            base = base / str(user_id)

        if not preferences.create_subfolders:
            return base / filename

        # Build subfolder path
        subfolders = []

        # Add date subfolder
        if preferences.subfolder_by_date:
            subfolders.append(datetime.now().strftime("%Y-%m-%d"))

        # Add analysis ID subfolder if provided
        if analysis_id:
            subfolders.append(analysis_id)

        # Add type subfolder
        if preferences.subfolder_by_type:
            if file_category:
                subfolders.append(file_category)
            else:
                # Auto-detect from extension
                ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
                category = self.FILE_TYPE_FOLDERS.get(ext, "other")
                subfolders.append(category)

        # Build full path
        output_dir = base
        for folder in subfolders:
            output_dir = output_dir / folder

        return output_dir / filename

    def ensure_output_directory(self, path: Path) -> Path:
        """
        Ensure the output directory exists, creating it if necessary.

        Args:
            path: Full file path (directory will be extracted)

        Returns:
            The directory path that was ensured
        """
        directory = path.parent
        directory.mkdir(parents=True, exist_ok=True)
        return directory

    def get_folder_structure_preview(
        self,
        preferences: StoragePreferences,
        user_id: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        Get a preview of the folder structure that will be created.

        Returns a dict describing the structure for UI display.
        """
        base = self.outputs_dir
        if user_id:
            base = base / str(user_id)

        structure = {
            "workspace_path": str(self._workspace_dir),
            "base_path": str(base),
            "subfolders": [],
        }

        if preferences.create_subfolders:
            if preferences.subfolder_by_date:
                structure["subfolders"].append({
                    "name": "YYYY-MM-DD",
                    "description": "Organized by date",
                    "example": datetime.now().strftime("%Y-%m-%d"),
                })

            if preferences.subfolder_by_type:
                structure["subfolders"].append({
                    "name": "results | reports | figures | data | logs",
                    "description": "Organized by file type",
                    "categories": list(set(self.FILE_TYPE_FOLDERS.values())),
                })

        # Example full path
        example_file = "analysis_results.csv"
        example_path = self.get_output_path(example_file, preferences, user_id)
        structure["example_path"] = str(example_path)

        return structure

    def get_storage_info(self) -> Dict[str, Any]:
        """
        Get information about the current storage configuration.
        """
        return {
            "workspace": str(self._workspace_dir),
            "uploads": str(self.uploads_dir),
            "outputs": str(self.outputs_dir),
            "projects": str(self.projects_dir),
            "exists": self._workspace_dir.exists(),
            "structure": {
                "uploads": "User uploaded files",
                "outputs": "Analysis outputs, results, reports, figures",
                "projects": "Project-organized analyses with provenance",
                "memory": "System memory, embeddings, artifacts",
                "registry": "File and analysis indexes",
            }
        }

    def ensure_workspace_structure(self) -> Dict[str, Path]:
        """
        Ensure the complete workspace structure exists.

        Returns dict of created directories.
        """
        dirs = {
            "workspace": self._workspace_dir,
            "uploads": self.uploads_dir,
            "outputs": self.outputs_dir,
            "projects": self.projects_dir,
            "memory": self._workspace_dir / "memory",
            "registry": self._workspace_dir / "registry",
        }

        for name, path in dirs.items():
            path.mkdir(parents=True, exist_ok=True)

        return dirs


# Singleton instance
storage_config_service = StorageConfigService()
