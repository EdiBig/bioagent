"""
Test the Research Agent literature search functionality.
"""

import sys
from pathlib import Path

# Add parent directory (bioagent root) to path
sys.path.insert(0, str(Path(__file__).parent.parent))

def test_literature_search():
    """Test the literature search clients and orchestrator."""

    print("=" * 60)
    print("RESEARCH AGENT - LITERATURE SEARCH TEST")
    print("=" * 60)

    # Import the clients
    from Research_Agent.literature.clients import (
        PubMedClient,
        SemanticScholarClient,
        EuropePMCClient,
        CrossRefClient,
        LiteratureSearchOrchestrator,
    )

    # Test query
    query = "CRISPR Cas9 gene therapy"

    # ── Test 1: PubMed ──────────────────────────────────────────
    print("\n[1] Testing PubMed...")
    try:
        pubmed = PubMedClient()
        papers = pubmed.search(query, max_results=3)
        print(f"    Found {len(papers)} papers")
        if papers:
            p = papers[0]
            print(f"    Example: {p.title[:60]}...")
            print(f"    Authors: {p.author_et_al}")
            print(f"    Year: {p.year}, PMID: {p.pmid}")
        print("    [OK] PubMed working")
    except Exception as e:
        print(f"    [FAIL] PubMed error: {e}")

    # ── Test 2: Semantic Scholar ────────────────────────────────
    print("\n[2] Testing Semantic Scholar...")
    try:
        s2 = SemanticScholarClient()
        papers = s2.search(query, max_results=3)
        print(f"    Found {len(papers)} papers")
        if papers:
            p = papers[0]
            print(f"    Example: {p.title[:60]}...")
            print(f"    Citations: {p.citation_count}, DOI: {p.doi or 'N/A'}")
            print(f"    Open Access: {p.is_open_access}")
        print("    [OK] Semantic Scholar working")
    except Exception as e:
        print(f"    [FAIL] Semantic Scholar error: {e}")

    # ── Test 3: Europe PMC ──────────────────────────────────────
    print("\n[3] Testing Europe PMC...")
    try:
        epmc = EuropePMCClient()
        papers = epmc.search(query, max_results=3)
        print(f"    Found {len(papers)} papers")
        if papers:
            p = papers[0]
            print(f"    Example: {p.title[:60]}...")
            print(f"    Journal: {p.journal}")
        print("    [OK] Europe PMC working")
    except Exception as e:
        print(f"    [FAIL] Europe PMC error: {e}")

    # ── Test 4: CrossRef ────────────────────────────────────────
    print("\n[4] Testing CrossRef...")
    try:
        crossref = CrossRefClient()
        papers = crossref.search(query, max_results=3)
        print(f"    Found {len(papers)} papers")
        if papers:
            p = papers[0]
            print(f"    Example: {p.title[:60]}...")
            print(f"    DOI: {p.doi}")
        print("    [OK] CrossRef working")
    except Exception as e:
        print(f"    [FAIL] CrossRef error: {e}")

    # ── Test 5: Orchestrator (Combined Search) ──────────────────
    print("\n[5] Testing Orchestrator (multi-source search)...")
    try:
        orchestrator = LiteratureSearchOrchestrator()
        results = orchestrator.search(
            query=query,
            sources=["pubmed", "semantic_scholar", "europe_pmc"],
            max_per_source=5,
            year_from=2020
        )
        print(f"    Total found: {results.total_found} papers (deduplicated)")
        print(f"    Sources: {', '.join(results.sources_searched)}")

        if results.papers:
            print("\n    Top 3 ranked papers:")
            for i, p in enumerate(results.papers[:3], 1):
                oa = " [OA]" if p.is_open_access else ""
                print(f"    {i}. {p.title[:50]}...{oa}")
                print(f"       {p.author_et_al} ({p.year}) | Citations: {p.citation_count}")

        print("    [OK] Orchestrator working")
    except Exception as e:
        print(f"    [FAIL] Orchestrator error: {e}")

    # ── Test 6: Citation Network ────────────────────────────────
    print("\n[6] Testing Citation Network (Semantic Scholar)...")
    try:
        # Use a well-known CRISPR paper DOI
        doi = "10.1126/science.1225829"  # Original Doudna/Charpentier CRISPR paper

        orchestrator = LiteratureSearchOrchestrator()
        network = orchestrator.get_citation_network(doi, direction="citations", max_results=3)
        print(f"    Papers citing DOI {doi}: {network.total_found}")

        if network.papers:
            print("    Recent citations:")
            for p in network.papers[:2]:
                print(f"    - {p.title[:50]}... ({p.year})")

        print("    [OK] Citation network working")
    except Exception as e:
        print(f"    [FAIL] Citation network error: {e}")

    # ── Test 7: Citation Manager ────────────────────────────────
    print("\n[7] Testing Citation Manager...")
    try:
        from Research_Agent.citations.manager import CitationManager, get_citation_style
        from Research_Agent.literature.clients import Paper, Author

        # Create a test paper
        test_paper = Paper(
            title="CRISPR-Cas9 Gene Editing for Sickle Cell Disease",
            authors=[Author(name="Jennifer Doudna"), Author(name="Emmanuelle Charpentier")],
            year=2023,
            journal="Nature Medicine",
            doi="10.1038/s41591-023-01234-5",
            pmid="12345678"
        )

        # Test different citation styles
        for style_name in ["vancouver", "apa", "nature", "harvard", "ieee"]:
            style = get_citation_style(style_name)
            cm = CitationManager(style=style)
            citation = cm.cite(test_paper)
            print(f"    {style_name.upper()}: {citation}")

        print("    [OK] Citation manager working")
    except Exception as e:
        print(f"    [FAIL] Citation manager error: {e}")

    print("\n" + "=" * 60)
    print("TEST COMPLETE")
    print("=" * 60)


if __name__ == "__main__":
    test_literature_search()
