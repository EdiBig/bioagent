# BioAgent User Guide

A comprehensive manual for using BioAgent - your AI-powered bioinformatics assistant.

---

## Table of Contents

1. [Getting Started](#1-getting-started)
   - [Installation](#11-installation)
   - [Configuration](#12-configuration)
   - [First Run](#13-first-run)
   - [Understanding the Interface](#14-understanding-the-interface)

2. [Core Concepts](#2-core-concepts)
   - [How BioAgent Works](#21-how-bioagent-works)
   - [Tools and Capabilities](#22-tools-and-capabilities)
   - [Query Types](#23-query-types)

3. [Database Queries](#3-database-queries)
   - [NCBI (Gene, PubMed, Nucleotide)](#31-ncbi)
   - [Ensembl](#32-ensembl)
   - [UniProt](#33-uniprot)
   - [KEGG](#34-kegg)
   - [STRING](#35-string)
   - [PDB](#36-pdb)
   - [AlphaFold](#37-alphafold)
   - [InterPro](#38-interpro)
   - [Reactome](#39-reactome)
   - [Gene Ontology](#310-gene-ontology)
   - [gnomAD](#311-gnomad)
   - [Combining Multiple Databases](#312-combining-multiple-databases)

4. [Code Execution](#4-code-execution)
   - [Python Scripts](#41-python-scripts)
   - [R Scripts](#42-r-scripts)
   - [Bash Commands](#43-bash-commands)
   - [Working with Files](#44-working-with-files)

5. [ML/AI Predictions](#5-mlai-predictions)
   - [Variant Pathogenicity](#51-variant-pathogenicity)
   - [Protein Structure Prediction](#52-protein-structure-prediction)
   - [Drug Response Prediction](#53-drug-response-prediction)
   - [Cell Type Annotation](#54-cell-type-annotation)
   - [Biomarker Discovery](#55-biomarker-discovery)

6. [Data Ingestion](#6-data-ingestion)
   - [Supported Formats](#61-supported-formats)
   - [Ingesting Files](#62-ingesting-files)
   - [Format-Specific Profiling](#63-format-specific-profiling)
   - [Dataset Validation](#64-dataset-validation)

7. [Workflow Management](#7-workflow-management)
   - [Nextflow Pipelines](#71-nextflow-pipelines)
   - [Snakemake Workflows](#72-snakemake-workflows)
   - [WDL Workflows](#73-wdl-workflows)
   - [Using nf-core Pipelines](#74-using-nf-core-pipelines)

8. [Cloud & HPC](#8-cloud--hpc)
   - [AWS Batch](#81-aws-batch)
   - [Google Cloud](#82-google-cloud)
   - [Azure Batch](#83-azure-batch)
   - [SLURM Clusters](#84-slurm-clusters)
   - [Cost Management](#85-cost-management)

9. [Visualization](#9-visualization)
   - [Publication Figures](#91-publication-figures)
   - [Interactive Plots](#92-interactive-plots)
   - [Common Plot Types](#93-common-plot-types)

10. [Report Generation](#10-report-generation)
    - [Jupyter Notebooks](#101-jupyter-notebooks)
    - [R Markdown Reports](#102-r-markdown-reports)
    - [Dashboards](#103-dashboards)

11. [Memory System](#11-memory-system)
    - [Searching Past Analyses](#111-searching-past-analyses)
    - [Saving Artifacts](#112-saving-artifacts)
    - [Knowledge Graph](#113-knowledge-graph)

12. [Workspace & Analysis Tracking](#12-workspace--analysis-tracking)
    - [Starting an Analysis](#121-starting-an-analysis)
    - [Managing Projects](#122-managing-projects)
    - [Finding Past Work](#123-finding-past-work)

13. [Multi-Agent Mode](#13-multi-agent-mode)
    - [When to Use Multi-Agent](#131-when-to-use-multi-agent)
    - [Understanding Specialists](#132-understanding-specialists)

14. [Complete Tutorials](#14-complete-tutorials)
    - [Tutorial 1: Gene Investigation](#141-tutorial-1-gene-investigation)
    - [Tutorial 2: RNA-seq Analysis](#142-tutorial-2-rna-seq-analysis)
    - [Tutorial 3: Variant Interpretation](#143-tutorial-3-variant-interpretation)
    - [Tutorial 4: Single-Cell Analysis](#144-tutorial-4-single-cell-analysis)

15. [Best Practices](#15-best-practices)

16. [Troubleshooting](#16-troubleshooting)

---

## 1. Getting Started

### 1.1 Installation

#### Step 1: Clone the Repository

```bash
git clone https://github.com/EdiBig/bioagent.git
cd bioagent
```

#### Step 2: Create a Virtual Environment (Recommended)

```bash
# Create virtual environment
python -m venv venv

# Activate it
# On Linux/Mac:
source venv/bin/activate

# On Windows:
venv\Scripts\activate
```

#### Step 3: Install Dependencies

```bash
pip install -r requirements.txt
```

#### Step 4: Verify Installation

```bash
python -c "from agent import BioAgent; print('Installation successful!')"
```

### 1.2 Configuration

#### Step 1: Create Environment File

Create a file named `.env` in the bioagent directory:

```bash
# Required - Get your key from https://console.anthropic.com
ANTHROPIC_API_KEY=sk-ant-your-key-here

# Recommended - For NCBI queries (get from https://www.ncbi.nlm.nih.gov/account/settings/)
NCBI_EMAIL=your.email@example.com
NCBI_API_KEY=your_ncbi_api_key

# Optional - Customize workspace location
BIOAGENT_WORKSPACE=/path/to/your/workspace
```

#### Step 2: Verify Configuration

```bash
python run.py --query "Hello, can you confirm you're working?"
```

### 1.3 First Run

#### Interactive Mode

Start BioAgent in chat mode:

```bash
python run.py
```

You'll see:
```
BioAgent ready. Type your query (or 'quit' to exit):
>
```

Type your question and press Enter.

#### Single Query Mode

For one-off questions:

```bash
python run.py --query "What is the function of the TP53 gene?"
```

#### Complex Analysis Mode

For multi-step analyses requiring deeper reasoning:

```bash
python run.py --complex "Design a complete variant calling pipeline for whole exome sequencing"
```

### 1.4 Understanding the Interface

When BioAgent processes your request, you'll see:

```
> What pathways involve BRCA1?

[Tool: query_kegg] Searching KEGG pathways...
[Tool: query_reactome] Searching Reactome pathways...

BRCA1 is involved in several key pathways:

1. **DNA Damage Response**
   - Homologous recombination repair
   - Double-strand break repair
   ...
```

**What the output shows:**
- `[Tool: name]` - Which tool BioAgent is using
- Tool results are processed internally
- Final response is a synthesized answer

---

## 2. Core Concepts

### 2.1 How BioAgent Works

BioAgent operates as an **autonomous agent** that:

```
Your Question
     ↓
┌─────────────────────┐
│   Claude AI Model   │  ← Reasons about your question
└─────────────────────┘
     ↓
┌─────────────────────┐
│   Select Tool(s)    │  ← Chooses appropriate tools
└─────────────────────┘
     ↓
┌─────────────────────┐
│   Execute Tool      │  ← Runs database query/code/etc.
└─────────────────────┘
     ↓
┌─────────────────────┐
│   Analyze Result    │  ← Interprets the output
└─────────────────────┘
     ↓
   Need more info? → Loop back to tool selection
     ↓
┌─────────────────────┐
│   Final Response    │  ← Synthesized answer
└─────────────────────┘
```

### 2.2 Tools and Capabilities

BioAgent has **58 tools** across 11 categories:

| Category | Tools | What They Do |
|----------|-------|--------------|
| **Code Execution** | 3 | Run Python, R, Bash |
| **Databases** | 11 | Query biological databases |
| **ML/AI** | 5 | Predictions and analysis |
| **Workflows** | 6 | Create and run pipelines |
| **Cloud/HPC** | 6 | Scale to cloud computing |
| **Visualization** | 3 | Create figures and reports |
| **Memory** | 5 | Remember and retrieve context |
| **Files** | 3 | Read, write, list files |
| **Data Ingestion** | 6 | Auto-detect formats, profile data |
| **Workspace Tracking** | 6 | Track analyses, manage projects |
| **Web Search** | 1 | Search documentation/papers |

### 2.3 Query Types

**Simple Queries** - Single database lookup:
```
"What is the UniProt ID for TP53?"
```

**Multi-Step Queries** - Multiple tools needed:
```
"Find all proteins that interact with BRCA1 and check which ones are in DNA repair pathways"
```

**Analysis Queries** - Code execution required:
```
"Analyze the gene expression data in counts.csv and find differentially expressed genes"
```

**Pipeline Queries** - Workflow creation:
```
"Create a Nextflow pipeline for RNA-seq alignment"
```

---

## 3. Database Queries

### 3.1 NCBI

**What it provides:** Gene information, sequences, literature (PubMed), taxonomy

#### Basic Gene Search

```
Query: "Search NCBI Gene for TP53 in humans"

What happens:
1. BioAgent queries NCBI Gene database
2. Returns gene ID, location, description, aliases
```

#### PubMed Literature Search

```
Query: "Find recent papers about CRISPR cancer therapy from PubMed"

What happens:
1. Searches PubMed with your terms
2. Returns titles, authors, abstracts, PMIDs
```

#### Sequence Retrieval

```
Query: "Get the mRNA sequence for human BRCA1 from NCBI"

What happens:
1. Searches NCBI Nucleotide database
2. Returns sequence in FASTA format
```

#### Step-by-Step Example: Complete Gene Lookup

```
Step 1: Start BioAgent
$ python run.py

Step 2: Enter your query
> Get comprehensive information about the MDM2 gene from NCBI

Step 3: BioAgent will:
- Search NCBI Gene for MDM2
- Retrieve gene summary, location, aliases
- Find associated RefSeq transcripts
- Return organized information

Step 4: Review the response
- Gene ID, chromosome location
- Function summary
- Associated transcripts and proteins
```

### 3.2 Ensembl

**What it provides:** Genomic coordinates, variants, comparative genomics, regulatory data

#### Gene Lookup

```
Query: "Get Ensembl information for EGFR including all transcripts"
```

#### Variant Information

```
Query: "Find all known variants in the BRAF gene from Ensembl"
```

#### Cross-References

```
Query: "Get all database cross-references for ENSG00000141510 (TP53)"
```

#### Step-by-Step: Finding Gene Coordinates

```
Step 1: Query
> What are the genomic coordinates of the KRAS gene in GRCh38?

Step 2: BioAgent queries Ensembl REST API

Step 3: Response includes:
- Chromosome: 12
- Start: 25205246
- End: 25250936
- Strand: -1 (reverse)
- Assembly: GRCh38
```

### 3.3 UniProt

**What it provides:** Protein sequences, function, domains, modifications, structure

#### Protein Information

```
Query: "Get UniProt entry for human p53 protein"
```

#### Protein Function

```
Query: "What is the molecular function of BRCA1 protein according to UniProt?"
```

#### Sequence Features

```
Query: "Show me all domains and motifs in the EGFR protein"
```

#### Step-by-Step: Complete Protein Analysis

```
Step 1: Query
> Give me a complete UniProt analysis of the insulin receptor protein

Step 2: BioAgent retrieves:
- Accession: P06213
- Protein name, gene name
- Function description
- Subcellular location
- Domain architecture
- Post-translational modifications
- Disease associations

Step 3: Review organized output with all annotations
```

### 3.4 KEGG

**What it provides:** Pathways, genes, compounds, diseases, drug information

#### Pathway Search

```
Query: "What KEGG pathways involve the PI3K-AKT signaling?"
```

#### Gene-Pathway Links

```
Query: "Which pathways contain both BRCA1 and BRCA2?"
```

#### Compound Information

```
Query: "Get KEGG information about metformin"
```

#### Step-by-Step: Pathway Analysis

```
Step 1: Query
> Find all pathways involving TP53 and show the pathway map IDs

Step 2: BioAgent searches KEGG

Step 3: Response includes:
- hsa04110: Cell cycle
- hsa04115: p53 signaling pathway
- hsa04210: Apoptosis
- hsa05200: Pathways in cancer
... with links and descriptions
```

### 3.5 STRING

**What it provides:** Protein-protein interactions, functional associations, networks

#### Interaction Partners

```
Query: "Find proteins that interact with MYC with high confidence"
```

#### Network Analysis

```
Query: "Get the interaction network for DNA damage response proteins"
```

#### Enrichment Analysis

```
Query: "What functions are enriched in the TP53 interaction network?"
```

#### Step-by-Step: Building an Interaction Network

```
Step 1: Query
> Find all high-confidence (score > 900) interaction partners of BRCA1
  and tell me what biological processes they're involved in

Step 2: BioAgent:
- Queries STRING for BRCA1 interactions
- Filters by confidence score
- Retrieves functional annotations

Step 3: Response includes:
- List of interacting proteins (BARD1, RAD51, etc.)
- Interaction scores
- Shared biological processes
- Network statistics
```

### 3.6 PDB

**What it provides:** Experimental 3D protein structures, ligands, methods

#### Structure Search

```
Query: "Find all PDB structures for human hemoglobin"
```

#### Structure Details

```
Query: "Get details about PDB structure 1TUP (p53 DNA-binding domain)"
```

#### Ligand Information

```
Query: "What ligands are bound in EGFR kinase structures?"
```

### 3.7 AlphaFold

**What it provides:** AI-predicted protein structures, confidence scores

#### Structure Retrieval

```
Query: "Get the AlphaFold predicted structure for UniProt P04637 (p53)"
```

#### Quality Assessment

```
Query: "What is the confidence score for the AlphaFold BRCA1 structure?"
```

#### Step-by-Step: Getting a Predicted Structure

```
Step 1: Query
> Get the AlphaFold structure for human insulin and assess its quality

Step 2: BioAgent:
- Queries AlphaFold database
- Retrieves structure URL
- Gets pLDDT confidence scores

Step 3: Response includes:
- PDB file URL
- Mean pLDDT score (e.g., 92.5 - very high confidence)
- Model version
- Regions of high/low confidence
```

### 3.8 InterPro

**What it provides:** Protein families, domains, functional sites

#### Domain Analysis

```
Query: "What domains are in the STAT3 protein?"
```

#### Family Classification

```
Query: "What protein family does kinase ABL1 belong to?"
```

### 3.9 Reactome

**What it provides:** Curated biological pathways, reactions, molecular events

#### Pathway Search

```
Query: "Find Reactome pathways for DNA repair"
```

#### Pathway Details

```
Query: "Describe the Reactome pathway for homologous recombination"
```

### 3.10 Gene Ontology

**What it provides:** Standardized gene/protein annotations (function, process, location)

#### GO Term Lookup

```
Query: "What GO terms are associated with TP53?"
```

#### Enrichment Analysis

```
Query: "What GO biological processes are enriched in my gene list: BRCA1, BRCA2, RAD51, PALB2?"
```

#### Step-by-Step: GO Analysis

```
Step 1: Query
> Get all GO annotations for the ATM gene, organized by category

Step 2: BioAgent retrieves GO annotations

Step 3: Response organized by:
- Molecular Function: protein kinase activity, DNA binding
- Biological Process: DNA damage response, cell cycle checkpoint
- Cellular Component: nucleus, nucleoplasm
```

### 3.11 gnomAD

**What it provides:** Population variant frequencies, constraint metrics

#### Variant Frequency

```
Query: "What is the gnomAD frequency of BRCA1 c.5266dupC?"
```

#### Gene Constraint

```
Query: "Is TP53 constrained against loss-of-function variants?"
```

#### Step-by-Step: Variant Lookup

```
Step 1: Query
> Look up variant 17-7577121-G-A in gnomAD and tell me if it's common or rare

Step 2: BioAgent queries gnomAD GraphQL API

Step 3: Response includes:
- Allele frequency: 0.00001 (very rare)
- Population breakdown (European, African, etc.)
- Homozygote count
- Clinical significance if available
```

### 3.12 Combining Multiple Databases

The real power of BioAgent is combining information from multiple sources:

#### Example: Complete Gene Investigation

```
Query:
"For gene EGFR:
1. Get basic info from NCBI
2. Get protein details from UniProt
3. Find all pathways (KEGG + Reactome)
4. Get interaction partners (STRING, score > 800)
5. Check for clinical variants (gnomAD)
6. Get the AlphaFold structure"
```

BioAgent will systematically query each database and synthesize a comprehensive report.

---

## 4. Code Execution

### 4.1 Python Scripts

BioAgent can write and execute Python code for data analysis.

#### Basic Analysis

```
Query: "Read the file counts.csv and calculate basic statistics for each column"
```

#### Data Processing

```
Query: "Load the expression matrix from data.csv, normalize it using log2 transformation,
        and save the result to normalized_data.csv"
```

#### Step-by-Step: Python Analysis

```
Step 1: Query
> Analyze the gene expression data in expression.csv:
  - Load the data
  - Calculate mean and variance for each gene
  - Find the top 10 most variable genes
  - Create a bar plot of their variance

Step 2: BioAgent writes Python code:
```python
import pandas as pd
import matplotlib.pyplot as plt

# Load data
df = pd.read_csv('expression.csv', index_col=0)

# Calculate statistics
variance = df.var(axis=1).sort_values(ascending=False)

# Top 10 most variable
top10 = variance.head(10)

# Create plot
plt.figure(figsize=(10, 6))
top10.plot(kind='bar')
plt.title('Top 10 Most Variable Genes')
plt.ylabel('Variance')
plt.tight_layout()
plt.savefig('top_variable_genes.png')
```

```
Step 3: Code executes, plot saved

Step 4: BioAgent reports results and shows the plot
```

### 4.2 R Scripts

BioAgent can execute R code for statistical analysis.

#### DESeq2 Analysis

```
Query: "Run DESeq2 differential expression analysis on counts.csv using metadata.csv"
```

#### Statistical Tests

```
Query: "Perform a Wilcoxon test comparing expression of TP53 between tumor and normal samples"
```

#### Step-by-Step: R Analysis

```
Step 1: Query
> Using R, perform survival analysis on the clinical data in survival_data.csv
  with columns: time, status, treatment_group

Step 2: BioAgent writes R code:
```r
library(survival)
library(survminer)

# Load data
data <- read.csv('survival_data.csv')

# Fit survival model
fit <- survfit(Surv(time, status) ~ treatment_group, data = data)

# Create Kaplan-Meier plot
pdf('survival_plot.pdf')
ggsurvplot(fit, data = data, pval = TRUE, risk.table = TRUE)
dev.off()

# Log-rank test
survdiff(Surv(time, status) ~ treatment_group, data = data)
```

```
Step 3: Analysis runs, plot generated

Step 4: BioAgent reports p-value and survival statistics
```

### 4.3 Bash Commands

BioAgent can run command-line tools.

#### File Operations

```
Query: "Count the number of sequences in all FASTA files in the data directory"
```

#### Bioinformatics Tools

```
Query: "Run samtools flagstat on aligned.bam to get alignment statistics"
```

### 4.4 Working with Files

#### Reading Files

```
Query: "Read the first 50 lines of results.txt and summarize what it contains"
```

#### Writing Files

```
Query: "Create a new file called gene_list.txt containing just the gene names from my analysis"
```

#### Listing Files

```
Query: "Show me all CSV files in the results directory"
```

---

## 5. ML/AI Predictions

### 5.1 Variant Pathogenicity

Predict whether genetic variants are harmful using multiple scoring systems.

#### Single Variant

```
Query: "Predict the pathogenicity of variant 17-7577121-G-A"
```

#### Multiple Variants

```
Query: "Assess pathogenicity for these variants:
        - BRCA1: c.5266dupC
        - TP53: p.Arg248Trp
        - EGFR: p.Leu858Arg"
```

#### Step-by-Step: Variant Interpretation

```
Step 1: Query
> I found variant chr17:7577121:G>A in a patient.
  Is this pathogenic? What do the prediction scores say?

Step 2: BioAgent runs pathogenicity prediction

Step 3: Response includes:

Variant: 17-7577121-G-A

Prediction Scores:
┌─────────────────┬─────────┬─────────────────┐
│ Score           │ Value   │ Interpretation  │
├─────────────────┼─────────┼─────────────────┤
│ CADD PHRED      │ 35.0    │ Highly damaging │
│ REVEL           │ 0.89    │ Pathogenic      │
│ AlphaMissense   │ 0.92    │ Pathogenic      │
└─────────────────┴─────────┴─────────────────┘

Consensus: LIKELY PATHOGENIC (High confidence)

Step 4: BioAgent explains the biological implications
```

#### Understanding Scores

| Score | Range | Pathogenic Threshold |
|-------|-------|---------------------|
| CADD PHRED | 0-99 | >20 damaging, >30 highly damaging |
| REVEL | 0-1 | >0.5 likely pathogenic |
| AlphaMissense | 0-1 | >0.564 likely pathogenic |

### 5.2 Protein Structure Prediction

Get or predict 3D protein structures.

#### AlphaFold (Pre-computed)

```
Query: "Get the AlphaFold structure for BRCA1 protein"
```

#### ESMFold (De Novo)

```
Query: "Predict the structure of this peptide sequence: MVLSPADKTNVKAAWGKVGAHAGEYGAEAL"
```

#### Step-by-Step: Structure Analysis

```
Step 1: Query
> Get the AlphaFold structure for TP53 and tell me which regions have
  confident predictions vs uncertain regions

Step 2: BioAgent retrieves structure from AlphaFold DB

Step 3: Response includes:

Structure: TP53 (P04637)
Method: AlphaFold v4
Mean pLDDT: 75.1

Region Confidence:
┌────────────────────┬───────────┬─────────────┐
│ Region             │ Residues  │ Confidence  │
├────────────────────┼───────────┼─────────────┤
│ DNA-binding domain │ 94-292    │ Very High   │
│ Tetramerization    │ 325-356   │ High        │
│ N-terminal TAD     │ 1-61      │ Low         │
│ C-terminal reg.    │ 364-393   │ Low         │
└────────────────────┴───────────┴─────────────┘

PDB URL: https://alphafold.ebi.ac.uk/files/AF-P04637-F1-model_v4.pdb
```

### 5.3 Drug Response Prediction

Predict how cancer cell lines respond to drugs.

#### Single Drug Query

```
Query: "How do lung cancer cell lines respond to Erlotinib?"
```

#### Mutation-Based Prediction

```
Query: "Predict drug response for a tumor with EGFR L858R mutation"
```

#### Step-by-Step: Drug Sensitivity Analysis

```
Step 1: Query
> I have a melanoma patient with BRAF V600E mutation.
  Which drugs should be most effective?

Step 2: BioAgent queries drug response models

Step 3: Response includes:

BRAF V600E Melanoma - Drug Sensitivity Predictions:

High Sensitivity (Recommended):
┌──────────────┬─────────────┬────────────┬────────────┐
│ Drug         │ Target      │ IC50 (μM)  │ Confidence │
├──────────────┼─────────────┼────────────┼────────────┤
│ Vemurafenib  │ BRAF V600E  │ 0.12       │ 95%        │
│ Dabrafenib   │ BRAF V600E  │ 0.08       │ 93%        │
│ Trametinib   │ MEK1/2      │ 0.02       │ 88%        │
└──────────────┴─────────────┴────────────┴────────────┘

Combination Recommended: BRAF + MEK inhibitor

Note: Resistance may develop; consider combination therapy
```

### 5.4 Cell Type Annotation

Annotate cell types in single-cell RNA-seq data.

#### Basic Annotation

```
Query: "Annotate cell types in my single-cell data using CellTypist"
```

#### With Tissue Context

```
Query: "Annotate cell types in my PBMC single-cell data"
```

#### Step-by-Step: Cell Annotation

```
Step 1: Prepare your data
- Expression matrix (cells x genes) in CSV, H5AD, or as variable

Step 2: Query
> Annotate cell types in the file pbmc_counts.h5ad using CellTypist
  with the Immune_All_High model

Step 3: BioAgent runs annotation

Step 4: Response includes:

Cell Type Annotation Summary
────────────────────────────
Total cells: 2,638
Cell types identified: 12
Mean confidence: 0.84

Distribution:
┌─────────────────────┬───────┬─────────┐
│ Cell Type           │ Count │ Percent │
├─────────────────────┼───────┼─────────┤
│ CD4+ T cells        │ 632   │ 24.0%   │
│ CD14+ Monocytes     │ 521   │ 19.8%   │
│ CD8+ T cells        │ 398   │ 15.1%   │
│ NK cells            │ 312   │ 11.8%   │
│ B cells             │ 287   │ 10.9%   │
│ FCGR3A+ Monocytes   │ 198   │ 7.5%    │
│ ...                 │ ...   │ ...     │
└─────────────────────┴───────┴─────────┘

Low confidence cells: 142 (5.4%)
```

### 5.5 Biomarker Discovery

Find biomarkers that distinguish groups in your data.

#### Basic Discovery

```
Query: "Find biomarkers that distinguish tumor from normal samples in expression.csv"
```

#### With Specific Methods

```
Query: "Run biomarker discovery using Random Forest and LASSO on my dataset"
```

#### Step-by-Step: Biomarker Analysis

```
Step 1: Prepare your data
- Feature matrix (samples x features)
- Labels (group assignments)

Step 2: Query
> Find the top 20 biomarkers that distinguish responders from non-responders
  in treatment_data.csv. Use all available methods and validate with cross-validation.

Step 3: BioAgent runs ensemble feature selection

Step 4: Response includes:

Biomarker Discovery Results
───────────────────────────
Methods: Differential, Random Forest, LASSO, Mutual Information
Cross-validation: 5-fold

Performance:
- AUC: 0.92
- Sensitivity: 0.88
- Specificity: 0.85

Top 10 Biomarkers:
┌──────┬────────────┬─────────────┬────────────┐
│ Rank │ Gene       │ Importance  │ Direction  │
├──────┼────────────┼─────────────┼────────────┤
│ 1    │ CD274      │ 0.156       │ ↑ Resp     │
│ 2    │ PDCD1      │ 0.142       │ ↑ Resp     │
│ 3    │ IFNG       │ 0.128       │ ↑ Resp     │
│ 4    │ GZMB       │ 0.115       │ ↑ Resp     │
│ 5    │ MKI67      │ 0.098       │ ↑ Resp     │
│ ...  │ ...        │ ...         │ ...        │
└──────┴────────────┴─────────────┴────────────┘
```

---

## 6. Data Ingestion

BioAgent can automatically detect, profile, and validate your data files, helping you understand what you have before analysis begins.

### 6.1 Supported Formats

| Category | Formats |
|----------|---------|
| **Sequence** | FASTQ, FASTQ.gz, FASTA, FASTA.gz |
| **Alignment** | BAM, SAM, CRAM |
| **Variant** | VCF, VCF.gz, BCF, MAF |
| **Expression** | h5ad (AnnData), HDF5, MTX, Loom |
| **Annotation** | GTF, GFF3, GFF |
| **Genomic Ranges** | BED, BigWig, BedGraph |
| **Structure** | PDB, mmCIF |
| **Tabular** | CSV, TSV, Excel, Parquet |

### 6.2 Ingesting Files

#### Single File

```
Query: "Ingest my data file at /data/experiment/counts.csv"
```

BioAgent will:
1. Detect the source (local file, URL, S3, GCS)
2. Identify the format (CSV in this case)
3. Generate a profile with statistics
4. Suggest appropriate analyses

#### Multiple Files

```
Query: "Ingest all files in /data/rnaseq/"
```

#### From URLs

```
Query: "Ingest the GTF file from https://ftp.ensembl.org/pub/release-110/gtf/homo_sapiens/Homo_sapiens.GRCh38.110.gtf.gz"
```

#### Pasted Data

```
Query: ">BRCA1_variant
MVLSPADKTNVKAAWGKVGAHAGEYGAEALERMFLSFPTTKTYFPHFDLSH"
```

BioAgent recognizes this as a FASTA sequence and profiles it automatically.

### 6.3 Format-Specific Profiling

Each format receives specialized analysis:

#### FASTQ Files

```
Query: "Profile my sequencing reads at reads_R1.fastq.gz"

Response includes:
- Read count: 10,234,567
- Average length: 150 bp
- GC content: 42.3%
- Mean quality: 35.2 (Phred)
- Detected mate file: reads_R2.fastq.gz
```

#### VCF Files

```
Query: "Assess my variant file variants.vcf.gz"

Response includes:
- Variant count: 1,234,567
- Types: SNV (1.1M), Insertion (80K), Deletion (55K)
- Samples: 3
- PASS rate: 85%
- Warning: Missing tabix index
```

#### CSV/TSV (Tabular Data)

```
Query: "Profile the expression matrix in counts.csv"

Response includes:
- Dimensions: 20,000 genes × 12 samples
- Column types detected
- Data pattern: Expression count matrix
- Suggested analysis: Differential expression
```

### 6.4 Dataset Validation

For multi-file analyses, validate that your dataset is ready:

```
Query: "Validate my RNA-seq dataset: counts.csv and metadata.csv"

Response:
✅ Expression matrix found (20,000 genes × 12 samples)
✅ Sample metadata found (12 samples with condition column)
⚠️ No gene annotation (GTF) — will use gene IDs for enrichment

Ready for differential expression analysis.
```

#### Validation Types

| Type | Checks For |
|------|------------|
| `rnaseq` | Count matrix + metadata + optional GTF |
| `variant` | VCF with variants + optional index |
| `singlecell` | h5ad/MTX/Loom expression data |
| `alignment` | FASTQ pairs + reference genome |

---

## 7. Workflow Management

### 7.1 Nextflow Pipelines

#### Creating a Pipeline

```
Query: "Create a Nextflow pipeline for FastQC quality control of FASTQ files"
```

#### Running a Pipeline

```
Query: "Run my Nextflow pipeline at workflows/rnaseq/main.nf with these parameters:
        reads: 'data/*_{1,2}.fastq.gz'
        genome: 'reference/hg38.fa'"
```

#### Step-by-Step: Complete Nextflow Workflow

```
Step 1: Query to create pipeline
> Create a Nextflow DSL2 pipeline that:
  1. Runs FastQC on input FASTQ files
  2. Trims adapters with Trimmomatic
  3. Aligns with STAR
  4. Counts features with featureCounts

  Save it as 'rnaseq_pipeline'

Step 2: BioAgent creates the pipeline file

Step 3: Query to run it
> Run the rnaseq_pipeline with reads from data/samples/
  and reference genome at ref/hg38/

Step 4: BioAgent executes:
- Validates inputs exist
- Starts Nextflow run
- Returns run ID and status

Step 5: Check progress
> What's the status of my Nextflow run?

Step 6: Get outputs
> Show me the outputs from my completed pipeline
```

### 7.2 Snakemake Workflows

#### Creating a Workflow

```
Query: "Create a Snakemake workflow for variant calling with BWA and GATK"
```

#### Running a Workflow

```
Query: "Run the Snakemake workflow in workflows/variant_calling/Snakefile with 8 cores"
```

### 7.3 WDL Workflows

#### Creating a Workflow

```
Query: "Create a WDL workflow for germline variant calling"
```

### 7.4 Using nf-core Pipelines

nf-core provides production-ready pipelines.

#### List Available Pipelines

```
Query: "What nf-core pipelines are available for RNA-seq analysis?"
```

#### Run nf-core Pipeline

```
Query: "Run the nf-core/rnaseq pipeline with my samplesheet.csv using the test profile"
```

#### Step-by-Step: nf-core RNA-seq

```
Step 1: Prepare samplesheet (CSV format)
sample,fastq_1,fastq_2,strandedness
sample1,data/s1_R1.fastq.gz,data/s1_R2.fastq.gz,auto
sample2,data/s2_R1.fastq.gz,data/s2_R2.fastq.gz,auto

Step 2: Query
> Run nf-core/rnaseq with:
  - input: samplesheet.csv
  - genome: GRCh38
  - aligner: star_salmon
  - outdir: results/rnaseq

Step 3: BioAgent configures and launches the pipeline

Step 4: Monitor progress
> Check the status of my nf-core/rnaseq run
```

---

## 8. Cloud & HPC

### 8.1 AWS Batch

#### Setup Requirements

```bash
# Set in .env file
AWS_ACCESS_KEY_ID=your-key
AWS_SECRET_ACCESS_KEY=your-secret
AWS_DEFAULT_REGION=us-east-1
BIOAGENT_AWS_BATCH_QUEUE=your-queue-name
BIOAGENT_AWS_S3_BUCKET=your-bucket
```

#### Submitting Jobs

```
Query: "Submit a job to AWS Batch that runs FastQC on all FASTQ files in s3://my-bucket/reads/"
```

#### Step-by-Step: AWS Batch Analysis

```
Step 1: Query
> Submit a variant calling job to AWS Batch:
  - Input: s3://my-data/sample.bam
  - Reference: s3://my-data/hg38.fa
  - Use 16 vCPUs and 64GB RAM
  - Use spot instances to save cost

Step 2: BioAgent:
- Creates job definition
- Stages input files
- Submits to AWS Batch

Step 3: Response includes:
- Job ID: abc-123-def
- Queue: bioagent-queue
- Status: SUBMITTED
- Estimated cost: $2.40

Step 4: Monitor
> Check the status of AWS Batch job abc-123-def

Step 5: Get results
> Download results from my completed AWS Batch job
```

### 8.2 Google Cloud

#### Setup Requirements

```bash
GOOGLE_APPLICATION_CREDENTIALS=/path/to/credentials.json
BIOAGENT_GCP_PROJECT=my-project
BIOAGENT_GCP_REGION=us-central1
BIOAGENT_GCS_BUCKET=my-bucket
```

#### Submitting Jobs

```
Query: "Run my analysis on Google Cloud Life Sciences with 32GB RAM"
```

### 8.3 Azure Batch

#### Setup Requirements

```bash
AZURE_BATCH_ACCOUNT=mybatchaccount
AZURE_BATCH_KEY=your-key
AZURE_BATCH_URL=https://mybatchaccount.region.batch.azure.com
AZURE_STORAGE_CONNECTION_STRING=your-connection-string
```

### 8.4 SLURM Clusters

#### Setup Requirements

```bash
BIOAGENT_SLURM_HOST=cluster.example.com
BIOAGENT_SLURM_USER=username
BIOAGENT_SLURM_KEY_FILE=~/.ssh/id_rsa
BIOAGENT_SLURM_PARTITION=compute
```

#### Submitting Jobs

```
Query: "Submit my RNA-seq pipeline to the SLURM cluster using the gpu partition"
```

### 8.5 Cost Management

#### Cost Estimation

```
Query: "How much would it cost to run a job with 16 CPUs and 64GB RAM for 8 hours on AWS vs GCP?"
```

#### Using Spot Instances

```
Query: "Submit my job to AWS using spot instances to minimize cost"
```

---

## 9. Visualization

### 9.1 Publication Figures

Create journal-ready figures.

#### Volcano Plot

```
Query: "Create a Nature-style volcano plot from my DESeq2 results in deg_results.csv"
```

#### Heatmap

```
Query: "Make a publication-quality heatmap of the top 50 differentially expressed genes"
```

#### Step-by-Step: Publication Figure

```
Step 1: Query
> Create a Cell-style figure with 2 panels:
  A) Volcano plot of deg_results.csv
  B) Heatmap of top 20 significant genes
  Label significant genes (padj < 0.01, |log2FC| > 2)
  Save as PDF at 300 DPI

Step 2: BioAgent creates the figure

Step 3: Response includes:
- Figure saved to: figures/figure1.pdf
- Panel A: 245 significant genes highlighted
- Panel B: Clustered heatmap with dendrogram
- Format: Cell journal specifications
```

#### Available Styles

| Style | Journal | Specifications |
|-------|---------|----------------|
| `nature` | Nature | Single column: 89mm, double: 183mm |
| `cell` | Cell | Figure width up to 174mm |
| `science` | Science | Single: 55mm, double: 114mm |
| `pnas` | PNAS | Single: 8.7cm, double: 17.8cm |

### 9.2 Interactive Plots

Create web-based interactive visualizations.

#### Interactive Volcano

```
Query: "Create an interactive volcano plot where I can hover to see gene names"
```

#### Interactive Network

```
Query: "Create an interactive network visualization of the STRING interaction data"
```

### 9.3 Common Plot Types

| Plot Type | Use Case | Query Example |
|-----------|----------|---------------|
| Volcano | Differential expression | "Create volcano plot from DEG results" |
| MA plot | Expression vs fold change | "Make MA plot from DESeq2 output" |
| Heatmap | Expression patterns | "Heatmap of top variable genes" |
| PCA | Sample relationships | "PCA plot colored by treatment" |
| Survival | Clinical outcomes | "Kaplan-Meier plot by risk group" |
| Forest | Meta-analysis | "Forest plot of effect sizes" |
| Manhattan | GWAS | "Manhattan plot of association results" |

---

## 10. Report Generation

### 10.1 Jupyter Notebooks

Generate reproducible analysis notebooks.

#### Basic Notebook

```
Query: "Create a Jupyter notebook documenting my differential expression analysis"
```

#### Step-by-Step: Analysis Notebook

```
Step 1: Query
> Create a Jupyter notebook for RNA-seq analysis that includes:
  - Data loading and QC
  - Normalization
  - Differential expression with DESeq2
  - Visualization (volcano, heatmap)
  - GO enrichment analysis
  - Results summary
  Use my data files: counts.csv, metadata.csv

Step 2: BioAgent generates notebook with:
- Markdown descriptions for each step
- Code cells with your data paths
- Placeholder outputs
- Bibliography section

Step 3: Response:
Notebook saved to: reports/rnaseq_analysis.ipynb

To run: jupyter notebook reports/rnaseq_analysis.ipynb
```

### 10.2 R Markdown Reports

Generate HTML or PDF reports.

#### HTML Report

```
Query: "Create an R Markdown report of my variant analysis with HTML output"
```

#### PDF Report

```
Query: "Generate a PDF report of my single-cell analysis results"
```

### 10.3 Dashboards

Create interactive data exploration apps.

#### Streamlit Dashboard

```
Query: "Create a Streamlit dashboard for exploring my gene expression data"
```

#### Dash Dashboard

```
Query: "Build a Dash app for interactive visualization of my results"
```

#### Step-by-Step: Interactive Dashboard

```
Step 1: Query
> Create a Streamlit dashboard that allows users to:
  - Select genes from a dropdown
  - View expression across samples
  - Compare between treatment groups
  - Download filtered results
  Use the expression data in results/expression.csv

Step 2: BioAgent generates dashboard code

Step 3: Response:
Dashboard saved to: dashboards/expression_explorer.py

To run: streamlit run dashboards/expression_explorer.py

Step 4: Open http://localhost:8501 in browser
```

---

## 11. Memory System

### 11.1 Searching Past Analyses

Find relevant information from previous work.

```
Query: "Search my memory for previous analyses involving BRCA1"
```

```
Query: "What did I find out about drug resistance in my earlier analysis?"
```

#### Step-by-Step: Using Memory

```
Step 1: Do an analysis
> Analyze the TP53 pathway and its role in cancer

Step 2: Later, recall it
> What did I learn about TP53 before?

Step 3: BioAgent searches memory and returns:
- Previous analysis summary
- Key findings
- Related artifacts saved
```

### 11.2 Saving Artifacts

Save important results for later use.

```
Query: "Save my current DEG results as an artifact for future reference"
```

```
Query: "List all artifacts I've saved"
```

```
Query: "Retrieve my saved biomarker panel"
```

### 11.3 Knowledge Graph

Track entities and relationships discovered during analyses.

```
Query: "What genes have I studied that are related to DNA repair?"
```

```
Query: "Show me all relationships I've found for TP53"
```

---

## 12. Workspace & Analysis Tracking

BioAgent tracks your analyses with unique IDs and organizes results into projects for easy retrieval and reproducibility.

### 12.1 Starting an Analysis

```
Query: "Start a new analysis for my RNA-seq differential expression study"

Response:
Started analysis: BIO-20250205-001
Title: RNA-seq Differential Expression
Type: differential_expression

All outputs will be tracked under this ID.
```

BioAgent automatically:
- Generates a unique ID (e.g., `BIO-20250205-001`)
- Creates a workspace directory
- Tracks all inputs and outputs
- Records which tools were used

### 12.2 Managing Projects

Group related analyses into projects:

```
Query: "Create a new project called 'Cancer Study 2025'"

Response:
Created project: cancer-study-2025
Directory: workspace/projects/cancer-study-2025/
```

#### Add Analysis to Project

```
Query: "Add my current analysis to the cancer-study-2025 project"
```

#### List Project Analyses

```
Query: "Show all analyses in the cancer-study-2025 project"

Response:
Project: cancer-study-2025
Analyses:
┌────────────────────┬────────────────────────┬───────────┬─────────────┐
│ ID                 │ Title                  │ Status    │ Date        │
├────────────────────┼────────────────────────┼───────────┼─────────────┤
│ BIO-20250205-001   │ RNA-seq DE Analysis    │ completed │ 2025-02-05  │
│ BIO-20250205-002   │ Pathway Enrichment     │ completed │ 2025-02-05  │
│ BIO-20250206-001   │ Variant Analysis       │ running   │ 2025-02-06  │
└────────────────────┴────────────────────────┴───────────┴─────────────┘
```

### 12.3 Finding Past Work

#### Search by Keyword

```
Query: "Find my analyses involving BRCA1"
```

#### Search by Type

```
Query: "List all my differential expression analyses"
```

#### Get Analysis Details

```
Query: "Show details for analysis BIO-20250205-001"

Response:
Analysis: BIO-20250205-001
Title: RNA-seq Differential Expression
Status: completed
Project: cancer-study-2025

Inputs:
- counts.csv (expression_matrix)
- metadata.csv (sample_metadata)

Outputs:
- deg_results.csv (de_results)
- volcano_plot.pdf (figure)

Tools Used: execute_r, create_plot
Summary: Found 1,234 DEGs (FDR < 0.05)
```

### 12.4 Directory Structure

```
workspace/projects/
├── cancer-study-2025/
│   ├── PROJECT_MANIFEST.json
│   ├── analyses/
│   │   ├── BIO-20250205-001/
│   │   │   ├── ANALYSIS_MANIFEST.json
│   │   │   ├── inputs/
│   │   │   ├── outputs/
│   │   │   ├── reports/
│   │   │   └── logs/
│   │   └── BIO-20250205-002/
│   │       └── ...
│   └── data/
└── registry/
    ├── analyses.json
    ├── projects.json
    └── files.json
```

---

## 13. Multi-Agent Mode

### 13.1 When to Use Multi-Agent

Enable multi-agent mode for complex tasks requiring multiple specialties:

```bash
# Enable in environment
export BIOAGENT_MULTI_AGENT=true
```

Or in Python:
```python
config.enable_multi_agent = True
```

**Good use cases:**
- Complex multi-step analyses
- Tasks requiring both code and literature
- Quality control with domain interpretation

### 13.2 Understanding Specialists

| Specialist | Role | Tools | Best For |
|------------|------|-------|----------|
| **Pipeline Engineer** | Code & workflows | 40 | Running analyses, creating pipelines |
| **Statistician** | Statistical analysis | 21 | DE analysis, enrichment, ML |
| **Literature Agent** | Database queries | 20 | Gene info, pathways, literature |
| **QC Reviewer** | Quality control | 8 | Validating results, checking data |
| **Domain Expert** | Biological interpretation | 18 | Making sense of results |

#### Example: Multi-Agent Analysis

```
Query: "Analyze my RNA-seq data, find differentially expressed genes,
        identify enriched pathways, and provide biological interpretation"

With multi-agent enabled:

1. Coordinator receives query

2. Routes to specialists:
   - Pipeline Engineer: Loads data, runs normalization
   - Statistician: Runs DESeq2, finds DEGs
   - Literature Agent: Queries pathway databases
   - Domain Expert: Interprets biological meaning

3. Coordinator synthesizes final response
```

---

## 14. Complete Tutorials

### 14.1 Tutorial 1: Gene Investigation

**Goal:** Comprehensively investigate a gene of interest

```
Step 1: Start BioAgent
$ python run.py

Step 2: Initial query
> I want to investigate the KRAS gene. Give me a comprehensive overview.

Step 3: BioAgent provides:
- Gene location, aliases
- Protein function
- Key pathways
- Known mutations
- Disease associations

Step 4: Dive deeper
> What are the most common KRAS mutations in cancer and their frequencies?

Step 5: Get structural info
> Show me the KRAS protein structure and highlight the G12 mutation site

Step 6: Find interactions
> What proteins interact with KRAS? Focus on high-confidence interactions.

Step 7: Check therapeutics
> What drugs target KRAS or its pathway?

Step 8: Literature search
> Find recent papers about KRAS inhibitors

Step 9: Create summary
> Create a summary report of everything we've learned about KRAS
```

### 14.2 Tutorial 2: RNA-seq Analysis

**Goal:** Complete differential expression analysis from raw counts

```
Step 1: Prepare your data
- counts.csv: Gene expression counts (genes x samples)
- metadata.csv: Sample information with conditions

Step 2: Start analysis
> I have RNA-seq count data in counts.csv with metadata in metadata.csv.
  The groups are 'tumor' and 'normal' in the 'condition' column.
  Perform differential expression analysis.

Step 3: BioAgent runs DESeq2 analysis

Step 4: Explore results
> How many genes are significantly differentially expressed (FDR < 0.05)?

Step 5: Visualize
> Create a volcano plot highlighting the top 20 genes by significance

Step 6: Pathway analysis
> What pathways are enriched in the upregulated genes?

Step 7: Create figures
> Make publication-ready figures: volcano plot and heatmap of top 50 DEGs

Step 8: Generate report
> Create a Jupyter notebook documenting this entire analysis
```

### 14.3 Tutorial 3: Variant Interpretation

**Goal:** Interpret clinical significance of genetic variants

```
Step 1: Start with variants
> I have these variants from a patient:
  - TP53: c.743G>A (p.Arg248Gln)
  - BRCA2: c.5946delT
  - PIK3CA: c.3140A>G (p.His1047Arg)

Step 2: Get pathogenicity scores
> Predict the pathogenicity of each variant using CADD, REVEL, and AlphaMissense

Step 3: Check population frequency
> What are the gnomAD frequencies for these variants?

Step 4: Literature search
> Search for clinical reports on these specific variants

Step 5: Drug implications
> Based on these mutations, what targeted therapies might be relevant?

Step 6: Structural impact
> Show me how the TP53 R248Q mutation affects protein structure

Step 7: Create report
> Generate a clinical-style variant interpretation report
```

### 14.4 Tutorial 4: Single-Cell Analysis

**Goal:** Analyze single-cell RNA-seq data

```
Step 1: Load data
> Load the single-cell data from pbmc_3k.h5ad and show me basic QC metrics

Step 2: Quality control
> Filter cells with:
  - Minimum 200 genes detected
  - Maximum 5% mitochondrial content
  - Remove doublets

Step 3: Normalize and process
> Normalize the data, find highly variable genes, run PCA and UMAP

Step 4: Cluster
> Cluster the cells using Leiden algorithm at resolution 0.5

Step 5: Annotate cell types
> Annotate cell types using CellTypist with the immune model

Step 6: Find markers
> Find marker genes for each cell type cluster

Step 7: Visualize
> Create a UMAP plot colored by cell type and a dot plot of top markers

Step 8: Compare populations
> Compare gene expression between CD4+ and CD8+ T cells

Step 9: Create report
> Generate a complete analysis report with all figures
```

---

## 15. Best Practices

### Query Formulation

**Be specific:**
```
Bad:  "Tell me about TP53"
Good: "Get UniProt protein information for human TP53 including domains and PTMs"
```

**Provide context:**
```
Bad:  "Analyze my data"
Good: "Analyze the differential expression data in results.csv, where column 'log2FC'
       contains fold changes and 'padj' contains adjusted p-values"
```

**Break complex tasks into steps:**
```
Good: "First, load the expression data. Then normalize it. Finally, run PCA."
```

### Data Organization

```
project/
├── data/
│   ├── raw/           # Original data files
│   ├── processed/     # Processed/normalized data
│   └── metadata/      # Sample information
├── results/           # Analysis outputs
├── figures/           # Generated plots
├── reports/           # Notebooks and reports
└── workflows/         # Pipeline files
```

### Reproducibility

1. **Use workflows** for multi-step analyses
2. **Save artifacts** for important intermediate results
3. **Generate notebooks** to document your analysis
4. **Record parameters** used for each analysis

### Cost Optimization

1. **Use Sonnet** for routine queries (cheaper, faster)
2. **Reserve Opus** for complex reasoning
3. **Enable caching** in memory system
4. **Use spot instances** for cloud jobs
5. **Batch similar queries** together

---

## 16. Troubleshooting

### Common Issues

#### "ANTHROPIC_API_KEY not set"

```bash
# Solution: Set the environment variable
export ANTHROPIC_API_KEY="sk-ant-your-key-here"
# Or add to .env file
```

#### "NCBI rate limit exceeded"

```bash
# Solution: Add NCBI API key for higher limits
export NCBI_API_KEY="your-ncbi-key"
```

#### "Tool execution error"

```
# Check that required packages are installed
pip install pandas numpy scipy scikit-learn matplotlib seaborn

# For R tools, ensure R is installed and in PATH
```

#### "Workflow engine not found"

```bash
# For Nextflow
curl -s https://get.nextflow.io | bash

# For Snakemake
pip install snakemake

# For WDL (requires WSL on Windows)
pip install miniwdl
```

#### "Memory system error"

```
# Memory falls back to simple mode automatically
# For full features, ensure sentence-transformers is installed
pip install sentence-transformers
```

### Getting Help

1. **Check documentation:** `docs/` directory
2. **GitHub Issues:** Report bugs or request features
3. **Cloud setup:** See `docs/cloud-setup.md`

### Debug Mode

Run with verbose output:

```bash
export BIOAGENT_VERBOSE=true
python run.py
```

This shows all tool calls and their results for debugging.

---

## Quick Reference

### Essential Commands

```bash
# Interactive mode
python run.py

# Single query
python run.py --query "Your question"

# Complex analysis
python run.py --complex "Complex task"
```

### Common Queries

| Task | Query |
|------|-------|
| Gene info | "Get information about [GENE] from UniProt" |
| Pathways | "What pathways involve [GENE]?" |
| Variants | "Check gnomAD for [VARIANT]" |
| Literature | "Find papers about [TOPIC]" |
| Interactions | "Find proteins that interact with [PROTEIN]" |
| Structure | "Get AlphaFold structure for [PROTEIN]" |
| DE analysis | "Find differentially expressed genes in [FILE]" |
| Pathogenicity | "Predict pathogenicity of [VARIANT]" |
| Visualization | "Create [TYPE] plot from [DATA]" |

---

*Last updated: February 2025*
*BioAgent v1.1*
