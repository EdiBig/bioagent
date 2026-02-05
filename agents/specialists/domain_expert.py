"""
Domain Expert specialist agent.

Handles biological interpretation and domain expertise.
"""

from ..base import BaseAgent, SpecialistType
from ..prompts import DOMAIN_EXPERT_PROMPT
from ..tools import SPECIALIST_TOOLS


class DomainExpertAgent(BaseAgent):
    """
    Specialist for biological interpretation and domain expertise.

    Capabilities:
    - Biological interpretation of computational results
    - Understanding molecular mechanisms and pathways
    - Clinical and translational significance assessment
    - Contextualizing findings in the literature
    - Generating biological hypotheses
    """

    @property
    def specialist_type(self) -> SpecialistType:
        return SpecialistType.DOMAIN_EXPERT

    @property
    def system_prompt(self) -> str:
        return DOMAIN_EXPERT_PROMPT

    @property
    def tool_names(self) -> list[str]:
        return SPECIALIST_TOOLS["domain_expert"]

    def _identify_interpretation_context(self, task: str) -> dict:
        """
        Identify the biological context for interpretation.

        Returns dict with context hints for interpretation.
        """
        task_lower = task.lower()

        context = {
            "domain": None,
            "level": [],
            "focus_areas": [],
        }

        # Identify domain
        domains = {
            "cancer": ["cancer", "tumor", "tumour", "oncol", "malignant", "metasta"],
            "immunology": ["immune", "inflammat", "cytokine", "t cell", "b cell", "antibod"],
            "neurology": ["neuro", "brain", "neuron", "cognit", "synapse"],
            "cardiology": ["cardiac", "heart", "cardiovascular", "arrhythm"],
            "metabolism": ["metabol", "diabetes", "glucose", "lipid", "obesity"],
            "development": ["develop", "embryo", "differentiat", "stem cell"],
            "infectious": ["infect", "virus", "bacteria", "pathogen", "host"],
        }

        for domain, keywords in domains.items():
            if any(kw in task_lower for kw in keywords):
                context["domain"] = domain
                break

        # Identify analysis level
        levels = {
            "molecular": ["gene", "protein", "mrna", "transcript", "variant", "mutation"],
            "cellular": ["cell", "cellular", "organelle", "membrane"],
            "tissue": ["tissue", "organ", "histolog"],
            "organism": ["patient", "phenotype", "clinical", "disease"],
            "population": ["population", "cohort", "epidemiol", "gwas"],
        }

        for level, keywords in levels.items():
            if any(kw in task_lower for kw in keywords):
                context["level"].append(level)

        # Identify focus areas
        if any(w in task_lower for w in ["pathway", "signal", "cascade"]):
            context["focus_areas"].append("signaling_pathways")
        if any(w in task_lower for w in ["drug", "therapeutic", "treatment", "target"]):
            context["focus_areas"].append("therapeutic_potential")
        if any(w in task_lower for w in ["mechanism", "how does", "function"]):
            context["focus_areas"].append("molecular_mechanism")
        if any(w in task_lower for w in ["clinical", "prognosis", "diagnosis"]):
            context["focus_areas"].append("clinical_significance")
        if any(w in task_lower for w in ["interaction", "network", "partner"]):
            context["focus_areas"].append("interaction_networks")

        return context

    def _get_interpretation_framework(self, context: dict) -> str:
        """Get interpretation framework based on context."""
        frameworks = []

        if context["domain"] == "cancer":
            frameworks.append("""
## Cancer Biology Framework
- Consider hallmarks of cancer (proliferation, apoptosis evasion, etc.)
- Assess oncogene vs tumor suppressor roles
- Consider druggable targets and existing therapies
- Evaluate prognostic/diagnostic potential""")

        elif context["domain"] == "immunology":
            frameworks.append("""
## Immunology Framework
- Consider immune cell types involved
- Assess inflammatory vs anti-inflammatory balance
- Evaluate cytokine/chemokine signaling
- Consider autoimmune and immunotherapy implications""")

        if "therapeutic_potential" in context.get("focus_areas", []):
            frameworks.append("""
## Therapeutic Assessment
- Identify druggable targets
- Consider existing drugs and clinical trials
- Assess potential side effects (essential gene functions)
- Evaluate biomarker potential""")

        if "clinical_significance" in context.get("focus_areas", []):
            frameworks.append("""
## Clinical Relevance
- Consider diagnostic applications
- Assess prognostic value
- Evaluate patient stratification potential
- Consider companion diagnostics""")

        return "\n".join(frameworks)

    def run(self, task: str, context=None, previous_outputs=None):
        """
        Execute a biological interpretation task.

        Adds interpretation framework and context.
        """
        # Identify interpretation context
        interp_context = self._identify_interpretation_context(task)

        # Get appropriate framework
        framework = self._get_interpretation_framework(interp_context)

        # Build enhanced task
        enhancements = []

        if interp_context["domain"]:
            enhancements.append(f"Domain: {interp_context['domain'].title()}")

        if interp_context["level"]:
            enhancements.append(f"Analysis level: {', '.join(interp_context['level'])}")

        if interp_context["focus_areas"]:
            enhancements.append(
                f"Focus areas: {', '.join(a.replace('_', ' ') for a in interp_context['focus_areas'])}"
            )

        enhanced_task = task

        if enhancements:
            enhanced_task += "\n\n## Context\n" + "\n".join(f"- {e}" for e in enhancements)

        if framework:
            enhanced_task += f"\n\n{framework}"

        # Add output structure
        enhanced_task += """

## Expected Output Structure

1. **Summary Interpretation**: Key biological findings in 2-3 sentences

2. **Detailed Analysis**:
   - Molecular/cellular mechanisms
   - Pathway involvement
   - Known biology connections

3. **Clinical/Translational Relevance** (if applicable):
   - Disease associations
   - Therapeutic implications
   - Biomarker potential

4. **Confidence Assessment**:
   - Well-established findings
   - Speculative interpretations
   - Knowledge gaps

5. **Suggested Follow-up**:
   - Experiments to validate findings
   - Additional analyses
   - Literature to review
"""

        return super().run(enhanced_task, context, previous_outputs)
