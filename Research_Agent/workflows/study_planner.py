"""
Study Planning Workflow.

Decomposes research questions into structured study plans with:
- Section breakdown
- Analysis flow
- Search strategies per section
- Agent delegation suggestions
"""

from dataclasses import dataclass, field
from typing import Optional
from datetime import datetime


@dataclass
class SearchStrategy:
    """Search strategy for a single section/sub-question."""
    databases: list[str]
    primary_terms: list[str]
    mesh_terms: list[str] = field(default_factory=list)
    boolean_query: str = ""
    filters: dict = field(default_factory=dict)
    expected_results: str = ""


@dataclass
class StudySection:
    """A section within the study plan."""
    section_id: str
    title: str
    section_type: str  # e.g., "introduction", "methods", "results"
    sub_questions: list[str]
    search_strategy: Optional[SearchStrategy] = None
    agent_delegation: Optional[str] = None  # which agent handles computation
    dependencies: list[str] = field(default_factory=list)  # section_ids this depends on
    estimated_papers: int = 10
    notes: str = ""


@dataclass
class AnalysisStep:
    """A step in the analysis flow."""
    step_id: str
    description: str
    agent: str  # which agent performs this
    inputs: list[str]  # what this step needs
    outputs: list[str]  # what this step produces
    tools: list[str] = field(default_factory=list)  # tools to use
    notes: str = ""


@dataclass
class StudyPlan:
    """Complete study plan."""
    title: str
    research_question: str
    study_type: str
    scope: str
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())

    # Structure
    sections: list[StudySection] = field(default_factory=list)
    analysis_flow: list[AnalysisStep] = field(default_factory=list)

    # Metadata
    estimated_total_papers: int = 0
    estimated_search_time: str = ""
    key_databases: list[str] = field(default_factory=list)

    def to_markdown(self) -> str:
        """Render the study plan as Markdown."""
        lines = [
            f"# Study Plan: {self.title}",
            "",
            f"**Research Question:** {self.research_question}",
            f"**Study Type:** {self.study_type}",
            f"**Scope:** {self.scope}",
            f"**Created:** {self.created_at}",
            f"**Estimated Papers:** ~{self.estimated_total_papers}",
            "",
            "---",
            "",
            "## Section Structure",
            "",
        ]

        for i, section in enumerate(self.sections, 1):
            lines.append(f"### {i}. {section.title} ({section.section_type})")
            lines.append("")

            if section.sub_questions:
                lines.append("**Sub-questions:**")
                for sq in section.sub_questions:
                    lines.append(f"- {sq}")
                lines.append("")

            if section.search_strategy:
                ss = section.search_strategy
                lines.append(f"**Search strategy:**")
                lines.append(f"- Databases: {', '.join(ss.databases)}")
                lines.append(f"- Primary terms: {', '.join(ss.primary_terms)}")
                if ss.mesh_terms:
                    lines.append(f"- MeSH terms: {', '.join(ss.mesh_terms)}")
                if ss.boolean_query:
                    lines.append(f"- Query: `{ss.boolean_query}`")
                lines.append("")

            if section.agent_delegation:
                lines.append(f"**Agent delegation:** {section.agent_delegation}")
                lines.append("")

            if section.dependencies:
                lines.append(f"**Depends on:** sections {', '.join(section.dependencies)}")
                lines.append("")

            lines.append(f"**Estimated papers:** ~{section.estimated_papers}")
            if section.notes:
                lines.append(f"**Notes:** {section.notes}")
            lines.append("")

        if self.analysis_flow:
            lines.extend([
                "---",
                "",
                "## Analysis Flow",
                "",
            ])
            for step in self.analysis_flow:
                lines.append(f"### Step: {step.description}")
                lines.append(f"- **Agent:** {step.agent}")
                lines.append(f"- **Inputs:** {', '.join(step.inputs)}")
                lines.append(f"- **Outputs:** {', '.join(step.outputs)}")
                if step.tools:
                    lines.append(f"- **Tools:** {', '.join(step.tools)}")
                if step.notes:
                    lines.append(f"- **Notes:** {step.notes}")
                lines.append("")

        return "\n".join(lines)

    def to_dict(self) -> dict:
        """Serialise for inter-agent communication."""
        return {
            "title": self.title,
            "research_question": self.research_question,
            "study_type": self.study_type,
            "scope": self.scope,
            "sections": [
                {
                    "id": s.section_id,
                    "title": s.title,
                    "type": s.section_type,
                    "sub_questions": s.sub_questions,
                    "agent": s.agent_delegation,
                    "dependencies": s.dependencies,
                    "estimated_papers": s.estimated_papers,
                }
                for s in self.sections
            ],
            "analysis_flow": [
                {
                    "id": step.step_id,
                    "description": step.description,
                    "agent": step.agent,
                    "inputs": step.inputs,
                    "outputs": step.outputs,
                }
                for step in self.analysis_flow
            ],
        }


# ═══════════════════════════════════════════════════════════
# STUDY PLAN TEMPLATES
# ═══════════════════════════════════════════════════════════

def literature_review_template(research_question: str,
                                scope: str = "comprehensive") -> StudyPlan:
    """Generate a standard literature review study plan template."""
    plan = StudyPlan(
        title=f"Literature Review: {research_question[:80]}",
        research_question=research_question,
        study_type="literature_review",
        scope=scope,
    )

    plan.sections = [
        StudySection(
            section_id="s1",
            title="Introduction & Background",
            section_type="introduction",
            sub_questions=[
                "What is the current state of knowledge on this topic?",
                "What are the key definitions and concepts?",
                "Why is this topic important / what is the clinical or scientific significance?",
            ],
            search_strategy=SearchStrategy(
                databases=["pubmed", "semantic_scholar"],
                primary_terms=[],  # to be filled by agent
                expected_results="Seminal papers, foundational reviews",
            ),
            estimated_papers=5,
        ),
        StudySection(
            section_id="s2",
            title="Methods & Approaches in the Field",
            section_type="methods",
            sub_questions=[
                "What experimental/computational methods are commonly used?",
                "What are the strengths and limitations of each approach?",
                "Are there emerging methodologies that address previous limitations?",
            ],
            search_strategy=SearchStrategy(
                databases=["pubmed", "semantic_scholar", "biorxiv"],
                primary_terms=[],
                filters={"article_type": ["methods", "review"]},
                expected_results="Methodological papers, benchmarking studies",
            ),
            agent_delegation="pipeline_engineer (for computational method assessment)",
            estimated_papers=10,
        ),
        StudySection(
            section_id="s3",
            title="Key Findings & Evidence",
            section_type="results",
            sub_questions=[
                "What are the main findings in recent literature?",
                "What is the strength and consistency of the evidence?",
                "Are there notable contradictions or conflicting results?",
            ],
            search_strategy=SearchStrategy(
                databases=["pubmed", "semantic_scholar", "europe_pmc"],
                primary_terms=[],
                expected_results="Primary research, cohort studies, clinical trials",
            ),
            dependencies=["s1", "s2"],
            estimated_papers=20,
        ),
        StudySection(
            section_id="s4",
            title="Discussion & Synthesis",
            section_type="discussion",
            sub_questions=[
                "How do the findings fit together?",
                "What are the implications for the field?",
                "What are the limitations of the current evidence?",
                "What are the knowledge gaps?",
            ],
            dependencies=["s3"],
            estimated_papers=5,
            notes="Primarily synthesis; may cite additional context papers",
        ),
        StudySection(
            section_id="s5",
            title="Future Directions & Conclusion",
            section_type="conclusion",
            sub_questions=[
                "What research is needed to address current gaps?",
                "What methodological improvements would strengthen the evidence?",
                "What are the practical/translational implications?",
            ],
            dependencies=["s4"],
            estimated_papers=3,
        ),
    ]

    paper_counts = {"focused": 25, "comprehensive": 50, "exhaustive": 100}
    plan.estimated_total_papers = paper_counts.get(scope, 50)
    plan.key_databases = ["pubmed", "semantic_scholar", "europe_pmc"]

    return plan


def data_interpretation_template(research_question: str,
                                  scope: str = "comprehensive") -> StudyPlan:
    """Generate a study plan for interpreting computational results."""
    plan = StudyPlan(
        title=f"Data Interpretation: {research_question[:80]}",
        research_question=research_question,
        study_type="data_interpretation",
        scope=scope,
    )

    plan.sections = [
        StudySection(
            section_id="s1",
            title="Context & Study Background",
            section_type="introduction",
            sub_questions=[
                "What was the experimental design?",
                "What data was generated and how?",
                "What are the key questions the data should address?",
            ],
            estimated_papers=3,
        ),
        StudySection(
            section_id="s2",
            title="Computational Analysis Summary",
            section_type="methods",
            sub_questions=[
                "What bioinformatics pipelines were used?",
                "What quality control steps were applied?",
                "What statistical methods were used for analysis?",
            ],
            agent_delegation="pipeline_engineer + statistical_ml",
            estimated_papers=5,
        ),
        StudySection(
            section_id="s3",
            title="Results in Biological Context",
            section_type="results",
            sub_questions=[
                "What are the key findings from the analysis?",
                "How do these findings relate to known biology?",
                "Are the identified genes/pathways/variants known players?",
            ],
            search_strategy=SearchStrategy(
                databases=["pubmed", "semantic_scholar", "europe_pmc"],
                primary_terms=[],
                expected_results="Gene function studies, pathway analyses, clinical associations",
            ),
            agent_delegation="literature_db (for database annotations)",
            dependencies=["s2"],
            estimated_papers=20,
        ),
        StudySection(
            section_id="s4",
            title="Comparison with Published Studies",
            section_type="discussion",
            sub_questions=[
                "Do our results confirm or contradict published findings?",
                "How does our dataset compare to similar published datasets?",
                "What novel findings emerge from our analysis?",
            ],
            dependencies=["s3"],
            estimated_papers=15,
        ),
        StudySection(
            section_id="s5",
            title="Conclusions & Recommendations",
            section_type="conclusion",
            sub_questions=[
                "What are the key take-home messages?",
                "What additional experiments or analyses are warranted?",
                "What are the translational implications?",
            ],
            dependencies=["s4"],
            estimated_papers=3,
        ),
    ]

    plan.analysis_flow = [
        AnalysisStep(
            step_id="a1",
            description="QC and preprocessing",
            agent="pipeline_engineer",
            inputs=["raw data files"],
            outputs=["QC report", "processed data"],
            tools=["execute_code", "run_pipeline"],
        ),
        AnalysisStep(
            step_id="a2",
            description="Statistical analysis",
            agent="statistical_ml",
            inputs=["processed data"],
            outputs=["DE results", "enrichment results", "clustering"],
            tools=["execute_code"],
        ),
        AnalysisStep(
            step_id="a3",
            description="Database annotation",
            agent="literature_db",
            inputs=["gene lists", "variant lists"],
            outputs=["functional annotations", "pathway mappings"],
            tools=["query_ncbi", "query_ensembl"],
        ),
        AnalysisStep(
            step_id="a4",
            description="Literature contextualisation",
            agent="research_agent",
            inputs=["DE results", "enrichment results", "annotations"],
            outputs=["contextualised report", "presentation"],
            tools=["search_literature", "generate_report_section", "generate_presentation"],
        ),
    ]

    plan.estimated_total_papers = 50
    plan.key_databases = ["pubmed", "semantic_scholar", "europe_pmc"]

    return plan


# Template registry
STUDY_TEMPLATES = {
    "literature_review": literature_review_template,
    "systematic_review": literature_review_template,  # enhanced version TODO
    "data_interpretation": data_interpretation_template,
    "case_study_analysis": data_interpretation_template,  # adapted version TODO
    "methods_comparison": literature_review_template,  # adapted version TODO
    "hypothesis_generation": literature_review_template,  # adapted version TODO
    "pipeline_evaluation": data_interpretation_template,  # adapted version TODO
}


def create_study_plan(research_question: str,
                      study_type: str = "literature_review",
                      scope: str = "comprehensive",
                      context: str = "") -> StudyPlan:
    """
    Create a study plan from a template.

    The agent will customise the template with specific search terms,
    sub-questions, and delegation based on the research question.
    """
    template_fn = STUDY_TEMPLATES.get(study_type, literature_review_template)
    plan = template_fn(research_question, scope)

    if context:
        # Add context note to the plan
        plan.sections[0].notes = f"Context from other agents: {context[:500]}"

    return plan
