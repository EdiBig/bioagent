"""
Inter-Agent Communication Protocols.

Defines message schemas and handlers for communication between
the Research Agent and other agents in the BioAgent system.
"""

from dataclasses import dataclass, field
from typing import Any, Optional
from datetime import datetime
import json


# ═══════════════════════════════════════════════════════════
# MESSAGE SCHEMAS
# ═══════════════════════════════════════════════════════════

@dataclass
class AgentMessage:
    """Base message between agents."""
    from_agent: str
    to_agent: str
    message_type: str
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    conversation_id: str = ""
    payload: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "from": self.from_agent,
            "to": self.to_agent,
            "type": self.message_type,
            "timestamp": self.timestamp,
            "conversation_id": self.conversation_id,
            "payload": self.payload,
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2)

    @classmethod
    def from_dict(cls, d: dict) -> "AgentMessage":
        return cls(
            from_agent=d.get("from", ""),
            to_agent=d.get("to", ""),
            message_type=d.get("type", ""),
            timestamp=d.get("timestamp", ""),
            conversation_id=d.get("conversation_id", ""),
            payload=d.get("payload", {}),
        )


@dataclass
class ResearchRequest(AgentMessage):
    """Request from Orchestrator to Research Agent."""
    message_type: str = "research_request"

    @property
    def research_question(self) -> str:
        return self.payload.get("research_question", "")

    @property
    def study_type(self) -> str:
        return self.payload.get("study_type", "literature_review")

    @property
    def scope(self) -> str:
        return self.payload.get("scope", "comprehensive")

    @property
    def agent_results(self) -> dict:
        """Results from other agents to contextualise."""
        return self.payload.get("agent_results", {})

    @property
    def output_format(self) -> list[str]:
        """Requested output formats: 'report', 'presentation', 'summary'."""
        return self.payload.get("output_format", ["report"])


@dataclass
class AdvisoryMessage(AgentMessage):
    """Advisory from Research Agent to another agent."""
    message_type: str = "advisory"

    @property
    def advisory_type(self) -> str:
        return self.payload.get("advisory_type", "")

    @property
    def message(self) -> str:
        return self.payload.get("message", "")

    @property
    def priority(self) -> str:
        return self.payload.get("priority", "medium")

    @property
    def supporting_papers(self) -> list[str]:
        return self.payload.get("supporting_papers", [])

    @property
    def recommended_action(self) -> str:
        return self.payload.get("recommended_action", "")


@dataclass
class ResearchOutput(AgentMessage):
    """Output from Research Agent back to Orchestrator."""
    message_type: str = "research_output"

    @property
    def report_markdown(self) -> str:
        return self.payload.get("report_markdown", "")

    @property
    def report_path(self) -> str:
        return self.payload.get("report_path", "")

    @property
    def presentation_path(self) -> str:
        return self.payload.get("presentation_path", "")

    @property
    def bibtex(self) -> str:
        return self.payload.get("bibtex", "")

    @property
    def summary(self) -> str:
        return self.payload.get("summary", "")

    @property
    def advisories(self) -> list[dict]:
        return self.payload.get("advisories", [])

    @property
    def papers_cited(self) -> int:
        return self.payload.get("papers_cited", 0)


@dataclass
class ContextUpdate(AgentMessage):
    """Context update from another agent to Research Agent."""
    message_type: str = "context_update"

    @property
    def source_agent(self) -> str:
        return self.from_agent

    @property
    def data_type(self) -> str:
        """e.g., 'de_results', 'pathway_enrichment', 'variant_annotations'."""
        return self.payload.get("data_type", "")

    @property
    def data_summary(self) -> str:
        return self.payload.get("data_summary", "")

    @property
    def key_findings(self) -> list[str]:
        return self.payload.get("key_findings", [])

    @property
    def file_paths(self) -> list[str]:
        return self.payload.get("file_paths", [])


# ═══════════════════════════════════════════════════════════
# MESSAGE BUILDERS
# ═══════════════════════════════════════════════════════════

class ResearchAgentMessageBuilder:
    """Helper to build messages from the Research Agent."""

    AGENT_NAME = "research_agent"

    @classmethod
    def advisory(cls,
                 target_agent: str,
                 advisory_type: str,
                 message: str,
                 priority: str = "medium",
                 supporting_papers: list[str] = None,
                 recommended_action: str = "",
                 conversation_id: str = "") -> AdvisoryMessage:
        """Build an advisory message to another agent."""
        return AdvisoryMessage(
            from_agent=cls.AGENT_NAME,
            to_agent=target_agent,
            conversation_id=conversation_id,
            payload={
                "advisory_type": advisory_type,
                "message": message,
                "priority": priority,
                "supporting_papers": supporting_papers or [],
                "recommended_action": recommended_action,
            }
        )

    @classmethod
    def research_output(cls,
                        conversation_id: str = "",
                        report_markdown: str = "",
                        report_path: str = "",
                        presentation_path: str = "",
                        bibtex: str = "",
                        summary: str = "",
                        advisories: list[dict] = None,
                        papers_cited: int = 0) -> ResearchOutput:
        """Build a research output message."""
        return ResearchOutput(
            from_agent=cls.AGENT_NAME,
            to_agent="orchestrator",
            conversation_id=conversation_id,
            payload={
                "report_markdown": report_markdown,
                "report_path": report_path,
                "presentation_path": presentation_path,
                "bibtex": bibtex,
                "summary": summary,
                "advisories": advisories or [],
                "papers_cited": papers_cited,
            }
        )


# ═══════════════════════════════════════════════════════════
# MESSAGE QUEUE (simple in-memory for single-process)
# ═══════════════════════════════════════════════════════════

class MessageQueue:
    """
    Simple in-memory message queue for inter-agent communication.

    For production, replace with Redis, RabbitMQ, or similar.
    """

    def __init__(self):
        self._queues: dict[str, list[AgentMessage]] = {}

    def send(self, message: AgentMessage):
        """Send a message to an agent's queue."""
        target = message.to_agent
        if target not in self._queues:
            self._queues[target] = []
        self._queues[target].append(message)

    def receive(self, agent_name: str,
                message_type: str = None) -> list[AgentMessage]:
        """Receive all pending messages for an agent."""
        if agent_name not in self._queues:
            return []

        messages = self._queues[agent_name]
        if message_type:
            messages = [m for m in messages if m.message_type == message_type]

        # Remove received messages from queue
        if message_type:
            self._queues[agent_name] = [
                m for m in self._queues[agent_name]
                if m.message_type != message_type
            ]
        else:
            self._queues[agent_name] = []

        return messages

    def peek(self, agent_name: str) -> int:
        """Check how many messages are pending for an agent."""
        return len(self._queues.get(agent_name, []))

    def clear(self, agent_name: str = None):
        """Clear message queue(s)."""
        if agent_name:
            self._queues[agent_name] = []
        else:
            self._queues.clear()
