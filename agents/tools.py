"""
Tool filtering and management for specialist agents.

Defines which tools each specialist has access to and provides
utilities for getting filtered tool definitions.
"""

from typing import Any

# Import tool definitions from main definitions module
from definitions import TOOLS


# Tool subsets for each specialist type
SPECIALIST_TOOLS: dict[str, list[str]] = {
    # Pipeline Engineer: Code execution, file management, workflows, visualization, cloud, ML, data ingestion, workspace
    "pipeline_engineer": [
        "execute_python",
        "execute_r",
        "execute_bash",
        "workflow_create",
        "workflow_run",
        "workflow_status",
        "workflow_outputs",
        "workflow_list",
        "workflow_check_engines",
        "read_file",
        "write_file",
        "list_files",
        "memory_search",
        "memory_save_artifact",
        "create_plot",
        "generate_report",
        "create_dashboard",
        "cloud_submit_job",
        "cloud_job_status",
        "cloud_job_logs",
        "cloud_cancel_job",
        "cloud_list_jobs",
        "cloud_estimate_cost",
        # ML/AI tools
        "predict_pathogenicity",
        "predict_structure",
        "predict_drug_response",
        "annotate_cell_types",
        "discover_biomarkers",
        # Data ingestion tools
        "ingest_file",
        "ingest_batch",
        "ingest_directory",
        "list_ingested_files",
        "get_file_profile",
        "validate_dataset",
        # Workspace & Analysis tracking
        "start_analysis",
        "complete_analysis",
        "list_analyses",
        "get_analysis",
        "manage_project",
        "tag_file",
    ],

    # Literature Agent: Database queries, web search, memory, data awareness
    "literature_agent": [
        "query_ncbi",
        "query_ensembl",
        "query_uniprot",
        "query_pdb",
        "query_alphafold",
        "query_interpro",
        "query_kegg",
        "query_reactome",
        "query_string",
        "query_go",
        "query_gnomad",
        "web_search",
        "read_file",
        "memory_search",
        "memory_save_artifact",
        "memory_list_artifacts",
        "memory_read_artifact",
        "memory_get_entities",
        # Data awareness (read-only)
        "list_ingested_files",
        "get_file_profile",
    ],

    # Statistician: Code execution for stats, enrichment databases, visualization, ML, data validation
    "statistician": [
        "execute_python",
        "execute_r",
        "query_go",
        "query_kegg",
        "query_reactome",
        "query_string",  # For enrichment analysis
        "read_file",
        "write_file",
        "list_files",
        "memory_search",
        "memory_save_artifact",
        "memory_list_artifacts",
        "memory_read_artifact",
        "create_plot",
        "generate_report",
        # ML/AI tools
        "predict_drug_response",
        "annotate_cell_types",
        "discover_biomarkers",
        # Data validation tools
        "list_ingested_files",
        "get_file_profile",
        "validate_dataset",
    ],

    # QC Reviewer: Read-only analysis tools, data quality assessment
    "qc_reviewer": [
        "read_file",
        "list_files",
        "memory_search",
        "memory_list_artifacts",
        "memory_read_artifact",
        # Data quality assessment (read-only)
        "list_ingested_files",
        "get_file_profile",
        "validate_dataset",
    ],

    # Domain Expert: Database queries for interpretation, no code execution, ML interpretation
    "domain_expert": [
        "query_ncbi",
        "query_ensembl",
        "query_uniprot",
        "query_pdb",
        "query_alphafold",
        "query_interpro",
        "query_kegg",
        "query_reactome",
        "query_string",
        "query_go",
        "query_gnomad",
        "web_search",
        "read_file",
        "memory_search",
        "memory_get_entities",
        # ML/AI tools for interpretation
        "predict_pathogenicity",
        "predict_structure",
        "predict_drug_response",
    ],

    # Coordinator: Limited tools - mainly for context gathering and analysis tracking
    "coordinator": [
        "read_file",
        "list_files",
        "memory_search",
        "memory_get_entities",
        "memory_list_artifacts",
        # Analysis tracking (read-only for context)
        "list_analyses",
        "get_analysis",
    ],
}


def get_specialist_tools(tool_names: list[str]) -> list[dict[str, Any]]:
    """
    Get tool definitions filtered to the specified tool names.

    Args:
        tool_names: List of tool names to include

    Returns:
        List of tool definition dicts for the specified tools
    """
    return [tool for tool in TOOLS if tool["name"] in tool_names]


def get_tools_for_specialist(specialist_type: str) -> list[dict[str, Any]]:
    """
    Get tool definitions for a specific specialist type.

    Args:
        specialist_type: One of the SPECIALIST_TOOLS keys

    Returns:
        List of tool definition dicts for that specialist
    """
    tool_names = SPECIALIST_TOOLS.get(specialist_type, [])
    return get_specialist_tools(tool_names)


def get_all_specialist_tool_names() -> dict[str, list[str]]:
    """Return a copy of the SPECIALIST_TOOLS mapping."""
    return SPECIALIST_TOOLS.copy()


def validate_tool_assignment(specialist_type: str, tool_name: str) -> bool:
    """
    Check if a tool is assigned to a specialist type.

    Args:
        specialist_type: The specialist type to check
        tool_name: The tool name to check

    Returns:
        True if the tool is assigned to the specialist
    """
    return tool_name in SPECIALIST_TOOLS.get(specialist_type, [])


def get_tool_description(tool_name: str) -> str | None:
    """
    Get the description for a specific tool.

    Args:
        tool_name: Name of the tool

    Returns:
        Tool description or None if not found
    """
    for tool in TOOLS:
        if tool["name"] == tool_name:
            return tool.get("description", "")
    return None


def summarize_specialist_capabilities() -> dict[str, dict[str, Any]]:
    """
    Generate a summary of each specialist's capabilities based on their tools.

    Returns:
        Dict mapping specialist type to capability summary
    """
    summaries = {}

    capability_categories = {
        "code_execution": ["execute_python", "execute_r", "execute_bash"],
        "workflow_management": ["workflow_create", "workflow_run", "workflow_status", "workflow_outputs", "workflow_list", "workflow_check_engines"],
        "database_queries": ["query_ncbi", "query_ensembl", "query_uniprot", "query_pdb", "query_alphafold", "query_interpro", "query_kegg", "query_reactome", "query_string", "query_go", "query_gnomad"],
        "file_operations": ["read_file", "write_file", "list_files"],
        "web_search": ["web_search"],
        "memory_access": ["memory_search", "memory_save_artifact", "memory_list_artifacts", "memory_read_artifact", "memory_get_entities"],
        "visualization": ["create_plot", "generate_report", "create_dashboard"],
        "cloud_hpc": ["cloud_submit_job", "cloud_job_status", "cloud_job_logs", "cloud_cancel_job", "cloud_list_jobs", "cloud_estimate_cost"],
        "ml_ai": ["predict_pathogenicity", "predict_structure", "predict_drug_response", "annotate_cell_types", "discover_biomarkers"],
        "data_ingestion": ["ingest_file", "ingest_batch", "ingest_directory", "list_ingested_files", "get_file_profile", "validate_dataset"],
        "workspace_tracking": ["start_analysis", "complete_analysis", "list_analyses", "get_analysis", "manage_project", "tag_file"],
    }

    for specialist, tools in SPECIALIST_TOOLS.items():
        capabilities = {}
        for category, category_tools in capability_categories.items():
            matching = [t for t in tools if t in category_tools]
            if matching:
                capabilities[category] = matching

        summaries[specialist] = {
            "tool_count": len(tools),
            "capabilities": capabilities,
            "tools": tools,
        }

    return summaries


# Pre-computed tool counts for quick reference
TOOL_COUNTS = {
    specialist: len(tools)
    for specialist, tools in SPECIALIST_TOOLS.items()
}
