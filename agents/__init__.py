"""
Multi-agent architecture for BioAgent.

This module provides a Coordinator-Specialist architecture where a Coordinator
routes tasks to specialized agents, each with focused prompts and tool subsets.

Specialists:
- PipelineEngineerAgent: Workflow design, code execution, pipeline building
- StatisticianAgent: Statistical analysis, differential expression, enrichment
- LiteratureAgent: Database queries, literature search, biological context
- QCReviewerAgent: Quality control, validation, review of outputs
- DomainExpertAgent: Biological interpretation and domain expertise
"""

from .base import BaseAgent, SpecialistOutput, SpecialistType
from .coordinator import CoordinatorAgent
from .routing import TaskRouter, RoutingResult
from .context import SpecialistContext, AgentSessionCache
from .tools import get_specialist_tools, SPECIALIST_TOOLS
from .prompts import (
    COORDINATOR_PROMPT,
    PIPELINE_ENGINEER_PROMPT,
    STATISTICIAN_PROMPT,
    LITERATURE_AGENT_PROMPT,
    QC_REVIEWER_PROMPT,
    DOMAIN_EXPERT_PROMPT,
)

__all__ = [
    # Core classes
    "BaseAgent",
    "SpecialistOutput",
    "SpecialistType",
    "CoordinatorAgent",
    "TaskRouter",
    "RoutingResult",
    "SpecialistContext",
    "AgentSessionCache",
    # Tool utilities
    "get_specialist_tools",
    "SPECIALIST_TOOLS",
    # Prompts
    "COORDINATOR_PROMPT",
    "PIPELINE_ENGINEER_PROMPT",
    "STATISTICIAN_PROMPT",
    "LITERATURE_AGENT_PROMPT",
    "QC_REVIEWER_PROMPT",
    "DOMAIN_EXPERT_PROMPT",
]
