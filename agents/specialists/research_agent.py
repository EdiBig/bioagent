"""
Research Agent specialist.

Handles deep literature synthesis, citation management, academic report
generation, and presentation creation.

This specialist wraps the standalone Research Agent module to integrate
with the multi-agent coordinator pattern.
"""

from ..base import BaseAgent, SpecialistType, SpecialistOutput
from ..tools import SPECIALIST_TOOLS


# Research Agent system prompt
RESEARCH_AGENT_PROMPT = """You are a Senior Postdoctoral Research Scientist with expertise in computational biology and bioinformatics.

## Your Role

You are the research synthesis specialist in a multi-agent bioinformatics system. Your role is to:

1. **Conduct Deep Literature Reviews** - Search across PubMed, Semantic Scholar, Europe PMC, CrossRef, and bioRxiv to gather comprehensive evidence
2. **Synthesize Findings** - Combine results from other agents with literature evidence to provide publication-quality analysis
3. **Manage Citations** - Track all sources with proper academic citations (Vancouver, APA, Nature, Harvard, IEEE styles)
4. **Generate Reports** - Create structured research reports with proper sections and references
5. **Create Presentations** - Generate PowerPoint presentations with data visualizations

## Research Approach

When conducting research:

1. **Define the Question** - Clarify the specific research question and scope
2. **Plan the Search** - Develop systematic search strategies with appropriate databases and keywords
3. **Gather Evidence** - Search literature systematically, noting key papers
4. **Synthesize** - Identify consensus, contradictions, and knowledge gaps
5. **Present** - Format findings with proper citations and clear structure

## Evidence Quality Grading

Rate evidence by strength:
- **Strong**: Meta-analyses, systematic reviews, large cohort studies
- **Moderate**: Well-designed cohort or case-control studies
- **Limited**: Small studies, retrospective analyses
- **Preliminary**: Single studies, preprints, case reports
- **Conflicting**: Mixed results requiring careful interpretation

## Citation Standards

- Every factual claim must be cited
- Distinguish between primary research, reviews, and preprints
- Use consistent citation style throughout
- Include DOI or PMID when available

## Tools Available

You have access to:
- Literature search across multiple databases
- Paper details and citation networks
- Citation management and formatting
- Study planning templates
- Report section generation
- Presentation creation

## Working with Other Agents

When receiving context from other agents:
- Integrate their computational findings with literature evidence
- Identify supporting or contradicting published research
- Provide biological interpretation backed by citations
- Suggest additional analyses based on literature gaps
"""


class ResearchAgentSpecialist(BaseAgent):
    """
    Specialist for deep literature synthesis and academic output.

    Capabilities:
    - Multi-source literature search (PubMed, Semantic Scholar, Europe PMC, etc.)
    - Citation management with multiple academic styles
    - Study planning and structured research workflows
    - Publication-quality report generation
    - Academic presentation creation
    - Evidence synthesis and inter-agent advisory
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._research_agent = None

    @property
    def specialist_type(self) -> SpecialistType:
        return SpecialistType.RESEARCH_AGENT

    @property
    def system_prompt(self) -> str:
        return RESEARCH_AGENT_PROMPT

    @property
    def tool_names(self) -> list[str]:
        return SPECIALIST_TOOLS["research_agent"]

    def _get_research_agent(self):
        """Lazy-initialize the standalone Research Agent for advanced features."""
        if self._research_agent is None:
            try:
                from Research_Agent import ResearchAgent, ResearchAgentConfig
                config = ResearchAgentConfig.from_env()
                self._research_agent = ResearchAgent(config)
            except ImportError:
                # Research Agent module not available, use base agent functionality
                self._research_agent = None
        return self._research_agent

    def plan_study(self, research_question: str, study_type: str = "literature_review",
                   scope: str = "comprehensive") -> str:
        """
        Create a structured study plan for a research question.

        This can be called directly without going through the full agent loop.
        """
        agent = self._get_research_agent()
        if agent:
            return agent.plan_study(research_question, study_type, scope)

        # Fallback: Return basic plan structure
        return f"""## Study Plan: {research_question}

### Study Type
{study_type.replace('_', ' ').title()}

### Scope
{scope.title()}

### Recommended Sections
1. Introduction / Background
2. Methods / Search Strategy
3. Results / Findings
4. Discussion / Interpretation
5. Conclusions

### Suggested Search Strategy
- PubMed: [relevant MeSH terms]
- Semantic Scholar: [keyword search]
- Europe PMC: [preprint search]
"""

    def _identify_research_tasks(self, task: str) -> dict:
        """
        Identify what type of research task is being requested.

        Returns dict with identified tasks and suggested approaches.
        """
        task_lower = task.lower()

        research_tasks = {
            "is_literature_review": False,
            "is_report_generation": False,
            "is_presentation_request": False,
            "is_citation_task": False,
            "suggested_approach": [],
        }

        # Literature review indicators
        if any(term in task_lower for term in [
            "review", "literature", "evidence", "papers", "publications",
            "research on", "what is known", "current understanding"
        ]):
            research_tasks["is_literature_review"] = True
            research_tasks["suggested_approach"].append("systematic_search")

        # Report generation indicators
        if any(term in task_lower for term in [
            "report", "write up", "document", "summarize", "synthesis"
        ]):
            research_tasks["is_report_generation"] = True
            research_tasks["suggested_approach"].append("structured_report")

        # Presentation indicators
        if any(term in task_lower for term in [
            "presentation", "slides", "powerpoint", "pptx"
        ]):
            research_tasks["is_presentation_request"] = True
            research_tasks["suggested_approach"].append("generate_presentation")

        # Citation indicators
        if any(term in task_lower for term in [
            "cite", "citation", "reference", "bibliography", "bibtex"
        ]):
            research_tasks["is_citation_task"] = True
            research_tasks["suggested_approach"].append("citation_management")

        return research_tasks
