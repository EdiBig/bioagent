"""
Integration guide — how to wire the file ingestion system into BioAgent.

This module provides the tool handler that plugs into agent.py's
_execute_tool() method, plus a convenience mixin for the BioAgent class.
"""

from pathlib import Path
from data_input.file_ingestor import FileIngestor, IngestResult
from data_input.dataset_validator import DatasetValidator


class IngestHandler:
    """
    Handles ingestion tool calls from the agent loop.

    Wire this into your existing agent.py by:

    1. Add the tool definitions to your tools list:

        from ingest_tool_definitions import get_ingest_tools
        from definitions import get_tools

        all_tools = get_tools() + get_ingest_tools()

    2. Create an IngestHandler in your BioAgent.__init__:

        self.ingest_handler = IngestHandler(workspace_dir=self.config.workspace_dir)

    3. Add routing in _execute_tool():

        elif name in self.ingest_handler.handled_tools:
            return self.ingest_handler.handle(name, input_data)
    """

    handled_tools = {
        "ingest_file",
        "ingest_batch",
        "ingest_directory",
        "list_ingested_files",
        "get_file_profile",
        "validate_dataset",
    }

    def __init__(self, workspace_dir: str = "/workspace"):
        self.ingestor = FileIngestor(workspace_dir=workspace_dir)
        self.validator = DatasetValidator()

    def handle(self, tool_name: str, input_data: dict) -> str:
        """
        Handle a tool call and return a string result for the agent.
        """
        try:
            if tool_name == "ingest_file":
                return self._handle_ingest_file(input_data)
            elif tool_name == "ingest_batch":
                return self._handle_ingest_batch(input_data)
            elif tool_name == "ingest_directory":
                return self._handle_ingest_directory(input_data)
            elif tool_name == "list_ingested_files":
                return self._handle_list_ingested()
            elif tool_name == "get_file_profile":
                return self._handle_get_profile(input_data)
            elif tool_name == "validate_dataset":
                return self._handle_validate(input_data)
            else:
                return f"Unknown ingestion tool: {tool_name}"
        except Exception as e:
            return f"Ingestion error ({tool_name}): {e}"

    def _handle_ingest_file(self, input_data: dict) -> str:
        source = input_data["source"]
        label = input_data.get("label", "")

        profile = self.ingestor.ingest(source, label=label)
        return profile.to_agent_summary()

    def _handle_ingest_batch(self, input_data: dict) -> str:
        sources = input_data["sources"]
        labels = input_data.get("labels", [])

        result = self.ingestor.ingest_batch(sources, labels=labels or None)
        return result.to_agent_context()

    def _handle_ingest_directory(self, input_data: dict) -> str:
        directory = input_data["directory"]
        pattern = input_data.get("pattern", "*")
        recursive = input_data.get("recursive", False)

        result = self.ingestor.ingest_directory(
            directory, pattern=pattern, recursive=recursive
        )
        return result.to_agent_context()

    def _handle_list_ingested(self) -> str:
        return self.ingestor.get_ingested_files_summary()

    def _handle_get_profile(self, input_data: dict) -> str:
        label = input_data["label_or_name"]
        profile = self.ingestor.get_profile(label)
        if profile:
            return profile.to_agent_summary()
        else:
            # Try to find by partial match
            ingested = self.ingestor.list_ingested()
            matches = [
                f for f in ingested
                if label.lower() in f["label"].lower()
                or label.lower() in f["file_name"].lower()
            ]
            if matches:
                return (
                    f"No exact match for '{label}'. Did you mean one of:\n"
                    + "\n".join(f"  - {m['label']} ({m['file_name']})" for m in matches)
                )
            return f"No ingested file found with label or name '{label}'"

    def _handle_validate(self, input_data: dict) -> str:
        file_labels = input_data["file_labels"]
        analysis_type = input_data.get("analysis_type", "auto")

        profiles = []
        for label in file_labels:
            profile = self.ingestor.get_profile(label)
            if profile:
                profiles.append(profile)

        if not profiles:
            return "No matching ingested files found. Use ingest_file first."

        result = self.validator.validate(profiles, analysis_type=analysis_type)
        return result.to_agent_summary()


# ═══════════════════════════════════════════════════════════════════
# INTEGRATION CODE FOR agent.py
# ═══════════════════════════════════════════════════════════════════

AGENT_INTEGRATION_PATCH = """
# ─── Add to agent.py imports ─────────────────────────────────────

from ingest_tool_definitions import get_ingest_tools
from integration import IngestHandler

# ─── Add to BioAgent.__init__() ──────────────────────────────────

self.ingest_handler = IngestHandler(workspace_dir=self.config.workspace_dir)

# ─── Modify _call_claude() to include ingest tools ───────────────
# Replace:  "tools": get_tools(),
# With:     "tools": get_tools() + get_ingest_tools(),

# ─── Add to _execute_tool() ──────────────────────────────────────
# Add this block before the final `else: return f"Unknown tool"`:

elif name in self.ingest_handler.handled_tools:
    return self.ingest_handler.handle(name, input_data)

# ─── That's it! The agent can now ingest and analyse files. ──────
"""


def print_integration_guide():
    """Print the integration guide to stdout."""
    print("=" * 60)
    print("BioAgent File Ingestion — Integration Guide")
    print("=" * 60)
    print(AGENT_INTEGRATION_PATCH)
    print("=" * 60)
    print("\nThe agent will now automatically:")
    print("  1. Accept files from paths, URLs, S3, or pasted data")
    print("  2. Detect the bioinformatics format (30+ formats)")
    print("  3. Generate rich profiles with stats and quality flags")
    print("  4. Suggest appropriate analyses based on the data")
    print("  5. Validate multi-file datasets for specific workflows")
    print()
    print("Example user queries the agent can now handle:")
    print('  "Ingest /data/experiment/reads_R1.fastq.gz and assess quality"')
    print('  "Load these files: counts.csv, metadata.csv — run DE analysis"')
    print('  "Scan /data/project/ for all VCF files and summarise variants"')
    print('  ">MVLSPADKTNVK... — what protein is this?"')


if __name__ == "__main__":
    print_integration_guide()
