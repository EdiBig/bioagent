"""
Tool definitions for the Research Agent.

These are the Claude API tool_use schemas that the Research Agent
exposes to the Orchestrator and to its own agentic loop.
"""


RESEARCH_TOOLS = [
    # ═══════════════════════════════════════════════════════════
    # LITERATURE SEARCH TOOLS
    # ═══════════════════════════════════════════════════════════
    {
        "name": "search_literature",
        "description": (
            "Search scientific literature across multiple databases simultaneously. "
            "Searches PubMed, Semantic Scholar, Europe PMC, CrossRef, and optionally "
            "bioRxiv for preprints. Returns deduplicated, ranked results with "
            "titles, authors, abstracts, citation counts, and DOIs. "
            "Use this as the primary tool for finding relevant papers on any topic."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": (
                        "Search query. For PubMed, use MeSH terms when possible "
                        "(e.g., 'RNA-Seq[MeSH] AND differential expression'). "
                        "For broader search, use natural language."
                    )
                },
                "sources": {
                    "type": "array",
                    "items": {
                        "type": "string",
                        "enum": ["pubmed", "semantic_scholar", "europe_pmc",
                                 "crossref", "biorxiv"]
                    },
                    "description": "Which databases to search. Defaults to all.",
                    "default": ["pubmed", "semantic_scholar", "europe_pmc"]
                },
                "max_results_per_source": {
                    "type": "integer",
                    "description": "Maximum results per source (1-50)",
                    "default": 20,
                    "minimum": 1,
                    "maximum": 50
                },
                "year_from": {
                    "type": "integer",
                    "description": "Filter: minimum publication year (e.g., 2020)"
                },
                "year_to": {
                    "type": "integer",
                    "description": "Filter: maximum publication year (e.g., 2025)"
                },
                "article_types": {
                    "type": "array",
                    "items": {
                        "type": "string",
                        "enum": ["research", "review", "meta-analysis",
                                 "clinical-trial", "preprint"]
                    },
                    "description": "Filter by article type"
                },
                "sort_by": {
                    "type": "string",
                    "enum": ["relevance", "citations", "date", "combined"],
                    "description": "How to rank results. 'combined' uses relevance + citations + recency.",
                    "default": "combined"
                }
            },
            "required": ["query"]
        }
    },
    {
        "name": "get_paper_details",
        "description": (
            "Fetch full metadata for a specific paper by DOI, PMID, or "
            "Semantic Scholar paper ID. Returns title, all authors with "
            "affiliations, abstract, journal, volume, issue, pages, "
            "citation count, references, and open access status."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "identifier": {
                    "type": "string",
                    "description": (
                        "Paper identifier: DOI (e.g., '10.1038/s41586-020-2308-7'), "
                        "PMID (e.g., '32269341'), or Semantic Scholar ID"
                    )
                },
                "identifier_type": {
                    "type": "string",
                    "enum": ["doi", "pmid", "s2id", "auto"],
                    "description": "Type of identifier. 'auto' will attempt to detect.",
                    "default": "auto"
                }
            },
            "required": ["identifier"]
        }
    },
    {
        "name": "get_citation_network",
        "description": (
            "Explore the citation network of a paper. Returns papers that cite "
            "this paper (forward citations) and/or papers this paper cites "
            "(references/backward citations). Useful for finding related work, "
            "identifying seminal papers, and tracing how a finding has been "
            "built upon."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "paper_id": {
                    "type": "string",
                    "description": "DOI or Semantic Scholar paper ID"
                },
                "direction": {
                    "type": "string",
                    "enum": ["citations", "references", "both"],
                    "description": (
                        "'citations' = papers that cite this one (forward), "
                        "'references' = papers this one cites (backward), "
                        "'both' = both directions"
                    ),
                    "default": "both"
                },
                "max_results": {
                    "type": "integer",
                    "description": "Maximum papers to return per direction",
                    "default": 20,
                    "minimum": 1,
                    "maximum": 100
                },
                "sort_by": {
                    "type": "string",
                    "enum": ["citations", "date", "influence"],
                    "description": "How to rank results. 'influence' uses Semantic Scholar's influential citation metric.",
                    "default": "citations"
                }
            },
            "required": ["paper_id"]
        }
    },
    {
        "name": "get_paper_recommendations",
        "description": (
            "Get ML-based paper recommendations from Semantic Scholar. "
            "Given a seed paper, returns related papers the researcher might "
            "find useful. Good for discovering papers you might miss with "
            "keyword search alone."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "paper_id": {
                    "type": "string",
                    "description": "DOI or Semantic Scholar paper ID of the seed paper"
                },
                "max_results": {
                    "type": "integer",
                    "description": "Number of recommendations (1-20)",
                    "default": 10,
                    "minimum": 1,
                    "maximum": 20
                }
            },
            "required": ["paper_id"]
        }
    },
    {
        "name": "find_open_access_pdf",
        "description": (
            "Find a freely available PDF for a paper using its DOI. "
            "Checks Unpaywall and Europe PMC for open access versions. "
            "Returns the URL to the PDF if available."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "doi": {
                    "type": "string",
                    "description": "DOI of the paper (e.g., '10.1038/s41586-020-2308-7')"
                }
            },
            "required": ["doi"]
        }
    },

    # ═══════════════════════════════════════════════════════════
    # CITATION MANAGEMENT TOOLS
    # ═══════════════════════════════════════════════════════════
    {
        "name": "add_citation",
        "description": (
            "Register a paper in the citation manager for the current report. "
            "Returns the in-text citation string (e.g., '[1]' for Vancouver, "
            "'(Smith et al., 2024)' for APA). The paper will be included in "
            "the reference list when format_reference_list is called."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "doi": {
                    "type": "string",
                    "description": "DOI of the paper to cite"
                },
                "pmid": {
                    "type": "string",
                    "description": "PubMed ID (alternative to DOI)"
                },
                "title": {
                    "type": "string",
                    "description": "Paper title (used if DOI/PMID not available)"
                },
                "authors": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Author names (e.g., ['Smith J', 'Jones K'])"
                },
                "year": {
                    "type": "integer",
                    "description": "Publication year"
                },
                "journal": {
                    "type": "string",
                    "description": "Journal name"
                }
            }
        }
    },
    {
        "name": "format_reference_list",
        "description": (
            "Generate the formatted reference list / bibliography for all "
            "papers cited so far. Uses the configured citation style."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "style": {
                    "type": "string",
                    "enum": ["vancouver", "apa", "nature", "harvard", "ieee", "chicago"],
                    "description": "Citation style to use",
                    "default": "vancouver"
                }
            }
        }
    },
    {
        "name": "export_bibtex",
        "description": (
            "Export all cited papers as a BibTeX file. Useful for importing "
            "into reference managers (Zotero, Mendeley, EndNote)."
        ),
        "input_schema": {
            "type": "object",
            "properties": {}
        }
    },

    # ═══════════════════════════════════════════════════════════
    # STUDY PLANNING & REPORT TOOLS
    # ═══════════════════════════════════════════════════════════
    {
        "name": "plan_study",
        "description": (
            "Decompose a research topic into structured sections with a "
            "planned analysis flow. Returns a study plan with sections, "
            "sub-questions, search strategies, and suggested agent delegations. "
            "This should be the FIRST tool called for any deep research task."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "research_question": {
                    "type": "string",
                    "description": "The main research question or topic"
                },
                "study_type": {
                    "type": "string",
                    "enum": [
                        "literature_review",
                        "systematic_review",
                        "methods_comparison",
                        "case_study_analysis",
                        "data_interpretation",
                        "hypothesis_generation",
                        "pipeline_evaluation"
                    ],
                    "description": "Type of study/analysis to plan",
                    "default": "literature_review"
                },
                "scope": {
                    "type": "string",
                    "enum": ["focused", "comprehensive", "exhaustive"],
                    "description": (
                        "'focused' = 10-20 key papers, targeted. "
                        "'comprehensive' = 30-50 papers, thorough coverage. "
                        "'exhaustive' = 100+ papers, systematic approach."
                    ),
                    "default": "comprehensive"
                },
                "context_from_agents": {
                    "type": "string",
                    "description": (
                        "Any context or results from other agents that should "
                        "inform the study plan (e.g., DE gene lists, pathway "
                        "enrichment results, variant annotations)"
                    )
                }
            },
            "required": ["research_question"]
        }
    },
    {
        "name": "generate_report_section",
        "description": (
            "Write a specific section of the research report. The section "
            "will include inline citations and be written in academic style. "
            "Call this once per section after literature gathering is complete."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "section_type": {
                    "type": "string",
                    "enum": [
                        "abstract", "introduction", "background",
                        "methods", "results", "discussion",
                        "conclusion", "limitations", "future_directions"
                    ],
                    "description": "Type of section to generate"
                },
                "section_title": {
                    "type": "string",
                    "description": "Custom title for the section (optional)"
                },
                "content_guidance": {
                    "type": "string",
                    "description": (
                        "Guidance on what this section should cover. Include "
                        "key points, sub-topics, specific papers to reference, "
                        "or data from other agents to incorporate."
                    )
                },
                "max_words": {
                    "type": "integer",
                    "description": "Approximate maximum word count for the section",
                    "default": 800
                }
            },
            "required": ["section_type", "content_guidance"]
        }
    },
    {
        "name": "compile_report",
        "description": (
            "Assemble all generated sections into a complete report. "
            "Adds title page, table of contents, formatted reference list, "
            "and optional appendices. Outputs as Markdown with optional DOCX."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "title": {
                    "type": "string",
                    "description": "Report title"
                },
                "authors": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Report author names"
                },
                "output_format": {
                    "type": "string",
                    "enum": ["markdown", "docx", "both"],
                    "description": "Output format",
                    "default": "both"
                },
                "citation_style": {
                    "type": "string",
                    "enum": ["vancouver", "apa", "nature", "harvard", "ieee"],
                    "default": "vancouver"
                },
                "include_supplementary": {
                    "type": "boolean",
                    "description": "Whether to include supplementary materials section",
                    "default": False
                }
            },
            "required": ["title"]
        }
    },

    # ═══════════════════════════════════════════════════════════
    # PRESENTATION TOOLS
    # ═══════════════════════════════════════════════════════════
    {
        "name": "generate_presentation",
        "description": (
            "Create a PowerPoint presentation (PPTX) from research findings. "
            "Generates professional slides with title, outline, content slides "
            "with key findings, charts/visualisations, and a references slide. "
            "Uses PptxGenJS for slide generation."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "title": {
                    "type": "string",
                    "description": "Presentation title"
                },
                "subtitle": {
                    "type": "string",
                    "description": "Subtitle or author/affiliation line"
                },
                "sections": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "title": {"type": "string"},
                            "key_points": {
                                "type": "array",
                                "items": {"type": "string"}
                            },
                            "speaker_notes": {"type": "string"},
                            "chart_data": {
                                "type": "object",
                                "description": "Optional chart data for this slide"
                            }
                        },
                        "required": ["title", "key_points"]
                    },
                    "description": "Slide sections with content"
                },
                "template": {
                    "type": "string",
                    "enum": ["academic", "clinical", "conference", "lab_meeting", "minimal"],
                    "description": "Slide template style",
                    "default": "academic"
                },
                "include_references_slide": {
                    "type": "boolean",
                    "description": "Add a references slide at the end",
                    "default": True
                },
                "color_scheme": {
                    "type": "string",
                    "enum": [
                        "ocean", "forest", "midnight", "teal",
                        "charcoal", "berry", "sage", "coral"
                    ],
                    "description": "Color scheme for the presentation",
                    "default": "ocean"
                }
            },
            "required": ["title", "sections"]
        }
    },
    {
        "name": "add_chart_slide",
        "description": (
            "Add a data visualisation slide to an existing presentation. "
            "Supports bar charts, line charts, pie charts, scatter plots, "
            "and heatmap-style tables. The chart data can come from other "
            "agents' analysis outputs."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "slide_title": {
                    "type": "string",
                    "description": "Title for the chart slide"
                },
                "chart_type": {
                    "type": "string",
                    "enum": ["bar", "line", "pie", "scatter", "doughnut", "table"],
                    "description": "Type of chart to generate"
                },
                "data": {
                    "type": "object",
                    "properties": {
                        "labels": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "X-axis labels or category names"
                        },
                        "series": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "name": {"type": "string"},
                                    "values": {
                                        "type": "array",
                                        "items": {"type": "number"}
                                    }
                                },
                                "required": ["name", "values"]
                            },
                            "description": "Data series"
                        }
                    },
                    "required": ["labels", "series"]
                },
                "caption": {
                    "type": "string",
                    "description": "Caption or footnote for the chart"
                },
                "speaker_notes": {
                    "type": "string",
                    "description": "Speaker notes explaining the chart"
                }
            },
            "required": ["slide_title", "chart_type", "data"]
        }
    },

    # ═══════════════════════════════════════════════════════════
    # INTER-AGENT COMMUNICATION
    # ═══════════════════════════════════════════════════════════
    {
        "name": "advise_agent",
        "description": (
            "Send an evidence-based recommendation or advisory message to "
            "another agent in the system. Use this when you have literature "
            "evidence suggesting a methodological improvement, alternative "
            "analysis approach, or important caveat for another agent's work."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "target_agent": {
                    "type": "string",
                    "enum": [
                        "orchestrator", "pipeline_engineer",
                        "statistical_ml", "literature_db"
                    ],
                    "description": "Which agent to advise"
                },
                "advisory_type": {
                    "type": "string",
                    "enum": [
                        "methodology_recommendation",
                        "alternative_approach",
                        "quality_concern",
                        "contextual_information",
                        "interpretation_guidance",
                        "next_steps_suggestion"
                    ],
                    "description": "Type of advisory message"
                },
                "message": {
                    "type": "string",
                    "description": (
                        "The advisory message. Should include: context, "
                        "specific recommendation, and supporting evidence "
                        "with citations."
                    )
                },
                "priority": {
                    "type": "string",
                    "enum": ["low", "medium", "high", "critical"],
                    "description": "Priority level of the advisory",
                    "default": "medium"
                },
                "supporting_papers": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "DOIs of papers supporting this advisory"
                }
            },
            "required": ["target_agent", "advisory_type", "message"]
        }
    },
]


def get_research_tools() -> list[dict]:
    """Return all Research Agent tool definitions."""
    return RESEARCH_TOOLS


def get_research_tool_names() -> list[str]:
    """Return list of available research tool names."""
    return [t["name"] for t in RESEARCH_TOOLS]
