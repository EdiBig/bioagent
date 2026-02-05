"""Literature search clients and orchestration."""

from .clients import (
    Paper,
    Author,
    SearchResults,
    LiteratureSearchOrchestrator,
    PubMedClient,
    SemanticScholarClient,
    EuropePMCClient,
    CrossRefClient,
    BioRxivClient,
    UnpaywallClient,
)

__all__ = [
    "Paper",
    "Author",
    "SearchResults",
    "LiteratureSearchOrchestrator",
    "PubMedClient",
    "SemanticScholarClient",
    "EuropePMCClient",
    "CrossRefClient",
    "BioRxivClient",
    "UnpaywallClient",
]
