"""
Tool definitions for BioAgent file ingestion.

These tool schemas are added to the agent's tool list so Claude
can ingest, assess, and reason about user-provided data files.
"""

INGEST_TOOLS = [
    {
        "name": "ingest_file",
        "description": (
            "Ingest a data file from any source (local path, URL, S3, GCS, or raw pasted data). "
            "Automatically detects the file format (FASTQ, VCF, BAM, CSV, h5ad, BED, FASTA, etc.), "
            "generates a comprehensive profile with statistics, quality assessment, and suggested analyses. "
            "Use this as the FIRST step whenever a user provides data files. "
            "The profile includes: file format, dimensions, quality flags, data preview, "
            "column information (for tabular data), and recommended next steps. "
            "\n\nSupported sources:\n"
            "- Local path: /data/reads.fastq.gz\n"
            "- URL: https://ftp.example.com/sample.vcf\n"
            "- S3: s3://bucket/path/to/file.csv\n"
            "- GCS: gs://bucket/path/to/file.h5ad\n"
            "- Raw data: Paste a FASTA sequence, gene list, or other text data directly"
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "source": {
                    "type": "string",
                    "description": (
                        "File path, URL, S3/GCS URI, or raw data content. "
                        "Examples: '/data/reads_R1.fastq.gz', "
                        "'https://ftp.ncbi.nlm.nih.gov/genomes/all/GCF/.../GCF_000001405.40_GRCh38.p14_genomic.fna.gz', "
                        "'s3://my-bucket/experiment/counts.csv', "
                        "'>seq1\\nACGTACGTACGT' (raw FASTA)"
                    ),
                },
                "label": {
                    "type": "string",
                    "description": (
                        "Optional human-readable label for this file "
                        "(e.g., 'patient_tumor_rnaseq', 'control_sample'). "
                        "Used for referencing the file later."
                    ),
                    "default": "",
                },
            },
            "required": ["source"],
        },
    },
    {
        "name": "ingest_batch",
        "description": (
            "Ingest multiple data files at once and generate a dataset-level summary. "
            "Automatically detects the overall dataset type (e.g., 'RNA-seq paired reads', "
            "'variant data', 'single-cell data') and recommends an end-to-end workflow. "
            "\n\nUse this when the user provides multiple related files:\n"
            "- Paired-end FASTQ files (R1 + R2)\n"
            "- A count matrix + metadata file\n"
            "- Multiple VCF files for comparison\n"
            "- A complete project directory"
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "sources": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": (
                        "List of file paths, URLs, or S3/GCS URIs to ingest. "
                        "Example: ['/data/sample_R1.fastq.gz', '/data/sample_R2.fastq.gz', '/data/metadata.csv']"
                    ),
                },
                "labels": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Optional labels for each file (same order as sources)",
                    "default": [],
                },
            },
            "required": ["sources"],
        },
    },
    {
        "name": "ingest_directory",
        "description": (
            "Scan a directory and ingest all matching files. "
            "Useful when the user points to a project folder or data directory. "
            "Supports glob patterns to filter specific file types. "
            "\n\nExamples:\n"
            "- Ingest all FASTQ files: pattern='*.fastq.gz'\n"
            "- Ingest all VCFs: pattern='*.vcf*'\n"
            "- Ingest everything: pattern='*'"
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "directory": {
                    "type": "string",
                    "description": "Path to the directory to scan",
                },
                "pattern": {
                    "type": "string",
                    "description": "Glob pattern to match files (default: '*' for all files)",
                    "default": "*",
                },
                "recursive": {
                    "type": "boolean",
                    "description": "Search subdirectories recursively (default: false)",
                    "default": False,
                },
            },
            "required": ["directory"],
        },
    },
    {
        "name": "list_ingested_files",
        "description": (
            "List all files that have been ingested in this session. "
            "Shows file name, format, size, quality status, and workspace path. "
            "Use this to check what data is available for analysis."
        ),
        "input_schema": {
            "type": "object",
            "properties": {},
            "required": [],
        },
    },
    {
        "name": "get_file_profile",
        "description": (
            "Get the detailed profile for a previously ingested file. "
            "Returns comprehensive statistics, quality flags, column information, "
            "and analysis suggestions. Use this to re-examine a file's properties."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "label_or_name": {
                    "type": "string",
                    "description": "The label or filename of the previously ingested file",
                },
            },
            "required": ["label_or_name"],
        },
    },
    {
        "name": "validate_dataset",
        "description": (
            "Validate that a set of ingested files form a coherent dataset "
            "suitable for a specific analysis. Checks for: matching samples "
            "across files, compatible formats, required companion files, "
            "and potential issues. "
            "\n\nValidation types:\n"
            "- 'rnaseq': Checks for count matrix + metadata + optional GTF\n"
            "- 'variant': Checks for VCF + reference + optional annotation\n"
            "- 'singlecell': Checks for expression matrix (h5ad/mtx) + metadata\n"
            "- 'alignment': Checks for FASTQ pairs, reference genome availability\n"
            "- 'auto': Automatically detect and validate"
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "file_labels": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Labels or filenames of ingested files to validate together",
                },
                "analysis_type": {
                    "type": "string",
                    "enum": ["rnaseq", "variant", "singlecell", "alignment", "auto"],
                    "description": "Type of analysis to validate for (default: 'auto')",
                    "default": "auto",
                },
            },
            "required": ["file_labels"],
        },
    },
]


def get_ingest_tools() -> list[dict]:
    """Return all file ingestion tool definitions."""
    return INGEST_TOOLS


def get_ingest_tool_names() -> list[str]:
    """Return names of all ingestion tools."""
    return [t["name"] for t in INGEST_TOOLS]
