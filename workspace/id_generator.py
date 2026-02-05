"""
Analysis ID generation utilities.

Generates unique, human-readable Analysis IDs in the format:
BIO-{YYYYMMDD}-{SEQ}[-{TAG}]

Examples:
  BIO-20250205-001              # First analysis of Feb 5, 2025
  BIO-20250205-002-rnaseq       # Second analysis, tagged as RNA-seq
  BIO-20250205-003-variant-tp53 # Third analysis, variant analysis of TP53
"""

import json
import re
from datetime import datetime
from pathlib import Path
from threading import Lock


class IDGenerator:
    """
    Generate unique, human-readable Analysis IDs.

    IDs are guaranteed unique within the workspace through persistent
    counter tracking per day.
    """

    def __init__(self, registry_path: Path, prefix: str = "BIO"):
        """
        Initialize the ID generator.

        Args:
            registry_path: Path to the registry directory
            prefix: Prefix for analysis IDs (default: "BIO")
        """
        self.registry_path = Path(registry_path)
        self.prefix = prefix
        self._counters_file = self.registry_path / "id_counters.json"
        self._counters: dict[str, int] = {}
        self._lock = Lock()
        self._load_counters()

    def _load_counters(self) -> None:
        """Load counters from persistent storage."""
        if self._counters_file.exists():
            try:
                with open(self._counters_file, "r") as f:
                    self._counters = json.load(f)
            except (json.JSONDecodeError, IOError):
                self._counters = {}
        else:
            self._counters = {}

    def _save_counters(self) -> None:
        """Save counters to persistent storage."""
        self.registry_path.mkdir(parents=True, exist_ok=True)
        with open(self._counters_file, "w") as f:
            json.dump(self._counters, f, indent=2)

    def _get_next_counter(self, date_str: str) -> int:
        """Get and increment the counter for a given date."""
        with self._lock:
            current = self._counters.get(date_str, 0)
            next_val = current + 1
            self._counters[date_str] = next_val
            self._save_counters()
            return next_val

    def _sanitize_tag(self, tag: str) -> str:
        """
        Sanitize a tag for use in an ID.

        - Lowercase
        - Replace spaces with hyphens
        - Remove invalid characters
        - Limit length
        """
        if not tag:
            return ""

        # Lowercase and replace spaces
        sanitized = tag.lower().replace(" ", "-").replace("_", "-")

        # Keep only alphanumeric and hyphens
        sanitized = re.sub(r"[^a-z0-9-]", "", sanitized)

        # Remove consecutive hyphens
        sanitized = re.sub(r"-+", "-", sanitized)

        # Remove leading/trailing hyphens
        sanitized = sanitized.strip("-")

        # Limit length (keep it reasonably short)
        if len(sanitized) > 30:
            sanitized = sanitized[:30].rsplit("-", 1)[0]

        return sanitized

    def generate(self, tag: str | None = None) -> str:
        """
        Generate the next analysis ID for today.

        Args:
            tag: Optional descriptive tag to append (e.g., "rnaseq", "variant-tp53")

        Returns:
            Analysis ID in format BIO-YYYYMMDD-NNN[-tag]

        Example:
            >>> gen = IDGenerator(Path("/workspace/registry"))
            >>> gen.generate()
            'BIO-20250205-001'
            >>> gen.generate("rnaseq")
            'BIO-20250205-002-rnaseq'
        """
        today = datetime.now().strftime("%Y%m%d")
        counter = self._get_next_counter(today)

        base_id = f"{self.prefix}-{today}-{counter:03d}"

        if tag:
            safe_tag = self._sanitize_tag(tag)
            if safe_tag:
                return f"{base_id}-{safe_tag}"

        return base_id

    def parse(self, analysis_id: str) -> dict[str, str | int | None]:
        """
        Parse an analysis ID into its components.

        Args:
            analysis_id: The ID to parse

        Returns:
            Dictionary with prefix, date, sequence, and optional tag

        Example:
            >>> gen.parse("BIO-20250205-001-rnaseq")
            {'prefix': 'BIO', 'date': '20250205', 'sequence': 1, 'tag': 'rnaseq'}
        """
        # Pattern: PREFIX-YYYYMMDD-NNN[-tag]
        pattern = r"^([A-Z]+)-(\d{8})-(\d{3})(?:-(.+))?$"
        match = re.match(pattern, analysis_id)

        if not match:
            return {
                "prefix": None,
                "date": None,
                "sequence": None,
                "tag": None,
                "valid": False,
            }

        return {
            "prefix": match.group(1),
            "date": match.group(2),
            "sequence": int(match.group(3)),
            "tag": match.group(4),
            "valid": True,
        }

    def is_valid(self, analysis_id: str) -> bool:
        """Check if an analysis ID is valid."""
        parsed = self.parse(analysis_id)
        return parsed.get("valid", False)

    def get_date(self, analysis_id: str) -> datetime | None:
        """Extract the date from an analysis ID."""
        parsed = self.parse(analysis_id)
        if not parsed.get("valid"):
            return None

        try:
            return datetime.strptime(parsed["date"], "%Y%m%d")
        except (ValueError, TypeError):
            return None

    def reset_counters(self) -> None:
        """Reset all counters (for testing)."""
        with self._lock:
            self._counters = {}
            self._save_counters()

    def get_current_count(self, date_str: str | None = None) -> int:
        """Get the current counter value for a date."""
        if date_str is None:
            date_str = datetime.now().strftime("%Y%m%d")
        return self._counters.get(date_str, 0)


def generate_file_id(file_path: str, analysis_id: str) -> str:
    """
    Generate a unique file ID based on path and analysis.

    Uses a hash of the file path and analysis ID for uniqueness.
    """
    import hashlib

    content = f"{analysis_id}:{file_path}"
    hash_val = hashlib.md5(content.encode()).hexdigest()[:12]
    return f"f-{hash_val}"
