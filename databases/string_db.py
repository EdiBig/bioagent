"""
STRING database API client for protein-protein interactions.

Provides access to protein interaction networks, functional enrichment,
interaction scores, and homology mapping.
"""

import json
import time
import urllib.parse
import urllib.request
from dataclasses import dataclass


BASE_URL = "https://string-db.org/api"

# STRING: be conservative, ~1 request/second
_last_request_time = 0.0


@dataclass
class STRINGResult:
    """Result from a STRING query."""
    data: str
    proteins: str
    operation: str
    success: bool
    count: int | None = None

    def to_string(self) -> str:
        status = "Success" if self.success else "Failed"
        parts = [f"STRING {self.operation} [{status}]: {self.proteins}"]
        if self.count is not None:
            parts.append(f"Results: {self.count}")
        parts.append(f"\n{self.data}")
        return "\n".join(parts)


class STRINGClient:
    """Client for the STRING database API."""

    def __init__(self, max_retries: int = 2):
        self.max_retries = max_retries

    def query(
        self,
        proteins: str | list[str],
        operation: str = "network",
        species: int = 9606,  # Human by default
        score_threshold: int = 400,
        limit: int = 25,
    ) -> STRINGResult:
        """
        Execute a STRING query.

        Args:
            proteins: Protein identifier(s) - gene symbol or STRING ID
            operation: Operation type (network, interactions, enrichment, map_ids)
            species: NCBI taxonomy ID (9606=human, 10090=mouse, etc.)
            score_threshold: Minimum interaction score (0-1000)
            limit: Maximum number of interactors to return

        Returns:
            STRINGResult with the response data
        """
        self._rate_limit()

        # Convert to list if string
        if isinstance(proteins, str):
            proteins_list = [p.strip() for p in proteins.split(",")]
        else:
            proteins_list = proteins

        proteins_str = ", ".join(proteins_list[:10])  # Limit display

        if operation == "network":
            return self._get_network(proteins_list, species, score_threshold, limit)
        elif operation == "interactions":
            return self._get_interactions(proteins_list, species, score_threshold, limit)
        elif operation == "enrichment":
            return self._get_enrichment(proteins_list, species)
        elif operation == "map_ids":
            return self._map_ids(proteins_list, species)
        else:
            return STRINGResult(
                data=f"Unknown operation: {operation}. Use network, interactions, enrichment, or map_ids.",
                proteins=proteins_str,
                operation=operation,
                success=False,
            )

    def _get_network(
        self, proteins: list[str], species: int, score_threshold: int, limit: int
    ) -> STRINGResult:
        """Get the interaction network for given proteins."""
        proteins_str = "%0d".join(proteins)

        params = {
            "identifiers": proteins_str,
            "species": species,
            "required_score": score_threshold,
            "limit": limit,
            "caller_identity": "BioAgent",
        }

        url = f"{BASE_URL}/json/network?{urllib.parse.urlencode(params)}"
        response = self._request(url)

        if response.startswith("Error"):
            return STRINGResult(
                data=response,
                proteins=", ".join(proteins),
                operation="network",
                success=False,
            )

        try:
            data = json.loads(response)
            if not data:
                return STRINGResult(
                    data="No interactions found for the given proteins.",
                    proteins=", ".join(proteins),
                    operation="network",
                    success=True,
                    count=0,
                )

            formatted = self._format_network(data)
            return STRINGResult(
                data=formatted,
                proteins=", ".join(proteins),
                operation="network",
                success=True,
                count=len(data),
            )
        except json.JSONDecodeError as e:
            return STRINGResult(
                data=f"Error parsing response: {e}\nRaw: {response[:1000]}",
                proteins=", ".join(proteins),
                operation="network",
                success=False,
            )

    def _get_interactions(
        self, proteins: list[str], species: int, score_threshold: int, limit: int
    ) -> STRINGResult:
        """Get interaction partners for given proteins."""
        proteins_str = "%0d".join(proteins)

        params = {
            "identifiers": proteins_str,
            "species": species,
            "required_score": score_threshold,
            "limit": limit,
            "caller_identity": "BioAgent",
        }

        url = f"{BASE_URL}/json/interaction_partners?{urllib.parse.urlencode(params)}"
        response = self._request(url)

        if response.startswith("Error"):
            return STRINGResult(
                data=response,
                proteins=", ".join(proteins),
                operation="interactions",
                success=False,
            )

        try:
            data = json.loads(response)
            if not data:
                return STRINGResult(
                    data="No interaction partners found.",
                    proteins=", ".join(proteins),
                    operation="interactions",
                    success=True,
                    count=0,
                )

            formatted = self._format_interactions(data)
            return STRINGResult(
                data=formatted,
                proteins=", ".join(proteins),
                operation="interactions",
                success=True,
                count=len(data),
            )
        except json.JSONDecodeError as e:
            return STRINGResult(
                data=f"Error parsing response: {e}\nRaw: {response[:1000]}",
                proteins=", ".join(proteins),
                operation="interactions",
                success=False,
            )

    def _get_enrichment(self, proteins: list[str], species: int) -> STRINGResult:
        """Get functional enrichment analysis for a set of proteins."""
        proteins_str = "%0d".join(proteins)

        params = {
            "identifiers": proteins_str,
            "species": species,
            "caller_identity": "BioAgent",
        }

        url = f"{BASE_URL}/json/enrichment?{urllib.parse.urlencode(params)}"
        response = self._request(url)

        if response.startswith("Error"):
            return STRINGResult(
                data=response,
                proteins=", ".join(proteins),
                operation="enrichment",
                success=False,
            )

        try:
            data = json.loads(response)
            if not data:
                return STRINGResult(
                    data="No enrichment results found.",
                    proteins=", ".join(proteins),
                    operation="enrichment",
                    success=True,
                    count=0,
                )

            formatted = self._format_enrichment(data)
            return STRINGResult(
                data=formatted,
                proteins=", ".join(proteins),
                operation="enrichment",
                success=True,
                count=len(data),
            )
        except json.JSONDecodeError as e:
            return STRINGResult(
                data=f"Error parsing response: {e}\nRaw: {response[:1000]}",
                proteins=", ".join(proteins),
                operation="enrichment",
                success=False,
            )

    def _map_ids(self, proteins: list[str], species: int) -> STRINGResult:
        """Map protein identifiers to STRING IDs."""
        proteins_str = "%0d".join(proteins)

        params = {
            "identifiers": proteins_str,
            "species": species,
            "limit": 1,  # Best match only
            "caller_identity": "BioAgent",
        }

        url = f"{BASE_URL}/json/get_string_ids?{urllib.parse.urlencode(params)}"
        response = self._request(url)

        if response.startswith("Error"):
            return STRINGResult(
                data=response,
                proteins=", ".join(proteins),
                operation="map_ids",
                success=False,
            )

        try:
            data = json.loads(response)
            if not data:
                return STRINGResult(
                    data="Could not map any identifiers to STRING IDs.",
                    proteins=", ".join(proteins),
                    operation="map_ids",
                    success=True,
                    count=0,
                )

            formatted_lines = []
            for entry in data:
                query = entry.get("queryItem", "?")
                string_id = entry.get("stringId", "?")
                preferred = entry.get("preferredName", "?")
                annotation = entry.get("annotation", "")[:100]
                formatted_lines.append(
                    f"{query} -> {string_id} ({preferred})\n   {annotation}"
                )

            formatted = "\n".join(formatted_lines)
            return STRINGResult(
                data=formatted,
                proteins=", ".join(proteins),
                operation="map_ids",
                success=True,
                count=len(data),
            )
        except json.JSONDecodeError as e:
            return STRINGResult(
                data=f"Error parsing response: {e}\nRaw: {response[:1000]}",
                proteins=", ".join(proteins),
                operation="map_ids",
                success=False,
            )

    def _format_network(self, data: list[dict]) -> str:
        """Format network data for display."""
        lines = ["Protein Interaction Network:"]
        lines.append("-" * 50)

        for interaction in data[:50]:  # Limit to 50 interactions
            prot_a = interaction.get("preferredName_A", interaction.get("stringId_A", "?"))
            prot_b = interaction.get("preferredName_B", interaction.get("stringId_B", "?"))
            score = interaction.get("score", 0)

            # Convert score to percentage
            score_pct = int(score * 100) if score <= 1 else score / 10

            lines.append(f"{prot_a} <-> {prot_b}  (score: {score_pct:.0f}%)")

        if len(data) > 50:
            lines.append(f"\n... ({len(data)} total interactions)")

        return "\n".join(lines)

    def _format_interactions(self, data: list[dict]) -> str:
        """Format interaction partners for display."""
        lines = ["Interaction Partners:"]
        lines.append("-" * 50)

        # Group by query protein
        by_query = {}
        for interaction in data:
            prot_a = interaction.get("preferredName_A", interaction.get("stringId_A", "?"))
            prot_b = interaction.get("preferredName_B", interaction.get("stringId_B", "?"))
            score = interaction.get("score", 0)

            if prot_a not in by_query:
                by_query[prot_a] = []
            by_query[prot_a].append((prot_b, score))

        for query_prot, partners in by_query.items():
            lines.append(f"\n{query_prot} interacts with:")
            # Sort by score descending
            partners.sort(key=lambda x: x[1], reverse=True)
            for partner, score in partners[:20]:  # Limit to top 20
                score_pct = int(score * 100) if score <= 1 else score / 10
                lines.append(f"  - {partner} (score: {score_pct:.0f}%)")
            if len(partners) > 20:
                lines.append(f"  ... ({len(partners)} total partners)")

        return "\n".join(lines)

    def _format_enrichment(self, data: list[dict]) -> str:
        """Format enrichment results for display."""
        lines = ["Functional Enrichment Analysis:"]
        lines.append("-" * 50)

        # Group by category
        by_category = {}
        for entry in data:
            category = entry.get("category", "Other")
            if category not in by_category:
                by_category[category] = []
            by_category[category].append(entry)

        # Sort categories by relevance
        category_order = ["Process", "Component", "Function", "KEGG", "Reactome", "Pfam", "InterPro"]

        for category in category_order:
            if category not in by_category:
                continue

            entries = by_category[category]
            lines.append(f"\n{category}:")

            # Sort by FDR/p-value
            entries.sort(key=lambda x: x.get("fdr", 1))

            for entry in entries[:10]:  # Top 10 per category
                term = entry.get("term", entry.get("description", "?"))
                fdr = entry.get("fdr", 1)
                gene_count = entry.get("number_of_genes", "?")

                # Format FDR
                if fdr < 0.001:
                    fdr_str = f"{fdr:.2e}"
                else:
                    fdr_str = f"{fdr:.4f}"

                lines.append(f"  - {term} (FDR: {fdr_str}, genes: {gene_count})")

            if len(entries) > 10:
                lines.append(f"  ... ({len(entries)} total terms)")

        # Handle remaining categories
        for category, entries in by_category.items():
            if category in category_order:
                continue

            lines.append(f"\n{category}:")
            entries.sort(key=lambda x: x.get("fdr", 1))

            for entry in entries[:5]:  # Top 5 for other categories
                term = entry.get("term", entry.get("description", "?"))
                fdr = entry.get("fdr", 1)
                fdr_str = f"{fdr:.2e}" if fdr < 0.001 else f"{fdr:.4f}"
                lines.append(f"  - {term} (FDR: {fdr_str})")

        return "\n".join(lines)

    def _request(self, url: str) -> str:
        """Make an HTTP request to STRING."""
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
                    return f"Error: Bad request - check protein identifiers and species"
                else:
                    return f"Error: HTTP {e.code} - {e.reason}"
            except Exception as e:
                if attempt < self.max_retries:
                    time.sleep(1)
                    continue
                return f"Error querying STRING: {e}"

        return "Error: Max retries exceeded"

    def _rate_limit(self):
        """Enforce rate limits (~1 request/second)."""
        global _last_request_time
        min_interval = 1.0  # 1 request per second (conservative)
        elapsed = time.time() - _last_request_time
        if elapsed < min_interval:
            time.sleep(min_interval - elapsed)
        _last_request_time = time.time()
