"""
Integration Example — Wiring the Research Agent into BioAgent.

This file shows exactly how to integrate the Research Agent into your
existing multi-agent BioAgent system. There are three integration patterns:

1. STANDALONE — Research Agent runs independently
2. ORCHESTRATED — Orchestrator delegates to Research Agent
3. REACTIVE — Research Agent reacts to outputs from other agents
"""

# ═══════════════════════════════════════════════════════════════════
# PATTERN 1: STANDALONE
# Use when you want the Research Agent to work independently.
# ═══════════════════════════════════════════════════════════════════

def standalone_example():
    """Run the Research Agent as a standalone tool."""
    from research_agent import ResearchAgent, ResearchAgentConfig

    config = ResearchAgentConfig.from_env()
    agent = ResearchAgent(config)

    # Simple research query
    response = agent.run(
        "Review the current evidence on single-cell RNA sequencing "
        "deconvolution methods for bulk tissue samples. Compare "
        "CIBERSORTx, MuSiC, and BisqueRNA."
    )
    print(response)

    # Study planning only (no agent loop)
    plan = agent.plan_study(
        research_question="What is the role of gut microbiome in immunotherapy response?",
        study_type="literature_review",
        scope="comprehensive",
    )
    print(plan)


# ═══════════════════════════════════════════════════════════════════
# PATTERN 2: ORCHESTRATED
# The Orchestrator delegates research tasks to the Research Agent.
# This is the recommended production pattern.
# ═══════════════════════════════════════════════════════════════════

def orchestrated_example():
    """
    How to integrate into your existing BioAgent multi-agent coordinator.

    Add these changes to your existing agent.py / coordinator:
    """
    from research_agent import ResearchAgent, ResearchAgentConfig
    from research_agent.inter_agent.protocols import (
        ResearchRequest, ContextUpdate, MessageQueue,
    )
    from research_agent.tools.definitions import get_research_tools

    # ─── Step 1: Add Research Agent to your coordinator ───

    class MultiAgentCoordinator:
        """Your existing coordinator — add these lines."""

        def __init__(self, config):
            # ... existing agents ...
            # self.pipeline_agent = PipelineAgent(config)
            # self.stats_agent = StatsAgent(config)
            # self.lit_agent = LitAgent(config)

            # NEW: Add Research Agent
            research_config = ResearchAgentConfig(
                anthropic_api_key=config.anthropic_api_key,
                ncbi_api_key=config.ncbi_api_key,
                ncbi_email=config.ncbi_email,
                workspace_dir=f"{config.workspace_dir}/research",
                output_dir=f"{config.workspace_dir}/research/outputs",
            )
            self.research_agent = ResearchAgent(research_config)

            # Shared message queue
            self.message_queue = MessageQueue()
            self.research_agent.message_queue = self.message_queue

        def delegate_research(self, question: str,
                              agent_results: dict = None) -> str:
            """
            Delegate a research task to the Research Agent.

            Args:
                question: The research question
                agent_results: Dict of results from other agents
                    e.g., {"pipeline_engineer": "DE results: ...",
                           "statistical_ml": "Enrichment: ..."}
            """
            # Build context from other agents' results
            context_parts = []
            if agent_results:
                for agent_name, results in agent_results.items():
                    context_parts.append(
                        f"=== Results from {agent_name} ===\n{results}"
                    )

            context = "\n\n".join(context_parts)

            # Run the research agent
            response = self.research_agent.run(
                user_message=question,
                context=context,
            )

            # Check for advisories sent to other agents
            advisories = self.message_queue.receive("orchestrator")
            for advisory in advisories:
                print(f"Advisory from Research Agent: {advisory.payload}")

            return response

    # ─── Step 2: Wire into the orchestrator's routing logic ───

    # In your orchestrator's task decomposition, add research as a phase:
    #
    # Phase 1: Pipeline Engineer → raw data → processed results
    # Phase 2: Statistical Agent → processed results → DE, enrichment
    # Phase 3: Literature Agent → gene/variant lists → annotations
    # Phase 4: Research Agent → all results → contextualised report + presentation
    #
    # Example routing logic:
    def route_task(coordinator, user_query):
        """Example: how to route through the full pipeline."""

        # Phase 1-3: Your existing pipeline
        pipeline_results = "..."   # coordinator.pipeline_agent.run(...)
        stats_results = "..."      # coordinator.stats_agent.run(...)
        lit_results = "..."        # coordinator.lit_agent.run(...)

        # Phase 4: Research synthesis
        report = coordinator.delegate_research(
            question=user_query,
            agent_results={
                "pipeline_engineer": pipeline_results,
                "statistical_ml": stats_results,
                "literature_db": lit_results,
            }
        )

        return report


# ═══════════════════════════════════════════════════════════════════
# PATTERN 3: REACTIVE
# Research Agent reacts to outputs from other agents in real-time.
# Use when agents run in parallel or in a streaming architecture.
# ═══════════════════════════════════════════════════════════════════

def reactive_example():
    """
    Research Agent receives context updates as other agents produce output.
    """
    from research_agent import ResearchAgent, ResearchAgentConfig
    from research_agent.inter_agent.protocols import ContextUpdate

    agent = ResearchAgent()

    # Another agent finishes DE analysis
    de_update = ContextUpdate(
        from_agent="statistical_ml",
        to_agent="research_agent",
        payload={
            "data_type": "de_results",
            "data_summary": (
                "Differential expression analysis of tumour vs normal colon tissue. "
                "1,247 genes significant (padj < 0.05, |log2FC| > 1). "
                "Top upregulated: MYC, VEGFA, CDK4, CCND1. "
                "Top downregulated: APC, TP53, SMAD4, MLH1."
            ),
            "key_findings": [
                "Strong MYC amplification signature (log2FC = 3.2)",
                "Wnt pathway activation (APC loss + beta-catenin targets up)",
                "DNA mismatch repair deficiency signature (MLH1, MSH2 down)",
                "Unexpected: VEGFA upregulated without hypoxia signature",
            ],
        }
    )

    # Feed the context update to the Research Agent
    agent.handle_context_update(de_update)

    # Now ask the Research Agent to contextualise
    response = agent.run(
        "Based on the DE results just received, search the literature to "
        "contextualise these findings. Specifically: (1) Is the MYC-VEGFA "
        "co-upregulation without hypoxia a known phenomenon in CRC? "
        "(2) What does the MMR deficiency signature suggest about "
        "immunotherapy eligibility? Provide a brief report with citations."
    )
    print(response)


# ═══════════════════════════════════════════════════════════════════
# PATTERN 4: TOOL REGISTRATION
# Add Research Agent tools to your existing BioAgent tool_use definitions.
# ═══════════════════════════════════════════════════════════════════

def tool_registration_example():
    """
    How to register Research Agent tools alongside your existing tools.

    In your existing tools/definitions.py, add:
    """
    from research_agent.tools.definitions import get_research_tools

    # Your existing tools
    EXISTING_TOOLS = [
        # ... execute_python, query_ncbi, etc.
    ]

    # Merge — research tools get prefixed to avoid name collisions
    def get_all_tools():
        """Get all tools including research agent tools."""
        research_tools = get_research_tools()
        # Optional: prefix research tools
        for tool in research_tools:
            tool["name"] = f"research_{tool['name']}"
        return EXISTING_TOOLS + research_tools

    # In your agent loop's _execute_tool:
    # if name.startswith("research_"):
    #     stripped_name = name[len("research_"):]
    #     return self.research_agent._execute_tool(stripped_name, input_data)


# ═══════════════════════════════════════════════════════════════════
# INTEGRATION CHECKLIST
# ═══════════════════════════════════════════════════════════════════

INTEGRATION_CHECKLIST = """
╔══════════════════════════════════════════════════════════════════╗
║                    INTEGRATION CHECKLIST                        ║
╠══════════════════════════════════════════════════════════════════╣
║                                                                  ║
║  1. ENVIRONMENT VARIABLES                                        ║
║     □ ANTHROPIC_API_KEY (required)                               ║
║     □ NCBI_API_KEY (recommended — higher rate limits)            ║
║     □ NCBI_EMAIL (recommended for PubMed)                        ║
║     □ S2_API_KEY (optional — Semantic Scholar higher limits)     ║
║                                                                  ║
║  2. DEPENDENCIES                                                 ║
║     □ pip install anthropic                                      ║
║     □ npm install -g pptxgenjs (for presentations)               ║
║     □ pip install python-docx (for DOCX export — Phase 2)       ║
║                                                                  ║
║  3. WORKSPACE SETUP                                              ║
║     □ Create research workspace directory                        ║
║     □ Create research output directory                           ║
║     □ Verify write permissions                                   ║
║                                                                  ║
║  4. WIRE INTO COORDINATOR                                        ║
║     □ Import ResearchAgent in coordinator                        ║
║     □ Initialise with shared config                              ║
║     □ Add message queue                                          ║
║     □ Add routing logic for research phase                       ║
║                                                                  ║
║  5. TEST                                                         ║
║     □ Test standalone: agent.run("simple query")                 ║
║     □ Test study planning: agent.plan_study(...)                 ║
║     □ Test with context: agent.run(query, context=...)           ║
║     □ Test orchestrated: coordinator.delegate_research(...)      ║
║     □ Test presentation generation                               ║
║                                                                  ║
║  6. PRODUCTION READINESS                                         ║
║     □ Configure rate limits for all APIs                         ║
║     □ Add error handling for API failures                        ║
║     □ Set up logging                                             ║
║     □ Monitor token usage                                        ║
║     □ Test with real research queries end-to-end                 ║
║                                                                  ║
╚══════════════════════════════════════════════════════════════════╝
"""

if __name__ == "__main__":
    print(INTEGRATION_CHECKLIST)
    print("\nSee the four integration patterns above for code examples.")
