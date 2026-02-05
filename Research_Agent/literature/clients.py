"""
Literature Search Clients and Orchestrator.

Provides unified access to multiple scientific literature APIs:
- PubMed (via NCBI E-utilities)
- Semantic Scholar
- Europe PMC
- CrossRef
- bioRxiv/medRxiv
- Unpaywall (open access PDF detection)
"""

import json
import re
import time
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional


# ═══════════════════════════════════════════════════════════════════
# DATA CLASSES
# ═══════════════════════════════════════════════════════════════════

@dataclass
class Author:
    """Paper author."""
    name: str
    orcid: str = ""
    affiliation: str = ""

    @property
    def last_name(self) -> str:
        """Extract last name."""
        parts = self.name.split()
        return parts[-1] if parts else ""

    @property
    def initials(self) -> str:
        """Get initials from first/middle names."""
        parts = self.name.split()
        if len(parts) > 1:
            return "".join(p[0].upper() for p in parts[:-1])
        return ""


@dataclass
class Paper:
    """Unified paper representation across all sources."""
    title: str
    authors: list[Author] = field(default_factory=list)
    year: int = 0
    journal: str = ""
    doi: str = ""
    pmid: str = ""
    pmc_id: str = ""
    s2_id: str = ""  # Semantic Scholar ID
    abstract: str = ""
    citation_count: int = 0
    reference_count: int = 0
    is_open_access: bool = False
    pdf_url: str = ""
    source: str = ""  # Which API this came from
    relevance_score: float = 0.0

    @property
    def author_et_al(self) -> str:
        """Get first author et al. format."""
        if not self.authors:
            return "Unknown"
        first = self.authors[0].last_name
        if len(self.authors) > 2:
            return f"{first} et al."
        elif len(self.authors) == 2:
            return f"{first} and {self.authors[1].last_name}"
        return first

    @property
    def identifier(self) -> str:
        """Get best available identifier."""
        return self.doi or self.pmid or self.s2_id or self.pmc_id

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "title": self.title,
            "authors": [a.name for a in self.authors],
            "year": self.year,
            "journal": self.journal,
            "doi": self.doi,
            "pmid": self.pmid,
            "pmc_id": self.pmc_id,
            "s2_id": self.s2_id,
            "citation_count": self.citation_count,
            "is_open_access": self.is_open_access,
            "source": self.source,
        }


@dataclass
class SearchResults:
    """Results from a literature search."""
    papers: list[Paper] = field(default_factory=list)
    query: str = ""
    total_found: int = 0
    sources_searched: list[str] = field(default_factory=list)

    def to_agent_summary(self, max_papers: int = 15) -> str:
        """Format results for the agent."""
        lines = [
            f"**Literature Search Results**",
            f"Query: {self.query}",
            f"Sources: {', '.join(self.sources_searched)}",
            f"Total found: {self.total_found} (showing top {min(len(self.papers), max_papers)})",
            "",
        ]

        for i, paper in enumerate(self.papers[:max_papers], 1):
            oa = " [OA]" if paper.is_open_access else ""
            lines.append(
                f"{i}. **{paper.title}**{oa}\n"
                f"   {paper.author_et_al} ({paper.year}) | {paper.journal}\n"
                f"   Citations: {paper.citation_count} | DOI: {paper.doi or 'N/A'} | PMID: {paper.pmid or 'N/A'}"
            )
            if paper.abstract:
                abstract_preview = paper.abstract[:200] + "..." if len(paper.abstract) > 200 else paper.abstract
                lines.append(f"   > {abstract_preview}")
            lines.append("")

        return "\n".join(lines)


# ═══════════════════════════════════════════════════════════════════
# BASE CLIENT
# ═══════════════════════════════════════════════════════════════════

class BaseLiteratureClient:
    """Base class for literature API clients."""

    def __init__(self, rate_limit_delay: float = 0.34):
        self._last_request = 0.0
        self._rate_limit_delay = rate_limit_delay

    def _rate_limit(self):
        """Enforce rate limiting."""
        elapsed = time.time() - self._last_request
        if elapsed < self._rate_limit_delay:
            time.sleep(self._rate_limit_delay - elapsed)
        self._last_request = time.time()

    def _fetch_json(self, url: str, headers: dict = None) -> dict | None:
        """Fetch JSON from URL with error handling."""
        self._rate_limit()
        try:
            req = urllib.request.Request(url, headers=headers or {})
            with urllib.request.urlopen(req, timeout=30) as response:
                return json.loads(response.read().decode("utf-8"))
        except Exception as e:
            print(f"[{self.__class__.__name__}] Request failed: {e}")
            return None


# ═══════════════════════════════════════════════════════════════════
# PUBMED CLIENT (via NCBI E-utilities)
# ═══════════════════════════════════════════════════════════════════

class PubMedClient(BaseLiteratureClient):
    """PubMed search via NCBI E-utilities."""

    BASE_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"

    def __init__(self, api_key: str = None, email: str = None):
        # NCBI: 3 req/s without key, 10 with key
        delay = 0.1 if api_key else 0.34
        super().__init__(rate_limit_delay=delay)
        self.api_key = api_key
        self.email = email

    def _build_url(self, endpoint: str, params: dict) -> str:
        """Build URL with common parameters."""
        if self.api_key:
            params["api_key"] = self.api_key
        if self.email:
            params["email"] = self.email
        params["retmode"] = "json"
        query = urllib.parse.urlencode(params)
        return f"{self.BASE_URL}/{endpoint}.fcgi?{query}"

    def search(self, query: str, max_results: int = 20,
               year_from: int = None, year_to: int = None) -> list[Paper]:
        """Search PubMed and return papers."""
        # Build date range
        date_range = ""
        if year_from or year_to:
            start = year_from or 1900
            end = year_to or datetime.now().year
            date_range = f" AND {start}:{end}[dp]"

        # Search
        url = self._build_url("esearch", {
            "db": "pubmed",
            "term": query + date_range,
            "retmax": max_results,
            "sort": "relevance",
        })
        data = self._fetch_json(url)
        if not data or "esearchresult" not in data:
            return []

        ids = data["esearchresult"].get("idlist", [])
        if not ids:
            return []

        # Fetch details
        return self._fetch_papers(ids)

    def _fetch_papers(self, pmids: list[str]) -> list[Paper]:
        """Fetch paper details by PMIDs."""
        url = self._build_url("esummary", {
            "db": "pubmed",
            "id": ",".join(pmids),
        })
        data = self._fetch_json(url)
        if not data or "result" not in data:
            return []

        papers = []
        for pmid in pmids:
            if pmid not in data["result"]:
                continue
            item = data["result"][pmid]

            # Parse authors
            authors = []
            for auth in item.get("authors", []):
                authors.append(Author(name=auth.get("name", "")))

            # Extract DOI from articleids
            doi = ""
            for aid in item.get("articleids", []):
                if aid.get("idtype") == "doi":
                    doi = aid.get("value", "")
                    break

            papers.append(Paper(
                title=item.get("title", ""),
                authors=authors,
                year=int(item.get("pubdate", "0")[:4]) if item.get("pubdate") else 0,
                journal=item.get("source", ""),
                doi=doi,
                pmid=pmid,
                source="pubmed",
            ))

        return papers

    def get_paper(self, pmid: str) -> Paper | None:
        """Get a single paper by PMID."""
        papers = self._fetch_papers([pmid])
        return papers[0] if papers else None


# ═══════════════════════════════════════════════════════════════════
# SEMANTIC SCHOLAR CLIENT
# ═══════════════════════════════════════════════════════════════════

class SemanticScholarClient(BaseLiteratureClient):
    """Semantic Scholar API client."""

    BASE_URL = "https://api.semanticscholar.org/graph/v1"

    def __init__(self, api_key: str = None):
        # S2: 100 req/5min without key = ~0.3 req/s
        super().__init__(rate_limit_delay=0.5)
        self.api_key = api_key
        self.headers = {"x-api-key": api_key} if api_key else {}

    def search(self, query: str, max_results: int = 20,
               year_from: int = None, year_to: int = None) -> list[Paper]:
        """Search Semantic Scholar."""
        params = {
            "query": query,
            "limit": min(max_results, 100),
            "fields": "paperId,title,authors,year,venue,citationCount,referenceCount,isOpenAccess,openAccessPdf,externalIds,abstract",
        }
        if year_from:
            params["year"] = f"{year_from}-" + (str(year_to) if year_to else "")

        url = f"{self.BASE_URL}/paper/search?" + urllib.parse.urlencode(params)
        data = self._fetch_json(url, self.headers)
        if not data or "data" not in data:
            return []

        return [self._parse_paper(p) for p in data["data"]]

    def _parse_paper(self, data: dict) -> Paper:
        """Parse S2 paper response."""
        authors = [
            Author(name=a.get("name", ""))
            for a in data.get("authors", [])
        ]

        ext_ids = data.get("externalIds", {}) or {}
        oa_pdf = data.get("openAccessPdf", {}) or {}

        return Paper(
            title=data.get("title", ""),
            authors=authors,
            year=data.get("year", 0) or 0,
            journal=data.get("venue", ""),
            doi=ext_ids.get("DOI", ""),
            pmid=ext_ids.get("PubMed", ""),
            s2_id=data.get("paperId", ""),
            abstract=data.get("abstract", "") or "",
            citation_count=data.get("citationCount", 0) or 0,
            reference_count=data.get("referenceCount", 0) or 0,
            is_open_access=data.get("isOpenAccess", False),
            pdf_url=oa_pdf.get("url", "") if oa_pdf else "",
            source="semantic_scholar",
        )

    def get_paper(self, paper_id: str) -> Paper | None:
        """Get paper by S2 ID or DOI."""
        url = f"{self.BASE_URL}/paper/{paper_id}?fields=paperId,title,authors,year,venue,citationCount,referenceCount,isOpenAccess,openAccessPdf,externalIds,abstract"
        data = self._fetch_json(url, self.headers)
        return self._parse_paper(data) if data else None

    def get_citations(self, paper_id: str, max_results: int = 20) -> list[Paper]:
        """Get papers that cite this paper."""
        url = f"{self.BASE_URL}/paper/{paper_id}/citations?fields=paperId,title,authors,year,venue,citationCount,externalIds&limit={max_results}"
        data = self._fetch_json(url, self.headers)
        if not data or "data" not in data:
            return []
        return [self._parse_paper(c["citingPaper"]) for c in data["data"] if "citingPaper" in c]

    def get_references(self, paper_id: str, max_results: int = 20) -> list[Paper]:
        """Get papers this paper cites."""
        url = f"{self.BASE_URL}/paper/{paper_id}/references?fields=paperId,title,authors,year,venue,citationCount,externalIds&limit={max_results}"
        data = self._fetch_json(url, self.headers)
        if not data or "data" not in data:
            return []
        return [self._parse_paper(r["citedPaper"]) for r in data["data"] if "citedPaper" in r]

    def get_recommendations(self, paper_id: str, max_results: int = 10) -> list[Paper]:
        """Get recommended papers based on a seed paper."""
        url = f"{self.BASE_URL}/recommendations/v1/papers/forpaper/{paper_id}?fields=paperId,title,authors,year,venue,citationCount,externalIds&limit={max_results}"
        data = self._fetch_json(url, self.headers)
        if not data or "recommendedPapers" not in data:
            return []
        return [self._parse_paper(p) for p in data["recommendedPapers"]]


# ═══════════════════════════════════════════════════════════════════
# EUROPE PMC CLIENT
# ═══════════════════════════════════════════════════════════════════

class EuropePMCClient(BaseLiteratureClient):
    """Europe PMC API client."""

    BASE_URL = "https://www.ebi.ac.uk/europepmc/webservices/rest"

    def __init__(self):
        super().__init__(rate_limit_delay=0.2)

    def search(self, query: str, max_results: int = 20,
               year_from: int = None, year_to: int = None) -> list[Paper]:
        """Search Europe PMC."""
        # Add year filter
        q = query
        if year_from or year_to:
            start = year_from or 1900
            end = year_to or datetime.now().year
            q += f" AND PUB_YEAR:[{start} TO {end}]"

        params = {
            "query": q,
            "format": "json",
            "pageSize": min(max_results, 100),
            "sort": "RELEVANCE",
        }
        url = f"{self.BASE_URL}/search?" + urllib.parse.urlencode(params)
        data = self._fetch_json(url)
        if not data or "resultList" not in data:
            return []

        papers = []
        for item in data["resultList"].get("result", []):
            authors = []
            for auth in (item.get("authorList", {}).get("author", []) or []):
                name = auth.get("fullName", "") or f"{auth.get('firstName', '')} {auth.get('lastName', '')}"
                authors.append(Author(name=name.strip()))

            papers.append(Paper(
                title=item.get("title", ""),
                authors=authors,
                year=int(item.get("pubYear", 0)) if item.get("pubYear") else 0,
                journal=item.get("journalTitle", ""),
                doi=item.get("doi", ""),
                pmid=item.get("pmid", ""),
                pmc_id=item.get("pmcid", ""),
                abstract=item.get("abstractText", "") or "",
                citation_count=int(item.get("citedByCount", 0)) if item.get("citedByCount") else 0,
                is_open_access=item.get("isOpenAccess") == "Y",
                source="europe_pmc",
            ))

        return papers


# ═══════════════════════════════════════════════════════════════════
# CROSSREF CLIENT
# ═══════════════════════════════════════════════════════════════════

class CrossRefClient(BaseLiteratureClient):
    """CrossRef API client."""

    BASE_URL = "https://api.crossref.org/works"

    def __init__(self, email: str = None):
        super().__init__(rate_limit_delay=0.5)
        self.headers = {"User-Agent": f"BioAgent/1.0 (mailto:{email})" if email else "BioAgent/1.0"}

    def search(self, query: str, max_results: int = 20,
               year_from: int = None, year_to: int = None) -> list[Paper]:
        """Search CrossRef."""
        params = {
            "query": query,
            "rows": min(max_results, 100),
            "sort": "relevance",
        }
        if year_from:
            params["filter"] = f"from-pub-date:{year_from}"
        if year_to:
            params["filter"] = params.get("filter", "") + f",until-pub-date:{year_to}"

        url = f"{self.BASE_URL}?" + urllib.parse.urlencode(params)
        data = self._fetch_json(url, self.headers)
        if not data or "message" not in data:
            return []

        papers = []
        for item in data["message"].get("items", []):
            # Parse authors
            authors = []
            for auth in item.get("author", []):
                name = f"{auth.get('given', '')} {auth.get('family', '')}".strip()
                authors.append(Author(name=name))

            # Get year
            year = 0
            if "published-print" in item:
                year = item["published-print"].get("date-parts", [[0]])[0][0]
            elif "published-online" in item:
                year = item["published-online"].get("date-parts", [[0]])[0][0]

            papers.append(Paper(
                title=item.get("title", [""])[0] if item.get("title") else "",
                authors=authors,
                year=year,
                journal=item.get("container-title", [""])[0] if item.get("container-title") else "",
                doi=item.get("DOI", ""),
                citation_count=item.get("is-referenced-by-count", 0),
                source="crossref",
            ))

        return papers

    def get_by_doi(self, doi: str) -> Paper | None:
        """Get paper by DOI."""
        url = f"{self.BASE_URL}/{urllib.parse.quote(doi, safe='')}"
        data = self._fetch_json(url, self.headers)
        if not data or "message" not in data:
            return None

        item = data["message"]
        authors = []
        for auth in item.get("author", []):
            name = f"{auth.get('given', '')} {auth.get('family', '')}".strip()
            authors.append(Author(name=name))

        year = 0
        if "published-print" in item:
            year = item["published-print"].get("date-parts", [[0]])[0][0]

        return Paper(
            title=item.get("title", [""])[0] if item.get("title") else "",
            authors=authors,
            year=year,
            journal=item.get("container-title", [""])[0] if item.get("container-title") else "",
            doi=item.get("DOI", ""),
            citation_count=item.get("is-referenced-by-count", 0),
            source="crossref",
        )


# ═══════════════════════════════════════════════════════════════════
# BIORXIV CLIENT
# ═══════════════════════════════════════════════════════════════════

class BioRxivClient(BaseLiteratureClient):
    """bioRxiv/medRxiv API client."""

    BASE_URL = "https://api.biorxiv.org"

    def __init__(self):
        super().__init__(rate_limit_delay=0.5)

    def search(self, query: str, max_results: int = 20,
               year_from: int = None, year_to: int = None,
               server: str = "biorxiv") -> list[Paper]:
        """Search bioRxiv or medRxiv."""
        # bioRxiv API is limited - uses date-based content retrieval
        # For keyword search, we use the RSS/API hybrid approach
        # This returns recent preprints matching keywords

        start_date = f"{year_from or 2019}-01-01"
        end_date = f"{year_to or datetime.now().year}-12-31"

        url = f"{self.BASE_URL}/details/{server}/{start_date}/{end_date}/0/json"
        data = self._fetch_json(url)
        if not data or "collection" not in data:
            return []

        # Filter by query terms
        query_terms = query.lower().split()
        papers = []
        for item in data["collection"]:
            title = item.get("title", "").lower()
            abstract = item.get("abstract", "").lower()
            if any(term in title or term in abstract for term in query_terms):
                authors = []
                for auth in item.get("authors", "").split("; "):
                    if auth:
                        authors.append(Author(name=auth))

                papers.append(Paper(
                    title=item.get("title", ""),
                    authors=authors,
                    year=int(item.get("date", "")[:4]) if item.get("date") else 0,
                    journal=f"{server} (preprint)",
                    doi=item.get("doi", ""),
                    abstract=item.get("abstract", ""),
                    is_open_access=True,
                    source=server,
                ))

                if len(papers) >= max_results:
                    break

        return papers


# ═══════════════════════════════════════════════════════════════════
# UNPAYWALL CLIENT (Open Access Detection)
# ═══════════════════════════════════════════════════════════════════

class UnpaywallClient(BaseLiteratureClient):
    """Unpaywall API for finding open access PDFs."""

    BASE_URL = "https://api.unpaywall.org/v2"

    def __init__(self, email: str):
        super().__init__(rate_limit_delay=0.1)
        self.email = email

    def find_oa_pdf(self, doi: str) -> str | None:
        """Find open access PDF URL for a DOI."""
        if not self.email:
            return None

        url = f"{self.BASE_URL}/{urllib.parse.quote(doi, safe='')}?email={self.email}"
        data = self._fetch_json(url)
        if not data:
            return None

        # Check best OA location
        best_oa = data.get("best_oa_location")
        if best_oa and best_oa.get("url_for_pdf"):
            return best_oa["url_for_pdf"]

        # Check all locations
        for loc in data.get("oa_locations", []):
            if loc.get("url_for_pdf"):
                return loc["url_for_pdf"]

        return None


# ═══════════════════════════════════════════════════════════════════
# ORCHESTRATOR
# ═══════════════════════════════════════════════════════════════════

class LiteratureSearchOrchestrator:
    """
    Orchestrates literature search across multiple sources.

    Features:
    - Multi-source search with configurable sources
    - Deduplication by DOI/PMID
    - Ranking by relevance + citations + recency
    - Citation network exploration
    - Paper recommendations
    """

    def __init__(self, ncbi_api_key: str = None, ncbi_email: str = None,
                 s2_api_key: str = None):
        self.pubmed = PubMedClient(api_key=ncbi_api_key, email=ncbi_email)
        self.s2 = SemanticScholarClient(api_key=s2_api_key)
        self.europe_pmc = EuropePMCClient()
        self.crossref = CrossRefClient(email=ncbi_email)
        self.biorxiv = BioRxivClient()
        self.unpaywall = UnpaywallClient(email=ncbi_email or "")

    def search(self, query: str, sources: list[str] = None,
               max_per_source: int = 20,
               year_from: int = None, year_to: int = None) -> SearchResults:
        """
        Search across multiple literature sources.

        Args:
            query: Search query
            sources: List of sources to search (pubmed, semantic_scholar, europe_pmc, crossref, biorxiv)
            max_per_source: Max results per source
            year_from: Filter by publication year (start)
            year_to: Filter by publication year (end)

        Returns:
            SearchResults with deduplicated, ranked papers
        """
        if sources is None:
            sources = ["pubmed", "semantic_scholar", "europe_pmc"]

        all_papers = []

        # Search each source
        for source in sources:
            try:
                if source == "pubmed":
                    papers = self.pubmed.search(query, max_per_source, year_from, year_to)
                elif source == "semantic_scholar":
                    papers = self.s2.search(query, max_per_source, year_from, year_to)
                elif source == "europe_pmc":
                    papers = self.europe_pmc.search(query, max_per_source, year_from, year_to)
                elif source == "crossref":
                    papers = self.crossref.search(query, max_per_source, year_from, year_to)
                elif source == "biorxiv":
                    papers = self.biorxiv.search(query, max_per_source, year_from, year_to)
                else:
                    continue
                all_papers.extend(papers)
            except Exception as e:
                print(f"[Orchestrator] Error searching {source}: {e}")

        # Deduplicate
        deduplicated = self._deduplicate(all_papers)

        # Rank
        ranked = self._rank(deduplicated, query)

        return SearchResults(
            papers=ranked,
            query=query,
            total_found=len(ranked),
            sources_searched=sources,
        )

    def _deduplicate(self, papers: list[Paper]) -> list[Paper]:
        """Deduplicate papers by DOI, PMID, or title."""
        seen = set()
        unique = []

        for paper in papers:
            # Generate unique key
            key = None
            if paper.doi:
                key = f"doi:{paper.doi.lower()}"
            elif paper.pmid:
                key = f"pmid:{paper.pmid}"
            else:
                # Normalize title
                normalized = re.sub(r"[^a-z0-9]", "", paper.title.lower())
                key = f"title:{normalized[:100]}"

            if key not in seen:
                seen.add(key)
                unique.append(paper)

        return unique

    def _rank(self, papers: list[Paper], query: str) -> list[Paper]:
        """Rank papers by relevance, citations, and recency."""
        query_terms = set(query.lower().split())
        current_year = datetime.now().year

        for paper in papers:
            score = 0.0

            # Title match (highest weight)
            title_terms = set(paper.title.lower().split())
            title_overlap = len(query_terms & title_terms)
            score += title_overlap * 10

            # Citation score (log scale)
            if paper.citation_count > 0:
                import math
                score += math.log10(paper.citation_count + 1) * 5

            # Recency bonus (papers from last 5 years)
            if paper.year:
                age = current_year - paper.year
                if age <= 5:
                    score += (5 - age) * 2

            paper.relevance_score = score

        return sorted(papers, key=lambda p: p.relevance_score, reverse=True)

    def get_paper(self, identifier: str, id_type: str = "auto") -> Paper | None:
        """
        Get a paper by identifier.

        Args:
            identifier: DOI, PMID, or S2 paper ID
            id_type: One of 'auto', 'doi', 'pmid', 's2'
        """
        if id_type == "auto":
            if identifier.startswith("10."):
                id_type = "doi"
            elif identifier.isdigit():
                id_type = "pmid"
            else:
                id_type = "s2"

        if id_type == "doi":
            # Try Semantic Scholar first (has most data)
            paper = self.s2.get_paper(f"DOI:{identifier}")
            if not paper:
                paper = self.crossref.get_by_doi(identifier)
            return paper
        elif id_type == "pmid":
            return self.pubmed.get_paper(identifier)
        elif id_type == "s2":
            return self.s2.get_paper(identifier)

        return None

    def get_citation_network(self, paper_id: str, direction: str = "both",
                             max_results: int = 20) -> SearchResults:
        """
        Get citation network for a paper.

        Args:
            paper_id: Paper identifier (DOI or S2 ID)
            direction: 'citations' (papers citing this), 'references' (papers cited), or 'both'
            max_results: Max papers per direction
        """
        papers = []

        # Normalize to S2 format if DOI
        if paper_id.startswith("10."):
            paper_id = f"DOI:{paper_id}"

        if direction in ("citations", "both"):
            papers.extend(self.s2.get_citations(paper_id, max_results))

        if direction in ("references", "both"):
            papers.extend(self.s2.get_references(paper_id, max_results))

        deduplicated = self._deduplicate(papers)

        return SearchResults(
            papers=deduplicated,
            query=f"Citation network for {paper_id}",
            total_found=len(deduplicated),
            sources_searched=["semantic_scholar"],
        )

    def get_recommendations(self, paper_id: str, max_results: int = 10) -> list[Paper]:
        """Get ML-based paper recommendations from Semantic Scholar."""
        if paper_id.startswith("10."):
            paper_id = f"DOI:{paper_id}"
        return self.s2.get_recommendations(paper_id, max_results)

    def find_open_access_pdf(self, doi: str) -> str | None:
        """Find open access PDF for a paper."""
        return self.unpaywall.find_oa_pdf(doi)
