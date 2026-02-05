"""
gnomAD API client for population genetics data.

Provides access to allele frequencies, constraint metrics,
and population-level variant information.
"""

import json
import time
import urllib.parse
import urllib.request
from dataclasses import dataclass


# gnomAD uses GraphQL API
BASE_URL = "https://gnomad.broadinstitute.org/api"

# gnomAD allows reasonable request rates
_last_request_time = 0.0


@dataclass
class GnomADResult:
    """Result from a gnomAD query."""
    data: str
    query: str
    operation: str
    success: bool

    def to_string(self) -> str:
        status = "Success" if self.success else "Failed"
        return f"gnomAD {self.operation} [{status}]: {self.query}\n\n{self.data}"


class GnomADClient:
    """Client for the gnomAD GraphQL API."""

    def __init__(self, max_retries: int = 2):
        self.max_retries = max_retries

    def query(
        self,
        query: str,
        operation: str = "variant",
        dataset: str = "gnomad_r4",
    ) -> GnomADResult:
        """
        Execute a gnomAD query.

        Args:
            query: Variant ID (1-55516888-G-A), gene symbol, or region
            operation: Operation type (variant, gene, region)
            dataset: gnomAD dataset version (gnomad_r4, gnomad_r3, etc.)

        Returns:
            GnomADResult with the response data
        """
        self._rate_limit()

        if operation == "variant":
            return self._get_variant(query, dataset)
        elif operation == "gene":
            return self._get_gene_constraint(query, dataset)
        elif operation == "region":
            return self._get_region_variants(query, dataset)
        else:
            return GnomADResult(
                data=f"Unknown operation: {operation}. Use variant, gene, or region.",
                query=query,
                operation=operation,
                success=False,
            )

    def _get_variant(self, variant_id: str, dataset: str) -> GnomADResult:
        """Get variant details including allele frequencies."""
        variant_id = variant_id.strip()

        # Parse variant ID (chr-pos-ref-alt format)
        parts = variant_id.replace(":", "-").split("-")
        if len(parts) != 4:
            return GnomADResult(
                data=f"Invalid variant format. Use chr-pos-ref-alt (e.g., 1-55516888-G-A)",
                query=variant_id,
                operation="variant",
                success=False,
            )

        chrom, pos, ref, alt = parts
        chrom = chrom.replace("chr", "")

        graphql_query = """
        query VariantQuery($variantId: String!, $dataset: DatasetId!) {
            variant(variantId: $variantId, dataset: $dataset) {
                variant_id
                reference_genome
                chrom
                pos
                ref
                alt
                rsids
                exome {
                    ac
                    an
                    af
                    homozygote_count
                    populations {
                        id
                        ac
                        an
                        af
                    }
                }
                genome {
                    ac
                    an
                    af
                    homozygote_count
                    populations {
                        id
                        ac
                        an
                        af
                    }
                }
                transcript_consequences {
                    gene_symbol
                    transcript_id
                    consequence_terms
                    hgvsc
                    hgvsp
                    lof
                    lof_filter
                }
                in_silico_predictors {
                    id
                    value
                }
            }
        }
        """

        variables = {
            "variantId": f"{chrom}-{pos}-{ref}-{alt}",
            "dataset": dataset,
        }

        response = self._graphql_request(graphql_query, variables)

        if response.startswith("Error"):
            return GnomADResult(
                data=response,
                query=variant_id,
                operation="variant",
                success=False,
            )

        try:
            data = json.loads(response)
            variant = data.get("data", {}).get("variant")

            if not variant:
                return GnomADResult(
                    data=f"Variant {variant_id} not found in {dataset}.",
                    query=variant_id,
                    operation="variant",
                    success=False,
                )

            formatted = self._format_variant(variant)
            return GnomADResult(
                data=formatted,
                query=variant_id,
                operation="variant",
                success=True,
            )
        except (json.JSONDecodeError, KeyError) as e:
            return GnomADResult(
                data=f"Error parsing response: {e}",
                query=variant_id,
                operation="variant",
                success=False,
            )

    def _get_gene_constraint(self, gene: str, dataset: str) -> GnomADResult:
        """Get gene constraint metrics (pLI, LOEUF, etc.)."""
        gene = gene.upper().strip()

        graphql_query = """
        query GeneQuery($geneSymbol: String!) {
            gene(gene_symbol: $geneSymbol, reference_genome: GRCh38) {
                gene_id
                symbol
                name
                chrom
                start
                stop
                strand
                gnomad_constraint {
                    exp_lof
                    exp_mis
                    exp_syn
                    obs_lof
                    obs_mis
                    obs_syn
                    oe_lof
                    oe_lof_lower
                    oe_lof_upper
                    oe_mis
                    oe_syn
                    lof_z
                    mis_z
                    syn_z
                    pLI
                    flags
                }
            }
        }
        """

        variables = {
            "geneSymbol": gene,
        }

        response = self._graphql_request(graphql_query, variables)

        if response.startswith("Error"):
            return GnomADResult(
                data=response,
                query=gene,
                operation="gene",
                success=False,
            )

        try:
            data = json.loads(response)
            gene_data = data.get("data", {}).get("gene")

            if not gene_data:
                return GnomADResult(
                    data=f"Gene {gene} not found.",
                    query=gene,
                    operation="gene",
                    success=False,
                )

            formatted = self._format_gene_constraint(gene_data)
            return GnomADResult(
                data=formatted,
                query=gene,
                operation="gene",
                success=True,
            )
        except (json.JSONDecodeError, KeyError) as e:
            return GnomADResult(
                data=f"Error parsing response: {e}",
                query=gene,
                operation="gene",
                success=False,
            )

    def _get_region_variants(self, region: str, dataset: str) -> GnomADResult:
        """Get variants in a genomic region."""
        # Parse region (chr:start-stop)
        region = region.strip()

        try:
            if ":" in region:
                chrom, coords = region.split(":")
                start, stop = coords.replace(",", "").split("-")
            else:
                return GnomADResult(
                    data="Invalid region format. Use chr:start-stop (e.g., 1:55516000-55520000)",
                    query=region,
                    operation="region",
                    success=False,
                )

            chrom = chrom.replace("chr", "")
            start = int(start)
            stop = int(stop)

            # Limit region size
            if stop - start > 100000:
                return GnomADResult(
                    data="Region too large. Maximum size is 100kb.",
                    query=region,
                    operation="region",
                    success=False,
                )

        except ValueError:
            return GnomADResult(
                data="Invalid region format. Use chr:start-stop (e.g., 1:55516000-55520000)",
                query=region,
                operation="region",
                success=False,
            )

        graphql_query = """
        query RegionQuery($chrom: String!, $start: Int!, $stop: Int!, $dataset: DatasetId!) {
            region(chrom: $chrom, start: $start, stop: $stop, reference_genome: GRCh38) {
                variants(dataset: $dataset) {
                    variant_id
                    pos
                    ref
                    alt
                    rsids
                    exome {
                        ac
                        an
                        af
                    }
                    genome {
                        ac
                        an
                        af
                    }
                }
            }
        }
        """

        variables = {
            "chrom": chrom,
            "start": start,
            "stop": stop,
            "dataset": dataset,
        }

        response = self._graphql_request(graphql_query, variables)

        if response.startswith("Error"):
            return GnomADResult(
                data=response,
                query=region,
                operation="region",
                success=False,
            )

        try:
            data = json.loads(response)
            region_data = data.get("data", {}).get("region", {})
            variants = region_data.get("variants", [])

            if not variants:
                return GnomADResult(
                    data=f"No variants found in region {region}.",
                    query=region,
                    operation="region",
                    success=True,
                )

            formatted = self._format_region_variants(variants, region)
            return GnomADResult(
                data=formatted,
                query=region,
                operation="region",
                success=True,
            )
        except (json.JSONDecodeError, KeyError) as e:
            return GnomADResult(
                data=f"Error parsing response: {e}",
                query=region,
                operation="region",
                success=False,
            )

    def _format_variant(self, variant: dict) -> str:
        """Format variant details."""
        parts = []

        var_id = variant.get("variant_id", "N/A")
        parts.append(f"Variant: {var_id}")

        # rsIDs
        rsids = variant.get("rsids", [])
        if rsids:
            parts.append(f"rsID(s): {', '.join(rsids)}")

        # Exome frequencies
        exome = variant.get("exome")
        if exome and exome.get("an"):
            parts.append(f"\nExome Data:")
            parts.append(f"  Allele Count: {exome.get('ac', 0):,}")
            parts.append(f"  Allele Number: {exome.get('an', 0):,}")
            af = exome.get('af', 0)
            parts.append(f"  Allele Frequency: {af:.6f}" if af else "  Allele Frequency: 0")
            parts.append(f"  Homozygotes: {exome.get('homozygote_count', 0):,}")

            # Population frequencies
            pops = exome.get("populations", [])
            if pops:
                parts.append("  Population Frequencies:")
                for pop in pops[:8]:
                    pop_id = pop.get("id", "")
                    pop_af = pop.get("af", 0)
                    if pop_af and pop_af > 0:
                        parts.append(f"    {pop_id}: {pop_af:.6f}")

        # Genome frequencies
        genome = variant.get("genome")
        if genome and genome.get("an"):
            parts.append(f"\nGenome Data:")
            parts.append(f"  Allele Count: {genome.get('ac', 0):,}")
            parts.append(f"  Allele Number: {genome.get('an', 0):,}")
            af = genome.get('af', 0)
            parts.append(f"  Allele Frequency: {af:.6f}" if af else "  Allele Frequency: 0")
            parts.append(f"  Homozygotes: {genome.get('homozygote_count', 0):,}")

        # Transcript consequences
        consequences = variant.get("transcript_consequences", [])
        if consequences:
            parts.append(f"\nTranscript Consequences:")
            for cons in consequences[:5]:
                gene = cons.get("gene_symbol", "")
                terms = cons.get("consequence_terms", [])
                hgvsp = cons.get("hgvsp", "")
                lof = cons.get("lof", "")

                term_str = ", ".join(terms) if terms else "N/A"
                parts.append(f"  {gene}: {term_str}")
                if hgvsp:
                    parts.append(f"    Protein: {hgvsp}")
                if lof:
                    parts.append(f"    LoF: {lof}")

        # In silico predictors
        predictors = variant.get("in_silico_predictors", [])
        if predictors:
            parts.append(f"\nIn Silico Predictions:")
            for pred in predictors[:5]:
                pred_id = pred.get("id", "")
                value = pred.get("value", "")
                if value:
                    parts.append(f"  {pred_id}: {value}")

        return "\n".join(parts)

    def _format_gene_constraint(self, gene: dict) -> str:
        """Format gene constraint metrics."""
        parts = []

        symbol = gene.get("symbol", "N/A")
        name = gene.get("name", "N/A")
        chrom = gene.get("chrom", "")
        start = gene.get("start", "")
        stop = gene.get("stop", "")

        parts.append(f"Gene: {symbol}")
        parts.append(f"Name: {name}")
        parts.append(f"Location: chr{chrom}:{start}-{stop}")

        constraint = gene.get("gnomad_constraint", {})
        if constraint:
            parts.append(f"\nConstraint Metrics (gnomAD):")

            # pLI score
            pli = constraint.get("pLI")
            if pli is not None:
                parts.append(f"  pLI: {pli:.4f}")
                if pli >= 0.9:
                    parts.append("    -> Highly intolerant to LoF variants")
                elif pli >= 0.5:
                    parts.append("    -> Moderately intolerant to LoF")

            # LOEUF (oe_lof_upper)
            loeuf = constraint.get("oe_lof_upper")
            if loeuf is not None:
                parts.append(f"  LOEUF: {loeuf:.4f}")
                if loeuf < 0.35:
                    parts.append("    -> Highly constrained (LoF intolerant)")

            # Observed/Expected ratios
            oe_lof = constraint.get("oe_lof")
            oe_mis = constraint.get("oe_mis")
            oe_syn = constraint.get("oe_syn")

            parts.append(f"\n  Observed/Expected Ratios:")
            if oe_lof is not None:
                parts.append(f"    LoF: {oe_lof:.3f}")
            if oe_mis is not None:
                parts.append(f"    Missense: {oe_mis:.3f}")
            if oe_syn is not None:
                parts.append(f"    Synonymous: {oe_syn:.3f}")

            # Z-scores
            lof_z = constraint.get("lof_z")
            mis_z = constraint.get("mis_z")

            parts.append(f"\n  Z-scores:")
            if lof_z is not None:
                parts.append(f"    LoF: {lof_z:.2f}")
            if mis_z is not None:
                parts.append(f"    Missense: {mis_z:.2f}")

            # Observed vs Expected counts
            parts.append(f"\n  Variant Counts (observed/expected):")
            obs_lof = constraint.get("obs_lof", 0)
            exp_lof = constraint.get("exp_lof", 0)
            if exp_lof:
                parts.append(f"    LoF: {obs_lof}/{exp_lof:.1f}")

            obs_mis = constraint.get("obs_mis", 0)
            exp_mis = constraint.get("exp_mis", 0)
            if exp_mis:
                parts.append(f"    Missense: {obs_mis}/{exp_mis:.1f}")

            # Flags
            flags = constraint.get("flags", [])
            if flags:
                parts.append(f"\n  Flags: {', '.join(flags)}")
        else:
            parts.append("\nNo constraint data available for this gene.")

        return "\n".join(parts)

    def _format_region_variants(self, variants: list, region: str) -> str:
        """Format variants in a region."""
        parts = [f"Variants in {region}"]
        parts.append(f"Total: {len(variants)}")
        parts.append("-" * 50)

        for var in variants[:50]:
            var_id = var.get("variant_id", "N/A")
            rsids = var.get("rsids", [])

            # Get AF from exome or genome
            exome = var.get("exome", {})
            genome = var.get("genome", {})
            af = exome.get("af") or genome.get("af") or 0

            rsid_str = f" ({rsids[0]})" if rsids else ""
            parts.append(f"\n{var_id}{rsid_str}")
            parts.append(f"  AF: {af:.6f}" if af else "  AF: 0")

        if len(variants) > 50:
            parts.append(f"\n... and {len(variants) - 50} more variants")

        return "\n".join(parts)

    def _graphql_request(self, query: str, variables: dict) -> str:
        """Make a GraphQL request to gnomAD."""
        for attempt in range(self.max_retries + 1):
            try:
                payload = json.dumps({"query": query, "variables": variables}).encode("utf-8")
                req = urllib.request.Request(
                    BASE_URL,
                    data=payload,
                    headers={
                        "User-Agent": "BioAgent/1.0 (Bioinformatics Agent)",
                        "Content-Type": "application/json",
                        "Accept": "application/json",
                    },
                )
                with urllib.request.urlopen(req, timeout=60) as resp:
                    return resp.read().decode("utf-8")
            except urllib.error.HTTPError as e:
                if e.code == 404:
                    return f"Error: Entry not found (404)"
                else:
                    return f"Error: HTTP {e.code} - {e.reason}"
            except Exception as e:
                if attempt < self.max_retries:
                    time.sleep(1)
                    continue
                return f"Error querying gnomAD: {e}"

        return "Error: Max retries exceeded"

    def _rate_limit(self):
        """Enforce rate limits."""
        global _last_request_time
        min_interval = 0.5  # gnomAD can be slow
        elapsed = time.time() - _last_request_time
        if elapsed < min_interval:
            time.sleep(min_interval - elapsed)
        _last_request_time = time.time()
