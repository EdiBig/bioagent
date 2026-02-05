"""
Data source abstraction for BioAgent file ingestion.

Handles fetching files from multiple sources into the local workspace:
- Local file paths
- HTTP/FTP URLs
- S3 bucket paths
- Google Cloud Storage paths
- Raw pasted data (e.g., FASTA sequences from chat)
"""

import hashlib
import os
import shutil
import subprocess
import tempfile
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Optional
from datetime import datetime


class SourceType(str, Enum):
    LOCAL = "local"
    URL = "url"
    S3 = "s3"
    GCS = "gcs"
    RAW = "raw"           # Pasted data / inline content
    UPLOAD = "upload"      # Web upload (future web app)


@dataclass
class DataSource:
    """
    Represents an input data source before it's been fetched.

    Examples:
        DataSource.from_path("/data/samples/reads_1.fastq.gz")
        DataSource.from_url("https://example.com/variants.vcf")
        DataSource.from_s3("s3://my-bucket/experiment/counts.csv")
        DataSource.from_raw(">seq1\nACGTACGT", suggested_name="query.fasta")
    """
    source_type: SourceType
    location: str                 # Path, URL, or S3 URI
    original_name: str = ""       # Original filename
    suggested_name: str = ""      # User-suggested name for raw data
    metadata: dict = field(default_factory=dict)

    @classmethod
    def from_path(cls, path: str) -> "DataSource":
        """Create from a local file path."""
        p = Path(path)
        return cls(
            source_type=SourceType.LOCAL,
            location=str(p.resolve()),
            original_name=p.name,
        )

    @classmethod
    def from_url(cls, url: str) -> "DataSource":
        """Create from an HTTP/HTTPS/FTP URL."""
        parsed = urllib.parse.urlparse(url)
        name = Path(parsed.path).name or "downloaded_file"
        return cls(
            source_type=SourceType.URL,
            location=url,
            original_name=name,
        )

    @classmethod
    def from_s3(cls, uri: str) -> "DataSource":
        """Create from an S3 URI (s3://bucket/key)."""
        # Parse s3://bucket/path/to/file.ext
        parts = uri.replace("s3://", "").split("/", 1)
        bucket = parts[0]
        key = parts[1] if len(parts) > 1 else ""
        name = Path(key).name if key else "s3_file"
        return cls(
            source_type=SourceType.S3,
            location=uri,
            original_name=name,
            metadata={"bucket": bucket, "key": key},
        )

    @classmethod
    def from_gcs(cls, uri: str) -> "DataSource":
        """Create from a GCS URI (gs://bucket/key)."""
        parts = uri.replace("gs://", "").split("/", 1)
        bucket = parts[0]
        key = parts[1] if len(parts) > 1 else ""
        name = Path(key).name if key else "gcs_file"
        return cls(
            source_type=SourceType.GCS,
            location=uri,
            original_name=name,
            metadata={"bucket": bucket, "key": key},
        )

    @classmethod
    def from_raw(cls, content: str, suggested_name: str = "input_data.txt") -> "DataSource":
        """Create from raw pasted content (e.g., a FASTA sequence)."""
        return cls(
            source_type=SourceType.RAW,
            location="<inline>",
            original_name=suggested_name,
            suggested_name=suggested_name,
            metadata={"content": content, "size": len(content)},
        )

    @classmethod
    def from_upload(cls, upload_path: str, original_name: str) -> "DataSource":
        """Create from a web upload (file already on disk in temp location)."""
        return cls(
            source_type=SourceType.UPLOAD,
            location=upload_path,
            original_name=original_name,
        )

    @classmethod
    def detect(cls, source_string: str) -> "DataSource":
        """
        Auto-detect source type from a string.

        Handles:
            /path/to/file.vcf          → LOCAL
            https://example.com/f.gz   → URL
            ftp://server.com/data.fa   → URL
            s3://bucket/key            → S3
            gs://bucket/key            → GCS
            >seq1\nACGT...            → RAW (FASTA)
            ACGTACGTACGT...           → RAW (sequence)
        """
        source_string = source_string.strip()

        if source_string.startswith("s3://"):
            return cls.from_s3(source_string)
        elif source_string.startswith("gs://"):
            return cls.from_gcs(source_string)
        elif source_string.startswith(("http://", "https://", "ftp://")):
            return cls.from_url(source_string)
        elif source_string.startswith(">") or _looks_like_sequence(source_string):
            fmt = "fasta" if source_string.startswith(">") else "txt"
            return cls.from_raw(source_string, suggested_name=f"input.{fmt}")
        elif os.path.exists(source_string):
            return cls.from_path(source_string)
        elif "/" in source_string or "\\" in source_string:
            # Looks like a path even if it doesn't exist yet
            return cls.from_path(source_string)
        else:
            # Assume raw data
            return cls.from_raw(source_string, suggested_name="input_data.txt")


@dataclass
class FetchedFile:
    """
    A file that has been fetched into the local workspace.
    Ready for profiling and analysis.
    """
    local_path: Path
    original_name: str
    source: DataSource
    size_bytes: int
    md5: str
    fetch_time: datetime
    is_compressed: bool = False
    compression_type: str = ""      # gzip, bzip2, xz, zip

    @property
    def extension(self) -> str:
        """Get the file extension (handles .fastq.gz etc.)."""
        name = self.local_path.name
        # Handle double extensions
        double_ext_patterns = [
            ".fastq.gz", ".fasta.gz", ".fa.gz", ".fq.gz",
            ".vcf.gz", ".bed.gz", ".gff.gz", ".gtf.gz",
            ".sam.gz", ".tar.gz", ".tar.bz2", ".tar.xz",
            ".csv.gz", ".tsv.gz",
        ]
        name_lower = name.lower()
        for pattern in double_ext_patterns:
            if name_lower.endswith(pattern):
                return pattern
        return self.local_path.suffix.lower()

    @property
    def size_human(self) -> str:
        """Human-readable file size."""
        size = self.size_bytes
        for unit in ["B", "KB", "MB", "GB", "TB"]:
            if size < 1024:
                return f"{size:.1f} {unit}" if unit != "B" else f"{size} {unit}"
            size /= 1024
        return f"{size:.1f} PB"


class FileFetcher:
    """
    Fetches files from various sources into the local workspace.
    """

    def __init__(self, workspace_dir: str = "/workspace/data"):
        self.workspace_dir = Path(workspace_dir)
        self.workspace_dir.mkdir(parents=True, exist_ok=True)
        self.ingested_dir = self.workspace_dir / "ingested"
        self.ingested_dir.mkdir(exist_ok=True)

    def fetch(self, source: DataSource, target_name: str = "") -> FetchedFile:
        """
        Fetch a file from any source into the workspace.

        Args:
            source: The data source to fetch
            target_name: Override filename in workspace (optional)

        Returns:
            FetchedFile with local path and metadata
        """
        filename = target_name or source.suggested_name or source.original_name
        target_path = self.ingested_dir / filename

        # Avoid overwriting — add suffix if exists
        if target_path.exists():
            stem = target_path.stem
            suffix = target_path.suffix
            counter = 1
            while target_path.exists():
                target_path = self.ingested_dir / f"{stem}_{counter}{suffix}"
                counter += 1

        if source.source_type == SourceType.LOCAL:
            target_path = self._fetch_local(source.location, target_path)
        elif source.source_type == SourceType.URL:
            target_path = self._fetch_url(source.location, target_path)
        elif source.source_type == SourceType.S3:
            target_path = self._fetch_s3(source.location, target_path)
        elif source.source_type == SourceType.GCS:
            target_path = self._fetch_gcs(source.location, target_path)
        elif source.source_type == SourceType.RAW:
            target_path = self._fetch_raw(source.metadata["content"], target_path)
        elif source.source_type == SourceType.UPLOAD:
            target_path = self._fetch_local(source.location, target_path)
        else:
            raise ValueError(f"Unsupported source type: {source.source_type}")

        # Compute metadata
        size = target_path.stat().st_size
        md5 = self._compute_md5(target_path)
        is_compressed, comp_type = self._detect_compression(target_path)

        return FetchedFile(
            local_path=target_path,
            original_name=source.original_name,
            source=source,
            size_bytes=size,
            md5=md5,
            fetch_time=datetime.now(),
            is_compressed=is_compressed,
            compression_type=comp_type,
        )

    def fetch_multiple(self, sources: list[DataSource]) -> list[FetchedFile]:
        """Fetch multiple files. Returns list of FetchedFile objects."""
        results = []
        for source in sources:
            try:
                fetched = self.fetch(source)
                results.append(fetched)
            except Exception as e:
                # Log error but continue with other files
                print(f"Error fetching {source.location}: {e}")
        return results

    # ── Fetch implementations ────────────────────────────────────────

    def _fetch_local(self, path: str, target: Path) -> Path:
        """Copy a local file to the workspace."""
        src = Path(path)
        if not src.exists():
            raise FileNotFoundError(f"File not found: {path}")
        if src.resolve() == target.resolve():
            return target  # Already in workspace
        shutil.copy2(src, target)
        return target

    def _fetch_url(self, url: str, target: Path) -> Path:
        """Download a file from HTTP/HTTPS/FTP."""
        try:
            req = urllib.request.Request(
                url,
                headers={"User-Agent": "BioAgent/1.0"},
            )
            with urllib.request.urlopen(req, timeout=300) as response:
                with open(target, "wb") as f:
                    shutil.copyfileobj(response, f)
            return target
        except Exception as e:
            raise RuntimeError(f"Failed to download {url}: {e}")

    def _fetch_s3(self, uri: str, target: Path) -> Path:
        """Download from S3 using AWS CLI."""
        result = subprocess.run(
            ["aws", "s3", "cp", uri, str(target)],
            capture_output=True, text=True, timeout=600,
        )
        if result.returncode != 0:
            raise RuntimeError(f"S3 download failed: {result.stderr}")
        return target

    def _fetch_gcs(self, uri: str, target: Path) -> Path:
        """Download from GCS using gsutil."""
        result = subprocess.run(
            ["gsutil", "cp", uri, str(target)],
            capture_output=True, text=True, timeout=600,
        )
        if result.returncode != 0:
            raise RuntimeError(f"GCS download failed: {result.stderr}")
        return target

    def _fetch_raw(self, content: str, target: Path) -> Path:
        """Write raw content to a file."""
        with open(target, "w", encoding="utf-8") as f:
            f.write(content)
        return target

    # ── Utilities ────────────────────────────────────────────────────

    @staticmethod
    def _compute_md5(path: Path, chunk_size: int = 8192) -> str:
        """Compute MD5 checksum of a file."""
        h = hashlib.md5()
        with open(path, "rb") as f:
            while chunk := f.read(chunk_size):
                h.update(chunk)
        return h.hexdigest()

    @staticmethod
    def _detect_compression(path: Path) -> tuple[bool, str]:
        """Detect if a file is compressed and what type."""
        try:
            with open(path, "rb") as f:
                magic = f.read(6)
        except Exception:
            return False, ""

        if magic[:2] == b"\x1f\x8b":
            return True, "gzip"
        elif magic[:3] == b"BZh":
            return True, "bzip2"
        elif magic[:6] == b"\xfd7zXZ\x00":
            return True, "xz"
        elif magic[:4] == b"PK\x03\x04":
            return True, "zip"
        elif magic[:4] == b"\x42\x41\x4d\x01":
            return True, "bam"  # BAM is bgzf-compressed
        elif magic[:4] == b"CRAM":
            return True, "cram"
        else:
            return False, ""


def _looks_like_sequence(text: str) -> bool:
    """Check if text looks like a raw nucleotide or protein sequence."""
    text = text.strip().upper().replace("\n", "").replace(" ", "")
    if len(text) < 10:
        return False
    nucleotide_chars = set("ACGTURYKMSWBDHVN")
    protein_chars = set("ACDEFGHIKLMNPQRSTVWY")
    chars = set(text)
    return chars.issubset(nucleotide_chars) or chars.issubset(protein_chars)
