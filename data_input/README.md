# BioAgent File Ingestion System

A data intake layer for BioAgent that accepts files from any source, automatically detects bioinformatics formats, generates rich profiles with quality assessment, and suggests appropriate analyses.

## What It Does

When a user provides data files, the ingestion system:

```
User provides file(s)
       ↓
┌──────────────────────┐
│  1. SOURCE DETECTION │  Local path / URL / S3 / GCS / pasted data
└──────────┬───────────┘
           ↓
┌──────────────────────┐
│  2. FETCH TO WORKSPACE│  Copy/download into workspace
└──────────┬───────────┘
           ↓
┌──────────────────────┐
│  3. FORMAT DETECTION │  Extension + magic bytes + header inspection
└──────────┬───────────┘
           ↓
┌──────────────────────┐
│  4. PROFILING        │  Format-specific stats, quality metrics, preview
└──────────┬───────────┘
           ↓
┌──────────────────────┐
│  5. QUALITY FLAGS    │  Warnings and errors the agent should address
└──────────┬───────────┘
           ↓
┌──────────────────────┐
│  6. ANALYSIS SUGGEST │  What to do next, with example queries
└──────────┬───────────┘
           ↓
┌──────────────────────┐
│  7. DATASET VALIDATE │  Multi-file coherence check
└──────────────────────┘
```

The agent receives a structured profile it can reason about — format, dimensions, quality flags, column types, and concrete next-step suggestions with example queries.

## Supported Formats (34 formats, 52 extension mappings)

| Category | Formats |
|----------|---------|
| **Sequence** | FASTQ, FASTQ.gz, FASTA, FASTA.gz |
| **Alignment** | BAM, SAM, CRAM |
| **Variant** | VCF, VCF.gz, BCF, MAF |
| **Expression** | h5ad (AnnData), HDF5, MTX, Loom |
| **Annotation** | GTF, GFF3, GFF |
| **Genomic Ranges** | BED, BigWig, BedGraph |
| **Structure** | PDB, mmCIF |
| **Phylogenetic** | Newick, Nexus |
| **Tabular** | CSV, TSV, Excel (.xlsx/.xls), Parquet |
| **Other** | PDF, PNG, TIFF, SVG |

## Data Sources

```python
# Local file
profile = ingestor.ingest("/data/experiment/reads_R1.fastq.gz")

# HTTP/FTP URL
profile = ingestor.ingest("https://ftp.ensembl.org/pub/release-110/gtf/homo_sapiens/Homo_sapiens.GRCh38.110.gtf.gz")

# S3 bucket
profile = ingestor.ingest("s3://my-lab-data/rnaseq/counts.csv")

# Google Cloud Storage
profile = ingestor.ingest("gs://genomics-bucket/variants.vcf.gz")

# Pasted data (FASTA sequence, gene list, etc.)
profile = ingestor.ingest(">BRCA1\nMVLSPADKTNVKAAWGKV...")

# Auto-detected from any string
source = DataSource.detect(user_input)  # figures out the type
```

## What the Agent Sees

When Claude uses the `ingest_file` tool, it receives a structured summary like:

```
## File Profile: counts.csv
- **Format**: CSV (tabular)
- **Size**: 959 B
- **Path**: /workspace/ingested/counts.csv

### Statistics
- columns: 8
- rows: 20
- dimensions: 20 rows × 8 columns

### Columns
- `gene_id` (string, 0 nulls)
- `gene_name` (string, 0 nulls)
- `tumor_1` (integer, 0 nulls)
- `tumor_2` (integer, 0 nulls)
- `normal_1` (integer, 0 nulls)
- `normal_2` (integer, 0 nulls)

### Preview
gene_id,gene_name,tumor_1,tumor_2,normal_1,normal_2
ENSG872246,TP53,962,254,2056,1878
ENSG131244,BRCA1,889,4517,4887,3506

### Overall Quality: good

### Suggested Analyses
- **Differential Expression Analysis** (suggested): Identify DEGs between conditions
  Try: "Run differential expression analysis on this count matrix."
- **Pathway Enrichment** (suggested): Identify enriched biological pathways
  Try: "Find enriched GO terms and KEGG pathways in the DEGs"
```

## Format-Specific Profiling

Each format gets a specialised profiler that extracts relevant metrics:

### FASTQ Profiler
- Read count, average/min/max length
- GC content percentage
- Mean quality score (Phred+33)
- Paired-end mate detection (R1→R2)
- Flags: low quality, unusual GC, variable lengths

### VCF Profiler
- Variant count, types (SNV/indel/MNV), chromosomes
- Sample names and count
- Filter summary (PASS rate)
- INFO fields available
- Index file detection (.tbi/.csi)

### Tabular Profiler (CSV/TSV/Excel)
- Row/column count, dimensions
- Per-column: name, inferred dtype, null count, min/max/mean
- Smart detection of biological data patterns:
  - Count matrix (gene IDs + numeric columns → suggest DE analysis)
  - DE results (log2FC + padj → suggest volcano plot + enrichment)
  - Variant table (chr/pos/ref/alt → suggest annotation)
  - Sample metadata (sample_id + condition → suggest design review)

### BAM Profiler
- Total/mapped/duplicate reads (via samtools flagstat)
- Mapping rate with quality flags
- Reads per chromosome (via samtools idxstats)
- Index file (.bai) detection

### FASTA Profiler
- Sequence count, total length, N50
- GC content, protein vs nucleotide detection
- Header preview

### BED Profiler
- Region count, chromosomes, total coverage
- Mean/min/max region length

## Dataset Validation

For multi-file analyses, the validator checks coherence:

```python
validator = DatasetValidator()
result = validator.validate(
    [counts_profile, metadata_profile],
    analysis_type="rnaseq"
)
# Returns: passed/failed checks, missing files, suggested fixes
```

**Validation types:**
- `rnaseq` — Checks for count matrix + metadata + optional GTF
- `variant` — Checks for VCF with variants + optional index
- `singlecell` — Checks for h5ad/MTX/Loom expression data
- `alignment` — Checks for FASTQ pairs + reference genome
- `auto` — Detects the most likely analysis type

## Agent Tool Definitions (6 tools)

| Tool | Description |
|------|-------------|
| `ingest_file` | Ingest a single file from any source |
| `ingest_batch` | Ingest multiple files with dataset-level summary |
| `ingest_directory` | Scan a directory with glob pattern matching |
| `list_ingested_files` | Show all ingested files with status |
| `get_file_profile` | Retrieve detailed profile for a file |
| `validate_dataset` | Check multi-file dataset readiness |

## Integration with BioAgent

Three changes to `agent.py`:

```python
# 1. Import
from ingest_tool_definitions import get_ingest_tools
from integration import IngestHandler

# 2. In __init__()
self.ingest_handler = IngestHandler(workspace_dir=self.config.workspace_dir)

# 3. In _call_claude() — add tools
"tools": get_tools() + get_ingest_tools()

# 4. In _execute_tool() — add routing
elif name in self.ingest_handler.handled_tools:
    return self.ingest_handler.handle(name, input_data)
```

## Module Structure

```
file_ingestion/
├── __init__.py                 # Clean exports
├── data_source.py              # Source detection + fetching (local/URL/S3/GCS/raw)
├── format_detector.py          # 34 formats, extension + magic byte + header detection
├── profilers.py                # Format-specific profilers (FASTQ/VCF/BAM/CSV/BED/FASTA)
├── file_ingestor.py            # Main orchestrator (ingest → detect → profile → register)
├── dataset_validator.py        # Multi-file coherence validation
├── ingest_tool_definitions.py  # 6 tool schemas for Claude API
├── integration.py              # Agent handler + wiring guide
└── README.md                   # This file
```

## Example User Workflows

### "Here's my RNA-seq data"
```
User: I have counts.csv and metadata.csv in /data/experiment/

Agent calls: ingest_batch(["/data/experiment/counts.csv", "/data/experiment/metadata.csv"])

Agent sees:
  - counts.csv: 20,000 genes × 12 samples, expression count matrix
  - metadata.csv: 12 rows with sample_id, condition, batch columns
  - Dataset type: Tabular / expression data
  - Suggested: DE analysis → Pathway enrichment

Agent calls: validate_dataset(["counts.csv", "metadata.csv"], "rnaseq")

Agent sees:
  ✅ Expression matrix found (20,000 genes × 12 samples)
  ✅ Sample metadata found
  ⚠️ No gene annotation (GTF) — will use gene IDs for enrichment

Agent proceeds with DESeq2 analysis...
```

### "Check this VCF"
```
User: Assess the quality of variants.vcf.gz

Agent calls: ingest_file("variants.vcf.gz")

Agent sees:
  - Format: VCF (bgzipped)
  - 1,234,567 variants, 3 samples
  - 85% PASS rate
  - SNV: 1.1M, Insertion: 80K, Deletion: 55K
  - ⚠️ Missing tabix index
  - Suggest: variant stats → annotation → pathogenicity → gnomAD

Agent: "Your VCF contains 1.23M variants across 3 samples with an 85% PASS rate.
        I'd recommend starting with bcftools stats for detailed QC, then annotation
        with VEP. Note: the file needs a tabix index for efficient access."
```

### "I pasted a protein sequence"
```
User: >BRCA1_variant
MVLSPADKTNVKAAWGKVGAHAGEYGAEALERMFLSFPTTKTYFPHFDLSH...

Agent calls: ingest_file(raw_fasta)

Agent sees:
  - Format: FASTA (sequence)
  - 1 protein sequence, 152 aa
  - Suggest: BLAST search, structure prediction

Agent: "This is a 152-residue protein sequence. I can search it against
        UniProt/NCBI, predict its structure via AlphaFold/ESMFold, or
        check for known domains via InterPro."
```
