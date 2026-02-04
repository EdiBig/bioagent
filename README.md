# 🧬 BioAgent

An AI-powered bioinformatics assistant that combines Claude's reasoning capabilities with computational tools for expert-level genomics, transcriptomics, and biological data analysis.

## What It Does

BioAgent is an **agentic system** — not just a chatbot. When you give it a task, it:

1. **Reasons** about the biological question and experimental design
2. **Plans** an analysis workflow with appropriate methods
3. **Executes** code (Python, R, Bash) to run bioinformatics tools
4. **Queries** 11+ biological databases for annotation and context
5. **Searches** the web for documentation, tutorials, and latest research
6. **Runs** workflow engines (Nextflow, Snakemake, WDL) for reproducible pipelines
7. **Iterates** — checking outputs, debugging errors, refining results
8. **Saves** all results automatically for reproducibility

All through natural language conversation.

## Features

### 🗄️ Database Integrations

| Database | Description | Tool |
|----------|-------------|------|
| **NCBI** | Genes, sequences, literature (PubMed) | `query_ncbi` |
| **Ensembl** | Genomic annotations, variants, comparative genomics | `query_ensembl` |
| **UniProt** | Protein sequences, annotations, functional data | `query_uniprot` |
| **KEGG** | Pathways, genes, compounds, diseases | `query_kegg` |
| **STRING** | Protein-protein interactions | `query_string` |
| **PDB** | 3D protein structures | `query_pdb` |
| **AlphaFold** | AI-predicted protein structures | `query_alphafold` |
| **InterPro** | Protein domains and families | `query_interpro` |
| **Reactome** | Biological pathways | `query_reactome` |
| **Gene Ontology** | GO terms, gene annotations | `query_go` |
| **gnomAD** | Population variant frequencies | `query_gnomad` |

### 🔄 Workflow Engines

| Engine | Description | Status |
|--------|-------------|--------|
| **Nextflow** | DSL2 workflows for scalable pipelines | ✅ Supported |
| **Snakemake** | Rule-based workflow management | ✅ Supported |
| **WDL/miniwdl** | Workflow Description Language | ✅ Supported (via WSL on Windows) |

### 🔍 Web Search

- Search documentation, tutorials, and papers
- Find troubleshooting solutions
- Look up latest research and methods
- No API key required (uses DuckDuckGo)

### 💾 Auto-Save Results

- All query results automatically saved to markdown files
- Includes timestamp, query, tools used, and full response
- Stored in `<workspace>/results/` directory

## Quick Start

### 1. Install

```bash
# Clone the repository
git clone https://github.com/EdiBig/bioagent.git
cd bioagent

# Install dependencies
pip install anthropic ddgs

# Set your API key
export ANTHROPIC_API_KEY="sk-ant-your-key-here"
```

### 2. Run

```bash
# Interactive chat mode
python run.py

# Single query mode
python run.py --query "What genes are associated with BRCA1 and what pathways are they involved in?"

# Complex analysis (uses the more powerful model)
python run.py --complex "Design a complete RNA-seq analysis pipeline for a 3-centre study with batch effects"
```

### 3. Example Queries

```bash
# Database queries
python run.py --query "Get protein info for TP53 from UniProt and find its interaction partners in STRING"

# Pathway analysis
python run.py --query "What pathways is BRCA1 involved in? Check Reactome and KEGG"

# Variant analysis
python run.py --query "Look up the gnomAD frequency for the BRCA1 gene"

# Web search
python run.py --query "Search the web for the latest DESeq2 tutorial for RNA-seq analysis"

# Combined analysis
python run.py --query "For gene MDM2: get protein info from UniProt, find pathways in KEGG, and get interaction partners from STRING"
```

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                         User Query                               │
└─────────────────────────┬───────────────────────────────────────┘
                          ▼
┌─────────────────────────────────────────────────────────────────┐
│                    Claude (Anthropic API)                        │
│  ┌────────────────────────────────────────────────────────────┐ │
│  │  System Prompt: Deep bioinformatics expertise, SOPs        │ │
│  └────────────────────────────────────────────────────────────┘ │
│                                                                  │
│     Reasons → Selects Tool → Reads Result → Iterates            │
└──────┬──────┬──────┬──────┬──────┬──────┬──────┬───────────────┘
       │      │      │      │      │      │      │
  ┌────┘  ┌───┘  ┌───┘  ┌───┘  ┌───┘  ┌───┘  ┌───┘
  ▼       ▼      ▼      ▼      ▼      ▼      ▼
┌─────┐┌─────┐┌─────┐┌─────┐┌─────┐┌─────┐┌─────┐
│Code ││Data-││Work-││Files││Web  ││  11 ││Auto │
│Exec ││bases││flows││     ││Search│Databases│Save│
│     ││     ││     ││     ││     ││     ││     │
│Py/R/││NCBI ││Next-││Read ││DDG  ││UniProt│Results│
│Bash ││Ensem││flow ││Write││     ││KEGG  ││     │
│     ││etc  ││Snake││List ││     ││STRING││     │
└─────┘└─────┘└─────┘└─────┘└─────┘└─────┘└─────┘
```

## Configuration

Create a `.env` file in the project root:

```bash
# Required
ANTHROPIC_API_KEY=sk-ant-your-key-here

# Recommended
NCBI_EMAIL=your.email@example.com
NCBI_API_KEY=your_ncbi_key

# Optional
BIOAGENT_MODEL=claude-sonnet-4-20250514
BIOAGENT_WORKSPACE=/path/to/workspace
BIOAGENT_VERBOSE=true
BIOAGENT_AUTO_SAVE=true
BIOAGENT_RESULTS_DIR=results
```

### Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `ANTHROPIC_API_KEY` | ✅ | - | Your Anthropic API key |
| `NCBI_EMAIL` | Recommended | - | Email for NCBI E-utilities |
| `NCBI_API_KEY` | Optional | - | NCBI API key (higher rate limits) |
| `BIOAGENT_MODEL` | Optional | `claude-sonnet-4-20250514` | Default model |
| `BIOAGENT_MODEL_COMPLEX` | Optional | `claude-opus-4-0-20250115` | Model for complex queries |
| `BIOAGENT_WORKSPACE` | Optional | `~/bioagent_workspace` (Win) or `/workspace` (Linux) | Working directory |
| `BIOAGENT_VERBOSE` | Optional | `true` | Show tool calls |
| `BIOAGENT_AUTO_SAVE` | Optional | `true` | Auto-save results |
| `BIOAGENT_RESULTS_DIR` | Optional | `results` | Results subdirectory |
| `BIOAGENT_USE_DOCKER` | Optional | `false` | Run tools in Docker |
| `BIOAGENT_MAX_ROUNDS` | Optional | `25` | Max tool iterations |

## Project Structure

```
bioagent/
├── run.py                 # CLI entry point
├── agent.py               # Core agentic loop
├── config.py              # Configuration management
├── system.py              # System prompt with domain expertise
├── definitions.py         # Tool schemas for Claude API
├── code_executor.py       # Python/R/Bash execution
├── file_manager.py        # File I/O operations
├── web_search.py          # Web search client
│
├── # Database Clients
├── ncbi.py                # NCBI E-utilities
├── ensembl.py             # Ensembl REST API
├── uniprot.py             # UniProt REST API
├── kegg.py                # KEGG REST API
├── string_db.py           # STRING database API
├── pdb.py                 # PDB/RCSB API
├── alphafold.py           # AlphaFold DB API
├── interpro.py            # InterPro API
├── reactome.py            # Reactome API
├── gene_ontology.py       # Gene Ontology API
├── gnomad.py              # gnomAD GraphQL API
│
├── # Workflow Engines
└── workflows/
    ├── __init__.py
    ├── base.py            # Base classes
    ├── manager.py         # Unified workflow manager
    ├── nextflow.py        # Nextflow engine
    ├── snakemake.py       # Snakemake engine
    └── wdl.py             # WDL/miniwdl engine
```

## Programmatic Usage

```python
from agent import BioAgent
from config import Config

# Default config from environment
agent = BioAgent()

# Or custom config
config = Config(
    anthropic_api_key="sk-ant-...",
    workspace_dir="./my_analysis",
    model="claude-sonnet-4-20250514",
    auto_save_results=True,
)
agent = BioAgent(config=config)

# Run a query
result = agent.run("Analyse the VCF file at /data/variants.vcf")

# Use the advanced model for complex tasks
result = agent.run(
    "Design a batch-corrected multi-centre RNA-seq pipeline",
    use_complex_model=True
)

# Save/load sessions
agent.save_session("session.json")
agent.load_session("session.json")
```

## Workflow Engine Usage

### Nextflow

```python
from workflows import WorkflowManager

wm = WorkflowManager(workspace_dir="./workspace")

# Check installation
status = wm.check_engines()
print(status)  # {'nextflow': (True, 'Nextflow 25.10.3 is installed'), ...}

# Create a workflow
result = wm.create_workflow(
    engine="nextflow",
    name="my_pipeline",
    definition="""
    nextflow.enable.dsl=2

    process HELLO {
        output: stdout
        script: "echo Hello World"
    }

    workflow {
        HELLO()
    }
    """,
)

# Run the workflow
result = wm.run_workflow(engine="nextflow", workflow_path=result.outputs["workflow_path"])
```

### Snakemake

```python
result = wm.create_workflow(
    engine="snakemake",
    name="my_pipeline",
    definition="""
    rule all:
        input: "output.txt"

    rule hello:
        output: "output.txt"
        shell: "echo 'Hello World' > {output}"
    """,
)
```

## Windows Notes

- **Snakemake**: Works natively on Windows
- **Nextflow**: Requires WSL (Windows Subsystem for Linux) with Java installed
- **WDL/miniwdl**: Requires WSL with miniwdl installed (`pip3 install --user miniwdl`)

To set up WSL:
```powershell
wsl --install -d Ubuntu
```

Then in WSL:
```bash
sudo apt update && sudo apt install -y default-jdk
pip3 install --user miniwdl
```

## Docker Setup (Optional)

For a fully sandboxed environment:

```bash
# Build the tools container
docker build -t bioagent-tools -f Dockerfile.biotools .

# Enable Docker execution
echo "BIOAGENT_USE_DOCKER=true" >> .env
```

## Cost Estimates

| Usage Level | Model | Approximate Monthly Cost |
|-------------|-------|--------------------------|
| Light (5-10 queries/day) | Sonnet | $20-40 |
| Moderate (20-30 queries/day) | Sonnet | $60-120 |
| Heavy / Complex analyses | Sonnet + Opus | $100-200 |

Most routine work works excellently on Sonnet. Reserve Opus for complex biological interpretation and multi-step reasoning.

## Extending BioAgent

### Adding New Database Clients

1. Create a new module (e.g., `mydb.py`) following the pattern of existing clients
2. Define a result dataclass with `to_string()` method
3. Add the tool schema in `definitions.py`
4. Add routing logic in `agent.py → _execute_tool()`
5. Initialize the client in `agent.py → __init__()`

### Adding New Workflow Engines

1. Create a new engine class in `workflows/` extending `WorkflowEngine`
2. Implement required methods: `check_installation`, `create_workflow`, `run_workflow`, etc.
3. Register in `workflows/manager.py`

## License

MIT
