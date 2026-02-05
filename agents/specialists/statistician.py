"""
Statistician specialist agent.

Handles statistical analysis, differential expression, and enrichment analysis.
"""

from ..base import BaseAgent, SpecialistType
from ..prompts import STATISTICIAN_PROMPT
from ..tools import SPECIALIST_TOOLS


class StatisticianAgent(BaseAgent):
    """
    Specialist for statistical analysis.

    Capabilities:
    - Differential expression analysis (DESeq2, edgeR, limma)
    - Enrichment analysis (GO, KEGG, GSEA)
    - Batch effect correction
    - Statistical testing and multiple testing correction
    - Experimental design assessment
    """

    @property
    def specialist_type(self) -> SpecialistType:
        return SpecialistType.STATISTICIAN

    @property
    def system_prompt(self) -> str:
        return STATISTICIAN_PROMPT

    @property
    def tool_names(self) -> list[str]:
        return SPECIALIST_TOOLS["statistician"]

    def _assess_experimental_design(self, task: str) -> dict:
        """
        Assess experimental design from task description.

        Returns dict with design characteristics and warnings.
        """
        task_lower = task.lower()
        assessment = {
            "has_replicates": any(w in task_lower for w in ["replicate", "n=", "samples"]),
            "has_batch": any(w in task_lower for w in ["batch", "site", "center", "lab"]),
            "is_paired": any(w in task_lower for w in ["paired", "matched", "before and after"]),
            "is_timecourse": any(w in task_lower for w in ["time", "day", "hour", "week"]),
            "warnings": [],
        }

        # Add warnings based on assessment
        if not assessment["has_replicates"]:
            assessment["warnings"].append(
                "Replicate information not detected - ensure adequate replication"
            )

        if assessment["has_batch"]:
            assessment["warnings"].append(
                "Batch effects may be present - consider batch correction strategy"
            )

        return assessment

    def _get_recommended_method(self, task: str) -> str:
        """Get recommended statistical method based on task."""
        task_lower = task.lower()

        # Differential expression
        if any(w in task_lower for w in ["differential expression", "de analysis", "deg", "dge"]):
            if "single cell" in task_lower or "scrna" in task_lower:
                return "For single-cell DE: consider Seurat FindMarkers (Wilcoxon), MAST, or pseudobulk DESeq2"
            elif "small" in task_lower or "few" in task_lower:
                return "For small sample sizes: DESeq2 with shrunken LFCs or edgeR with robust dispersion"
            else:
                return "For bulk RNA-seq DE: DESeq2 or edgeR with appropriate design matrix"

        # Enrichment
        if any(w in task_lower for w in ["enrichment", "pathway", "go term", "gsea"]):
            if "ranked" in task_lower or "gsea" in task_lower:
                return "For ranked gene lists: GSEA or fgsea"
            else:
                return "For gene lists: clusterProfiler enrichGO/enrichKEGG with appropriate background"

        # Clustering
        if any(w in task_lower for w in ["cluster", "group", "subtype"]):
            return "For clustering: assess stability with bootstrap, use silhouette/gap statistics for k selection"

        return ""

    def run(self, task: str, context=None, previous_outputs=None):
        """
        Execute a statistical analysis task.

        Adds statistical method recommendations and design assessment.
        """
        # Assess experimental design
        design = self._assess_experimental_design(task)

        # Get method recommendation
        recommendation = self._get_recommended_method(task)

        # Build enhanced task with statistical guidance
        enhancements = []

        if design["warnings"]:
            enhancements.append("Design considerations:\n- " + "\n- ".join(design["warnings"]))

        if recommendation:
            enhancements.append(f"Recommended approach: {recommendation}")

        enhanced_task = task
        if enhancements:
            enhanced_task = f"{task}\n\n## Statistical Guidance\n" + "\n".join(enhancements)

        return super().run(enhanced_task, context, previous_outputs)
