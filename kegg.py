"""
KEGG REST API client for pathway and compound queries.

Provides access to pathways, genes, compounds, drugs, diseases,
and cross-reference mappings.
"""

import time
import urllib.parse
import urllib.request
from dataclasses import dataclass


BASE_URL = "https://rest.kegg.jp"

# KEGG allows ~10 requests/second
_last_request_time = 0.0


@dataclass
class KEGGResult:
    """Result from a KEGG query."""
    data: str
    operation: str
    database: str | None
    query: str
    success: bool

    def to_string(self) -> str:
        status = "Success" if self.success else "Failed"
        db_info = f" [{self.database}]" if self.database else ""
        return f"KEGG {self.operation}{db_info} [{status}]: {self.query}\n\n{self.data}"


class KEGGClient:
    """Client for the KEGG REST API."""

    def __init__(self, max_retries: int = 2):
        self.max_retries = max_retries

    def query(
        self,
        operation: str,
        database: str | None = None,
        query: str = "",
    ) -> KEGGResult:
        """
        Execute a KEGG query.

        Args:
            operation: Operation type (get, find, link, list, conv)
            database: KEGG database (pathway, genes, compound, drug, disease, etc.)
            query: Search query or entry ID

        Returns:
            KEGGResult with the response data
        """
        self._rate_limit()

        if operation == "get":
            return self._get(query)
        elif operation == "find":
            return self._find(database, query)
        elif operation == "link":
            return self._link(database, query)
        elif operation == "list":
            return self._list(database, query)
        elif operation == "conv":
            return self._conv(database, query)
        else:
            return KEGGResult(
                data=f"Unknown operation: {operation}. Use get, find, link, list, or conv.",
                operation=operation,
                database=database,
                query=query,
                success=False,
            )

    def _get(self, entry: str) -> KEGGResult:
        """
        Get KEGG entry data.

        Entry can be: pathway ID (hsa04110), gene (hsa:7157),
        compound (C00001), drug (D00001), etc.
        """
        if not entry:
            return KEGGResult(
                data="Error: Entry ID required for 'get' operation",
                operation="get",
                database=None,
                query=entry,
                success=False,
            )

        url = f"{BASE_URL}/get/{urllib.parse.quote(entry, safe=':')}"
        response = self._request(url)

        if response.startswith("Error"):
            return KEGGResult(
                data=response,
                operation="get",
                database=None,
                query=entry,
                success=False,
            )

        # Parse and format the response
        formatted = self._format_entry(response, entry)

        return KEGGResult(
            data=formatted,
            operation="get",
            database=None,
            query=entry,
            success=True,
        )

    def _find(self, database: str, query: str) -> KEGGResult:
        """
        Search a KEGG database.

        Databases: pathway, module, ko, genome, genes, compound, drug, disease, etc.
        """
        if not database or not query:
            return KEGGResult(
                data="Error: Both database and query required for 'find' operation",
                operation="find",
                database=database,
                query=query,
                success=False,
            )

        url = f"{BASE_URL}/find/{database}/{urllib.parse.quote(query)}"
        response = self._request(url)

        if response.startswith("Error"):
            return KEGGResult(
                data=response,
                operation="find",
                database=database,
                query=query,
                success=False,
            )

        # Format search results
        lines = response.strip().split("\n")
        if not lines or (len(lines) == 1 and not lines[0].strip()):
            formatted = "No results found."
        else:
            formatted_lines = []
            for line in lines[:50]:  # Limit to 50 results
                parts = line.split("\t")
                if len(parts) >= 2:
                    formatted_lines.append(f"{parts[0]}: {parts[1]}")
                else:
                    formatted_lines.append(line)
            formatted = "\n".join(formatted_lines)
            if len(lines) > 50:
                formatted += f"\n... ({len(lines)} total results)"

        return KEGGResult(
            data=formatted,
            operation="find",
            database=database,
            query=query,
            success=True,
        )

    def _link(self, target_db: str, source: str) -> KEGGResult:
        """
        Get cross-reference links between databases.

        Example: link(pathway, hsa:7157) - get pathways for gene TP53
        """
        if not target_db or not source:
            return KEGGResult(
                data="Error: Both target database and source required for 'link' operation",
                operation="link",
                database=target_db,
                query=source,
                success=False,
            )

        url = f"{BASE_URL}/link/{target_db}/{urllib.parse.quote(source, safe=':')}"
        response = self._request(url)

        if response.startswith("Error"):
            return KEGGResult(
                data=response,
                operation="link",
                database=target_db,
                query=source,
                success=False,
            )

        # Format link results
        lines = response.strip().split("\n")
        if not lines or (len(lines) == 1 and not lines[0].strip()):
            formatted = "No links found."
        else:
            formatted_lines = []
            for line in lines[:100]:  # Limit to 100 links
                parts = line.split("\t")
                if len(parts) >= 2:
                    formatted_lines.append(f"{parts[0]} -> {parts[1]}")
                else:
                    formatted_lines.append(line)
            formatted = "\n".join(formatted_lines)
            if len(lines) > 100:
                formatted += f"\n... ({len(lines)} total links)"

        return KEGGResult(
            data=formatted,
            operation="link",
            database=target_db,
            query=source,
            success=True,
        )

    def _list(self, database: str, organism: str = "") -> KEGGResult:
        """
        List entries in a KEGG database.

        For organism-specific databases, specify organism code (e.g., hsa for human).
        """
        if not database:
            return KEGGResult(
                data="Error: Database required for 'list' operation",
                operation="list",
                database=database,
                query=organism,
                success=False,
            )

        if organism:
            url = f"{BASE_URL}/list/{database}/{organism}"
        else:
            url = f"{BASE_URL}/list/{database}"

        response = self._request(url)

        if response.startswith("Error"):
            return KEGGResult(
                data=response,
                operation="list",
                database=database,
                query=organism,
                success=False,
            )

        # Limit output for large lists
        lines = response.strip().split("\n")
        if len(lines) > 100:
            formatted = "\n".join(lines[:100])
            formatted += f"\n\n... (showing 100 of {len(lines)} entries)"
        else:
            formatted = response

        return KEGGResult(
            data=formatted[:20000],
            operation="list",
            database=database,
            query=organism,
            success=True,
        )

    def _conv(self, target_db: str, source: str) -> KEGGResult:
        """
        Convert identifiers between databases.

        Example: conv(ncbi-geneid, hsa:7157) - convert KEGG gene ID to NCBI gene ID
        """
        if not target_db or not source:
            return KEGGResult(
                data="Error: Both target database and source required for 'conv' operation",
                operation="conv",
                database=target_db,
                query=source,
                success=False,
            )

        url = f"{BASE_URL}/conv/{target_db}/{urllib.parse.quote(source, safe=':')}"
        response = self._request(url)

        if response.startswith("Error"):
            return KEGGResult(
                data=response,
                operation="conv",
                database=target_db,
                query=source,
                success=False,
            )

        # Format conversion results
        lines = response.strip().split("\n")
        if not lines or (len(lines) == 1 and not lines[0].strip()):
            formatted = "No conversion mappings found."
        else:
            formatted_lines = []
            for line in lines[:50]:
                parts = line.split("\t")
                if len(parts) >= 2:
                    formatted_lines.append(f"{parts[0]} = {parts[1]}")
                else:
                    formatted_lines.append(line)
            formatted = "\n".join(formatted_lines)

        return KEGGResult(
            data=formatted,
            operation="conv",
            database=target_db,
            query=source,
            success=True,
        )

    def _format_entry(self, response: str, entry: str) -> str:
        """Format a KEGG entry response for better readability."""
        # KEGG entries are already reasonably formatted
        # Just truncate if too long
        if len(response) > 20000:
            return response[:20000] + "\n... [truncated]"
        return response

    def _request(self, url: str) -> str:
        """Make an HTTP request to KEGG."""
        for attempt in range(self.max_retries + 1):
            try:
                req = urllib.request.Request(
                    url,
                    headers={
                        "User-Agent": "BioAgent/1.0 (Bioinformatics Agent)",
                    },
                )
                with urllib.request.urlopen(req, timeout=30) as resp:
                    return resp.read().decode("utf-8")
            except urllib.error.HTTPError as e:
                if e.code == 404:
                    return f"Error: Entry not found (404)"
                elif e.code == 400:
                    return f"Error: Bad request - check database/query format"
                else:
                    return f"Error: HTTP {e.code} - {e.reason}"
            except Exception as e:
                if attempt < self.max_retries:
                    time.sleep(0.5)
                    continue
                return f"Error querying KEGG: {e}"

        return "Error: Max retries exceeded"

    def _rate_limit(self):
        """Enforce rate limits (~10 requests/second)."""
        global _last_request_time
        min_interval = 0.1  # 10 requests per second
        elapsed = time.time() - _last_request_time
        if elapsed < min_interval:
            time.sleep(min_interval - elapsed)
        _last_request_time = time.time()
