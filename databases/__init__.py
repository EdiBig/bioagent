"""
Database API clients for querying biological databases.

This module provides clients for accessing major bioinformatics databases:
- NCBI (PubMed, Gene, Nucleotide, Protein, SNP, etc.)
- Ensembl (Gene/variant information, VEP)
- UniProt (Protein sequences and annotations)
- KEGG (Pathways, genes, compounds)
- STRING (Protein-protein interactions)
- PDB (Protein structures)
- AlphaFold (AI-predicted structures)
- InterPro (Protein domains and families)
- Reactome (Biological pathways)
- Gene Ontology (Functional annotations)
- gnomAD (Population allele frequencies)
"""

from .ncbi import NCBIClient
from .ensembl import EnsemblClient
from .uniprot import UniProtClient
from .kegg import KEGGClient
from .string_db import STRINGClient
from .pdb_client import PDBClient
from .alphafold import AlphaFoldClient
from .interpro import InterProClient
from .reactome import ReactomeClient
from .gene_ontology import GeneOntologyClient
from .gnomad import GnomADClient

__all__ = [
    "NCBIClient",
    "EnsemblClient",
    "UniProtClient",
    "KEGGClient",
    "STRINGClient",
    "PDBClient",
    "AlphaFoldClient",
    "InterProClient",
    "ReactomeClient",
    "GeneOntologyClient",
    "GnomADClient",
]
