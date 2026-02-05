"""
ML/AI Capabilities for BioAgent.

Provides machine learning and AI-powered analysis tools:
- Variant pathogenicity prediction (CADD, REVEL, AlphaMissense)
- Protein structure prediction (AlphaFold, ESMFold)
- Drug response prediction (GDSC, CCLE)
- Cell type annotation (CellTypist, scType)
- Biomarker discovery (feature selection pipelines)
"""

from .pathogenicity import (
    PathogenicityPredictor,
    predict_variant_pathogenicity,
    get_cadd_scores,
    get_revel_scores,
    get_alphamissense_scores,
)
from .structure import (
    StructurePredictor,
    predict_structure_alphafold,
    predict_structure_esmfold,
    get_alphafold_structure,
)
from .drug_response import (
    DrugResponsePredictor,
    predict_drug_response,
    get_gdsc_predictions,
    get_ccle_predictions,
)
from .cell_annotation import (
    CellTypeAnnotator,
    annotate_cell_types,
    run_celltypist,
    run_sctype,
)
from .biomarkers import (
    BiomarkerDiscovery,
    discover_biomarkers,
    run_feature_selection,
)

__all__ = [
    # Pathogenicity
    "PathogenicityPredictor",
    "predict_variant_pathogenicity",
    "get_cadd_scores",
    "get_revel_scores",
    "get_alphamissense_scores",
    # Structure
    "StructurePredictor",
    "predict_structure_alphafold",
    "predict_structure_esmfold",
    "get_alphafold_structure",
    # Drug response
    "DrugResponsePredictor",
    "predict_drug_response",
    "get_gdsc_predictions",
    "get_ccle_predictions",
    # Cell annotation
    "CellTypeAnnotator",
    "annotate_cell_types",
    "run_celltypist",
    "run_sctype",
    # Biomarkers
    "BiomarkerDiscovery",
    "discover_biomarkers",
    "run_feature_selection",
]
