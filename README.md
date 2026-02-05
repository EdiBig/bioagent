# BioAgent

An AI-powered bioinformatics assistant that combines Claude's reasoning capabilities with computational tools for expert-level genomics, transcriptomics, proteomics, and biological data analysis.

## Table of Contents

- [Overview](#overview)
- [Features](#features)
- [Quick Start](#quick-start)
- [Architecture](#architecture)
- [Database Integrations](#database-integrations)
- [ML/AI Capabilities](#mlai-capabilities)
- [Workflow Engines](#workflow-engines)
- [Cloud & HPC Integration](#cloud--hpc-integration)
- [Visualization & Reporting](#visualization--reporting)
- [Memory System](#memory-system)
- [Multi-Agent System](#multi-agent-system)
- [Configuration](#configuration)
- [API Reference](#api-reference)
- [Examples](#examples)
- [Extending BioAgent](#extending-bioagent)
- [Troubleshooting](#troubleshooting)

---

## Overview

BioAgent is an **agentic system** — not just a chatbot. When you give it a task, it:

1. **Reasons** about the biological question and experimental design
2. **Plans** an analysis workflow with appropriate methods
3. **Executes** code (Python, R, Bash) to run bioinformatics tools
4. **Queries** 11+ biological databases for annotation and context
5. **Predicts** using ML/AI models (pathogenicity, structure, drug response)
6. **Searches** the web for documentation, tutorials, and latest research
7. **Runs** workflow engines (Nextflow, Snakemake, WDL) for reproducible pipelines
8. **Scales** to cloud/HPC backends (AWS, GCP, Azure, SLURM)
9. **Visualizes** results with publication-quality figures
10. **Remembers** context across sessions with intelligent memory
11. **Iterates** — checking outputs, debugging errors, refining results
12. **Saves** all results automatically for reproducibility

All through natural language conversation.

---

## Features

### Core Capabilities

| Category | Features |
|----------|----------|
| **Code Execution** | Python, R, Bash with sandboxed execution |
| **Databases** | 11 biological databases (NCBI, Ensembl, UniProt, KEGG, STRING, PDB, AlphaFold, InterPro, Reactome, GO, gnomAD) |
| **ML/AI** | Variant pathogenicity, structure prediction, drug response, cell annotation, biomarker discovery |
| **Workflows** | Nextflow, Snakemake, WDL/Cromwell support |
| **Cloud/HPC** | AWS Batch, GCP Life Sciences, Azure Batch, SLURM |
| **Visualization** | Publication-quality figures (Nature, Cell, Science styles), interactive plots |
| **Reporting** | Jupyter notebooks, R Markdown, Streamlit/Dash dashboards |
| **Memory** | Semantic search, knowledge graphs, artifact storage, session summarization |
| **Multi-Agent** | Coordinator-Specialist architecture with 5 specialist agents |

### Tool Count by Category

| Category | Tools | Description |
|----------|-------|-------------|
| Code Execution | 3 | Python, R, Bash |
| Database Queries | 11 | All major bioinformatics databases |
| Workflow Management | 6 | Create, run, monitor workflows |
| File Operations | 3 | Read, write, list files |
| Memory System | 5 | Search, save, retrieve context |
| Visualization | 3 | Plots, reports, dashboards |
| Cloud/HPC | 6 | Submit, monitor, scale jobs |
| ML/AI | 5 | Predictive analytics |
| Web Search | 1 | Documentation and literature |
| **Total** | **43** | |

---

## Quick Start

### 1. Installation

```bash
# Clone the repository
git clone https://github.com/EdiBig/bioagent.git
cd bioagent

# Create virtual environment (recommended)
python -m venv venv
source venv/bin/activate  # Linux/Mac
# or: venv\Scripts\activate  # Windows

# Install dependencies
pip install -r requirements.txt

# Set your API key
export ANTHROPIC_API_KEY="sk-ant-your-key-here"
```

### 2. Basic Usage

```bash
# Interactive chat mode
python run.py

# Single query mode
python run.py --query "What genes are associated with BRCA1?"

# Complex analysis (uses more powerful model)
python run.py --complex "Design a complete RNA-seq pipeline for tumor vs normal comparison"
```

### 3. Example Queries

```bash
# Database queries
python run.py --query "Get protein info for TP53 from UniProt and find its interaction partners"

# ML predictions
python run.py --query "Predict the pathogenicity of variant 17-7577121-G-A"

# Structure prediction
python run.py --query "Get the AlphaFold structure for BRCA1 protein"

# Drug response
python run.py --query "Predict drug response for Erlotinib in lung cancer cell lines"

# Workflow creation
python run.py --query "Create a Nextflow pipeline for RNA-seq alignment with STAR"

# Cloud submission
python run.py --query "Submit a variant calling job to AWS Batch"
```

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              USER QUERY                                      │
└─────────────────────────────────┬───────────────────────────────────────────┘
                                  ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                         COORDINATOR AGENT                                    │
│                   (routes tasks, synthesizes results)                        │
└────────┬──────────┬──────────┬──────────┬──────────┬───────────────────────┘
         │          │          │          │          │
    ┌────┘     ┌────┘     ┌────┘     ┌────┘     ┌────┘
    ▼          ▼          ▼          ▼          ▼
┌────────┐┌────────┐┌────────┐┌────────┐┌────────┐
│Pipeline││Statist-││Literat-││   QC   ││ Domain │
│Engineer││ ician  ││  ure   ││Reviewer││ Expert │
│        ││        ││ Agent  ││        ││        │
│28 tools││18 tools││18 tools││5 tools ││18 tools│
└───┬────┘└───┬────┘└───┬────┘└───┬────┘└───┬────┘
    │         │         │         │         │
    └─────────┴─────────┴────┬────┴─────────┘
                             ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                              TOOL LAYER                                      │
├─────────┬─────────┬─────────┬─────────┬─────────┬─────────┬─────────────────┤
│  Code   │Database │   ML    │Workflow │ Cloud   │  Viz    │    Memory       │
│  Exec   │ Queries │   AI    │ Engines │  HPC    │Reporting│    System       │
├─────────┼─────────┼─────────┼─────────┼─────────┼─────────┼─────────────────┤
│Python   │NCBI     │Pathogen.│Nextflow │AWS Batch│Pub Figs │Vector Store     │
│R        │Ensembl  │Structure│Snakemake│GCP Life │Interact.│Knowledge Graph  │
│Bash     │UniProt  │Drug Resp│WDL      │Azure    │Notebooks│Artifact Store   │
│         │KEGG     │Cell Ann.│         │SLURM    │RMarkdown│Session Summary  │
│         │STRING   │Biomarker│         │         │Dashboard│                 │
│         │PDB      │         │         │         │         │                 │
│         │AlphaFold│         │         │         │         │                 │
│         │InterPro │         │         │         │         │                 │
│         │Reactome │         │         │         │         │                 │
│         │GO       │         │         │         │         │                 │
│         │gnomAD   │         │         │         │         │                 │
└─────────┴─────────┴─────────┴─────────┴─────────┴─────────┴─────────────────┘
```

---

## Database Integrations

BioAgent provides unified access to 11 major biological databases:

| Database | Description | Operations | Tool |
|----------|-------------|------------|------|
| **NCBI** | Genes, sequences, literature (PubMed, Gene, Nucleotide, Protein) | search, fetch, link | `query_ncbi` |
| **Ensembl** | Genomic annotations, variants, comparative genomics | lookup, sequence, xrefs, variants | `query_ensembl` |
| **UniProt** | Protein sequences, annotations, functional data | search, fetch, batch | `query_uniprot` |
| **KEGG** | Pathways, genes, compounds, diseases | get, find, link, list | `query_kegg` |
| **STRING** | Protein-protein interactions, networks | interactions, enrichment, network | `query_string` |
| **PDB** | 3D protein structures | fetch, search, ligands | `query_pdb` |
| **AlphaFold** | AI-predicted protein structures | prediction, pae | `query_alphafold` |
| **InterPro** | Protein domains and families | protein, entry, search | `query_interpro` |
| **Reactome** | Biological pathways and reactions | pathway, reaction, species | `query_reactome` |
| **Gene Ontology** | GO terms, gene annotations | term, annotation, enrichment | `query_go` |
| **gnomAD** | Population variant frequencies | variant, gene, region | `query_gnomad` |

### Example: Multi-Database Query

```python
from agent import BioAgent

agent = BioAgent()
result = agent.run("""
For gene TP53:
1. Get protein info from UniProt
2. Find all pathways in KEGG and Reactome
3. Get interaction partners from STRING (score > 900)
4. Check gnomAD for common variants
5. Get the AlphaFold structure
""")
```

---

## ML/AI Capabilities

BioAgent includes 5 ML/AI modules for predictive bioinformatics:

### 1. Variant Pathogenicity Prediction

Predicts variant pathogenicity using multiple scoring systems:

| Score | Description | Range | Interpretation |
|-------|-------------|-------|----------------|
| **CADD** | Combined Annotation Dependent Depletion | PHRED 0-99 | >20 damaging, >30 highly damaging |
| **REVEL** | Rare Exome Variant Ensemble Learner | 0-1 | >0.5 likely pathogenic |
| **AlphaMissense** | DeepMind's missense predictor | 0-1 | >0.564 likely pathogenic |

```python
from ml import predict_variant_pathogenicity

results = predict_variant_pathogenicity(
    variants=["17-7577121-G-A", "BRCA1:p.Cys61Gly"],
    genome_build="GRCh38"
)
# Returns: CADD, REVEL, AlphaMissense scores with interpretations
```

### 2. Protein Structure Prediction

Two methods for structure prediction:

| Method | Source | Use Case |
|--------|--------|----------|
| **AlphaFold DB** | Pre-computed structures | Known proteins with UniProt IDs |
| **ESMFold** | On-demand prediction | Novel sequences, variants |

```python
from ml import predict_structure_alphafold, predict_structure_esmfold

# AlphaFold (pre-computed)
structure = predict_structure_alphafold(uniprot_id="P04637")  # TP53

# ESMFold (de novo)
structure = predict_structure_esmfold(sequence="MVLSPADKTNVKAAWGKVGAHAGEYGAEAL...")
```

### 3. Drug Response Prediction

Pharmacogenomics predictions using GDSC and CCLE data:

```python
from ml import predict_drug_response

results = predict_drug_response(
    drug="Erlotinib",
    tissue="lung",
    mutations=["EGFR"]
)
# Returns: IC50, AUC, sensitivity predictions for cell lines
```

**Supported Drug Classes:**
- EGFR inhibitors (Erlotinib, Gefitinib, Lapatinib)
- BRAF inhibitors (Vemurafenib, Dabrafenib)
- MEK inhibitors (Trametinib)
- PARP inhibitors (Olaparib, Talazoparib)
- ALK inhibitors (Crizotinib)
- BCR-ABL inhibitors (Imatinib)
- Chemotherapy (Paclitaxel, Cisplatin, Doxorubicin)

### 4. Cell Type Annotation

Single-cell RNA-seq cell type annotation:

| Method | Description |
|--------|-------------|
| **CellTypist** | ML-based annotation with pre-trained models |
| **scType** | Marker-based annotation |

```python
from ml import annotate_cell_types

results = annotate_cell_types(
    expression_data=adata,  # AnnData or matrix
    method="celltypist",
    model="Immune_All_Low.pkl"
)
# Returns: Cell type predictions with confidence scores
```

**Available CellTypist Models:**
- `Immune_All_Low.pkl` / `Immune_All_High.pkl`
- `Healthy_COVID19_PBMC.pkl`
- `COVID19_Immune_Landscape.pkl`
- `Pan_Fetal_Human.pkl`
- `Cells_Lung_Airway.pkl`
- `Cells_Intestinal_Tract.pkl`

### 5. Biomarker Discovery

Ensemble feature selection for biomarker identification:

```python
from ml import discover_biomarkers

results = discover_biomarkers(
    X=expression_matrix,      # samples x features
    y=labels,                 # class labels
    n_features=20,
    methods=["differential", "random_forest", "lasso", "mutual_info"]
)
# Returns: Ranked biomarkers with importance scores, CV performance
```

**Selection Methods:**
| Method | Description |
|--------|-------------|
| `differential` | T-test with fold change weighting |
| `random_forest` | RF feature importance |
| `lasso` | L1-regularized logistic regression |
| `mutual_info` | Mutual information scores |

---

## Workflow Engines

BioAgent supports three major workflow engines for reproducible pipelines:

### Nextflow

```python
from workflows import WorkflowManager

wm = WorkflowManager(workspace_dir="./workspace")

# Create workflow
result = wm.create_workflow(
    engine="nextflow",
    name="rnaseq_pipeline",
    definition="""
    nextflow.enable.dsl=2

    params.reads = "data/*_{1,2}.fastq.gz"
    params.genome = "reference/genome.fa"

    process FASTQC {
        input: tuple val(sample_id), path(reads)
        output: path("*_fastqc.{zip,html}")
        script: "fastqc ${reads}"
    }

    process ALIGN {
        input: tuple val(sample_id), path(reads)
        output: tuple val(sample_id), path("*.bam")
        script: "STAR --readFilesIn ${reads} --genomeDir ${params.genome}"
    }

    workflow {
        reads_ch = Channel.fromFilePairs(params.reads)
        FASTQC(reads_ch)
        ALIGN(reads_ch)
    }
    """
)

# Run workflow
run_result = wm.run_workflow(
    workflow_path=result.outputs["workflow_path"],
    engine="nextflow",
    params={"reads": "samples/*_{1,2}.fq.gz"}
)
```

### Snakemake

```python
result = wm.create_workflow(
    engine="snakemake",
    name="variant_calling",
    definition="""
    SAMPLES = ["sample1", "sample2", "sample3"]

    rule all:
        input: expand("results/{sample}.vcf", sample=SAMPLES)

    rule align:
        input: "data/{sample}.fastq.gz"
        output: "aligned/{sample}.bam"
        shell: "bwa mem reference.fa {input} | samtools sort -o {output}"

    rule call_variants:
        input: "aligned/{sample}.bam"
        output: "results/{sample}.vcf"
        shell: "bcftools mpileup -f reference.fa {input} | bcftools call -mv -o {output}"
    """
)
```

### WDL (Workflow Description Language)

```python
result = wm.create_workflow(
    engine="wdl",
    name="germline_pipeline",
    definition="""
    version 1.0

    workflow GermlineVariants {
        input {
            File input_bam
            File reference
        }

        call HaplotypeCaller {
            input: bam = input_bam, ref = reference
        }

        output {
            File vcf = HaplotypeCaller.vcf
        }
    }

    task HaplotypeCaller {
        input {
            File bam
            File ref
        }
        command {
            gatk HaplotypeCaller -R ~{ref} -I ~{bam} -O output.vcf
        }
        output {
            File vcf = "output.vcf"
        }
    }
    """
)
```

### Using nf-core Pipelines

```python
# Use pre-built nf-core pipelines
result = wm.create_workflow(
    engine="nextflow",
    name="nfcore_rnaseq",
    template="nf-core/rnaseq",
    params={
        "input": "samplesheet.csv",
        "genome": "GRCh38",
        "aligner": "star_salmon"
    }
)
```

---

## Cloud & HPC Integration

BioAgent supports scaling workloads to cloud and HPC backends:

### Supported Backends

| Backend | Provider | Features |
|---------|----------|----------|
| **AWS Batch** | Amazon Web Services | S3 staging, CloudWatch logs, spot instances |
| **GCP Life Sciences** | Google Cloud | GCS staging, Compute Engine, preemptible VMs |
| **Azure Batch** | Microsoft Azure | Blob storage, low-priority VMs |
| **SLURM** | HPC Clusters | SSH-based submission, partition support |

### Configuration

```bash
# AWS
export AWS_ACCESS_KEY_ID="your-key"
export AWS_SECRET_ACCESS_KEY="your-secret"
export AWS_DEFAULT_REGION="us-east-1"
export BIOAGENT_AWS_BATCH_QUEUE="bioagent-queue"
export BIOAGENT_AWS_S3_BUCKET="bioagent-data"

# GCP
export GOOGLE_APPLICATION_CREDENTIALS="/path/to/credentials.json"
export BIOAGENT_GCP_PROJECT="my-project"
export BIOAGENT_GCP_REGION="us-central1"

# Azure
export AZURE_BATCH_ACCOUNT="mybatchaccount"
export AZURE_BATCH_KEY="your-key"
export AZURE_STORAGE_CONNECTION_STRING="your-connection-string"

# SLURM
export BIOAGENT_SLURM_HOST="cluster.example.com"
export BIOAGENT_SLURM_USER="username"
export BIOAGENT_SLURM_KEY_FILE="~/.ssh/id_rsa"
```

### Usage

```python
from cloud import CloudExecutor, ResourceSpec

executor = CloudExecutor()

# Define resources
resources = ResourceSpec(
    vcpus=8,
    memory_gb=32,
    gpu_count=1,
    gpu_type="nvidia-tesla-v100",
    timeout_hours=4,
    use_spot=True
)

# Submit to AWS Batch
job = executor.run_on_aws_batch(
    command="nextflow run nf-core/rnaseq -profile docker",
    resources=resources,
    job_name="rnaseq-analysis"
)

# Check status
status = executor.get_job_status(job.job_id, backend="aws")

# Get logs
logs = executor.get_job_logs(job.job_id, backend="aws")

# Estimate costs
cost = executor.estimate_cost(resources, backend="aws", hours=4)
```

### Cost Estimation

```python
from cloud import CloudExecutor, ResourceSpec

executor = CloudExecutor()
resources = ResourceSpec(vcpus=16, memory_gb=64, gpu_count=1)

# Compare costs across providers
for backend in ["aws", "gcp", "azure"]:
    cost = executor.estimate_cost(resources, backend=backend, hours=8)
    print(f"{backend}: ${cost['total']:.2f} ({cost['instance_type']})")
```

---

## Visualization & Reporting

### Publication-Quality Figures

Create journal-ready figures with pre-defined styles:

```python
from visualization import PublicationFigure

# Create Nature-style figure
pub_fig = PublicationFigure(style="nature")
fig, axes = pub_fig.create_figure(n_panels=2, figsize=(7, 3.5))

# Volcano plot
pub_fig.volcano_plot(
    axes[0],
    data=deg_results,
    x_col="log2FoldChange",
    y_col="padj",
    label_col="gene_name"
)

# Heatmap
pub_fig.heatmap(
    axes[1],
    data=expression_matrix,
    row_labels=gene_names,
    col_labels=sample_names
)

pub_fig.save("figure1.pdf", dpi=300)
```

**Available Styles:**
- `nature` - Nature journal format
- `cell` - Cell journal format
- `science` - Science journal format
- `pnas` - PNAS format
- `default` - Clean default style

**Plot Types:**
- Volcano plots
- MA plots
- Heatmaps
- PCA plots
- Survival curves (Kaplan-Meier)
- Forest plots
- Manhattan plots

### Interactive Plots

```python
from visualization import InteractivePlotter

plotter = InteractivePlotter()

# Interactive volcano plot
fig = plotter.volcano_plot(
    data=deg_results,
    x_col="log2FoldChange",
    y_col="padj",
    hover_data=["gene_name", "baseMean"]
)
fig.write_html("volcano_interactive.html")

# Network visualization
fig = plotter.network_plot(
    nodes=genes,
    edges=interactions,
    node_size="degree",
    node_color="pathway"
)
```

### Report Generation

```python
from reporting import create_analysis_notebook, create_rmarkdown_report, create_dashboard

# Jupyter notebook
notebook = create_analysis_notebook(
    title="RNA-seq Analysis Report",
    analysis_type="differential_expression",
    data_files=["counts.csv", "metadata.csv"],
    parameters={"fdr": 0.05, "lfc": 1.0}
)

# R Markdown report
report = create_rmarkdown_report(
    title="Variant Analysis Report",
    analysis_type="variant_annotation",
    output_format="html"
)

# Streamlit dashboard
dashboard = create_dashboard(
    title="Gene Expression Explorer",
    framework="streamlit",
    data_source="expression_data.h5ad"
)
```

---

## Memory System

BioAgent includes an intelligent memory system for context persistence:

### Components

| Component | Description | Use Case |
|-----------|-------------|----------|
| **Vector Store** | Semantic similarity search | Find relevant past analyses |
| **Knowledge Graph** | Entity-relationship tracking | Connect genes, pathways, findings |
| **Artifact Store** | Intermediate result storage | Cache expensive computations |
| **Session Summarizer** | Conversation compression | Maintain context in long sessions |

### Usage

```python
from memory import ContextManager, MemoryConfig

# Initialize memory system
config = MemoryConfig.from_env(workspace_dir="./workspace")
memory = ContextManager(config)

# Search past analyses
results = memory.search_memory("BRCA1 pathway analysis", max_results=5)

# Save artifacts
memory.save_artifact(
    name="deg_results",
    content=deg_dataframe.to_json(),
    artifact_type="analysis_result",
    description="Differential expression results for tumor vs normal"
)

# Track entities
memory.on_tool_result(
    tool_name="query_uniprot",
    tool_input={"query": "TP53"},
    result=uniprot_result
)
# Automatically extracts and stores: Gene(TP53), Protein(P53), etc.

# Get related entities
entities = memory.get_entities(query="TP53", include_relationships=True)
```

### Configuration

```bash
# Memory system settings
export BIOAGENT_MEMORY_ENABLED=true
export BIOAGENT_MEMORY_DIR=".bioagent_memory"
export BIOAGENT_VECTOR_SIMILARITY_THRESHOLD=0.3
export BIOAGENT_MAX_MEMORY_RESULTS=10
```

---

## Multi-Agent System

BioAgent supports a Coordinator-Specialist architecture for complex tasks:

### Specialist Agents

| Agent | Role | Tools | Capabilities |
|-------|------|-------|--------------|
| **Pipeline Engineer** | Code & workflows | 28 | Python, R, Bash, workflows, cloud, ML, visualization |
| **Statistician** | Statistical analysis | 18 | Stats, enrichment, DE analysis, ML, visualization |
| **Literature Agent** | Database queries | 18 | All database tools, web search, memory |
| **QC Reviewer** | Quality control | 5 | Read-only analysis and validation |
| **Domain Expert** | Biological interpretation | 18 | Database queries, ML predictions, knowledge synthesis |

### Enabling Multi-Agent Mode

```bash
# Environment variable
export BIOAGENT_MULTI_AGENT=true
export BIOAGENT_MULTI_AGENT_PARALLEL=true

# Or in code
from agent import BioAgent
from config import Config

config = Config.from_env()
config.enable_multi_agent = True

agent = BioAgent(config=config)
```

### How It Works

1. **User Query** → Coordinator Agent
2. **Task Routing** → Identifies required specialists
3. **Parallel/Sequential Execution** → Specialists work on subtasks
4. **Output Synthesis** → Coordinator combines results
5. **Response** → Unified answer to user

```
User: "Analyze DEGs and find enriched pathways with literature support"

Coordinator routes to:
├── Statistician → DE analysis, enrichment
├── Literature Agent → Pathway databases, PubMed
└── Domain Expert → Biological interpretation

Coordinator synthesizes → Final comprehensive response
```

---

## Configuration

### Environment Variables

Create a `.env` file in the project root:

```bash
# =============================================================================
# REQUIRED
# =============================================================================
ANTHROPIC_API_KEY=sk-ant-your-key-here

# =============================================================================
# RECOMMENDED
# =============================================================================
NCBI_EMAIL=your.email@example.com
NCBI_API_KEY=your_ncbi_key

# =============================================================================
# MODEL SETTINGS
# =============================================================================
BIOAGENT_MODEL=claude-sonnet-4-20250514
BIOAGENT_MODEL_COMPLEX=claude-opus-4-0-20250115
BIOAGENT_MAX_ROUNDS=25

# =============================================================================
# WORKSPACE SETTINGS
# =============================================================================
BIOAGENT_WORKSPACE=/path/to/workspace
BIOAGENT_VERBOSE=true
BIOAGENT_AUTO_SAVE=true
BIOAGENT_RESULTS_DIR=results

# =============================================================================
# MULTI-AGENT SETTINGS
# =============================================================================
BIOAGENT_MULTI_AGENT=false
BIOAGENT_MULTI_AGENT_PARALLEL=true
BIOAGENT_COORDINATOR_MODEL=claude-sonnet-4-20250514
BIOAGENT_SPECIALIST_MODEL=claude-sonnet-4-20250514

# =============================================================================
# MEMORY SETTINGS
# =============================================================================
BIOAGENT_MEMORY_ENABLED=true
BIOAGENT_MEMORY_DIR=.bioagent_memory
BIOAGENT_VECTOR_SIMILARITY_THRESHOLD=0.3

# =============================================================================
# EXECUTION SETTINGS
# =============================================================================
BIOAGENT_USE_DOCKER=false
BIOAGENT_DOCKER_IMAGE=bioagent-tools:latest

# =============================================================================
# CLOUD SETTINGS (AWS)
# =============================================================================
AWS_ACCESS_KEY_ID=your-key
AWS_SECRET_ACCESS_KEY=your-secret
AWS_DEFAULT_REGION=us-east-1
BIOAGENT_AWS_BATCH_QUEUE=bioagent-queue
BIOAGENT_AWS_S3_BUCKET=bioagent-data

# =============================================================================
# CLOUD SETTINGS (GCP)
# =============================================================================
GOOGLE_APPLICATION_CREDENTIALS=/path/to/credentials.json
BIOAGENT_GCP_PROJECT=my-project
BIOAGENT_GCP_REGION=us-central1
BIOAGENT_GCS_BUCKET=bioagent-data

# =============================================================================
# CLOUD SETTINGS (Azure)
# =============================================================================
AZURE_BATCH_ACCOUNT=mybatchaccount
AZURE_BATCH_KEY=your-key
AZURE_BATCH_URL=https://mybatchaccount.region.batch.azure.com
AZURE_STORAGE_CONNECTION_STRING=your-connection-string
BIOAGENT_AZURE_POOL_ID=bioagent-pool

# =============================================================================
# CLOUD SETTINGS (SLURM)
# =============================================================================
BIOAGENT_SLURM_HOST=cluster.example.com
BIOAGENT_SLURM_USER=username
BIOAGENT_SLURM_KEY_FILE=~/.ssh/id_rsa
BIOAGENT_SLURM_PARTITION=gpu
```

### Configuration Reference

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `ANTHROPIC_API_KEY` | Yes | - | Anthropic API key |
| `NCBI_EMAIL` | Recommended | - | Email for NCBI E-utilities |
| `NCBI_API_KEY` | No | - | NCBI API key (higher rate limits) |
| `BIOAGENT_MODEL` | No | `claude-sonnet-4-20250514` | Default model |
| `BIOAGENT_MODEL_COMPLEX` | No | `claude-opus-4-0-20250115` | Model for complex queries |
| `BIOAGENT_WORKSPACE` | No | `~/bioagent_workspace` | Working directory |
| `BIOAGENT_VERBOSE` | No | `true` | Show tool calls |
| `BIOAGENT_AUTO_SAVE` | No | `true` | Auto-save results |
| `BIOAGENT_USE_DOCKER` | No | `false` | Run tools in Docker |
| `BIOAGENT_MAX_ROUNDS` | No | `25` | Max tool iterations |
| `BIOAGENT_MULTI_AGENT` | No | `false` | Enable multi-agent mode |
| `BIOAGENT_MEMORY_ENABLED` | No | `true` | Enable memory system |

---

## API Reference

### BioAgent Class

```python
from agent import BioAgent
from config import Config

# Initialize with default config
agent = BioAgent()

# Initialize with custom config
config = Config(
    anthropic_api_key="sk-ant-...",
    workspace_dir="./analysis",
    model="claude-sonnet-4-20250514",
    auto_save_results=True,
    enable_multi_agent=True
)
agent = BioAgent(config=config)

# Run a query
result = agent.run("Analyze TP53 variants in my VCF file")

# Run with complex model
result = agent.run(
    "Design a multi-omics integration pipeline",
    use_complex_model=True
)

# Session management
agent.save_session("session.json")
agent.load_session("session.json")

# Get conversation history
history = agent.get_history()
```

### Tool Functions

```python
# Database queries
from ncbi import NCBIClient
from ensembl import EnsemblClient
from uniprot import UniProtClient
# ... etc

# ML/AI
from ml import (
    predict_variant_pathogenicity,
    predict_structure_alphafold,
    predict_structure_esmfold,
    predict_drug_response,
    annotate_cell_types,
    discover_biomarkers
)

# Workflows
from workflows import WorkflowManager

# Cloud
from cloud import CloudExecutor, ResourceSpec, CloudConfig

# Visualization
from visualization import PublicationFigure, InteractivePlotter

# Reporting
from reporting import (
    create_analysis_notebook,
    create_rmarkdown_report,
    create_dashboard
)

# Memory
from memory import ContextManager, MemoryConfig
```

---

## Examples

### Example 1: Complete Gene Analysis

```python
from agent import BioAgent

agent = BioAgent()

result = agent.run("""
Perform a comprehensive analysis of the BRCA1 gene:

1. Get basic gene information from NCBI
2. Fetch protein details from UniProt
3. Find all pathways involving BRCA1 (KEGG + Reactome)
4. Get protein interaction network from STRING (score > 700)
5. Check gnomAD for clinically significant variants
6. Get the AlphaFold structure and assess quality
7. Summarize findings with biological interpretation
""")
```

### Example 2: RNA-seq Analysis Pipeline

```python
from agent import BioAgent

agent = BioAgent()

result = agent.run("""
Create and run an RNA-seq analysis:

1. Create a Nextflow pipeline that:
   - Runs FastQC on raw reads
   - Aligns with STAR
   - Quantifies with featureCounts
   - Runs DESeq2 for differential expression

2. Submit to AWS Batch with 16 vCPUs, 64GB RAM

3. Generate a publication-quality volcano plot of the results

4. Create a Jupyter notebook documenting the analysis
""", use_complex_model=True)
```

### Example 3: Variant Interpretation

```python
from agent import BioAgent

agent = BioAgent()

result = agent.run("""
Interpret these variants found in a cancer patient:

Variants:
- TP53: c.743G>A (p.Arg248Gln)
- BRCA1: c.5266dupC (p.Gln1756fs)
- EGFR: c.2573T>G (p.Leu858Arg)

For each variant:
1. Predict pathogenicity (CADD, REVEL, AlphaMissense)
2. Check gnomAD population frequency
3. Find relevant literature
4. Assess drug response implications
5. Provide clinical interpretation
""")
```

### Example 4: Single-Cell Analysis

```python
from agent import BioAgent

agent = BioAgent()

result = agent.run("""
Analyze the single-cell RNA-seq data in 'pbmc_3k.h5ad':

1. Perform quality control (filter cells and genes)
2. Normalize and log-transform
3. Find highly variable genes
4. Run PCA and UMAP
5. Cluster cells (Leiden algorithm)
6. Annotate cell types using CellTypist
7. Find marker genes for each cluster
8. Create publication figures:
   - UMAP colored by cell type
   - Dot plot of top markers
   - Violin plots for key genes
9. Generate an HTML report
""")
```

---

## Extending BioAgent

### Adding New Database Clients

1. Create module (e.g., `mydb.py`):

```python
from dataclasses import dataclass

@dataclass
class MyDBResult:
    success: bool
    data: dict
    error: str | None = None

    def to_string(self) -> str:
        if not self.success:
            return f"Error: {self.error}"
        return json.dumps(self.data, indent=2)

class MyDBClient:
    BASE_URL = "https://api.mydb.org"

    def query(self, query: str, **kwargs) -> MyDBResult:
        # Implementation
        pass
```

2. Add tool schema in `definitions.py`:

```python
{
    "name": "query_mydb",
    "description": "Query MyDB for...",
    "input_schema": {
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "Search query"}
        },
        "required": ["query"]
    }
}
```

3. Add handler in `agent.py`:

```python
elif name == "query_mydb":
    result = self.mydb.query(
        query=input_data["query"],
        # ... other params
    )
    return result.to_string()
```

### Adding New ML Models

1. Create module in `ml/`:

```python
# ml/my_predictor.py

@dataclass
class MyPrediction:
    # fields...

    def to_dict(self) -> dict:
        return {...}

class MyPredictor:
    def predict(self, input_data) -> MyPrediction:
        # Implementation
        pass

def predict_my_thing(input_data) -> dict:
    predictor = MyPredictor()
    result = predictor.predict(input_data)
    return result.to_dict()
```

2. Export in `ml/__init__.py`
3. Add tool definition in `definitions.py`
4. Add handler in `agent.py`

### Adding New Cloud Backends

Extend `CloudExecutor` in `cloud/base.py`:

```python
def run_on_my_cloud(
    self,
    command: str,
    resources: ResourceSpec,
    **kwargs
) -> JobInfo:
    # Implementation
    pass
```

---

## Troubleshooting

### Common Issues

**1. API Key Errors**
```
Error: ANTHROPIC_API_KEY is not set
```
Solution: Set the environment variable or add to `.env` file.

**2. NCBI Rate Limiting**
```
Error: Too Many Requests
```
Solution: Set `NCBI_API_KEY` for higher rate limits.

**3. Memory System Errors**
```
Error: ChromaDB not available
```
Solution: BioAgent falls back to SimpleVectorStore automatically. For full features, install with Python < 3.14.

**4. Workflow Engine Not Found**
```
Error: Nextflow not installed
```
Solution: Install the workflow engine or use WSL on Windows.

**5. Cloud Authentication**
```
Error: AWS credentials not found
```
Solution: Configure AWS CLI or set environment variables.

### Getting Help

- **Documentation**: See `docs/` directory
- **Issues**: [GitHub Issues](https://github.com/EdiBig/bioagent/issues)
- **Cloud Setup**: See `docs/cloud-setup.md`

---

## Project Structure

```
bioagent/
├── run.py                    # CLI entry point
├── agent.py                  # Core agentic loop
├── config.py                 # Configuration management
├── system.py                 # System prompt
├── definitions.py            # Tool schemas (43 tools)
│
├── # Code Execution
├── code_executor.py          # Python/R/Bash execution
├── file_manager.py           # File I/O
│
├── # Database Clients (11)
├── ncbi.py                   # NCBI E-utilities
├── ensembl.py                # Ensembl REST API
├── uniprot.py                # UniProt REST API
├── kegg.py                   # KEGG REST API
├── string_db.py              # STRING database
├── pdb_client.py             # PDB/RCSB
├── alphafold.py              # AlphaFold DB
├── interpro.py               # InterPro
├── reactome.py               # Reactome
├── gene_ontology.py          # Gene Ontology
├── gnomad.py                 # gnomAD
│
├── # ML/AI Modules (5)
├── ml/
│   ├── __init__.py
│   ├── pathogenicity.py      # Variant scoring
│   ├── structure.py          # Structure prediction
│   ├── drug_response.py      # Pharmacogenomics
│   ├── cell_annotation.py    # Cell typing
│   └── biomarkers.py         # Feature selection
│
├── # Workflow Engines
├── workflows/
│   ├── __init__.py
│   ├── base.py               # Base classes
│   ├── manager.py            # Unified manager
│   ├── nextflow.py           # Nextflow engine
│   ├── snakemake.py          # Snakemake engine
│   └── wdl.py                # WDL/miniwdl
│
├── # Cloud/HPC Integration
├── cloud/
│   ├── __init__.py
│   ├── config.py             # Cloud configuration
│   ├── base.py               # CloudExecutor
│   ├── aws.py                # AWS Batch
│   ├── gcp.py                # GCP Life Sciences
│   ├── azure.py              # Azure Batch
│   └── slurm.py              # SLURM
│
├── # Visualization
├── visualization/
│   ├── __init__.py
│   ├── publication.py        # Publication figures
│   ├── interactive.py        # Plotly/Bokeh
│   └── themes.py             # Journal themes
│
├── # Reporting
├── reporting/
│   ├── __init__.py
│   ├── notebook.py           # Jupyter notebooks
│   ├── rmarkdown.py          # R Markdown
│   └── dashboard.py          # Streamlit/Dash
│
├── # Memory System
├── memory/
│   ├── __init__.py
│   ├── vector_store.py       # Semantic search
│   ├── knowledge_graph.py    # Entity tracking
│   ├── artifacts.py          # Result storage
│   ├── summarizer.py         # Session compression
│   └── context_manager.py    # Orchestration
│
├── # Multi-Agent System
├── agents/
│   ├── __init__.py
│   ├── base.py               # BaseAgent
│   ├── coordinator.py        # Coordinator
│   ├── routing.py            # Task routing
│   ├── context.py            # Shared context
│   ├── prompts.py            # Agent prompts
│   ├── tools.py              # Tool filtering
│   └── specialists/          # Specialist agents
│
├── # Web Search
├── web_search.py             # DuckDuckGo search
│
├── # Documentation
├── docs/
│   ├── cloud-setup.md        # Cloud setup guide
│   └── cloud-quickref.md     # Quick reference
│
└── # Tests
    └── test_ml_tools.py      # ML tools test suite
```

---

## Cost Estimates

| Usage Level | Model | Approx. Monthly Cost |
|-------------|-------|----------------------|
| Light (5-10 queries/day) | Sonnet | $20-40 |
| Moderate (20-30 queries/day) | Sonnet | $60-120 |
| Heavy / Complex analyses | Sonnet + Opus | $100-200 |
| Multi-agent intensive | Opus | $200-400 |

**Tips for cost optimization:**
- Use Sonnet for routine queries
- Reserve Opus for complex multi-step reasoning
- Enable caching in memory system
- Use multi-agent mode only when needed

---

## License

MIT License - see [LICENSE](LICENSE) for details.

---

## Citation

If you use BioAgent in your research, please cite:

```bibtex
@software{bioagent2025,
  title = {BioAgent: AI-Powered Bioinformatics Assistant},
  author = {EdiBig},
  year = {2025},
  url = {https://github.com/EdiBig/bioagent}
}
```

---

## Acknowledgments

BioAgent integrates with many excellent open-source tools and databases:

- [Anthropic Claude](https://anthropic.com) - AI backbone
- [NCBI](https://www.ncbi.nlm.nih.gov/) - Sequence and literature databases
- [Ensembl](https://ensembl.org/) - Genome browser and annotations
- [UniProt](https://uniprot.org/) - Protein knowledge base
- [AlphaFold](https://alphafold.ebi.ac.uk/) - Structure predictions
- [Nextflow](https://nextflow.io/) - Workflow engine
- [Snakemake](https://snakemake.github.io/) - Workflow engine
- And many more...
