"""
Coordinator agent for multi-agent architecture.

Orchestrates specialist agents, routes tasks, manages execution,
and synthesizes outputs into coherent responses.
"""

import json
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import datetime
from typing import Any

import anthropic

from .base import BaseAgent, SpecialistOutput, SpecialistType
from .context import AgentSessionCache, ContextBuilder, SpecialistContext
from .prompts import COORDINATOR_PROMPT
from .routing import RoutingResult, TaskRouter
from .tools import SPECIALIST_TOOLS, get_specialist_tools
from .specialists import (
    DomainExpertAgent,
    LiteratureAgent,
    PipelineEngineerAgent,
    QCReviewerAgent,
    StatisticianAgent,
    ResearchAgentSpecialist,
)


@dataclass
class CoordinatorResult:
    """
    Result from the coordinator's orchestration.

    Attributes:
        response: Final synthesized response text
        specialist_outputs: Outputs from each specialist that ran
        routing: The routing decision that was made
        execution_time: Total execution time in seconds
        metadata: Additional metadata
    """
    response: str
    specialist_outputs: list[SpecialistOutput]
    routing: RoutingResult
    execution_time: float
    metadata: dict[str, Any]


class CoordinatorAgent:
    """
    Orchestrates specialist agents to handle complex bioinformatics tasks.

    The coordinator:
    1. Routes tasks to appropriate specialist(s)
    2. Manages sequential or parallel execution
    3. Passes context between specialists
    4. Synthesizes outputs into a coherent response
    """

    # Mapping of specialist types to their agent classes
    SPECIALIST_CLASSES = {
        SpecialistType.PIPELINE_ENGINEER: PipelineEngineerAgent,
        SpecialistType.STATISTICIAN: StatisticianAgent,
        SpecialistType.LITERATURE_AGENT: LiteratureAgent,
        SpecialistType.QC_REVIEWER: QCReviewerAgent,
        SpecialistType.DOMAIN_EXPERT: DomainExpertAgent,
        SpecialistType.RESEARCH_AGENT: ResearchAgentSpecialist,
    }

    def __init__(
        self,
        client: anthropic.Anthropic,
        tool_handlers: dict[str, callable],
        memory=None,
        coordinator_model: str = "claude-sonnet-4-20250514",
        specialist_model: str = "claude-sonnet-4-20250514",
        qc_model: str = "claude-haiku-3-5-20241022",
        max_specialists: int = 3,
        enable_parallel: bool = True,
        verbose: bool = True,
    ):
        """
        Initialize the coordinator.

        Args:
            client: Anthropic API client
            tool_handlers: Dict mapping tool names to handler functions
            memory: Optional ContextManager for shared memory
            coordinator_model: Model for coordinator synthesis
            specialist_model: Model for specialist agents
            qc_model: Model for QC reviewer (lighter weight)
            max_specialists: Maximum specialists per query
            enable_parallel: Allow parallel specialist execution
            verbose: Print debug information
        """
        self.client = client
        self.tool_handlers = tool_handlers
        self.memory = memory
        self.coordinator_model = coordinator_model
        self.specialist_model = specialist_model
        self.qc_model = qc_model
        self.max_specialists = max_specialists
        self.enable_parallel = enable_parallel
        self.verbose = verbose

        # Initialize components
        self.router = TaskRouter(client=client, use_llm_fallback=True)
        self.context_builder = ContextBuilder(memory=memory)

        # Session cache for sharing state
        self.session_cache = AgentSessionCache(
            session_id=datetime.now().strftime("%Y%m%d_%H%M%S")
        )

        # Specialist agent instances (created on demand)
        self._specialists: dict[SpecialistType, BaseAgent] = {}

    def run(self, query: str, conversation_history: list[dict] | None = None) -> CoordinatorResult:
        """
        Process a user query through the multi-agent system.

        Args:
            query: User's query/task
            conversation_history: Optional conversation history

        Returns:
            CoordinatorResult with synthesized response
        """
        start_time = datetime.now()

        if self.verbose:
            self._log(f"\n{'='*60}")
            self._log(f"🎯 Coordinator: Processing query")
            self._log(f"{'='*60}")

        # Step 1: Route the query
        routing = self.router.route(query, max_specialists=self.max_specialists)

        if self.verbose:
            self._log(f"📍 Routing: primary={routing.primary.value}, "
                      f"secondary={[s.value for s in routing.secondary]}, "
                      f"confidence={routing.confidence:.2f}")

        # Step 2: Build context
        context = self.context_builder.build_context(
            user_query=query,
            conversation_history=conversation_history,
        )

        # Step 3: Execute specialists
        if routing.requires_parallel and self.enable_parallel:
            specialist_outputs = self._execute_parallel(routing, context)
        else:
            specialist_outputs = self._execute_sequential(routing, context)

        # Step 4: Synthesize outputs
        response = self._synthesize_outputs(query, specialist_outputs, routing)

        execution_time = (datetime.now() - start_time).total_seconds()

        if self.verbose:
            self._log(f"\n✅ Coordinator: Complete in {execution_time:.1f}s")

        return CoordinatorResult(
            response=response,
            specialist_outputs=specialist_outputs,
            routing=routing,
            execution_time=execution_time,
            metadata={
                "session_id": self.session_cache.session_id,
                "specialists_used": [o.specialist.value for o in specialist_outputs],
            },
        )

    def _execute_sequential(
        self,
        routing: RoutingResult,
        context: SpecialistContext,
    ) -> list[SpecialistOutput]:
        """Execute specialists sequentially, passing outputs forward."""
        outputs = []

        for specialist_type in routing.execution_order:
            if self.verbose:
                self._log(f"\n🔄 Running: {specialist_type.value}")

            # Get or create specialist
            specialist = self._get_specialist(specialist_type)

            # Build task with context
            task = context.user_query

            # Run specialist with previous outputs
            output = specialist.run(
                task=task,
                context=context,
                previous_outputs=outputs if outputs else None,
            )

            outputs.append(output)

            if self.verbose:
                self._log(f"   Status: {output.status}, Tools: {output.tools_used}")

            # Update session cache with any discoveries
            self._update_session_cache(output)

            # If specialist errored critically, stop
            if output.status == "error" and "critical" in output.error.lower():
                if self.verbose:
                    self._log(f"   ⚠️ Critical error, stopping pipeline")
                break

        return outputs

    def _execute_parallel(
        self,
        routing: RoutingResult,
        context: SpecialistContext,
    ) -> list[SpecialistOutput]:
        """Execute specialists in parallel where possible."""
        outputs = []

        # First, run primary specialist sequentially (might be needed by others)
        primary = routing.primary
        if self.verbose:
            self._log(f"\n🔄 Running primary: {primary.value}")

        primary_specialist = self._get_specialist(primary)
        primary_output = primary_specialist.run(
            task=context.user_query,
            context=context,
        )
        outputs.append(primary_output)
        self._update_session_cache(primary_output)

        # Then run secondary specialists in parallel
        if routing.secondary:
            if self.verbose:
                self._log(f"\n🔀 Running in parallel: {[s.value for s in routing.secondary]}")

            with ThreadPoolExecutor(max_workers=len(routing.secondary)) as executor:
                future_to_specialist = {}

                for specialist_type in routing.secondary:
                    specialist = self._get_specialist(specialist_type)

                    future = executor.submit(
                        specialist.run,
                        task=context.user_query,
                        context=context,
                        previous_outputs=[primary_output],
                    )
                    future_to_specialist[future] = specialist_type

                for future in as_completed(future_to_specialist):
                    specialist_type = future_to_specialist[future]
                    try:
                        output = future.result()
                        outputs.append(output)
                        self._update_session_cache(output)

                        if self.verbose:
                            self._log(f"   ✓ {specialist_type.value}: {output.status}")

                    except Exception as e:
                        # Create error output
                        outputs.append(SpecialistOutput(
                            specialist=specialist_type,
                            status="error",
                            summary=f"Execution failed: {str(e)}",
                            details="",
                            error=str(e),
                        ))
                        if self.verbose:
                            self._log(f"   ✗ {specialist_type.value}: Error - {e}")

        return outputs

    def _get_specialist(self, specialist_type: SpecialistType) -> BaseAgent:
        """Get or create a specialist agent instance."""
        if specialist_type not in self._specialists:
            agent_class = self.SPECIALIST_CLASSES[specialist_type]

            # Use lighter model for QC reviewer
            if specialist_type == SpecialistType.QC_REVIEWER:
                model = self.qc_model
            else:
                model = self.specialist_model

            self._specialists[specialist_type] = agent_class(
                client=self.client,
                model=model,
                tool_handlers=self.tool_handlers,
                memory=self.memory,
                verbose=self.verbose,
            )

        return self._specialists[specialist_type]

    def _synthesize_outputs(
        self,
        query: str,
        outputs: list[SpecialistOutput],
        routing: RoutingResult,
    ) -> str:
        """Synthesize specialist outputs into a coherent response."""
        # If only one specialist with successful output, return it directly
        if len(outputs) == 1 and outputs[0].is_successful:
            return outputs[0].details

        # If all specialists errored, return error summary
        if all(o.status == "error" for o in outputs):
            error_summary = "\n".join(
                f"- {o.specialist.value}: {o.error}"
                for o in outputs
            )
            return f"I encountered errors while processing your request:\n\n{error_summary}"

        # Build synthesis prompt
        synthesis_prompt = self._build_synthesis_prompt(query, outputs, routing)

        # Call Claude to synthesize
        try:
            response = self.client.messages.create(
                model=self.coordinator_model,
                max_tokens=8192,
                temperature=0.0,
                system=COORDINATOR_PROMPT,
                messages=[{
                    "role": "user",
                    "content": synthesis_prompt,
                }],
            )

            return response.content[0].text

        except Exception as e:
            # Fallback: concatenate outputs
            if self.verbose:
                self._log(f"   ⚠️ Synthesis error: {e}, using fallback")

            return self._fallback_synthesis(outputs)

    def _build_synthesis_prompt(
        self,
        query: str,
        outputs: list[SpecialistOutput],
        routing: RoutingResult,
    ) -> str:
        """Build the prompt for output synthesis."""
        parts = [
            f"## Original Query\n{query}",
            f"\n## Routing Decision\n{routing.reasoning}",
            "\n## Specialist Outputs\n",
        ]

        for output in outputs:
            status_icon = "✓" if output.is_successful else "✗"
            parts.append(
                f"\n### {output.specialist.value} ({status_icon} {output.status})\n"
                f"**Summary:** {output.summary}\n\n"
                f"**Details:**\n{output.details[:3000]}"
            )
            if output.error:
                parts.append(f"\n**Error:** {output.error}")

        parts.append("""

## Your Task

Synthesize the specialist outputs above into a single, coherent response for the user.

Guidelines:
1. Start with a clear summary of what was accomplished
2. Integrate findings from all specialists logically
3. Resolve any contradictions by favoring more confident/reliable sources
4. Highlight the most important findings
5. Include specific results, numbers, and data where available
6. Note any limitations or caveats
7. Suggest next steps if appropriate

Write the final response now:
""")

        return "\n".join(parts)

    def _fallback_synthesis(self, outputs: list[SpecialistOutput]) -> str:
        """Simple fallback synthesis when LLM fails."""
        parts = ["## Analysis Results\n"]

        for output in outputs:
            if output.is_successful:
                parts.append(f"### {output.specialist.value.replace('_', ' ').title()}\n")
                parts.append(output.details[:2000])
                parts.append("\n")

        # Add any errors at the end
        errors = [o for o in outputs if o.status == "error"]
        if errors:
            parts.append("\n## Errors Encountered\n")
            for error in errors:
                parts.append(f"- {error.specialist.value}: {error.error}\n")

        return "\n".join(parts)

    def _update_session_cache(self, output: SpecialistOutput):
        """Update session cache with discoveries from specialist output."""
        # Track tools used
        for tool in output.tools_used:
            self.session_cache.set_shared_data(f"used_{tool}", True)

        # Track artifacts
        for artifact in output.artifacts:
            self.session_cache.set_shared_data(f"artifact_{artifact}", output.specialist.value)

    def _log(self, message: str):
        """Print log message if verbose."""
        if self.verbose:
            print(message)

    # ── Direct Specialist Access ──────────────────────────────────────

    def run_specialist(
        self,
        specialist_type: SpecialistType,
        task: str,
        context: SpecialistContext | None = None,
    ) -> SpecialistOutput:
        """
        Run a specific specialist directly without routing.

        Args:
            specialist_type: Which specialist to run
            task: The task to perform
            context: Optional context

        Returns:
            SpecialistOutput from the specialist
        """
        specialist = self._get_specialist(specialist_type)

        if context is None:
            context = self.context_builder.build_context(user_query=task)

        return specialist.run(task=task, context=context)

    def get_routing_preview(self, query: str) -> RoutingResult:
        """
        Get routing decision without executing.

        Args:
            query: The query to route

        Returns:
            RoutingResult with the routing decision
        """
        return self.router.route(query, max_specialists=self.max_specialists)
