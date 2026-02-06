"""
Storage Configuration Service

Manages user-configurable output storage locations with automatic
folder structure generation.

Supports:
- System downloads folder (default)
- Custom local path
- Workspace directory
"""

import os
import sys
import platform
from pathlib import Path
from typing import Optional, Dict, Any, Literal
from dataclasses import dataclass, asdict
from datetime import datetime
import json


# Storage location types
StorageLocationType = Literal["downloads", "workspace", "custom"]


@dataclass
class StoragePreferences:
    """User storage preferences."""
    location_type: StorageLocationType = "downloads"  # downloads, workspace, custom
    custom_path: Optional[str] = None  # Only used if location_type == "custom"
    create_subfolders: bool = True  # Auto-create organized subfolders
    subfolder_by_date: bool = True  # Organize by date (YYYY-MM-DD)
    subfolder_by_type: bool = True  # Organize by file type (results, reports, figures)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "StoragePreferences":
        """Create from dictionary, with defaults for missing keys."""
        return cls(
            location_type=data.get("location_type", "downloads"),
            custom_path=data.get("custom_path"),
            create_subfolders=data.get("create_subfolders", True),
            subfolder_by_date=data.get("subfolder_by_date", True),
            subfolder_by_type=data.get("subfolder_by_type", True),
        )


class StorageConfigService:
    """
    Manages output file storage locations and folder structures.

    Provides platform-aware defaults and automatic folder generation.
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
        "pdf_figure": "figures",

        # Data
        "fastq": "data",
        "fasta": "data",
        "vcf": "data",
        "bam": "data",
        "bed": "data",
        "h5ad": "data",

        # Logs
        "log": "logs",
        "txt": "logs",
    }

    def __init__(self):
        self._workspace_dir = self._get_workspace_dir()

    @staticmethod
    def _get_workspace_dir() -> Path:
        """Get the configured workspace directory."""
        if sys.platform == "win32":
            default = Path.home() / "bioagent_workspace"
        else:
            default = Path("/workspace")
        return Path(os.getenv("BIOAGENT_WORKSPACE", str(default)))

    @staticmethod
    def get_system_downloads_folder() -> Path:
        """
        Get the system's default downloads folder.

        Platform-aware detection with fallbacks.
        """
        system = platform.system()

        if system == "Windows":
            # Try to get Windows Downloads folder via registry
            try:
                import winreg
                sub_key = r"SOFTWARE\Microsoft\Windows\CurrentVersion\Explorer\Shell Folders"
                with winreg.OpenKey(winreg.HKEY_CURRENT_USER, sub_key) as key:
                    downloads_path, _ = winreg.QueryValueEx(key, "{374DE290-123F-4565-9164-39C4925E467B}")
                    return Path(downloads_path)
            except Exception:
                pass
            # Fallback to standard location
            return Path.home() / "Downloads"

        elif system == "Darwin":  # macOS
            return Path.home() / "Downloads"

        else:  # Linux and others
            # Check XDG user dirs
            xdg_download = os.getenv("XDG_DOWNLOAD_DIR")
            if xdg_download:
                return Path(xdg_download)
            # Try to read from user-dirs.dirs
            user_dirs_file = Path.home() / ".config" / "user-dirs.dirs"
            if user_dirs_file.exists():
                try:
                    content = user_dirs_file.read_text()
                    for line in content.splitlines():
                        if line.startswith("XDG_DOWNLOAD_DIR"):
                            path = line.split("=", 1)[1].strip().strip('"')
                            path = path.replace("$HOME", str(Path.home()))
                            return Path(path)
                except Exception:
                    pass
            # Fallback
            return Path.home() / "Downloads"

    def get_base_output_path(
        self,
        preferences: StoragePreferences,
        user_id: Optional[int] = None
    ) -> Path:
        """
        Get the base output path based on user preferences.

        Args:
            preferences: User's storage preferences
            user_id: Optional user ID for workspace isolation

        Returns:
            Base path for storing output files
        """
        if preferences.location_type == "downloads":
            base = self.get_system_downloads_folder() / "BioAgent"
        elif preferences.location_type == "workspace":
            base = self._workspace_dir / "outputs"
            if user_id:
                base = base / str(user_id)
        elif preferences.location_type == "custom":
            if preferences.custom_path:
                base = Path(preferences.custom_path)
            else:
                # Fallback to downloads if custom path not set
                base = self.get_system_downloads_folder() / "BioAgent"
        else:
            base = self.get_system_downloads_folder() / "BioAgent"

        return base

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
            user_id: Optional user ID
            file_category: Override automatic category detection (results, reports, figures, etc.)
            analysis_id: Optional analysis ID for grouping related files

        Returns:
            Full path where the file should be saved
        """
        base = self.get_base_output_path(preferences, user_id)

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
        base = self.get_base_output_path(preferences, user_id)

        structure = {
            "base_path": str(base),
            "location_type": preferences.location_type,
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

    def validate_custom_path(self, path: str) -> Dict[str, Any]:
        """
        Validate a custom path for use as output directory.

        Returns validation result with any issues.
        """
        result = {
            "valid": False,
            "path": path,
            "exists": False,
            "writable": False,
            "issues": [],
        }

        try:
            p = Path(path)

            # Check if it's an absolute path
            if not p.is_absolute():
                result["issues"].append("Path must be absolute")
                return result

            # Check if path exists
            if p.exists():
                result["exists"] = True

                # Check if it's a directory
                if not p.is_dir():
                    result["issues"].append("Path exists but is not a directory")
                    return result

                # Check if writable
                try:
                    test_file = p / ".bioagent_write_test"
                    test_file.touch()
                    test_file.unlink()
                    result["writable"] = True
                except Exception:
                    result["issues"].append("Directory exists but is not writable")
                    return result
            else:
                # Try to create it
                try:
                    p.mkdir(parents=True, exist_ok=True)
                    result["exists"] = True
                    result["writable"] = True
                except Exception as e:
                    result["issues"].append(f"Cannot create directory: {str(e)}")
                    return result

            result["valid"] = True

        except Exception as e:
            result["issues"].append(f"Invalid path: {str(e)}")

        return result


# Singleton instance
storage_config_service = StorageConfigService()
