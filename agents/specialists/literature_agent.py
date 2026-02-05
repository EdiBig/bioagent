"""
Literature Agent specialist.

Handles database queries, literature search, and biological information retrieval.
"""

from ..base import BaseAgent, SpecialistType
from ..prompts import LITERATURE_AGENT_PROMPT
from ..tools import SPECIALIST_TOOLS


class LiteratureAgent(BaseAgent):
    """
    Specialist for database queries and literature search.

    Capabilities:
    - Query biological databases (NCBI, UniProt, Ensembl, etc.)
    - Literature search and synthesis
    - Gene/protein/pathway information retrieval
    - Cross-referencing between databases
    """

    @property
    def specialist_type(self) -> SpecialistType:
        return SpecialistType.LITERATURE_AGENT

    @property
    def system_prompt(self) -> str:
        return LITERATURE_AGENT_PROMPT

    @property
    def tool_names(self) -> list[str]:
        return SPECIALIST_TOOLS["literature_agent"]

    def _identify_query_targets(self, task: str) -> dict:
        """
        Identify what biological entities the user is asking about.

        Returns dict with identified entities and suggested databases.
        """
        import re

        task_upper = task.upper()

        targets = {
            "genes": [],
            "proteins": [],
            "variants": [],
            "pathways": [],
            "databases_to_query": [],
        }

        # Common gene symbol pattern (2-5 uppercase letters, optionally followed by numbers)
        gene_pattern = r'\b([A-Z][A-Z0-9]{1,5})\b'
        potential_genes = re.findall(gene_pattern, task_upper)

        # Filter out common non-gene words
        non_genes = {"THE", "AND", "FOR", "WITH", "FROM", "WHAT", "HOW", "WHY", "DNA", "RNA",
                     "PCR", "QC", "GO", "KEGG", "PDB", "NCBI", "API"}
        targets["genes"] = [g for g in potential_genes if g not in non_genes][:10]

        # UniProt accession pattern
        uniprot_pattern = r'\b([OPQ][0-9][A-Z0-9]{3}[0-9]|[A-NR-Z][0-9]([A-Z][A-Z0-9]{2}[0-9]){1,2})\b'
        targets["proteins"] = re.findall(uniprot_pattern, task_upper)[:5]

        # Variant patterns
        variant_patterns = [
            r'rs\d+',  # dbSNP IDs
            r'[A-Z]\d+[A-Z]',  # Amino acid changes
            r'c\.\d+[ATCG]>[ATCG]',  # HGVS coding
        ]
        for pattern in variant_patterns:
            targets["variants"].extend(re.findall(pattern, task, re.IGNORECASE))

        # Suggest databases based on context
        task_lower = task.lower()

        if any(g in targets["genes"] for g in targets["genes"]):
            targets["databases_to_query"].extend(["ncbi_gene", "uniprot", "ensembl"])

        if "pathway" in task_lower or "signaling" in task_lower:
            targets["databases_to_query"].extend(["kegg", "reactome"])

        if "interaction" in task_lower or "partner" in task_lower:
            targets["databases_to_query"].append("string")

        if "structure" in task_lower or "3d" in task_lower:
            targets["databases_to_query"].extend(["pdb", "alphafold"])

        if "domain" in task_lower or "family" in task_lower:
            targets["databases_to_query"].append("interpro")

        if "variant" in task_lower or "mutation" in task_lower or targets["variants"]:
            targets["databases_to_query"].extend(["gnomad", "ensembl_vep"])

        if "function" in task_lower or "go term" in task_lower:
            targets["databases_to_query"].append("gene_ontology")

        # Deduplicate
        targets["databases_to_query"] = list(set(targets["databases_to_query"]))

        return targets

    def run(self, task: str, context=None, previous_outputs=None):
        """
        Execute a literature/database query task.

        Adds entity identification and database suggestions.
        """
        # Identify query targets
        targets = self._identify_query_targets(task)

        # Build enhanced task with entity hints
        enhancements = []

        if targets["genes"]:
            enhancements.append(f"Identified genes: {', '.join(targets['genes'][:5])}")

        if targets["proteins"]:
            enhancements.append(f"Identified proteins: {', '.join(targets['proteins'][:3])}")

        if targets["variants"]:
            enhancements.append(f"Identified variants: {', '.join(targets['variants'][:3])}")

        if targets["databases_to_query"]:
            enhancements.append(
                f"Suggested databases: {', '.join(targets['databases_to_query'][:5])}"
            )

        enhanced_task = task
        if enhancements:
            enhanced_task = f"{task}\n\n## Query Hints\n" + "\n".join(f"- {e}" for e in enhancements)

        return super().run(enhanced_task, context, previous_outputs)
