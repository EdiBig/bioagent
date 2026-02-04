"""
BioAgent configuration.

Loads settings from environment variables and .env file.
"""

import os
import sys
from dataclasses import dataclass, field
from pathlib import Path


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
    max_tool_rounds: int = 25  # Max agentic loop iterations
    verbose: bool = True  # Print tool calls and results
    log_file: str | None = None  # Optional file to log interactions
    enable_extended_thinking: bool = False  # Use extended thinking for complex queries

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
            max_tool_rounds=int(os.getenv("BIOAGENT_MAX_ROUNDS", "25")),
            verbose=os.getenv("BIOAGENT_VERBOSE", "true").lower() == "true",
            log_file=os.getenv("BIOAGENT_LOG_FILE", None),
            enable_extended_thinking=os.getenv("BIOAGENT_EXTENDED_THINKING", "false").lower() == "true",
        )

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
