"""
BioAgent configuration.

Loads settings from environment variables and .env file.
"""

import os
import sys
from dataclasses import dataclass, field
from pathlib import Path

# Auto-load .env file if present
try:
    from dotenv import load_dotenv
    # Look for .env in the bioagent directory
    _env_path = Path(__file__).parent / ".env"
    if _env_path.exists():
        load_dotenv(_env_path)
except ImportError:
    pass  # python-dotenv not installed, rely on environment variables


def _default_workspace() -> str:
    """Return platform-appropriate default workspace directory."""
    if sys.platform == "win32":
        # Windows: use user's home directory
        return str(Path.home() / "bioagent_workspace")
    else:
        # Linux/macOS: use /workspace (common in containers)
        return "/workspace"


@dataclass
class Config:
    """Agent configuration."""

    # ── Anthropic API ────────────────────────────────────────────────
    anthropic_api_key: str = ""
    model: str = "claude-sonnet-4-20250514"  # Sonnet for routine work
    model_complex: str = "claude-opus-4-0-20250115"  # Opus for complex interpretation
    max_tokens: int = 8192
    temperature: float = 0.0  # Deterministic for reproducibility

    # ── NCBI ─────────────────────────────────────────────────────────
    ncbi_api_key: str = ""  # Optional but recommended
    ncbi_email: str = ""  # Required by NCBI

    # ── Execution ────────────────────────────────────────────────────
    workspace_dir: str = ""  # Set dynamically based on platform
    use_docker: bool = False
    docker_image: str = "bioagent-tools:latest"
    max_execution_timeout: int = 600

    # ── Agent Behaviour ──────────────────────────────────────────────
    max_tool_rounds: int = 50  # Max agentic loop iterations (increased for complex analyses)
    verbose: bool = True  # Print tool calls and results
    log_file: str | None = None  # Optional file to log interactions
    enable_extended_thinking: bool = False  # Use extended thinking for complex queries
    auto_save_results: bool = True  # Automatically save query results to files
    results_dir: str = "results"  # Subdirectory for auto-saved results
    fast_mode: bool = False  # Fast mode: disables multi-agent, memory, uses fewer rounds

    # ── Memory System ─────────────────────────────────────────────────
    enable_memory: bool = True  # Master toggle for memory subsystem
    enable_rag: bool = True  # Enable RAG vector store for semantic search
    enable_summaries: bool = True  # Enable automatic session summarization
    enable_knowledge_graph: bool = True  # Enable biological entity tracking
    enable_artifacts: bool = True  # Enable artifact storage
    summary_after_rounds: int = 5  # Summarize conversation every N rounds

    # ── Multi-Agent Mode ───────────────────────────────────────────────
    enable_multi_agent: bool = False  # Master toggle for multi-agent mode
    multi_agent_parallel: bool = True  # Allow parallel specialist execution
    multi_agent_max_specialists: int = 3  # Max specialists per query
    coordinator_model: str = "claude-sonnet-4-20250514"  # Model for coordinator
    specialist_model: str = "claude-sonnet-4-20250514"  # Model for specialists
    qc_model: str = "claude-haiku-3-5-20241022"  # Lighter model for QC reviewer

    # ── Workspace & Analysis Tracking ────────────────────────────────────
    enable_analysis_tracking: bool = True  # Master toggle for analysis tracking
    auto_create_analysis: bool = False  # Auto-start analysis on query
    default_project: str = ""  # Default project for new analyses
    analysis_id_prefix: str = "BIO"  # Prefix for analysis IDs (BIO-YYYYMMDD-NNN)

    @classmethod
    def from_env(cls) -> "Config":
        """Load configuration from environment variables."""
        return cls(
            anthropic_api_key=os.getenv("ANTHROPIC_API_KEY", ""),
            model=os.getenv("BIOAGENT_MODEL", "claude-sonnet-4-20250514"),
            model_complex=os.getenv("BIOAGENT_MODEL_COMPLEX", "claude-opus-4-0-20250115"),
            max_tokens=int(os.getenv("BIOAGENT_MAX_TOKENS", "8192")),
            temperature=float(os.getenv("BIOAGENT_TEMPERATURE", "0.0")),
            ncbi_api_key=os.getenv("NCBI_API_KEY", ""),
            ncbi_email=os.getenv("NCBI_EMAIL", ""),
            workspace_dir=os.getenv("BIOAGENT_WORKSPACE", _default_workspace()),
            use_docker=os.getenv("BIOAGENT_USE_DOCKER", "false").lower() == "true",
            docker_image=os.getenv("BIOAGENT_DOCKER_IMAGE", "bioagent-tools:latest"),
            max_execution_timeout=int(os.getenv("BIOAGENT_TIMEOUT", "600")),
            max_tool_rounds=int(os.getenv("BIOAGENT_MAX_ROUNDS", "50")),
            verbose=os.getenv("BIOAGENT_VERBOSE", "true").lower() == "true",
            log_file=os.getenv("BIOAGENT_LOG_FILE", None),
            enable_extended_thinking=os.getenv("BIOAGENT_EXTENDED_THINKING", "false").lower() == "true",
            auto_save_results=os.getenv("BIOAGENT_AUTO_SAVE", "true").lower() == "true",
            results_dir=os.getenv("BIOAGENT_RESULTS_DIR", "results"),
            fast_mode=os.getenv("BIOAGENT_FAST_MODE", "false").lower() == "true",
            # Memory system
            enable_memory=os.getenv("BIOAGENT_ENABLE_MEMORY", "true").lower() == "true",
            enable_rag=os.getenv("BIOAGENT_ENABLE_RAG", "true").lower() == "true",
            enable_summaries=os.getenv("BIOAGENT_ENABLE_SUMMARIES", "true").lower() == "true",
            enable_knowledge_graph=os.getenv("BIOAGENT_ENABLE_KG", "true").lower() == "true",
            enable_artifacts=os.getenv("BIOAGENT_ENABLE_ARTIFACTS", "true").lower() == "true",
            summary_after_rounds=int(os.getenv("BIOAGENT_SUMMARY_ROUNDS", "5")),
            # Multi-agent mode
            enable_multi_agent=os.getenv("BIOAGENT_MULTI_AGENT", "false").lower() == "true",
            multi_agent_parallel=os.getenv("BIOAGENT_MULTI_AGENT_PARALLEL", "true").lower() == "true",
            multi_agent_max_specialists=int(os.getenv("BIOAGENT_MAX_SPECIALISTS", "3")),
            coordinator_model=os.getenv("BIOAGENT_COORDINATOR_MODEL", "claude-sonnet-4-20250514"),
            specialist_model=os.getenv("BIOAGENT_SPECIALIST_MODEL", "claude-sonnet-4-20250514"),
            qc_model=os.getenv("BIOAGENT_QC_MODEL", "claude-haiku-3-5-20241022"),
            # Workspace & Analysis Tracking
            enable_analysis_tracking=os.getenv("BIOAGENT_ENABLE_TRACKING", "true").lower() == "true",
            auto_create_analysis=os.getenv("BIOAGENT_AUTO_CREATE_ANALYSIS", "false").lower() == "true",
            default_project=os.getenv("BIOAGENT_DEFAULT_PROJECT", ""),
            analysis_id_prefix=os.getenv("BIOAGENT_ANALYSIS_PREFIX", "BIO"),
        )

    def apply_fast_mode(self) -> "Config":
        """
        Apply fast mode optimizations for quicker responses.

        Fast mode:
        - Disables multi-agent coordination (single agent)
        - Disables memory system (RAG, summaries, knowledge graph)
        - Reduces max tool rounds to 15
        - Keeps artifacts enabled for file tracking

        Returns self for chaining.
        """
        if not self.fast_mode:
            return self

        # Disable multi-agent
        self.enable_multi_agent = False

        # Disable memory overhead
        self.enable_memory = False
        self.enable_rag = False
        self.enable_summaries = False
        self.enable_knowledge_graph = False

        # Keep artifacts for file tracking
        self.enable_artifacts = True

        # Reduce tool rounds for faster completion
        self.max_tool_rounds = 15

        return self

    def validate(self) -> list[str]:
        """Validate configuration, return list of issues."""
        issues = []

        if not self.anthropic_api_key:
            issues.append("ANTHROPIC_API_KEY is not set")

        if not self.ncbi_email:
            issues.append(
                "NCBI_EMAIL is not set (recommended: NCBI requires email for E-utilities)"
            )

        workspace = Path(self.workspace_dir)
        if not workspace.exists():
            try:
                workspace.mkdir(parents=True, exist_ok=True)
            except PermissionError:
                issues.append(f"Cannot create workspace directory: {self.workspace_dir}")

        return issues
