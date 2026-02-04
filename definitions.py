"""
Tool definitions for the Anthropic API tool_use feature.

Each tool is defined as a JSON schema that Claude uses to understand
what tools are available and how to call them.
"""

TOOLS = [
    {
        "name": "execute_python",
        "description": (
            "Execute Python code in a sandboxed environment. "
            "Common bioinformatics libraries are available: numpy, pandas, scipy, "
            "scikit-learn, matplotlib, seaborn, biopython, pysam, scanpy, anndata. "
            "Use this for data manipulation, statistical analysis, ML, and plotting. "
            "Code runs in a persistent session — variables persist between calls. "
            "For plots, save to file with plt.savefig() and report the path."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "code": {
                    "type": "string",
                    "description": "Python code to execute"
                },
                "timeout": {
                    "type": "integer",
                    "description": "Max execution time in seconds (default: 300)",
                    "default": 300
                }
            },
            "required": ["code"]
        }
    },
    {
        "name": "execute_r",
        "description": (
            "Execute R code. Bioconductor packages available: DESeq2, edgeR, "
            "limma, clusterProfiler, GenomicRanges, Biostrings, sva (ComBat), "
            "ggplot2, pheatmap, EnhancedVolcano. "
            "Use this for differential expression, enrichment analysis, and "
            "Bioconductor-specific workflows. "
            "For plots, save with ggsave() or pdf()/png() and report the path."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "code": {
                    "type": "string",
                    "description": "R code to execute"
                },
                "timeout": {
                    "type": "integer",
                    "description": "Max execution time in seconds (default: 300)",
                    "default": 300
                }
            },
            "required": ["code"]
        }
    },
    {
        "name": "execute_bash",
        "description": (
            "Execute a bash command. Use for running bioinformatics CLI tools "
            "(samtools, bcftools, bedtools, STAR, bwa, fastqc, multiqc, etc.), "
            "file operations, and system commands. "
            "Tools are available via conda/docker. "
            "For long-running commands, consider using & for background execution."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "command": {
                    "type": "string",
                    "description": "Bash command to execute"
                },
                "timeout": {
                    "type": "integer",
                    "description": "Max execution time in seconds (default: 600)",
                    "default": 600
                },
                "working_dir": {
                    "type": "string",
                    "description": "Working directory for the command (default: /workspace)",
                    "default": "/workspace"
                }
            },
            "required": ["command"]
        }
    },
    {
        "name": "query_ncbi",
        "description": (
            "Query NCBI databases using E-utilities. Supports: "
            "- esearch: Search a database (pubmed, gene, nucleotide, protein, etc.) "
            "- efetch: Retrieve records by ID "
            "- esummary: Get document summaries "
            "- einfo: Get database information "
            "Use for literature search, gene information, sequence retrieval, "
            "and cross-referencing biological databases."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "database": {
                    "type": "string",
                    "description": "NCBI database to query (pubmed, gene, nucleotide, protein, snp, omim, etc.)",
                    "enum": [
                        "pubmed", "gene", "nucleotide", "protein", "snp",
                        "omim", "taxonomy", "biosample", "sra", "gds",
                        "clinvar", "dbvar"
                    ]
                },
                "operation": {
                    "type": "string",
                    "description": "E-utility operation",
                    "enum": ["esearch", "efetch", "esummary", "einfo"]
                },
                "query": {
                    "type": "string",
                    "description": "Search query or comma-separated list of IDs (for efetch/esummary)"
                },
                "max_results": {
                    "type": "integer",
                    "description": "Maximum number of results to return (default: 10)",
                    "default": 10
                },
                "return_type": {
                    "type": "string",
                    "description": "Return type format (e.g., 'xml', 'json', 'fasta', 'gb', 'abstract')",
                    "default": "json"
                }
            },
            "required": ["database", "operation", "query"]
        }
    },
    {
        "name": "query_ensembl",
        "description": (
            "Query the Ensembl REST API for gene/variant/regulatory information. "
            "Supports: gene lookup, variant consequences, sequence retrieval, "
            "homology, regulatory features, and cross-references. "
            "Useful for annotation, variant effect prediction, and comparative genomics."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "endpoint": {
                    "type": "string",
                    "description": (
                        "Ensembl REST API endpoint, e.g.: "
                        "'lookup/id/{id}', 'lookup/symbol/{species}/{symbol}', "
                        "'vep/{species}/hgvs/{hgvs}', 'sequence/id/{id}', "
                        "'homology/id/{id}', 'overlap/region/{species}/{region}', "
                        "'xrefs/id/{id}'"
                    )
                },
                "params": {
                    "type": "object",
                    "description": "Optional query parameters as key-value pairs",
                    "default": {}
                },
                "species": {
                    "type": "string",
                    "description": "Species name (default: homo_sapiens)",
                    "default": "homo_sapiens"
                }
            },
            "required": ["endpoint"]
        }
    },
    {
        "name": "read_file",
        "description": (
            "Read the contents of a file. Supports text files, CSVs, TSVs, "
            "and common bioinformatics formats (BED, GFF, VCF headers, etc.). "
            "For large files, use head_lines to read only the first N lines. "
            "For binary files (BAM, etc.), use execute_bash with samtools instead."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Absolute path to the file"
                },
                "head_lines": {
                    "type": "integer",
                    "description": "Only read the first N lines (useful for large files)",
                    "default": None
                },
                "encoding": {
                    "type": "string",
                    "description": "File encoding (default: utf-8)",
                    "default": "utf-8"
                }
            },
            "required": ["path"]
        }
    },
    {
        "name": "write_file",
        "description": (
            "Write content to a file. Use for saving analysis scripts, "
            "results, reports, and intermediate data. "
            "Creates parent directories if they don't exist."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Absolute path for the file to write"
                },
                "content": {
                    "type": "string",
                    "description": "Content to write to the file"
                },
                "mode": {
                    "type": "string",
                    "description": "Write mode: 'w' (overwrite) or 'a' (append)",
                    "enum": ["w", "a"],
                    "default": "w"
                }
            },
            "required": ["path", "content"]
        }
    },
    {
        "name": "list_files",
        "description": (
            "List files and directories at a given path. "
            "Useful for exploring data directories and checking output files."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Directory path to list"
                },
                "pattern": {
                    "type": "string",
                    "description": "Glob pattern to filter files (e.g., '*.fastq.gz', '*.vcf')",
                    "default": "*"
                },
                "recursive": {
                    "type": "boolean",
                    "description": "Whether to list recursively",
                    "default": False
                }
            },
            "required": ["path"]
        }
    },
    {
        "name": "web_search",
        "description": (
            "Search the web for bioinformatics documentation, tool manuals, "
            "troubleshooting, and recent publications. Use when you need "
            "current information about tool parameters, new methods, or "
            "to find solutions to specific error messages."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Search query"
                }
            },
            "required": ["query"]
        }
    },
    {
        "name": "query_uniprot",
        "description": (
            "Query UniProt for protein sequences, annotations, and functional data. "
            "UniProt is the most comprehensive protein database. Use for: "
            "- Protein lookup by accession (P04637, P53_HUMAN) or gene name "
            "- Protein function, domains, GO terms, and annotations "
            "- Protein sequences in FASTA format "
            "- Cross-references to PDB, KEGG, STRING, and other databases"
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Search query (gene name, protein name, accession) or UniProt accession for fetch/fasta"
                },
                "operation": {
                    "type": "string",
                    "description": "Operation type",
                    "enum": ["search", "fetch", "fasta"],
                    "default": "search"
                },
                "format": {
                    "type": "string",
                    "description": "Response format for search (json, tsv)",
                    "default": "json"
                },
                "limit": {
                    "type": "integer",
                    "description": "Maximum results for search (default: 10, max: 25)",
                    "default": 10
                }
            },
            "required": ["query"]
        }
    },
    {
        "name": "query_kegg",
        "description": (
            "Query KEGG for pathways, genes, compounds, drugs, and diseases. "
            "KEGG provides comprehensive pathway and molecular interaction data. Use for: "
            "- Pathway lookup (hsa04110 for cell cycle, hsa05200 for cancer pathways) "
            "- Gene-to-pathway mapping (find pathways for a gene) "
            "- Compound/drug information "
            "- Disease associations "
            "- ID conversion between databases"
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "operation": {
                    "type": "string",
                    "description": "Operation type: get (entry), find (search), link (cross-refs), list (all entries), conv (ID conversion)",
                    "enum": ["get", "find", "link", "list", "conv"]
                },
                "database": {
                    "type": "string",
                    "description": "KEGG database for find/link/list/conv (pathway, genes, compound, drug, disease, module, ko)",
                    "enum": ["pathway", "genes", "compound", "drug", "disease", "module", "ko", "genome", "brite", "organism"]
                },
                "query": {
                    "type": "string",
                    "description": "Entry ID for get (e.g., hsa04110, hsa:7157), search term for find, or source for link/conv"
                }
            },
            "required": ["operation", "query"]
        }
    },
    {
        "name": "query_string",
        "description": (
            "Query STRING database for protein-protein interactions and functional enrichment. "
            "STRING is the premier database for protein interactions. Use for: "
            "- Protein interaction networks (what proteins interact with your protein) "
            "- Interaction partners with confidence scores "
            "- Functional enrichment analysis (GO terms, pathways for a protein set) "
            "- Mapping gene names to STRING IDs"
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "proteins": {
                    "type": "string",
                    "description": "Protein identifier(s) - gene symbol(s) or STRING ID(s), comma-separated for multiple"
                },
                "operation": {
                    "type": "string",
                    "description": "Operation type: network (full network), interactions (partners), enrichment (functional), map_ids (resolve identifiers)",
                    "enum": ["network", "interactions", "enrichment", "map_ids"],
                    "default": "interactions"
                },
                "species": {
                    "type": "integer",
                    "description": "NCBI taxonomy ID (9606=human, 10090=mouse, 10116=rat, 7227=fly, 6239=worm, 7955=zebrafish)",
                    "default": 9606
                },
                "score_threshold": {
                    "type": "integer",
                    "description": "Minimum interaction score 0-1000 (400=medium, 700=high, 900=highest confidence)",
                    "default": 400
                },
                "limit": {
                    "type": "integer",
                    "description": "Maximum number of interaction partners to return (default: 25)",
                    "default": 25
                }
            },
            "required": ["proteins"]
        }
    },
    {
        "name": "query_pdb",
        "description": (
            "Query the Protein Data Bank (PDB) for 3D protein structures and ligand binding sites. "
            "PDB is the primary repository for experimentally determined 3D structures. Use for: "
            "- Fetching structure details by PDB ID (e.g., 1TUP, 6LU7) "
            "- Searching for structures by protein name, gene, or keyword "
            "- Getting ligand and binding site information "
            "- Retrieving experimental metadata (resolution, method, organism)"
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "PDB ID (e.g., '1TUP', '6LU7') for fetch/ligands/summary, or search term for search"
                },
                "operation": {
                    "type": "string",
                    "description": "Operation type: fetch (full entry), search (find structures), ligands (binding sites), summary (brief info)",
                    "enum": ["fetch", "search", "ligands", "summary"],
                    "default": "fetch"
                },
                "limit": {
                    "type": "integer",
                    "description": "Maximum results for search (default: 10)",
                    "default": 10
                }
            },
            "required": ["query"]
        }
    }
]


def get_tools() -> list[dict]:
    """Return all tool definitions."""
    return TOOLS


def get_tool_names() -> list[str]:
    """Return list of available tool names."""
    return [t["name"] for t in TOOLS]
