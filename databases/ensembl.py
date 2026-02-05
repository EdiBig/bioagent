"""
Ensembl REST API client for gene/variant/regulatory queries.

Provides access to gene information, variant effect prediction,
sequence retrieval, homology, and cross-references.
"""

import json
import time
import urllib.parse
import urllib.request
from dataclasses import dataclass


BASE_URL = "https://rest.ensembl.org"
_last_request_time = 0.0


@dataclass
class EnsemblResult:
    """Result from an Ensembl query."""
    data: str
    endpoint: str
    success: bool

    def to_string(self) -> str:
        status = "✓" if self.success else "✗"
        return f"Ensembl {status} [{self.endpoint}]\n\n{self.data}"


class EnsemblClient:
    """Client for the Ensembl REST API."""

    def __init__(self, max_retries: int = 2):
        self.max_retries = max_retries

    def query(
        self,
        endpoint: str,
        params: dict | None = None,
        species: str = "homo_sapiens",
    ) -> EnsemblResult:
        """
        Query the Ensembl REST API.

        Args:
            endpoint: API endpoint path (e.g., 'lookup/symbol/homo_sapiens/BRCA1')
            params: Optional query parameters
            species: Species (used for endpoint substitution)

        Returns:
            EnsemblResult with the response data
        """
        self._rate_limit()

        # Replace {species} placeholder if present
        endpoint = endpoint.replace("{species}", species)

        url = f"{BASE_URL}/{endpoint}"
        if params:
            url += "?" + urllib.parse.urlencode(params)

        for attempt in range(self.max_retries + 1):
            try:
                req = urllib.request.Request(
                    url,
                    headers={
                        "Content-Type": "application/json",
                        "Accept": "application/json",
                        "User-Agent": "BioAgent/1.0",
                    },
                )
                with urllib.request.urlopen(req, timeout=30) as resp:
                    data = json.loads(resp.read().decode("utf-8"))
                    formatted = json.dumps(data, indent=2)

                    # Truncate if very large
                    if len(formatted) > 20000:
                        formatted = formatted[:20000] + "\n... [truncated]"

                    return EnsemblResult(
                        data=formatted,
                        endpoint=endpoint,
                        success=True,
                    )

            except urllib.error.HTTPError as e:
                if e.code == 429:  # Rate limited
                    retry_after = int(e.headers.get("Retry-After", 1))
                    time.sleep(retry_after)
                    continue
                elif e.code == 400:
                    return EnsemblResult(
                        data=f"Bad request: {e.read().decode('utf-8', errors='replace')}",
                        endpoint=endpoint,
                        success=False,
                    )
                else:
                    return EnsemblResult(
                        data=f"HTTP error {e.code}: {e.reason}",
                        endpoint=endpoint,
                        success=False,
                    )
            except Exception as e:
                if attempt < self.max_retries:
                    time.sleep(1)
                    continue
                return EnsemblResult(
                    data=f"Error querying Ensembl: {e}",
                    endpoint=endpoint,
                    success=False,
                )

        return EnsemblResult(
            data="Max retries exceeded",
            endpoint=endpoint,
            success=False,
        )

    # ── Convenience methods ──────────────────────────────────────────

    def lookup_gene(self, symbol: str, species: str = "homo_sapiens") -> EnsemblResult:
        """Look up a gene by symbol."""
        return self.query(f"lookup/symbol/{species}/{symbol}", params={"expand": "1"})

    def lookup_id(self, ensembl_id: str) -> EnsemblResult:
        """Look up any Ensembl object by stable ID."""
        return self.query(f"lookup/id/{ensembl_id}", params={"expand": "1"})

    def get_sequence(
        self, ensembl_id: str, seq_type: str = "genomic"
    ) -> EnsemblResult:
        """Get sequence for an Ensembl ID."""
        return self.query(f"sequence/id/{ensembl_id}", params={"type": seq_type})

    def vep_hgvs(self, hgvs: str, species: str = "homo_sapiens") -> EnsemblResult:
        """Predict variant effects using HGVS notation."""
        return self.query(f"vep/{species}/hgvs/{urllib.parse.quote(hgvs, safe='')}")

    def get_homology(self, ensembl_id: str) -> EnsemblResult:
        """Get homologs for a gene."""
        return self.query(f"homology/id/{ensembl_id}")

    def get_xrefs(self, ensembl_id: str) -> EnsemblResult:
        """Get cross-references for an Ensembl ID."""
        return self.query(f"xrefs/id/{ensembl_id}")

    def get_variants_in_region(
        self, region: str, species: str = "homo_sapiens"
    ) -> EnsemblResult:
        """Get variants overlapping a genomic region (e.g., '7:140453136-140624564')."""
        return self.query(
            f"overlap/region/{species}/{region}",
            params={"feature": "variation"},
        )

    def _rate_limit(self):
        """Ensembl allows 15 requests/second."""
        global _last_request_time
        min_interval = 0.067  # ~15 requests/second
        elapsed = time.time() - _last_request_time
        if elapsed < min_interval:
            time.sleep(min_interval - elapsed)
        _last_request_time = time.time()
