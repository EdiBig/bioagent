"""
Code execution engine for Python, R, and Bash.

Executes code in sandboxed subprocesses with timeout support,
output capture, and error handling.
"""

import subprocess
import tempfile
import os
import sys
import signal
from pathlib import Path
from dataclasses import dataclass


@dataclass
class ExecutionResult:
    """Result of a code execution."""
    stdout: str
    stderr: str
    return_code: int
    timed_out: bool = False

    @property
    def success(self) -> bool:
        return self.return_code == 0 and not self.timed_out

    def to_string(self) -> str:
        """Format result for Claude to read."""
        parts = []
        if self.timed_out:
            parts.append("⚠️ EXECUTION TIMED OUT")
        if self.stdout.strip():
            parts.append(f"STDOUT:\n{self.stdout.strip()}")
        if self.stderr.strip():
            parts.append(f"STDERR:\n{self.stderr.strip()}")
        if not self.stdout.strip() and not self.stderr.strip():
            parts.append(f"(No output. Return code: {self.return_code})")
        elif self.return_code != 0:
            parts.append(f"Return code: {self.return_code}")
        return "\n\n".join(parts)


class CodeExecutor:
    """Executes code in sandboxed environments."""

    def __init__(
        self,
        workspace_dir: str = "/workspace",
        use_docker: bool = False,
        docker_image: str = "bioagent-tools:latest",
        max_output_chars: int = 50_000,
    ):
        self.workspace_dir = Path(workspace_dir)
        self.workspace_dir.mkdir(parents=True, exist_ok=True)
        self.use_docker = use_docker
        self.docker_image = docker_image
        self.max_output_chars = max_output_chars

        # Persistent Python session state (shared namespace across calls)
        self._python_globals: dict = {}

    def execute_python(self, code: str, timeout: int = 300) -> ExecutionResult:
        """Execute Python code."""
        # Write code to a temp file
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".py", dir=self.workspace_dir,
            delete=False, prefix="bioagent_py_", encoding="utf-8"
        ) as f:
            # Wrap code to handle matplotlib non-interactively
            # Use repr() to properly escape Windows paths with backslashes
            workspace_path = repr(str(self.workspace_dir))
            wrapped_code = (
                "# -*- coding: utf-8 -*-\n"
                "import matplotlib\n"
                "matplotlib.use('Agg')\n"
                "import warnings\n"
                "warnings.filterwarnings('ignore')\n"
                f"import os\nos.chdir({workspace_path})\n\n"
                f"{code}"
            )
            f.write(wrapped_code)
            script_path = f.name

        try:
            if self.use_docker:
                return self._run_in_docker(
                    f"python3 {os.path.basename(script_path)}",
                    timeout=timeout,
                )
            else:
                return self._run_subprocess(
                    [sys.executable, script_path],
                    timeout=timeout,
                    cwd=str(self.workspace_dir),
                )
        finally:
            os.unlink(script_path)

    def execute_r(self, code: str, timeout: int = 300) -> ExecutionResult:
        """Execute R code."""
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".R", dir=self.workspace_dir,
            delete=False, prefix="bioagent_r_", encoding="utf-8"
        ) as f:
            # Use forward slashes for R on Windows (R accepts both)
            workspace_path = str(self.workspace_dir).replace("\\", "/")
            wrapped_code = (
                f'setwd("{workspace_path}")\n'
                "options(warn = 1)\n\n"
                f"{code}"
            )
            f.write(wrapped_code)
            script_path = f.name

        try:
            if self.use_docker:
                return self._run_in_docker(
                    f"Rscript {os.path.basename(script_path)}",
                    timeout=timeout,
                )
            else:
                return self._run_subprocess(
                    ["Rscript", script_path],
                    timeout=timeout,
                    cwd=str(self.workspace_dir),
                )
        finally:
            os.unlink(script_path)

    def execute_bash(
        self, command: str, timeout: int = 600, working_dir: str | None = None
    ) -> ExecutionResult:
        """Execute a bash command."""
        cwd = working_dir or str(self.workspace_dir)

        if self.use_docker:
            return self._run_in_docker(command, timeout=timeout)
        else:
            return self._run_subprocess(
                ["bash", "-c", command],
                timeout=timeout,
                cwd=cwd,
            )

    def _run_subprocess(
        self, cmd: list[str], timeout: int, cwd: str | None = None,
    ) -> ExecutionResult:
        """Run a command as a subprocess with timeout."""
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=timeout,
                cwd=cwd,
                env={**os.environ, "PYTHONUNBUFFERED": "1"},
            )
            return ExecutionResult(
                stdout=self._truncate(result.stdout),
                stderr=self._truncate(result.stderr),
                return_code=result.returncode,
            )
        except subprocess.TimeoutExpired:
            return ExecutionResult(
                stdout="",
                stderr=f"Execution timed out after {timeout} seconds",
                return_code=-1,
                timed_out=True,
            )
        except FileNotFoundError as e:
            return ExecutionResult(
                stdout="",
                stderr=f"Command not found: {e}",
                return_code=-1,
            )
        except Exception as e:
            return ExecutionResult(
                stdout="",
                stderr=f"Execution error: {e}",
                return_code=-1,
            )

    def _run_in_docker(self, command: str, timeout: int = 600) -> ExecutionResult:
        """Run a command inside the Docker container."""
        docker_cmd = [
            "docker", "run", "--rm",
            "-v", f"{self.workspace_dir}:/workspace",
            "-w", "/workspace",
            "--memory", "8g",
            "--cpus", "4",
            self.docker_image,
            "bash", "-c", command,
        ]
        return self._run_subprocess(docker_cmd, timeout=timeout)

    def _truncate(self, text: str) -> str:
        """Truncate output to avoid overwhelming the context window."""
        if len(text) > self.max_output_chars:
            half = self.max_output_chars // 2
            return (
                text[:half]
                + f"\n\n... [TRUNCATED {len(text) - self.max_output_chars} chars] ...\n\n"
                + text[-half:]
            )
        return text
