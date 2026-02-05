"""
BioAgent File Ingestion System

Accepts data from any source, detects format, profiles content,
assesses quality, and suggests appropriate analyses.

Supports 30+ bioinformatics file formats including:
FASTQ, FASTA, BAM, SAM, CRAM, VCF, BCF, BED, GFF, GTF,
h5ad, MTX, Loom, PDB, mmCIF, CSV, TSV, Excel, Parquet,
BigWig, BedGraph, MAF, Newick, Nexus, and more.
"""

from data_input.data_source import DataSource, FetchedFile, FileFetcher, SourceType
from data_input.format_detector import FormatDetector, FileFormat, FormatCategory
from data_input.profilers import FileProfile, QualityFlag, AnalysisSuggestion
from data_input.file_ingestor import FileIngestor, IngestResult
from data_input.dataset_validator import DatasetValidator, ValidationResult
from data_input.integration import IngestHandler
from data_input.ingest_tool_definitions import get_ingest_tools, get_ingest_tool_names

__version__ = "1.0.0"

__all__ = [
    # Main classes
    "FileIngestor",
    "IngestResult",
    "IngestHandler",
    # Data source
    "DataSource",
    "FetchedFile",
    "FileFetcher",
    "SourceType",
    # Format detection
    "FormatDetector",
    "FileFormat",
    "FormatCategory",
    # Profiling
    "FileProfile",
    "QualityFlag",
    "AnalysisSuggestion",
    # Validation
    "DatasetValidator",
    "ValidationResult",
    # Tool definitions
    "get_ingest_tools",
    "get_ingest_tool_names",
]
