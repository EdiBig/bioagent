# Research Agent — Architecture & Integration Blueprint

## Executive Summary

The Research Agent is a postdoctoral-level AI research specialist designed to integrate into the BioAgent multi-agent system. It receives findings from other agents (Pipeline Engineer, Statistical/ML, Literature & Database), conducts deep literature-backed research, produces publication-quality reports with proper citations, and generates presentation decks with data visualisations.

---

## 1. Agent Identity & Persona

The Research Agent operates as a **Senior Postdoctoral Researcher** with:

- **Study Coordination**: Decomposes any research topic into structured sections, plans the analysis flow, and coordinates which sub-investigations each agent should perform
- **Literature Mastery**: Searches multiple scientific databases simultaneously, identifies seminal papers, tracks citation networks, and synthesises findings across sources
- **Critical Analysis**: Evaluates evidence quality, identifies gaps in existing literature, assesses statistical rigour, and provides balanced interpretations
- **Report Writing**: Produces structured academic reports with proper in-text citations and formatted reference lists in any standard style (APA, Vancouver, Nature, Harvard, IEEE)
- **Presentation Design**: Generates PowerPoint decks with charts, figures, and visual layouts suitable for lab meetings, conferences, or stakeholder briefings
- **Advisory Role**: Provides evidence-based recommendations to other agents in the system, suggesting methodological improvements or alternative analytical approaches

---

## 2. System Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    ORCHESTRATOR AGENT (PI)                       │
│                                                                 │
│  Receives user query → decomposes → routes to specialists       │
│  Collects results → sends to Research Agent for synthesis        │
└──────────┬──────────────────────────────────────────────────────┘
           │
           ├── Pipeline Engineer Agent ──→ analysis results
           ├── Statistical / ML Agent ──→ statistical outputs
           ├── Literature & DB Agent ──→ database annotations
           │
           └── RESEARCH AGENT (Postdoc) ◄── receives all outputs
               │
               ├── 1. Study Planning Workflow
               │   ├── Topic decomposition
               │   ├── Section planning
               │   ├── Analysis flow design
               │   └── Agent task delegation suggestions
               │
               ├── 2. Literature Engine
               │   ├── PubMed (NCBI E-utilities)
               │   ├── Europe PMC (full-text, citations)
               │   ├── Semantic Scholar (citation graphs, recommendations)
               │   ├── CrossRef (DOI resolution, metadata)
               │   ├── bioRxiv / medRxiv (preprints)
               │   ├── Unpaywall (open access PDF links)
               │   └── LiteratureSearchOrchestrator (unified multi-source)
               │
               ├── 3. Citation Manager
               │   ├── In-text citations (numbered or author-year)
               │   ├── Reference list formatting
               │   ├── Style support (APA, Vancouver, Nature, Harvard, IEEE)
               │   ├── BibTeX export
               │   └── Deduplication & validation
               │
               ├── 4. Report Generator
               │   ├── Structured sections (Abstract → Conclusion)
               │   ├── Markdown + DOCX output
               │   ├── Integrated citations & reference list
               │   ├── Figures & tables
               │   └── Supplementary materials
               │
               ├── 5. Presentation Generator
               │   ├── PptxGenJS-based slide creation
               │   ├── Charts (bar, line, pie, scatter)
               │   ├── Data visualisation integration
               │   ├── Template system (academic, clinical, conference)
               │   └── Speaker notes generation
               │
               └── 6. Inter-Agent Communication
                   ├── Advisory messages to other agents
                   ├── Methodology recommendations
                   ├── Evidence summaries for Orchestrator
                   └── Quality assessment reports
```

---

## 3. Directory Structure

```
research_agent/
├── __init__.py                      # Package init, exports ResearchAgent
├── agent.py                         # Main Research Agent class
├── config.py                        # Configuration & API keys
├── prompts/
│   └── system.py                    # Postdoc persona system prompt
│
├── literature/
│   ├── __init__.py
│   ├── clients.py                   # All API clients (PubMed, Semantic Scholar, etc.)
│   └── orchestrator.py              # Multi-source search coordination
│
├── citations/
│   ├── __init__.py
│   ├── manager.py                   # Citation tracking & deduplication
│   └── styles.py                    # APA, Vancouver, Nature, Harvard, IEEE formatters
│
├── reports/
│   ├── __init__.py
│   ├── generator.py                 # Report assembly engine
│   ├── sections.py                  # Section templates (intro, methods, results, etc.)
│   └── templates/                   # Report templates (review, case study, methods paper)
│
├── presentations/
│   ├── __init__.py
│   ├── generator.py                 # PPTX generation via PptxGenJS
│   ├── charts.py                    # Chart/figure generation helpers
│   └── templates/                   # Slide templates (academic, clinical, conference)
│
├── workflows/
│   ├── __init__.py
│   ├── study_planner.py             # Study decomposition & planning
│   ├── deep_research.py             # Multi-phase research workflow
│   └── evidence_synthesis.py        # Cross-source evidence grading
│
├── inter_agent/
│   ├── __init__.py
│   ├── advisor.py                   # Advisory message generation
│   ├── protocols.py                 # Message schemas for agent communication
│   └── quality_reviewer.py          # Reviews other agents' outputs
│
└── tools/
    ├── __init__.py
    └── definitions.py               # Tool schemas for Claude API tool_use
```

---

## 4. Scientific Literature APIs

### 4.1 Available Free APIs (No API Key Required)

| API | Coverage | Rate Limit | Best For |
|-----|----------|------------|----------|
| **PubMed (E-utilities)** | 36M+ biomedical articles | 3/sec (10/sec with key) | Biomedical literature, MeSH-indexed search |
| **Europe PMC** | 44M+ articles, full-text for OA | 10/sec | Full-text search, citation data, preprints |
| **Semantic Scholar** | 200M+ papers, all fields | 100/sec (free tier) | Citation graphs, influential citations, recommendations |
| **CrossRef** | 150M+ DOIs | Polite pool (unlimited) | DOI resolution, reference metadata, cited-by |
| **bioRxiv/medRxiv** | 250K+ preprints | Reasonable | Latest preprints before peer review |
| **Unpaywall** | 30M+ OA articles | 100K/day | Finding open access PDFs |

### 4.2 Optional Premium APIs

| API | Purpose | Cost |
|-----|---------|------|
| **Semantic Scholar Academic Graph** | Bulk data, embedding search | Free (with API key for higher limits) |
| **OpenAlex** | 250M+ works, fully open | Free, no key needed |
| **Elsevier (ScienceDirect)** | Full-text Elsevier articles | Institutional API key |
| **Springer Nature** | Full-text Springer articles | Institutional API key |
| **CORE** | 300M+ OA articles, full-text | Free API key |

### 4.3 Recommended Priority

For the BioAgent system, implement in this order:
1. **PubMed** — essential for biomedical work (you already have a basic NCBI client)
2. **Semantic Scholar** — citation graph analysis, paper recommendations
3. **CrossRef** — DOI resolution, accurate reference metadata
4. **Europe PMC** — full-text search, broader coverage
5. **bioRxiv** — latest preprints
6. **Unpaywall** — find open access PDFs

---

## 5. Tool Definitions (Claude API tool_use)

The Research Agent exposes **14 tools** to the Claude API:

### Literature Tools
1. `search_literature` — Multi-source literature search
2. `get_paper_details` — Full metadata for a specific paper (by DOI/PMID)
3. `get_citation_network` — Papers that cite or are cited by a paper
4. `get_paper_recommendations` — ML-based related paper suggestions
5. `find_open_access_pdf` — Locate freely available PDF versions

### Citation Tools
6. `add_citation` — Register a paper in the citation manager
7. `format_reference_list` — Generate formatted bibliography
8. `export_bibtex` — Export citations as BibTeX

### Report Tools
9. `plan_study` — Decompose a topic into research sections with analysis flow
10. `generate_report_section` — Write a specific section with citations
11. `compile_report` — Assemble sections into complete report (Markdown/DOCX)

### Presentation Tools
12. `generate_presentation` — Create PPTX from research findings
13. `add_chart_slide` — Add a data visualisation slide

### Inter-Agent Tools
14. `advise_agent` — Send evidence-based recommendation to another agent

---

## 6. Core Workflows

### 6.1 Deep Research Workflow

```
User/Orchestrator request
        │
        ▼
┌─ PHASE 1: STUDY PLANNING ──────────────────┐
│  • Decompose research question               │
│  • Identify key themes & sub-questions        │
│  • Plan section structure                     │
│  • Define search strategies per section       │
│  • Identify which agents should contribute    │
└─────────────────────────────────────────────┘
        │
        ▼
┌─ PHASE 2: LITERATURE GATHERING ─────────────┐
│  For each sub-question:                       │
│  • Search PubMed + Semantic Scholar + PMC     │
│  • Deduplicate across sources                 │
│  • Rank by relevance, citations, recency      │
│  • Fetch abstracts & key details              │
│  • Build citation graph for key papers        │
│  • Identify review articles & meta-analyses   │
└─────────────────────────────────────────────┘
        │
        ▼
┌─ PHASE 3: EVIDENCE SYNTHESIS ───────────────┐
│  • Grade evidence quality per finding         │
│  • Identify consensus vs. contradictions      │
│  • Map evidence to research sub-questions     │
│  • Flag gaps where evidence is thin           │
│  • Register all cited papers in CitationMgr   │
└─────────────────────────────────────────────┘
        │
        ▼
┌─ PHASE 4: INTEGRATION WITH OTHER AGENTS ────┐
│  • Receive computational results from         │
│    Pipeline/Statistical agents                │
│  • Contextualise results against literature   │
│  • Identify if results confirm/contradict     │
│    published findings                         │
│  • Generate advisory messages                 │
└─────────────────────────────────────────────┘
        │
        ▼
┌─ PHASE 5: REPORT GENERATION ───────────────┐
│  • Write each section with inline citations   │
│  • Generate reference list in chosen style    │
│  • Include figures/tables from other agents   │
│  • Produce Markdown + optional DOCX           │
└─────────────────────────────────────────────┘
        │
        ▼
┌─ PHASE 6: PRESENTATION GENERATION ─────────┐
│  • Create slide deck summarising findings     │
│  • Include key charts and visualisations      │
│  • Add speaker notes                          │
│  • Apply academic/conference template         │
└─────────────────────────────────────────────┘
```

### 6.2 Advisory Workflow

When other agents produce results, the Research Agent can:

1. **Receive** analysis outputs (DE results, pathway enrichment, variant lists)
2. **Search** literature for context (are these genes known? similar findings?)
3. **Assess** whether the methodology was appropriate
4. **Advise** on additional analyses, alternative approaches, or caveats
5. **Provide** a structured advisory message back to the Orchestrator

---

## 7. Integration with Existing BioAgent

### 7.1 Integration Pattern

The Research Agent follows the same pattern as your existing tools. Add it as a specialist that the Orchestrator can delegate to:

```python
# In your multi-agent coordinator:
from research_agent import ResearchAgent

class MultiAgentCoordinator:
    def __init__(self, config):
        self.research_agent = ResearchAgent(config)
        # ... other agents

    def delegate_research(self, task, context_from_other_agents=None):
        return self.research_agent.run(task, context=context_from_other_agents)
```

### 7.2 Four Integration Points

1. **Tool Registration** — Add research tools to the Orchestrator's tool definitions
2. **Message Passing** — Define schemas for inter-agent communication
3. **Context Injection** — Pass outputs from other agents as context to the Research Agent
4. **Output Collection** — Collect reports/presentations and return to user

### 7.3 Safe Integration Checklist

- [ ] Research Agent runs in its own workspace directory
- [ ] API rate limits are enforced per-client with configurable delays
- [ ] All literature API calls have timeouts (30s default)
- [ ] Citation deduplication prevents reference inflation
- [ ] Report generation has section-level error handling (one failed section doesn't crash the whole report)
- [ ] Presentation generation validates chart data before rendering
- [ ] Inter-agent messages follow a strict schema (no arbitrary code execution)
- [ ] All external API keys are loaded from environment variables, never hardcoded

---

## 8. Future-Proofing & Extensibility

### 8.1 Plugin Architecture

Each component (literature client, citation style, report template, slide template) is a self-contained module. To add a new literature source:

```python
class NewAPIClient(BaseLiteratureClient):
    def search(self, query, max_results=20) -> SearchResult:
        # Implement search
        ...

    def get_paper(self, identifier) -> Optional[Paper]:
        # Implement paper fetch
        ...

# Register in orchestrator
orchestrator.register_client("new_api", NewAPIClient())
```

### 8.2 Planned Extensions

| Phase | Addition | Purpose |
|-------|----------|---------|
| **v1.1** | OpenAlex integration | Broader coverage, concept tagging |
| **v1.2** | Full-text PDF analysis | Extract methods, figures from PDFs |
| **v1.3** | PRISMA workflow | Systematic review automation |
| **v1.4** | Knowledge graph builder | Map relationships between findings |
| **v2.0** | Multi-agent debate | Agents critique each other's interpretations |

### 8.3 Configuration-Driven Behaviour

All behaviours are configurable without code changes:

```yaml
research_agent:
  default_citation_style: "vancouver"
  max_papers_per_search: 50
  search_sources: ["pubmed", "semantic_scholar", "crossref"]
  report_sections: ["abstract", "introduction", "methods", "results", "discussion", "conclusion"]
  presentation_template: "academic"
  evidence_grading: true
  api_keys:
    ncbi: ${NCBI_API_KEY}
    semantic_scholar: ${S2_API_KEY}
```

---

## 9. System Prompt (Postdoc Persona)

The Research Agent uses a specialised system prompt that establishes its identity as a senior postdoctoral researcher. Key elements:

- **Role definition**: "You are a senior postdoctoral researcher with deep expertise in bioinformatics, computational biology, and biomedical research methodology."
- **Reasoning approach**: "Always think step-by-step: define the question, plan the search strategy, gather evidence, synthesise, and present with proper citations."
- **Quality standards**: "Every claim must be supported by a citation. Distinguish between strong evidence (meta-analyses, large cohorts) and preliminary findings (single studies, preprints)."
- **Collaborative tone**: "When advising other agents, be constructive and specific. Explain *why* you recommend a particular approach, citing evidence."

---

## 10. Implementation Priority

### Sprint 1 (Core — 1 week)
- [x] Literature API clients (PubMed, Semantic Scholar, CrossRef, Europe PMC, bioRxiv, Unpaywall)
- [x] Citation manager with multiple styles
- [ ] Research Agent class with system prompt
- [ ] Tool definitions for Claude API
- [ ] Basic study planning workflow

### Sprint 2 (Reports — 1 week)
- [ ] Report section generator
- [ ] Report compiler (Markdown output)
- [ ] DOCX export
- [ ] Evidence synthesis workflow

### Sprint 3 (Presentations — 1 week)
- [ ] PPTX generator using PptxGenJS
- [ ] Chart integration (matplotlib → PNG → slide)
- [ ] Academic slide templates
- [ ] Speaker notes generation

### Sprint 4 (Integration — 1 week)
- [ ] Inter-agent communication protocols
- [ ] Advisory message system
- [ ] Quality reviewer
- [ ] Integration into MultiAgentCoordinator
- [ ] End-to-end testing with real research queries
