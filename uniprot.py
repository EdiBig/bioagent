"""
UniProt REST API client for protein queries.

Provides access to protein information, sequences, functional annotations,
domains, GO terms, and cross-references.
"""

import json
import time
import urllib.parse
import urllib.request
from dataclasses import dataclass


BASE_URL = "https://rest.uniprot.org"

# UniProt requests: be conservative, ~1 request/second
_last_request_time = 0.0


@dataclass
class UniProtResult:
    """Result from a UniProt query."""
    data: str
    query: str
    operation: str
    success: bool
    count: int | None = None

    def to_string(self) -> str:
        status = "Success" if self.success else "Failed"
        parts = [f"UniProt {self.operation} [{status}]: {self.query}"]
        if self.count is not None:
            parts.append(f"Total results: {self.count}")
        parts.append(f"\n{self.data}")
        return "\n".join(parts)


class UniProtClient:
    """Client for the UniProt REST API."""

    def __init__(self, max_retries: int = 2):
        self.max_retries = max_retries

    def query(
        self,
        query: str,
        operation: str = "search",
        format: str = "json",
        limit: int = 10,
    ) -> UniProtResult:
        """
        Execute a UniProt query.

        Args:
            query: Search query or accession ID
            operation: Operation type (search, fetch, fasta)
            format: Response format (json, fasta, tsv)
            limit: Maximum results for search operations

        Returns:
            UniProtResult with the response data
        """
        self._rate_limit()

        if operation == "search":
            return self._search(query, format, limit)
        elif operation == "fetch":
            return self._fetch(query, format)
        elif operation == "fasta":
            return self._fetch_fasta(query)
        else:
            return UniProtResult(
                data=f"Unknown operation: {operation}. Use search, fetch, or fasta.",
                query=query,
                operation=operation,
                success=False,
            )

    def _search(self, query: str, format: str, limit: int) -> UniProtResult:
        """Search UniProtKB."""
        params = {
            "query": query,
            "format": format,
            "size": min(limit, 25),  # Cap at 25 for reasonable response size
        }

        # Add useful fields for JSON format
        if format == "json":
            params["fields"] = "accession,id,protein_name,gene_names,organism_name,length,cc_function,go,xref_pdb"

        url = f"{BASE_URL}/uniprotkb/search?{urllib.parse.urlencode(params)}"
        response = self._request(url)

        if response.startswith("Error"):
            return UniProtResult(
                data=response,
                query=query,
                operation="search",
                success=False,
            )

        try:
            if format == "json":
                data = json.loads(response)
                results = data.get("results", [])
                count = len(results)

                # Format results nicely
                formatted_results = []
                for entry in results:
                    accession = entry.get("primaryAccession", "N/A")
                    entry_id = entry.get("uniProtkbId", "N/A")
                    protein_name = self._extract_protein_name(entry)
                    gene_names = self._extract_gene_names(entry)
                    organism = entry.get("organism", {}).get("scientificName", "N/A")
                    length = entry.get("sequence", {}).get("length", "N/A")
                    function = self._extract_function(entry)

                    formatted = f"""
Accession: {accession}
Entry ID: {entry_id}
Protein: {protein_name}
Gene(s): {gene_names}
Organism: {organism}
Length: {length} aa
Function: {function}
"""
                    formatted_results.append(formatted.strip())

                formatted_data = "\n---\n".join(formatted_results) if formatted_results else "No results found."
            else:
                formatted_data = response[:20000]
                count = None

            return UniProtResult(
                data=formatted_data,
                query=query,
                operation="search",
                success=True,
                count=count,
            )
        except (json.JSONDecodeError, KeyError) as e:
            return UniProtResult(
                data=f"Error parsing response: {e}\nRaw: {response[:2000]}",
                query=query,
                operation="search",
                success=False,
            )

    def _fetch(self, accession: str, format: str) -> UniProtResult:
        """Fetch a specific UniProt entry by accession."""
        # Clean accession (remove version if present)
        accession = accession.split(".")[0].strip()

        url = f"{BASE_URL}/uniprotkb/{accession}"
        if format == "json":
            url += ".json"
        elif format == "fasta":
            url += ".fasta"

        response = self._request(url)

        if response.startswith("Error"):
            return UniProtResult(
                data=response,
                query=accession,
                operation="fetch",
                success=False,
            )

        try:
            if format == "json":
                data = json.loads(response)
                formatted = self._format_full_entry(data)
            else:
                formatted = response[:20000]

            return UniProtResult(
                data=formatted,
                query=accession,
                operation="fetch",
                success=True,
            )
        except (json.JSONDecodeError, KeyError) as e:
            return UniProtResult(
                data=f"Error parsing response: {e}\nRaw: {response[:2000]}",
                query=accession,
                operation="fetch",
                success=False,
            )

    def _fetch_fasta(self, accession: str) -> UniProtResult:
        """Fetch FASTA sequence for a UniProt entry."""
        accession = accession.split(".")[0].strip()
        url = f"{BASE_URL}/uniprotkb/{accession}.fasta"

        response = self._request(url)

        if response.startswith("Error"):
            return UniProtResult(
                data=response,
                query=accession,
                operation="fasta",
                success=False,
            )

        return UniProtResult(
            data=response[:20000],
            query=accession,
            operation="fasta",
            success=True,
        )

    def _format_full_entry(self, entry: dict) -> str:
        """Format a full UniProt entry for display."""
        parts = []

        accession = entry.get("primaryAccession", "N/A")
        entry_id = entry.get("uniProtkbId", "N/A")
        parts.append(f"Accession: {accession}")
        parts.append(f"Entry ID: {entry_id}")

        # Protein name
        protein_name = self._extract_protein_name(entry)
        parts.append(f"Protein Name: {protein_name}")

        # Gene names
        gene_names = self._extract_gene_names(entry)
        parts.append(f"Gene Name(s): {gene_names}")

        # Organism
        organism = entry.get("organism", {})
        parts.append(f"Organism: {organism.get('scientificName', 'N/A')} (TaxID: {organism.get('taxonId', 'N/A')})")

        # Sequence info
        seq = entry.get("sequence", {})
        parts.append(f"Sequence Length: {seq.get('length', 'N/A')} aa")
        parts.append(f"Molecular Weight: {seq.get('molWeight', 'N/A')} Da")

        # Function
        function = self._extract_function(entry)
        if function != "N/A":
            parts.append(f"\nFunction:\n{function}")

        # GO terms
        go_terms = self._extract_go_terms(entry)
        if go_terms:
            parts.append(f"\nGO Terms:\n{go_terms}")

        # Domains/Features
        features = self._extract_features(entry)
        if features:
            parts.append(f"\nProtein Features:\n{features}")

        # Cross-references (limited)
        xrefs = self._extract_xrefs(entry)
        if xrefs:
            parts.append(f"\nCross-References:\n{xrefs}")

        return "\n".join(parts)

    def _extract_protein_name(self, entry: dict) -> str:
        """Extract protein name from entry."""
        try:
            protein_desc = entry.get("proteinDescription", {})
            rec_name = protein_desc.get("recommendedName", {})
            if rec_name:
                return rec_name.get("fullName", {}).get("value", "N/A")
            sub_names = protein_desc.get("submissionNames", [])
            if sub_names:
                return sub_names[0].get("fullName", {}).get("value", "N/A")
        except (KeyError, IndexError):
            pass
        return "N/A"

    def _extract_gene_names(self, entry: dict) -> str:
        """Extract gene names from entry."""
        try:
            genes = entry.get("genes", [])
            names = []
            for gene in genes:
                if "geneName" in gene:
                    names.append(gene["geneName"].get("value", ""))
                synonyms = gene.get("synonyms", [])
                for syn in synonyms[:2]:  # Limit synonyms
                    names.append(syn.get("value", ""))
            return ", ".join(filter(None, names)) or "N/A"
        except (KeyError, IndexError):
            return "N/A"

    def _extract_function(self, entry: dict) -> str:
        """Extract function annotation from entry."""
        try:
            comments = entry.get("comments", [])
            for comment in comments:
                if comment.get("commentType") == "FUNCTION":
                    texts = comment.get("texts", [])
                    if texts:
                        return texts[0].get("value", "N/A")[:1000]
        except (KeyError, IndexError):
            pass
        return "N/A"

    def _extract_go_terms(self, entry: dict) -> str:
        """Extract GO terms from entry."""
        try:
            xrefs = entry.get("uniProtKBCrossReferences", [])
            go_terms = []
            for xref in xrefs:
                if xref.get("database") == "GO":
                    go_id = xref.get("id", "")
                    props = xref.get("properties", [])
                    term = ""
                    for prop in props:
                        if prop.get("key") == "GoTerm":
                            term = prop.get("value", "")
                            break
                    go_terms.append(f"  {go_id}: {term}")
            return "\n".join(go_terms[:15]) if go_terms else ""  # Limit to 15
        except (KeyError, IndexError):
            return ""

    def _extract_features(self, entry: dict) -> str:
        """Extract protein features/domains."""
        try:
            features = entry.get("features", [])
            formatted = []
            seen_types = set()
            for feat in features:
                feat_type = feat.get("type", "")
                # Only show select feature types, limit duplicates
                if feat_type in ("Domain", "Region", "Active site", "Binding site", "Motif"):
                    if feat_type not in seen_types or feat_type == "Domain":
                        desc = feat.get("description", "")
                        loc = feat.get("location", {})
                        start = loc.get("start", {}).get("value", "?")
                        end = loc.get("end", {}).get("value", "?")
                        formatted.append(f"  {feat_type}: {desc} ({start}-{end})")
                        seen_types.add(feat_type)
            return "\n".join(formatted[:10]) if formatted else ""  # Limit to 10
        except (KeyError, IndexError):
            return ""

    def _extract_xrefs(self, entry: dict) -> str:
        """Extract key cross-references."""
        try:
            xrefs = entry.get("uniProtKBCrossReferences", [])
            formatted = []
            for xref in xrefs:
                db = xref.get("database", "")
                if db in ("PDB", "RefSeq", "Ensembl", "GeneID", "KEGG", "STRING"):
                    xref_id = xref.get("id", "")
                    formatted.append(f"  {db}: {xref_id}")
            return "\n".join(formatted[:10]) if formatted else ""  # Limit to 10
        except (KeyError, IndexError):
            return ""

    def _request(self, url: str) -> str:
        """Make an HTTP request to UniProt."""
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
                if e.code == 429:  # Rate limited
                    retry_after = int(e.headers.get("Retry-After", 2))
                    time.sleep(retry_after)
                    continue
                elif e.code == 404:
                    return f"Error: Entry not found (404)"
                else:
                    return f"Error: HTTP {e.code} - {e.reason}"
            except Exception as e:
                if attempt < self.max_retries:
                    time.sleep(1)
                    continue
                return f"Error querying UniProt: {e}"

        return "Error: Max retries exceeded"

    def _rate_limit(self):
        """Enforce rate limits (~1 request/second)."""
        global _last_request_time
        min_interval = 1.0  # 1 request per second (conservative)
        elapsed = time.time() - _last_request_time
        if elapsed < min_interval:
            time.sleep(min_interval - elapsed)
        _last_request_time = time.time()
