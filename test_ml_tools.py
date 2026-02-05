"""
Comprehensive ML/AI Tools Test Suite.

Tests all 5 ML modules with realistic bioinformatics scenarios.
"""

import json
import numpy as np
from ml import (
    predict_variant_pathogenicity,
    predict_structure_alphafold,
    predict_structure_esmfold,
    predict_drug_response,
    annotate_cell_types,
    discover_biomarkers,
)


def test_pathogenicity():
    """Test variant pathogenicity prediction."""
    print("\n" + "─" * 70)
    print("1. VARIANT PATHOGENICITY PREDICTION")
    print("─" * 70)

    # Test with clinically relevant variants
    variants = [
        "17-7577121-G-A",      # TP53 common mutation region
        "13-32914438-T-C",     # BRCA2 region
        "BRCA1:p.Cys61Gly",    # HGVS protein notation
        "rs121913529",         # Known pathogenic BRCA1 variant
    ]

    print(f"Testing {len(variants)} variants...")
    results = predict_variant_pathogenicity(
        variants=variants,
        genome_build="GRCh38",
    )

    for r in results:
        print(f"  {r['variant']}:")
        consensus = r.get("consensus", {})
        pathogenic = "Pathogenic" if consensus.get("pathogenic") else "Not pathogenic"
        confidence = consensus.get("confidence", "unknown")
        print(f"    Consensus: {pathogenic} (confidence: {confidence})")
        if r["scores"].get("cadd_phred"):
            print(f"    CADD PHRED: {r['scores']['cadd_phred']} -> {r['interpretations'].get('cadd', 'N/A')}")
        if r["scores"].get("revel"):
            print(f"    REVEL: {r['scores']['revel']} -> {r['interpretations'].get('revel', 'N/A')}")
        if r["scores"].get("alphamissense"):
            print(f"    AlphaMissense: {r['scores']['alphamissense']} -> {r['interpretations'].get('alphamissense', 'N/A')}")

    return len(results) == len(variants)


def test_structure_prediction():
    """Test protein structure prediction."""
    print("\n" + "─" * 70)
    print("2. PROTEIN STRUCTURE PREDICTION")
    print("─" * 70)

    # Test AlphaFold with real UniProt IDs
    test_proteins = [
        ("P04637", "TP53 (Tumor protein p53)"),
        ("P38398", "BRCA1"),
        ("Q9Y6K9", "NEMO/IKK-gamma"),
    ]

    print("AlphaFold Database lookups:")
    af_success = 0
    for uniprot_id, name in test_proteins:
        try:
            struct = predict_structure_alphafold(uniprot_id=uniprot_id)
            print(f"  {name} ({uniprot_id}):")
            print(f"    Method: {struct['method']}")
            print(f"    Mean pLDDT: {struct['quality']['mean_plddt']}")
            if struct.get("pdb_url"):
                print(f"    PDB URL: {struct['pdb_url'][:60]}...")
            af_success += 1
        except Exception as e:
            print(f"  {name}: Error - {e}")

    # Test ESMFold with a short sequence
    print("\nESMFold prediction (insulin B chain):")
    insulin_b = "FVNQHLCGSHLVEALYLVCGERGFFYTPKT"
    try:
        esm_result = predict_structure_esmfold(sequence=insulin_b)
        print(f"  Sequence length: {len(insulin_b)} aa")
        print(f"  Method: {esm_result['method']}")
        print(f"  Mean pLDDT: {esm_result['quality']['mean_plddt']}")
        esm_success = True
    except Exception as e:
        print(f"  Result: {e}")
        esm_success = False

    return af_success >= 2 and esm_success


def test_drug_response():
    """Test drug response prediction."""
    print("\n" + "─" * 70)
    print("3. DRUG RESPONSE PREDICTION")
    print("─" * 70)

    # Test with real drug-tissue combinations
    drug_tests = [
        ("Erlotinib", "lung", ["EGFR"]),
        ("Vemurafenib", "melanoma", ["BRAF_V600E"]),
        ("Olaparib", "breast", ["BRCA1"]),
        ("Imatinib", "leukemia", ["BCR-ABL"]),
    ]

    total_results = 0
    for drug, tissue, mutations in drug_tests:
        print(f"\n  {drug} in {tissue} (mutations: {mutations}):")
        results = predict_drug_response(
            drug=drug,
            tissue=tissue,
            mutations=mutations
        )

        if results:
            total_results += len(results)
            for r in results[:2]:  # Show top 2
                resp = r["response"]
                print(f"    Cell line: {r['cell_line']}")
                print(f"    Prediction: {resp['prediction']} (IC50: {resp['ic50']} {resp['ic50_unit']})")
                print(f"    Confidence: {resp['confidence']}")

    return total_results > 0


def test_cell_annotation():
    """Test cell type annotation."""
    print("\n" + "─" * 70)
    print("4. CELL TYPE ANNOTATION (Single-cell RNA-seq)")
    print("─" * 70)

    # Simulate PBMC-like single-cell data
    np.random.seed(42)
    n_cells = 500
    n_genes = 100

    # Create expression matrix with cell-type-like patterns
    expression_data = np.random.exponential(scale=2, size=(n_cells, n_genes))

    print(f"Simulated dataset: {n_cells} cells x {n_genes} genes")
    print("Running CellTypist annotation...")

    results = annotate_cell_types(
        expression_data=expression_data,
        method="celltypist",
        model="Immune_All_Low.pkl"
    )

    summary = results["summary"]
    print(f"  Total cells: {summary['total_cells']}")
    print(f"  Cell types identified: {summary['n_types']}")
    print(f"  Mean confidence: {summary['mean_confidence']:.3f}")
    print(f"  Low confidence cells: {summary['low_confidence_cells']}")

    print("\n  Cell type distribution:")
    for cell_type, prop in sorted(results["type_proportions"].items(),
                                   key=lambda x: x[1], reverse=True)[:5]:
        count = results["type_counts"][cell_type]
        print(f"    {cell_type}: {count} cells ({prop*100:.1f}%)")

    return summary["total_cells"] == n_cells


def test_biomarker_discovery():
    """Test biomarker discovery."""
    print("\n" + "─" * 70)
    print("5. BIOMARKER DISCOVERY (Feature Selection)")
    print("─" * 70)

    # Simulate gene expression data with differential expression
    np.random.seed(123)
    n_samples = 100
    n_features = 500

    # Create two groups with some differentially expressed genes
    X = np.random.randn(n_samples, n_features)
    y = np.array([0] * 50 + [1] * 50)

    # Add signal to first 20 features (true biomarkers)
    X[:50, :20] += 1.5  # Group 0 has higher expression
    X[50:, :20] -= 1.5  # Group 1 has lower expression

    # Add some noise features with weak signal
    X[:50, 20:30] += 0.5

    feature_names = [f"Gene_{i}" for i in range(n_features)]

    print(f"Simulated dataset: {n_samples} samples x {n_features} features")
    print("Running ensemble biomarker discovery...")
    print("Methods: differential expression, Random Forest, LASSO")

    results = discover_biomarkers(
        X=X,
        y=y,
        feature_names=feature_names,
        n_features=15,
        methods=["differential", "random_forest", "lasso"]
    )

    print(f"\n  Biomarkers discovered: {results['n_biomarkers']}")
    print(f"  Application: {results['application']}")
    print(f"  Discovery methods: {results['methods']['discovery']}")

    perf = results["performance"]
    print(f"\n  Cross-validation performance:")
    print(f"    AUC: {perf['auc']:.3f}")
    print(f"    Sensitivity: {perf['sensitivity']:.3f}")
    print(f"    Specificity: {perf['specificity']:.3f}")

    print(f"\n  Top 10 biomarkers:")
    for b in results["biomarkers"][:10]:
        idx = int(b["name"].split("_")[1])
        true_marker = "T" if idx < 20 else " "
        print(f"    [{true_marker}] {b['name']}: importance={b['importance_score']:.4f} (rank {b['rank']})")

    # Count how many true biomarkers were found in top 15
    true_found = sum(1 for b in results["biomarkers"][:15]
                     if int(b["name"].split("_")[1]) < 20)
    print(f"\n  True biomarkers in top 15: {true_found}/15")
    print(f"  (Dataset has 20 true differential features)")

    return true_found >= 10  # At least 10 of 15 should be true biomarkers


def main():
    """Run all ML tool tests."""
    print("=" * 70)
    print("ML/AI TOOLS COMPREHENSIVE TEST")
    print("=" * 70)

    results = {}

    # Run all tests
    results["pathogenicity"] = test_pathogenicity()
    results["structure"] = test_structure_prediction()
    results["drug_response"] = test_drug_response()
    results["cell_annotation"] = test_cell_annotation()
    results["biomarkers"] = test_biomarker_discovery()

    # Summary
    print("\n" + "=" * 70)
    print("TEST SUMMARY")
    print("=" * 70)

    all_passed = True
    for test_name, passed in results.items():
        status = "PASS" if passed else "FAIL"
        symbol = "✓" if passed else "✗"
        print(f"  {symbol} {test_name}: {status}")
        if not passed:
            all_passed = False

    print("\n" + "=" * 70)
    if all_passed:
        print("ALL ML/AI TOOLS TESTED SUCCESSFULLY")
    else:
        print("SOME TESTS FAILED - CHECK OUTPUT ABOVE")
    print("=" * 70)

    return all_passed


if __name__ == "__main__":
    main()
