"""
BioAgent: Core agent loop.

Implements the agentic tool-use loop using the Anthropic API.
The agent receives a user message, reasons about it, optionally calls
tools (code execution, database queries, file I/O), and iterates
until it has a final response.
"""

import json
import sys
import time
from datetime import datetime
from pathlib import Path

import anthropic

from config import Config
from system import SYSTEM_PROMPT
from definitions import get_tools
from code_executor import CodeExecutor
from ncbi import NCBIClient
from ensembl import EnsemblClient
from uniprot import UniProtClient
from kegg import KEGGClient
from string_db import STRINGClient
from pdb_client import PDBClient
from alphafold import AlphaFoldClient
from interpro import InterProClient
from reactome import ReactomeClient
from gene_ontology import GeneOntologyClient
from gnomad import GnomADClient
from file_manager import FileManager
from workflows import WorkflowManager, format_engine_status
from web_search import WebSearchClient
from memory import MemoryConfig, ContextManager


class BioAgent:
    """
    An agentic bioinformatics assistant powered by Claude.

    Usage:
        agent = BioAgent()
        response = agent.run("Analyse this RNA-seq dataset...")
    """

    def __init__(self, config: Config | None = None):
        self.config = config or Config.from_env()

        # Validate config
        issues = self.config.validate()
        if any("ANTHROPIC_API_KEY" in i for i in issues):
            raise ValueError(
                "ANTHROPIC_API_KEY is not set. "
                "Set it as an environment variable or in a .env file."
            )
        for issue in issues:
            self._log(f"⚠️  Config warning: {issue}")

        # Initialise Anthropic client
        self.client = anthropic.Anthropic(api_key=self.config.anthropic_api_key)

        # Initialise tools
        self.executor = CodeExecutor(
            workspace_dir=self.config.workspace_dir,
            use_docker=self.config.use_docker,
            docker_image=self.config.docker_image,
        )
        self.ncbi = NCBIClient(
            api_key=self.config.ncbi_api_key or None,
            email=self.config.ncbi_email or None,
        )
        self.ensembl = EnsemblClient()
        self.uniprot = UniProtClient()
        self.kegg = KEGGClient()
        self.string = STRINGClient()
        self.pdb = PDBClient()
        self.alphafold = AlphaFoldClient()
        self.interpro = InterProClient()
        self.reactome = ReactomeClient()
        self.go = GeneOntologyClient()
        self.gnomad = GnomADClient()
        self.web_search = WebSearchClient()
        self.files = FileManager(workspace_dir=self.config.workspace_dir)
        self.workflows = WorkflowManager(workspace_dir=self.config.workspace_dir)

        # Initialize memory system
        self.memory = None
        if self.config.enable_memory:
            try:
                memory_config = MemoryConfig.from_env(self.config.workspace_dir)
                memory_config.enable_rag = self.config.enable_rag
                memory_config.enable_summaries = self.config.enable_summaries
                memory_config.enable_knowledge_graph = self.config.enable_knowledge_graph
                memory_config.enable_artifacts = self.config.enable_artifacts
                memory_config.summary_after_rounds = self.config.summary_after_rounds
                self.memory = ContextManager(memory_config, self.client)
                self._log(f"🧠 Memory system initialized: {memory_config}")
            except Exception as e:
                self._log(f"⚠️  Memory system initialization failed: {e}")
                self.memory = None

        # Conversation history
        self.messages: list[dict] = []

        # Session log
        self._session_log: list[dict] = []

    def run(self, user_message: str, use_complex_model: bool = False) -> str:
        """
        Process a user message through the agentic loop.

        Args:
            user_message: The user's input/question/task
            use_complex_model: Use the more powerful (and expensive) model

        Returns:
            The agent's final text response
        """
        # Add user message to history
        self.messages.append({"role": "user", "content": user_message})

        model = self.config.model_complex if use_complex_model else self.config.model
        self._log(f"\n{'='*60}")
        self._log(f"🧬 BioAgent [{model}]")
        self._log(f"{'='*60}")
        self._log(f"📝 User: {user_message[:200]}{'...' if len(user_message) > 200 else ''}")

        # Track tools used during this query
        tools_used = []

        # Agentic loop
        for round_num in range(1, self.config.max_tool_rounds + 1):
            self._log(f"\n--- Round {round_num} ---")

            # Get enhanced context from memory system
            memory_context = ""
            if self.memory:
                try:
                    memory_context = self.memory.get_enhanced_context(
                        user_message, self.messages, round_num
                    )
                    if memory_context and round_num == 1:
                        self._log(f"🧠 Memory context injected ({len(memory_context)} chars)")
                except Exception as e:
                    self._log(f"⚠️  Memory context error: {e}")

            # Call Claude
            response = self._call_claude(model, memory_context)

            # Check for stop conditions
            if response.stop_reason == "end_turn":
                # Extract final text
                final_text = self._extract_text(response)
                self.messages.append({"role": "assistant", "content": response.content})
                self._log(f"\n✅ Final response ({len(final_text)} chars)")

                # Update memory with completed analysis
                if self.memory:
                    try:
                        self.memory.on_analysis_complete(user_message, final_text, tools_used)
                    except Exception as e:
                        self._log(f"⚠️  Memory analysis save error: {e}")

                # Auto-save results
                self._auto_save_result(user_message, final_text, tools_used if tools_used else None)

                return final_text

            elif response.stop_reason == "tool_use":
                # Process tool calls and track tools used
                tool_results = self._process_tool_calls(response)

                # Extract tool names from response
                for block in response.content:
                    if block.type == "tool_use":
                        if block.name not in tools_used:
                            tools_used.append(block.name)

                # Add assistant message + tool results to history
                self.messages.append({"role": "assistant", "content": response.content})
                self.messages.append({"role": "user", "content": tool_results})

                # Update memory after round complete
                if self.memory:
                    try:
                        self.memory.on_round_complete(self.messages, round_num, tools_used)
                    except Exception as e:
                        self._log(f"⚠️  Memory round update error: {e}")

            else:
                self._log(f"⚠️  Unexpected stop reason: {response.stop_reason}")
                final_text = self._extract_text(response)
                self.messages.append({"role": "assistant", "content": response.content})

                # Auto-save results
                self._auto_save_result(user_message, final_text, tools_used if tools_used else None)

                return final_text

        # Max rounds exceeded
        self._log(f"⚠️  Max tool rounds ({self.config.max_tool_rounds}) exceeded")
        max_rounds_msg = (
            "I've reached the maximum number of tool-use iterations. "
            "Here's what I've done so far — you may want to continue from here."
        )

        # Auto-save even on max rounds
        self._auto_save_result(user_message, max_rounds_msg, tools_used if tools_used else None)

        return max_rounds_msg

    def chat(self):
        """
        Interactive chat loop. Run from the terminal.
        """
        print("🧬 BioAgent — Interactive Bioinformatics Assistant")
        print("=" * 55)
        print(f"Model: {self.config.model}")
        print(f"Workspace: {self.config.workspace_dir}")
        print("Type 'quit' to exit, 'reset' to clear history,")
        print("'complex' before a message to use the advanced model.")
        print("=" * 55)
        print()

        while True:
            try:
                user_input = input("You: ").strip()
            except (EOFError, KeyboardInterrupt):
                print("\nGoodbye! 👋")
                break

            if not user_input:
                continue
            if user_input.lower() == "quit":
                print("Goodbye! 👋")
                break
            if user_input.lower() == "reset":
                self.messages = []
                print("🔄 Conversation history cleared.\n")
                continue

            # Check for complex model flag
            use_complex = False
            if user_input.lower().startswith("complex "):
                use_complex = True
                user_input = user_input[8:]
                print(f"  Using advanced model: {self.config.model_complex}")

            try:
                response = self.run(user_input, use_complex_model=use_complex)
                print(f"\nBioAgent: {response}\n")
            except anthropic.APIError as e:
                print(f"\n❌ API Error: {e}\n")
            except Exception as e:
                print(f"\n❌ Error: {e}\n")

    # ── Internal Methods ─────────────────────────────────────────────

    def _call_claude(self, model: str, memory_context: str = "") -> anthropic.types.Message:
        """Make an API call to Claude with tools."""
        # Build system prompt with optional memory context
        system_prompt = SYSTEM_PROMPT
        if memory_context:
            system_prompt = f"{SYSTEM_PROMPT}\n\n{memory_context}"

        kwargs = {
            "model": model,
            "max_tokens": self.config.max_tokens,
            "system": system_prompt,
            "tools": get_tools(),
            "messages": self.messages,
        }

        # Only set temperature for non-extended-thinking calls
        if not self.config.enable_extended_thinking:
            kwargs["temperature"] = self.config.temperature

        return self.client.messages.create(**kwargs)

    def _process_tool_calls(self, response) -> list[dict]:
        """Process all tool calls in a response and return results."""
        tool_results = []

        for block in response.content:
            if block.type == "tool_use":
                tool_name = block.name
                tool_input = block.input
                tool_id = block.id

                self._log(f"🔧 Tool: {tool_name}")
                if self.config.verbose:
                    self._log_tool_input(tool_name, tool_input)

                # Execute the tool
                result = self._execute_tool(tool_name, tool_input)

                if self.config.verbose:
                    self._log(f"   Result: {result[:300]}{'...' if len(result) > 300 else ''}")

                # Update memory with tool result (skip memory tools themselves)
                if self.memory and not tool_name.startswith("memory_"):
                    try:
                        self.memory.on_tool_result(tool_name, tool_input, result)
                    except Exception as e:
                        self._log(f"⚠️  Memory update error: {e}")

                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": tool_id,
                    "content": result,
                })

            elif block.type == "text" and block.text.strip():
                self._log(f"💭 Thinking: {block.text[:200]}{'...' if len(block.text) > 200 else ''}")

        return tool_results

    def _execute_tool(self, name: str, input_data: dict) -> str:
        """Route a tool call to the appropriate handler."""
        try:
            if name == "execute_python":
                result = self.executor.execute_python(
                    code=input_data["code"],
                    timeout=input_data.get("timeout", 300),
                )
                return result.to_string()

            elif name == "execute_r":
                result = self.executor.execute_r(
                    code=input_data["code"],
                    timeout=input_data.get("timeout", 300),
                )
                return result.to_string()

            elif name == "execute_bash":
                result = self.executor.execute_bash(
                    command=input_data["command"],
                    timeout=input_data.get("timeout", 600),
                    working_dir=input_data.get("working_dir"),
                )
                return result.to_string()

            elif name == "query_ncbi":
                result = self.ncbi.query(
                    database=input_data["database"],
                    operation=input_data["operation"],
                    query=input_data["query"],
                    max_results=input_data.get("max_results", 10),
                    return_type=input_data.get("return_type", "json"),
                )
                return result.to_string()

            elif name == "query_ensembl":
                result = self.ensembl.query(
                    endpoint=input_data["endpoint"],
                    params=input_data.get("params", {}),
                    species=input_data.get("species", "homo_sapiens"),
                )
                return result.to_string()

            elif name == "query_uniprot":
                result = self.uniprot.query(
                    query=input_data["query"],
                    operation=input_data.get("operation", "search"),
                    format=input_data.get("format", "json"),
                    limit=input_data.get("limit", 10),
                )
                return result.to_string()

            elif name == "query_kegg":
                result = self.kegg.query(
                    operation=input_data["operation"],
                    database=input_data.get("database"),
                    query=input_data.get("query", ""),
                )
                return result.to_string()

            elif name == "query_string":
                result = self.string.query(
                    proteins=input_data["proteins"],
                    operation=input_data.get("operation", "interactions"),
                    species=input_data.get("species", 9606),
                    score_threshold=input_data.get("score_threshold", 400),
                    limit=input_data.get("limit", 25),
                )
                return result.to_string()

            elif name == "query_pdb":
                result = self.pdb.query(
                    query=input_data["query"],
                    operation=input_data.get("operation", "fetch"),
                    limit=input_data.get("limit", 10),
                )
                return result.to_string()

            elif name == "query_alphafold":
                result = self.alphafold.query(
                    query=input_data["query"],
                    operation=input_data.get("operation", "prediction"),
                )
                return result.to_string()

            elif name == "query_interpro":
                result = self.interpro.query(
                    query=input_data["query"],
                    operation=input_data.get("operation", "protein"),
                    limit=input_data.get("limit", 20),
                )
                return result.to_string()

            elif name == "query_reactome":
                result = self.reactome.query(
                    query=input_data["query"],
                    operation=input_data.get("operation", "pathway"),
                    species=input_data.get("species", "Homo sapiens"),
                    limit=input_data.get("limit", 20),
                )
                return result.to_string()

            elif name == "query_go":
                result = self.go.query(
                    query=input_data["query"],
                    operation=input_data.get("operation", "term"),
                    limit=input_data.get("limit", 25),
                )
                return result.to_string()

            elif name == "query_gnomad":
                result = self.gnomad.query(
                    query=input_data["query"],
                    operation=input_data.get("operation", "variant"),
                    dataset=input_data.get("dataset", "gnomad_r4"),
                )
                return result.to_string()

            elif name == "read_file":
                result = self.files.read_file(
                    path=input_data["path"],
                    head_lines=input_data.get("head_lines"),
                    encoding=input_data.get("encoding", "utf-8"),
                )
                return result.to_string()

            elif name == "write_file":
                result = self.files.write_file(
                    path=input_data["path"],
                    content=input_data["content"],
                    mode=input_data.get("mode", "w"),
                )
                return result.to_string()

            elif name == "list_files":
                result = self.files.list_files(
                    path=input_data["path"],
                    pattern=input_data.get("pattern", "*"),
                    recursive=input_data.get("recursive", False),
                )
                return result.to_string()

            elif name == "web_search":
                result = self.web_search.search(
                    query=input_data.get("query", ""),
                    max_results=input_data.get("max_results", 10),
                )
                return result.to_string()

            # ── Workflow Engine Tools ─────────────────────────────────────
            elif name == "workflow_create":
                result = self.workflows.create_workflow(
                    name=input_data["name"],
                    engine=input_data["engine"],
                    definition=input_data.get("definition"),
                    template=input_data.get("template"),
                    params=input_data.get("params"),
                )
                return result.to_string()

            elif name == "workflow_run":
                result = self.workflows.run_workflow(
                    workflow_path=input_data["workflow_path"],
                    engine=input_data.get("engine"),
                    params=input_data.get("params"),
                    resume=input_data.get("resume", False),
                )
                return result.to_string()

            elif name == "workflow_status":
                result = self.workflows.get_status(
                    workflow_id=input_data["workflow_id"],
                    engine=input_data["engine"],
                )
                return result.to_string()

            elif name == "workflow_outputs":
                result = self.workflows.get_outputs(
                    workflow_id=input_data["workflow_id"],
                    engine=input_data["engine"],
                )
                return result.to_string()

            elif name == "workflow_list":
                engine = input_data.get("engine")
                list_templates = input_data.get("list_templates", True)

                parts = []
                workflows = self.workflows.list_workflows(engine)
                for eng, wf_list in workflows.items():
                    parts.append(f"\n{eng.capitalize()} Workflows ({len(wf_list)}):")
                    for wf in wf_list:
                        parts.append(f"  - {wf['id']}: {wf['path']}")

                if list_templates:
                    templates = self.workflows.list_templates(engine)
                    parts.append("\nAvailable Templates:")
                    for eng, tpl_list in templates.items():
                        parts.append(f"  {eng}: {', '.join(tpl_list)}")

                return "\n".join(parts) if parts else "No workflows found."

            elif name == "workflow_check_engines":
                status = self.workflows.check_engines()
                return format_engine_status(status)

            # ── Memory System Tools ───────────────────────────────────────
            elif name == "memory_search":
                if not self.memory:
                    return "Memory system not available"
                return self.memory.search_memory(
                    query=input_data["query"],
                    max_results=input_data.get("max_results", 5),
                )

            elif name == "memory_save_artifact":
                if not self.memory:
                    return "Memory system not available"
                return self.memory.save_artifact(
                    name=input_data["name"],
                    content=input_data["content"],
                    artifact_type=input_data.get("artifact_type", "analysis_result"),
                    description=input_data["description"],
                    tags=input_data.get("tags"),
                )

            elif name == "memory_list_artifacts":
                if not self.memory:
                    return "Memory system not available"
                return self.memory.list_artifacts(
                    artifact_type=input_data.get("artifact_type"),
                    query=input_data.get("query"),
                )

            elif name == "memory_read_artifact":
                if not self.memory:
                    return "Memory system not available"
                return self.memory.read_artifact(
                    artifact_id=input_data["artifact_id"],
                )

            elif name == "memory_get_entities":
                if not self.memory:
                    return "Memory system not available"
                return self.memory.get_entities(
                    query=input_data.get("query"),
                    entity_type=input_data.get("entity_type"),
                    include_relationships=input_data.get("include_relationships", False),
                )

            else:
                return f"Unknown tool: {name}"

        except Exception as e:
            return f"Tool execution error ({name}): {e}"

    def _extract_text(self, response) -> str:
        """Extract text content from a response."""
        texts = []
        for block in response.content:
            if hasattr(block, "text"):
                texts.append(block.text)
        return "\n".join(texts)

    def _log_tool_input(self, tool_name: str, tool_input: dict):
        """Log tool input in a readable format."""
        if tool_name in ("execute_python", "execute_r"):
            code = tool_input.get("code", "")
            lines = code.strip().split("\n")
            if len(lines) > 10:
                preview = "\n".join(lines[:5]) + f"\n   ... ({len(lines)} lines total)"
            else:
                preview = code.strip()
            self._log(f"   Code:\n   {preview}")
        elif tool_name == "execute_bash":
            self._log(f"   Command: {tool_input.get('command', '')}")
        elif tool_name in ("query_ncbi", "query_ensembl", "query_uniprot", "query_kegg", "query_string", "query_pdb", "query_alphafold", "query_interpro", "query_reactome", "query_go", "query_gnomad"):
            self._log(f"   Query: {json.dumps(tool_input, indent=2)[:300]}")
        elif tool_name.startswith("workflow_"):
            self._log(f"   Workflow: {json.dumps(tool_input, indent=2)[:300]}")
        elif tool_name.startswith("memory_"):
            self._log(f"   Memory: {json.dumps(tool_input, indent=2)[:300]}")
        else:
            self._log(f"   Input: {json.dumps(tool_input)[:300]}")

    def _log(self, message: str):
        """Print a log message if verbose mode is on."""
        if self.config.verbose:
            print(message, file=sys.stderr)

        if self.config.log_file:
            with open(self.config.log_file, "a") as f:
                f.write(f"[{datetime.now().isoformat()}] {message}\n")

    def _auto_save_result(self, query: str, response: str, tools_used: list[str] | None = None):
        """Automatically save query results to a file."""
        if not self.config.auto_save_results:
            return None

        # Create results directory
        results_dir = Path(self.config.workspace_dir) / self.config.results_dir
        results_dir.mkdir(parents=True, exist_ok=True)

        # Generate filename from query (sanitized)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        # Extract key terms from query for filename
        query_words = "".join(c if c.isalnum() or c == " " else "" for c in query.lower())
        query_slug = "_".join(query_words.split()[:5])  # First 5 words
        if not query_slug:
            query_slug = "query"
        filename = f"{timestamp}_{query_slug}.md"
        filepath = results_dir / filename

        # Build the result document
        doc_lines = [
            f"# BioAgent Query Result",
            f"",
            f"**Date:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            f"",
            f"**Query:** {query}",
            f"",
        ]

        if tools_used:
            doc_lines.extend([
                f"**Tools Used:** {', '.join(tools_used)}",
                f"",
            ])

        doc_lines.extend([
            f"---",
            f"",
            f"## Response",
            f"",
            response,
            f"",
            f"---",
            f"*Generated by BioAgent*",
        ])

        content = "\n".join(doc_lines)

        try:
            filepath.write_text(content, encoding="utf-8")
            self._log(f"💾 Results auto-saved to: {filepath}")
            return str(filepath)
        except Exception as e:
            self._log(f"⚠️  Failed to auto-save results: {e}")
            return None

    # ── Utility Methods ──────────────────────────────────────────────

    def get_history(self) -> list[dict]:
        """Return the conversation history."""
        return self.messages.copy()

    def clear_history(self):
        """Clear conversation history."""
        self.messages = []

    def save_session(self, path: str):
        """Save the current session to a JSON file."""
        session = {
            "timestamp": datetime.now().isoformat(),
            "model": self.config.model,
            "messages": self.messages,
        }
        # Include memory session ID if available
        if self.memory:
            session["memory_session_id"] = self.memory.session_id
        with open(path, "w") as f:
            json.dump(session, f, indent=2, default=str)
        self._log(f"💾 Session saved to {path}")

    def load_session(self, path: str):
        """Load a session from a JSON file."""
        with open(path) as f:
            session = json.load(f)
        self.messages = session["messages"]
        # Restore memory session ID if available
        if self.memory and "memory_session_id" in session:
            self.memory.session_id = session["memory_session_id"]
        self._log(f"📂 Session loaded from {path} ({len(self.messages)} messages)")

    def get_memory_stats(self) -> dict | None:
        """Get memory system statistics."""
        if not self.memory:
            return None
        return self.memory.get_stats()
