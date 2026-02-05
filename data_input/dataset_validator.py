"""
Dataset validation — checks that ingested files form a coherent
dataset suitable for a specific type of analysis.

Validates cross-file consistency, required companions, and
readiness for downstream analysis tools.
"""

from dataclasses import dataclass, field
from data_input.profilers import FileProfile, QualityFlag
from data_input.format_detector import FormatCategory


@dataclass
class ValidationResult:
    """Result of dataset validation."""
    is_valid: bool = False
    analysis_type: str = ""
    checks_passed: list[str] = field(default_factory=list)
    checks_failed: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    missing_files: list[str] = field(default_factory=list)
    ready_to_analyse: bool = False
    suggested_fixes: list[str] = field(default_factory=list)

    def to_agent_summary(self) -> str:
        icon = "✅" if self.is_valid else "❌"
        parts = [
            f"{icon} **Dataset Validation: {self.analysis_type}**",
            f"Ready to analyse: {'Yes' if self.ready_to_analyse else 'No'}",
        ]

        if self.checks_passed:
            parts.append("\n**Passed:**")
            for check in self.checks_passed:
                parts.append(f"  ✓ {check}")

        if self.checks_failed:
            parts.append("\n**Failed:**")
            for check in self.checks_failed:
                parts.append(f"  ✗ {check}")

        if self.warnings:
            parts.append("\n**Warnings:**")
            for w in self.warnings:
                parts.append(f"  ⚠️ {w}")

        if self.missing_files:
            parts.append("\n**Missing files:**")
            for m in self.missing_files:
                parts.append(f"  • {m}")

        if self.suggested_fixes:
            parts.append("\n**Suggested fixes:**")
            for fix in self.suggested_fixes:
                parts.append(f"  → {fix}")

        return "\n".join(parts)


class DatasetValidator:
    """Validates that a set of files is ready for a specific analysis."""

    def validate(
        self,
        profiles: list[FileProfile],
        analysis_type: str = "auto",
    ) -> ValidationResult:
        """
        Validate a dataset for a specific analysis type.

        Args:
            profiles: List of FileProfile objects
            analysis_type: Type of analysis ('rnaseq', 'variant', etc.)

        Returns:
            ValidationResult with pass/fail details
        """
        if analysis_type == "auto":
            analysis_type = self._detect_analysis_type(profiles)

        validators = {
            "rnaseq": self._validate_rnaseq,
            "variant": self._validate_variant,
            "singlecell": self._validate_singlecell,
            "alignment": self._validate_alignment,
        }

        validator = validators.get(analysis_type, self._validate_generic)
        return validator(profiles)

    def _detect_analysis_type(self, profiles: list[FileProfile]) -> str:
        """Auto-detect the most likely analysis type."""
        formats = [p.file_format.name for p in profiles]
        categories = [p.file_format.category for p in profiles]

        if any("h5ad" in f or "Loom" in f or "Matrix Market" in f for f in formats):
            return "singlecell"
        if any("VCF" in f or f == "BCF" for f in formats):
            return "variant"
        if any("FASTQ" in f for f in formats):
            return "alignment"

        # Check tabular data for expression signatures
        for p in profiles:
            if p.file_format.category == FormatCategory.TABULAR:
                col_names = [c.get("name", "").lower() for c in p.column_info]
                if any("gene" in c or "ensembl" in c for c in col_names):
                    return "rnaseq"

        return "generic"

    def _validate_rnaseq(self, profiles: list[FileProfile]) -> ValidationResult:
        """Validate files for RNA-seq differential expression analysis."""
        result = ValidationResult(analysis_type="RNA-seq Analysis")

        # Check for expression data
        has_counts = False
        has_metadata = False
        has_annotation = False

        for p in profiles:
            fmt = p.file_format.name
            cols = [c.get("name", "").lower() for c in p.column_info]

            if p.file_format.category == FormatCategory.TABULAR:
                if any("gene" in c or "ensembl" in c or "symbol" in c for c in cols):
                    numeric_cols = sum(
                        1 for c in p.column_info
                        if c.get("dtype", "") in ("numeric", "integer")
                    )
                    if numeric_cols >= 2:
                        has_counts = True
                        result.checks_passed.append(
                            f"Expression matrix found: {p.file_name} "
                            f"({p.stats.get('rows', '?')} genes × {numeric_cols} samples)"
                        )

                if any(m in c for c in cols for m in [
                    "sample", "condition", "group", "treatment", "batch"
                ]):
                    has_metadata = True
                    result.checks_passed.append(f"Sample metadata found: {p.file_name}")

            if fmt in ("GTF", "GFF3", "GFF"):
                has_annotation = True
                result.checks_passed.append(f"Gene annotation found: {p.file_name}")

        if not has_counts:
            result.checks_failed.append("No expression count matrix detected")
            result.missing_files.append(
                "Count matrix (CSV/TSV with gene IDs and sample counts)"
            )
            result.suggested_fixes.append(
                "Provide a count matrix file (genes as rows, samples as columns)"
            )

        if not has_metadata:
            result.warnings.append("No sample metadata file detected")
            result.suggested_fixes.append(
                "Provide a metadata CSV with columns: sample_id, condition "
                "(and optionally: batch, sex, age, etc.)"
            )

        if not has_annotation:
            result.warnings.append(
                "No gene annotation (GTF/GFF) — will use gene IDs for enrichment"
            )

        # Check data quality
        for p in profiles:
            error_flags = [f for f in p.quality_flags if f.level == "error"]
            if error_flags:
                result.checks_failed.append(
                    f"Quality issues in {p.file_name}: "
                    + "; ".join(f.message for f in error_flags)
                )

        result.is_valid = has_counts
        result.ready_to_analyse = has_counts  # Metadata is nice but not required
        return result

    def _validate_variant(self, profiles: list[FileProfile]) -> ValidationResult:
        """Validate files for variant analysis."""
        result = ValidationResult(analysis_type="Variant Analysis")

        has_vcf = False
        total_variants = 0

        for p in profiles:
            if "VCF" in p.file_format.name or p.file_format.name == "BCF":
                has_vcf = True
                variant_str = p.stats.get("total_variants", "0").replace(",", "")
                try:
                    total_variants += int(variant_str)
                except ValueError:
                    pass
                result.checks_passed.append(
                    f"VCF found: {p.file_name} "
                    f"({p.stats.get('total_variants', '?')} variants, "
                    f"{p.stats.get('samples', '?')} samples)"
                )

                # Check for index
                if p.missing_companions:
                    result.warnings.append(
                        f"Missing index for {p.file_name} — "
                        "some tools require tabix index"
                    )
                    result.suggested_fixes.append(
                        f"Create index: tabix -p vcf {p.file_name}"
                    )

        if not has_vcf:
            result.checks_failed.append("No VCF/BCF file found")
            result.missing_files.append("VCF file with variants")

        if total_variants == 0 and has_vcf:
            result.checks_failed.append("VCF file(s) contain no variants")

        result.is_valid = has_vcf and total_variants > 0
        result.ready_to_analyse = result.is_valid
        return result

    def _validate_singlecell(self, profiles: list[FileProfile]) -> ValidationResult:
        """Validate files for single-cell analysis."""
        result = ValidationResult(analysis_type="Single-Cell Analysis")

        has_expression = False

        for p in profiles:
            if p.file_format.name in ("AnnData (h5ad)", "Loom", "HDF5"):
                has_expression = True
                result.checks_passed.append(f"Expression data found: {p.file_name}")
            elif p.file_format.name == "Matrix Market":
                has_expression = True
                result.checks_passed.append(f"Sparse matrix found: {p.file_name}")
                # Check for barcodes and features files
                parent = p.file_path.rsplit("/", 1)[0] if "/" in p.file_path else "."
                result.warnings.append(
                    "MTX format requires barcodes.tsv.gz and features.tsv.gz "
                    f"in the same directory ({parent})"
                )

        if not has_expression:
            result.checks_failed.append("No single-cell expression data found")
            result.missing_files.append(
                "Expression matrix (.h5ad, .h5, .mtx, or .loom)"
            )

        result.is_valid = has_expression
        result.ready_to_analyse = has_expression
        return result

    def _validate_alignment(self, profiles: list[FileProfile]) -> ValidationResult:
        """Validate files for read alignment."""
        result = ValidationResult(analysis_type="Read Alignment")

        fastq_files = []
        has_reference = False

        for p in profiles:
            if "FASTQ" in p.file_format.name:
                fastq_files.append(p)
                result.checks_passed.append(
                    f"Reads found: {p.file_name} ({p.stats.get('average_read_length', '?')} bp avg)"
                )
            if "FASTA" in p.file_format.name and p.size_bytes > 1_000_000:
                has_reference = True
                result.checks_passed.append(f"Reference genome: {p.file_name}")

        if not fastq_files:
            result.checks_failed.append("No FASTQ files found")
            result.missing_files.append("FASTQ sequencing reads")

        # Check paired-end pairing
        if len(fastq_files) >= 2:
            result.checks_passed.append(
                f"Multiple FASTQ files detected ({len(fastq_files)} files) — "
                "likely paired-end"
            )
        elif len(fastq_files) == 1:
            result.warnings.append(
                "Only one FASTQ file — if paired-end, provide the mate file"
            )

        if not has_reference:
            result.warnings.append(
                "No reference genome provided — "
                "you'll need to specify one (e.g., GRCh38) during alignment"
            )

        # Quality check
        for p in fastq_files:
            qual_flags = [f for f in p.quality_flags if f.level in ("warning", "error")]
            if qual_flags:
                result.warnings.extend(
                    f"{p.file_name}: {f.message}" for f in qual_flags
                )

        result.is_valid = len(fastq_files) > 0
        result.ready_to_analyse = len(fastq_files) > 0
        return result

    def _validate_generic(self, profiles: list[FileProfile]) -> ValidationResult:
        """Generic validation for unrecognised dataset types."""
        result = ValidationResult(analysis_type="General Analysis")

        for p in profiles:
            if p.overall_quality in ("good", "acceptable"):
                result.checks_passed.append(
                    f"{p.file_name}: {p.file_format.name} ({p.size_human})"
                )
            else:
                result.checks_failed.append(
                    f"{p.file_name}: quality is {p.overall_quality}"
                )

        result.is_valid = any(
            p.overall_quality in ("good", "acceptable", "unknown")
            for p in profiles
        )
        result.ready_to_analyse = result.is_valid
        return result
