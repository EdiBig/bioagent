"""
AlphaFold Database API client for predicted protein structures.

Provides access to AI-predicted 3D protein structures for proteins
that may not have experimental crystal structures.
"""

import json
import time
import urllib.parse
import urllib.request
from dataclasses import dataclass


BASE_URL = "https://alphafold.ebi.ac.uk/api"

# AlphaFold DB allows reasonable request rates
_last_request_time = 0.0


@dataclass
class AlphaFoldResult:
    """Result from an AlphaFold query."""
    data: str
    query: str
    operation: str
    success: bool

    def to_string(self) -> str:
        status = "Success" if self.success else "Failed"
        return f"AlphaFold {self.operation} [{status}]: {self.query}\n\n{self.data}"


class AlphaFoldClient:
    """Client for the AlphaFold Database API."""

    def __init__(self, max_retries: int = 2):
        self.max_retries = max_retries

    def query(
        self,
        query: str,
        operation: str = "prediction",
    ) -> AlphaFoldResult:
        """
        Execute an AlphaFold DB query.

        Args:
            query: UniProt accession (e.g., 'P04637' for p53)
            operation: Operation type (prediction, pae, summary)

        Returns:
            AlphaFoldResult with the response data
        """
        self._rate_limit()

        if operation == "prediction":
            return self._get_prediction(query)
        elif operation == "pae":
            return self._get_pae_summary(query)
        elif operation == "summary":
            return self._get_summary(query)
        else:
            return AlphaFoldResult(
                data=f"Unknown operation: {operation}. Use prediction, pae, or summary.",
                query=query,
                operation=operation,
                success=False,
            )

    def _get_prediction(self, uniprot_id: str) -> AlphaFoldResult:
        """Get AlphaFold prediction details for a UniProt accession."""
        uniprot_id = uniprot_id.upper().strip()
        url = f"{BASE_URL}/prediction/{uniprot_id}"
        response = self._request(url)

        if response.startswith("Error"):
            return AlphaFoldResult(
                data=response,
                query=uniprot_id,
                operation="prediction",
                success=False,
            )

        try:
            data = json.loads(response)
            # AlphaFold returns a list, get first entry
            if isinstance(data, list) and len(data) > 0:
                entry = data[0]
            else:
                entry = data

            formatted = self._format_prediction(entry, uniprot_id)
            return AlphaFoldResult(
                data=formatted,
                query=uniprot_id,
                operation="prediction",
                success=True,
            )
        except (json.JSONDecodeError, KeyError, IndexError) as e:
            return AlphaFoldResult(
                data=f"Error parsing response: {e}\nRaw: {response[:2000]}",
                query=uniprot_id,
                operation="prediction",
                success=False,
            )

    def _get_pae_summary(self, uniprot_id: str) -> AlphaFoldResult:
        """Get Predicted Aligned Error (PAE) summary for quality assessment."""
        uniprot_id = uniprot_id.upper().strip()
        url = f"{BASE_URL}/prediction/{uniprot_id}"
        response = self._request(url)

        if response.startswith("Error"):
            return AlphaFoldResult(
                data=response,
                query=uniprot_id,
                operation="pae",
                success=False,
            )

        try:
            data = json.loads(response)
            if isinstance(data, list) and len(data) > 0:
                entry = data[0]
            else:
                entry = data

            formatted = self._format_pae_info(entry, uniprot_id)
            return AlphaFoldResult(
                data=formatted,
                query=uniprot_id,
                operation="pae",
                success=True,
            )
        except (json.JSONDecodeError, KeyError, IndexError) as e:
            return AlphaFoldResult(
                data=f"Error parsing response: {e}",
                query=uniprot_id,
                operation="pae",
                success=False,
            )

    def _get_summary(self, uniprot_id: str) -> AlphaFoldResult:
        """Get a brief summary of the AlphaFold prediction."""
        uniprot_id = uniprot_id.upper().strip()
        url = f"{BASE_URL}/prediction/{uniprot_id}"
        response = self._request(url)

        if response.startswith("Error"):
            return AlphaFoldResult(
                data=response,
                query=uniprot_id,
                operation="summary",
                success=False,
            )

        try:
            data = json.loads(response)
            if isinstance(data, list) and len(data) > 0:
                entry = data[0]
            else:
                entry = data

            # Brief summary
            entry_id = entry.get("entryId", "N/A")
            gene = entry.get("gene", "N/A")
            organism = entry.get("organismScientificName", "N/A")
            seq_len = entry.get("uniprotEnd", 0) - entry.get("uniprotStart", 0) + 1
            model_url = entry.get("pdbUrl", "N/A")

            # Confidence info
            global_metric = entry.get("globalMetricValue", "N/A")

            summary = f"""AlphaFold Prediction Summary
UniProt: {uniprot_id}
Entry ID: {entry_id}
Gene: {gene}
Organism: {organism}
Sequence Length: {seq_len} residues
Global Confidence (pLDDT): {global_metric}
Structure File: {model_url}"""

            return AlphaFoldResult(
                data=summary,
                query=uniprot_id,
                operation="summary",
                success=True,
            )
        except (json.JSONDecodeError, KeyError, IndexError) as e:
            return AlphaFoldResult(
                data=f"Error parsing response: {e}",
                query=uniprot_id,
                operation="summary",
                success=False,
            )

    def _format_prediction(self, entry: dict, uniprot_id: str) -> str:
        """Format AlphaFold prediction details."""
        parts = []

        entry_id = entry.get("entryId", "N/A")
        parts.append(f"AlphaFold Entry: {entry_id}")
        parts.append(f"UniProt Accession: {uniprot_id}")

        # Gene and organism
        gene = entry.get("gene", "N/A")
        organism = entry.get("organismScientificName", "N/A")
        tax_id = entry.get("taxId", "N/A")
        parts.append(f"Gene: {gene}")
        parts.append(f"Organism: {organism} (TaxID: {tax_id})")

        # Protein info
        uniprot_desc = entry.get("uniprotDescription", "")
        if uniprot_desc:
            parts.append(f"Description: {uniprot_desc}")

        # Sequence range
        start = entry.get("uniprotStart", 1)
        end = entry.get("uniprotEnd", 0)
        seq_len = end - start + 1
        parts.append(f"Modeled Range: {start}-{end} ({seq_len} residues)")

        # Model confidence
        parts.append(f"\nModel Confidence:")
        global_metric = entry.get("globalMetricValue")
        if global_metric:
            parts.append(f"  Global pLDDT: {global_metric:.1f}")
            parts.append(self._interpret_plddt(global_metric))

        # Available files
        parts.append(f"\nAvailable Structure Files:")
        pdb_url = entry.get("pdbUrl")
        cif_url = entry.get("cifUrl")
        pae_url = entry.get("paeImageUrl")

        if pdb_url:
            parts.append(f"  PDB: {pdb_url}")
        if cif_url:
            parts.append(f"  mmCIF: {cif_url}")
        if pae_url:
            parts.append(f"  PAE Image: {pae_url}")

        # Model dates
        model_created = entry.get("modelCreatedDate", "")
        latest_version = entry.get("latestVersion", "")
        if model_created:
            parts.append(f"\nModel Created: {model_created}")
        if latest_version:
            parts.append(f"Version: {latest_version}")

        return "\n".join(parts)

    def _format_pae_info(self, entry: dict, uniprot_id: str) -> str:
        """Format PAE (Predicted Aligned Error) information."""
        parts = [f"AlphaFold PAE Information for {uniprot_id}"]
        parts.append("-" * 50)

        # Global confidence
        global_metric = entry.get("globalMetricValue")
        if global_metric:
            parts.append(f"Global pLDDT Score: {global_metric:.1f}")
            parts.append(self._interpret_plddt(global_metric))

        # PAE image URL
        pae_url = entry.get("paeImageUrl")
        pae_doc_url = entry.get("paeDocUrl")

        parts.append(f"\nPAE (Predicted Aligned Error):")
        parts.append("PAE measures the confidence in relative domain positions.")
        parts.append("Lower values (blue) indicate higher confidence.")

        if pae_url:
            parts.append(f"\nPAE Image: {pae_url}")
        if pae_doc_url:
            parts.append(f"PAE Data (JSON): {pae_doc_url}")

        parts.append(f"\npLDDT Score Interpretation:")
        parts.append("  > 90: Very high confidence (blue)")
        parts.append("  70-90: Confident (cyan)")
        parts.append("  50-70: Low confidence (yellow)")
        parts.append("  < 50: Very low confidence (orange)")

        return "\n".join(parts)

    def _interpret_plddt(self, score: float) -> str:
        """Interpret pLDDT confidence score."""
        if score >= 90:
            return "  Interpretation: Very high confidence - highly accurate"
        elif score >= 70:
            return "  Interpretation: Confident - backbone likely accurate"
        elif score >= 50:
            return "  Interpretation: Low confidence - treat with caution"
        else:
            return "  Interpretation: Very low confidence - may be disordered"

    def _request(self, url: str) -> str:
        """Make an HTTP request to AlphaFold DB."""
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
                    return f"Error: No AlphaFold prediction found for this UniProt accession (404)"
                else:
                    return f"Error: HTTP {e.code} - {e.reason}"
            except Exception as e:
                if attempt < self.max_retries:
                    time.sleep(0.5)
                    continue
                return f"Error querying AlphaFold: {e}"

        return "Error: Max retries exceeded"

    def _rate_limit(self):
        """Enforce rate limits (~5 requests/second)."""
        global _last_request_time
        min_interval = 0.2  # 5 requests per second
        elapsed = time.time() - _last_request_time
        if elapsed < min_interval:
            time.sleep(min_interval - elapsed)
        _last_request_time = time.time()
