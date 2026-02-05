"""
Cloud & HPC Integration for BioAgent.

Provides execution backends for scaling bioinformatics workloads to:
- AWS Batch
- Google Cloud Life Sciences
- Azure Batch
- SLURM HPC clusters

Usage:
    from cloud import CloudExecutor, CloudConfig

    executor = CloudExecutor(config)
    job_id = executor.submit_job(workflow, resources)
    status = executor.get_job_status(job_id)
"""

from .config import CloudConfig, ResourceSpec, JobStatus
from .base import CloudExecutor, ExecutorBackend
from .aws import AWSBatchExecutor
from .gcp import GoogleLifeSciencesExecutor
from .azure import AzureBatchExecutor
from .slurm import SLURMExecutor

__all__ = [
    # Configuration
    "CloudConfig",
    "ResourceSpec",
    "JobStatus",
    # Executors
    "CloudExecutor",
    "ExecutorBackend",
    "AWSBatchExecutor",
    "GoogleLifeSciencesExecutor",
    "AzureBatchExecutor",
    "SLURMExecutor",
]
