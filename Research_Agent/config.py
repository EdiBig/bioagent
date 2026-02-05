"""
Configuration for the Research Agent.

Loads settings from environment variables and/or a config dict.
"""

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

# Auto-load .env file if present (check both Research_Agent dir and parent bioagent dir)
try:
    from dotenv import load_dotenv
    # First try parent directory (bioagent/.env)
    _env_path = Path(__file__).parent.parent / ".env"
    if _env_path.exists():
        load_dotenv(_env_path)
    else:
        # Fallback to Research_Agent/.env
        _env_path = Path(__file__).parent / ".env"
        if _env_path.exists():
            load_dotenv(_env_path)
except ImportError:
    pass  # python-dotenv not installed


@dataclass
class ResearchAgentConfig:
    """Configuration for the Research Agent."""

    # Anthropic
    anthropic_api_key: str = ""
    model: str = "claude-sonnet-4-20250514"
    max_tokens: int = 8192

    # NCBI / PubMed
    ncbi_api_key: str = ""
    ncbi_email: str = "bioagent@research.org"

    # Semantic Scholar
    semantic_scholar_api_key: str = ""

    # Literature defaults
    default_citation_style: str = "vancouver"
    default_search_sources: list[str] = field(
        default_factory=lambda: ["pubmed", "semantic_scholar", "europe_pmc"]
    )
    max_papers_per_search: int = 50

    # Report defaults
    default_report_sections: list[str] = field(
        default_factory=lambda: [
            "abstract", "introduction", "methods",
            "results", "discussion", "conclusion"
        ]
    )

    # Presentation defaults
    default_presentation_template: str = "academic"
    default_color_scheme: str = "ocean"

    # Workspace
    workspace_dir: str = "/workspace/research"
    output_dir: str = "/workspace/research/outputs"

    # Output organization
    enable_workspace_tracking: bool = True  # Use BioAgent workspace system
    default_project_id: str = ""  # Project to organize outputs under
    auto_start_analysis: bool = True  # Auto-start analysis session on run()

    # Rate limiting
    pubmed_rate_limit: float = 0.35  # seconds between requests
    semantic_scholar_rate_limit: float = 0.1
    crossref_rate_limit: float = 0.1
    europe_pmc_rate_limit: float = 0.1

    # Agent identity
    agent_name: str = "ResearchAgent"
    agent_role: str = "Senior Postdoctoral Research Scientist"

    @classmethod
    def from_env(cls) -> "ResearchAgentConfig":
        """Create config from environment variables."""
        import sys

        # Platform-appropriate default workspace
        if sys.platform == "win32":
            from pathlib import Path
            default_workspace = str(Path.home() / "bioagent_workspace" / "research")
        else:
            default_workspace = "/workspace/research"

        workspace = os.getenv("RESEARCH_WORKSPACE", default_workspace)

        return cls(
            anthropic_api_key=os.getenv("ANTHROPIC_API_KEY", ""),
            ncbi_api_key=os.getenv("NCBI_API_KEY", ""),
            ncbi_email=os.getenv("NCBI_EMAIL", "bioagent@research.org"),
            semantic_scholar_api_key=os.getenv("S2_API_KEY", ""),
            workspace_dir=workspace,
            output_dir=os.getenv("RESEARCH_OUTPUT", f"{workspace}/outputs"),
            default_citation_style=os.getenv("CITATION_STYLE", "vancouver"),
            enable_workspace_tracking=os.getenv("RESEARCH_ENABLE_TRACKING", "true").lower() == "true",
            default_project_id=os.getenv("RESEARCH_PROJECT_ID", ""),
            auto_start_analysis=os.getenv("RESEARCH_AUTO_ANALYSIS", "true").lower() == "true",
        )

    @classmethod
    def from_dict(cls, d: dict) -> "ResearchAgentConfig":
        """Create config from a dictionary (e.g., loaded from YAML)."""
        valid_fields = {f.name for f in cls.__dataclass_fields__.values()}
        filtered = {k: v for k, v in d.items() if k in valid_fields}
        return cls(**filtered)

    def validate(self) -> list[str]:
        """Return list of configuration issues."""
        issues = []
        if not self.anthropic_api_key:
            issues.append("ANTHROPIC_API_KEY not set — agent loop won't work")
        if not self.ncbi_api_key:
            issues.append(
                "NCBI_API_KEY not set — PubMed searches limited to 3/sec "
                "(get free key at https://ncbiinsights.ncbi.nlm.nih.gov/2017/11/02/new-api-keys-for-the-e-utilities/)"
            )
        if not self.semantic_scholar_api_key:
            issues.append(
                "S2_API_KEY not set — Semantic Scholar limited to 100 requests/5min "
                "(get free key at https://www.semanticscholar.org/product/api)"
            )
        return issues
