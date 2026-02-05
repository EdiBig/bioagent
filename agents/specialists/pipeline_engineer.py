"""
Pipeline Engineer specialist agent.

Handles code execution, workflow building, and bioinformatics tool execution.
"""

from ..base import BaseAgent, SpecialistType
from ..prompts import PIPELINE_ENGINEER_PROMPT
from ..tools import SPECIALIST_TOOLS


class PipelineEngineerAgent(BaseAgent):
    """
    Specialist for code execution and pipeline building.

    Capabilities:
    - Execute Python, R, and Bash code
    - Build Nextflow, Snakemake, and WDL workflows
    - Run bioinformatics CLI tools
    - Manage files and data processing
    """

    @property
    def specialist_type(self) -> SpecialistType:
        return SpecialistType.PIPELINE_ENGINEER

    @property
    def system_prompt(self) -> str:
        return PIPELINE_ENGINEER_PROMPT

    @property
    def tool_names(self) -> list[str]:
        return SPECIALIST_TOOLS["pipeline_engineer"]

    def _validate_code(self, code: str, language: str) -> list[str]:
        """
        Basic validation of code before execution.

        Returns list of warnings (not errors that block execution).
        """
        warnings = []

        if language == "python":
            # Check for common issues
            if "import os" in code and "os.remove" in code:
                warnings.append("Code includes file deletion operations")
            if "while True" in code and "break" not in code:
                warnings.append("Potential infinite loop detected")
            if "os.system" in code or "subprocess.call" in code:
                warnings.append("Code uses shell execution - verify command safety")

        elif language == "r":
            # Check for common R issues
            if "rm(" in code and "list = ls()" in code:
                warnings.append("Code clears the R environment")
            if "setwd(" in code:
                warnings.append("Code changes working directory")

        elif language == "bash":
            # Check for dangerous bash patterns
            dangerous_patterns = ["rm -rf /", ":(){ :|:& };:", "dd if=", "> /dev/"]
            for pattern in dangerous_patterns:
                if pattern in code:
                    warnings.append(f"Potentially dangerous pattern detected: {pattern}")

        return warnings

    def _format_code_output(self, result: str, language: str) -> str:
        """Format code execution output for readability."""
        if not result:
            return "Code executed successfully (no output)"

        # Truncate very long outputs
        max_length = 10000
        if len(result) > max_length:
            return result[:max_length] + f"\n\n... (output truncated, {len(result)} total characters)"

        return result

    def run(self, task: str, context=None, previous_outputs=None):
        """
        Execute a task with code execution capabilities.

        Overrides base run to add code-specific processing.
        """
        # Add code-specific context hints
        enhanced_task = task

        # If task mentions specific tools, add hints
        tool_hints = {
            "deseq2": "Use R with DESeq2 package",
            "star": "Use bash to run STAR aligner",
            "samtools": "Use bash for samtools commands",
            "fastqc": "Use bash for FastQC",
            "seurat": "Use R with Seurat package",
            "scanpy": "Use Python with scanpy",
        }

        task_lower = task.lower()
        hints = []
        for tool, hint in tool_hints.items():
            if tool in task_lower:
                hints.append(hint)

        if hints:
            enhanced_task = f"{task}\n\nHints: {'; '.join(hints)}"

        return super().run(enhanced_task, context, previous_outputs)
