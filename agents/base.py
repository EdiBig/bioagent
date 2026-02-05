"""
Base classes for multi-agent architecture.

Defines the abstract base class for all specialist agents and the
structured output format they return.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any

import anthropic


class SpecialistType(Enum):
    """Types of specialist agents available."""
    PIPELINE_ENGINEER = "pipeline_engineer"
    STATISTICIAN = "statistician"
    LITERATURE_AGENT = "literature_agent"
    QC_REVIEWER = "qc_reviewer"
    DOMAIN_EXPERT = "domain_expert"
    COORDINATOR = "coordinator"


@dataclass
class SpecialistOutput:
    """
    Structured output from a specialist agent.

    Attributes:
        specialist: The type of specialist that produced this output
        status: Success/failure status ('success', 'partial', 'error')
        summary: Brief summary of what was accomplished
        details: Full detailed response
        confidence: Confidence score 0.0-1.0 in the results
        artifacts: List of artifact IDs produced during execution
        tools_used: List of tools that were called
        error: Error message if status is 'error'
        metadata: Additional metadata (timing, model used, etc.)
    """
    specialist: SpecialistType
    status: str  # 'success', 'partial', 'error'
    summary: str
    details: str
    confidence: float = 1.0
    artifacts: list[str] = field(default_factory=list)
    tools_used: list[str] = field(default_factory=list)
    error: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def is_successful(self) -> bool:
        """Check if the output indicates success."""
        return self.status in ('success', 'partial')

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "specialist": self.specialist.value,
            "status": self.status,
            "summary": self.summary,
            "details": self.details,
            "confidence": self.confidence,
            "artifacts": self.artifacts,
            "tools_used": self.tools_used,
            "error": self.error,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "SpecialistOutput":
        """Create from dictionary."""
        return cls(
            specialist=SpecialistType(data["specialist"]),
            status=data["status"],
            summary=data["summary"],
            details=data["details"],
            confidence=data.get("confidence", 1.0),
            artifacts=data.get("artifacts", []),
            tools_used=data.get("tools_used", []),
            error=data.get("error"),
            metadata=data.get("metadata", {}),
        )


class BaseAgent(ABC):
    """
    Abstract base class for all specialist agents.

    Each specialist agent:
    - Has a focused system prompt for their domain
    - Has access to a filtered subset of tools
    - Returns structured SpecialistOutput
    - Shares memory/context with other agents
    """

    def __init__(
        self,
        client: anthropic.Anthropic,
        model: str,
        tool_handlers: dict[str, callable],
        memory=None,
        max_tool_rounds: int = 15,
        verbose: bool = True,
    ):
        """
        Initialize the specialist agent.

        Args:
            client: Anthropic API client
            model: Model identifier to use
            tool_handlers: Dict mapping tool names to handler functions
            memory: Optional ContextManager for shared memory
            max_tool_rounds: Maximum agentic loop iterations
            verbose: Whether to print debug info
        """
        self.client = client
        self.model = model
        self.tool_handlers = tool_handlers
        self.memory = memory
        self.max_tool_rounds = max_tool_rounds
        self.verbose = verbose

        # Track execution state
        self._messages: list[dict] = []
        self._tools_used: list[str] = []
        self._artifacts: list[str] = []

    @property
    @abstractmethod
    def specialist_type(self) -> SpecialistType:
        """Return the specialist type for this agent."""
        pass

    @property
    @abstractmethod
    def system_prompt(self) -> str:
        """Return the system prompt for this specialist."""
        pass

    @property
    @abstractmethod
    def tool_names(self) -> list[str]:
        """Return list of tool names this specialist can use."""
        pass

    def run(
        self,
        task: str,
        context: "SpecialistContext | None" = None,
        previous_outputs: list[SpecialistOutput] | None = None,
    ) -> SpecialistOutput:
        """
        Execute a task and return structured output.

        Args:
            task: The task description/query
            context: Optional context from coordinator
            previous_outputs: Optional outputs from previous specialists

        Returns:
            SpecialistOutput with results
        """
        start_time = datetime.now()
        self._messages = []
        self._tools_used = []
        self._artifacts = []

        try:
            # Build the full prompt
            full_task = self._build_task_prompt(task, context, previous_outputs)
            self._messages.append({"role": "user", "content": full_task})

            # Run the agentic loop
            result = self._run_agent_loop()

            # Parse and return structured output
            return self._create_output(
                result=result,
                start_time=start_time,
                status="success" if result else "partial",
            )

        except Exception as e:
            return SpecialistOutput(
                specialist=self.specialist_type,
                status="error",
                summary=f"Error during execution: {str(e)}",
                details="",
                error=str(e),
                tools_used=self._tools_used,
                artifacts=self._artifacts,
                metadata={"duration_seconds": (datetime.now() - start_time).total_seconds()},
            )

    def _build_task_prompt(
        self,
        task: str,
        context: "SpecialistContext | None",
        previous_outputs: list[SpecialistOutput] | None,
    ) -> str:
        """Build the full task prompt including context and previous outputs."""
        parts = [task]

        # Add context if provided
        if context and context.memory_context:
            parts.append(f"\n\n## Relevant Context\n{context.memory_context}")

        # Add previous specialist outputs if provided
        if previous_outputs:
            parts.append("\n\n## Previous Specialist Results")
            for output in previous_outputs:
                parts.append(
                    f"\n### {output.specialist.value} ({output.status}):\n"
                    f"{output.summary}\n\n{output.details[:2000]}"
                )

        return "\n".join(parts)

    def _run_agent_loop(self) -> str:
        """Run the agentic tool-use loop."""
        from .tools import get_specialist_tools

        tools = get_specialist_tools(self.tool_names)

        for round_num in range(1, self.max_tool_rounds + 1):
            if self.verbose:
                self._log(f"  [{self.specialist_type.value}] Round {round_num}")

            # Call Claude
            response = self.client.messages.create(
                model=self.model,
                max_tokens=8192,
                system=self.system_prompt,
                tools=tools,
                messages=self._messages,
                temperature=0.0,
            )

            # Check stop conditions
            if response.stop_reason == "end_turn":
                # Extract final text
                final_text = self._extract_text(response)
                self._messages.append({"role": "assistant", "content": response.content})
                return final_text

            elif response.stop_reason == "tool_use":
                # Process tool calls
                tool_results = self._process_tool_calls(response)
                self._messages.append({"role": "assistant", "content": response.content})
                self._messages.append({"role": "user", "content": tool_results})

            else:
                # Unexpected stop reason
                return self._extract_text(response)

        # Max rounds exceeded
        return "Maximum tool rounds exceeded. Partial results may be available."

    def _process_tool_calls(self, response) -> list[dict]:
        """Process tool calls in the response."""
        tool_results = []

        for block in response.content:
            if block.type == "tool_use":
                tool_name = block.name
                tool_input = block.input
                tool_id = block.id

                # Track tool usage
                if tool_name not in self._tools_used:
                    self._tools_used.append(tool_name)

                if self.verbose:
                    self._log(f"    Tool: {tool_name}")

                # Execute the tool
                if tool_name in self.tool_handlers:
                    try:
                        result = self.tool_handlers[tool_name](tool_input)

                        # Track artifacts if saved
                        if tool_name == "memory_save_artifact" and "artifact_id" in str(result):
                            self._artifacts.append(tool_input.get("name", "unknown"))

                        # Update memory if available
                        if self.memory and not tool_name.startswith("memory_"):
                            try:
                                self.memory.on_tool_result(tool_name, tool_input, result)
                            except Exception:
                                pass

                    except Exception as e:
                        result = f"Tool execution error ({tool_name}): {e}"
                else:
                    result = f"Tool not available for this specialist: {tool_name}"

                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": tool_id,
                    "content": result if isinstance(result, str) else str(result),
                })

        return tool_results

    def _extract_text(self, response) -> str:
        """Extract text content from a response."""
        texts = []
        for block in response.content:
            if hasattr(block, "text"):
                texts.append(block.text)
        return "\n".join(texts)

    def _create_output(
        self,
        result: str,
        start_time: datetime,
        status: str,
    ) -> SpecialistOutput:
        """Create a SpecialistOutput from the agent result."""
        # Extract summary (first paragraph or first 200 chars)
        summary = result.split("\n\n")[0][:500] if result else "No result produced"

        return SpecialistOutput(
            specialist=self.specialist_type,
            status=status,
            summary=summary,
            details=result,
            confidence=0.9 if status == "success" else 0.6,
            tools_used=self._tools_used,
            artifacts=self._artifacts,
            metadata={
                "duration_seconds": (datetime.now() - start_time).total_seconds(),
                "model": self.model,
                "rounds": len([m for m in self._messages if m["role"] == "assistant"]),
            },
        )

    def _log(self, message: str):
        """Print log message if verbose."""
        if self.verbose:
            print(message)


# Import SpecialistContext here to avoid circular import
from .context import SpecialistContext  # noqa: E402
