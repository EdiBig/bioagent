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
from visualization import InteractivePlotter, PublicationFigure
from reporting import create_analysis_notebook, create_rmarkdown_report, create_dashboard
from cloud import CloudExecutor, CloudConfig, ResourceSpec, JobStatus
from ml import (
    predict_variant_pathogenicity,
    predict_structure_alphafold,
    predict_structure_esmfold,
    predict_drug_response,
    annotate_cell_types,
    discover_biomarkers,
)
from data_input import IngestHandler, get_ingest_tools


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

        # Initialize file ingestion system
        self.ingest_handler = IngestHandler(workspace_dir=self.config.workspace_dir)
        self._log("📂 File ingestion system initialized (34 formats supported)")

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

        # Initialize multi-agent coordinator if enabled
        self.coordinator = None
        if self.config.enable_multi_agent:
            self._init_coordinator()

    def _init_coordinator(self):
        """Initialize the multi-agent coordinator."""
        try:
            from agents import CoordinatorAgent

            # Build tool handlers dict for specialist agents
            tool_handlers = self._build_tool_handlers()

            self.coordinator = CoordinatorAgent(
                client=self.client,
                tool_handlers=tool_handlers,
                memory=self.memory,
                coordinator_model=self.config.coordinator_model,
                specialist_model=self.config.specialist_model,
                qc_model=self.config.qc_model,
                max_specialists=self.config.multi_agent_max_specialists,
                enable_parallel=self.config.multi_agent_parallel,
                verbose=self.config.verbose,
            )
            self._log("🤖 Multi-agent coordinator initialized")

        except Exception as e:
            self._log(f"⚠️  Multi-agent initialization failed: {e}")
            self.coordinator = None

    def _build_tool_handlers(self) -> dict[str, callable]:
        """Build a dictionary mapping tool names to handler functions."""
        return {
            "execute_python": lambda args: self.executor.execute_python(
                code=args["code"],
                timeout=args.get("timeout", 300),
            ).to_string(),

            "execute_r": lambda args: self.executor.execute_r(
                code=args["code"],
                timeout=args.get("timeout", 300),
            ).to_string(),

            "execute_bash": lambda args: self.executor.execute_bash(
                command=args["command"],
                timeout=args.get("timeout", 600),
                working_dir=args.get("working_dir"),
            ).to_string(),

            "query_ncbi": lambda args: self.ncbi.query(
                database=args["database"],
                operation=args["operation"],
                query=args["query"],
                max_results=args.get("max_results", 10),
                return_type=args.get("return_type", "json"),
            ).to_string(),

            "query_ensembl": lambda args: self.ensembl.query(
                endpoint=args["endpoint"],
                params=args.get("params", {}),
                species=args.get("species", "homo_sapiens"),
            ).to_string(),

            "query_uniprot": lambda args: self.uniprot.query(
                query=args["query"],
                operation=args.get("operation", "search"),
                format=args.get("format", "json"),
                limit=args.get("limit", 10),
            ).to_string(),

            "query_kegg": lambda args: self.kegg.query(
                operation=args["operation"],
                database=args.get("database"),
                query=args.get("query", ""),
            ).to_string(),

            "query_string": lambda args: self.string.query(
                proteins=args["proteins"],
                operation=args.get("operation", "interactions"),
                species=args.get("species", 9606),
                score_threshold=args.get("score_threshold", 400),
                limit=args.get("limit", 25),
            ).to_string(),

            "query_pdb": lambda args: self.pdb.query(
                query=args["query"],
                operation=args.get("operation", "fetch"),
                limit=args.get("limit", 10),
            ).to_string(),

            "query_alphafold": lambda args: self.alphafold.query(
                query=args["query"],
                operation=args.get("operation", "prediction"),
            ).to_string(),

            "query_interpro": lambda args: self.interpro.query(
                query=args["query"],
                operation=args.get("operation", "protein"),
                limit=args.get("limit", 20),
            ).to_string(),

            "query_reactome": lambda args: self.reactome.query(
                query=args["query"],
                operation=args.get("operation", "pathway"),
                species=args.get("species", "Homo sapiens"),
                limit=args.get("limit", 20),
            ).to_string(),

            "query_go": lambda args: self.go.query(
                query=args["query"],
                operation=args.get("operation", "term"),
                limit=args.get("limit", 25),
            ).to_string(),

            "query_gnomad": lambda args: self.gnomad.query(
                query=args["query"],
                operation=args.get("operation", "variant"),
                dataset=args.get("dataset", "gnomad_r4"),
            ).to_string(),

            "read_file": lambda args: self.files.read_file(
                path=args["path"],
                head_lines=args.get("head_lines"),
                encoding=args.get("encoding", "utf-8"),
            ).to_string(),

            "write_file": lambda args: self.files.write_file(
                path=args["path"],
                content=args["content"],
                mode=args.get("mode", "w"),
            ).to_string(),

            "list_files": lambda args: self.files.list_files(
                path=args["path"],
                pattern=args.get("pattern", "*"),
                recursive=args.get("recursive", False),
            ).to_string(),

            "web_search": lambda args: self.web_search.search(
                query=args.get("query", ""),
                max_results=args.get("max_results", 10),
            ).to_string(),

            "workflow_create": lambda args: self.workflows.create_workflow(
                name=args["name"],
                engine=args["engine"],
                definition=args.get("definition"),
                template=args.get("template"),
                params=args.get("params"),
            ).to_string(),

            "workflow_run": lambda args: self.workflows.run_workflow(
                workflow_path=args["workflow_path"],
                engine=args.get("engine"),
                params=args.get("params"),
                resume=args.get("resume", False),
            ).to_string(),

            "workflow_status": lambda args: self.workflows.get_status(
                workflow_id=args["workflow_id"],
                engine=args["engine"],
            ).to_string(),

            "workflow_outputs": lambda args: self.workflows.get_outputs(
                workflow_id=args["workflow_id"],
                engine=args["engine"],
            ).to_string(),

            "workflow_list": lambda args: self._handle_workflow_list(args),

            "workflow_check_engines": lambda args: format_engine_status(
                self.workflows.check_engines()
            ),

            "memory_search": lambda args: self.memory.search_memory(
                query=args["query"],
                max_results=args.get("max_results", 5),
            ) if self.memory else "Memory system not available",

            "memory_save_artifact": lambda args: self.memory.save_artifact(
                name=args["name"],
                content=args["content"],
                artifact_type=args.get("artifact_type", "analysis_result"),
                description=args["description"],
                tags=args.get("tags"),
            ) if self.memory else "Memory system not available",

            "memory_list_artifacts": lambda args: self.memory.list_artifacts(
                artifact_type=args.get("artifact_type"),
                query=args.get("query"),
            ) if self.memory else "Memory system not available",

            "memory_read_artifact": lambda args: self.memory.read_artifact(
                artifact_id=args["artifact_id"],
            ) if self.memory else "Memory system not available",

            "memory_get_entities": lambda args: self.memory.get_entities(
                query=args.get("query"),
                entity_type=args.get("entity_type"),
                include_relationships=args.get("include_relationships", False),
            ) if self.memory else "Memory system not available",

            # Data Ingestion tools
            "ingest_file": lambda args: self.ingest_handler.handle("ingest_file", args),
            "ingest_batch": lambda args: self.ingest_handler.handle("ingest_batch", args),
            "ingest_directory": lambda args: self.ingest_handler.handle("ingest_directory", args),
            "list_ingested_files": lambda args: self.ingest_handler.handle("list_ingested_files", args),
            "get_file_profile": lambda args: self.ingest_handler.handle("get_file_profile", args),
            "validate_dataset": lambda args: self.ingest_handler.handle("validate_dataset", args),
        }

    def _handle_workflow_list(self, args: dict) -> str:
        """Handle workflow_list tool call."""
        engine = args.get("engine")
        list_templates = args.get("list_templates", True)

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

    def run(self, user_message: str, use_complex_model: bool = False) -> str:
        """
        Process a user message through the agentic loop.

        Args:
            user_message: The user's input/question/task
            use_complex_model: Use the more powerful (and expensive) model

        Returns:
            The agent's final text response
        """
        # Route through multi-agent coordinator if enabled
        if self.coordinator and self.config.enable_multi_agent:
            return self._run_multi_agent(user_message)

        # Otherwise use single-agent mode
        return self._run_single_agent(user_message, use_complex_model)

    def _run_multi_agent(self, user_message: str) -> str:
        """Process user message through the multi-agent coordinator."""
        self._log(f"\n{'='*60}")
        self._log(f"🤖 BioAgent [Multi-Agent Mode]")
        self._log(f"{'='*60}")
        self._log(f"📝 User: {user_message[:200]}{'...' if len(user_message) > 200 else ''}")

        try:
            # Add to history for context
            self.messages.append({"role": "user", "content": user_message})

            # Run through coordinator
            result = self.coordinator.run(
                query=user_message,
                conversation_history=self.messages,
            )

            # Add response to history
            self.messages.append({"role": "assistant", "content": result.response})

            # Update memory with completed analysis
            if self.memory:
                try:
                    tools_used = []
                    for output in result.specialist_outputs:
                        tools_used.extend(output.tools_used)
                    self.memory.on_analysis_complete(user_message, result.response, tools_used)
                except Exception as e:
                    self._log(f"⚠️  Memory analysis save error: {e}")

            # Auto-save results
            tools_used = []
            for output in result.specialist_outputs:
                tools_used.extend(output.tools_used)
            self._auto_save_result(user_message, result.response, tools_used if tools_used else None)

            self._log(f"\n✅ Multi-agent response complete ({result.execution_time:.1f}s)")

            return result.response

        except Exception as e:
            self._log(f"⚠️  Multi-agent error: {e}, falling back to single-agent")
            return self._run_single_agent(user_message, use_complex_model=False)

    def _run_single_agent(self, user_message: str, use_complex_model: bool = False) -> str:
        """Process user message through single-agent mode."""
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

            # ── Visualization & Reporting Tools ─────────────────────────────
            elif name == "create_plot":
                return self._create_plot(input_data)

            elif name == "generate_report":
                return self._generate_report(input_data)

            elif name == "create_dashboard":
                return self._create_dashboard(input_data)

            # ── Cloud & HPC Tools ───────────────────────────────────────────
            elif name == "cloud_submit_job":
                return self._cloud_submit_job(input_data)

            elif name == "cloud_job_status":
                return self._cloud_job_status(input_data)

            elif name == "cloud_job_logs":
                return self._cloud_job_logs(input_data)

            elif name == "cloud_cancel_job":
                return self._cloud_cancel_job(input_data)

            elif name == "cloud_list_jobs":
                return self._cloud_list_jobs(input_data)

            elif name == "cloud_estimate_cost":
                return self._cloud_estimate_cost(input_data)

            # ── ML/AI Tools ─────────────────────────────────────────────────
            elif name == "predict_pathogenicity":
                result = predict_variant_pathogenicity(
                    variants=input_data["variants"],
                    genome_build=input_data.get("genome_build", "GRCh38"),
                    include_scores=input_data.get("include_scores", ["cadd", "revel"]),
                )
                return json.dumps(result, indent=2)

            elif name == "predict_structure":
                method = input_data.get("method", "alphafold")
                if method == "alphafold":
                    result = predict_structure_alphafold(
                        sequence=input_data.get("sequence"),
                        uniprot_id=input_data.get("uniprot_id"),
                    )
                else:  # esmfold
                    result = predict_structure_esmfold(
                        sequence=input_data["sequence"],
                    )
                return json.dumps(result, indent=2)

            elif name == "predict_drug_response":
                result = predict_drug_response(
                    drug=input_data["drug"],
                    cell_line=input_data.get("cell_line"),
                    tissue=input_data.get("tissue"),
                    mutations=input_data.get("mutations"),
                )
                return json.dumps(result, indent=2)

            elif name == "annotate_cell_types":
                result = annotate_cell_types(
                    expression_data=input_data["expression_data"],
                    method=input_data.get("method", "celltypist"),
                    model=input_data.get("model", "Immune_All_Low.pkl"),
                    tissue=input_data.get("tissue"),
                )
                return json.dumps(result, indent=2)

            elif name == "discover_biomarkers":
                result = discover_biomarkers(
                    X=input_data["X"],
                    y=input_data["y"],
                    feature_names=input_data.get("feature_names"),
                    n_features=input_data.get("n_features", 20),
                    methods=input_data.get("methods"),
                )
                return json.dumps(result, indent=2)

            # ── Data Ingestion Tools ───────────────────────────────────────
            elif name in self.ingest_handler.handled_tools:
                return self.ingest_handler.handle(name, input_data)

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

    # ── Visualization & Reporting Methods ────────────────────────────

    def _create_plot(self, input_data: dict) -> str:
        """Create publication-quality or interactive plots."""
        import pandas as pd

        plot_type = input_data["plot_type"]
        data_source = input_data["data_source"]
        output_path = input_data.get("output_path")
        output_format = input_data.get("output_format", "png")
        interactive = input_data.get("interactive", False)
        theme = input_data.get("theme")
        title = input_data.get("title", "")
        options = input_data.get("options", {})

        # Load data
        data_path = Path(self.config.workspace_dir) / data_source
        if not data_path.exists():
            return f"Data file not found: {data_source}"

        try:
            if data_path.suffix == ".csv":
                df = pd.read_csv(data_path)
            elif data_path.suffix in (".tsv", ".txt"):
                df = pd.read_csv(data_path, sep="\t")
            elif data_path.suffix == ".parquet":
                df = pd.read_parquet(data_path)
            else:
                df = pd.read_csv(data_path)
        except Exception as e:
            return f"Failed to load data: {e}"

        # Generate output path if not provided
        if not output_path:
            output_dir = Path(self.config.workspace_dir) / "figures"
            output_dir.mkdir(parents=True, exist_ok=True)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            ext = "html" if interactive else output_format
            output_path = str(output_dir / f"{plot_type}_{timestamp}.{ext}")
        else:
            output_path = str(Path(self.config.workspace_dir) / output_path)

        try:
            if interactive:
                # Use InteractivePlotter
                plotter = InteractivePlotter(backend="plotly")
                fig = None

                if plot_type == "volcano":
                    fig = plotter.volcano_plot(
                        df,
                        fc_col=options.get("fc_col", "log2FoldChange"),
                        pval_col=options.get("pval_col", "pvalue"),
                        gene_col=options.get("gene_col", "gene"),
                        fc_threshold=options.get("fc_threshold", 1.0),
                        pval_threshold=options.get("pval_threshold", 0.05),
                        title=title or "Volcano Plot",
                    )
                elif plot_type == "heatmap":
                    fig = plotter.heatmap(
                        df,
                        title=title or "Heatmap",
                    )
                elif plot_type == "pca":
                    fig = plotter.pca_plot(
                        df,
                        color_col=options.get("color_col"),
                        title=title or "PCA Plot",
                    )
                elif plot_type == "scatter":
                    fig = plotter.scatter_plot(
                        df,
                        x=options.get("x_col", df.columns[0]),
                        y=options.get("y_col", df.columns[1]),
                        color=options.get("color_col"),
                        title=title or "Scatter Plot",
                    )
                elif plot_type == "bar":
                    fig = plotter.bar_plot(
                        df,
                        x=options.get("x_col", df.columns[0]),
                        y=options.get("y_col", df.columns[1]),
                        title=title or "Bar Plot",
                    )

                if fig:
                    fig.write_html(output_path)
                    return f"Interactive {plot_type} plot saved to: {output_path}"
                else:
                    return f"Unsupported interactive plot type: {plot_type}"

            else:
                # Use PublicationFigure
                pub_fig = PublicationFigure(style=theme or "nature")
                fig, axes = pub_fig.create_figure(n_panels=1)
                ax = axes[0] if isinstance(axes, list) else axes

                if plot_type == "volcano":
                    pub_fig.volcano_plot(
                        ax,
                        df,
                        x_col=options.get("fc_col", "log2FoldChange"),
                        y_col=options.get("pval_col", "pvalue"),
                        label_col=options.get("gene_col", "gene"),
                        fc_threshold=options.get("fc_threshold", 1.0),
                        pval_threshold=options.get("pval_threshold", 0.05),
                        title=title or "Volcano Plot",
                    )
                elif plot_type == "heatmap":
                    # For heatmap, need numeric matrix
                    numeric_cols = df.select_dtypes(include="number").columns
                    matrix = df[numeric_cols]
                    pub_fig.heatmap(
                        ax,
                        matrix,
                        title=title or "Heatmap",
                    )
                elif plot_type == "pca":
                    pub_fig.pca_plot(
                        ax,
                        df,
                        color_col=options.get("color_col"),
                        title=title or "PCA Plot",
                    )
                elif plot_type == "ma":
                    pub_fig.ma_plot(
                        ax,
                        df,
                        x_col=options.get("mean_col", "baseMean"),
                        y_col=options.get("fc_col", "log2FoldChange"),
                        pval_col=options.get("pval_col", "padj"),
                        title=title or "MA Plot",
                    )
                elif plot_type == "enrichment":
                    pub_fig.enrichment_barplot(
                        ax,
                        df,
                        term_col=options.get("term_col", "Term"),
                        pval_col=options.get("pval_col", "P.value"),
                        n_terms=options.get("n_terms", 15),
                        title=title or "Enrichment Results",
                    )

                if fig:
                    from visualization.utils import save_figure
                    save_figure(fig, output_path, dpi=options.get("dpi", 300))
                    return f"Publication-quality {plot_type} plot saved to: {output_path}"
                else:
                    return f"Unsupported plot type: {plot_type}"

        except Exception as e:
            return f"Plot creation failed: {e}"

    def _generate_report(self, input_data: dict) -> str:
        """Generate automated analysis reports."""
        report_type = input_data["report_type"]
        title = input_data["title"]
        analysis_type = input_data.get("analysis_type", "custom")
        data_path = input_data.get("data_path")
        output_path = input_data.get("output_path")
        options = input_data.get("options", {})

        # Generate output path if not provided
        if not output_path:
            output_dir = Path(self.config.workspace_dir) / "reports"
            output_dir.mkdir(parents=True, exist_ok=True)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            slug = title.lower().replace(" ", "_")[:30]
            ext = ".ipynb" if report_type == "notebook" else ".Rmd"
            output_path = str(output_dir / f"{slug}_{timestamp}{ext}")
        else:
            output_path = str(Path(self.config.workspace_dir) / output_path)

        # Resolve data path
        if data_path:
            data_path = str(Path(self.config.workspace_dir) / data_path)

        try:
            if report_type == "notebook":
                saved_path = create_analysis_notebook(
                    title=title,
                    analysis_type=analysis_type,
                    data_path=data_path,
                    output_path=output_path,
                    **options,
                )
                return f"Jupyter notebook report saved to: {saved_path}"

            elif report_type == "rmarkdown":
                saved_path = create_rmarkdown_report(
                    title=title,
                    report_type=analysis_type,
                    data_path=data_path,
                    output_path=output_path,
                    **options,
                )
                return f"R Markdown report saved to: {saved_path}"

            else:
                return f"Unknown report type: {report_type}. Use 'notebook' or 'rmarkdown'."

        except Exception as e:
            return f"Report generation failed: {e}"

    def _create_dashboard(self, input_data: dict) -> str:
        """Generate interactive dashboards."""
        dashboard_type = input_data["dashboard_type"]  # deseq2, expression, enrichment
        data_path = input_data["data_path"]
        output_path = input_data["output_path"]
        framework = input_data.get("framework", "streamlit")
        metadata_path = input_data.get("metadata_path")

        # Resolve paths relative to workspace
        data_path = str(Path(self.config.workspace_dir) / data_path)
        output_path = str(Path(self.config.workspace_dir) / output_path)

        # Ensure output directory exists
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)

        try:
            saved_path = create_dashboard(
                dashboard_type=dashboard_type,
                data_path=data_path,
                framework=framework,
                output_path=output_path,
                metadata_path=metadata_path,
            )
            return f"{framework.capitalize()} dashboard saved to: {saved_path}. Run with: {framework} run {saved_path}"

        except Exception as e:
            return f"Dashboard creation failed: {e}"

    # ── Cloud & HPC Methods ──────────────────────────────────────────

    def _get_cloud_executor(self) -> CloudExecutor:
        """Get or create cloud executor instance."""
        if not hasattr(self, "_cloud_executor"):
            cloud_config = CloudConfig.from_env()
            self._cloud_executor = CloudExecutor(cloud_config)
        return self._cloud_executor

    def _cloud_submit_job(self, input_data: dict) -> str:
        """Submit a job to cloud/HPC backend."""
        command = input_data["command"]
        backend = input_data.get("backend", "auto")

        # Build resource specification
        resources = ResourceSpec(
            vcpus=input_data.get("vcpus", 4),
            memory_gb=input_data.get("memory_gb", 16),
            gpu_count=input_data.get("gpu_count", 0),
            timeout_hours=input_data.get("timeout_hours", 24),
            use_spot=input_data.get("use_spot", True),
        )

        # Optional parameters
        container = input_data.get("container")
        input_files = input_data.get("input_files", [])
        output_path = input_data.get("output_path")

        try:
            executor = self._get_cloud_executor()

            # Check available backends
            available = executor.get_available_backends()
            if not available:
                return (
                    "No cloud backends are configured. Set environment variables for:\n"
                    "- AWS: AWS_S3_BUCKET, AWS_BATCH_QUEUE\n"
                    "- GCP: GCP_PROJECT, GCP_GCS_BUCKET\n"
                    "- Azure: AZURE_SUBSCRIPTION_ID, AZURE_BATCH_ACCOUNT\n"
                    "- SLURM: SLURM_HOST, SLURM_USER"
                )

            # Submit job
            if backend == "auto":
                job_id = executor.submit_job(
                    command=command,
                    resources=resources,
                    container=container,
                    input_files=input_files,
                    output_path=output_path,
                )
            else:
                job_id = executor.submit_job(
                    command=command,
                    backend=backend,
                    resources=resources,
                    container=container,
                    input_files=input_files,
                    output_path=output_path,
                )

            # Get cost estimate
            cost = executor._select_best_executor(resources).estimate_cost(resources, resources.timeout_hours)

            return (
                f"Job submitted successfully!\n"
                f"  Job ID: {job_id}\n"
                f"  Backend: {backend}\n"
                f"  Resources: {resources.vcpus} vCPUs, {resources.memory_gb}GB RAM"
                f"{f', {resources.gpu_count} GPUs' if resources.gpu_count else ''}\n"
                f"  Estimated cost: ${cost.get('spot', 0):.2f} (spot) / ${cost.get('on_demand', 0):.2f} (on-demand)\n"
                f"Use cloud_job_status to check progress."
            )

        except Exception as e:
            return f"Job submission failed: {e}"

    def _cloud_job_status(self, input_data: dict) -> str:
        """Get status of a cloud job."""
        job_id = input_data["job_id"]
        backend = input_data.get("backend")

        try:
            executor = self._get_cloud_executor()
            info = executor.get_job_status(job_id, backend)

            status_emoji = {
                JobStatus.PENDING: "⏳",
                JobStatus.SUBMITTED: "📤",
                JobStatus.RUNNING: "🔄",
                JobStatus.SUCCEEDED: "✅",
                JobStatus.FAILED: "❌",
                JobStatus.CANCELLED: "🚫",
                JobStatus.UNKNOWN: "❓",
            }

            result = [
                f"Job Status: {status_emoji.get(info.status, '')} {info.status.value.upper()}",
                f"  Job ID: {info.job_id}",
                f"  Backend: {info.backend}",
                f"  Submitted: {info.submit_time}",
            ]

            if info.start_time:
                result.append(f"  Started: {info.start_time}")
            if info.end_time:
                result.append(f"  Ended: {info.end_time}")
            if info.exit_code is not None:
                result.append(f"  Exit Code: {info.exit_code}")
            if info.error_message:
                result.append(f"  Error: {info.error_message}")
            if info.log_url:
                result.append(f"  Logs: {info.log_url}")

            return "\n".join(result)

        except Exception as e:
            return f"Failed to get job status: {e}"

    def _cloud_job_logs(self, input_data: dict) -> str:
        """Get logs for a cloud job."""
        job_id = input_data["job_id"]
        tail = input_data.get("tail", 100)
        backend = input_data.get("backend")

        try:
            executor = self._get_cloud_executor()
            logs = executor.get_job_logs(job_id, backend, tail)
            return f"=== Logs for job {job_id} (last {tail} lines) ===\n\n{logs}"

        except Exception as e:
            return f"Failed to get logs: {e}"

    def _cloud_cancel_job(self, input_data: dict) -> str:
        """Cancel a cloud job."""
        job_id = input_data["job_id"]
        backend = input_data.get("backend")

        try:
            executor = self._get_cloud_executor()
            success = executor.cancel_job(job_id, backend)

            if success:
                return f"Job {job_id} cancelled successfully."
            else:
                return f"Failed to cancel job {job_id}. It may have already completed."

        except Exception as e:
            return f"Failed to cancel job: {e}"

    def _cloud_list_jobs(self, input_data: dict) -> str:
        """List cloud jobs."""
        status_filter = input_data.get("status")
        backend = input_data.get("backend")
        limit = input_data.get("limit", 50)

        try:
            executor = self._get_cloud_executor()

            # Map status string to enum
            status_enum = None
            if status_filter:
                status_map = {
                    "pending": JobStatus.PENDING,
                    "running": JobStatus.RUNNING,
                    "succeeded": JobStatus.SUCCEEDED,
                    "failed": JobStatus.FAILED,
                }
                status_enum = status_map.get(status_filter.lower())

            if backend:
                # List from specific backend
                exec_backend = executor.get_executor(backend)
                jobs = exec_backend.list_jobs(status_enum, limit)
                jobs_by_backend = {backend: jobs}
            else:
                # List from all backends
                jobs_by_backend = executor.list_all_jobs(status_enum, limit)

            # Format output
            lines = ["=== Cloud/HPC Jobs ==="]

            total = 0
            for backend_name, jobs in jobs_by_backend.items():
                if jobs:
                    lines.append(f"\n{backend_name.upper()}:")
                    for job in jobs[:limit]:
                        status_icon = "✅" if job.status == JobStatus.SUCCEEDED else "❌" if job.status == JobStatus.FAILED else "🔄" if job.status == JobStatus.RUNNING else "⏳"
                        lines.append(f"  {status_icon} {job.job_id}: {job.status.value}")
                        total += 1

            if total == 0:
                lines.append("\nNo jobs found.")
            else:
                lines.append(f"\nTotal: {total} jobs")

            return "\n".join(lines)

        except Exception as e:
            return f"Failed to list jobs: {e}"

    def _cloud_estimate_cost(self, input_data: dict) -> str:
        """Estimate cost for cloud job."""
        vcpus = input_data["vcpus"]
        memory_gb = input_data["memory_gb"]
        gpu_count = input_data.get("gpu_count", 0)
        duration_hours = input_data["duration_hours"]

        resources = ResourceSpec(
            vcpus=vcpus,
            memory_gb=memory_gb,
            gpu_count=gpu_count,
        )

        try:
            executor = self._get_cloud_executor()

            # Get cost estimates
            if executor._executors:
                backend = next(iter(executor._executors.values()))
                estimates = backend.estimate_cost(resources, duration_hours)
            else:
                # Use base pricing if no backends configured
                estimates = {
                    "on_demand": round((vcpus * 0.05 + memory_gb * 0.005 + gpu_count * 1.0) * duration_hours, 2),
                    "spot": round((vcpus * 0.015 + memory_gb * 0.002 + gpu_count * 0.3) * duration_hours, 2),
                }

            return (
                f"=== Cost Estimate ===\n\n"
                f"Resources: {vcpus} vCPUs, {memory_gb}GB RAM"
                f"{f', {gpu_count} GPUs' if gpu_count else ''}\n"
                f"Duration: {duration_hours} hours\n\n"
                f"Estimated Cost:\n"
                f"  On-Demand: ${estimates['on_demand']:.2f}\n"
                f"  Spot/Preemptible: ${estimates['spot']:.2f}\n"
                f"  Savings with Spot: {(1 - estimates['spot']/estimates['on_demand'])*100:.0f}%\n\n"
                f"Note: Actual costs vary by cloud provider and region."
            )

        except Exception as e:
            return f"Failed to estimate cost: {e}"

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
