"""
PDB (Protein Data Bank) REST API client for 3D structure queries.

Provides access to protein structures, ligand binding sites,
experimental metadata, and structural annotations.
"""

import json
import time
import urllib.parse
import urllib.request
from dataclasses import dataclass


BASE_URL = "https://data.rcsb.org/rest/v1"
SEARCH_URL = "https://search.rcsb.org/rcsbsearch/v2/query"

# PDB allows reasonable request rates, ~5 requests/second
_last_request_time = 0.0


@dataclass
class PDBResult:
    """Result from a PDB query."""
    data: str
    query: str
    operation: str
    success: bool
    count: int | None = None

    def to_string(self) -> str:
        status = "Success" if self.success else "Failed"
        parts = [f"PDB {self.operation} [{status}]: {self.query}"]
        if self.count is not None:
            parts.append(f"Results: {self.count}")
        parts.append(f"\n{self.data}")
        return "\n".join(parts)


class PDBClient:
    """Client for the RCSB PDB REST API."""

    def __init__(self, max_retries: int = 2):
        self.max_retries = max_retries

    def query(
        self,
        query: str,
        operation: str = "fetch",
        limit: int = 10,
    ) -> PDBResult:
        """
        Execute a PDB query.

        Args:
            query: PDB ID (e.g., '1TUP') or search term
            operation: Operation type (fetch, search, ligands, summary)
            limit: Maximum results for search operations

        Returns:
            PDBResult with the response data
        """
        self._rate_limit()

        if operation == "fetch":
            return self._fetch_entry(query)
        elif operation == "search":
            return self._search(query, limit)
        elif operation == "ligands":
            return self._get_ligands(query)
        elif operation == "summary":
            return self._get_summary(query)
        else:
            return PDBResult(
                data=f"Unknown operation: {operation}. Use fetch, search, ligands, or summary.",
                query=query,
                operation=operation,
                success=False,
            )

    def _fetch_entry(self, pdb_id: str) -> PDBResult:
        """Fetch detailed information for a PDB entry."""
        pdb_id = pdb_id.upper().strip()
        url = f"{BASE_URL}/core/entry/{pdb_id}"
        response = self._request(url)

        if response.startswith("Error"):
            return PDBResult(
                data=response,
                query=pdb_id,
                operation="fetch",
                success=False,
            )

        try:
            data = json.loads(response)
            formatted = self._format_entry(data, pdb_id)
            return PDBResult(
                data=formatted,
                query=pdb_id,
                operation="fetch",
                success=True,
            )
        except (json.JSONDecodeError, KeyError) as e:
            return PDBResult(
                data=f"Error parsing response: {e}\nRaw: {response[:2000]}",
                query=pdb_id,
                operation="fetch",
                success=False,
            )

    def _search(self, query: str, limit: int) -> PDBResult:
        """Search PDB for structures matching a query."""
        # Build search request for text search
        search_request = {
            "query": {
                "type": "terminal",
                "service": "full_text",
                "parameters": {
                    "value": query
                }
            },
            "return_type": "entry",
            "request_options": {
                "results_content_type": ["experimental"],
                "sort": [{"sort_by": "score", "direction": "desc"}],
                "paginate": {"start": 0, "rows": min(limit, 25)}
            }
        }

        try:
            req_data = json.dumps(search_request).encode('utf-8')
            req = urllib.request.Request(
                SEARCH_URL,
                data=req_data,
                headers={
                    "Content-Type": "application/json",
                    "User-Agent": "BioAgent/1.0 (Bioinformatics Agent)",
                },
            )
            with urllib.request.urlopen(req, timeout=30) as resp:
                response = resp.read().decode("utf-8")
        except Exception as e:
            return PDBResult(
                data=f"Error searching PDB: {e}",
                query=query,
                operation="search",
                success=False,
            )

        try:
            data = json.loads(response)
            total = data.get("total_count", 0)
            results = data.get("result_set", [])

            if not results:
                return PDBResult(
                    data="No structures found matching the query.",
                    query=query,
                    operation="search",
                    success=True,
                    count=0,
                )

            # Get summaries for found entries
            pdb_ids = [r.get("identifier", "") for r in results[:limit]]
            formatted_results = []

            for pdb_id in pdb_ids[:10]:  # Limit detailed fetches
                summary = self._get_summary_data(pdb_id)
                if summary:
                    formatted_results.append(summary)

            formatted = "\n---\n".join(formatted_results) if formatted_results else "No details available."

            return PDBResult(
                data=formatted,
                query=query,
                operation="search",
                success=True,
                count=total,
            )
        except (json.JSONDecodeError, KeyError) as e:
            return PDBResult(
                data=f"Error parsing search response: {e}",
                query=query,
                operation="search",
                success=False,
            )

    def _get_ligands(self, pdb_id: str) -> PDBResult:
        """Get ligand/binding site information for a PDB entry."""
        pdb_id = pdb_id.upper().strip()
        url = f"{BASE_URL}/core/entry/{pdb_id}"
        response = self._request(url)

        if response.startswith("Error"):
            return PDBResult(
                data=response,
                query=pdb_id,
                operation="ligands",
                success=False,
            )

        try:
            data = json.loads(response)
            formatted = self._format_ligands(data, pdb_id)
            return PDBResult(
                data=formatted,
                query=pdb_id,
                operation="ligands",
                success=True,
            )
        except (json.JSONDecodeError, KeyError) as e:
            return PDBResult(
                data=f"Error parsing response: {e}",
                query=pdb_id,
                operation="ligands",
                success=False,
            )

    def _get_summary(self, pdb_id: str) -> PDBResult:
        """Get a brief summary of a PDB entry."""
        pdb_id = pdb_id.upper().strip()
        summary = self._get_summary_data(pdb_id)

        if summary:
            return PDBResult(
                data=summary,
                query=pdb_id,
                operation="summary",
                success=True,
            )
        else:
            return PDBResult(
                data=f"Could not retrieve summary for {pdb_id}",
                query=pdb_id,
                operation="summary",
                success=False,
            )

    def _get_summary_data(self, pdb_id: str) -> str | None:
        """Get formatted summary data for a PDB entry."""
        url = f"{BASE_URL}/core/entry/{pdb_id}"
        response = self._request(url)

        if response.startswith("Error"):
            return None

        try:
            data = json.loads(response)

            title = data.get("struct", {}).get("title", "N/A")

            # Experimental method
            method = "N/A"
            exptl = data.get("exptl", [])
            if exptl:
                method = exptl[0].get("method", "N/A")

            # Resolution
            resolution = "N/A"
            refine = data.get("refine", [])
            if refine:
                res = refine[0].get("ls_dres_high")
                if res:
                    resolution = f"{res} Å"

            # Release date
            release_date = data.get("rcsb_accession_info", {}).get("initial_release_date", "N/A")
            if release_date and release_date != "N/A":
                release_date = release_date.split("T")[0]

            # Organism
            organisms = []
            sources = data.get("rcsb_entry_info", {}).get("polymer_entity_count_protein", 0)
            entity_src = data.get("rcsb_entity_source_organism", [])
            for src in entity_src[:3]:
                org = src.get("scientific_name", "")
                if org and org not in organisms:
                    organisms.append(org)
            organism = ", ".join(organisms) if organisms else "N/A"

            return f"""PDB ID: {pdb_id}
Title: {title}
Method: {method}
Resolution: {resolution}
Release Date: {release_date}
Organism: {organism}"""
        except (json.JSONDecodeError, KeyError):
            return None

    def _format_entry(self, data: dict, pdb_id: str) -> str:
        """Format a full PDB entry for display."""
        parts = []

        parts.append(f"PDB ID: {pdb_id}")

        # Title
        title = data.get("struct", {}).get("title", "N/A")
        parts.append(f"Title: {title}")

        # Experimental method and resolution
        exptl = data.get("exptl", [])
        if exptl:
            method = exptl[0].get("method", "N/A")
            parts.append(f"Method: {method}")

        refine = data.get("refine", [])
        if refine:
            resolution = refine[0].get("ls_dres_high")
            if resolution:
                parts.append(f"Resolution: {resolution} Å")
            r_factor = refine[0].get("ls_rfactor_rwork")
            if r_factor:
                parts.append(f"R-factor: {r_factor}")

        # Release date
        release_date = data.get("rcsb_accession_info", {}).get("initial_release_date", "")
        if release_date:
            parts.append(f"Release Date: {release_date.split('T')[0]}")

        # Authors
        audit_authors = data.get("audit_author", [])
        if audit_authors:
            authors = [a.get("name", "") for a in audit_authors[:5]]
            author_str = ", ".join(authors)
            if len(audit_authors) > 5:
                author_str += f" et al. ({len(audit_authors)} authors)"
            parts.append(f"Authors: {author_str}")

        # Citation
        citation = data.get("citation", [])
        if citation:
            cit = citation[0]
            journal = cit.get("rcsb_journal_abbrev", "")
            year = cit.get("year", "")
            if journal and year:
                parts.append(f"Citation: {journal} ({year})")
            pmid = cit.get("pdbx_database_id_PubMed")
            if pmid:
                parts.append(f"PubMed ID: {pmid}")

        # Entity information
        entry_info = data.get("rcsb_entry_info", {})
        polymer_count = entry_info.get("polymer_entity_count", 0)
        protein_count = entry_info.get("polymer_entity_count_protein", 0)
        na_count = entry_info.get("polymer_entity_count_nucleic_acid", 0)
        ligand_count = entry_info.get("nonpolymer_entity_count", 0)

        parts.append(f"\nComposition:")
        parts.append(f"  Polymer entities: {polymer_count} (Protein: {protein_count}, Nucleic acid: {na_count})")
        parts.append(f"  Ligands/small molecules: {ligand_count}")

        # Organism
        entity_src = data.get("rcsb_entity_source_organism", [])
        organisms = []
        for src in entity_src:
            org = src.get("scientific_name", "")
            if org and org not in organisms:
                organisms.append(org)
        if organisms:
            parts.append(f"  Organism(s): {', '.join(organisms[:3])}")

        # Keywords
        keywords = data.get("struct_keywords", {}).get("pdbx_keywords", "")
        if keywords:
            parts.append(f"\nClassification: {keywords}")

        # Assembly info
        assemblies = data.get("rcsb_assembly_info", [])
        if assemblies:
            assembly = assemblies[0] if isinstance(assemblies, list) else assemblies
            polymer_comp = assembly.get("polymer_composition", "")
            if polymer_comp:
                parts.append(f"Assembly: {polymer_comp}")

        return "\n".join(parts)

    def _format_ligands(self, data: dict, pdb_id: str) -> str:
        """Format ligand/binding site information."""
        parts = [f"Ligands and Binding Sites for {pdb_id}"]
        parts.append("-" * 50)

        # Get nonpolymer entities (ligands)
        nonpoly = data.get("rcsb_entry_info", {}).get("nonpolymer_entity_count", 0)

        if nonpoly == 0:
            parts.append("No ligands found in this structure.")
            return "\n".join(parts)

        parts.append(f"Total ligands/small molecules: {nonpoly}")

        # Try to get binding site info
        binding_sites = data.get("rcsb_binding_affinity", [])
        if binding_sites:
            parts.append(f"\nBinding Affinity Data:")
            for site in binding_sites[:10]:
                comp_id = site.get("comp_id", "?")
                affinity = site.get("value", "?")
                unit = site.get("unit", "")
                aff_type = site.get("type", "")
                parts.append(f"  {comp_id}: {aff_type} = {affinity} {unit}")

        # Struct site information
        struct_site = data.get("struct_site", [])
        if struct_site:
            parts.append(f"\nDefined Sites:")
            for site in struct_site[:10]:
                site_id = site.get("id", "?")
                details = site.get("details", "")
                parts.append(f"  {site_id}: {details[:100]}")

        # Get info about small molecule components
        entry_info = data.get("rcsb_entry_info", {})
        if entry_info:
            # Drug-like molecules
            has_drug = entry_info.get("structure_determination_methodology", "")
            parts.append(f"\nStructure Type: {has_drug}" if has_drug else "")

        return "\n".join(parts)

    def _request(self, url: str) -> str:
        """Make an HTTP request to PDB."""
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
                    return f"Error: PDB entry not found (404)"
                else:
                    return f"Error: HTTP {e.code} - {e.reason}"
            except Exception as e:
                if attempt < self.max_retries:
                    time.sleep(0.5)
                    continue
                return f"Error querying PDB: {e}"

        return "Error: Max retries exceeded"

    def _rate_limit(self):
        """Enforce rate limits (~5 requests/second)."""
        global _last_request_time
        min_interval = 0.2  # 5 requests per second
        elapsed = time.time() - _last_request_time
        if elapsed < min_interval:
            time.sleep(min_interval - elapsed)
        _last_request_time = time.time()
