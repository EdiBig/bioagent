# 🧬 BioAgent

An AI-powered bioinformatics assistant that combines Claude's reasoning capabilities with computational tools for expert-level genomics, transcriptomics, and biological data analysis.

## What It Does

BioAgent is an **agentic system** — not just a chatbot. When you give it a task, it:

1. **Reasons** about the biological question and experimental design
2. **Plans** an analysis workflow with appropriate methods
3. **Executes** code (Python, R, Bash) to run bioinformatics tools
4. **Queries** biological databases (NCBI, Ensembl) for annotation and context
5. **Iterates** — checking outputs, debugging errors, refining results
6. **Interprets** findings with biological context and statistical rigour

All through natural language conversation.

## Quick Start

### 1. Install

```bash
# Clone/download the project
cd bioagent

# Install the one required dependency
pip install anthropic

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

### 3. Example Interaction

```
You: I have a gene list from a differential expression analysis. The top hits are
     TP53, BRCA1, CDK2, CCND1, RB1, E2F1, and MDM2. What pathways are enriched
     and what's the biological story here?

BioAgent: [Queries NCBI Gene for each gene]
          [Runs pathway enrichment analysis in Python]
          [Cross-references with KEGG and Reactome]

          Your gene list is strongly enriched for cell cycle regulation and the
          p53 signalling pathway. Here's the biological narrative...
```

## Architecture

```
┌─────────────────────────────────────────────────┐
│                   User Query                     │
└─────────────────┬───────────────────────────────┘
                  ▼
┌─────────────────────────────────────────────────┐
│              Claude (Anthropic API)               │
│  ┌──────────────────────────────────────────┐   │
│  │  System Prompt: Deep bioinformatics      │   │
│  │  expertise, SOPs, best practices         │   │
│  └──────────────────────────────────────────┘   │
│                                                   │
│  Reasons → Selects Tool → Reads Result → Repeats │
└────────┬──────┬──────┬──────┬──────┬────────────┘
         │      │      │      │      │
    ┌────┘  ┌───┘  ┌───┘  ┌───┘  ┌──┘
    ▼       ▼      ▼      ▼      ▼
┌──────┐┌──────┐┌──────┐┌──────┐┌──────┐
│Python││  R   ││ Bash ││ NCBI ││Ensembl│
│      ││      ││      ││      ││      │
│pandas││DESeq2││STAR  ││Gene  ││VEP   │
│scipy ││edgeR ││bwa   ││PubMed││Lookup │
│scanpy││limma ││samtools│     ││Homol. │
└──────┘└──────┘└──────┘└──────┘└──────┘
```

## Configuration

Copy `.env.example` to `.env` and fill in your values:

```bash
cp .env.example .env
```

| Variable | Required | Description |
|---|---|---|
| `ANTHROPIC_API_KEY` | ✅ | Your Anthropic API key |
| `NCBI_EMAIL` | Recommended | Email for NCBI E-utilities |
| `NCBI_API_KEY` | Optional | NCBI API key (higher rate limits) |
| `BIOAGENT_MODEL` | Optional | Model override (default: claude-sonnet-4-20250514) |
| `BIOAGENT_WORKSPACE` | Optional | Working directory (default: /workspace) |
| `BIOAGENT_USE_DOCKER` | Optional | Run tools in Docker (default: false) |

## Docker Setup (Optional but Recommended)

For a fully sandboxed environment with all bioinformatics tools pre-installed:

```bash
# Build the tools container
docker build -t bioagent-tools -f Dockerfile.biotools .

# Enable Docker execution
echo "BIOAGENT_USE_DOCKER=true" >> .env

# Now the agent will execute code inside the container
python run.py
```

This gives you samtools, STAR, BWA, GATK, DESeq2, and dozens more tools without polluting your local environment.

## Programmatic Usage

```python
from bioagent import BioAgent, Config

# Default config from environment
agent = BioAgent()

# Or custom config
config = Config(
    anthropic_api_key="sk-ant-...",
    workspace_dir="./my_analysis",
    model="claude-sonnet-4-20250514",
)
agent = BioAgent(config=config)

# Run a query
result = agent.run("Analyse the VCF file at /data/variants.vcf and summarise the variant landscape")

# Use the advanced model for complex tasks
result = agent.run(
    "Design a batch-corrected multi-centre RNA-seq pipeline",
    use_complex_model=True
)

# Save/load sessions for continuity
agent.save_session("session_2024.json")
agent.load_session("session_2024.json")
```

## Project Structure

```
bioagent/
├── run.py                     # CLI entry point
├── .env.example               # Configuration template
├── requirements.txt           # Python dependencies
├── Dockerfile.biotools        # Bioinformatics tools container
└── bioagent/
    ├── __init__.py
    ├── agent.py               # Core agentic loop
    ├── config.py              # Configuration management
    ├── prompts/
    │   └── system.py          # Domain expertise & SOPs
    └── tools/
        ├── definitions.py     # Tool schemas for Claude API
        ├── code_executor.py   # Python/R/Bash execution
        ├── ncbi.py            # NCBI E-utilities client
        ├── ensembl.py         # Ensembl REST API client
        └── file_manager.py    # File I/O operations
```

## Extending BioAgent

### Adding New Tools

1. Define the tool schema in `tools/definitions.py`
2. Implement the handler in a new module under `tools/`
3. Add the routing logic in `agent.py → _execute_tool()`

### Specialising the System Prompt

Edit `prompts/system.py` to add:
- Lab-specific SOPs and protocols
- Preferred tools and parameter defaults
- Reference genome paths and annotation versions
- Custom analysis templates

### Upgrading to Multi-Agent

The system prompt file already includes specialist sub-prompts (`PIPELINE_ENGINEER_PROMPT`, `STATISTICIAN_PROMPT`, etc.) ready for Phase 2. When you're ready to split into multiple agents, each specialist gets its own `BioAgent` instance with its own system prompt and tool subset, orchestrated by a coordinator agent.

## Cost Estimates

| Usage Level | Model | Approximate Monthly Cost |
|---|---|---|
| Light (5-10 queries/day) | Sonnet | £20-40 |
| Moderate (20-30 queries/day) | Sonnet | £60-120 |
| Heavy / Complex analyses | Sonnet + Opus | £100-200 |

Most routine work (running pipelines, querying databases, writing scripts) works excellently on Sonnet. Reserve Opus for complex biological interpretation, experimental design review, and multi-step reasoning.

## Licence

MIT
