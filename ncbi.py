"""
NCBI E-utilities client for querying biological databases.

Supports esearch, efetch, esummary, and einfo operations across
all major NCBI databases (PubMed, Gene, Nucleotide, Protein, etc.).
"""

import json
import time
import urllib.parse
import urllib.request
from dataclasses import dataclass


BASE_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"

# NCBI requests max 3 requests/second without API key, 10 with
_last_request_time = 0.0


@dataclass
class NCBIResult:
    """Result from an NCBI query."""
    data: str
    query: str
    database: str
    operation: str
    count: int | None = None

    def to_string(self) -> str:
        parts = [f"NCBI {self.operation} on '{self.database}' for: {self.query}"]
        if self.count is not None:
            parts.append(f"Total results found: {self.count}")
        parts.append(f"\n{self.data}")
        return "\n".join(parts)


class NCBIClient:
    """Client for NCBI E-utilities."""

    def __init__(self, api_key: str | None = None, email: str | None = None):
        """
        Args:
            api_key: NCBI API key (get one at https://www.ncbi.nlm.nih.gov/account/settings/)
                     Increases rate limit from 3 to 10 requests/second.
            email: Email address (required by NCBI for identification).
        """
        self.api_key = api_key
        self.email = email

    def query(
        self,
        database: str,
        operation: str,
        query: str,
        max_results: int = 10,
        return_type: str = "json",
    ) -> NCBIResult:
        """
        Execute an NCBI E-utilities query.

        Args:
            database: NCBI database name (pubmed, gene, nucleotide, etc.)
            operation: E-utility operation (esearch, efetch, esummary, einfo)
            query: Search term or comma-separated IDs
            max_results: Maximum results to return
            return_type: Return format (json, xml, fasta, gb, abstract)

        Returns:
            NCBIResult with the response data
        """
        self._rate_limit()

        if operation == "esearch":
            return self._esearch(database, query, max_results, return_type)
        elif operation == "efetch":
            return self._efetch(database, query, return_type)
        elif operation == "esummary":
            return self._esummary(database, query, max_results)
        elif operation == "einfo":
            return self._einfo(database)
        else:
            return NCBIResult(
                data=f"Unknown operation: {operation}. Use esearch, efetch, esummary, or einfo.",
                query=query,
                database=database,
                operation=operation,
            )

    def _esearch(
        self, database: str, query: str, max_results: int, return_type: str
    ) -> NCBIResult:
        """Search an NCBI database."""
        params = {
            "db": database,
            "term": query,
            "retmax": max_results,
            "retmode": "json",
            "usehistory": "y",
        }
        response = self._request("esearch.fcgi", params)

        try:
            data = json.loads(response)
            result = data.get("esearchresult", {})
            count = int(result.get("count", 0))
            id_list = result.get("idlist", [])

            # If we got IDs, fetch summaries for convenience
            if id_list and database != "pubmed":
                summary = self._esummary(database, ",".join(id_list), max_results)
                return NCBIResult(
                    data=f"Found {count} results. Top {len(id_list)} IDs: {', '.join(id_list)}\n\nSummaries:\n{summary.data}",
                    query=query,
                    database=database,
                    operation="esearch",
                    count=count,
                )
            elif id_list and database == "pubmed":
                # For PubMed, fetch abstracts
                abstract_result = self._efetch(database, ",".join(id_list[:5]), "abstract")
                return NCBIResult(
                    data=f"Found {count} results. Top {len(id_list)} IDs: {', '.join(id_list)}\n\nAbstracts:\n{abstract_result.data}",
                    query=query,
                    database=database,
                    operation="esearch",
                    count=count,
                )
            else:
                return NCBIResult(
                    data=f"Found {count} results but no IDs returned.",
                    query=query,
                    database=database,
                    operation="esearch",
                    count=count,
                )
        except (json.JSONDecodeError, KeyError) as e:
            return NCBIResult(
                data=f"Error parsing response: {e}\nRaw response:\n{response[:2000]}",
                query=query,
                database=database,
                operation="esearch",
            )

    def _efetch(self, database: str, ids: str, return_type: str) -> NCBIResult:
        """Fetch records by ID."""
        rettype_map = {
            "abstract": ("abstract", "text"),
            "fasta": ("fasta", "text"),
            "gb": ("gb", "text"),
            "xml": ("xml", "xml"),
            "json": ("docsum", "json"),
        }
        rettype, retmode = rettype_map.get(return_type, ("docsum", "json"))

        params = {
            "db": database,
            "id": ids,
            "rettype": rettype,
            "retmode": retmode,
        }
        response = self._request("efetch.fcgi", params)

        return NCBIResult(
            data=response[:20000],  # Truncate very long responses
            query=ids,
            database=database,
            operation="efetch",
        )

    def _esummary(self, database: str, ids: str, max_results: int = 10) -> NCBIResult:
        """Get document summaries."""
        params = {
            "db": database,
            "id": ids,
            "retmode": "json",
        }
        response = self._request("esummary.fcgi", params)

        try:
            data = json.loads(response)
            result = data.get("result", {})
            # Format summaries nicely
            uids = result.get("uids", [])
            summaries = []
            for uid in uids[:max_results]:
                entry = result.get(uid, {})
                summaries.append(json.dumps(entry, indent=2))
            formatted = "\n---\n".join(summaries) if summaries else response[:5000]
        except (json.JSONDecodeError, KeyError):
            formatted = response[:5000]

        return NCBIResult(
            data=formatted,
            query=ids,
            database=database,
            operation="esummary",
        )

    def _einfo(self, database: str) -> NCBIResult:
        """Get database information."""
        params = {"db": database, "retmode": "json"}
        response = self._request("einfo.fcgi", params)

        return NCBIResult(
            data=response[:10000],
            query="",
            database=database,
            operation="einfo",
        )

    def _request(self, endpoint: str, params: dict) -> str:
        """Make an HTTP request to NCBI."""
        if self.api_key:
            params["api_key"] = self.api_key
        if self.email:
            params["email"] = self.email

        url = f"{BASE_URL}/{endpoint}?{urllib.parse.urlencode(params)}"

        try:
            req = urllib.request.Request(
                url,
                headers={"User-Agent": "BioAgent/1.0 (Bioinformatics Agent)"},
            )
            with urllib.request.urlopen(req, timeout=30) as resp:
                return resp.read().decode("utf-8")
        except Exception as e:
            return f"Error querying NCBI: {e}"

    def _rate_limit(self):
        """Enforce NCBI rate limits."""
        global _last_request_time
        min_interval = 0.1 if self.api_key else 0.34  # 10/s or 3/s
        elapsed = time.time() - _last_request_time
        if elapsed < min_interval:
            time.sleep(min_interval - elapsed)
        _last_request_time = time.time()
