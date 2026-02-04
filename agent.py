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
from pdb import PDBClient
from file_manager import FileManager


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
        self.files = FileManager(workspace_dir=self.config.workspace_dir)

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

        # Agentic loop
        for round_num in range(1, self.config.max_tool_rounds + 1):
            self._log(f"\n--- Round {round_num} ---")

            # Call Claude
            response = self._call_claude(model)

            # Check for stop conditions
            if response.stop_reason == "end_turn":
                # Extract final text
                final_text = self._extract_text(response)
                self.messages.append({"role": "assistant", "content": response.content})
                self._log(f"\n✅ Final response ({len(final_text)} chars)")
                return final_text

            elif response.stop_reason == "tool_use":
                # Process tool calls
                tool_results = self._process_tool_calls(response)

                # Add assistant message + tool results to history
                self.messages.append({"role": "assistant", "content": response.content})
                self.messages.append({"role": "user", "content": tool_results})

            else:
                self._log(f"⚠️  Unexpected stop reason: {response.stop_reason}")
                final_text = self._extract_text(response)
                self.messages.append({"role": "assistant", "content": response.content})
                return final_text

        # Max rounds exceeded
        self._log(f"⚠️  Max tool rounds ({self.config.max_tool_rounds}) exceeded")
        return (
            "I've reached the maximum number of tool-use iterations. "
            "Here's what I've done so far — you may want to continue from here."
        )

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

    def _call_claude(self, model: str) -> anthropic.types.Message:
        """Make an API call to Claude with tools."""
        kwargs = {
            "model": model,
            "max_tokens": self.config.max_tokens,
            "system": SYSTEM_PROMPT,
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
                # Placeholder — can integrate with a search API
                return (
                    "Web search is not yet configured. "
                    "To enable it, integrate a search API (e.g., Tavily, SerpAPI) "
                    "in the _execute_tool method."
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
        elif tool_name in ("query_ncbi", "query_ensembl", "query_uniprot", "query_kegg", "query_string", "query_pdb"):
            self._log(f"   Query: {json.dumps(tool_input, indent=2)[:300]}")
        else:
            self._log(f"   Input: {json.dumps(tool_input)[:300]}")

    def _log(self, message: str):
        """Print a log message if verbose mode is on."""
        if self.config.verbose:
            print(message, file=sys.stderr)

        if self.config.log_file:
            with open(self.config.log_file, "a") as f:
                f.write(f"[{datetime.now().isoformat()}] {message}\n")

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
        with open(path, "w") as f:
            json.dump(session, f, indent=2, default=str)
        self._log(f"💾 Session saved to {path}")

    def load_session(self, path: str):
        """Load a session from a JSON file."""
        with open(path) as f:
            session = json.load(f)
        self.messages = session["messages"]
        self._log(f"📂 Session loaded from {path} ({len(self.messages)} messages)")
