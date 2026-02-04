"""
Workflow engine integrations for BioAgent.

Supports Nextflow, Snakemake, and WDL/Cromwell for reproducible pipeline execution.
"""

from .base import WorkflowResult, WorkflowStatus
from .nextflow import NextflowEngine, NEXTFLOW_TEMPLATES
from .snakemake import SnakemakeEngine, SNAKEMAKE_TEMPLATES
from .wdl import WDLEngine, WDL_TEMPLATES
from .manager import WorkflowManager, format_engine_status

__all__ = [
    "WorkflowResult",
    "WorkflowStatus",
    "NextflowEngine",
    "SnakemakeEngine",
    "WDLEngine",
    "WorkflowManager",
    "format_engine_status",
    "NEXTFLOW_TEMPLATES",
    "SNAKEMAKE_TEMPLATES",
    "WDL_TEMPLATES",
]
