"""
Web search client using DuckDuckGo.

Provides web search capabilities for finding documentation, papers,
tool manuals, and troubleshooting information.
"""

import time
from dataclasses import dataclass


@dataclass
class WebSearchResult:
    """Result from a web search."""
    query: str
    results: list[dict]
    success: bool
    error: str | None = None

    def to_string(self) -> str:
        """Format results for display."""
        if not self.success:
            return f"Web search failed: {self.error}"

        if not self.results:
            return f"No results found for: {self.query}"

        parts = [f"Web Search Results for: {self.query}"]
        parts.append("=" * 60)

        for i, result in enumerate(self.results, 1):
            title = result.get("title", "No title")
            url = result.get("href", result.get("url", "No URL"))
            snippet = result.get("body", result.get("snippet", "No description"))

            # Truncate long snippets
            if len(snippet) > 300:
                snippet = snippet[:300] + "..."

            parts.append(f"\n{i}. {title}")
            parts.append(f"   URL: {url}")
            parts.append(f"   {snippet}")

        return "\n".join(parts)


class WebSearchClient:
    """Web search client using DuckDuckGo."""

    def __init__(self, max_results: int = 10):
        self.max_results = max_results
        self._last_search_time = 0.0

    def search(
        self,
        query: str,
        max_results: int | None = None,
        region: str = "wt-wt",  # Worldwide
        time_range: str | None = None,  # None, 'd' (day), 'w' (week), 'm' (month), 'y' (year)
    ) -> WebSearchResult:
        """
        Search the web using DuckDuckGo.

        Args:
            query: Search query
            max_results: Maximum number of results (default: 10)
            region: Region code (wt-wt = worldwide)
            time_range: Time filter (None, 'd', 'w', 'm', 'y')

        Returns:
            WebSearchResult with search results
        """
        # Rate limiting - be nice to DuckDuckGo
        self._rate_limit()

        if not query or not query.strip():
            return WebSearchResult(
                query=query,
                results=[],
                success=False,
                error="Empty search query"
            )

        max_results = max_results or self.max_results

        try:
            from ddgs import DDGS

            with DDGS() as ddgs:
                results = list(ddgs.text(
                    query,
                    max_results=max_results,
                    region=region,
                    timelimit=time_range,
                ))

            return WebSearchResult(
                query=query,
                results=results,
                success=True,
            )

        except ImportError:
            return WebSearchResult(
                query=query,
                results=[],
                success=False,
                error="ddgs library not installed. Run: pip install ddgs"
            )
        except Exception as e:
            error_msg = str(e)
            # Handle common errors
            if "Ratelimit" in error_msg:
                return WebSearchResult(
                    query=query,
                    results=[],
                    success=False,
                    error="Rate limited by DuckDuckGo. Please wait a moment and try again."
                )
            return WebSearchResult(
                query=query,
                results=[],
                success=False,
                error=f"Search error: {error_msg}"
            )

    def search_news(
        self,
        query: str,
        max_results: int | None = None,
        time_range: str | None = None,
    ) -> WebSearchResult:
        """
        Search news articles using DuckDuckGo.

        Args:
            query: Search query
            max_results: Maximum number of results
            time_range: Time filter (None, 'd', 'w', 'm')

        Returns:
            WebSearchResult with news results
        """
        self._rate_limit()

        if not query or not query.strip():
            return WebSearchResult(
                query=query,
                results=[],
                success=False,
                error="Empty search query"
            )

        max_results = max_results or self.max_results

        try:
            from ddgs import DDGS

            with DDGS() as ddgs:
                results = list(ddgs.news(
                    query,
                    max_results=max_results,
                    timelimit=time_range,
                ))

            # Normalize news result format
            normalized = []
            for r in results:
                normalized.append({
                    "title": r.get("title", ""),
                    "href": r.get("url", ""),
                    "body": r.get("body", ""),
                    "date": r.get("date", ""),
                    "source": r.get("source", ""),
                })

            return WebSearchResult(
                query=query,
                results=normalized,
                success=True,
            )

        except ImportError:
            return WebSearchResult(
                query=query,
                results=[],
                success=False,
                error="ddgs library not installed. Run: pip install ddgs"
            )
        except Exception as e:
            return WebSearchResult(
                query=query,
                results=[],
                success=False,
                error=f"News search error: {e}"
            )

    def _rate_limit(self):
        """Enforce rate limiting to be respectful to DuckDuckGo."""
        min_interval = 1.0  # 1 second between searches
        elapsed = time.time() - self._last_search_time
        if elapsed < min_interval:
            time.sleep(min_interval - elapsed)
        self._last_search_time = time.time()
