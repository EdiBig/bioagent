"""
File profilers — generate rich metadata profiles for each file format.

Each profiler extracts format-specific statistics, quality metrics,
data previews, and flags potential issues. The agent uses this
information to reason about appropriate analysis approaches.
"""

import csv
import gzip
import io
import json
import os
import re
import subprocess
from abc import ABC, abstractmethod
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

from data_input.format_detector import FileFormat, FormatCategory


@dataclass
class QualityFlag:
    """A quality concern or issue detected in a file."""
    level: str          # "info", "warning", "error"
    code: str           # Machine-readable code
    message: str        # Human-readable description
    details: dict = field(default_factory=dict)


@dataclass
class AnalysisSuggestion:
    """A suggested analysis based on the file type and content."""
    name: str                       # e.g., "Differential Expression Analysis"
    description: str                # What it does
    tools: list[str]                # Recommended tools
    prerequisites: list[str]        # What else is needed
    priority: str = "suggested"     # "required", "suggested", "optional"
    example_query: str = ""         # Example query the user could type


@dataclass
class FileProfile:
    """
    Comprehensive profile of an ingested file.

    This is the primary output of the profiling system, consumed by
    the agent to reason about the data and suggest analyses.
    """
    file_path: str
    file_name: str
    file_format: FileFormat
    size_bytes: int
    size_human: str
    md5: str

    # ── Format-specific statistics ───────────────────────────────
    stats: dict[str, Any] = field(default_factory=dict)

    # ── Data preview ─────────────────────────────────────────────
    preview: str = ""               # First few lines / summary
    column_info: list[dict] = field(default_factory=list)  # For tabular data

    # ── Quality assessment ───────────────────────────────────────
    quality_flags: list[QualityFlag] = field(default_factory=list)
    overall_quality: str = "unknown"  # "good", "acceptable", "poor", "unknown"

    # ── Suggested analyses ───────────────────────────────────────
    suggested_analyses: list[AnalysisSuggestion] = field(default_factory=list)

    # ── Related files ────────────────────────────────────────────
    companion_files: list[str] = field(default_factory=list)  # .bai for .bam, etc.
    missing_companions: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        """Convert to dictionary for serialization / agent consumption."""
        return {
            "file_path": self.file_path,
            "file_name": self.file_name,
            "format": self.file_format.to_dict(),
            "size": self.size_human,
            "size_bytes": self.size_bytes,
            "md5": self.md5,
            "stats": self.stats,
            "preview": self.preview,
            "column_info": self.column_info,
            "quality_flags": [
                {"level": f.level, "code": f.code, "message": f.message}
                for f in self.quality_flags
            ],
            "overall_quality": self.overall_quality,
            "suggested_analyses": [
                {
                    "name": s.name,
                    "description": s.description,
                    "tools": s.tools,
                    "prerequisites": s.prerequisites,
                    "priority": s.priority,
                    "example_query": s.example_query,
                }
                for s in self.suggested_analyses
            ],
            "companion_files": self.companion_files,
            "missing_companions": self.missing_companions,
        }

    def to_agent_summary(self) -> str:
        """
        Generate a concise text summary for the agent's context window.
        This is what Claude sees when it needs to reason about the file.
        """
        parts = [
            f"## File Profile: {self.file_name}",
            f"- **Format**: {self.file_format.name} ({self.file_format.category.value})",
            f"- **Size**: {self.size_human}",
            f"- **Path**: {self.file_path}",
        ]

        if self.stats:
            parts.append("\n### Statistics")
            for key, value in self.stats.items():
                parts.append(f"- {key}: {value}")

        if self.column_info:
            parts.append("\n### Columns")
            for col in self.column_info[:20]:
                dtype = col.get("dtype", "")
                nulls = col.get("null_count", 0)
                parts.append(f"- `{col['name']}` ({dtype}, {nulls} nulls)")
            if len(self.column_info) > 20:
                parts.append(f"  ... and {len(self.column_info) - 20} more columns")

        if self.preview:
            parts.append(f"\n### Preview\n```\n{self.preview}\n```")

        if self.quality_flags:
            parts.append("\n### Quality Flags")
            for flag in self.quality_flags:
                icon = {"info": "ℹ️", "warning": "⚠️", "error": "❌"}.get(flag.level, "•")
                parts.append(f"- {icon} [{flag.code}] {flag.message}")

        parts.append(f"\n### Overall Quality: {self.overall_quality}")

        if self.suggested_analyses:
            parts.append("\n### Suggested Analyses")
            for suggestion in self.suggested_analyses:
                parts.append(
                    f"- **{suggestion.name}** ({suggestion.priority}): {suggestion.description}"
                )
                if suggestion.example_query:
                    parts.append(f"  Try: \"{suggestion.example_query}\"")

        if self.missing_companions:
            parts.append(f"\n### Missing Companion Files: {', '.join(self.missing_companions)}")

        return "\n".join(parts)


# ═══════════════════════════════════════════════════════════════════
# PROFILER IMPLEMENTATIONS
# ═══════════════════════════════════════════════════════════════════

class BaseProfiler(ABC):
    """Base class for format-specific profilers."""

    @abstractmethod
    def profile(self, filepath: Path, file_format: FileFormat) -> dict:
        """
        Generate format-specific profile data.

        Returns a dict with keys:
            stats: dict of statistics
            preview: str preview text
            column_info: list of column descriptors (tabular only)
            quality_flags: list of QualityFlag
            suggested_analyses: list of AnalysisSuggestion
            companion_files: list of found companion files
            missing_companions: list of expected but missing companions
        """
        pass


class FastqProfiler(BaseProfiler):
    """Profile FASTQ/FASTQ.gz sequencing read files."""

    def profile(self, filepath: Path, file_format: FileFormat) -> dict:
        stats = {}
        flags = []
        preview_lines = []

        open_func = gzip.open if file_format.is_binary else open
        mode = "rt" if file_format.is_binary else "r"

        try:
            read_count = 0
            total_bases = 0
            quality_scores = []
            gc_count = 0
            lengths = []
            max_reads_to_sample = 10_000

            with open_func(filepath, mode, errors="replace") as f:
                for i, line in enumerate(f):
                    line = line.strip()
                    record_pos = i % 4

                    # Capture preview (first 2 reads = 8 lines)
                    if i < 8:
                        preview_lines.append(line)

                    if record_pos == 0:  # Header
                        read_count += 1
                        if read_count > max_reads_to_sample:
                            break

                    elif record_pos == 1:  # Sequence
                        seq_len = len(line)
                        total_bases += seq_len
                        lengths.append(seq_len)
                        gc_count += line.upper().count("G") + line.upper().count("C")

                    elif record_pos == 3:  # Quality
                        scores = [ord(c) - 33 for c in line]
                        if scores:
                            quality_scores.extend(scores[:50])  # Sample first 50 per read

            # Estimate total reads if we sampled
            is_sampled = read_count >= max_reads_to_sample
            file_size = filepath.stat().st_size

            if is_sampled:
                # Rough estimate based on bytes per read
                bytes_per_read = file_size / max_reads_to_sample if max_reads_to_sample > 0 else 1
                estimated_total = int(file_size / bytes_per_read) if not file_format.is_binary else None
                stats["reads_sampled"] = max_reads_to_sample
                stats["estimated_total_reads"] = f"~{estimated_total:,}" if estimated_total else "unknown"
            else:
                stats["total_reads"] = f"{read_count:,}"

            avg_length = sum(lengths) / len(lengths) if lengths else 0
            stats["average_read_length"] = f"{avg_length:.0f} bp"
            stats["min_read_length"] = f"{min(lengths)} bp" if lengths else "N/A"
            stats["max_read_length"] = f"{max(lengths)} bp" if lengths else "N/A"

            gc_pct = (gc_count / total_bases * 100) if total_bases > 0 else 0
            stats["gc_content"] = f"{gc_pct:.1f}%"
            stats["total_bases_sampled"] = f"{total_bases:,}"

            if quality_scores:
                avg_qual = sum(quality_scores) / len(quality_scores)
                stats["mean_quality_score"] = f"{avg_qual:.1f} (Phred+33)"
                stats["min_quality_score"] = min(quality_scores)

                if avg_qual < 20:
                    flags.append(QualityFlag(
                        level="warning",
                        code="LOW_QUALITY",
                        message=f"Low average quality score ({avg_qual:.1f}). Consider quality trimming.",
                    ))
                if avg_qual < 10:
                    flags.append(QualityFlag(
                        level="error",
                        code="VERY_LOW_QUALITY",
                        message=f"Very low quality scores detected ({avg_qual:.1f}). Data may be unusable.",
                    ))

            if gc_pct < 30 or gc_pct > 65:
                flags.append(QualityFlag(
                    level="warning",
                    code="UNUSUAL_GC",
                    message=f"GC content ({gc_pct:.1f}%) is outside typical range (30-65%). May indicate contamination.",
                ))

            # Check for read length consistency
            if lengths and max(lengths) != min(lengths):
                flags.append(QualityFlag(
                    level="info",
                    code="VARIABLE_LENGTH",
                    message="Variable read lengths detected (may be already trimmed).",
                ))

        except Exception as e:
            flags.append(QualityFlag(
                level="error", code="READ_ERROR",
                message=f"Error reading FASTQ: {e}",
            ))

        # Look for paired-end mate
        companions, missing = self._check_paired_end(filepath)

        suggestions = [
            AnalysisSuggestion(
                name="Quality Control",
                description="Run FastQC/MultiQC for comprehensive read quality assessment",
                tools=["FastQC", "MultiQC", "fastp"],
                prerequisites=[],
                priority="required",
                example_query="Run FastQC on this FASTQ file and summarise the results",
            ),
            AnalysisSuggestion(
                name="Read Trimming",
                description="Trim adapters and low-quality bases",
                tools=["fastp", "trimmomatic", "cutadapt"],
                prerequisites=["Quality Control"],
                priority="suggested",
                example_query="Trim adapters and low-quality bases from this FASTQ file",
            ),
            AnalysisSuggestion(
                name="Alignment",
                description="Align reads to a reference genome",
                tools=["BWA-MEM2", "STAR (RNA-seq)", "HISAT2", "minimap2"],
                prerequisites=["Quality Control", "Reference genome"],
                priority="suggested",
                example_query="Align these reads to the GRCh38 reference genome",
            ),
        ]

        overall = "good"
        if any(f.level == "error" for f in flags):
            overall = "poor"
        elif any(f.level == "warning" for f in flags):
            overall = "acceptable"

        return {
            "stats": stats,
            "preview": "\n".join(preview_lines),
            "column_info": [],
            "quality_flags": flags,
            "suggested_analyses": suggestions,
            "companion_files": companions,
            "missing_companions": missing,
            "overall_quality": overall,
        }

    def _check_paired_end(self, filepath: Path) -> tuple[list[str], list[str]]:
        """Check for paired-end mate file."""
        name = filepath.name
        companions = []
        missing = []

        # Common paired-end naming patterns
        patterns = [
            (r"_1\.f", "_2.f"),
            (r"_R1", "_R2"),
            (r"_R1_001", "_R2_001"),
            (r"\.R1\.", ".R2."),
        ]

        for pattern, replacement in patterns:
            if re.search(pattern, name):
                mate_name = re.sub(pattern, replacement, name, count=1)
                mate_path = filepath.parent / mate_name
                if mate_path.exists():
                    companions.append(str(mate_path))
                else:
                    missing.append(f"Paired-end mate: {mate_name}")
                break

        return companions, missing


class VcfProfiler(BaseProfiler):
    """Profile VCF/VCF.gz variant call files."""

    def profile(self, filepath: Path, file_format: FileFormat) -> dict:
        stats = {}
        flags = []
        preview_lines = []

        is_gz = file_format.extension in (".vcf.gz",)
        open_func = gzip.open if is_gz else open
        mode = "rt" if is_gz else "r"

        try:
            variant_count = 0
            samples = []
            chroms = Counter()
            variant_types = Counter()
            filters = Counter()
            info_fields = set()
            max_variants_to_count = 100_000

            with open_func(filepath, mode, errors="replace") as f:
                for line in f:
                    line = line.strip()

                    if line.startswith("##"):
                        if len(preview_lines) < 10:
                            preview_lines.append(line)
                        # Parse header metadata
                        if line.startswith("##INFO="):
                            match = re.search(r'ID=(\w+)', line)
                            if match:
                                info_fields.add(match.group(1))
                        continue

                    if line.startswith("#CHROM"):
                        preview_lines.append(line)
                        fields = line.split("\t")
                        if len(fields) > 9:
                            samples = fields[9:]
                        continue

                    # Data line
                    variant_count += 1
                    if variant_count <= 5:
                        preview_lines.append(line[:200])

                    if variant_count <= max_variants_to_count:
                        fields = line.split("\t")
                        if len(fields) >= 8:
                            chroms[fields[0]] += 1
                            ref, alt = fields[3], fields[4]
                            filt = fields[6]
                            filters[filt] += 1

                            # Classify variant type
                            for allele in alt.split(","):
                                if len(ref) == len(allele) == 1:
                                    variant_types["SNV"] += 1
                                elif len(ref) == len(allele):
                                    variant_types["MNV"] += 1
                                elif len(ref) > len(allele):
                                    variant_types["Deletion"] += 1
                                elif len(ref) < len(allele):
                                    variant_types["Insertion"] += 1
                                else:
                                    variant_types["Complex"] += 1

            stats["total_variants"] = f"{variant_count:,}"
            stats["samples"] = len(samples)
            stats["sample_names"] = samples[:10]
            if len(samples) > 10:
                stats["sample_names"].append(f"... and {len(samples) - 10} more")
            stats["chromosomes"] = len(chroms)
            stats["variant_types"] = dict(variant_types.most_common())
            stats["filter_summary"] = dict(filters.most_common(10))
            stats["info_fields"] = sorted(info_fields)[:20]

            # Top chromosomes by variant count
            stats["variants_per_chromosome"] = dict(chroms.most_common(5))

            # Quality flags
            pass_count = filters.get("PASS", 0) + filters.get(".", 0)
            if variant_count > 0:
                pass_rate = pass_count / variant_count * 100
                stats["pass_rate"] = f"{pass_rate:.1f}%"
                if pass_rate < 50:
                    flags.append(QualityFlag(
                        level="warning",
                        code="LOW_PASS_RATE",
                        message=f"Only {pass_rate:.1f}% of variants pass filters.",
                    ))

            if variant_count == 0:
                flags.append(QualityFlag(
                    level="error", code="EMPTY_VCF",
                    message="VCF file contains no variants.",
                ))

            if len(samples) == 0:
                flags.append(QualityFlag(
                    level="info", code="SITES_ONLY",
                    message="VCF is sites-only (no sample genotypes).",
                ))

        except Exception as e:
            flags.append(QualityFlag(
                level="error", code="READ_ERROR",
                message=f"Error reading VCF: {e}",
            ))

        # Check for index
        companions, missing = [], []
        for idx_ext in [".tbi", ".csi"]:
            idx_path = Path(str(filepath) + idx_ext)
            if idx_path.exists():
                companions.append(str(idx_path))
        if is_gz and not companions:
            missing.append(f"Tabix index ({filepath.name}.tbi)")

        suggestions = [
            AnalysisSuggestion(
                name="Variant Statistics",
                description="Generate variant summary statistics (Ti/Tv, het/hom, per-sample counts)",
                tools=["bcftools stats", "rtg vcfstats"],
                prerequisites=[],
                priority="required",
                example_query="Generate variant statistics and QC metrics for this VCF",
            ),
            AnalysisSuggestion(
                name="Variant Annotation",
                description="Annotate variants with functional impact, gene names, population frequencies",
                tools=["VEP (Ensembl)", "SnpEff", "ANNOVAR"],
                prerequisites=[],
                priority="suggested",
                example_query="Annotate the variants with VEP and predict functional impact",
            ),
            AnalysisSuggestion(
                name="Pathogenicity Prediction",
                description="Score variants using CADD, REVEL, AlphaMissense",
                tools=["BioAgent ML: predict_variant_pathogenicity"],
                prerequisites=["Variant Annotation"],
                priority="suggested",
                example_query="Predict pathogenicity for the missense variants in this VCF",
            ),
            AnalysisSuggestion(
                name="Population Frequency Check",
                description="Check variant frequencies in gnomAD",
                tools=["gnomAD", "bcftools annotate"],
                prerequisites=[],
                priority="suggested",
                example_query="Check gnomAD population frequencies for all variants",
            ),
        ]

        overall = "good"
        if any(f.level == "error" for f in flags):
            overall = "poor"
        elif any(f.level == "warning" for f in flags):
            overall = "acceptable"

        return {
            "stats": stats,
            "preview": "\n".join(preview_lines),
            "column_info": [],
            "quality_flags": flags,
            "suggested_analyses": suggestions,
            "companion_files": companions,
            "missing_companions": missing,
            "overall_quality": overall,
        }


class TabularProfiler(BaseProfiler):
    """Profile CSV/TSV/Excel tabular data files."""

    def profile(self, filepath: Path, file_format: FileFormat) -> dict:
        stats = {}
        flags = []
        column_info = []
        preview_lines = []

        try:
            # Detect delimiter
            if file_format.name in ("Excel", "Excel (legacy)"):
                return self._profile_excel(filepath, file_format)

            delimiter = "\t" if file_format.name == "TSV" else ","

            with open(filepath, "r", encoding="utf-8", errors="replace") as f:
                # Sniff for actual delimiter
                sample = f.read(4096)
                f.seek(0)

                # Try to detect delimiter from first line
                first_line = sample.split("\n")[0]
                tab_count = first_line.count("\t")
                comma_count = first_line.count(",")
                if tab_count > comma_count:
                    delimiter = "\t"
                elif comma_count > tab_count:
                    delimiter = ","

                reader = csv.reader(f, delimiter=delimiter)

                # Read header
                try:
                    header = next(reader)
                except StopIteration:
                    flags.append(QualityFlag(
                        level="error", code="EMPTY_FILE",
                        message="File appears to be empty.",
                    ))
                    return {
                        "stats": stats, "preview": "", "column_info": [],
                        "quality_flags": flags, "suggested_analyses": [],
                        "companion_files": [], "missing_companions": [],
                        "overall_quality": "poor",
                    }

                stats["columns"] = len(header)
                preview_lines.append(delimiter.join(header))

                # Read data rows (sample up to 10k)
                rows = []
                row_count = 0
                for row in reader:
                    row_count += 1
                    if len(rows) < 10_000:
                        rows.append(row)
                    if row_count <= 5:
                        preview_lines.append(delimiter.join(row[:10]))

                stats["rows"] = f"{row_count:,}"
                stats["dimensions"] = f"{row_count} rows × {len(header)} columns"

            # Analyse columns
            for col_idx, col_name in enumerate(header):
                col_values = [
                    row[col_idx] for row in rows
                    if col_idx < len(row) and row[col_idx].strip()
                ]
                null_count = row_count - len(col_values)

                dtype = self._infer_dtype(col_values[:100])
                info = {
                    "name": col_name.strip(),
                    "dtype": dtype,
                    "null_count": null_count,
                    "null_pct": f"{null_count/row_count*100:.1f}%" if row_count > 0 else "0%",
                    "unique_values": len(set(col_values[:1000])),
                }

                if dtype == "numeric" and col_values:
                    nums = []
                    for v in col_values[:1000]:
                        try:
                            nums.append(float(v))
                        except ValueError:
                            pass
                    if nums:
                        info["min"] = min(nums)
                        info["max"] = max(nums)
                        info["mean"] = sum(nums) / len(nums)

                if dtype == "string" and col_values:
                    info["sample_values"] = list(set(col_values[:5]))

                column_info.append(info)

            # Detect what kind of biological data this might be
            header_lower = [h.lower().strip() for h in header]
            suggestions = self._suggest_analyses(header_lower, column_info, rows[:100])

            # Quality flags
            for col in column_info:
                null_pct = float(col["null_pct"].rstrip("%"))
                if null_pct > 50:
                    flags.append(QualityFlag(
                        level="warning",
                        code="HIGH_MISSING",
                        message=f"Column '{col['name']}' has {col['null_pct']} missing values.",
                    ))

            if row_count == 0:
                flags.append(QualityFlag(
                    level="error", code="NO_DATA_ROWS",
                    message="File has headers but no data rows.",
                ))

        except Exception as e:
            flags.append(QualityFlag(
                level="error", code="READ_ERROR",
                message=f"Error reading tabular file: {e}",
            ))

        overall = "good"
        if any(f.level == "error" for f in flags):
            overall = "poor"
        elif any(f.level == "warning" for f in flags):
            overall = "acceptable"

        return {
            "stats": stats,
            "preview": "\n".join(preview_lines[:10]),
            "column_info": column_info,
            "quality_flags": flags,
            "suggested_analyses": suggestions,
            "companion_files": [],
            "missing_companions": [],
            "overall_quality": overall,
        }

    def _profile_excel(self, filepath: Path, file_format: FileFormat) -> dict:
        """Profile Excel files using openpyxl or just report metadata."""
        stats = {"note": "Excel file detected. Use pandas or openpyxl for full profiling."}
        size = filepath.stat().st_size
        stats["file_size"] = f"{size / 1024:.1f} KB"

        return {
            "stats": stats,
            "preview": "(Binary Excel file — load with pandas for preview)",
            "column_info": [],
            "quality_flags": [],
            "suggested_analyses": [
                AnalysisSuggestion(
                    name="Load and Inspect",
                    description="Load Excel file and inspect its structure",
                    tools=["pandas (openpyxl)", "R (readxl)"],
                    prerequisites=[],
                    priority="required",
                    example_query="Load this Excel file and show me the sheet names and first few rows",
                ),
            ],
            "companion_files": [],
            "missing_companions": [],
            "overall_quality": "unknown",
        }

    def _infer_dtype(self, values: list[str]) -> str:
        """Infer column data type from sample values."""
        if not values:
            return "empty"

        numeric = 0
        integer = 0
        for v in values:
            v = v.strip()
            try:
                float(v)
                numeric += 1
                if "." not in v and "e" not in v.lower():
                    integer += 1
            except ValueError:
                pass

        ratio = numeric / len(values)
        if ratio > 0.8:
            if integer == numeric:
                return "integer"
            return "numeric"
        elif ratio > 0.5:
            return "mixed (mostly numeric)"
        else:
            return "string"

    def _suggest_analyses(
        self, header_lower: list[str], column_info: list[dict], sample_rows: list
    ) -> list[AnalysisSuggestion]:
        """Infer data type and suggest analyses based on column names."""
        suggestions = []

        # Detect gene expression count matrix
        expression_indicators = ["gene", "geneid", "gene_id", "gene_name", "symbol", "ensembl"]
        count_indicators = ["count", "counts", "tpm", "fpkm", "rpkm", "cpm"]

        has_genes = any(ind in h for h in header_lower for ind in expression_indicators)
        has_counts = any(ind in h for h in header_lower for ind in count_indicators)
        many_numeric_cols = sum(1 for c in column_info if c["dtype"] in ("numeric", "integer")) > 3

        # Check if this is already DE results (don't suggest running DE on DE output)
        de_indicators = ["log2foldchange", "log2fc", "logfc", "padj", "fdr", "pvalue", "p_value", "adj.p.val"]
        has_de_results = any(ind in h for h in header_lower for ind in de_indicators)

        if has_genes and (has_counts or many_numeric_cols) and not has_de_results:
            suggestions.append(AnalysisSuggestion(
                name="Differential Expression Analysis",
                description="Identify differentially expressed genes between conditions",
                tools=["DESeq2", "edgeR", "limma-voom"],
                prerequisites=["Sample metadata with condition labels"],
                priority="suggested",
                example_query="Run differential expression analysis on this count matrix. The conditions are in the column names.",
            ))
            suggestions.append(AnalysisSuggestion(
                name="Pathway Enrichment",
                description="Identify enriched biological pathways",
                tools=["clusterProfiler", "fgsea", "enrichR"],
                prerequisites=["Differential expression results"],
                priority="suggested",
                example_query="Find enriched GO terms and KEGG pathways in the differentially expressed genes",
            ))

        # Detect DEG results
        if has_de_results:
            suggestions.append(AnalysisSuggestion(
                name="Volcano Plot",
                description="Visualise differential expression results",
                tools=["matplotlib", "EnhancedVolcano (R)"],
                prerequisites=[],
                priority="suggested",
                example_query="Create a volcano plot from these DE results, highlighting the top 20 genes",
            ))
            # Only add enrichment if not already suggested from count matrix detection
            existing_names = {s.name for s in suggestions}
            if "Pathway Enrichment" not in existing_names:
                suggestions.append(AnalysisSuggestion(
                    name="Pathway Enrichment",
                    description="Run GO/KEGG enrichment on significant genes",
                    tools=["clusterProfiler", "fgsea", "KEGG", "Reactome"],
                    prerequisites=[],
                    priority="suggested",
                    example_query="Run pathway enrichment analysis on the significantly upregulated genes (padj < 0.05, log2FC > 1)",
                ))

        # Detect variant data
        variant_indicators = ["chrom", "chr", "chromosome", "pos", "position", "ref", "alt", "rsid"]
        if sum(1 for h in header_lower if any(v in h for v in variant_indicators)) >= 3:
            suggestions.append(AnalysisSuggestion(
                name="Variant Annotation",
                description="Annotate variants with functional predictions",
                tools=["VEP", "SnpEff", "gnomAD"],
                prerequisites=[],
                priority="suggested",
                example_query="Annotate these variants with VEP and predict pathogenicity",
            ))

        # Detect metadata / sample sheet
        metadata_indicators = ["sample", "sample_id", "condition", "group", "batch", "treatment", "timepoint"]
        if sum(1 for h in header_lower if any(m in h for m in metadata_indicators)) >= 2:
            suggestions.append(AnalysisSuggestion(
                name="Experimental Design Review",
                description="Assess experimental design, check for confounders and batch effects",
                tools=["PCA", "statistical tests"],
                prerequisites=["Expression data"],
                priority="suggested",
                example_query="Review this sample metadata for potential confounders and batch effects",
            ))

        # Default for any tabular data
        if not suggestions:
            suggestions.append(AnalysisSuggestion(
                name="Exploratory Analysis",
                description="Explore the data structure, distributions, and relationships",
                tools=["pandas", "matplotlib", "seaborn"],
                prerequisites=[],
                priority="suggested",
                example_query="Explore this dataset: show me distributions, correlations, and any patterns",
            ))

        return suggestions


class BamProfiler(BaseProfiler):
    """Profile BAM alignment files using samtools."""

    def profile(self, filepath: Path, file_format: FileFormat) -> dict:
        stats = {}
        flags = []

        # Try samtools for rich stats
        try:
            result = subprocess.run(
                ["samtools", "flagstat", str(filepath)],
                capture_output=True, text=True, timeout=120,
            )
            if result.returncode == 0:
                stats["flagstat"] = result.stdout.strip()
                # Parse key metrics
                for line in result.stdout.split("\n"):
                    if "in total" in line:
                        stats["total_reads"] = line.split("+")[0].strip()
                    elif "mapped (" in line:
                        stats["mapped_reads"] = line.split("+")[0].strip()
                        match = re.search(r"\((\d+\.?\d*)%", line)
                        if match:
                            map_rate = float(match.group(1))
                            stats["mapping_rate"] = f"{map_rate:.2f}%"
                            if map_rate < 70:
                                flags.append(QualityFlag(
                                    level="warning", code="LOW_MAPPING",
                                    message=f"Low mapping rate ({map_rate:.1f}%).",
                                ))
                    elif "duplicates" in line:
                        stats["duplicates"] = line.split("+")[0].strip()
                    elif "paired in sequencing" in line:
                        stats["paired_reads"] = line.split("+")[0].strip()
                    elif "properly paired" in line:
                        stats["properly_paired"] = line.split("+")[0].strip()
        except FileNotFoundError:
            stats["note"] = "samtools not available — install for detailed BAM profiling"
        except Exception as e:
            stats["note"] = f"Error running samtools: {e}"

        # Try idxstats if index exists
        idx_path = Path(str(filepath) + ".bai")
        if not idx_path.exists():
            idx_path = filepath.with_suffix(".bam.bai")

        if idx_path.exists():
            try:
                result = subprocess.run(
                    ["samtools", "idxstats", str(filepath)],
                    capture_output=True, text=True, timeout=60,
                )
                if result.returncode == 0:
                    chroms = {}
                    for line in result.stdout.strip().split("\n"):
                        parts = line.split("\t")
                        if len(parts) >= 3 and parts[0] != "*":
                            chroms[parts[0]] = int(parts[2])
                    stats["reads_per_chromosome"] = dict(
                        sorted(chroms.items(), key=lambda x: x[1], reverse=True)[:10]
                    )
            except Exception:
                pass

        # Check for index
        companions = []
        missing = []
        for ext in [".bai", ".bam.bai"]:
            p = Path(str(filepath) + ext) if ext == ".bai" else filepath.with_suffix(".bam.bai")
            if p.exists():
                companions.append(str(p))
        if not companions:
            missing.append(f"BAM index ({filepath.name}.bai) — run 'samtools index'")
            flags.append(QualityFlag(
                level="warning", code="NO_INDEX",
                message="BAM file is not indexed. Many tools require an index.",
            ))

        suggestions = [
            AnalysisSuggestion(
                name="Alignment QC",
                description="Comprehensive alignment quality metrics",
                tools=["samtools stats", "picard CollectAlignmentSummaryMetrics", "deepTools"],
                prerequisites=[],
                priority="required",
                example_query="Run comprehensive alignment QC on this BAM file",
            ),
            AnalysisSuggestion(
                name="Variant Calling",
                description="Call variants from the aligned reads",
                tools=["GATK HaplotypeCaller", "DeepVariant", "bcftools mpileup"],
                prerequisites=["Reference genome"],
                priority="suggested",
                example_query="Call variants from this BAM file using GATK HaplotypeCaller",
            ),
            AnalysisSuggestion(
                name="Read Quantification",
                description="Count reads per gene/feature (RNA-seq)",
                tools=["featureCounts", "HTSeq", "Salmon"],
                prerequisites=["Gene annotation (GTF)"],
                priority="suggested",
                example_query="Count reads per gene using featureCounts with the GENCODE annotation",
            ),
        ]

        overall = "good"
        if any(f.level == "error" for f in flags):
            overall = "poor"
        elif any(f.level == "warning" for f in flags):
            overall = "acceptable"

        return {
            "stats": stats,
            "preview": stats.get("flagstat", "(Use samtools for BAM preview)"),
            "column_info": [],
            "quality_flags": flags,
            "suggested_analyses": suggestions,
            "companion_files": companions,
            "missing_companions": missing,
            "overall_quality": overall,
        }


class BedProfiler(BaseProfiler):
    """Profile BED genomic interval files."""

    def profile(self, filepath: Path, file_format: FileFormat) -> dict:
        stats = {}
        flags = []
        preview_lines = []

        try:
            region_count = 0
            chroms = Counter()
            total_length = 0
            min_length = float("inf")
            max_length = 0
            num_columns = 0

            with open(filepath, "r") as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith(("#", "track", "browser")):
                        continue

                    if region_count < 5:
                        preview_lines.append(line[:200])

                    fields = line.split("\t")
                    if region_count == 0:
                        num_columns = len(fields)

                    region_count += 1

                    if len(fields) >= 3:
                        chroms[fields[0]] += 1
                        try:
                            start = int(fields[1])
                            end = int(fields[2])
                            length = end - start
                            total_length += length
                            min_length = min(min_length, length)
                            max_length = max(max_length, length)
                        except ValueError:
                            pass

            stats["total_regions"] = f"{region_count:,}"
            stats["columns"] = num_columns
            stats["chromosomes"] = len(chroms)
            stats["total_coverage"] = f"{total_length:,} bp"
            if region_count > 0:
                stats["mean_region_length"] = f"{total_length / region_count:.0f} bp"
                stats["min_region_length"] = f"{min_length:,} bp" if min_length != float("inf") else "N/A"
                stats["max_region_length"] = f"{max_length:,} bp"

            if region_count == 0:
                flags.append(QualityFlag(
                    level="error", code="EMPTY_BED",
                    message="BED file contains no regions.",
                ))

        except Exception as e:
            flags.append(QualityFlag(
                level="error", code="READ_ERROR", message=f"Error reading BED: {e}",
            ))

        suggestions = [
            AnalysisSuggestion(
                name="Region Analysis",
                description="Analyse coverage, overlaps, and annotation of genomic regions",
                tools=["bedtools", "deepTools"],
                prerequisites=[],
                priority="suggested",
                example_query="Analyse these genomic regions: check overlaps with genes and regulatory elements",
            ),
        ]

        overall = "good" if not flags else ("poor" if any(f.level == "error" for f in flags) else "acceptable")

        return {
            "stats": stats,
            "preview": "\n".join(preview_lines),
            "column_info": [],
            "quality_flags": flags,
            "suggested_analyses": suggestions,
            "companion_files": [],
            "missing_companions": [],
            "overall_quality": overall,
        }


class FastaProfiler(BaseProfiler):
    """Profile FASTA sequence files."""

    def profile(self, filepath: Path, file_format: FileFormat) -> dict:
        stats = {}
        flags = []
        preview_lines = []

        is_gz = "gz" in file_format.extension
        open_func = gzip.open if is_gz else open
        mode = "rt" if is_gz else "r"

        try:
            seq_count = 0
            total_length = 0
            lengths = []
            gc_count = 0
            headers = []

            with open_func(filepath, mode, errors="replace") as f:
                current_length = 0
                for line in f:
                    line = line.strip()
                    if seq_count < 3 and len(preview_lines) < 8:
                        preview_lines.append(line[:100])

                    if line.startswith(">"):
                        if current_length > 0:
                            lengths.append(current_length)
                            total_length += current_length
                        current_length = 0
                        seq_count += 1
                        headers.append(line[1:].split()[0])
                    else:
                        current_length += len(line)
                        gc_count += line.upper().count("G") + line.upper().count("C")

                # Don't forget last sequence
                if current_length > 0:
                    lengths.append(current_length)
                    total_length += current_length

            stats["total_sequences"] = f"{seq_count:,}"
            stats["total_length"] = f"{total_length:,} bp/aa"
            if lengths:
                stats["mean_length"] = f"{sum(lengths)/len(lengths):.0f}"
                stats["min_length"] = f"{min(lengths):,}"
                stats["max_length"] = f"{max(lengths):,}"

                # N50
                sorted_lengths = sorted(lengths, reverse=True)
                cumulative = 0
                for l in sorted_lengths:
                    cumulative += l
                    if cumulative >= total_length / 2:
                        stats["N50"] = f"{l:,}"
                        break

            if total_length > 0:
                gc_pct = gc_count / total_length * 100
                stats["gc_content"] = f"{gc_pct:.1f}%"

            stats["first_headers"] = headers[:5]

            # Detect if protein or nucleotide
            if total_length > 0 and gc_count / total_length < 0.1:
                stats["sequence_type"] = "protein"
            else:
                stats["sequence_type"] = "nucleotide"

        except Exception as e:
            flags.append(QualityFlag(
                level="error", code="READ_ERROR", message=f"Error reading FASTA: {e}",
            ))

        suggestions = [
            AnalysisSuggestion(
                name="Sequence Search",
                description="Search sequences against databases",
                tools=["BLAST", "DIAMOND", "MMseqs2"],
                prerequisites=[],
                priority="suggested",
                example_query="BLAST these sequences against the nr database",
            ),
            AnalysisSuggestion(
                name="Multiple Sequence Alignment",
                description="Align sequences and build phylogeny",
                tools=["MAFFT", "MUSCLE", "ClustalOmega"],
                prerequisites=[],
                priority="suggested",
                example_query="Align these sequences with MAFFT and build a phylogenetic tree",
            ),
        ]

        overall = "good" if not flags else "poor"

        return {
            "stats": stats,
            "preview": "\n".join(preview_lines),
            "column_info": [],
            "quality_flags": flags,
            "suggested_analyses": suggestions,
            "companion_files": [],
            "missing_companions": [],
            "overall_quality": overall,
        }


class GenericProfiler(BaseProfiler):
    """Fallback profiler for unrecognised or unsupported formats."""

    def profile(self, filepath: Path, file_format: FileFormat) -> dict:
        stats = {}
        preview = ""

        if not file_format.is_binary:
            try:
                with open(filepath, "r", encoding="utf-8", errors="replace") as f:
                    lines = [f.readline() for _ in range(20)]
                    line_count = sum(1 for _ in f) + len(lines)
                preview = "".join(lines)
                stats["line_count"] = f"{line_count:,}"
            except Exception:
                preview = "(Could not read file preview)"
        else:
            preview = f"(Binary file, {filepath.stat().st_size:,} bytes)"

        return {
            "stats": stats,
            "preview": preview[:2000],
            "column_info": [],
            "quality_flags": [],
            "suggested_analyses": [
                AnalysisSuggestion(
                    name="Inspect File",
                    description="Examine file contents and determine appropriate analysis",
                    tools=["file", "head", "hexdump"],
                    prerequisites=[],
                    priority="suggested",
                    example_query=f"Inspect the file {filepath.name} and tell me what it contains",
                ),
            ],
            "companion_files": [],
            "missing_companions": [],
            "overall_quality": "unknown",
        }


# ── Profiler Registry ────────────────────────────────────────────

PROFILER_MAP: dict[str, BaseProfiler] = {
    "FASTQ": FastqProfiler(),
    "FASTQ (gzipped)": FastqProfiler(),
    "FASTA": FastaProfiler(),
    "FASTA (gzipped)": FastaProfiler(),
    "VCF": VcfProfiler(),
    "VCF (bgzipped)": VcfProfiler(),
    "BAM": BamProfiler(),
    "SAM": BamProfiler(),
    "CRAM": BamProfiler(),
    "BED": BedProfiler(),
    "CSV": TabularProfiler(),
    "TSV": TabularProfiler(),
    "Excel": TabularProfiler(),
    "Excel (legacy)": TabularProfiler(),
    "Parquet": TabularProfiler(),
}


def get_profiler(format_name: str) -> BaseProfiler:
    """Get the appropriate profiler for a file format."""
    return PROFILER_MAP.get(format_name, GenericProfiler())
