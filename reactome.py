"""
Reactome REST API client for pathway analysis.

Provides access to curated human pathways with mechanistic detail,
pathway enrichment analysis, and reaction information.
"""

import json
import time
import urllib.parse
import urllib.request
from dataclasses import dataclass


BASE_URL = "https://reactome.org/ContentService"
ANALYSIS_URL = "https://reactome.org/AnalysisService"

# Reactome allows reasonable request rates
_last_request_time = 0.0


@dataclass
class ReactomeResult:
    """Result from a Reactome query."""
    data: str
    query: str
    operation: str
    success: bool
    count: int | None = None

    def to_string(self) -> str:
        status = "Success" if self.success else "Failed"
        parts = [f"Reactome {self.operation} [{status}]: {self.query}"]
        if self.count is not None:
            parts.append(f"Results: {self.count}")
        parts.append(f"\n{self.data}")
        return "\n".join(parts)


class ReactomeClient:
    """Client for the Reactome REST API."""

    def __init__(self, max_retries: int = 2):
        self.max_retries = max_retries

    def query(
        self,
        query: str,
        operation: str = "pathway",
        species: str = "Homo sapiens",
        limit: int = 20,
    ) -> ReactomeResult:
        """
        Execute a Reactome query.

        Args:
            query: Pathway ID (R-HSA-...), gene symbol, or search term
            operation: Operation type (pathway, search, genes, enrichment)
            species: Species name (default: Homo sapiens)
            limit: Maximum results for search

        Returns:
            ReactomeResult with the response data
        """
        self._rate_limit()

        if operation == "pathway":
            return self._get_pathway(query)
        elif operation == "search":
            return self._search(query, species, limit)
        elif operation == "genes":
            return self._get_pathways_for_gene(query, species)
        elif operation == "reactions":
            return self._get_reactions(query)
        else:
            return ReactomeResult(
                data=f"Unknown operation: {operation}. Use pathway, search, genes, or reactions.",
                query=query,
                operation=operation,
                success=False,
            )

    def _get_pathway(self, pathway_id: str) -> ReactomeResult:
        """Get details for a Reactome pathway."""
        pathway_id = pathway_id.strip()
        url = f"{BASE_URL}/data/pathway/{pathway_id}/containedEvents"
        response = self._request(url)

        # Also get pathway details
        detail_url = f"{BASE_URL}/data/query/{pathway_id}"
        detail_response = self._request(detail_url)

        if response.startswith("Error") and detail_response.startswith("Error"):
            return ReactomeResult(
                data=detail_response,
                query=pathway_id,
                operation="pathway",
                success=False,
            )

        try:
            # Parse pathway details
            details = {}
            if not detail_response.startswith("Error"):
                details = json.loads(detail_response)

            # Parse contained events
            events = []
            if not response.startswith("Error"):
                events = json.loads(response)

            formatted = self._format_pathway(details, events, pathway_id)
            return ReactomeResult(
                data=formatted,
                query=pathway_id,
                operation="pathway",
                success=True,
                count=len(events) if events else None,
            )
        except (json.JSONDecodeError, KeyError) as e:
            return ReactomeResult(
                data=f"Error parsing response: {e}",
                query=pathway_id,
                operation="pathway",
                success=False,
            )

    def _search(self, query: str, species: str, limit: int) -> ReactomeResult:
        """Search Reactome for pathways."""
        encoded_query = urllib.parse.quote(query)
        encoded_species = urllib.parse.quote(species)
        url = f"{BASE_URL}/search/query?query={encoded_query}&species={encoded_species}&types=Pathway&cluster=true"
        response = self._request(url)

        if response.startswith("Error"):
            return ReactomeResult(
                data=response,
                query=query,
                operation="search",
                success=False,
            )

        try:
            data = json.loads(response)
            results = data.get("results", [])

            if not results:
                return ReactomeResult(
                    data="No pathways found matching the query.",
                    query=query,
                    operation="search",
                    success=True,
                    count=0,
                )

            # Extract entries from grouped results
            all_entries = []
            for group in results:
                entries = group.get("entries", [])
                all_entries.extend(entries[:limit])

            formatted = self._format_search_results(all_entries[:limit])
            return ReactomeResult(
                data=formatted,
                query=query,
                operation="search",
                success=True,
                count=len(all_entries),
            )
        except (json.JSONDecodeError, KeyError) as e:
            return ReactomeResult(
                data=f"Error parsing response: {e}",
                query=query,
                operation="search",
                success=False,
            )

    def _get_pathways_for_gene(self, gene: str, species: str) -> ReactomeResult:
        """Get all pathways containing a gene using search API."""
        gene = gene.upper().strip()
        encoded_gene = urllib.parse.quote(gene)
        encoded_species = urllib.parse.quote(species)
        url = f"{BASE_URL}/search/query?query={encoded_gene}&species={encoded_species}&types=Pathway&cluster=true"
        response = self._request(url)

        if response.startswith("Error"):
            return ReactomeResult(
                data=response,
                query=gene,
                operation="genes",
                success=False,
            )

        try:
            data = json.loads(response)
            results = data.get("results", [])

            if not results:
                return ReactomeResult(
                    data=f"No pathways found for gene {gene}.",
                    query=gene,
                    operation="genes",
                    success=True,
                    count=0,
                )

            # Extract entries from grouped results
            all_entries = []
            for group in results:
                entries = group.get("entries", [])
                all_entries.extend(entries)

            formatted = self._format_gene_pathways_search(all_entries, gene)
            return ReactomeResult(
                data=formatted,
                query=gene,
                operation="genes",
                success=True,
                count=len(all_entries),
            )
        except (json.JSONDecodeError, KeyError) as e:
            return ReactomeResult(
                data=f"Error parsing response: {e}",
                query=gene,
                operation="genes",
                success=False,
            )

    def _get_reactions(self, pathway_id: str) -> ReactomeResult:
        """Get reactions within a pathway."""
        pathway_id = pathway_id.strip()
        url = f"{BASE_URL}/data/pathway/{pathway_id}/containedEvents"
        response = self._request(url)

        if response.startswith("Error"):
            return ReactomeResult(
                data=response,
                query=pathway_id,
                operation="reactions",
                success=False,
            )

        try:
            data = json.loads(response)
            reactions = [e for e in data if e.get("schemaClass") == "Reaction"]

            formatted = self._format_reactions(reactions, pathway_id)
            return ReactomeResult(
                data=formatted,
                query=pathway_id,
                operation="reactions",
                success=True,
                count=len(reactions),
            )
        except (json.JSONDecodeError, KeyError) as e:
            return ReactomeResult(
                data=f"Error parsing response: {e}",
                query=pathway_id,
                operation="reactions",
                success=False,
            )

    def _format_pathway(self, details: dict, events: list, pathway_id: str) -> str:
        """Format pathway details."""
        parts = []

        name = details.get("displayName", pathway_id)
        parts.append(f"Reactome Pathway: {name}")
        parts.append(f"ID: {pathway_id}")

        # Species
        species = details.get("speciesName", "N/A")
        parts.append(f"Species: {species}")

        # Summation (description)
        summation = details.get("summation", [])
        if summation:
            desc = summation[0].get("text", "")[:500]
            if desc:
                parts.append(f"\nDescription:\n{desc}")

        # Compartments
        compartments = details.get("compartment", [])
        if compartments and isinstance(compartments, list):
            comp_names = [c.get("displayName", "") for c in compartments[:5] if isinstance(c, dict)]
            if comp_names:
                parts.append(f"\nCompartments: {', '.join(comp_names)}")

        # Sub-pathways and reactions
        if events and isinstance(events, list):
            sub_pathways = [e for e in events if isinstance(e, dict) and e.get("schemaClass") == "Pathway"]
            reactions = [e for e in events if isinstance(e, dict) and e.get("schemaClass") == "Reaction"]

            if sub_pathways:
                parts.append(f"\nSub-pathways ({len(sub_pathways)}):")
                for sp in sub_pathways[:10]:
                    sp_id = sp.get("stId", "")
                    sp_name = sp.get("displayName", "")
                    parts.append(f"  - {sp_id}: {sp_name}")

            if reactions:
                parts.append(f"\nReactions ({len(reactions)}):")
                for r in reactions[:10]:
                    r_name = r.get("displayName", "")
                    parts.append(f"  - {r_name}")

        # Literature references
        lit_refs = details.get("literatureReference", [])
        if lit_refs:
            parts.append(f"\nReferences ({len(lit_refs)}):")
            for ref in lit_refs[:3]:
                title = ref.get("title", "")
                pubmed = ref.get("pubMedIdentifier", "")
                if title:
                    parts.append(f"  - {title[:80]}{'...' if len(title) > 80 else ''}")
                    if pubmed:
                        parts.append(f"    PMID: {pubmed}")

        return "\n".join(parts)

    def _format_search_results(self, entries: list) -> str:
        """Format search results."""
        parts = ["Reactome Pathway Search Results"]
        parts.append("-" * 50)

        for entry in entries:
            st_id = entry.get("stId", "N/A")
            name = entry.get("name", "N/A")
            species = entry.get("species", [""])[0] if entry.get("species") else ""

            parts.append(f"\n{st_id}: {name}")
            if species:
                parts.append(f"  Species: {species}")

        return "\n".join(parts)

    def _format_gene_pathways(self, pathways: list, gene: str) -> str:
        """Format pathways for a gene."""
        parts = [f"Reactome Pathways for {gene}"]
        parts.append("-" * 50)

        # Group by top-level pathway
        for pathway in pathways[:25]:
            st_id = pathway.get("stId", "")
            name = pathway.get("displayName", "")
            species = pathway.get("speciesName", "")

            parts.append(f"\n{st_id}: {name}")
            if species:
                parts.append(f"  Species: {species}")

        if len(pathways) > 25:
            parts.append(f"\n... and {len(pathways) - 25} more pathways")

        return "\n".join(parts)

    def _format_gene_pathways_search(self, entries: list, gene: str) -> str:
        """Format pathways for a gene from search results."""
        parts = [f"Reactome Pathways for {gene}"]
        parts.append("-" * 50)

        import re
        for entry in entries[:25]:
            st_id = entry.get("stId", "N/A")
            # Remove HTML highlighting tags from name
            name = entry.get("name", "N/A")
            name = re.sub(r'<[^>]+>', '', name)
            species = entry.get("species", [""])[0] if entry.get("species") else ""

            parts.append(f"\n{st_id}: {name}")
            if species:
                parts.append(f"  Species: {species}")

        if len(entries) > 25:
            parts.append(f"\n... and {len(entries) - 25} more pathways")

        return "\n".join(parts)

    def _format_reactions(self, reactions: list, pathway_id: str) -> str:
        """Format reactions in a pathway."""
        parts = [f"Reactions in {pathway_id}"]
        parts.append("-" * 50)

        for rxn in reactions[:20]:
            name = rxn.get("displayName", "N/A")
            st_id = rxn.get("stId", "")
            parts.append(f"\n{st_id}: {name}")

        if len(reactions) > 20:
            parts.append(f"\n... and {len(reactions) - 20} more reactions")

        return "\n".join(parts)

    def _request(self, url: str) -> str:
        """Make an HTTP request to Reactome."""
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
                else:
                    return f"Error: HTTP {e.code} - {e.reason}"
            except Exception as e:
                if attempt < self.max_retries:
                    time.sleep(0.5)
                    continue
                return f"Error querying Reactome: {e}"

        return "Error: Max retries exceeded"

    def _rate_limit(self):
        """Enforce rate limits."""
        global _last_request_time
        min_interval = 0.2
        elapsed = time.time() - _last_request_time
        if elapsed < min_interval:
            time.sleep(min_interval - elapsed)
        _last_request_time = time.time()
