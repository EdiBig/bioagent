"""
Base classes for workflow engine integration.
"""

import os
import json
import subprocess
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any


class WorkflowStatus(Enum):
    """Status of a workflow execution."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class WorkflowResult:
    """Result from a workflow operation."""
    success: bool
    message: str
    workflow_id: str | None = None
    status: WorkflowStatus | None = None
    outputs: dict[str, Any] = field(default_factory=dict)
    logs: str = ""

    def to_string(self) -> str:
        """Format result for display."""
        parts = []
        status_str = self.status.value if self.status else "N/A"
        parts.append(f"Workflow [{status_str}]: {'Success' if self.success else 'Failed'}")

        if self.workflow_id:
            parts.append(f"ID: {self.workflow_id}")

        parts.append(f"\n{self.message}")

        if self.outputs:
            parts.append("\nOutputs:")
            for key, value in list(self.outputs.items())[:10]:
                parts.append(f"  {key}: {value}")

        if self.logs and len(self.logs) > 0:
            log_preview = self.logs[-2000:] if len(self.logs) > 2000 else self.logs
            parts.append(f"\nLogs (last 2000 chars):\n{log_preview}")

        return "\n".join(parts)


class WorkflowEngine(ABC):
    """Abstract base class for workflow engines."""

    def __init__(self, workspace_dir: str):
        self.workspace_dir = Path(workspace_dir)
        self.workflows_dir = self.workspace_dir / "workflows"
        self.workflows_dir.mkdir(parents=True, exist_ok=True)

    @abstractmethod
    def check_installation(self) -> tuple[bool, str]:
        """Check if the workflow engine is installed."""
        pass

    @abstractmethod
    def create_workflow(
        self,
        name: str,
        definition: str,
        params: dict[str, Any] | None = None,
    ) -> WorkflowResult:
        """Create a new workflow definition."""
        pass

    @abstractmethod
    def run_workflow(
        self,
        workflow_path: str,
        params: dict[str, Any] | None = None,
        resume: bool = False,
    ) -> WorkflowResult:
        """Execute a workflow."""
        pass

    @abstractmethod
    def get_status(self, workflow_id: str) -> WorkflowResult:
        """Get status of a running workflow."""
        pass

    @abstractmethod
    def get_outputs(self, workflow_id: str) -> WorkflowResult:
        """Get outputs from a completed workflow."""
        pass

    def _run_command(
        self,
        command: list[str],
        cwd: str | None = None,
        timeout: int = 3600,
        capture_output: bool = True,
    ) -> tuple[int, str, str]:
        """Run a shell command and return exit code, stdout, stderr."""
        try:
            result = subprocess.run(
                command,
                cwd=cwd or str(self.workspace_dir),
                capture_output=capture_output,
                text=True,
                timeout=timeout,
                shell=(os.name == 'nt'),  # Use shell on Windows
            )
            return result.returncode, result.stdout, result.stderr
        except subprocess.TimeoutExpired:
            return -1, "", f"Command timed out after {timeout} seconds"
        except Exception as e:
            return -1, "", str(e)

    def _generate_workflow_id(self, name: str) -> str:
        """Generate a unique workflow ID."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        return f"{name}_{timestamp}"
