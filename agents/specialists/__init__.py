"""
Specialist agents for multi-agent architecture.

Each specialist has focused expertise and a filtered tool set.
"""

from .pipeline_engineer import PipelineEngineerAgent
from .statistician import StatisticianAgent
from .literature_agent import LiteratureAgent
from .qc_reviewer import QCReviewerAgent
from .domain_expert import DomainExpertAgent

__all__ = [
    "PipelineEngineerAgent",
    "StatisticianAgent",
    "LiteratureAgent",
    "QCReviewerAgent",
    "DomainExpertAgent",
]


def get_specialist_class(specialist_type: str):
    """
    Get the specialist agent class for a given type.

    Args:
        specialist_type: String name of the specialist type

    Returns:
        The specialist agent class
    """
    mapping = {
        "pipeline_engineer": PipelineEngineerAgent,
        "statistician": StatisticianAgent,
        "literature_agent": LiteratureAgent,
        "qc_reviewer": QCReviewerAgent,
        "domain_expert": DomainExpertAgent,
    }
    return mapping.get(specialist_type)
