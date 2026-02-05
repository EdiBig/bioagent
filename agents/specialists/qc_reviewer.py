"""
QC Reviewer specialist agent.

Handles quality control assessment and validation of analysis outputs.
"""

from ..base import BaseAgent, SpecialistType
from ..prompts import QC_REVIEWER_PROMPT
from ..tools import SPECIALIST_TOOLS


class QCReviewerAgent(BaseAgent):
    """
    Specialist for quality control and validation.

    Capabilities:
    - Assess analysis quality metrics
    - Identify potential artifacts and biases
    - Check for outliers and batch effects
    - Validate reproducibility
    - Review statistical assumptions
    """

    @property
    def specialist_type(self) -> SpecialistType:
        return SpecialistType.QC_REVIEWER

    @property
    def system_prompt(self) -> str:
        return QC_REVIEWER_PROMPT

    @property
    def tool_names(self) -> list[str]:
        return SPECIALIST_TOOLS["qc_reviewer"]

    def _build_qc_checklist(self, task: str) -> list[str]:
        """
        Build a QC checklist based on the analysis type.

        Returns list of QC items to check.
        """
        task_lower = task.lower()
        checklist = []

        # General QC items
        checklist.extend([
            "Check for missing or invalid values",
            "Verify sample sizes and replication",
            "Assess data distributions",
        ])

        # RNA-seq specific
        if any(w in task_lower for w in ["rna-seq", "rnaseq", "expression", "deseq", "edger"]):
            checklist.extend([
                "Check mapping rates (expect >70%)",
                "Assess duplication rates (<30% typical)",
                "Review library complexity",
                "Check for 3'/5' bias",
                "Verify gene detection rates",
                "Assess sample clustering (PCA)",
                "Check for batch effects",
            ])

        # Differential expression
        if any(w in task_lower for w in ["differential", "de analysis", "deg", "dge"]):
            checklist.extend([
                "Verify appropriate normalization",
                "Check dispersion estimates",
                "Review p-value distribution (should be uniform under null)",
                "Assess log2FC distribution",
                "Verify multiple testing correction applied",
                "Check MA/volcano plot for asymmetry",
            ])

        # Variant calling
        if any(w in task_lower for w in ["variant", "snp", "mutation", "vcf"]):
            checklist.extend([
                "Check Ti/Tv ratio (expect ~2.0 for WGS)",
                "Assess het/hom ratio",
                "Review variant depth distribution",
                "Check for batch effects in variant calls",
                "Verify genotype quality metrics",
            ])

        # Single-cell
        if any(w in task_lower for w in ["single cell", "scrna", "10x", "seurat", "scanpy"]):
            checklist.extend([
                "Check cells per sample",
                "Assess UMI/gene counts per cell",
                "Review mitochondrial gene fraction",
                "Check doublet rates",
                "Assess batch integration quality",
                "Verify cluster stability",
            ])

        # Enrichment
        if any(w in task_lower for w in ["enrichment", "pathway", "go term", "gsea"]):
            checklist.extend([
                "Verify appropriate background used",
                "Check gene set sizes",
                "Assess biological coherence of top terms",
                "Review for redundant/similar terms",
            ])

        return checklist

    def run(self, task: str, context=None, previous_outputs=None):
        """
        Execute a QC review task.

        Adds QC checklist to guide the review.
        """
        # Build QC checklist
        checklist = self._build_qc_checklist(task)

        # Add checklist to task
        checklist_text = "\n".join(f"- [ ] {item}" for item in checklist)
        enhanced_task = f"{task}\n\n## QC Checklist\n{checklist_text}"

        # Add instruction for structured output
        enhanced_task += """

## Output Format

Please structure your QC review as:

1. **Summary**: Overall quality assessment (Good/Acceptable/Concerning/Poor)

2. **Metrics Reviewed**: List each metric checked with its value and status

3. **Issues Identified**: Any problems found, ranked by severity
   - CRITICAL: Must be addressed before proceeding
   - WARNING: Should be investigated
   - NOTE: Minor observation

4. **Recommendations**: Specific actions to address issues

5. **Conclusion**: Final assessment and go/no-go recommendation
"""

        return super().run(enhanced_task, context, previous_outputs)
