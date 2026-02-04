"""
InterPro API client for protein domains and functional sites.

Provides access to protein family classifications, domains,
functional sites, and sequence features.
"""

import json
import time
import urllib.parse
import urllib.request
from dataclasses import dataclass


BASE_URL = "https://www.ebi.ac.uk/interpro/api"

# InterPro allows reasonable request rates
_last_request_time = 0.0


@dataclass
class InterProResult:
    """Result from an InterPro query."""
    data: str
    query: str
    operation: str
    success: bool
    count: int | None = None

    def to_string(self) -> str:
        status = "Success" if self.success else "Failed"
        parts = [f"InterPro {self.operation} [{status}]: {self.query}"]
        if self.count is not None:
            parts.append(f"Results: {self.count}")
        parts.append(f"\n{self.data}")
        return "\n".join(parts)


class InterProClient:
    """Client for the InterPro REST API."""

    def __init__(self, max_retries: int = 2):
        self.max_retries = max_retries

    def query(
        self,
        query: str,
        operation: str = "protein",
        limit: int = 20,
    ) -> InterProResult:
        """
        Execute an InterPro query.

        Args:
            query: UniProt accession, InterPro ID, or search term
            operation: Operation type (protein, entry, search)
            limit: Maximum results for search

        Returns:
            InterProResult with the response data
        """
        self._rate_limit()

        if operation == "protein":
            return self._get_protein_domains(query)
        elif operation == "entry":
            return self._get_entry(query)
        elif operation == "search":
            return self._search(query, limit)
        else:
            return InterProResult(
                data=f"Unknown operation: {operation}. Use protein, entry, or search.",
                query=query,
                operation=operation,
                success=False,
            )

    def _get_protein_domains(self, uniprot_id: str) -> InterProResult:
        """Get all InterPro domains/features for a protein."""
        uniprot_id = uniprot_id.upper().strip()

        # First get protein metadata
        meta_url = f"{BASE_URL}/protein/UniProt/{uniprot_id}"
        meta_response = self._request(meta_url)

        protein_info = {}
        if not meta_response.startswith("Error"):
            try:
                meta_data = json.loads(meta_response)
                protein_info = meta_data.get("metadata", {})
            except json.JSONDecodeError:
                pass

        # Get entries (domains, families) for this protein
        url = f"{BASE_URL}/entry/interpro/protein/UniProt/{uniprot_id}"
        response = self._request(url)

        if response.startswith("Error"):
            return InterProResult(
                data=response,
                query=uniprot_id,
                operation="protein",
                success=False,
            )

        try:
            data = json.loads(response)
            results = data.get("results", [])
            count = data.get("count", len(results))

            formatted = self._format_protein_domains_v2(results, protein_info, uniprot_id)

            return InterProResult(
                data=formatted,
                query=uniprot_id,
                operation="protein",
                success=True,
                count=count,
            )
        except (json.JSONDecodeError, KeyError) as e:
            return InterProResult(
                data=f"Error parsing response: {e}\nRaw: {response[:2000]}",
                query=uniprot_id,
                operation="protein",
                success=False,
            )

    def _get_entry(self, interpro_id: str) -> InterProResult:
        """Get details for an InterPro entry."""
        interpro_id = interpro_id.upper().strip()
        url = f"{BASE_URL}/entry/interpro/{interpro_id}"
        response = self._request(url)

        if response.startswith("Error"):
            return InterProResult(
                data=response,
                query=interpro_id,
                operation="entry",
                success=False,
            )

        try:
            data = json.loads(response)
            formatted = self._format_entry(data)
            return InterProResult(
                data=formatted,
                query=interpro_id,
                operation="entry",
                success=True,
            )
        except (json.JSONDecodeError, KeyError) as e:
            return InterProResult(
                data=f"Error parsing response: {e}\nRaw: {response[:2000]}",
                query=interpro_id,
                operation="entry",
                success=False,
            )

    def _search(self, query: str, limit: int) -> InterProResult:
        """Search InterPro entries by text."""
        encoded_query = urllib.parse.quote(query)
        url = f"{BASE_URL}/entry/interpro?search={encoded_query}&page_size={min(limit, 20)}"
        response = self._request(url)

        if response.startswith("Error"):
            return InterProResult(
                data=response,
                query=query,
                operation="search",
                success=False,
            )

        try:
            data = json.loads(response)
            results = data.get("results", [])
            count = data.get("count", len(results))

            if not results:
                return InterProResult(
                    data="No InterPro entries found matching the query.",
                    query=query,
                    operation="search",
                    success=True,
                    count=0,
                )

            formatted = self._format_search_results(results)
            return InterProResult(
                data=formatted,
                query=query,
                operation="search",
                success=True,
                count=count,
            )
        except (json.JSONDecodeError, KeyError) as e:
            return InterProResult(
                data=f"Error parsing response: {e}\nRaw: {response[:2000]}",
                query=query,
                operation="search",
                success=False,
            )

    def _format_protein_domains_v2(self, results: list, protein_info: dict, uniprot_id: str) -> str:
        """Format protein domain information from entry endpoint."""
        parts = [f"InterPro Domains for {uniprot_id}"]
        parts.append("=" * 50)

        # Protein info
        name = protein_info.get("name", "N/A")
        length = protein_info.get("length", "N/A")
        organism = protein_info.get("source_organism", {}).get("scientificName", "N/A")

        parts.append(f"Protein: {name}")
        parts.append(f"Length: {length} aa")
        parts.append(f"Organism: {organism}")

        if not results:
            parts.append("\nNo InterPro annotations found.")
            return "\n".join(parts)

        # Group by entry type
        families = []
        domains = []
        sites = []
        repeats = []
        homolog_superfamilies = []
        others = []

        for entry in results:
            metadata = entry.get("metadata", {})
            entry_acc = metadata.get("accession", "")
            entry_name = metadata.get("name", "")
            entry_type = metadata.get("type", "").lower()

            # Get locations from proteins data
            proteins = entry.get("proteins", [])
            loc_str = ""
            if proteins:
                locations = proteins[0].get("entry_protein_locations", [])
                if locations:
                    fragments = locations[0].get("fragments", [])
                    if fragments:
                        locs = [f"{f.get('start', '?')}-{f.get('end', '?')}" for f in fragments[:3]]
                        loc_str = f" ({', '.join(locs)})"

            entry_str = f"{entry_acc}: {entry_name}{loc_str}"

            if entry_type == "family":
                families.append(entry_str)
            elif entry_type == "domain":
                domains.append(entry_str)
            elif entry_type in ("active_site", "binding_site", "conserved_site", "site"):
                sites.append(entry_str)
            elif entry_type == "repeat":
                repeats.append(entry_str)
            elif entry_type == "homologous_superfamily":
                homolog_superfamilies.append(entry_str)
            else:
                others.append(f"{entry_str} [{entry_type}]")

        # Output organized by type
        if families:
            parts.append(f"\nProtein Families ({len(families)}):")
            for f in families[:10]:
                parts.append(f"  - {f}")

        if homolog_superfamilies:
            parts.append(f"\nHomologous Superfamilies ({len(homolog_superfamilies)}):")
            for h in homolog_superfamilies[:10]:
                parts.append(f"  - {h}")

        if domains:
            parts.append(f"\nDomains ({len(domains)}):")
            for d in domains[:15]:
                parts.append(f"  - {d}")

        if sites:
            parts.append(f"\nFunctional Sites ({len(sites)}):")
            for s in sites[:10]:
                parts.append(f"  - {s}")

        if repeats:
            parts.append(f"\nRepeats ({len(repeats)}):")
            for r in repeats[:5]:
                parts.append(f"  - {r}")

        if others:
            parts.append(f"\nOther Annotations ({len(others)}):")
            for o in others[:5]:
                parts.append(f"  - {o}")

        return "\n".join(parts)

    def _format_protein_domains(self, data: dict, uniprot_id: str) -> str:
        """Format protein domain information."""
        parts = [f"InterPro Domains for {uniprot_id}"]
        parts.append("=" * 50)

        metadata = data.get("metadata", {})

        # Protein info
        name = metadata.get("name", "N/A")
        length = metadata.get("length", "N/A")
        organism = metadata.get("source_organism", {}).get("scientificName", "N/A")

        parts.append(f"Protein: {name}")
        parts.append(f"Length: {length} aa")
        parts.append(f"Organism: {organism}")

        # Get entries (domains, families, etc.)
        entries = data.get("entry_subset", [])

        if not entries:
            parts.append("\nNo InterPro annotations found.")
            return "\n".join(parts)

        # Group by entry type
        families = []
        domains = []
        sites = []
        repeats = []
        others = []

        for entry in entries:
            entry_acc = entry.get("accession", "")
            entry_name = entry.get("name", "")
            entry_type = entry.get("entry_type", "").lower()

            # Get locations
            locations = entry.get("entry_protein_locations", [])
            loc_str = ""
            if locations:
                fragments = locations[0].get("fragments", [])
                if fragments:
                    locs = [f"{f.get('start', '?')}-{f.get('end', '?')}" for f in fragments[:3]]
                    loc_str = f" ({', '.join(locs)})"

            entry_str = f"{entry_acc}: {entry_name}{loc_str}"

            if entry_type == "family":
                families.append(entry_str)
            elif entry_type == "domain":
                domains.append(entry_str)
            elif entry_type in ("active_site", "binding_site", "conserved_site", "site"):
                sites.append(entry_str)
            elif entry_type == "repeat":
                repeats.append(entry_str)
            else:
                others.append(f"{entry_str} [{entry_type}]")

        # Output organized by type
        if families:
            parts.append(f"\nProtein Families ({len(families)}):")
            for f in families[:10]:
                parts.append(f"  - {f}")

        if domains:
            parts.append(f"\nDomains ({len(domains)}):")
            for d in domains[:15]:
                parts.append(f"  - {d}")

        if sites:
            parts.append(f"\nFunctional Sites ({len(sites)}):")
            for s in sites[:10]:
                parts.append(f"  - {s}")

        if repeats:
            parts.append(f"\nRepeats ({len(repeats)}):")
            for r in repeats[:5]:
                parts.append(f"  - {r}")

        if others:
            parts.append(f"\nOther Annotations ({len(others)}):")
            for o in others[:5]:
                parts.append(f"  - {o}")

        return "\n".join(parts)

    def _format_entry(self, data: dict) -> str:
        """Format an InterPro entry."""
        parts = []

        metadata = data.get("metadata", {})

        accession = metadata.get("accession", "N/A")
        name = metadata.get("name", {})
        if isinstance(name, dict):
            name = name.get("name", "N/A")
        entry_type = metadata.get("type", "N/A")

        parts.append(f"InterPro Entry: {accession}")
        parts.append(f"Name: {name}")
        parts.append(f"Type: {entry_type}")

        # Description
        description = metadata.get("description", [])
        if description and isinstance(description, list):
            desc_text = description[0].get("text", "") if description else ""
            if desc_text:
                # Truncate if too long
                if len(desc_text) > 500:
                    desc_text = desc_text[:500] + "..."
                parts.append(f"\nDescription:\n{desc_text}")

        # GO terms
        go_terms = metadata.get("go_terms", [])
        if go_terms:
            parts.append(f"\nGO Terms ({len(go_terms)}):")
            for go in go_terms[:10]:
                go_id = go.get("identifier", "")
                go_name = go.get("name", "")
                go_cat = go.get("category", {}).get("name", "")
                parts.append(f"  - {go_id}: {go_name} [{go_cat}]")

        # Member databases
        member_dbs = metadata.get("member_databases", {})
        if member_dbs:
            parts.append(f"\nMember Database Signatures:")
            for db, entries in list(member_dbs.items())[:5]:
                for entry_id, entry_name in list(entries.items())[:3]:
                    parts.append(f"  - {db}: {entry_id} ({entry_name})")

        # Counters
        counters = metadata.get("counters", {})
        if counters:
            proteins = counters.get("proteins", 0)
            structures = counters.get("structures", 0)
            taxa = counters.get("taxa", 0)
            parts.append(f"\nStatistics:")
            parts.append(f"  Proteins: {proteins:,}")
            parts.append(f"  Structures: {structures:,}")
            parts.append(f"  Taxa: {taxa:,}")

        return "\n".join(parts)

    def _format_search_results(self, results: list) -> str:
        """Format search results."""
        parts = ["InterPro Search Results"]
        parts.append("-" * 50)

        for entry in results[:20]:
            metadata = entry.get("metadata", {})
            accession = metadata.get("accession", "N/A")
            name = metadata.get("name", "N/A")
            entry_type = metadata.get("type", "")

            # Get protein count
            counters = metadata.get("counters", {})
            protein_count = counters.get("proteins", 0)

            parts.append(f"\n{accession}: {name}")
            parts.append(f"  Type: {entry_type}")
            parts.append(f"  Proteins: {protein_count:,}")

        return "\n".join(parts)

    def _request(self, url: str) -> str:
        """Make an HTTP request to InterPro."""
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
                elif e.code == 204:
                    return "Error: No content found"
                else:
                    return f"Error: HTTP {e.code} - {e.reason}"
            except Exception as e:
                if attempt < self.max_retries:
                    time.sleep(0.5)
                    continue
                return f"Error querying InterPro: {e}"

        return "Error: Max retries exceeded"

    def _rate_limit(self):
        """Enforce rate limits (~5 requests/second)."""
        global _last_request_time
        min_interval = 0.2  # 5 requests per second
        elapsed = time.time() - _last_request_time
        if elapsed < min_interval:
            time.sleep(min_interval - elapsed)
        _last_request_time = time.time()
