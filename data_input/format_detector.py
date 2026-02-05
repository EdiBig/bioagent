"""
Bioinformatics file format detection.

Identifies file formats using a combination of:
1. File extension mapping
2. Magic bytes / file signatures
3. Content pattern matching (header inspection)

Supports 30+ bioinformatics and general scientific file formats.
"""

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Optional
import gzip
import io


class FormatCategory(str, Enum):
    """High-level categories of bioinformatics file formats."""
    SEQUENCE = "sequence"           # FASTQ, FASTA, BAM, SAM, CRAM
    VARIANT = "variant"             # VCF, BCF, BED, MAF
    EXPRESSION = "expression"       # Count matrices, h5ad, MTX, loom
    ANNOTATION = "annotation"       # GFF, GTF, GFF3, BED (annotation)
    ALIGNMENT = "alignment"         # BAM, SAM, CRAM, PAF
    STRUCTURE = "structure"         # PDB, mmCIF, PQR
    TABULAR = "tabular"             # CSV, TSV, Excel
    GENOMIC_RANGES = "genomic_ranges"  # BED, BigBed, BigWig, bedGraph
    PHYLOGENETIC = "phylogenetic"   # Newick, Nexus, PhyloXML
    IMAGE = "image"                 # PNG, TIFF, SVG (microscopy, plots)
    DOCUMENT = "document"           # PDF, HTML, Markdown
    ARCHIVE = "archive"             # tar, zip, gz
    OTHER = "other"


@dataclass
class FileFormat:
    """Detected file format with metadata."""
    name: str                       # e.g., "FASTQ", "VCF", "CSV"
    category: FormatCategory
    extension: str                  # Primary extension
    mime_type: str = ""
    description: str = ""
    is_binary: bool = False
    is_indexed: bool = False        # BAM with .bai, VCF with .tbi
    index_extensions: list[str] = field(default_factory=list)
    typical_tools: list[str] = field(default_factory=list)
    confidence: float = 1.0         # 0.0 to 1.0 detection confidence

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "category": self.category.value,
            "extension": self.extension,
            "description": self.description,
            "is_binary": self.is_binary,
            "typical_tools": self.typical_tools,
            "confidence": self.confidence,
        }


# ── Format Registry ─────────────────────────────────────────────────

FORMATS: dict[str, FileFormat] = {
    # ── Sequence formats ─────────────────────────────────────────
    "fastq": FileFormat(
        name="FASTQ",
        category=FormatCategory.SEQUENCE,
        extension=".fastq",
        description="Sequencing reads with quality scores",
        typical_tools=["FastQC", "fastp", "trimmomatic", "cutadapt", "STAR", "BWA"],
    ),
    "fastq.gz": FileFormat(
        name="FASTQ (gzipped)",
        category=FormatCategory.SEQUENCE,
        extension=".fastq.gz",
        description="Compressed sequencing reads with quality scores",
        is_binary=True,
        typical_tools=["FastQC", "fastp", "STAR", "BWA", "minimap2"],
    ),
    "fasta": FileFormat(
        name="FASTA",
        category=FormatCategory.SEQUENCE,
        extension=".fasta",
        description="Nucleotide or protein sequences",
        typical_tools=["BLAST", "MAFFT", "MUSCLE", "samtools faidx"],
    ),
    "fasta.gz": FileFormat(
        name="FASTA (gzipped)",
        category=FormatCategory.SEQUENCE,
        extension=".fasta.gz",
        is_binary=True,
        description="Compressed sequences",
        typical_tools=["samtools", "seqkit"],
    ),

    # ── Alignment formats ────────────────────────────────────────
    "bam": FileFormat(
        name="BAM",
        category=FormatCategory.ALIGNMENT,
        extension=".bam",
        description="Binary alignment map — aligned sequencing reads",
        is_binary=True,
        index_extensions=[".bai", ".bam.bai"],
        typical_tools=["samtools", "picard", "IGV", "deepTools", "featureCounts"],
    ),
    "sam": FileFormat(
        name="SAM",
        category=FormatCategory.ALIGNMENT,
        extension=".sam",
        description="Sequence alignment map (text format)",
        typical_tools=["samtools", "picard"],
    ),
    "cram": FileFormat(
        name="CRAM",
        category=FormatCategory.ALIGNMENT,
        extension=".cram",
        description="Compressed reference-based alignment",
        is_binary=True,
        index_extensions=[".crai"],
        typical_tools=["samtools", "cramtools"],
    ),

    # ── Variant formats ──────────────────────────────────────────
    "vcf": FileFormat(
        name="VCF",
        category=FormatCategory.VARIANT,
        extension=".vcf",
        description="Variant call format — SNVs, indels, structural variants",
        typical_tools=["bcftools", "GATK", "VEP", "SnpEff", "SnpSift", "plink"],
    ),
    "vcf.gz": FileFormat(
        name="VCF (bgzipped)",
        category=FormatCategory.VARIANT,
        extension=".vcf.gz",
        description="Compressed variant calls (bgzip + tabix indexed)",
        is_binary=True,
        index_extensions=[".tbi", ".csi"],
        typical_tools=["bcftools", "tabix", "GATK", "VEP"],
    ),
    "bcf": FileFormat(
        name="BCF",
        category=FormatCategory.VARIANT,
        extension=".bcf",
        description="Binary variant call format",
        is_binary=True,
        index_extensions=[".csi"],
        typical_tools=["bcftools"],
    ),
    "maf": FileFormat(
        name="MAF",
        category=FormatCategory.VARIANT,
        extension=".maf",
        description="Mutation Annotation Format (somatic variants)",
        typical_tools=["maftools", "Oncotator"],
    ),

    # ── Expression / quantification formats ──────────────────────
    "h5ad": FileFormat(
        name="AnnData (h5ad)",
        category=FormatCategory.EXPRESSION,
        extension=".h5ad",
        description="Annotated data matrix for single-cell analysis",
        is_binary=True,
        typical_tools=["scanpy", "anndata", "Seurat (via SeuratDisk)"],
    ),
    "h5": FileFormat(
        name="HDF5",
        category=FormatCategory.EXPRESSION,
        extension=".h5",
        description="Hierarchical data format (10x Genomics, etc.)",
        is_binary=True,
        typical_tools=["scanpy", "CellRanger", "h5py"],
    ),
    "mtx": FileFormat(
        name="Matrix Market",
        category=FormatCategory.EXPRESSION,
        extension=".mtx",
        description="Sparse matrix format (10x Genomics)",
        typical_tools=["scanpy", "Seurat", "scipy"],
    ),
    "loom": FileFormat(
        name="Loom",
        category=FormatCategory.EXPRESSION,
        extension=".loom",
        description="Large omics data matrix format",
        is_binary=True,
        typical_tools=["loompy", "scanpy", "velocyto"],
    ),

    # ── Annotation formats ───────────────────────────────────────
    "gff3": FileFormat(
        name="GFF3",
        category=FormatCategory.ANNOTATION,
        extension=".gff3",
        description="Generic feature format version 3",
        typical_tools=["bedtools", "AGAT", "gffread"],
    ),
    "gff": FileFormat(
        name="GFF",
        category=FormatCategory.ANNOTATION,
        extension=".gff",
        description="Generic feature format",
        typical_tools=["bedtools", "AGAT"],
    ),
    "gtf": FileFormat(
        name="GTF",
        category=FormatCategory.ANNOTATION,
        extension=".gtf",
        description="Gene transfer format (Ensembl/GENCODE annotations)",
        typical_tools=["featureCounts", "HTSeq", "StringTie", "STAR"],
    ),

    # ── Genomic range formats ────────────────────────────────────
    "bed": FileFormat(
        name="BED",
        category=FormatCategory.GENOMIC_RANGES,
        extension=".bed",
        description="Browser extensible data — genomic intervals",
        typical_tools=["bedtools", "deepTools", "HOMER"],
    ),
    "bigwig": FileFormat(
        name="BigWig",
        category=FormatCategory.GENOMIC_RANGES,
        extension=".bw",
        description="Binary indexed signal track",
        is_binary=True,
        typical_tools=["deepTools", "IGV", "pyBigWig"],
    ),
    "bedgraph": FileFormat(
        name="BedGraph",
        category=FormatCategory.GENOMIC_RANGES,
        extension=".bedgraph",
        description="Genomic signal track (text)",
        typical_tools=["bedtools", "UCSC tools"],
    ),

    # ── Structure formats ────────────────────────────────────────
    "pdb": FileFormat(
        name="PDB",
        category=FormatCategory.STRUCTURE,
        extension=".pdb",
        description="Protein Data Bank 3D structure",
        typical_tools=["PyMOL", "ChimeraX", "Mol*", "Biopython"],
    ),
    "cif": FileFormat(
        name="mmCIF",
        category=FormatCategory.STRUCTURE,
        extension=".cif",
        description="Macromolecular Crystallographic Information File",
        typical_tools=["PyMOL", "ChimeraX", "Mol*"],
    ),

    # ── Phylogenetic formats ─────────────────────────────────────
    "newick": FileFormat(
        name="Newick",
        category=FormatCategory.PHYLOGENETIC,
        extension=".nwk",
        description="Phylogenetic tree format",
        typical_tools=["FigTree", "iTOL", "ete3", "ggtree"],
    ),
    "nexus": FileFormat(
        name="Nexus",
        category=FormatCategory.PHYLOGENETIC,
        extension=".nex",
        description="NEXUS phylogenetic data format",
        typical_tools=["MrBayes", "BEAST", "FigTree"],
    ),

    # ── Tabular / general formats ────────────────────────────────
    "csv": FileFormat(
        name="CSV",
        category=FormatCategory.TABULAR,
        extension=".csv",
        description="Comma-separated values",
        typical_tools=["pandas", "R (readr)", "Excel"],
    ),
    "tsv": FileFormat(
        name="TSV",
        category=FormatCategory.TABULAR,
        extension=".tsv",
        description="Tab-separated values",
        typical_tools=["pandas", "R (readr)", "awk"],
    ),
    "xlsx": FileFormat(
        name="Excel",
        category=FormatCategory.TABULAR,
        extension=".xlsx",
        description="Microsoft Excel spreadsheet",
        is_binary=True,
        typical_tools=["pandas (openpyxl)", "R (readxl)"],
    ),
    "xls": FileFormat(
        name="Excel (legacy)",
        category=FormatCategory.TABULAR,
        extension=".xls",
        description="Legacy Excel format",
        is_binary=True,
        typical_tools=["pandas (xlrd)", "R (readxl)"],
    ),
    "parquet": FileFormat(
        name="Parquet",
        category=FormatCategory.TABULAR,
        extension=".parquet",
        description="Columnar storage format",
        is_binary=True,
        typical_tools=["pandas", "polars", "pyarrow"],
    ),

    # ── Document / report formats ────────────────────────────────
    "pdf": FileFormat(
        name="PDF",
        category=FormatCategory.DOCUMENT,
        extension=".pdf",
        description="PDF document (papers, reports)",
        is_binary=True,
        typical_tools=["pdfplumber", "PyPDF2", "tabula-py"],
    ),

    # ── Image formats ────────────────────────────────────────────
    "png": FileFormat(
        name="PNG",
        category=FormatCategory.IMAGE,
        extension=".png",
        description="PNG image",
        is_binary=True,
    ),
    "tiff": FileFormat(
        name="TIFF",
        category=FormatCategory.IMAGE,
        extension=".tiff",
        description="TIFF image (microscopy, histology)",
        is_binary=True,
        typical_tools=["scikit-image", "Pillow", "OpenSlide"],
    ),
    "svg": FileFormat(
        name="SVG",
        category=FormatCategory.IMAGE,
        extension=".svg",
        description="Scalable vector graphics",
    ),
}

# Extension → format key mapping (handles aliases)
EXTENSION_MAP: dict[str, str] = {
    ".fastq": "fastq", ".fq": "fastq",
    ".fastq.gz": "fastq.gz", ".fq.gz": "fastq.gz",
    ".fasta": "fasta", ".fa": "fasta", ".fna": "fasta", ".faa": "fasta",
    ".fasta.gz": "fasta.gz", ".fa.gz": "fasta.gz",
    ".bam": "bam",
    ".sam": "sam",
    ".cram": "cram",
    ".vcf": "vcf",
    ".vcf.gz": "vcf.gz",
    ".bcf": "bcf",
    ".maf": "maf",
    ".h5ad": "h5ad",
    ".h5": "h5", ".hdf5": "h5",
    ".mtx": "mtx", ".mtx.gz": "mtx",
    ".loom": "loom",
    ".gff3": "gff3",
    ".gff": "gff",
    ".gtf": "gtf",
    ".bed": "bed",
    ".bw": "bigwig", ".bigwig": "bigwig",
    ".bedgraph": "bedgraph", ".bg": "bedgraph",
    ".pdb": "pdb", ".ent": "pdb",
    ".cif": "cif", ".mmcif": "cif",
    ".nwk": "newick", ".newick": "newick", ".tree": "newick",
    ".nex": "nexus", ".nexus": "nexus",
    ".csv": "csv",
    ".tsv": "tsv", ".tab": "tsv", ".txt": "tsv",  # .txt as fallback
    ".xlsx": "xlsx",
    ".xls": "xls",
    ".parquet": "parquet",
    ".pdf": "pdf",
    ".png": "png",
    ".tiff": "tiff", ".tif": "tiff",
    ".svg": "svg",
}


class FormatDetector:
    """
    Detects bioinformatics file formats using extension + content inspection.
    """

    def detect(self, filepath: Path) -> FileFormat:
        """
        Detect the format of a file.

        Strategy:
        1. Try extension-based detection (fast)
        2. If ambiguous, inspect file content (magic bytes + header patterns)
        3. Return best match with confidence score
        """
        # Step 1: Extension-based detection
        ext_format = self._detect_by_extension(filepath)

        # Step 2: Content-based validation/detection
        content_format = self._detect_by_content(filepath)

        # Step 3: Reconcile
        if ext_format and content_format:
            if ext_format.name == content_format.name:
                ext_format.confidence = 1.0
                return ext_format
            else:
                # Content detection overrides extension when they disagree
                content_format.confidence = 0.9
                return content_format
        elif content_format:
            content_format.confidence = 0.8
            return content_format
        elif ext_format:
            ext_format.confidence = 0.7
            return ext_format
        else:
            return FileFormat(
                name="Unknown",
                category=FormatCategory.OTHER,
                extension=filepath.suffix,
                description="Unrecognized file format",
                confidence=0.0,
            )

    def _detect_by_extension(self, filepath: Path) -> Optional[FileFormat]:
        """Detect format from file extension."""
        name = filepath.name.lower()

        # Check double extensions first
        for ext, fmt_key in sorted(
            EXTENSION_MAP.items(), key=lambda x: len(x[0]), reverse=True
        ):
            if name.endswith(ext):
                fmt = FORMATS.get(fmt_key)
                if fmt:
                    return FileFormat(**{
                        k: v for k, v in fmt.__dict__.items()
                    })
                break

        return None

    def _detect_by_content(self, filepath: Path) -> Optional[FileFormat]:
        """Detect format by inspecting file content."""
        try:
            # Read first bytes for magic number detection
            with open(filepath, "rb") as f:
                header_bytes = f.read(1024)
        except Exception:
            return None

        if not header_bytes:
            return None

        # ── Magic bytes detection ────────────────────────────────
        # BAM
        if header_bytes[:4] == b"\x42\x41\x4d\x01":
            return FORMATS["bam"]

        # CRAM
        if header_bytes[:4] == b"CRAM":
            return FORMATS["cram"]

        # Gzip — need to peek inside
        if header_bytes[:2] == b"\x1f\x8b":
            return self._detect_gzipped_content(filepath)

        # HDF5 (h5ad, h5, loom)
        if header_bytes[:8] == b"\x89HDF\r\n\x1a\n":
            return self._detect_hdf5_subtype(filepath)

        # PDF
        if header_bytes[:5] == b"%PDF-":
            return FORMATS["pdf"]

        # PNG
        if header_bytes[:8] == b"\x89PNG\r\n\x1a\n":
            return FORMATS["png"]

        # TIFF
        if header_bytes[:2] in (b"II", b"MM"):
            return FORMATS["tiff"]

        # ZIP (xlsx is a zip file)
        if header_bytes[:4] == b"PK\x03\x04":
            return FORMATS["xlsx"]  # Could be any zip, but xlsx is common

        # Parquet
        if header_bytes[:4] == b"PAR1":
            return FORMATS["parquet"]

        # ── Text-based detection ─────────────────────────────────
        try:
            text = header_bytes.decode("utf-8", errors="replace")
            lines = text.split("\n")[:20]
        except Exception:
            return None

        return self._detect_text_format(lines)

    def _detect_text_format(self, lines: list[str]) -> Optional[FileFormat]:
        """Detect text-based formats from header lines."""
        if not lines:
            return None

        first_line = lines[0].strip()

        # FASTQ: starts with @
        if first_line.startswith("@") and len(lines) >= 4:
            if lines[2].strip().startswith("+"):
                return FORMATS["fastq"]

        # FASTA: starts with >
        if first_line.startswith(">"):
            return FORMATS["fasta"]

        # VCF: starts with ##fileformat=VCF
        if first_line.startswith("##fileformat=VCF"):
            return FORMATS["vcf"]

        # SAM: starts with @HD, @SQ, @RG, @PG, or has 11+ tab-delimited fields
        if first_line.startswith(("@HD", "@SQ", "@RG", "@PG", "@CO")):
            return FORMATS["sam"]

        # GFF3
        if first_line.startswith("##gff-version 3") or first_line.startswith("##gff-version\t3"):
            return FORMATS["gff3"]

        # GTF: look for gene_id attribute
        for line in lines[:10]:
            if not line.startswith("#") and line.strip():
                if 'gene_id "' in line or "gene_id '" in line:
                    return FORMATS["gtf"]
                break

        # BED: tab-delimited with chr/numeric start/end
        non_comment = [l for l in lines if l.strip() and not l.startswith(("#", "track", "browser"))]
        if non_comment:
            fields = non_comment[0].split("\t")
            if len(fields) >= 3:
                try:
                    int(fields[1])
                    int(fields[2])
                    if fields[0].startswith("chr") or fields[0].isdigit():
                        return FORMATS["bed"]
                except ValueError:
                    pass

        # MAF: has Hugo_Symbol or Variant_Classification header
        if "Hugo_Symbol" in first_line or "Variant_Classification" in first_line:
            return FORMATS["maf"]

        # Newick: starts with ( and ends with ;
        stripped = first_line.strip()
        if stripped.startswith("(") and stripped.endswith(";"):
            return FORMATS["newick"]

        # NEXUS: starts with #NEXUS
        if first_line.upper().startswith("#NEXUS"):
            return FORMATS["nexus"]

        # PDB
        if first_line.startswith(("HEADER", "ATOM  ", "HETATM", "REMARK")):
            return FORMATS["pdb"]

        # CSV vs TSV detection
        comma_count = sum(line.count(",") for line in lines[:5])
        tab_count = sum(line.count("\t") for line in lines[:5])
        if tab_count > comma_count and tab_count > 0:
            return FORMATS["tsv"]
        elif comma_count > 0:
            return FORMATS["csv"]

        return None

    def _detect_gzipped_content(self, filepath: Path) -> Optional[FileFormat]:
        """Peek inside a gzipped file to detect the inner format."""
        try:
            with gzip.open(filepath, "rt", errors="replace") as f:
                lines = []
                for i, line in enumerate(f):
                    if i >= 10:
                        break
                    lines.append(line)
        except Exception:
            return None

        if not lines:
            return None

        first_line = lines[0].strip()

        # FASTQ.gz
        if first_line.startswith("@") and len(lines) >= 4 and lines[2].strip().startswith("+"):
            return FORMATS["fastq.gz"]

        # FASTA.gz
        if first_line.startswith(">"):
            return FORMATS["fasta.gz"]

        # VCF.gz
        if first_line.startswith("##fileformat=VCF"):
            return FORMATS["vcf.gz"]

        return None

    def _detect_hdf5_subtype(self, filepath: Path) -> Optional[FileFormat]:
        """Detect HDF5 subtypes (h5ad, loom, 10x h5)."""
        name = filepath.name.lower()
        if name.endswith(".h5ad"):
            return FORMATS["h5ad"]
        elif name.endswith(".loom"):
            return FORMATS["loom"]
        else:
            return FORMATS["h5"]
