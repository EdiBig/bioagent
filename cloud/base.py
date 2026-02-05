"""
Base cloud executor class.

Defines the interface for all cloud/HPC execution backends.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any
import json
import uuid

from .config import CloudConfig, ResourceSpec, JobStatus, JobInfo


class ExecutorBackend(Enum):
    """Available execution backends."""
    AWS_BATCH = "aws_batch"
    GCP_LIFE_SCIENCES = "gcp_life_sciences"
    AZURE_BATCH = "azure_batch"
    SLURM = "slurm"
    LOCAL = "local"


class BaseExecutor(ABC):
    """
    Abstract base class for cloud executors.

    All cloud backends must implement these methods.
    """

    def __init__(self, config: CloudConfig):
        self.config = config
        self.jobs: dict[str, JobInfo] = {}

    @property
    @abstractmethod
    def backend(self) -> ExecutorBackend:
        """Return the backend type."""
        pass

    @abstractmethod
    def submit_job(
        self,
        command: str | list[str],
        resources: ResourceSpec | None = None,
        name: str | None = None,
        environment: dict[str, str] | None = None,
        input_files: list[str] | None = None,
        output_path: str | None = None,
        container: str | None = None,
    ) -> str:
        """
        Submit a job for execution.

        Args:
            command: Command to execute
            resources: Resource requirements
            name: Job name
            environment: Environment variables
            input_files: Files to stage to the job
            output_path: Where to store outputs
            container: Container image to use

        Returns:
            Job ID
        """
        pass

    @abstractmethod
    def get_job_status(self, job_id: str) -> JobInfo:
        """
        Get the status of a job.

        Args:
            job_id: Job identifier

        Returns:
            JobInfo with current status
        """
        pass

    @abstractmethod
    def cancel_job(self, job_id: str) -> bool:
        """
        Cancel a running job.

        Args:
            job_id: Job identifier

        Returns:
            True if cancelled successfully
        """
        pass

    @abstractmethod
    def get_job_logs(self, job_id: str, tail: int = 100) -> str:
        """
        Get job execution logs.

        Args:
            job_id: Job identifier
            tail: Number of lines from end

        Returns:
            Log content
        """
        pass

    @abstractmethod
    def list_jobs(
        self,
        status: JobStatus | None = None,
        limit: int = 100,
    ) -> list[JobInfo]:
        """
        List jobs.

        Args:
            status: Filter by status
            limit: Maximum number of jobs

        Returns:
            List of JobInfo
        """
        pass

    def submit_workflow(
        self,
        workflow_file: str,
        inputs: dict[str, Any] | None = None,
        resources: ResourceSpec | None = None,
        workflow_engine: str = "nextflow",
    ) -> str:
        """
        Submit a workflow (Nextflow/Snakemake) for execution.

        Args:
            workflow_file: Path to workflow file
            inputs: Workflow inputs
            resources: Resource requirements
            workflow_engine: Engine to use (nextflow, snakemake)

        Returns:
            Job ID
        """
        if workflow_engine == "nextflow":
            cmd = self._build_nextflow_command(workflow_file, inputs)
        elif workflow_engine == "snakemake":
            cmd = self._build_snakemake_command(workflow_file, inputs)
        else:
            raise ValueError(f"Unknown workflow engine: {workflow_engine}")

        return self.submit_job(
            command=cmd,
            resources=resources,
            name=f"workflow-{Path(workflow_file).stem}",
        )

    def _build_nextflow_command(
        self,
        workflow_file: str,
        inputs: dict[str, Any] | None,
    ) -> str:
        """Build Nextflow execution command."""
        cmd = f"nextflow run {workflow_file}"

        if inputs:
            for key, value in inputs.items():
                cmd += f" --{key} {value}"

        # Add cloud-specific profile
        if self.backend == ExecutorBackend.AWS_BATCH:
            cmd += " -profile aws"
        elif self.backend == ExecutorBackend.GCP_LIFE_SCIENCES:
            cmd += " -profile gcp"
        elif self.backend == ExecutorBackend.AZURE_BATCH:
            cmd += " -profile azure"

        return cmd

    def _build_snakemake_command(
        self,
        workflow_file: str,
        inputs: dict[str, Any] | None,
    ) -> str:
        """Build Snakemake execution command."""
        cmd = f"snakemake -s {workflow_file} --cores all"

        if inputs:
            config_items = " ".join(f"{k}={v}" for k, v in inputs.items())
            cmd += f" --config {config_items}"

        return cmd

    def wait_for_job(
        self,
        job_id: str,
        poll_interval: int = 30,
        timeout: int | None = None,
    ) -> JobInfo:
        """
        Wait for a job to complete.

        Args:
            job_id: Job identifier
            poll_interval: Seconds between status checks
            timeout: Maximum wait time in seconds

        Returns:
            Final JobInfo
        """
        import time

        start_time = time.time()
        while True:
            info = self.get_job_status(job_id)

            if info.status in (JobStatus.SUCCEEDED, JobStatus.FAILED, JobStatus.CANCELLED):
                return info

            if timeout and (time.time() - start_time) > timeout:
                raise TimeoutError(f"Job {job_id} did not complete within {timeout} seconds")

            time.sleep(poll_interval)

    def estimate_cost(
        self,
        resources: ResourceSpec,
        duration_hours: float,
    ) -> dict[str, float]:
        """
        Estimate job cost.

        Args:
            resources: Resource specification
            duration_hours: Expected duration

        Returns:
            Cost estimates by instance type
        """
        # Base pricing (approximate, varies by region)
        pricing = {
            "on_demand": {
                "vcpu_hour": 0.05,
                "memory_gb_hour": 0.005,
                "gpu_hour": 1.0,
            },
            "spot": {
                "vcpu_hour": 0.015,
                "memory_gb_hour": 0.002,
                "gpu_hour": 0.3,
            },
        }

        estimates = {}
        for price_type, rates in pricing.items():
            cpu_cost = resources.vcpus * rates["vcpu_hour"] * duration_hours
            mem_cost = resources.memory_gb * rates["memory_gb_hour"] * duration_hours
            gpu_cost = resources.gpu_count * rates["gpu_hour"] * duration_hours
            estimates[price_type] = round(cpu_cost + mem_cost + gpu_cost, 2)

        return estimates

    def _generate_job_id(self, prefix: str = "job") -> str:
        """Generate unique job ID."""
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        unique = str(uuid.uuid4())[:8]
        return f"{prefix}-{timestamp}-{unique}"


class CloudExecutor:
    """
    Unified cloud executor that supports multiple backends.

    Automatically selects the appropriate backend based on configuration.
    """

    def __init__(self, config: CloudConfig | None = None):
        self.config = config or CloudConfig.from_env()
        self._executors: dict[ExecutorBackend, BaseExecutor] = {}
        self._init_executors()

    def _init_executors(self):
        """Initialize available executors based on configuration."""
        from .aws import AWSBatchExecutor
        from .gcp import GoogleLifeSciencesExecutor
        from .azure import AzureBatchExecutor
        from .slurm import SLURMExecutor

        if self.config.is_aws_configured():
            self._executors[ExecutorBackend.AWS_BATCH] = AWSBatchExecutor(self.config)

        if self.config.is_gcp_configured():
            self._executors[ExecutorBackend.GCP_LIFE_SCIENCES] = GoogleLifeSciencesExecutor(self.config)

        if self.config.is_azure_configured():
            self._executors[ExecutorBackend.AZURE_BATCH] = AzureBatchExecutor(self.config)

        if self.config.is_slurm_configured():
            self._executors[ExecutorBackend.SLURM] = SLURMExecutor(self.config)

    def get_available_backends(self) -> list[ExecutorBackend]:
        """Return list of configured backends."""
        return list(self._executors.keys())

    def get_executor(self, backend: ExecutorBackend | str) -> BaseExecutor:
        """Get executor for specific backend."""
        if isinstance(backend, str):
            backend = ExecutorBackend(backend)

        if backend not in self._executors:
            raise ValueError(f"Backend {backend.value} is not configured")

        return self._executors[backend]

    def run_on_aws_batch(
        self,
        command: str | list[str],
        resources: ResourceSpec | None = None,
        **kwargs,
    ) -> str:
        """Run a job on AWS Batch."""
        executor = self.get_executor(ExecutorBackend.AWS_BATCH)
        return executor.submit_job(command, resources, **kwargs)

    def run_on_google_life_sciences(
        self,
        command: str | list[str],
        resources: ResourceSpec | None = None,
        **kwargs,
    ) -> str:
        """Run a job on Google Cloud Life Sciences."""
        executor = self.get_executor(ExecutorBackend.GCP_LIFE_SCIENCES)
        return executor.submit_job(command, resources, **kwargs)

    def run_on_azure_batch(
        self,
        command: str | list[str],
        resources: ResourceSpec | None = None,
        **kwargs,
    ) -> str:
        """Run a job on Azure Batch."""
        executor = self.get_executor(ExecutorBackend.AZURE_BATCH)
        return executor.submit_job(command, resources, **kwargs)

    def run_on_slurm(
        self,
        script: str,
        partition: str | None = None,
        resources: ResourceSpec | None = None,
        **kwargs,
    ) -> str:
        """Run a job on SLURM cluster."""
        executor = self.get_executor(ExecutorBackend.SLURM)
        if partition:
            kwargs["partition"] = partition
        return executor.submit_job(script, resources, **kwargs)

    def submit_job(
        self,
        command: str | list[str],
        backend: ExecutorBackend | str | None = None,
        resources: ResourceSpec | None = None,
        **kwargs,
    ) -> str:
        """
        Submit a job to the best available backend.

        Args:
            command: Command to execute
            backend: Specific backend to use (auto-selects if None)
            resources: Resource requirements
            **kwargs: Additional arguments

        Returns:
            Job ID
        """
        if backend:
            executor = self.get_executor(backend)
        else:
            executor = self._select_best_executor(resources)

        return executor.submit_job(command, resources, **kwargs)

    def _select_best_executor(self, resources: ResourceSpec | None) -> BaseExecutor:
        """Select the best executor based on resources and availability."""
        if not self._executors:
            raise RuntimeError("No cloud backends are configured")

        # Prefer SLURM for GPU workloads if available
        if resources and resources.gpu_count > 0:
            if ExecutorBackend.SLURM in self._executors:
                return self._executors[ExecutorBackend.SLURM]

        # Prefer spot instances if configured
        if self.config.prefer_spot:
            if ExecutorBackend.AWS_BATCH in self._executors:
                return self._executors[ExecutorBackend.AWS_BATCH]
            if ExecutorBackend.GCP_LIFE_SCIENCES in self._executors:
                return self._executors[ExecutorBackend.GCP_LIFE_SCIENCES]

        # Return first available
        return next(iter(self._executors.values()))

    def get_job_status(self, job_id: str, backend: ExecutorBackend | str | None = None) -> JobInfo:
        """Get job status from appropriate backend."""
        if backend:
            executor = self.get_executor(backend)
            return executor.get_job_status(job_id)

        # Search all backends
        for executor in self._executors.values():
            try:
                return executor.get_job_status(job_id)
            except Exception:
                continue

        raise ValueError(f"Job {job_id} not found in any backend")

    def cancel_job(self, job_id: str, backend: ExecutorBackend | str | None = None) -> bool:
        """Cancel a job."""
        if backend:
            executor = self.get_executor(backend)
            return executor.cancel_job(job_id)

        # Search all backends
        for executor in self._executors.values():
            try:
                if executor.cancel_job(job_id):
                    return True
            except Exception:
                continue

        return False

    def get_job_logs(self, job_id: str, backend: ExecutorBackend | str | None = None, tail: int = 100) -> str:
        """Get job logs."""
        if backend:
            executor = self.get_executor(backend)
            return executor.get_job_logs(job_id, tail)

        # Search all backends
        for executor in self._executors.values():
            try:
                return executor.get_job_logs(job_id, tail)
            except Exception:
                continue

        raise ValueError(f"Logs for job {job_id} not found")

    def list_all_jobs(self, status: JobStatus | None = None, limit: int = 100) -> dict[str, list[JobInfo]]:
        """List jobs from all backends."""
        results = {}
        for backend, executor in self._executors.items():
            try:
                jobs = executor.list_jobs(status, limit)
                results[backend.value] = jobs
            except Exception as e:
                results[backend.value] = []

        return results
