"""
BioAgent File Ingestor — Main orchestration module.

Provides a unified interface for accepting data from any source,
detecting format, profiling content, assessing quality, and
registering files for downstream analysis by the agent.

Usage:
    ingestor = FileIngestor(workspace_dir="/workspace")

    # From a local file
    profile = ingestor.ingest("/data/experiment/reads_R1.fastq.gz")

    # From a URL
    profile = ingestor.ingest("https://ftp.example.com/sample.vcf.gz")

    # From S3
    profile = ingestor.ingest("s3://my-bucket/counts.csv")

    # From pasted data
    profile = ingestor.ingest(">seq1\nACGTACGTACGT\n>seq2\nTTTTAAAACCCC")

    # Multiple files at once
    profiles = ingestor.ingest_batch([
        "/data/sample1_R1.fastq.gz",
        "/data/sample1_R2.fastq.gz",
        "/data/metadata.csv",
    ])

    # Get agent-readable summary
    print(profile.to_agent_summary())
"""

import json
import os
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from data_input.data_source import DataSource, FetchedFile, FileFetcher
from data_input.format_detector import FormatDetector, FileFormat, FormatCategory
from data_input.profilers import (
    FileProfile,
    QualityFlag,
    AnalysisSuggestion,
    get_profiler,
)


@dataclass
class IngestResult:
    """Result of ingesting one or more files."""
    profiles: list[FileProfile]
    dataset_summary: str = ""       # Overall summary for multi-file ingests
    dataset_type: str = ""          # Detected dataset type
    recommended_workflow: str = ""  # Suggested end-to-end workflow

    def to_agent_context(self) -> str:
        """
        Generate a comprehensive context string for the agent.
        This is what gets injected into the conversation to help
        Claude reason about the data.
        """
        parts = []

        if self.dataset_summary:
            parts.append(f"# Dataset Summary\n{self.dataset_summary}")

        if self.dataset_type:
            parts.append(f"**Dataset Type**: {self.dataset_type}")

        if self.recommended_workflow:
            parts.append(f"**Recommended Workflow**: {self.recommended_workflow}")

        parts.append(f"\n# Files ({len(self.profiles)} ingested)\n")

        for profile in self.profiles:
            parts.append(profile.to_agent_summary())
            parts.append("---")

        return "\n\n".join(parts)


class FileIngestor:
    """
    Main file ingestion orchestrator.

    Handles the complete lifecycle:
    1. Source detection (local, URL, S3, raw data)
    2. Fetching to local workspace
    3. Format detection
    4. Format-specific profiling
    5. Quality assessment
    6. Analysis suggestions
    7. Registration for downstream use
    """

    def __init__(self, workspace_dir: str = "/workspace"):
        self.workspace_dir = Path(workspace_dir)
        self.fetcher = FileFetcher(workspace_dir=workspace_dir)
        self.detector = FormatDetector()

        # Registry of ingested files
        self._registry: dict[str, FileProfile] = {}
        self._registry_path = self.workspace_dir / "data" / "registry.json"

        # Load existing registry
        self._load_registry()

    # ── Main API ─────────────────────────────────────────────────

    def ingest(self, source_input: str, label: str = "") -> FileProfile:
        """
        Ingest a single file from any source.

        Args:
            source_input: File path, URL, S3 URI, or raw data
            label: Optional human label for the file

        Returns:
            FileProfile with comprehensive metadata and suggestions
        """
        # Step 1: Detect source type
        source = DataSource.detect(source_input)

        # Step 2: Fetch to local workspace
        fetched = self.fetcher.fetch(source)

        # Step 3: Detect format
        file_format = self.detector.detect(fetched.local_path)

        # Step 4: Profile
        profiler = get_profiler(file_format.name)
        profile_data = profiler.profile(fetched.local_path, file_format)

        # Step 5: Assemble FileProfile
        profile = FileProfile(
            file_path=str(fetched.local_path),
            file_name=fetched.original_name or fetched.local_path.name,
            file_format=file_format,
            size_bytes=fetched.size_bytes,
            size_human=fetched.size_human,
            md5=fetched.md5,
            stats=profile_data.get("stats", {}),
            preview=profile_data.get("preview", ""),
            column_info=profile_data.get("column_info", []),
            quality_flags=profile_data.get("quality_flags", []),
            overall_quality=profile_data.get("overall_quality", "unknown"),
            suggested_analyses=profile_data.get("suggested_analyses", []),
            companion_files=profile_data.get("companion_files", []),
            missing_companions=profile_data.get("missing_companions", []),
        )

        # Step 6: Register
        key = label or profile.file_name
        self._registry[key] = profile
        self._save_registry()

        return profile

    def ingest_batch(
        self, sources: list[str], labels: list[str] | None = None
    ) -> IngestResult:
        """
        Ingest multiple files and generate a dataset-level summary.

        Args:
            sources: List of file paths, URLs, S3 URIs, or raw data
            labels: Optional labels for each file

        Returns:
            IngestResult with individual profiles and dataset summary
        """
        labels = labels or [""] * len(sources)
        profiles = []

        for source, label in zip(sources, labels):
            try:
                profile = self.ingest(source, label=label)
                profiles.append(profile)
            except Exception as e:
                # Create a minimal error profile
                profiles.append(FileProfile(
                    file_path=source,
                    file_name=Path(source).name if "/" in source else source[:50],
                    file_format=FileFormat(
                        name="Error",
                        category=FormatCategory.OTHER,
                        extension="",
                    ),
                    size_bytes=0,
                    size_human="0 B",
                    md5="",
                    quality_flags=[QualityFlag(
                        level="error",
                        code="INGEST_FAILED",
                        message=f"Failed to ingest: {e}",
                    )],
                    overall_quality="poor",
                ))

        # Generate dataset-level analysis
        result = IngestResult(profiles=profiles)
        result.dataset_type = self._detect_dataset_type(profiles)
        result.dataset_summary = self._generate_dataset_summary(profiles, result.dataset_type)
        result.recommended_workflow = self._suggest_workflow(profiles, result.dataset_type)

        return result

    def ingest_directory(
        self,
        directory: str,
        pattern: str = "*",
        recursive: bool = False,
    ) -> IngestResult:
        """
        Ingest all matching files from a directory.

        Args:
            directory: Path to directory
            pattern: Glob pattern to match files
            recursive: Whether to search recursively

        Returns:
            IngestResult with all matched file profiles
        """
        dir_path = Path(directory)
        if not dir_path.is_dir():
            raise ValueError(f"Not a directory: {directory}")

        if recursive:
            files = sorted(dir_path.rglob(pattern))
        else:
            files = sorted(dir_path.glob(pattern))

        # Filter to files only (not directories)
        file_paths = [str(f) for f in files if f.is_file()]

        if not file_paths:
            return IngestResult(
                profiles=[],
                dataset_summary=f"No files matching '{pattern}' found in {directory}",
            )

        return self.ingest_batch(file_paths)

    # ── Registry Management ──────────────────────────────────────

    def get_profile(self, label_or_name: str) -> Optional[FileProfile]:
        """Retrieve a previously ingested file profile."""
        return self._registry.get(label_or_name)

    def list_ingested(self) -> list[dict]:
        """List all ingested files with basic info."""
        return [
            {
                "label": key,
                "file_name": profile.file_name,
                "format": profile.file_format.name,
                "size": profile.size_human,
                "quality": profile.overall_quality,
                "path": profile.file_path,
            }
            for key, profile in self._registry.items()
        ]

    def get_ingested_files_summary(self) -> str:
        """Get a summary of all ingested files for the agent."""
        if not self._registry:
            return "No files have been ingested yet."

        lines = ["## Ingested Files\n"]
        for key, profile in self._registry.items():
            quality_icon = {
                "good": "✅", "acceptable": "⚠️", "poor": "❌", "unknown": "❓"
            }.get(profile.overall_quality, "❓")
            lines.append(
                f"- {quality_icon} **{profile.file_name}** "
                f"({profile.file_format.name}, {profile.size_human}) "
                f"→ `{profile.file_path}`"
            )
        return "\n".join(lines)

    # ── Dataset Intelligence ─────────────────────────────────────

    def _detect_dataset_type(self, profiles: list[FileProfile]) -> str:
        """Infer what kind of dataset this is from the collection of files."""
        categories = Counter()
        format_names = []
        for p in profiles:
            if p.file_format.name != "Error":
                categories[p.file_format.category] += 1
                format_names.append(p.file_format.name)

        if not categories:
            return "unknown"

        # RNA-seq: FASTQ pairs or BAM + GTF
        fastq_count = sum(1 for n in format_names if "FASTQ" in n)
        bam_count = sum(1 for n in format_names if n in ("BAM", "SAM", "CRAM"))
        has_gtf = any(n in ("GTF", "GFF3", "GFF") for n in format_names)
        has_counts = any(n in ("CSV", "TSV") for n in format_names)

        if fastq_count >= 2:
            if has_gtf:
                return "RNA-seq (raw reads + annotation)"
            return "Sequencing reads (paired-end)" if fastq_count % 2 == 0 else "Sequencing reads"

        if bam_count > 0 and has_gtf:
            return "RNA-seq (aligned reads + annotation)"

        if bam_count > 0:
            return "Aligned sequencing data"

        # Variant analysis
        if any("VCF" in n or n == "BCF" for n in format_names):
            return "Variant data"

        # Expression analysis
        if has_counts:
            return "Tabular / expression data"

        # Single-cell
        if any(n in ("AnnData (h5ad)", "Matrix Market", "Loom") for n in format_names):
            return "Single-cell data"

        # Structure
        if any(n in ("PDB", "mmCIF") for n in format_names):
            return "Protein structure data"

        # Mixed
        top_category = categories.most_common(1)[0][0]
        return f"{top_category.value} data"

    def _generate_dataset_summary(
        self, profiles: list[FileProfile], dataset_type: str
    ) -> str:
        """Generate a human-readable dataset summary."""
        valid = [p for p in profiles if p.file_format.name != "Error"]
        failed = [p for p in profiles if p.file_format.name == "Error"]

        parts = [f"**Dataset type**: {dataset_type}"]
        parts.append(f"**Files ingested**: {len(valid)} successful, {len(failed)} failed")

        total_size = sum(p.size_bytes for p in valid)
        size_units = ["B", "KB", "MB", "GB", "TB"]
        size_val = total_size
        for unit in size_units:
            if size_val < 1024:
                parts.append(f"**Total size**: {size_val:.1f} {unit}")
                break
            size_val /= 1024

        # Format breakdown
        format_counts = Counter(p.file_format.name for p in valid)
        parts.append("**Format breakdown**: " + ", ".join(
            f"{count}× {fmt}" for fmt, count in format_counts.most_common()
        ))

        # Quality overview
        quality_counts = Counter(p.overall_quality for p in valid)
        parts.append("**Quality**: " + ", ".join(
            f"{count} {q}" for q, count in quality_counts.most_common()
        ))

        # Aggregate flags
        all_flags = []
        for p in valid:
            all_flags.extend(p.quality_flags)
        error_flags = [f for f in all_flags if f.level == "error"]
        warning_flags = [f for f in all_flags if f.level == "warning"]
        if error_flags:
            parts.append(f"**Errors**: {len(error_flags)} issues detected")
        if warning_flags:
            parts.append(f"**Warnings**: {len(warning_flags)} concerns")

        return "\n".join(parts)

    def _suggest_workflow(self, profiles: list[FileProfile], dataset_type: str) -> str:
        """Suggest an end-to-end workflow based on the dataset type."""
        workflows = {
            "RNA-seq (raw reads + annotation)": (
                "Complete RNA-seq pipeline: "
                "FastQC → fastp (trimming) → STAR (alignment) → "
                "featureCounts (quantification) → DESeq2 (differential expression) → "
                "clusterProfiler (pathway enrichment)"
            ),
            "RNA-seq (aligned reads + annotation)": (
                "Post-alignment RNA-seq: "
                "samtools flagstat (QC) → featureCounts (quantification) → "
                "DESeq2 (differential expression) → clusterProfiler (enrichment)"
            ),
            "Sequencing reads (paired-end)": (
                "Read processing pipeline: "
                "FastQC → fastp → BWA-MEM2/STAR alignment → "
                "samtools sort/index → downstream analysis"
            ),
            "Sequencing reads": (
                "Read processing: "
                "FastQC → fastp → alignment → downstream analysis"
            ),
            "Aligned sequencing data": (
                "Post-alignment analysis: "
                "samtools stats (QC) → variant calling or quantification"
            ),
            "Variant data": (
                "Variant analysis pipeline: "
                "bcftools stats (QC) → VEP annotation → "
                "pathogenicity prediction → gnomAD frequency check → "
                "clinical interpretation"
            ),
            "Tabular / expression data": (
                "Data analysis: "
                "Load and inspect → quality assessment → "
                "exploratory analysis → statistical testing → visualization"
            ),
            "Single-cell data": (
                "scRNA-seq pipeline: "
                "QC filtering → normalization → HVG selection → "
                "PCA → UMAP → clustering → cell type annotation → "
                "marker gene detection → differential expression"
            ),
            "Protein structure data": (
                "Structure analysis: "
                "Load structure → quality assessment → "
                "visualize → compare with AlphaFold → "
                "identify binding sites/domains"
            ),
        }

        return workflows.get(dataset_type, "Inspect data and determine appropriate analysis pipeline")

    # ── Persistence ──────────────────────────────────────────────

    def _save_registry(self):
        """Save the file registry to disk."""
        self._registry_path.parent.mkdir(parents=True, exist_ok=True)
        data = {}
        for key, profile in self._registry.items():
            data[key] = profile.to_dict()
        with open(self._registry_path, "w") as f:
            json.dump(data, f, indent=2, default=str)

    def _load_registry(self):
        """Load the file registry from disk."""
        if self._registry_path.exists():
            try:
                with open(self._registry_path) as f:
                    data = json.load(f)
                # We store as dicts; full reconstruction would need more work
                # For now, just track what was previously ingested
                self._registry = {}
            except Exception:
                self._registry = {}


# ── Helper for use from Counter ──────────────────────────────────
from collections import Counter
