"""
Unified workflow manager for BioAgent.

Provides a single interface to create, run, and manage workflows
across different workflow engines (Nextflow, Snakemake, WDL).
"""

import json
from pathlib import Path
from typing import Any

from .base import WorkflowResult, WorkflowStatus
from .nextflow import NextflowEngine, NEXTFLOW_TEMPLATES
from .snakemake import SnakemakeEngine, SNAKEMAKE_TEMPLATES
from .wdl import WDLEngine, WDL_TEMPLATES


class WorkflowManager:
    """
    Unified workflow manager for bioinformatics pipelines.

    Supports Nextflow, Snakemake, and WDL workflow engines.
    """

    def __init__(self, workspace_dir: str):
        self.workspace_dir = Path(workspace_dir)
        self.workspace_dir.mkdir(parents=True, exist_ok=True)

        # Initialize engines
        self.nextflow = NextflowEngine(workspace_dir)
        self.snakemake = SnakemakeEngine(workspace_dir)
        self.wdl = WDLEngine(workspace_dir)

        # Engine mapping
        self._engines = {
            "nextflow": self.nextflow,
            "snakemake": self.snakemake,
            "wdl": self.wdl,
        }

        # Template mapping
        self._templates = {
            "nextflow": NEXTFLOW_TEMPLATES,
            "snakemake": SNAKEMAKE_TEMPLATES,
            "wdl": WDL_TEMPLATES,
        }

    def check_engines(self) -> dict[str, tuple[bool, str]]:
        """Check installation status of all workflow engines."""
        return {
            name: engine.check_installation()
            for name, engine in self._engines.items()
        }

    def create_workflow(
        self,
        name: str,
        engine: str,
        definition: str | None = None,
        template: str | None = None,
        params: dict[str, Any] | None = None,
    ) -> WorkflowResult:
        """
        Create a new workflow.

        Args:
            name: Workflow name
            engine: Workflow engine (nextflow, snakemake, wdl)
            definition: Custom workflow definition code
            template: Use a built-in template (rnaseq_basic, variant_calling)
            params: Default parameters for the workflow

        Returns:
            WorkflowResult with the created workflow path
        """
        engine = engine.lower()
        if engine not in self._engines:
            return WorkflowResult(
                success=False,
                message=f"Unknown engine: {engine}. Use: {', '.join(self._engines.keys())}",
                status=WorkflowStatus.FAILED,
            )

        # Get definition from template if not provided
        if definition is None and template:
            templates = self._templates.get(engine, {})
            if template not in templates:
                return WorkflowResult(
                    success=False,
                    message=f"Unknown template: {template}. Available: {', '.join(templates.keys())}",
                    status=WorkflowStatus.FAILED,
                )
            definition = templates[template]

        if definition is None:
            return WorkflowResult(
                success=False,
                message="Must provide either 'definition' or 'template'",
                status=WorkflowStatus.FAILED,
            )

        return self._engines[engine].create_workflow(name, definition, params)

    def run_workflow(
        self,
        workflow_path: str,
        engine: str | None = None,
        params: dict[str, Any] | None = None,
        resume: bool = False,
    ) -> WorkflowResult:
        """
        Execute a workflow.

        Args:
            workflow_path: Path to the workflow file or directory
            engine: Workflow engine (auto-detected if not specified)
            params: Runtime parameters
            resume: Resume from last checkpoint

        Returns:
            WorkflowResult with execution status
        """
        workflow_path = Path(workflow_path)

        # Auto-detect engine if not specified
        if engine is None:
            engine = self._detect_engine(workflow_path)
            if engine is None:
                return WorkflowResult(
                    success=False,
                    message=f"Could not detect workflow engine for: {workflow_path}",
                    status=WorkflowStatus.FAILED,
                )

        engine = engine.lower()
        if engine not in self._engines:
            return WorkflowResult(
                success=False,
                message=f"Unknown engine: {engine}",
                status=WorkflowStatus.FAILED,
            )

        return self._engines[engine].run_workflow(str(workflow_path), params, resume)

    def get_status(self, workflow_id: str, engine: str) -> WorkflowResult:
        """Get status of a workflow."""
        engine = engine.lower()
        if engine not in self._engines:
            return WorkflowResult(
                success=False,
                message=f"Unknown engine: {engine}",
                status=WorkflowStatus.FAILED,
            )
        return self._engines[engine].get_status(workflow_id)

    def get_outputs(self, workflow_id: str, engine: str) -> WorkflowResult:
        """Get outputs from a completed workflow."""
        engine = engine.lower()
        if engine not in self._engines:
            return WorkflowResult(
                success=False,
                message=f"Unknown engine: {engine}",
                status=WorkflowStatus.FAILED,
            )
        return self._engines[engine].get_outputs(workflow_id)

    def list_workflows(self, engine: str | None = None) -> dict[str, list[dict]]:
        """List all workflows, optionally filtered by engine."""
        if engine:
            engine = engine.lower()
            if engine not in self._engines:
                return {}
            return {engine: self._engines[engine].list_workflows()}

        return {
            name: eng.list_workflows()
            for name, eng in self._engines.items()
        }

    def list_templates(self, engine: str | None = None) -> dict[str, list[str]]:
        """List available workflow templates."""
        if engine:
            engine = engine.lower()
            templates = self._templates.get(engine, {})
            return {engine: list(templates.keys())}

        return {
            name: list(templates.keys())
            for name, templates in self._templates.items()
        }

    def get_template(self, engine: str, template: str) -> str | None:
        """Get the content of a workflow template."""
        engine = engine.lower()
        templates = self._templates.get(engine, {})
        return templates.get(template)

    def _detect_engine(self, workflow_path: Path) -> str | None:
        """Auto-detect workflow engine from file/directory."""
        if workflow_path.is_dir():
            if (workflow_path / "main.nf").exists():
                return "nextflow"
            elif (workflow_path / "Snakefile").exists():
                return "snakemake"
            elif (workflow_path / "main.wdl").exists():
                return "wdl"
        else:
            suffix = workflow_path.suffix.lower()
            if suffix == ".nf":
                return "nextflow"
            elif workflow_path.name == "Snakefile" or suffix == ".smk":
                return "snakemake"
            elif suffix == ".wdl":
                return "wdl"
        return None


def format_engine_status(status: dict[str, tuple[bool, str]]) -> str:
    """Format engine installation status for display."""
    lines = ["Workflow Engine Status", "=" * 50]
    for engine, (installed, message) in status.items():
        status_icon = "+" if installed else "x"
        lines.append(f"[{status_icon}] {engine.capitalize()}: {message}")
    return "\n".join(lines)
