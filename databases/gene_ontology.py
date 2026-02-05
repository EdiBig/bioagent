"""
Gene Ontology (GO) API client via QuickGO.

Provides access to GO terms, annotations, and functional enrichment
for biological process, molecular function, and cellular component.
"""

import json
import time
import urllib.parse
import urllib.request
from dataclasses import dataclass


BASE_URL = "https://www.ebi.ac.uk/QuickGO/services"

# QuickGO allows reasonable request rates
_last_request_time = 0.0


@dataclass
class GOResult:
    """Result from a Gene Ontology query."""
    data: str
    query: str
    operation: str
    success: bool
    count: int | None = None

    def to_string(self) -> str:
        status = "Success" if self.success else "Failed"
        parts = [f"GO {self.operation} [{status}]: {self.query}"]
        if self.count is not None:
            parts.append(f"Results: {self.count}")
        parts.append(f"\n{self.data}")
        return "\n".join(parts)


class GeneOntologyClient:
    """Client for the Gene Ontology via QuickGO API."""

    def __init__(self, max_retries: int = 2):
        self.max_retries = max_retries

    def query(
        self,
        query: str,
        operation: str = "term",
        limit: int = 25,
    ) -> GOResult:
        """
        Execute a GO query.

        Args:
            query: GO ID (GO:0008150), gene symbol, or search term
            operation: Operation type (term, search, annotations, children)
            limit: Maximum results

        Returns:
            GOResult with the response data
        """
        self._rate_limit()

        if operation == "term":
            return self._get_term(query)
        elif operation == "search":
            return self._search(query, limit)
        elif operation == "annotations":
            return self._get_annotations(query, limit)
        elif operation == "children":
            return self._get_children(query)
        else:
            return GOResult(
                data=f"Unknown operation: {operation}. Use term, search, annotations, or children.",
                query=query,
                operation=operation,
                success=False,
            )

    def _get_term(self, go_id: str) -> GOResult:
        """Get details for a GO term."""
        go_id = go_id.upper().strip()
        if not go_id.startswith("GO:"):
            go_id = f"GO:{go_id}"

        url = f"{BASE_URL}/ontology/go/terms/{go_id}"
        response = self._request(url)

        if response.startswith("Error"):
            return GOResult(
                data=response,
                query=go_id,
                operation="term",
                success=False,
            )

        try:
            data = json.loads(response)
            results = data.get("results", [])

            if not results:
                return GOResult(
                    data=f"GO term {go_id} not found.",
                    query=go_id,
                    operation="term",
                    success=False,
                )

            formatted = self._format_term(results[0])
            return GOResult(
                data=formatted,
                query=go_id,
                operation="term",
                success=True,
            )
        except (json.JSONDecodeError, KeyError, IndexError) as e:
            return GOResult(
                data=f"Error parsing response: {e}",
                query=go_id,
                operation="term",
                success=False,
            )

    def _search(self, query: str, limit: int) -> GOResult:
        """Search for GO terms by name or description."""
        encoded_query = urllib.parse.quote(query)
        url = f"{BASE_URL}/ontology/go/search?query={encoded_query}&limit={limit}"
        response = self._request(url)

        if response.startswith("Error"):
            return GOResult(
                data=response,
                query=query,
                operation="search",
                success=False,
            )

        try:
            data = json.loads(response)
            results = data.get("results", [])

            if not results:
                return GOResult(
                    data="No GO terms found matching the query.",
                    query=query,
                    operation="search",
                    success=True,
                    count=0,
                )

            formatted = self._format_search_results(results)
            total = data.get("numberOfHits", len(results))
            return GOResult(
                data=formatted,
                query=query,
                operation="search",
                success=True,
                count=total,
            )
        except (json.JSONDecodeError, KeyError) as e:
            return GOResult(
                data=f"Error parsing response: {e}",
                query=query,
                operation="search",
                success=False,
            )

    def _get_annotations(self, gene_or_protein: str, limit: int) -> GOResult:
        """Get GO annotations for a gene or protein."""
        gene_or_protein = gene_or_protein.strip()
        url = f"{BASE_URL}/annotation/search?geneProductId={gene_or_protein}&limit={limit}"
        response = self._request(url)

        # If that fails, try as gene symbol
        if response.startswith("Error") or '"numberOfHits":0' in response:
            url = f"{BASE_URL}/annotation/search?symbol={gene_or_protein}&taxonId=9606&limit={limit}"
            response = self._request(url)

        if response.startswith("Error"):
            return GOResult(
                data=response,
                query=gene_or_protein,
                operation="annotations",
                success=False,
            )

        try:
            data = json.loads(response)
            results = data.get("results", [])
            total = data.get("numberOfHits", len(results))

            if not results:
                return GOResult(
                    data=f"No GO annotations found for {gene_or_protein}.",
                    query=gene_or_protein,
                    operation="annotations",
                    success=True,
                    count=0,
                )

            formatted = self._format_annotations(results, gene_or_protein)
            return GOResult(
                data=formatted,
                query=gene_or_protein,
                operation="annotations",
                success=True,
                count=total,
            )
        except (json.JSONDecodeError, KeyError) as e:
            return GOResult(
                data=f"Error parsing response: {e}",
                query=gene_or_protein,
                operation="annotations",
                success=False,
            )

    def _get_children(self, go_id: str) -> GOResult:
        """Get child terms for a GO term."""
        go_id = go_id.upper().strip()
        if not go_id.startswith("GO:"):
            go_id = f"GO:{go_id}"

        url = f"{BASE_URL}/ontology/go/terms/{go_id}/children"
        response = self._request(url)

        if response.startswith("Error"):
            return GOResult(
                data=response,
                query=go_id,
                operation="children",
                success=False,
            )

        try:
            data = json.loads(response)
            results = data.get("results", [])

            if not results:
                return GOResult(
                    data=f"No child terms found for {go_id}.",
                    query=go_id,
                    operation="children",
                    success=True,
                    count=0,
                )

            formatted = self._format_children(results, go_id)
            return GOResult(
                data=formatted,
                query=go_id,
                operation="children",
                success=True,
                count=len(results),
            )
        except (json.JSONDecodeError, KeyError) as e:
            return GOResult(
                data=f"Error parsing response: {e}",
                query=go_id,
                operation="children",
                success=False,
            )

    def _format_term(self, term: dict) -> str:
        """Format a GO term."""
        parts = []

        go_id = term.get("id", "N/A")
        name = term.get("name", "N/A")
        aspect = term.get("aspect", "N/A")

        # Map aspect codes to full names
        aspect_map = {
            "biological_process": "Biological Process (BP)",
            "molecular_function": "Molecular Function (MF)",
            "cellular_component": "Cellular Component (CC)",
        }
        aspect_full = aspect_map.get(aspect, aspect)

        parts.append(f"GO Term: {go_id}")
        parts.append(f"Name: {name}")
        parts.append(f"Ontology: {aspect_full}")

        # Definition
        definition = term.get("definition", {}).get("text", "")
        if definition:
            if len(definition) > 500:
                definition = definition[:500] + "..."
            parts.append(f"\nDefinition:\n{definition}")

        # Synonyms
        synonyms = term.get("synonyms", [])
        if synonyms:
            syn_names = [s.get("name", "") for s in synonyms[:5]]
            parts.append(f"\nSynonyms: {', '.join(syn_names)}")

        # Is obsolete?
        if term.get("isObsolete", False):
            parts.append("\n[OBSOLETE TERM]")

        # Children count
        children = term.get("children", [])
        if children:
            parts.append(f"\nChild terms: {len(children)}")

        return "\n".join(parts)

    def _format_search_results(self, results: list) -> str:
        """Format search results."""
        parts = ["GO Term Search Results"]
        parts.append("-" * 50)

        for term in results:
            go_id = term.get("id", "N/A")
            name = term.get("name", "N/A")
            aspect = term.get("aspect", "")

            # Short aspect code
            aspect_short = {"biological_process": "BP", "molecular_function": "MF", "cellular_component": "CC"}.get(aspect, "")

            parts.append(f"\n{go_id}: {name} [{aspect_short}]")

        return "\n".join(parts)

    def _format_annotations(self, annotations: list, gene: str) -> str:
        """Format GO annotations for a gene."""
        parts = [f"GO Annotations for {gene}"]
        parts.append("=" * 50)

        # Group by aspect
        bp = []  # Biological Process
        mf = []  # Molecular Function
        cc = []  # Cellular Component

        for ann in annotations:
            go_id = ann.get("goId", "")
            go_name = ann.get("goName", "")
            aspect = ann.get("goAspect", "")
            evidence = ann.get("goEvidence", "")

            entry = f"{go_id}: {go_name} [{evidence}]"

            if aspect == "biological_process":
                bp.append(entry)
            elif aspect == "molecular_function":
                mf.append(entry)
            elif aspect == "cellular_component":
                cc.append(entry)

        if bp:
            parts.append(f"\nBiological Process ({len(bp)}):")
            for item in bp[:15]:
                parts.append(f"  - {item}")
            if len(bp) > 15:
                parts.append(f"  ... and {len(bp) - 15} more")

        if mf:
            parts.append(f"\nMolecular Function ({len(mf)}):")
            for item in mf[:10]:
                parts.append(f"  - {item}")
            if len(mf) > 10:
                parts.append(f"  ... and {len(mf) - 10} more")

        if cc:
            parts.append(f"\nCellular Component ({len(cc)}):")
            for item in cc[:10]:
                parts.append(f"  - {item}")
            if len(cc) > 10:
                parts.append(f"  ... and {len(cc) - 10} more")

        return "\n".join(parts)

    def _format_children(self, children: list, parent_id: str) -> str:
        """Format child terms."""
        parts = [f"Child Terms of {parent_id}"]
        parts.append("-" * 50)

        for child in children:
            child_id = child.get("id", "N/A")
            name = child.get("name", "N/A")
            relation = child.get("relation", "is_a")
            parts.append(f"\n{child_id}: {name}")
            parts.append(f"  Relation: {relation}")

        return "\n".join(parts)

    def _request(self, url: str) -> str:
        """Make an HTTP request to QuickGO."""
        for attempt in range(self.max_retries + 1):
            try:
                req = urllib.request.Request(
                    url,
                    headers={
                        "User-Agent": "BioAgent/1.0 (Bioinformatics Agent)",
                        "Accept": "application/json",
                    },
                )
                with urllib.request.urlopen(req, timeout=30) as resp:
                    return resp.read().decode("utf-8")
            except urllib.error.HTTPError as e:
                if e.code == 404:
                    return f"Error: Entry not found (404)"
                elif e.code == 400:
                    return f"Error: Bad request - check query format"
                else:
                    return f"Error: HTTP {e.code} - {e.reason}"
            except Exception as e:
                if attempt < self.max_retries:
                    time.sleep(0.5)
                    continue
                return f"Error querying GO: {e}"

        return "Error: Max retries exceeded"

    def _rate_limit(self):
        """Enforce rate limits."""
        global _last_request_time
        min_interval = 0.2
        elapsed = time.time() - _last_request_time
        if elapsed < min_interval:
            time.sleep(min_interval - elapsed)
        _last_request_time = time.time()
