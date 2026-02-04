"""
File management tools for reading, writing, and listing files.
"""

import glob
import os
from pathlib import Path
from dataclasses import dataclass


@dataclass
class FileResult:
    """Result of a file operation."""
    content: str
    path: str
    success: bool

    def to_string(self) -> str:
        if self.success:
            return self.content
        else:
            return f"Error with {self.path}: {self.content}"


class FileManager:
    """Manages file operations within the workspace."""

    def __init__(self, workspace_dir: str = "/workspace", max_read_chars: int = 100_000):
        self.workspace_dir = Path(workspace_dir)
        self.workspace_dir.mkdir(parents=True, exist_ok=True)
        self.max_read_chars = max_read_chars

    def _resolve_path(self, path: str) -> Path:
        """Resolve path, translating /workspace to actual workspace directory."""
        # Translate /workspace paths to actual workspace
        if path.startswith("/workspace/"):
            return self.workspace_dir / path[11:]  # len("/workspace/") = 11
        elif path == "/workspace":
            return self.workspace_dir
        return Path(path)

    def read_file(
        self,
        path: str,
        head_lines: int | None = None,
        encoding: str = "utf-8",
    ) -> FileResult:
        """Read a file's contents."""
        file_path = self._resolve_path(path)

        if not file_path.exists():
            return FileResult(
                content=f"File not found: {path}",
                path=path,
                success=False,
            )

        if not file_path.is_file():
            return FileResult(
                content=f"Not a file: {path}",
                path=path,
                success=False,
            )

        # Check file size
        size = file_path.stat().st_size
        if size > 50_000_000:  # 50MB
            return FileResult(
                content=f"File is too large ({size / 1_000_000:.1f} MB). Use head_lines parameter or bash tools to read portions.",
                path=path,
                success=False,
            )

        try:
            with open(file_path, "r", encoding=encoding, errors="replace") as f:
                if head_lines:
                    lines = []
                    for i, line in enumerate(f):
                        if i >= head_lines:
                            break
                        lines.append(line)
                    content = "".join(lines)
                    if i >= head_lines:
                        content += f"\n... (showing first {head_lines} lines of file)"
                else:
                    content = f.read()

            # Truncate if needed
            if len(content) > self.max_read_chars:
                content = (
                    content[: self.max_read_chars // 2]
                    + f"\n\n... [TRUNCATED — file is {len(content)} chars, showing first and last portions] ...\n\n"
                    + content[-self.max_read_chars // 2:]
                )

            return FileResult(content=content, path=path, success=True)

        except Exception as e:
            return FileResult(
                content=f"Error reading file: {e}",
                path=path,
                success=False,
            )

    def write_file(
        self, path: str, content: str, mode: str = "w"
    ) -> FileResult:
        """Write content to a file."""
        file_path = self._resolve_path(path)

        try:
            # Create parent directories
            file_path.parent.mkdir(parents=True, exist_ok=True)

            with open(file_path, mode, encoding="utf-8") as f:
                f.write(content)

            size = file_path.stat().st_size
            return FileResult(
                content=f"Successfully wrote {size:,} bytes to {path}",
                path=path,
                success=True,
            )

        except Exception as e:
            return FileResult(
                content=f"Error writing file: {e}",
                path=path,
                success=False,
            )

    def list_files(
        self, path: str, pattern: str = "*", recursive: bool = False
    ) -> FileResult:
        """List files in a directory."""
        dir_path = self._resolve_path(path)

        if not dir_path.exists():
            return FileResult(
                content=f"Directory not found: {path}",
                path=path,
                success=False,
            )

        if not dir_path.is_dir():
            return FileResult(
                content=f"Not a directory: {path}",
                path=path,
                success=False,
            )

        try:
            if recursive:
                files = sorted(dir_path.rglob(pattern))
            else:
                files = sorted(dir_path.glob(pattern))

            if not files:
                return FileResult(
                    content=f"No files matching '{pattern}' in {path}",
                    path=path,
                    success=True,
                )

            lines = []
            for f in files[:500]:  # Cap at 500 entries
                rel_path = f.relative_to(dir_path)
                if f.is_dir():
                    lines.append(f"📁 {rel_path}/")
                else:
                    size = f.stat().st_size
                    lines.append(f"   {rel_path} ({self._format_size(size)})")

            content = f"Contents of {path} (pattern: {pattern}):\n\n" + "\n".join(lines)

            if len(files) > 500:
                content += f"\n\n... and {len(files) - 500} more files"

            return FileResult(content=content, path=path, success=True)

        except Exception as e:
            return FileResult(
                content=f"Error listing files: {e}",
                path=path,
                success=False,
            )

    @staticmethod
    def _format_size(size_bytes: int) -> str:
        """Format file size for display."""
        for unit in ["B", "KB", "MB", "GB"]:
            if size_bytes < 1024:
                return f"{size_bytes:.1f} {unit}" if unit != "B" else f"{size_bytes} {unit}"
            size_bytes /= 1024
        return f"{size_bytes:.1f} TB"
