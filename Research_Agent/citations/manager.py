"""
Citation Manager — Academic citation formatting and management.

Supports multiple citation styles:
- Vancouver (numbered)
- APA (author-year)
- Nature (numbered, specific format)
- Harvard (author-year)
- IEEE (numbered)

Features:
- Paper deduplication by DOI/PMID/title
- In-text citation generation
- Reference list formatting
- BibTeX export
"""

import re
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..literature.clients import Paper


# ═══════════════════════════════════════════════════════════════════
# CITATION STYLES
# ═══════════════════════════════════════════════════════════════════

class CitationStyle(ABC):
    """Base class for citation styles."""

    @abstractmethod
    def format_inline(self, paper: "Paper", number: int) -> str:
        """Format an inline citation."""
        pass

    @abstractmethod
    def format_reference(self, paper: "Paper", number: int) -> str:
        """Format a reference list entry."""
        pass


class VancouverStyle(CitationStyle):
    """Vancouver citation style (numbered)."""

    def format_inline(self, paper: "Paper", number: int) -> str:
        """Format: [1]"""
        return f"[{number}]"

    def format_reference(self, paper: "Paper", number: int) -> str:
        """
        Format: 1. Author1 AB, Author2 CD. Title. Journal. Year;Vol:Pages.
        """
        # Authors (last name + initials, max 6 then et al.)
        authors_str = self._format_authors(paper)

        # Build reference
        parts = [f"{number}. {authors_str}"]

        # Title (no italics in Vancouver)
        title = paper.title.rstrip(".")
        parts.append(f"{title}.")

        # Journal (abbreviated if possible)
        if paper.journal:
            parts.append(f"{paper.journal}.")

        # Year
        if paper.year:
            parts.append(f"{paper.year}")

        # DOI
        if paper.doi:
            parts.append(f"doi:{paper.doi}")

        return " ".join(parts)

    def _format_authors(self, paper: "Paper") -> str:
        """Format authors for Vancouver style."""
        if not paper.authors:
            return "Anonymous."

        formatted = []
        for i, author in enumerate(paper.authors[:6]):
            last = author.last_name
            initials = author.initials
            if initials:
                formatted.append(f"{last} {initials}")
            else:
                formatted.append(last)

        result = ", ".join(formatted)
        if len(paper.authors) > 6:
            result += ", et al"
        return result + "."


class APAStyle(CitationStyle):
    """APA 7th edition citation style (author-year)."""

    def format_inline(self, paper: "Paper", number: int) -> str:
        """Format: (Author, Year) or (Author et al., Year)"""
        if not paper.authors:
            return f"(Anonymous, {paper.year})"

        if len(paper.authors) == 1:
            return f"({paper.authors[0].last_name}, {paper.year})"
        elif len(paper.authors) == 2:
            return f"({paper.authors[0].last_name} & {paper.authors[1].last_name}, {paper.year})"
        else:
            return f"({paper.authors[0].last_name} et al., {paper.year})"

    def format_reference(self, paper: "Paper", number: int) -> str:
        """
        Format: Author, A. B., & Author, C. D. (Year). Title. *Journal*, Vol(Issue), Pages. DOI
        """
        # Authors
        authors_str = self._format_authors(paper)

        # Year in parentheses
        year = f"({paper.year})" if paper.year else "(n.d.)"

        # Title (sentence case, not italicized)
        title = paper.title.rstrip(".")

        # Journal (italicized in markdown)
        journal = f"*{paper.journal}*" if paper.journal else ""

        # Build reference
        parts = [authors_str, year, f"{title}."]
        if journal:
            parts.append(f"{journal}.")
        if paper.doi:
            parts.append(f"https://doi.org/{paper.doi}")

        return " ".join(parts)

    def _format_authors(self, paper: "Paper") -> str:
        """Format authors for APA style."""
        if not paper.authors:
            return "Anonymous"

        formatted = []
        for i, author in enumerate(paper.authors[:20]):
            last = author.last_name
            initials = ". ".join(list(author.initials)) + "." if author.initials else ""
            if initials:
                formatted.append(f"{last}, {initials}")
            else:
                formatted.append(last)

        if len(formatted) == 1:
            return formatted[0]
        elif len(formatted) == 2:
            return f"{formatted[0]} & {formatted[1]}"
        else:
            return ", ".join(formatted[:-1]) + f", & {formatted[-1]}"


class NatureStyle(CitationStyle):
    """Nature citation style (superscript numbers)."""

    def format_inline(self, paper: "Paper", number: int) -> str:
        """Format: ^1 (superscript)"""
        return f"<sup>{number}</sup>"

    def format_reference(self, paper: "Paper", number: int) -> str:
        """
        Format: 1. Author, A. B. et al. Title. *Journal* Vol, Pages (Year).
        """
        # Authors (first author et al. if >1)
        if not paper.authors:
            authors_str = "Anonymous"
        elif len(paper.authors) == 1:
            a = paper.authors[0]
            authors_str = f"{a.last_name}, {a.initials}." if a.initials else a.last_name
        else:
            a = paper.authors[0]
            authors_str = f"{a.last_name}, {a.initials}. et al." if a.initials else f"{a.last_name} et al."

        # Title (not italicized)
        title = paper.title.rstrip(".")

        # Journal (italicized)
        journal = f"*{paper.journal}*" if paper.journal else ""

        # Build reference
        parts = [f"{number}. {authors_str}", f"{title}."]
        if journal:
            parts.append(journal)
        if paper.year:
            parts.append(f"({paper.year}).")
        if paper.doi:
            parts.append(f"doi:{paper.doi}")

        return " ".join(parts)


class HarvardStyle(CitationStyle):
    """Harvard citation style (author-year)."""

    def format_inline(self, paper: "Paper", number: int) -> str:
        """Format: (Author Year) or (Author et al. Year)"""
        if not paper.authors:
            return f"(Anonymous {paper.year})"

        if len(paper.authors) <= 2:
            names = " and ".join(a.last_name for a in paper.authors[:2])
            return f"({names} {paper.year})"
        else:
            return f"({paper.authors[0].last_name} et al. {paper.year})"

    def format_reference(self, paper: "Paper", number: int) -> str:
        """
        Format: Author, A.B. and Author, C.D. (Year) 'Title', *Journal*, Vol(Issue), pp. Pages.
        """
        # Authors
        authors_str = self._format_authors(paper)

        # Year
        year = f"({paper.year})" if paper.year else "(n.d.)"

        # Title in quotes
        title = f"'{paper.title.rstrip('.')}'"

        # Journal italicized
        journal = f"*{paper.journal}*" if paper.journal else ""

        parts = [authors_str, year, f"{title},"]
        if journal:
            parts.append(f"{journal}.")
        if paper.doi:
            parts.append(f"doi:{paper.doi}")

        return " ".join(parts)

    def _format_authors(self, paper: "Paper") -> str:
        """Format authors for Harvard style."""
        if not paper.authors:
            return "Anonymous"

        formatted = []
        for author in paper.authors:
            initials = ".".join(list(author.initials)) + "." if author.initials else ""
            if initials:
                formatted.append(f"{author.last_name}, {initials}")
            else:
                formatted.append(author.last_name)

        if len(formatted) == 1:
            return formatted[0]
        elif len(formatted) == 2:
            return f"{formatted[0]} and {formatted[1]}"
        else:
            return ", ".join(formatted[:-1]) + f" and {formatted[-1]}"


class IEEEStyle(CitationStyle):
    """IEEE citation style (numbered in brackets)."""

    def format_inline(self, paper: "Paper", number: int) -> str:
        """Format: [1]"""
        return f"[{number}]"

    def format_reference(self, paper: "Paper", number: int) -> str:
        """
        Format: [1] A. B. Author and C. D. Author, "Title," *Journal*, vol. X, no. Y, pp. Z, Year.
        """
        # Authors (initials first)
        authors_str = self._format_authors(paper)

        # Title in quotes
        title = f'"{paper.title.rstrip(".")}"'

        # Journal italicized
        journal = f"*{paper.journal}*" if paper.journal else ""

        parts = [f"[{number}] {authors_str},", f"{title},"]
        if journal:
            parts.append(f"{journal},")
        if paper.year:
            parts.append(f"{paper.year}.")
        if paper.doi:
            parts.append(f"doi:{paper.doi}")

        return " ".join(parts)

    def _format_authors(self, paper: "Paper") -> str:
        """Format authors for IEEE style (initials first)."""
        if not paper.authors:
            return "Anonymous"

        formatted = []
        for author in paper.authors[:6]:
            initials = " ".join(f"{c}." for c in author.initials) if author.initials else ""
            if initials:
                formatted.append(f"{initials} {author.last_name}")
            else:
                formatted.append(author.last_name)

        if len(paper.authors) > 6:
            formatted.append("et al.")

        if len(formatted) == 1:
            return formatted[0]
        elif len(formatted) == 2:
            return f"{formatted[0]} and {formatted[1]}"
        else:
            return ", ".join(formatted[:-1]) + f", and {formatted[-1]}"


# ═══════════════════════════════════════════════════════════════════
# CITATION MANAGER
# ═══════════════════════════════════════════════════════════════════

@dataclass
class CitedPaper:
    """A paper that has been cited, with its citation number."""
    paper: "Paper"
    number: int
    first_cited: datetime = field(default_factory=datetime.now)


class CitationManager:
    """
    Manages citations for a research document.

    Features:
    - Deduplication by DOI/PMID/title
    - Multiple citation styles
    - In-text citation generation
    - Reference list formatting
    - BibTeX export
    """

    def __init__(self, style: CitationStyle = None):
        """
        Initialize citation manager.

        Args:
            style: Citation style to use (default: Vancouver)
        """
        self.style = style or VancouverStyle()
        self._papers: dict[str, CitedPaper] = {}  # key -> CitedPaper
        self._order: list[str] = []  # Keys in citation order

    def _make_key(self, paper: "Paper") -> str:
        """Generate a unique key for deduplication."""
        if paper.doi:
            return f"doi:{paper.doi.lower()}"
        elif paper.pmid:
            return f"pmid:{paper.pmid}"
        else:
            # Normalize title
            normalized = re.sub(r"[^a-z0-9]", "", paper.title.lower())
            return f"title:{normalized[:100]}"

    def cite(self, paper: "Paper") -> str:
        """
        Cite a paper and return the inline citation.

        If the paper is already cited, returns the existing citation.
        Otherwise, adds it and returns a new citation.
        """
        key = self._make_key(paper)

        if key in self._papers:
            # Already cited
            cited = self._papers[key]
            return self.style.format_inline(cited.paper, cited.number)
        else:
            # New citation
            number = len(self._order) + 1
            cited = CitedPaper(paper=paper, number=number)
            self._papers[key] = cited
            self._order.append(key)
            return self.style.format_inline(paper, number)

    def get_inline_citation(self, paper: "Paper") -> str | None:
        """Get the inline citation for a paper if it's been cited."""
        key = self._make_key(paper)
        if key in self._papers:
            cited = self._papers[key]
            return self.style.format_inline(cited.paper, cited.number)
        return None

    def get_reference_list(self) -> str:
        """Generate the formatted reference list."""
        if not self._order:
            return "## References\n\nNo references cited."

        lines = ["## References", ""]
        for key in self._order:
            cited = self._papers[key]
            ref = self.style.format_reference(cited.paper, cited.number)
            lines.append(ref)
            lines.append("")

        return "\n".join(lines)

    def get_bibtex(self) -> str:
        """Export all citations as BibTeX."""
        entries = []

        for key in self._order:
            cited = self._papers[key]
            paper = cited.paper
            entry = self._paper_to_bibtex(paper, cited.number)
            entries.append(entry)

        return "\n\n".join(entries)

    def _paper_to_bibtex(self, paper: "Paper", number: int) -> str:
        """Convert a paper to BibTeX format."""
        # Generate cite key
        first_author = paper.authors[0].last_name if paper.authors else "unknown"
        cite_key = re.sub(r"[^a-zA-Z0-9]", "", first_author.lower())
        cite_key = f"{cite_key}{paper.year}" if paper.year else cite_key

        # Authors in BibTeX format
        authors = " and ".join(
            f"{a.last_name}, {a.initials}" if a.initials else a.last_name
            for a in paper.authors
        ) if paper.authors else "Anonymous"

        lines = [
            f"@article{{{cite_key},",
            f'  author = {{{authors}}},',
            f'  title = {{{{{paper.title}}}}},',  # Double braces for case preservation
        ]

        if paper.journal:
            lines.append(f'  journal = {{{paper.journal}}},')
        if paper.year:
            lines.append(f'  year = {{{paper.year}}},')
        if paper.doi:
            lines.append(f'  doi = {{{paper.doi}}},')
        if paper.pmid:
            lines.append(f'  pmid = {{{paper.pmid}}},')

        lines.append("}")
        return "\n".join(lines)

    def count(self) -> int:
        """Return the number of citations."""
        return len(self._papers)

    def get_all_papers(self) -> list["Paper"]:
        """Return all cited papers in citation order."""
        return [self._papers[key].paper for key in self._order]

    def clear(self):
        """Clear all citations."""
        self._papers.clear()
        self._order.clear()

    def set_style(self, style: CitationStyle):
        """Change the citation style."""
        self.style = style


# ═══════════════════════════════════════════════════════════════════
# STYLE REGISTRY
# ═══════════════════════════════════════════════════════════════════

CITATION_STYLES = {
    "vancouver": VancouverStyle,
    "apa": APAStyle,
    "nature": NatureStyle,
    "harvard": HarvardStyle,
    "ieee": IEEEStyle,
}


def get_citation_style(name: str) -> CitationStyle:
    """Get a citation style by name."""
    style_cls = CITATION_STYLES.get(name.lower())
    if style_cls:
        return style_cls()
    raise ValueError(f"Unknown citation style: {name}. Available: {list(CITATION_STYLES.keys())}")
