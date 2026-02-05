"""Citation management and formatting."""

from .manager import (
    CitationManager,
    CitationStyle,
    VancouverStyle,
    APAStyle,
    NatureStyle,
    HarvardStyle,
    IEEEStyle,
    CITATION_STYLES,
    get_citation_style,
)

__all__ = [
    "CitationManager",
    "CitationStyle",
    "VancouverStyle",
    "APAStyle",
    "NatureStyle",
    "HarvardStyle",
    "IEEEStyle",
    "CITATION_STYLES",
    "get_citation_style",
]
