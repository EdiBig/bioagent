"""
Research Agent — A postdoctoral-level AI research specialist.

The Research Agent integrates into the BioAgent multi-agent system to provide:
- Deep literature search across PubMed, Semantic Scholar, Europe PMC, CrossRef, bioRxiv
- Citation management with multiple academic styles (Vancouver, APA, Nature, Harvard, IEEE)
- Publication-quality report generation with proper references
- PowerPoint presentation creation with charts
- Inter-agent advisory communication

Usage:
    from Research_Agent import ResearchAgent, ResearchAgentConfig

    agent = ResearchAgent()
    response = agent.run("Review the role of TP53 in colorectal cancer progression")
"""

from .agent import ResearchAgent
from .config import ResearchAgentConfig

__all__ = [
    "ResearchAgent",
    "ResearchAgentConfig",
]

__version__ = "1.0.0"
