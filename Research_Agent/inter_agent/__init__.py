"""Inter-agent communication protocols."""

from .protocols import (
    AgentMessage,
    ResearchRequest,
    ResearchOutput,
    AdvisoryMessage,
    ContextUpdate,
    MessageQueue,
    ResearchAgentMessageBuilder,
)

__all__ = [
    "AgentMessage",
    "ResearchRequest",
    "ResearchOutput",
    "AdvisoryMessage",
    "ContextUpdate",
    "MessageQueue",
    "ResearchAgentMessageBuilder",
]
